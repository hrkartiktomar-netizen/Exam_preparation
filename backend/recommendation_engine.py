"""Phase 4: Recommendation engine for autonomous next-action suggestions.

Per Context7 docs for Python: Use Enum for decision states, validated data classes for
business logic inputs/outputs, proper error handling with custom exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import database as db


class RecommendationAction(str, Enum):
    """Recommendation actions per decision tree."""

    DRILL_CRITICAL = "DRILL_CRITICAL"
    MOCK = "MOCK"
    AMENDMENT_REVIEW = "AMENDMENT_REVIEW"
    ESSAY = "ESSAY"
    REVIEW = "REVIEW"
    # Plan v6 6.3: descriptive and replay actions.
    DRILL_PRECIS = "DRILL_PRECIS"
    DRILL_RC = "DRILL_RC"
    REPLAY_WRONG = "REPLAY_WRONG"


@dataclass
class AccuracySnapshot:
    """User accuracy data at a point in time."""

    topic: str
    accuracy_pct: float
    total_attempts: int
    last_improvement_at: str | None = None
    days_since_improvement: int | None = None

    def validate(self) -> None:
        """Validate accuracy snapshot data."""
        if not 0 <= self.accuracy_pct <= 100:
            raise ValueError(f"accuracy_pct must be 0-100, got {self.accuracy_pct}")
        if self.total_attempts < 0:
            raise ValueError(f"total_attempts must be >= 0, got {self.total_attempts}")

    def __post_init__(self) -> None:
        """Validate accuracy snapshot data at construction."""
        self.validate()


@dataclass
class Recommendation:
    """Recommendation output: next action for user."""

    action: RecommendationAction
    topic: str
    reason: str
    priority: int  # 5-10, where 10 is most urgent
    estimated_duration_minutes: int
    estimated_question_count: int

    def validate(self) -> None:
        """Validate recommendation is well-formed."""
        if not 5 <= self.priority <= 10:
            raise ValueError(f"priority must be 5-10, got {self.priority}")
        if self.estimated_duration_minutes < 1:
            raise ValueError(f"estimated_duration_minutes must be >= 1")
        if self.estimated_question_count < 1:
            raise ValueError(f"estimated_question_count must be >= 1")


def calculate_next_action(
    user_id: str,
    topic: str,
    accuracy_snapshot: AccuracySnapshot,
) -> Recommendation:
    """Calculate next recommended action per decision tree.

    Decision Tree (from PROJECT_REFACTOR_PLAN.xml Week 4):
    - IF accuracy < 40% AND attempts >= 5 → DRILL_CRITICAL (priority 10)
    - ELIF 40% <= accuracy < 60% AND no improvement 3 days → MOCK (priority 8)
    - ELIF 60% <= accuracy < 75% AND amendments exist → AMENDMENT_REVIEW (priority 7)
    - ELIF 75% <= accuracy < 90% → ESSAY (priority 6)
    - ELSE → REVIEW (priority 5)

    Per Context7 docs for Python: Validate inputs, handle errors explicitly,
    return validated output.
    """
    try:
        # Validate input
        accuracy_snapshot.validate()

        # Plan v6 6.3: descriptive components get their own drill actions. When the
        # weakest area is a Paper-1 descriptive component, recommend the matching
        # descriptive drill rather than a generic objective drill.
        if accuracy_snapshot.accuracy_pct < 60:
            if topic == "SUBJ_PRECIS":
                return Recommendation(
                    action=RecommendationAction.DRILL_PRECIS,
                    topic=topic,
                    reason=f"Précis accuracy {accuracy_snapshot.accuracy_pct:.1f}% - practice timed précis (120-130 IFSCA / 140-160 SEBI words)",
                    priority=9,
                    estimated_duration_minutes=20,
                    estimated_question_count=1,
                )
            if topic == "SUBJ_RC":
                return Recommendation(
                    action=RecommendationAction.DRILL_RC,
                    topic=topic,
                    reason=f"Reading comprehension accuracy {accuracy_snapshot.accuracy_pct:.1f}% - practice own-words comprehension answers",
                    priority=9,
                    estimated_duration_minutes=20,
                    estimated_question_count=3,
                )

        # Rule 1: Critical drill for very weak topics
        if accuracy_snapshot.accuracy_pct < 40 and accuracy_snapshot.total_attempts >= 5:
            return Recommendation(
                action=RecommendationAction.DRILL_CRITICAL,
                topic=topic,
                reason=f"Critical drilling needed: {accuracy_snapshot.accuracy_pct:.1f}% accuracy after {accuracy_snapshot.total_attempts} attempts",
                priority=10,
                estimated_duration_minutes=15,
                estimated_question_count=10,
            )

        # Rule 2: Mock for stalled progress
        if (
            40 <= accuracy_snapshot.accuracy_pct < 60
            and accuracy_snapshot.days_since_improvement is not None
            and accuracy_snapshot.days_since_improvement >= 3
        ):
            return Recommendation(
                action=RecommendationAction.MOCK,
                topic=topic,
                reason=f"No improvement for {accuracy_snapshot.days_since_improvement} days at {accuracy_snapshot.accuracy_pct:.1f}% - take a mock to assess",
                priority=8,
                estimated_duration_minutes=60,
                estimated_question_count=50,
            )

        # Rule 3: Amendment review for moderate topics with recent amendments
        if 60 <= accuracy_snapshot.accuracy_pct < 75:
            try:
                amendments_count = db.get_amendments_for_topic_count(topic)
                if amendments_count > 0:
                    return Recommendation(
                        action=RecommendationAction.AMENDMENT_REVIEW,
                        topic=topic,
                        reason=f"{amendments_count} amendments released for {topic} - review at {accuracy_snapshot.accuracy_pct:.1f}% accuracy",
                        priority=7,
                        estimated_duration_minutes=20,
                        estimated_question_count=amendments_count * 3,
                    )
            except Exception as e:
                # If amendment check fails, fall through to next rule
                print(f"⚠️ Amendment check failed for {topic}: {e}")

        # Rule 4: Essay for high-performing topics
        if 75 <= accuracy_snapshot.accuracy_pct < 90:
            return Recommendation(
                action=RecommendationAction.ESSAY,
                topic=topic,
                reason=f"Strong performance at {accuracy_snapshot.accuracy_pct:.1f}% - solidify with essay writing",
                priority=6,
                estimated_duration_minutes=25,
                estimated_question_count=1,
            )

        # Plan v6 6.3: replay wrong answers for moderate topics that reached this point
        # (i.e. not stalled into a mock and no pending amendments). Additive to Rules 1-4.
        if 40 <= accuracy_snapshot.accuracy_pct < 70 and accuracy_snapshot.total_attempts >= 5:
            return Recommendation(
                action=RecommendationAction.REPLAY_WRONG,
                topic=topic,
                reason=f"Replay wrong answers for {topic} ({accuracy_snapshot.accuracy_pct:.1f}% accuracy) to close the gap",
                priority=6,
                estimated_duration_minutes=15,
                estimated_question_count=10,
            )

        # Rule 5: Default to review
        return Recommendation(
            action=RecommendationAction.REVIEW,
            topic=topic,
            reason=f"Review recommended for {topic} at {accuracy_snapshot.accuracy_pct:.1f}% accuracy",
            priority=5,
            estimated_duration_minutes=10,
            estimated_question_count=5,
        )

    except ValueError as e:
        raise ValueError(f"Invalid accuracy snapshot: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to calculate recommendation: {e}") from e


def get_next_action_for_dashboard(user_id: str) -> Recommendation | None:
    """Get highest-priority recommendation for dashboard.

    Per Context7 docs: Handle missing data gracefully, return None if cannot compute.
    """
    try:
        # Get weakest topic for user
        weakest = db.get_weakest_topic_for_user(user_id)
        if weakest is None:
            return None

        topic = weakest["topic"]
        accuracy_pct = weakest["accuracy_pct"]
        total_attempts = weakest["total_attempts"]

        # Calculate days since improvement
        last_improved = weakest.get("last_improved_at")
        days_since_improvement = None
        if last_improved:
            try:
                last_improved_dt = datetime.fromisoformat(last_improved)
                days_since_improvement = (datetime.now() - last_improved_dt).days
            except Exception:
                pass

        # Create snapshot
        snapshot = AccuracySnapshot(
            topic=topic,
            accuracy_pct=accuracy_pct,
            total_attempts=total_attempts,
            last_improvement_at=last_improved,
            days_since_improvement=days_since_improvement,
        )

        # Calculate recommendation
        recommendation = calculate_next_action(user_id, topic, snapshot)
        recommendation.validate()
        return recommendation

    except IndexError:
        # No weak topics found
        return None
    except Exception as e:
        print(f"⚠️ Failed to get next action for dashboard: {e}")
        return None
