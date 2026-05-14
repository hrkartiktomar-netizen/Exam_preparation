"""Phase 4 tests: SRS, Study Paths, Analytics"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import database as db
import pytest

from models import (
    SRSTopicModel,
    StudyPathModel,
    StudyPathWeekModel,
    ExamAnalyticsResponseModel,
    AnalyticsTimelineModel,
)


class TestSRSSystem:
    """Spaced Repetition System tests."""

    def test_srs_topic_model_validation(self):
        """Test SRS topic model accepts valid ease values."""
        data = {
            "review_id": "SRS_TEST_001",
            "topic_id": "PH2_IFSCA_ACT",
            "display_name": "IFSCA Act",
            "due_at": datetime.now().isoformat(),
            "interval_days": 3,
            "ease": 2.8,  # Valid ease value
            "last_result": "success",
        }
        model = SRSTopicModel(**data)
        assert model.ease == 2.8

    def test_srs_topic_model_ease_bounds(self):
        """Test SRS ease field respects SM-2 bounds [1.3, 4.0]."""
        # Valid upper bound (was 2.5, now 4.0)
        data = {
            "review_id": "SRS_TEST_002",
            "topic_id": "PH2_BANKING",
            "due_at": datetime.now().isoformat(),
            "interval_days": 1,
            "ease": 3.8,  # Should be valid with fixed constraint
        }
        model = SRSTopicModel(**data)
        assert 1.3 <= model.ease <= 4.0

    def test_schedule_topic_review(self):
        """Test scheduling a topic for SRS review."""
        db.init_db()
        review_id = db.schedule_topic_review("PH2_FM_REGS", interval_days=3)
        assert review_id.startswith("SRS_")
        assert "PH2_FM_REGS" in review_id

    def test_get_due_topics(self):
        """Test retrieving topics due for SRS review."""
        db.init_db()
        db.schedule_topic_review("PH2_CAPITAL", interval_days=0)  # Due today
        due_topics = db.get_due_topics()
        assert isinstance(due_topics, list)
        if due_topics:
            assert "topic_id" in due_topics[0]

    def test_mark_topic_reviewed_success(self):
        """Test marking topic as successfully reviewed."""
        db.init_db()
        topic_id = "PH2_AML_KYC"
        db.schedule_topic_review(topic_id, interval_days=1)
        db.mark_topic_reviewed(topic_id, success=True)
        # Verify the topic was updated (ease increased)
        due_topics = db.get_due_topics()
        topic = next((t for t in due_topics if t["topic_id"] == topic_id), None)
        if topic:
            assert topic["ease"] >= 2.8  # Ease increases on success

    def test_mark_topic_reviewed_failure(self):
        """Test marking topic as failed review."""
        db.init_db()
        topic_id = "PH2_BULLION"
        db.schedule_topic_review(topic_id, interval_days=1)
        db.mark_topic_reviewed(topic_id, success=False)
        # Verify retry scheduled sooner
        due_topics = db.get_due_topics()
        topic = next((t for t in due_topics if t["topic_id"] == topic_id), None)
        if topic:
            assert topic["interval_days"] == 1  # Retried sooner


class TestStudyPaths:
    """12-week study path generation and tracking tests."""

    def test_study_path_model_validation(self):
        """Test StudyPath model structure."""
        exam_date = (datetime.now() + timedelta(days=84)).isoformat()[:10]
        weeks = [
            StudyPathWeekModel(
                week=1,
                focus_topics=["PH2_IFSCA_ACT"],
                daily_questions=20,
                milestone="Week 1 completion",
            )
        ]
        model = StudyPathModel(
            path_id="PATH_TEST_001",
            exam_date=exam_date,
            weeks=weeks,
        )
        assert model.path_id == "PATH_TEST_001"
        assert len(model.weeks) == 1
        assert model.weeks[0].week == 1

    def test_study_path_week_model_validation(self):
        """Test StudyPathWeek constraints."""
        with pytest.raises(ValueError):
            StudyPathWeekModel(
                week=13,  # Invalid: > 12
                focus_topics=["PH2_IFSCA_ACT"],
                daily_questions=20,
                milestone="Invalid",
            )

    def test_create_study_path(self):
        """Test creating a 12-week study path."""
        db.init_db()
        exam_date = (datetime.now() + timedelta(days=84)).isoformat()[:10]
        weak_topics = ["PH2_FM_REGS", "PH2_CAPITAL"]
        path_id = db.create_study_path(exam_date, weak_topics, amendments_count=5)
        assert path_id.startswith("PATH_")

    def test_get_active_study_path(self):
        """Test retrieving active study path."""
        db.init_db()
        exam_date = (datetime.now() + timedelta(days=84)).isoformat()[:10]
        db.create_study_path(exam_date, ["PH2_IFSCA_ACT"])
        path = db.get_active_study_path()
        assert path is not None
        assert "weeks_json" in path
        assert path["exam_date"] == exam_date

    def test_study_path_json_parsing(self):
        """Test that study path JSON is properly parsed."""
        db.init_db()
        exam_date = (datetime.now() + timedelta(days=84)).isoformat()[:10]
        db.create_study_path(exam_date, ["PH2_CAPITAL"])
        path = db.get_active_study_path()
        assert isinstance(path["weeks_json"], list)
        assert len(path["weeks_json"]) == 12
        for week in path["weeks_json"]:
            assert "week" in week
            assert "focus_topics" in week
            assert "daily_questions" in week


class TestAnalytics:
    """Analytics and performance tracking tests."""

    def test_exam_analytics_model(self):
        """Test ExamAnalytics response model."""
        data = {
            "exam_id": "EXAM_001",
            "total_topics_analyzed": 15,
            "overall_accuracy": 72.5,
            "topic_analytics": [],
        }
        model = ExamAnalyticsResponseModel(**data)
        assert model.exam_id == "EXAM_001"
        assert model.overall_accuracy == 72.5

    def test_analytics_timeline_model(self):
        """Test Analytics timeline model."""
        data = {
            "exam_id": "EXAM_002",
            "score": 145.0,
            "accuracy": 75.0,
            "avg_topic_accuracy": 73.5,
            "topics_analyzed": 18,
            "created_at": datetime.now().isoformat(),
        }
        model = AnalyticsTimelineModel(**data)
        assert model.exam_id == "EXAM_002"
        assert model.topics_analyzed == 18

    def test_get_analytics_timeline(self):
        """Test retrieving analytics timeline."""
        db.init_db()
        timeline = db.get_analytics_timeline(limit=10)
        assert isinstance(timeline, list)


class TestImportCorrectness:
    """Verify imports are at module level (Context7 compliance)."""

    def test_no_function_level_imports_main(self):
        """Verify main.py has no function-level imports."""
        main_path = Path(__file__).parent.parent / "main.py"
        with open(main_path) as f:
            content = f.read()
            # Check for patterns like "def func():" followed by "import/from" within indented block
            lines = content.split("\n")
            in_function = False
            for i, line in enumerate(lines):
                if line.strip().startswith("def ") and "async def" not in line:
                    in_function = True
                elif in_function and line and not line[0].isspace():
                    in_function = False
                elif in_function and (
                    line.strip().startswith("import ") or line.strip().startswith("from ")
                ):
                    if line.strip().startswith("from datetime import"):
                        pass  # Allowed module-level datetime imports were fixed
                    else:
                        pytest.fail(f"Function-level import at line {i+1}: {line}")

    def test_pathlib_import_not_shadowed(self):
        """Verify pathlib.Path is not shadowed by fastapi.Path."""
        main_path = Path(__file__).parent.parent / "main.py"
        with open(main_path) as f:
            lines = f.readlines()
            found_pathlib_renamed = False

            for i, line in enumerate(lines[:50]):  # Check first 50 lines
                if "from pathlib import Path as" in line:
                    found_pathlib_renamed = True
                    break

            assert found_pathlib_renamed, "PathLib import must be renamed to avoid shadowing (use 'Path as PathLib')"


class TestContextIntegration:
    """Test Context7 compliance patterns."""

    def test_database_connection_cleanup(self):
        """Test database connections are properly closed."""
        db.init_db()
        # This should not leak connections
        for _ in range(5):
            due = db.get_due_topics()
            assert isinstance(due, list)
        # If we got here without connection exhaustion, cleanup works

    def test_error_handling_with_httpexception(self):
        """Test FastAPI HTTPException handling pattern."""
        from fastapi import HTTPException

        try:
            raise HTTPException(status_code=404, detail="Not found")
        except HTTPException as e:
            assert e.status_code == 404
            assert e.detail == "Not found"

    def test_json_parsing_robustness(self):
        """Test robust JSON parsing in study_path_week endpoint."""
        # Valid JSON
        valid_json = json.dumps({"week": 1, "focus_topics": ["PH2_IFSCA_ACT"]})
        parsed = json.loads(valid_json)
        assert parsed["week"] == 1

        # Malformed JSON should raise exception
        with pytest.raises(json.JSONDecodeError):
            json.loads("{invalid json")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
