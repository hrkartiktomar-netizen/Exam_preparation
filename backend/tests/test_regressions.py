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

import gc
import re
import sqlite3
import tempfile
import time
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
        gc.collect()
        for attempt in range(5):
            try:
                Path(temp_db_path).unlink(missing_ok=True)
                break
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))


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
    # Plan v6 6.4 unified SM-2: ease 2.5 -> 2.6, interval = round(5 * 2.6) = 13.
    assert rows[0]["interval_days"] == 13


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
# 9. /api/questions/search must not be shadowed by /api/questions/{question_id}
# ---------------------------------------------------------------------------

def test_questions_search_route_is_not_shadowed_by_question_id(temp_db):
    """Starlette resolves routes in registration order.

    /api/questions/search was registered ~1,579 lines after
    /api/questions/{question_id}, so the literal segment "search" was captured as
    a question_id and every call fell into that handler's not-found branch,
    returning 404 "Question not found". The search endpoint was dead code.
    """
    import main

    client = TestClient(main.app)

    # A missing required `query` can only produce a 422 from the search handler's
    # own signature; the {question_id} handler has no required query param and
    # would answer 404 instead. This makes the check independent of DB contents.
    missing_param = client.get("/api/questions/search")
    assert missing_param.status_code == 422, (
        f"expected a 422 from the search handler's required `query` param, "
        f"got {missing_param.status_code}: {missing_param.text}"
    )

    response = client.get("/api/questions/search", params={"query": "IFSCA"})
    shadowed = response.status_code == 404 and response.json().get("detail") == "Question not found"
    assert not shadowed, (
        f"/api/questions/search was swallowed by /api/questions/{{question_id}}: {response.text}"
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["query"] == "IFSCA"
    assert payload["total"] == len(payload["results"])


# ---------------------------------------------------------------------------
# 10. job_queue must honour a patched database.DB_PATH (test isolation)
# ---------------------------------------------------------------------------

def test_job_queue_schema_respects_patched_db_path(temp_db):
    """job_queue resolved its own DB_PATH constant at import time.

    The temp_db fixture rebinds database.DB_PATH only, so init_job_queue_schema()
    -- reached from the lifespan during `with TestClient(app)` -- created the
    job_queue table in the real backend/ifsca_exam.db rather than the temp DB.
    Tests mutated the production database and leaked state between runs.
    """
    import job_queue

    job_queue.init_job_queue_schema()

    conn = sqlite3.connect(temp_db)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='job_queue'"
        ).fetchone()
    finally:
        conn.close()

    assert row is not None, (
        "job_queue.init_job_queue_schema() ignored database.DB_PATH and wrote to "
        "the production database file instead of the test database"
    )


# ---------------------------------------------------------------------------
# 11. /api/exams/{id}/submit must publish the score scale and topic breakdown
# ---------------------------------------------------------------------------

def test_exam_submit_exposes_max_score_and_topic_breakdown(temp_db):
    """The results panel read keys the endpoint never sent.

    frontend/js/exam.js renders `result.total_score || result.score` over
    `result.max_score`, and iterates `result.topic_breakdown`. The endpoint
    returned `final_score` with no scale and only `weak_areas` -- a subset
    filtered to accuracy < 60 -- so the score always displayed as 0 and
    competent topics disappeared from the grid entirely.

    db.submit_mock normalises every mock to a 100-mark scale
    (marks_per_question = 100 / total_questions). That scale is a scoring
    invariant, so the scorer owns it and the endpoint republishes it rather
    than the client hard-coding a number it has no way to derive.
    """
    import main

    _insert_smart_mock(_conn())

    with TestClient(main.app) as client:
        response = client.post(
            "/api/exams/SM_T1/submit",
            json={
                "answers": [
                    {"question_id": "Q_T1", "selected_answer": "B", "time_spent_seconds": 10}
                ]
            },
        )

    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload.get("max_score") == 100.0, (
        f"endpoint did not publish the 100-mark scale submit_mock scores "
        f"against; keys present: {sorted(payload)}"
    )

    breakdown = payload.get("topic_breakdown")
    assert breakdown, (
        f"endpoint dropped the full per-topic breakdown; only weak_areas "
        f"(accuracy < 60) survived, so topics the candidate answered well "
        f"vanish from the results grid. keys present: {sorted(payload)}"
    )

    entry = breakdown[0]
    for key in ("topic", "correct", "total"):
        assert key in entry, (
            f"topic_breakdown item is missing '{key}'; the results grid reads "
            f"t.correct and t.total, so it would render NaN. item: {entry}"
        )

    # weak_areas stays as the filtered subset -- a different question from the
    # breakdown, not a replacement for it.
    assert payload["weak_areas"] == []
    assert len(breakdown) == 1
    assert entry["correct"] == 1 and entry["total"] == 1


