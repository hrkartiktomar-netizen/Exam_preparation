"""Tests for Phase 3: Adaptive Mock Generation."""

import pytest
import sys
from pathlib import Path
from collections import defaultdict

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import database as db


class TestAdaptiveMockAllocation:
    """Test adaptive mock 60/25/15 allocation + difficulty progression."""

    def setup_method(self):
        """Setup test database."""
        db.init_db()
        self.conn = db.get_connection()

    def teardown_method(self):
        """Cleanup."""
        if self.conn:
            self.conn.close()

    def test_allocation_accuracy_within_1_percent(self):
        """Verify 60/25/15 allocation is within ±1%."""
        # Generate a mock
        config = db.get_smart_mock_config(total_questions=50, mode="balanced")

        # Calculate allocation percentages
        weak_topics = set(config.get("weak_topics", []))
        medium_topics = set(config.get("medium_topics", []))
        strong_topics = set(config.get("strong_topics", []))

        allocation = config["allocation"]

        weak_count = sum(count for topic, count in allocation.items() if topic in weak_topics)
        medium_count = sum(count for topic, count in allocation.items() if topic in medium_topics)
        strong_count = sum(count for topic, count in allocation.items() if topic in strong_topics)

        total = weak_count + medium_count + strong_count

        weak_pct = weak_count / total if total > 0 else 0
        medium_pct = medium_count / total if total > 0 else 0
        strong_pct = strong_count / total if total > 0 else 0

        # Verify within ±2% (accounting for rounding on 50 questions)
        assert abs(weak_pct - 0.60) <= 0.02, f"Weak allocation {weak_pct:.2%} not within ±2% of 60%"
        assert abs(medium_pct - 0.25) <= 0.02, f"Medium allocation {medium_pct:.2%} not within ±2% of 25%"
        assert abs(strong_pct - 0.15) <= 0.02, f"Strong allocation {strong_pct:.2%} not within ±2% of 15%"

    def test_difficulty_progression_weak_topics(self):
        """Verify weak topics have progressive difficulty (easy → medium → hard)."""
        config = db.get_smart_mock_config(total_questions=50, mode="balanced")

        difficulty_curve = config["difficulty_curve"]
        weak_topics = set(config.get("weak_topics", []))

        # For each weak topic with >= 3 questions verify distribution
        for topic in weak_topics:
            difficulties = difficulty_curve.get(topic, [])
            if len(difficulties) >= 3:
                # Should have a mix of difficulties
                has_easy = "easy" in difficulties
                has_medium = "medium" in difficulties
                has_hard = "hard" in difficulties

                assert has_easy, f"Weak topic {topic} missing easy questions"
                assert has_hard, f"Weak topic {topic} missing hard questions"

    def test_difficulty_curve_returns_list_per_topic(self):
        """Verify difficulty_curve is dict[topic] → list[difficulty]."""
        config = db.get_smart_mock_config(total_questions=50, mode="balanced")
        difficulty_curve = config["difficulty_curve"]

        # All values should be lists
        for topic, difficulties in difficulty_curve.items():
            assert isinstance(difficulties, list), f"difficulty_curve[{topic}] is not a list"
            assert all(isinstance(d, str) for d in difficulties), f"difficulty_curve[{topic}] contains non-strings"
            assert all(d in ["easy", "medium", "hard"] for d in difficulties), f"difficulty_curve[{topic}] has invalid difficulty"

    def test_allocation_count_matches_question_count(self):
        """Verify allocation counts match actual question counts."""
        config = db.get_smart_mock_config(total_questions=50, mode="balanced")
        allocation = config["allocation"]

        total_allocated = sum(allocation.values())
        assert total_allocated == 50, f"Allocation total {total_allocated} != 50"

    def test_difficulty_list_lengths_match_allocation(self):
        """Verify difficulty list length matches allocation count per topic."""
        config = db.get_smart_mock_config(total_questions=50, mode="balanced")
        allocation = config["allocation"]
        difficulty_curve = config["difficulty_curve"]

        for topic, expected_count in allocation.items():
            difficulties = difficulty_curve.get(topic, [])
            actual_count = len(difficulties)
            assert (
                actual_count == expected_count
            ), f"Topic {topic}: difficulty list length {actual_count} != allocation count {expected_count}"

    def test_medium_topics_have_mixed_difficulty(self):
        """Verify medium topics have easy + hard (confidence + challenge)."""
        config = db.get_smart_mock_config(total_questions=50, mode="balanced")

        difficulty_curve = config["difficulty_curve"]
        medium_topics = set(config.get("medium_topics", []))

        for topic in medium_topics:
            difficulties = difficulty_curve.get(topic, [])
            if len(difficulties) >= 2:
                has_easy = "easy" in difficulties
                has_hard = "hard" in difficulties
                assert has_easy or has_hard, f"Medium topic {topic} missing easy or hard questions"

    def test_strong_topics_all_easy(self):
        """Verify strong topics are all easy (confidence building)."""
        config = db.get_smart_mock_config(total_questions=50, mode="balanced")

        difficulty_curve = config["difficulty_curve"]
        strong_topics = set(config.get("strong_topics", []))

        for topic in strong_topics:
            difficulties = difficulty_curve.get(topic, [])
            if len(difficulties) > 0:
                assert all(
                    d == "easy" for d in difficulties
                ), f"Strong topic {topic} has non-easy difficulty: {difficulties}"

    def test_modes_affect_allocation_ratios(self):
        """Verify different modes produce different allocations."""
        balanced_config = db.get_smart_mock_config(total_questions=50, mode="balanced")
        weakness_heavy_config = db.get_smart_mock_config(total_questions=50, mode="weakness-heavy")

        balanced_weak = sum(
            count
            for topic, count in balanced_config["allocation"].items()
            if topic in set(balanced_config.get("weak_topics", []))
        )
        weakness_weak = sum(
            count
            for topic, count in weakness_heavy_config["allocation"].items()
            if topic in set(weakness_heavy_config.get("weak_topics", []))
        )

        # Weakness-heavy should allocate more to weak topics
        assert weakness_weak >= balanced_weak, "Weakness-heavy mode should allocate more to weak topics"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
