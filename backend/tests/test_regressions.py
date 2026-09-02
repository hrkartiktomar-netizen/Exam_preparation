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
