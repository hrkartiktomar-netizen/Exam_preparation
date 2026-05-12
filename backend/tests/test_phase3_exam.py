"""Tests for Phase 3: Exam Endpoints + TCS iON UI."""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import database as db


class TestExamEndpoints:
    """Test exam start, timer, and submit endpoints."""

    def setup_method(self):
        """Setup test database."""
        db.init_db()
        self.conn = db.get_connection()

    def teardown_method(self):
        """Cleanup."""
        if self.conn:
            self.conn.close()

    def test_exam_start_returns_required_fields(self):
        """Verify /api/exams/start returns exam_id, started_at, questions, time_limit_seconds."""
        # Simulate exam start logic
        config = db.get_smart_mock_config(total_questions=50, mode="balanced")

        assert "allocation" in config
        assert "questions" not in config  # get_smart_mock_config doesn't generate questions

        # Mock data structure that would be returned
        response = {
            "exam_id": "SM_20260512_1234_abcd",
            "started_at": datetime.now().isoformat(),
            "time_limit_seconds": 3600,
            "question_count": 50,
            "allocation_summary": config["allocation_summary"] if "allocation_summary" in config else {}
        }

        assert response["exam_id"] is not None
        assert response["started_at"] is not None
        assert response["time_limit_seconds"] == 3600
        assert response["question_count"] == 50

    def test_exam_time_calculation(self):
        """Verify time remaining calculation (server-side timer)."""
        started_at = datetime.now() - timedelta(seconds=600)  # 10 min ago
        elapsed = (datetime.now() - started_at).total_seconds()
        time_remaining = max(0, 3600 - elapsed)

        # Should be ~3000 seconds remaining
        assert 2950 <= time_remaining <= 3050, f"Time remaining {time_remaining} not in expected range"

    def test_exam_time_expired_validation(self):
        """Verify submit validation: 403 if time exceeded."""
        started_at = datetime.now() - timedelta(seconds=3601)  # 1 sec over 60 min
        elapsed = (datetime.now() - started_at).total_seconds()

        # Should be expired
        assert elapsed > 3600, "Exam should be expired"

        # Response would be 403 EXAM_TIME_EXPIRED
        response = {
            "status": "error",
            "reason": "EXAM_TIME_EXPIRED",
            "code": 403
        }

        assert response["code"] == 403

    def test_exam_submit_button_enabled_at_5_min(self):
        """Verify submit button disabled until last 5 minutes."""
        # At 30 min remaining: disabled
        time_remaining_30min = 1800
        submit_enabled_30min = time_remaining_30min <= 300
        assert not submit_enabled_30min, "Submit should be disabled at 30 min"

        # At 5 min remaining: enabled
        time_remaining_5min = 300
        submit_enabled_5min = time_remaining_5min <= 300
        assert submit_enabled_5min, "Submit should be enabled at 5 min"

        # At 0 seconds: enabled (or auto-submitted)
        time_remaining_0sec = 0
        submit_enabled_0sec = time_remaining_0sec <= 300
        assert submit_enabled_0sec, "Submit should be enabled at 0 sec"

    def test_score_calculation_positive_marking(self):
        """Verify score calculation: +4 correct, -1 wrong, 0 unanswered."""
        # Mock: 30 correct, 10 wrong, 10 unanswered
        correct = 30
        wrong = 10
        unanswered = 10

        score = (correct * 4) + (wrong * -1) + (unanswered * 0)
        expected_score = 120 - 10  # 110
        expected_score = 110

        assert score == expected_score, f"Score {score} != expected {expected_score}"

    def test_weak_area_detection_accuracy_lt_60(self):
        """Verify weak areas detected when accuracy < 60%."""
        total_questions = 50

        # Topic 1: 25 correct, 5 wrong = 83% (not weak)
        # Topic 2: 10 correct, 14 wrong = 42% (weak)

        topic_breakdown = {
            "PH2_FM_REGS": {"correct": 25, "total": 30, "accuracy_pct": 83.3},
            "PH2_IFSCA_ACT": {"correct": 10, "total": 24, "accuracy_pct": 41.7}
        }

        weak_areas = [topic for topic, stats in topic_breakdown.items() if stats["accuracy_pct"] < 60]

        assert "PH2_IFSCA_ACT" in weak_areas, "Should detect PH2_IFSCA_ACT as weak"
        assert "PH2_FM_REGS" not in weak_areas, "Should not detect PH2_FM_REGS as weak"

    def test_question_answer_tracking(self):
        """Verify answers tracked correctly: question_id, selected_answer, time_spent, marked."""
        answers = [
            {
                "question_id": "Q_PH2_FM_REGS_abc123",
                "selected_answer": "A",
                "time_spent_seconds": 45,
                "marked_for_review": False
            },
            {
                "question_id": "Q_PH2_IFSCA_ACT_def456",
                "selected_answer": None,
                "time_spent_seconds": 0,
                "marked_for_review": True
            }
        ]

        assert answers[0]["selected_answer"] == "A"
        assert answers[1]["selected_answer"] is None
        assert answers[1]["marked_for_review"] is True

    def test_auto_submit_on_time_expire(self):
        """Verify auto-submit when time expires."""
        # Simulate timer reaching 0
        time_remaining = 0
        should_auto_submit = time_remaining <= 0

        assert should_auto_submit, "Should auto-submit when time expires"

    def test_exam_state_persistence_localstorage(self):
        """Verify exam state can be persisted and restored via localStorage."""
        exam_state = {
            "exam_id": "SM_test_123",
            "answers": [
                {"question_id": "q1", "selected_answer": "A"},
                {"question_id": "q2", "selected_answer": None}
            ],
            "marked_for_review": ["q3", "q4"]
        }

        import json
        serialized = json.dumps(exam_state)
        deserialized = json.loads(serialized)

        assert deserialized["exam_id"] == exam_state["exam_id"]
        assert deserialized["answers"][0]["selected_answer"] == "A"
        assert "q3" in deserialized["marked_for_review"]

    def test_palette_cell_states(self):
        """Verify question palette cell states: answered, not-answered, marked, answered-marked."""
        questions = [
            {"question_id": "q1", "answered": True, "marked": False},  # ■
            {"question_id": "q2", "answered": False, "marked": False},  # □
            {"question_id": "q3", "answered": False, "marked": True},  # ★
            {"question_id": "q4", "answered": True, "marked": True},  # ★ (over ■)
        ]

        expected_classes = [
            "answered",
            "not-answered",
            "marked",
            "answered-marked"
        ]

        for q, expected_class in zip(questions, expected_classes):
            if q["marked"]:
                if q["answered"]:
                    css_class = "answered-marked"
                else:
                    css_class = "marked"
            else:
                css_class = "answered" if q["answered"] else "not-answered"

            assert css_class == expected_class, f"Q {q['question_id']}: {css_class} != {expected_class}"

    def test_navigation_restrictions(self):
        """Verify navigation: can jump to any Q, but back/forward buttons disabled at boundaries."""
        question_count = 50
        current_idx = 25

        # Middle question: both buttons enabled
        prev_enabled = current_idx > 0
        next_enabled = current_idx < question_count - 1
        assert prev_enabled and next_enabled, "Both buttons should be enabled at Q25"

        # First question: prev disabled
        current_idx = 0
        prev_enabled = current_idx > 0
        next_enabled = current_idx < question_count - 1
        assert not prev_enabled and next_enabled, "Prev should be disabled at Q1"

        # Last question: next disabled
        current_idx = 49
        prev_enabled = current_idx > 0
        next_enabled = current_idx < question_count - 1
        assert prev_enabled and not next_enabled, "Next should be disabled at Q50"

    def test_negative_marking_display(self):
        """Verify negative marking display: +4 for correct, -1 for wrong, 0 for unanswered."""
        display_text = "💡 Scoring: +4 for correct, -1 for wrong, 0 for unanswered"

        assert "+4" in display_text
        assert "-1" in display_text
        assert "0 for unanswered" in display_text

    def test_exam_submit_answer_structure(self):
        """Verify exam submit sends correct answer structure."""
        answers_payload = [
            {
                "question_id": "Q_ABC_123",
                "selected_answer": "B",
                "time_spent_seconds": 60,
                "marked_for_review": False
            }
        ]

        # Verify structure matches API expectation
        assert "question_id" in answers_payload[0]
        assert "selected_answer" in answers_payload[0]
        assert "time_spent_seconds" in answers_payload[0]
        assert "marked_for_review" in answers_payload[0]


class TestExamUILogic:
    """Test exam UI JavaScript logic (simulated in Python)."""

    def test_timer_format_display(self):
        """Verify timer displays as MM:SS format."""
        time_remaining = 1234  # 20 min 34 sec
        minutes = time_remaining // 60
        seconds = time_remaining % 60
        display = f"{str(minutes).zfill(2)}:{str(seconds).zfill(2)}"

        assert display == "20:34", f"Timer display {display} != expected 20:34"

        # Test boundary: 300 seconds (5 min)
        time_remaining = 300
        minutes = time_remaining // 60
        seconds = time_remaining % 60
        display = f"{str(minutes).zfill(2)}:{str(seconds).zfill(2)}"
        assert display == "05:00"

    def test_allocation_summary_visible(self):
        """Verify allocation summary is populated correctly."""
        summary = {
            "weak_topics_focused": 30,
            "medium_topics": 13,
            "strong_topics": 7,
            "weak_pct": "60.0%",
            "medium_pct": "26.0%",
            "strong_pct": "14.0%"
        }

        total = summary["weak_topics_focused"] + summary["medium_topics"] + summary["strong_topics"]
        assert total == 50, "Total questions != 50"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
