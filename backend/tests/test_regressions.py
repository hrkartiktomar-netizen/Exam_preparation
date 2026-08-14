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
    # A subsequent init_db repair must preserve the row
    db.init_db()
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

    with patch.object(main.db, "generate_smart_mock", side_effect=fake_generate_smart_mock):
        with TestClient(main.app) as client:
            response = client.post("/api/exams/start", json={"total_questions": 5})
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["question_count"] == 1
            question = data["questions"][0]
            assert question["expected_time_sec"] == 180
            assert question["negative_marking"] == -1
            assert question["correct_option"] == "B"


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