# ---------------------------------------------------------------------------
# 12. /api/drills/wrong-queue must cite the source document of a wrong answer
# ---------------------------------------------------------------------------

def test_wrong_queue_returns_the_source_document(temp_db):
    """The review view has a source line the endpoint never fed.

    frontend/js/views.js loadReview() renders a `.wrong-item__source` element
    guarded on a source field, but the endpoint selected only from
    question_attempts -- whose own `source` column records the attempt channel
    (SMART_MOCK / QRE), not where the fact came from. The guard therefore could
    never be true and the citation silently never rendered.

    questions.source does carry the originating document (32 distinct filenames
    across the bank), so the citation is one LEFT JOIN away. It is a LEFT JOIN
    because question_attempts.question_id is nullable and replayed drills may
    reference questions that are no longer in the bank; an inner join would drop
    those rows from the queue entirely.
    """
    import main

    conn = _conn()
    try:
        db.save_question(
            {
                "question_id": "Q_W1",
                "topic": "PH2_FM_REGS",
                "question_text": "Which regulation governs fund management?",
                "options": [
                    {"label": "A", "text": "x"},
                    {"label": "B", "text": "FME Regulations"},
                    {"label": "C", "text": "y"},
                    {"label": "D", "text": "z"},
                ],
                "correct_option": "B",
                "explanation": "FME",
                "source": "IFSCA_Compliance_Handbook.md",
                "difficulty": "easy",
                "source_policy": "exam_material",
            },
            created_by="test",
        )
        conn.execute(
            """
            INSERT INTO question_attempts
            (mock_id, question_id, topic, question_text, correct_option, your_option,
             is_correct, time_spent_seconds, attempt_date, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("SM_W1", "Q_W1", "PH2_FM_REGS", "Which regulation governs fund management?",
             "B", "C", 0, 12, "2026-09-01", "SMART_MOCK"),
        )
        conn.commit()
    finally:
        conn.close()

    with TestClient(main.app) as client:
        response = client.get("/api/drills/wrong-queue?limit=10")

    assert response.status_code == 200, response.text
    items = response.json()["wrong_answers"]
    assert len(items) == 1, items
    row = items[0]

    assert row.get("correct_option") == "B", row
    assert row.get("your_option") == "C", row
    assert row.get("source_document") == "IFSCA_Compliance_Handbook.md", (
        f"endpoint did not join questions.source, so the review view's citation "
        f"line can never render; keys present: {sorted(row)}"
    )


# ---------------------------------------------------------------------------
# 13. /api/descriptive/grade must reject a payload carrying no answer text
# ---------------------------------------------------------------------------

def test_descriptive_grade_rejects_payload_without_answer_text(temp_db):
    """A grade request with no answer text used to return 200 and a zero score.

    DescriptiveGradeRequestModel takes one field per component (essay_text,
    precis_text, rc_answers). The descriptive view posted {response_text,
    exam_type} instead, and Pydantic's default is to ignore unknown keys, so
    every answer field kept its empty default and the endpoint graded nothing --
    answering 200 with total_score 0.0 and components []. A client cannot tell
    that apart from a genuinely zero-scoring essay, which is why the mismatched
    payload survived unnoticed. Validation belongs at the boundary so that a
    request carrying no answer is loud rather than silently scoreless.
    """
    import main

    with TestClient(main.app) as client:
        stale = client.post(
            "/api/descriptive/grade",
            json={"response_text": "A precis of the passage.", "exam_type": "IFSCA"},
        )
        assert stale.status_code == 422, (
            f"payload with no recognised answer field was accepted with "
            f"{stale.status_code}: {stale.text[:200]}"
        )

        empty = client.post("/api/descriptive/grade", json={"exam": "IFSCA"})
        assert empty.status_code == 422, (
            f"payload with every answer field empty was accepted with "
            f"{empty.status_code}: {empty.text[:200]}"
        )


# ---------------------------------------------------------------------------
# 14. GET /api/pyq/sitting must return a whole sitting, not a single paper
# ---------------------------------------------------------------------------

# A sitting is not a paper. In the real bank, 2024 Phase 1 spans two exams and
# two papers (280 rows) and 2022 Phase 1 spans two exams and two papers (109
# rows), but /api/pyq/{doc_id}/load can only ever return one
# (exam, year, phase, paper) tuple, and /api/pyq/drill filters on subject_id --
# which is NULL on 109 real rows, so it cannot reach them at all. This fixture
# reproduces that shape in miniature: two subjects that each restart
# question_number at 1, a second paper, a second exam, and a row with no subject.
_SITTING_ROWS = [
    # (pyq_id, exam, paper, subject_id, question_number, question_text, incomplete)
    ("S_QUANT_1", "IFSCA", 1, "SUBJ_QUANT", 1, "IFSCA P1 QUANT q1", 0),
    ("S_QUANT_2", "IFSCA", 1, "SUBJ_QUANT", 2, "IFSCA P1 QUANT q2", 0),
    ("S_ENG_1", "IFSCA", 1, "SUBJ_ENGLISH", 1, "IFSCA P1 ENGLISH q1", 0),
    ("S_ENG_2", "IFSCA", 1, "SUBJ_ENGLISH", 2, "IFSCA P1 ENGLISH q2", 0),
    ("S_P2_QUANT_1", "IFSCA", 2, "SUBJ_QUANT", 1, "IFSCA P2 QUANT q1", 0),
    ("S_SEBI_1", "SEBI", 1, None, 1, "SEBI P1 UNSUBJECTED q1", 0),
    ("S_INCOMPLETE", "IFSCA", 1, "SUBJ_QUANT", 3, "IFSCA P1 QUANT q3 INCOMPLETE", 1),
]


def _seed_sitting() -> None:
    conn = _conn()
    try:
        already = conn.execute("SELECT COUNT(*) FROM previous_year_questions").fetchone()[0]
        assert already == 0, (
            f"temp_db arrived with {already} previous_year_questions rows; the "
            f"exact counts below assume a clean table"
        )
        for pyq_id, exam, paper, subject, qnum, text, incomplete in _SITTING_ROWS:
            conn.execute(
                """
                INSERT INTO previous_year_questions
                (pyq_id, exam, year, phase, paper, subject_id, question_number,
                 question_text, option_a, option_b, option_c, option_d,
                 correct_option, marks, incomplete)
                VALUES (?, ?, 2024, 1, ?, ?, ?, ?, 'a', 'b', 'c', 'd', 'A', 1, ?)
                """,
                (pyq_id, exam, paper, subject, qnum, text, incomplete),
            )
        conn.commit()
    finally:
        conn.close()


def _sitting_client():
    """A TestClient that does NOT run the lifespan.

    The endpoint under test reads SQLite and writes only the in-process answer
    cache, so it needs no startup. Running the lifespan would call
    db.bootstrap_from_knowledge(), which seeds previous_year_questions from the
    committed knowledge pack and would quietly change every count asserted here.
    """
    import main

    return TestClient(main.app)


def test_pyq_sitting_returns_every_paper_in_subject_order(temp_db):
    """One year+phase must yield the whole sitting, grouped so numbering reads.

    question_number restarts per subject -- the real bank has 170
    (year, phase, paper, question_number) groups that repeat, and every one of
    them holds distinct questions, so ordering by question_number alone
    interleaves subjects and reads as a shuffled paper. Deduping those repeats
    would destroy real exam content, so the count must survive intact.
    """
    _seed_sitting()

    response = _sitting_client().get("/api/pyq/sitting", params={"year": 2024, "phase": 1})

    assert response.status_code == 200, response.text
    session = response.json()

    assert session["total_questions"] == 6, (
        f"expected the 6 complete rows of the sitting; the incomplete row must be "
        f"excluded and the repeated per-subject question numbers must NOT be "
        f"deduped. got {session.get('total_questions')}"
    )

    order = [q["question_text"] for q in session["questions"]]
    assert order == [
        "IFSCA P1 ENGLISH q1",
        "IFSCA P1 ENGLISH q2",
        "IFSCA P1 QUANT q1",
        "IFSCA P1 QUANT q2",
        "IFSCA P2 QUANT q1",
        "SEBI P1 UNSUBJECTED q1",
    ], (
        f"questions were not grouped by paper then subject, so per-subject "
        f"numbering interleaves: {order}"
    )

    assert session["exam"] == "MIXED", (
        f"sitting spans IFSCA and SEBI but reported exam={session.get('exam')!r}"
    )
    assert "SEBI P1 UNSUBJECTED q1" in order, (
        "the row with no subject_id was dropped; /api/pyq/drill filters on "
        "subject_id and cannot serve those 109 real rows, so this endpoint is "
        "the only route to them"
    )


def test_pyq_sitting_session_id_cannot_collide_with_paper_load(temp_db):
    """The sitting's cache key must stay out of the single-paper namespace.

    /api/pyq/{pyq_id}/submit grades against pyq_cache.get_pyq_questions(pyq_id),
    and /api/pyq/{doc_id}/load caches under PYQ_DOC{EXAM}_{year}_P{phase}_PAPER{n}.
    The two order rows differently, so if a sitting narrowed to one paper reused
    that key it would overwrite the cached answer set of an attempt already in
    flight and silently misgrade it.
    """
    import pyq_cache

    _seed_sitting()
    client = _sitting_client()

    session = client.get(
        "/api/pyq/sitting", params={"year": 2024, "phase": 1, "exam": "IFSCA", "paper": 1}
    ).json()

    load_ids = {
        f"PYQ_DOC{exam}_2024_P1_PAPER{paper}"
        for exam in ("IFSCA", "SEBI")
        for paper in (1, 2)
    }
    assert session["pyq_id"] not in load_ids, (
        f"sitting session id {session['pyq_id']!r} collides with an id that "
        f"/api/pyq/{{doc_id}}/load mints for the same sitting"
    )
    assert session["exam"] == "IFSCA", (
        f"narrowed to one exam but reported {session.get('exam')!r}"
    )
    assert pyq_cache.get_pyq_questions(session["pyq_id"]), (
        "the sitting was not cached under its own id, so it cannot be submitted"
    )


def test_pyq_sitting_narrows_by_exam_and_paper_and_404s_when_empty(temp_db):
    _seed_sitting()
    client = _sitting_client()

    by_paper = client.get(
        "/api/pyq/sitting", params={"year": 2024, "phase": 1, "paper": 2}
    )
    assert by_paper.status_code == 200, by_paper.text
    assert by_paper.json()["total_questions"] == 1, by_paper.text

    by_exam = client.get(
        "/api/pyq/sitting", params={"year": 2024, "phase": 1, "exam": "SEBI"}
    )
    assert by_exam.status_code == 200, by_exam.text
    assert by_exam.json()["total_questions"] == 1, by_exam.text

    # 2021 is in bounds but the fixture seeds only 2024, so this exercises the
    # empty-result path rather than the parameter-bound path below.
    missing = client.get("/api/pyq/sitting", params={"year": 2021, "phase": 1})
    assert missing.status_code == 404, (
        f"an empty sitting answered {missing.status_code}; /api/pyq/drill 404s "
        f"on an empty result set and this endpoint should match: {missing.text[:200]}"
    )

    unbounded = client.get("/api/pyq/sitting", params={"year": 2024, "phase": 99})
    assert unbounded.status_code == 422, (
        f"phase=99 was accepted with {unbounded.status_code}; phase is bounded "
        f"to 1..4 so an out-of-range sitting is rejected at the boundary"
    )


# ---------------------------------------------------------------------------
# 15. POST /api/pyq/{pyq_id}/submit must publish the paper's real max_score
# ---------------------------------------------------------------------------

# frontend/js/exam.js renders the score as `result.final_score / result.max_score`
# and falls back to `examState.questions.length` when max_score is absent. That
# fallback is wrong for this bank: marks are 1 (400 rows), 1.25 (298 rows) and 2
# (350 rows), so on a 2-mark paper final_score can reach twice the question count
# and the panel reads "80 / 50". These seeds use marks != 1 so the expected
# max_score can never be mistaken for the question count.

def _seed_marked_sitting(year: int, marks: float, count: int) -> None:
    conn = _conn()
    try:
        already = conn.execute("SELECT COUNT(*) FROM previous_year_questions").fetchone()[0]
        assert already == 0, (
            f"temp_db arrived with {already} previous_year_questions rows; the "
            f"exact scores below assume a clean table"
        )
        for qnum in range(1, count + 1):
            conn.execute(
                """
                INSERT INTO previous_year_questions
                (pyq_id, exam, year, phase, paper, subject_id, question_number,
                 question_text, option_a, option_b, option_c, option_d,
                 correct_option, marks, incomplete)
                VALUES (?, 'IFSCA', ?, 1, 1, 'SUBJ_QUANT', ?, ?, 'a', 'b', 'c', 'd', 'A', ?, 0)
                """,
                (f"M_{year}_{qnum}", year, qnum, f"MARKED {year} q{qnum}", marks),
            )
        conn.commit()
    finally:
        conn.close()


def _submit(client, pyq_id: str, selected: dict[int, str | None]):
    """POST an attempt. selected maps question_number -> chosen option or None."""
    answers = [
        {
            "question_id": f"{pyq_id}_Q{qnum}",
            "selected_answer": choice,
            "time_spent_seconds": 5,
            "marked_for_review": False,
        }
        for qnum, choice in selected.items()
    ]
    return client.post(f"/api/pyq/{pyq_id}/submit", json={"answers": answers})


def test_pyq_submit_reports_max_score_from_the_papers_real_marking(temp_db):
    """A 2-mark paper's ceiling is marks x questions, not the question count."""
    _seed_marked_sitting(2024, marks=2, count=3)
    client = _sitting_client()

    session = client.get("/api/pyq/sitting", params={"year": 2024, "phase": 1}).json()
    assert session["marks_per_question"] == 2, session

    response = _submit(client, session["pyq_id"], {1: "A", 2: "B", 3: None})
    assert response.status_code == 200, response.text
    result = response.json()

    # Guards the payload actually parsed. Pydantic v2 defaults to extra='ignore',
    # so a mis-spelled answer field is silently dropped and still returns 200 with
    # a zero score -- which would make the max_score assertion below pass for the
    # wrong reason.
    assert result["total_answered"] == 2, result
    assert result["total_correct"] == 1, result

    assert "max_score" in result, (
        f"submit returned no max_score ({sorted(result)}); exam.js then divides by "
        f"the question count and a 2-mark paper reads '4 / 3'"
    )
    assert result["max_score"] == 6.0, (
        f"max_score was {result.get('max_score')!r}, expected 3 questions x 2 marks"
    )
    # raw 2 - negative 0.5 = 1.5, proving the session's real marking was used.
    assert result["final_score"] == 1.5, result


def test_pyq_submit_max_score_keeps_fractional_marks_exact(temp_db):
    """1.25-mark papers must not lose the fraction to integer rounding."""
    _seed_marked_sitting(2023, marks=1.25, count=3)
    client = _sitting_client()

    session = client.get("/api/pyq/sitting", params={"year": 2023, "phase": 1}).json()
    assert session["marks_per_question"] == 1.25, session

    response = _submit(client, session["pyq_id"], {1: "A", 2: "A", 3: "A"})
    assert response.status_code == 200, response.text
    result = response.json()

    assert result["total_correct"] == 3, result
    assert result["max_score"] == 3.75, (
        f"max_score was {result.get('max_score')!r}, expected 3 x 1.25 = 3.75"
    )
    assert result["final_score"] == result["max_score"], (
        f"all correct but final_score {result['final_score']} != max_score "
        f"{result['max_score']}"
    )


# ---------------------------------------------------------------------------
# 16. GET /api/pyq/list must publish the subject enum /api/pyq/drill needs
# ---------------------------------------------------------------------------

def test_pyq_list_publishes_subjects_so_the_drill_is_reachable(temp_db):
    """/api/pyq/drill requires subject_id, but nothing published the valid values.

    A client could only reach the drill by hardcoding the enum, which drifts the
    moment a subject is renamed or added. Counts cover complete rows only,
    because that is what the drill serves -- advertising a subject whose
    questions are all incomplete would offer a picker entry that 404s.

    The NULL-subject row is deliberately absent. The drill filters with
    `subject_id = ?`, which can never match NULL, so listing it would offer a
    choice that returns nothing; /api/pyq/sitting is the route to those rows.
    """
    _seed_sitting()

    response = _sitting_client().get("/api/pyq/list")
    assert response.status_code == 200, response.text
    payload = response.json()

    # The papers half is the existing contract and must survive unchanged.
    # _SITTING_ROWS spans three (exam, paper) tuples: IFSCA p1, IFSCA p2, SEBI p1.
    assert payload["status"] == "ok", payload
    assert len(payload["papers"]) == 3, payload["papers"]

    assert "subjects" in payload, (
        f"/api/pyq/list published no subjects ({sorted(payload)}), so the drill "
        f"endpoint has no discoverable subject_id values"
    )
    assert payload["subjects"] == [
        {"subject_id": "SUBJ_QUANT", "question_count": 3},
        {"subject_id": "SUBJ_ENGLISH", "question_count": 2},
    ], (
        f"subjects were {payload['subjects']}; expected the complete rows grouped "
        f"by subject, most drillable first, with the NULL-subject row excluded"
    )


def test_pyq_drill_serves_a_subject_the_list_advertised(temp_db):
    """The advertised subject_id must actually return questions from the drill."""
    _seed_sitting()
    client = _sitting_client()

    subjects = client.get("/api/pyq/list").json()["subjects"]
    assert subjects, "no subjects were advertised"

    for entry in subjects:
        response = client.get(
            "/api/pyq/drill", params={"subject_id": entry["subject_id"], "limit": 5}
        )
        assert response.status_code == 200, (
            f"/api/pyq/list advertised {entry['subject_id']} with "
            f"{entry['question_count']} questions but the drill answered "
            f"{response.status_code}: {response.text[:200]}"
        )
        assert response.json()["total_questions"] > 0, response.text


# ---------------------------------------------------------------------------
# 17. GET /api/pyq/drill must key its cache on the request, not on a random row
# ---------------------------------------------------------------------------

# The drill draws with ORDER BY RANDOM() and then built its pyq_id from rows[0]:
# f"PYQ_DOC{exam}_{year}_P{phase}_PAPER{paper}" with year pinned to 0. Two
# different subjects therefore mint the SAME id whenever their first random rows
# share (exam, phase, paper) -- observed live as PYQ_DOCSEBI_0_P1_PAPER1. The
# second drill overwrites the first's cached answers under that shared id, and
# because _format_bank_session also renumbers from 1 the question_ids are
# identical too, so submitting the attempt already in flight matches by position
# and grades it against the other subject's key. /api/pyq/sitting avoids exactly
# this with its own SITTING namespace; the drill needs the same treatment.
#
# Every seed row shares one (year, phase, paper) so the collision is guaranteed
# rather than something the random draw may or may not produce.
_DRILL_ROWS = [
    # (pyq_id, exam, subject_id, correct_option)
    ("D_ALPHA_IFSCA", "IFSCA", "SUBJ_ALPHA", "A"),
    ("D_BETA_IFSCA", "IFSCA", "SUBJ_BETA", "C"),
    ("D_ALPHA_SEBI", "SEBI", "SUBJ_ALPHA", "B"),
]


def _seed_drill_pair() -> None:
    conn = _conn()
    try:
        already = conn.execute("SELECT COUNT(*) FROM previous_year_questions").fetchone()[0]
        assert already == 0, (
            f"temp_db arrived with {already} previous_year_questions rows; the "
            f"single-row draws below assume a clean table"
        )
        for pyq_id, exam, subject, correct in _DRILL_ROWS:
            conn.execute(
                """
                INSERT INTO previous_year_questions
                (pyq_id, exam, year, phase, paper, subject_id, question_number,
                 question_text, option_a, option_b, option_c, option_d,
                 correct_option, marks, incomplete)
                VALUES (?, ?, 2024, 1, 1, ?, 1, ?, 'a', 'b', 'c', 'd', ?, 1, 0)
                """,
                (pyq_id, exam, subject, f"{subject} on {exam}", correct),
            )
        conn.commit()
    finally:
        conn.close()


def _drill(client, subject_id: str, exam: str | None = None):
    params: dict[str, object] = {"subject_id": subject_id, "limit": 5}
    if exam:
        params["exam"] = exam
    response = client.get("/api/pyq/drill", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_pyq_drill_attempt_is_not_misgraded_by_a_second_drill(temp_db):
    """Opening a second drill must not rewrite the key of the first attempt."""
    _seed_drill_pair()
    client = _sitting_client()

    # One row each, so ORDER BY RANDOM() cannot reorder the numbering and the
    # correct option the seed chose is the one the served question carries.
    alpha = _drill(client, "SUBJ_ALPHA", exam="IFSCA")
    beta = _drill(client, "SUBJ_BETA", exam="IFSCA")

    assert alpha["pyq_id"] != beta["pyq_id"], (
        f"two different subject drills both minted {alpha['pyq_id']!r}; the "
        f"second call overwrote the first's cached answers under that shared id"
    )

    # ALPHA's single question is correct at 'A'. Submitting ALPHA's own id must
    # still be graded against ALPHA's key even though BETA was opened after it.
    submitted = client.post(
        f"/api/pyq/{alpha['pyq_id']}/submit",
        json={
            "answers": [
                {
                    "question_id": alpha["questions"][0]["question_id"],
                    "selected_answer": "A",
                    "time_spent_seconds": 4,
                    "marked_for_review": False,
                }
            ]
        },
    )
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()
    assert result["total_correct"] == 1, (
        f"the right answer scored {result['total_correct']}/1: ALPHA's attempt "
        f"was graded against BETA's cached key (BETA is correct at 'C')"
    )


def test_pyq_drill_cache_key_is_stable_per_request_and_not_a_random_row(temp_db):
    """The key must be a function of the request, and stay out of the paper space."""
    _seed_drill_pair()
    client = _sitting_client()

    alpha_ifsca = _drill(client, "SUBJ_ALPHA", exam="IFSCA")
    alpha_again = _drill(client, "SUBJ_ALPHA", exam="IFSCA")
    beta_ifsca = _drill(client, "SUBJ_BETA", exam="IFSCA")
    alpha_sebi = _drill(client, "SUBJ_ALPHA", exam="SEBI")
    alpha_mixed = _drill(client, "SUBJ_ALPHA")

    assert alpha_ifsca["pyq_id"] == alpha_again["pyq_id"], (
        f"the same drill request minted {alpha_ifsca['pyq_id']!r} then "
        f"{alpha_again['pyq_id']!r}; a re-opened drill would orphan the attempt "
        f"already cached under the first id"
    )
    assert len({alpha_ifsca["pyq_id"], beta_ifsca["pyq_id"], alpha_sebi["pyq_id"],
                alpha_mixed["pyq_id"]}) == 4, (
        "each distinct drill request needs its own key: "
        f"ALPHA/IFSCA={alpha_ifsca['pyq_id']!r} BETA/IFSCA={beta_ifsca['pyq_id']!r} "
        f"ALPHA/SEBI={alpha_sebi['pyq_id']!r} ALPHA/unfiltered={alpha_mixed['pyq_id']!r}"
    )

    # The unfiltered draw spans both exams, so it serves both rows.
    assert alpha_mixed["total_questions"] == 2, alpha_mixed["total_questions"]

    # The key namespace must not double as a human-readable exam label, and must
    # stay out of the IFSCA_{year}_P{phase}_PAPER{paper} space that
    # /api/pyq/{doc_id}/load parses.
    for session in (alpha_ifsca, beta_ifsca, alpha_sebi, alpha_mixed):
        assert session["exam"] in ("IFSCA", "SEBI", "MIXED"), (
            f"drill reported exam={session['exam']!r}, which is a cache-key "
            f"fragment rather than an exam label"
        )
        assert not re.match(r"^(IFSCA|SEBI)_\d{4}_P\d+_PAPER\d+$", session["pyq_id"][len("PYQ_DOC"):]), (
            f"drill id {session['pyq_id']!r} is parseable as a real paper, so it "
            f"could collide with /api/pyq/{{doc_id}}/load"
        )


# ---------------------------------------------------------------------------
# 18. The PYQ post-attempt read path must report a title, not a cache key
# ---------------------------------------------------------------------------

# submit_pyq_attempt resolves pyq_title with
#     SELECT title FROM documents WHERE document_id = pyq_id.removeprefix("PYQ_DOC")
# but documents.document_id holds values like 'doc_ifsca_act_2019' -- a different
# namespace from PYQ doc ids like 'IFSCA_2024_P2_PAPER2'. The lookup returns no
# row for any PYQ session, so pyq_title always falls back to the raw cache key.
# Confirmed against the live database: its one pyq_sessions row stores
# pyq_title == 'PYQ_DOCIFSCA_2024_P2_PAPER2'.
#
# /api/pyq/analytics publishes pyq_title as the attempt's display name, so
# anything rendering that list shows cache keys. The real title already exists:
# _format_bank_session is handed one and returns it, it is simply never carried
# into the cache that submit later reads.
_SITTING_TITLE = "IFSCA Grade A 2024 - Phase 1 sitting"


def test_pyq_session_stores_a_readable_title_not_the_cache_key(temp_db):
    """pyq_sessions.pyq_title must be the title the load response advertised."""
    _seed_sitting()
    client = _sitting_client()

    response = client.get(
        "/api/pyq/sitting", params={"year": 2024, "phase": 1, "exam": "IFSCA", "limit": 50}
    )
    assert response.status_code == 200, response.text
    session = response.json()
    assert session["title"] == _SITTING_TITLE, session["title"]

    # Every seeded row is correct at 'A', so q1 right and q2 wrong is exact:
    # marks 1, negative 0.25 -> raw 1.0, penalty 0.25, final 0.75.
    submit_response = _submit(client, session["pyq_id"], {1: "A", 2: "B"})
    assert submit_response.status_code == 200, submit_response.text

    conn = _conn()
    try:
        row = conn.execute(
            "SELECT pyq_id, pyq_title, score, accuracy, total_questions, status "
            "FROM pyq_sessions WHERE pyq_id = ?",
            (session["pyq_id"],),
        ).fetchone()
    finally:
        # A leaked handle keeps the temp .db open and the fixture's unlink then
        # raises PermissionError on Windows.
        conn.close()
    assert row is not None, "submit wrote no pyq_sessions row"
    assert row["pyq_title"] == _SITTING_TITLE, (
        f"pyq_sessions stored pyq_title={row['pyq_title']!r}, the in-process "
        f"cache key, instead of the title {session['title']!r} that "
        f"/api/pyq/sitting advertised for this attempt"
    )
    assert row["status"] == "completed", row["status"]
    assert row["score"] == 0.75, row["score"]
    assert row["accuracy"] == 20.0, row["accuracy"]


def test_pyq_analytics_and_answer_reveal_report_the_completed_attempt(temp_db):
    """The two post-attempt endpoints must agree with what submit persisted."""
    _seed_sitting()
    client = _sitting_client()

    session = client.get(
        "/api/pyq/sitting", params={"year": 2024, "phase": 1, "exam": "IFSCA", "limit": 50}
    ).json()
    pyq_id = session["pyq_id"]
    submit_response = _submit(client, pyq_id, {1: "A", 2: "B"})
    assert submit_response.status_code == 200, submit_response.text
    submitted = submit_response.json()
    assert submitted["total_correct"] == 1, submitted
    assert submitted["total_wrong"] == 1, submitted

    analytics = client.get("/api/pyq/analytics")
    assert analytics.status_code == 200, analytics.text
    payload = analytics.json()
    assert payload["status"] == "ok", payload
    assert payload["total_pyq_attempts"] == 1, payload
    attempt = payload["attempts"][0]
    assert attempt["pyq_id"] == pyq_id, attempt
    assert attempt["pyq_title"] == _SITTING_TITLE, (
        f"/api/pyq/analytics advertised pyq_title={attempt['pyq_title']!r}; the "
        f"results list this feeds would show a cache key instead of a paper name"
    )
    assert attempt["score"] == 0.75, attempt
    assert attempt["accuracy"] == 20.0, attempt
    assert attempt["questions_attempted"] == 2, attempt
    assert attempt["correct_count"] == 1, attempt

    reveal = client.get(f"/api/pyq/{pyq_id}/answers")
    assert reveal.status_code == 200, reveal.text
    answers = reveal.json()["answers"]
    assert [a["question_number"] for a in answers] == [1, 2], answers
    # The reveal is the one place the official answer may be published: the
    # attempt is already graded and cached answers cleared.
    assert all(a["official_answer"] == "A" for a in answers), answers
    assert [a["selected_answer"] for a in answers] == ["A", "B"], answers
    assert [a["is_correct"] for a in answers] == [1, 0], answers
    assert all(a["time_spent_seconds"] == 5 for a in answers), answers
