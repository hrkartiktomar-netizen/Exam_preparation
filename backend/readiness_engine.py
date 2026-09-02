"""Phase 4: Readiness engine for exam score prediction and readiness estimation.

Per Context7 docs for Python: Use dataclasses with validation, handle statistical
calculations with overflow guards, return percentages as 0-100 integers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import database as db


@dataclass
class ReadinessEstimate:
    """Readiness prediction output."""

    readiness_percentage: int  # 0-100
    final_score_estimate: int  # 0-200 (exam max)
    days_to_exam: int
    weak_areas_count: int
    confidence: str  # "HIGH", "MEDIUM", "LOW"

    def validate(self) -> None:
        """Validate readiness estimate."""
        if not 0 <= self.readiness_percentage <= 100:
            raise ValueError(f"readiness_percentage must be 0-100, got {self.readiness_percentage}")
        if not 0 <= self.final_score_estimate <= 200:
            raise ValueError(f"final_score_estimate must be 0-200, got {self.final_score_estimate}")
        if self.days_to_exam < 1:
            raise ValueError(f"days_to_exam must be >= 1")
        if self.weak_areas_count < 0:
            raise ValueError(f"weak_areas_count must be >= 0")


@dataclass
class ScorePredictionByTopic:
    """Per-topic score prediction."""

    topic: str
    predicted_score: int  # 0-200 (max possible for that topic's weightage)
    confidence_interval: tuple[int, int]  # (lower, upper) bounds
    projection_days: int  # how many days for this prediction


def calculate_readiness_estimate(
    user_id: str,
    target_score: int = 130,  # Out of 200 (65%)
    days_to_exam: int = 28,
) -> ReadinessEstimate:
    """Estimate probability of achieving target score at current trajectory.

    Formula (from PROJECT_REFACTOR_PLAN.xml Week 4):
    1. Calculate trajectory: (current_avg - initial_score) / days_elapsed = delta_per_day
    2. Estimate final score: current_avg_accuracy × topic_weightage × 200
    3. Estimate readiness: P(final_score >= target_score) using normal distribution

    Per Context7 docs: Validate inputs, handle edge cases (no data), guard against overflow.
    """
    try:
        if target_score < 0 or target_score > 200:
            raise ValueError(f"target_score must be 0-200, got {target_score}")
        if days_to_exam < 1:
            raise ValueError(f"days_to_exam must be >= 1, got {days_to_exam}")

        # Get user's performance history
        history = db.get_user_performance_history(user_id)
        if not history or len(history) < 2:
            # Insufficient data for prediction
            return ReadinessEstimate(
                readiness_percentage=50,  # No data = 50% confidence
                final_score_estimate=100,
                days_to_exam=days_to_exam,
                weak_areas_count=len(db.get_weak_topics_for_user(user_id)),
                confidence="LOW",
            )

        # Calculate trend: delta_per_day
        earliest = history[0]
        latest = history[-1]
        earliest_date = datetime.fromisoformat(earliest["tested_at"])
        latest_date = datetime.fromisoformat(latest["tested_at"])
        days_elapsed = max(1, (latest_date - earliest_date).days)

        initial_score = earliest["total_score"]
        current_score = latest["total_score"]
        score_delta = current_score - initial_score
        delta_per_day = score_delta / days_elapsed

        # Plan v6 6.2: exponential smoothing (alpha=0.35) over the score history.
        # This anchors the projection base on a smoothed current level that weights
        # recent runs more heavily without overreacting to a single outlier score.
        alpha = 0.35
        smoothed_score = float(history[0]["total_score"])
        for entry in history[1:]:
            smoothed_score = alpha * float(entry["total_score"]) + (1.0 - alpha) * smoothed_score

        # Project forward from the smoothed level using the observed trend.
        projected_score = smoothed_score + (delta_per_day * days_to_exam)

        # Plan v6 6.2: aggregate + gating mapping. Mock history scores are on the
        # 0-100 objective (Paper-2) scale; the Phase-II merit formula is
        # Paper-1 descriptive × 1/3 + Paper-2 objective × 2/3, and a paper below
        # its cut-off eliminates the candidate regardless of aggregate.
        paper2_marks = max(0.0, min(100.0, float(projected_score)))
        gate_failure = None
        if paper2_marks < 40.0:
            gate_failure = "PAPER2_CUTOFF"
        descriptive_perf = db.latest_descriptive_performance()
        if descriptive_perf:
            paper1_marks = float(descriptive_perf.get("total_pct") or 0.0)
            cutoff = descriptive_perf.get("cutoff_pct")
            if cutoff is not None and paper1_marks < float(cutoff):
                gate_failure = gate_failure or "PAPER1_CUTOFF"
            aggregate_marks = paper1_marks * (1.0 / 3.0) + paper2_marks * (2.0 / 3.0)
            # Re-express the estimate on the engine's 0-200 scale (both papers).
            final_score_estimate = max(0, min(200, int(round(paper1_marks + paper2_marks))))
        else:
            aggregate_marks = paper2_marks
            final_score_estimate = max(0, min(200, int(projected_score)))

        # Readiness: P(aggregate >= target), bands kept from the original heuristic.
        target_aggregate = (target_score / 200.0) * 100.0
        if aggregate_marks >= target_aggregate:
            readiness_pct = min(100, 50 + int(20 * (aggregate_marks - target_aggregate) / 10))
            confidence = "HIGH" if aggregate_marks >= target_aggregate + 20 else "MEDIUM"
        else:
            gap = target_aggregate - aggregate_marks
            readiness_pct = max(0, 50 - int(50 * gap / target_aggregate))
            confidence = "LOW"
        if gate_failure:
            readiness_pct = min(readiness_pct, 25)
            confidence = "LOW"

        # Count weak areas (accuracy < 60%)
        weak_areas = db.get_weak_topics_for_user(user_id)
        weak_count = len(weak_areas)

        estimate = ReadinessEstimate(
            readiness_percentage=readiness_pct,
            final_score_estimate=final_score_estimate,
            days_to_exam=days_to_exam,
            weak_areas_count=weak_count,
            confidence=confidence,
        )
        estimate.validate()
        return estimate

    except ValueError as e:
        raise ValueError(f"Invalid readiness parameters: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to calculate readiness: {e}") from e


def get_score_prediction_by_topic(user_id: str) -> dict[str, ScorePredictionByTopic]:
    """Predict scores by topic based on current accuracy and historical trend.

    Per Context7 docs: Return dict mapping topic_id → prediction, handle missing topics.
    """
    predictions: dict[str, ScorePredictionByTopic] = {}
    try:
        # Get all topics with user performance
        topic_stats = db.get_topic_stats_for_user(user_id)

        for topic_stat in topic_stats:
            topic_id = topic_stat["topic_id"]
            accuracy_pct = topic_stat["accuracy_pct"]
            total_attempts = topic_stat.get("total_attempts", 1)

            try:
                # Simple prediction: accuracy-based score estimate
                # Each topic worth approximately 200/22 ≈ 9 points max
                topic_max_score = 9

                # Base prediction on current accuracy
                predicted = int((accuracy_pct / 100) * topic_max_score)

                # Confidence interval: ±2 points
                lower = max(0, predicted - 2)
                upper = min(topic_max_score, predicted + 2)

                # Calculate projection days: when will accuracy stabilize?
                if total_attempts < 5:
                    projection_days = 14  # Still learning
                elif total_attempts < 15:
                    projection_days = 7  # Converging
                else:
                    projection_days = 3  # Stable

                predictions[topic_id] = ScorePredictionByTopic(
                    topic=topic_id,
                    predicted_score=predicted,
                    confidence_interval=(lower, upper),
                    projection_days=projection_days,
                )
            except Exception as e:
                print(f"⚠️ Failed prediction for {topic_id}: {e}")
                continue

        return predictions

    except Exception as e:
        print(f"⚠️ Failed to get score predictions: {e}")
        return {}


def is_ready_for_exam(user_id: str, target_score: int = 130, cutoff_pct: int = 70) -> bool:
    """Check if user is ready to take the exam.

    Readiness check: readiness_percentage >= cutoff_pct

    Per Context7 docs: Simple predicate function, handle all exceptions gracefully.
    """
    try:
        estimate = calculate_readiness_estimate(user_id, target_score=target_score)
        return estimate.readiness_percentage >= cutoff_pct
    except Exception as e:
        print(f"⚠️ Readiness check failed: {e}")
        return False
