"""Regression tests for critical bugs found during the codebase audit (2026-08).

Each test reproduces a confirmed bug and asserts the fixed behavior. Tests are
hermetic: they run against a temporary SQLite database and never call Gemini.

Covered regressions:
1. /api/topics 422 on fresh DBs (TopicModel required phase/paper, seed leaves NULL)
2. Migration 004 non-idempotency ("duplicate column name: source_role" per init_db)
3. PYQ legacy foreign keys making every submission 500 (pyq_source_doc_id=0,
   question_id not in questions)
4. submit_mock double-submission polluting question_attempts
5. PYQ scoring: partial answers inflating accuracy / unanswered miscounted
6. _categorize_materials leaving documents.source_role NULL (PYQ list empty)
7. /api/exams/start 500 (Pydantic item assignment)
"""

from __future__ import annotations

import asyncio
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import database as db
from models import OptionModel, QuestionModel, TopicModel


@pytest.fixture()
def temp_db():
    """Fresh temporary database with the full production schema + migrations."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".db") as f:
        temp_db_path = f.name
    original_db_path = db.DB_PATH
    db.DB_PATH = Path(temp_db_path)
    try:
        db.init_db()
        yield Path(temp_db_path)
    finally:
        db.DB_PATH = original_db_path
        Path(temp_db_path).unlink(missing_ok=True)


def _conn() -> sqlite3.Connection:
    return db.get_connection()


# ---------------------------------------------------------------------------
# 1. TopicModel must accept seeded topics (phase/paper are NULL)
# ---------------------------------------------------------------------------

def test_topic_model_accepts_seeded_topic_with_null_phase_paper():
    row = {
        "topic_id": "PH2_FM_REGS",
        "parent_topic_id": None,
        "phase": None,
        "paper": None,
        "display_name": "Fund Management Regulations",
        "description": "d",
        "base_weight": 1.0,
        "exam_priority": 10,
        "is_amendment_sensitive": True,
    }
    model = TopicModel.model_validate(row)
    assert model.topic_id == "PH2_FM_REGS"
    assert model.phase is None


def test_topics_endpoint_returns_all_seeded_topics(temp_db):
    topics = db.list_topics()
    assert len(topics) == len(db.TOPIC_DEFINITIONS)
    for topic in topics:
        TopicModel.model_validate(topic)  # must not raise


# ---------------------------------------------------------------------------
# 2. init_db / migration 004 must be idempotent
# ---------------------------------------------------------------------------

def test_init_db_is_idempotent_without_migration_errors(temp_db, capsys):
    # Second run used to raise "duplicate column name: source_role"
    db.init_db()
    db.init_db()
    output = capsys.readouterr().out + capsys.readouterr().err
    assert "duplicate column name" not in output


def test_repair_pyq_schema_removes_legacy_fks(temp_db):
    conn = _conn()
    fks_sessions = conn.execute("PRAGMA foreign_key_list(pyq_sessions)").fetchall()
    fks_attempts = conn.execute("PRAGMA foreign_key_list(pyq_question_attempts)").fetchall()
    conn.close()
    assert fks_sessions == [], f"pyq_sessions still has FKs: {fks_sessions}"
    assert fks_attempts == [], f"pyq_question_attempts still has FKs: {fks_attempts}"


def test_repair_pyq_schema_preserves_rows(temp_db):
    conn = _conn()
    conn.execute(
        "INSERT INTO pyq_sessions (pyq_id, pyq_source_doc_id, pyq_title, status) VALUES ('PYQ_X', 0, 't', 'completed')"
    )
    conn.commit()
    conn.close()
    # A re-run of the repair must preserve existing rows
    conn = _conn()
    db._repair_pyq_schema(conn)
    conn.commit()
    conn.close()
    conn = _conn()
    row = conn.execute("SELECT pyq_title, status FROM pyq_sessions WHERE pyq_id = 'PYQ_X'").fetchone()
    conn.close()
    assert row is not None and row["status"] == "completed"


# ---------------------------------------------------------------------------
# 3. _categorize_materials must assign roles on the canonical documents table
# ---------------------------------------------------------------------------

def test_categorize_materials_populates_documents_roles(temp_db):
    conn = _conn()
    conn.execute(
        "INSERT INTO documents (document_id, title, category) VALUES ('d1', 'IFSCA Grade A 2024 Memory Based Phase 1 Question Paper 1', 'Exam Papers (Memory-based)')"
    )
    conn.execute(
        "INSERT INTO documents (document_id, title, category) VALUES ('d2', 'IFSCA Annual Report 2023-24', 'IFSCA Publications (Reports/Bulletins)')"
    )
    conn.commit()
    conn.close()

    db._categorize_materials(_conn())

    conn = _conn()
    role1 = conn.execute("SELECT source_role FROM documents WHERE document_id = 'd1'").fetchone()[0]
    role2 = conn.execute("SELECT source_role FROM documents WHERE document_id = 'd2'").fetchone()[0]
    conn.close()
    assert role1 == "pyq_phase_paper"
    assert role2 == "regulatory_core"


def test_categorize_materials_does_not_clobber_manual_roles(temp_db):
    conn = _conn()
    conn.execute(
        "INSERT INTO documents (document_id, title, category, source_role) VALUES ('d1', 'IFSCA Grade A 2024 Memory Based Phase 1 Question Paper 1', 'Exam Papers (Memory-based)', 'essay_examples')"
    )
    conn.commit()
    conn.close()

    db._categorize_materials(_conn())

    conn = _conn()
    role = conn.execute("SELECT source_role FROM documents WHERE document_id = 'd1'").fetchone()[0]
    conn.close()
    assert role == "essay_examples"  # manual assignment survives


def test_categorize_materials_fast_path_skips_fully_categorized_db(temp_db):
    """When every document already has a role and source_documents is empty,
    _categorize_materials must be a no-op (it runs inside init_db on hot paths)."""
    conn = _conn()
    # Give every topic a role so the fast path triggers
    conn.execute("UPDATE documents SET source_role = 'regulatory_core'")
    conn.commit()
    conn.close()

    class _CountingCursor:
        def __init__(self, real, owner):
            self._real = real
            self._owner = owner

        def execute(self, sql, parameters=()):
            if isinstance(sql, str) and sql.strip().upper().startswith("UPDATE"):
                self._owner.updates += 1
            return self._real.execute(sql, parameters)

        def __getattr__(self, name):
            return getattr(self._real, name)

    class _CountingConn:
        def __init__(self, real):
            self._real = real
            self.updates = 0

        def cursor(self):
            return _CountingCursor(self._real.cursor(), self)

        def __getattr__(self, name):
            return getattr(self._real, name)

    original_get_connection = db.get_connection
    counter = _CountingConn(original_get_connection())
    db.get_connection = lambda: counter
    try:
        db._categorize_materials(counter)
    finally:
        db.get_connection = original_get_connection

    assert counter.updates == 0, f"fast path issued {counter.updates} UPDATEs"


# ---------------------------------------------------------------------------
# 4. submit_mock idempotency (double submission pollutes question_attempts)
# ---------------------------------------------------------------------------

def _insert_smart_mock(conn, mock_id="SM_T1"):
    question = {
        "question_id": "Q_T1",
        "topic": "PH2_FM_REGS",
        "question_text": "Who regulates IFSC?",
        "options": [
            {"label": "A", "text": "x"},
            {"label": "B", "text": "IFSCA"},
            {"label": "C", "text": "y"},
            {"label": "D", "text": "z"},
        ],
        "correct_option": "B",
        "explanation": "IFSCA",
        "source": "t",
        "difficulty": "easy",
        "source_policy": "exam_material",
    }
    db.save_question(question, created_by="test")
    db.save_smart_mock(mock_id, [], {"PH2_FM_REGS": 1}, {"PH2_FM_REGS": ["easy"]}, questions=[question])


def test_submit_mock_rejects_duplicate_submission(temp_db):
    _insert_smart_mock(_conn())
    answers = [{"question_id": "Q_T1", "selected_answer": "B", "time_spent_seconds": 10}]

    first = db.submit_mock("SM_T1", answers)
    assert first["total_correct"] == 1

    with pytest.raises(ValueError, match="already been submitted"):
        db.submit_mock("SM_T1", answers)

    conn = _conn()
    count = conn.execute("SELECT COUNT(*) FROM question_attempts WHERE mock_id = 'SM_T1'").fetchone()[0]
    conn.close()
    assert count == 1  # one submission -> one attempt row


# ---------------------------------------------------------------------------
# 5. PYQ scoring integrity (partial submissions must not inflate accuracy)
# ---------------------------------------------------------------------------

def test_pyq_submit_scoring_uses_displayed_question_count(temp_db):
    import pyq_cache
    from pyq_parser import ParsedQuestion

    questions = [
        ParsedQuestion(question_number=i, question_text=f"Q{i}", options={"A": "a", "B": "b", "C": "c", "D": "d"}, correct_answer="B")
        for i in range(1, 5)
    ]
    pyq_cache.cache_pyq_questions("PYQ_DOCX", questions)

    import main
    from fastapi.testclient import TestClient

    # Pre-seed a document so the lifespan skips corpus ingestion
    conn = _conn()
    conn.execute("INSERT INTO documents (document_id, title) VALUES ('doc_x', 'IFSCA Grade A 2024 Memory Based Phase 1 Question Paper 1')")
    conn.commit()
    conn.close()

    with TestClient(main.app) as client:
        # Only 1 of 4 questions answered
        response = client.post(
            "/api/pyq/PYQ_DOCX/submit",
            json={"answers": [{"question_id": "PYQ_DOCX_Q1", "selected_answer": "B"}]},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total_questions"] == 4
        assert data["total_answered"] == 1
        assert data["total_correct"] == 1
        assert data["total_unanswered"] == 3
        assert data["accuracy_pct"] == 25.0  # not 100.0


# ---------------------------------------------------------------------------
# 6. /api/exams/start must not crash on Pydantic models
# ---------------------------------------------------------------------------

def test_exam_start_returns_expected_time_and_negative_marking(temp_db):
    import main

    fake_question = {
        "question_id": "Q_AI_EXAM1",
        "topic": "PH2_FM_REGS",
        "question_text": "Which regulator governs GIFT IFSC?",
        "options": [
            {"label": "A", "text": "SEBI"},
            {"label": "B", "text": "IFSCA"},
            {"label": "C", "text": "RBI"},
            {"label": "D", "text": "IRDAI"},
        ],
        "correct_option": "B",
        "explanation": "IFSCA is the unified regulator.",
        "source": "Test",
        "source_policy": "exam_material",
        "created_by": "gemini",
    }

    def fake_generate_smart_mock(total_questions=50, mode="balanced", use_gemini=True):
        return {
            "mock_id": "SM_EXAM1",
            "allocation": {"PH2_FM_REGS": 1},
            "allocation_summary": {},
            "weakness_analysis": [],
            "questions": [fake_question],
        }

    conn = _conn()
    conn.execute("INSERT INTO documents (document_id, title) VALUES ('doc_exam', 'x')")
    conn.commit()
    conn.close()

    with patch.object(main, "available_gemini_keys", return_value=["test-key"]):
        with patch.object(main.db, "generate_smart_mock", side_effect=fake_generate_smart_mock):
            with TestClient(main.app) as client:
                response = client.post("/api/exams/start", json={"total_questions": 5})
                assert response.status_code == 200, response.text
                data = response.json()
                assert data["question_count"] == 1
                question = data["questions"][0]
                assert question["expected_time_sec"] == 180
                assert question["negative_marking"] == -1
                # Blind exam payload: the answer key must NOT be shipped to the browser
                assert "correct_option" not in question
                assert "explanation" not in question


# ---------------------------------------------------------------------------
# 7. QuestionModel still round-trips (no regressions from exam payload change)
# ---------------------------------------------------------------------------

def test_question_model_round_trip():
    question = QuestionModel(
        question_id="Q1",
        topic="T1",
        question_text="text",
        options=[
            OptionModel(label="A", text="1"),
            OptionModel(label="B", text="2"),
            OptionModel(label="C", text="3"),
            OptionModel(label="D", text="4"),
        ],
        correct_option="B",
        explanation="exp",
    )
    dumped = question.model_dump()
    assert QuestionModel.model_validate(dumped).question_id == "Q1"


# ---------------------------------------------------------------------------
# 8. PR #1 cross-check regressions (study path, SRS, recency, priority, keys)
# ---------------------------------------------------------------------------

def test_study_path_persists_returned_weeks(temp_db):
    """generate endpoint must persist the exact weeks it returns."""
    weeks = [
        {"week": 1, "focus_topics": ["PH2_FM_REGS"], "daily_questions": 25, "milestone": "Gemini milestone"},
        {"week": 2, "focus_topics": ["PH2_BANKING"], "daily_questions": 30, "milestone": "Gemini milestone 2"},
    ]
    path_id = db.create_study_path("2026-11-06", ["PH2_FM_REGS"], weeks=weeks)
    active = db.get_active_study_path()
    assert active is not None
    assert active["path_id"] == path_id
    stored = active["weeks_json"]
    assert stored[0]["milestone"] == "Gemini milestone"
    assert stored[0]["status"] == "not_started"  # default added
    assert len(stored) == 2


def test_srs_schedule_keeps_one_row_per_topic(temp_db):
    db.schedule_topic_review("PH2_FM_REGS", interval_days=1)
    db.schedule_topic_review("PH2_FM_REGS", interval_days=3)
    db.schedule_topic_review("PH2_FM_REGS", interval_days=7)
    conn = _conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM review_items WHERE item_type='topic' AND topic_id='PH2_FM_REGS'"
    ).fetchone()[0]
    conn.close()
    assert count == 1, f"expected 1 row per topic, got {count}"


def test_srs_mark_reviewed_touches_only_soonest_row(temp_db):
    db.schedule_topic_review("PH2_BANKING", interval_days=5)
    db.mark_topic_reviewed("PH2_BANKING", success=True)
    conn = _conn()
    rows = conn.execute(
        "SELECT last_result, interval_days FROM review_items WHERE item_type='topic' AND topic_id='PH2_BANKING'"
    ).fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["last_result"] == "success"
    assert rows[0]["interval_days"] == 3


def test_amendment_recency_cutoff_matches_sqlite_timestamp_format(temp_db):
    """created_at is 'YYYY-MM-DD HH:MM:SS'; ISO 'T' cutoffs excluded boundary rows."""
    conn = _conn()
    conn.execute(
        "INSERT INTO amendments (amendment_id, topic, rule_name, created_at) VALUES ('A1', 'PH2_FM_REGS', 'r1', datetime('now', '-1 day'))"
    )
    conn.execute(
        "INSERT INTO amendments (amendment_id, topic, rule_name, created_at) VALUES ('A2', 'PH2_FM_REGS', 'r2', datetime('now'))"
    )
    conn.commit()
    conn.close()
    recent = db.get_recent_amendments(days_back=30, limit=10)
    ids = {item["amendment_id"] for item in recent}
    assert "A2" in ids
    # A1 is within 30 days too (created_at is a valid space-format timestamp)
    assert "A1" in ids


def test_amendment_recent_ordering_critical_first(temp_db):
    conn = _conn()
    for priority in ("NORMAL", "CRITICAL", "HIGH"):
        conn.execute(
            "INSERT INTO amendments (amendment_id, topic, rule_name, priority, created_at) VALUES (?, 'PH2_FM_REGS', ?, ?, datetime('now'))",
            (f"AMN_{priority}", priority, priority),
        )
    conn.commit()
    conn.close()
    recent = db.get_recent_amendments(days_back=30, limit=10)
    priorities = [item["priority"] for item in recent]
    assert priorities[0] == "CRITICAL", f"CRITICAL must sort first, got {priorities}"


def test_available_gemini_keys_respect_cooldown(monkeypatch):
    import gemini_integration

    # refresh_gemini_keys() reloads keys from the environment, so the env must
    # match the injected state.
    monkeypatch.setenv("GEMINI_KEY_1", "k1")
    monkeypatch.setenv("GEMINI_KEY_2", "k2")
    gemini_integration.refresh_gemini_keys()
    gemini_integration.GEMINI_STATE["rate_limited_until"] = {
        "k1": 10 ** 12,  # far future -> rate limited
        "k2": 10 ** 12,
    }
    assert gemini_integration.available_gemini_keys() == []
    # mixed: only the available key is returned
    gemini_integration.GEMINI_STATE["rate_limited_until"]["k2"] = 0
    assert gemini_integration.available_gemini_keys() == ["k2"]


def test_pyq_cache_ttl_covers_full_exam():
    import pyq_cache

    assert pyq_cache._CACHE_TTL_SECONDS >= 3600, "cache must outlive the 60-minute exam timer"

# ---------------------------------------------------------------------------
# 9. Gemini availability must treat cooldown as unavailable
# ---------------------------------------------------------------------------

def test_gemini_available_false_when_all_keys_cooling_down(monkeypatch):
    import gemini_integration

    monkeypatch.setenv("GEMINI_KEY_1", "k1")
    monkeypatch.setenv("GEMINI_KEY_2", "k2")
    gemini_integration.refresh_gemini_keys()
    gemini_integration.GEMINI_STATE["rate_limited_until"] = {
        "k1": 10 ** 12,
        "k2": 10 ** 12,
    }
    assert gemini_integration.available_gemini_keys() == []
    assert gemini_integration.gemini_available() is False
    gemini_integration.GEMINI_STATE["rate_limited_until"]["k2"] = 0
    assert gemini_integration.available_gemini_keys() == ["k2"]
    assert gemini_integration.gemini_available() is True


# ---------------------------------------------------------------------------
# 10. Job queue claim is atomic; process_queue reaps stale running jobs
# ---------------------------------------------------------------------------

def test_mark_job_running_claim_is_atomic(temp_db):
    import job_queue

    job_queue.init_job_queue_schema()
    job_id = job_queue.enqueue_job("amendment_questions", target_resource="A1", payload={"topic_id": "PH2_FM_REGS"})
    assert job_queue.mark_job_running(job_id) is True
    assert job_queue.mark_job_running(job_id) is False
    conn = _conn()
    row = conn.execute("SELECT status FROM job_queue WHERE job_id = ?", (job_id,)).fetchone()
    conn.close()
    assert row["status"] == "running"


def test_process_queue_reaps_stale_running_jobs(temp_db):
    import job_queue
    from datetime import datetime, timedelta

    job_queue.init_job_queue_schema()
    job_id = job_queue.enqueue_job(
        "amendment_questions",
        target_resource="A1",
        payload={"topic_id": "PH2_FM_REGS", "count": 1},
    )
    stale = (datetime.now() - timedelta(minutes=31)).isoformat()
    conn = _conn()
    conn.execute(
        "UPDATE job_queue SET status = ?, started_at = ? WHERE job_id = ?",
        ("running", stale, job_id),
    )
    conn.commit()
    conn.close()

    # Fresh running jobs must not be reaped
    fresh_id = job_queue.enqueue_job("amendment_questions", target_resource="A2", payload={})
    assert job_queue.mark_job_running(fresh_id) is True

    async def fake_execute(target, payload):
        return {"amendment_id": target, "questions_generated": 0, "question_ids": []}

    with patch.object(job_queue, "execute_amendment_questions", side_effect=fake_execute):
        results = asyncio.run(job_queue.process_queue())

    conn = _conn()
    stale_row = conn.execute("SELECT status, error_message FROM job_queue WHERE job_id = ?", (job_id,)).fetchone()
    fresh_row = conn.execute("SELECT status FROM job_queue WHERE job_id = ?", (fresh_id,)).fetchone()
    conn.close()
    assert stale_row["status"] == "complete"
    assert results["completed"] >= 1
    assert fresh_row["status"] == "running"


def test_generate_smart_mock_returns_503_when_gemini_unavailable(temp_db):
    import main

    conn = _conn()
    conn.execute("INSERT INTO documents (document_id, title) VALUES ('doc_503', 'x')")
    conn.commit()
    conn.close()

    with patch.object(main, "available_gemini_keys", return_value=[]):
        with patch.object(main, "gemini_available", return_value=False):
            with TestClient(main.app) as client:
                response = client.post("/api/generate-smart-mock", json={"total_questions": 5, "use_gemini": True})
                assert response.status_code == 503, response.text
