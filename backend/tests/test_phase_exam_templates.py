"""Tests for the phase/paper exam feature: catalogue, endpoint, and exam start.

Covers three things that one feature depends on:
  1. db.list_exam_templates -- which templates can actually generate an exam.
  2. GET /api/exam-templates -- the wire contract the picker renders.
  3. POST /api/exams/start -- that the chosen template reaches generate_smart_mock
     and that the paper's own time limit replaces the hardcoded hour.

The conftest `test_db` fixture runs SCHEMA plus migration 002 only, and
TestClient is built without a context manager so `lifespan` (and therefore
db.init_db) never runs. exam_templates is created by migration 005, so tests
that need the table create and seed it via db._run_migration_005 -- the same
house pattern conftest uses for migration 002.

The exam-start tests monkeypatch db.generate_smart_mock. This worktree has no
Gemini keys, so the real function raises before it reads template_id; without
the spy these tests would fail environmentally and prove nothing.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

import pytest

import database as db


# Mirrors the 10 rows in backend/ifsca_exam.db at plan-authoring time.
# Column order matches _COLUMNS below.
LIVE_TEMPLATES: list[dict[str, Any]] = [
    {
        "template_id": "CUSTOM", "exam": "ANY", "name": "Custom mock",
        "phase": None, "paper": None, "total_questions": 50,
        "marks_per_question": 1.0, "total_marks": None, "time_limit_minutes": 60,
        "cutoff_pct": None, "aggregate_cutoff_pct": None,
        "sections_json": "[]", "syllabus_units_json": "[]",
        "descriptive_components_json": "[]", "notes": None,
    },
    {
        "template_id": "IFSCA_PH1_P1", "exam": "IFSCA",
        "name": "IFSCA Phase I Paper 1 (all streams)",
        "phase": 1, "paper": 1, "total_questions": 100,
        "marks_per_question": 1.0, "total_marks": 100, "time_limit_minutes": 60,
        "cutoff_pct": 30.0, "aggregate_cutoff_pct": None,
        "sections_json": json.dumps([
            {"name": "General Awareness (Financial Sector)", "questions": 25},
            {"name": "English Language", "questions": 25},
            {"name": "Quantitative Aptitude", "questions": 25},
            {"name": "Reasoning", "questions": 25},
        ]),
        "syllabus_units_json": "[]", "descriptive_components_json": "[]",
        "notes": "Screening only; marks not counted for final selection.",
    },
    {
        "template_id": "IFSCA_PH1_P2_GENERAL", "exam": "IFSCA",
        "name": "IFSCA Phase I Paper 2 (General stream)",
        "phase": 1, "paper": 2, "total_questions": 50,
        "marks_per_question": 2.0, "total_marks": 100, "time_limit_minutes": 60,
        "cutoff_pct": 40.0, "aggregate_cutoff_pct": None,
        "sections_json": "[]",
        "syllabus_units_json": json.dumps([
            "General knowledge & current events",
            "Economic & social development",
            "Commerce & accountancy",
            "Management", "Finance", "Costing",
            "Indian & global economy",
            "GoI financial-sector schemes",
        ]),
        "descriptive_components_json": "[]",
        "notes": "Aggregate cut-off across both Phase I papers: 40%.",
    },
    {
        "template_id": "IFSCA_PH2_P1_DESC", "exam": "IFSCA",
        "name": "IFSCA Phase II Paper 1 (Descriptive English)",
        "phase": 2, "paper": 1, "total_questions": None,
        "marks_per_question": None, "total_marks": 100, "time_limit_minutes": 60,
        "cutoff_pct": 30.0, "aggregate_cutoff_pct": None,
        "sections_json": "[]", "syllabus_units_json": "[]",
        "descriptive_components_json": json.dumps([
            {"type": "ESSAY", "marks": 30, "word_limit_min": 200, "word_limit_max": 400},
            {"type": "PRECIS", "marks": 35, "word_limit_min": 120, "word_limit_max": 130, "title_required": True},
            {"type": "RC", "marks": 35, "answers_in_own_words": True},
        ]),
        "notes": "Typed on computer; one question displayed at a time.",
    },
    {
        "template_id": "IFSCA_PH2_P2_GENERAL", "exam": "IFSCA",
        "name": "IFSCA Phase II Paper 2 (General stream)",
        "phase": 2, "paper": 2, "total_questions": 50,
        "marks_per_question": 2.0, "total_marks": 100, "time_limit_minutes": 60,
        "cutoff_pct": 40.0, "aggregate_cutoff_pct": None,
        "sections_json": "[]",
        "syllabus_units_json": json.dumps([
            "IFSCA Act/IFSCA/IFSC/GIFT IFSC/GIFT City/Global Financial Centres",
            "Union Budget & Economic Survey", "Banking", "Capital Market",
            "Insurance", "Pension Sector",
        ]),
        "descriptive_components_json": "[]", "notes": None,
    },
    {
        "template_id": "SEBI_PH1_P1", "exam": "SEBI", "name": "SEBI Phase 1 Paper 1",
        "phase": 1, "paper": 1, "total_questions": 80,
        "marks_per_question": 1.25, "total_marks": 100, "time_limit_minutes": 60,
        "cutoff_pct": 30.0, "aggregate_cutoff_pct": None,
        "sections_json": json.dumps([
            {"name": "General Awareness", "questions": 20, "marks": 25},
            {"name": "English Language", "questions": 20, "marks": 25},
            {"name": "Quantitative Aptitude", "questions": 20, "marks": 25},
            {"name": "Reasoning", "questions": 20, "marks": 25},
        ]),
        "syllabus_units_json": "[]", "descriptive_components_json": "[]",
        "notes": None,
    },
    {
        "template_id": "SEBI_PH1_P2_GENERAL", "exam": "SEBI",
        "name": "SEBI Phase 1 Paper 2 (General stream)",
        "phase": 1, "paper": 2, "total_questions": 50,
        "marks_per_question": 2.0, "total_marks": 100, "time_limit_minutes": 40,
        "cutoff_pct": 40.0, "aggregate_cutoff_pct": None,
        "sections_json": "[]",
        "syllabus_units_json": json.dumps([
            "Commerce & Accountancy", "Management", "Finance", "Costing",
            "Companies Act", "Economics",
        ]),
        "descriptive_components_json": "[]", "notes": None,
    },
    {
        "template_id": "SEBI_PH2_P1_DESC", "exam": "SEBI",
        "name": "SEBI Phase 2 Paper 1 (Descriptive)",
        "phase": 2, "paper": 1, "total_questions": None,
        "marks_per_question": None, "total_marks": 100, "time_limit_minutes": 60,
        "cutoff_pct": 30.0, "aggregate_cutoff_pct": None,
        "sections_json": "[]", "syllabus_units_json": "[]",
        "descriptive_components_json": json.dumps([
            {"type": "ESSAY", "marks": 30, "word_limit_min": 250, "word_limit_max": 270, "topics_offered": 4},
            {"type": "PRECIS", "marks": 30, "word_limit_min": 140, "word_limit_max": 160, "title_required": True},
            {"type": "RC", "marks": 40, "questions": 5},
        ]),
        "notes": "Letter Writing appears in the 2025 TOC.",
    },
    {
        "template_id": "SEBI_PH2_P2_GENERAL", "exam": "SEBI",
        "name": "SEBI Phase 2 Paper 2 (General stream)",
        "phase": 2, "paper": 2, "total_questions": 100,
        "marks_per_question": 1.0, "total_marks": 100, "time_limit_minutes": 90,
        "cutoff_pct": 40.0, "aggregate_cutoff_pct": 50.0,
        "sections_json": "[]",
        "syllabus_units_json": json.dumps([
            "Commerce & Accountancy", "Management", "Finance", "Costing",
            "Companies Act", "Economics",
        ]),
        "descriptive_components_json": "[]",
        "notes": "Post-2024 pattern: 100 x 1 mark (2022 was 50 x 2 marks).",
    },
    {
        "template_id": "SUBJECT_DRILL", "exam": "ANY",
        "name": "Subject drill (cross-exam)",
        "phase": None, "paper": None, "total_questions": 20,
        "marks_per_question": 1.0, "total_marks": None, "time_limit_minutes": 20,
        "cutoff_pct": None, "aggregate_cutoff_pct": None,
        "sections_json": "[]", "syllabus_units_json": "[]",
        "descriptive_components_json": "[]",
        "notes": "Mixed IFSCA/SEBI bank questions filtered by subject_id.",
    },
]

_COLUMNS = (
    "template_id, exam, name, phase, paper, total_questions, marks_per_question, "
    "total_marks, time_limit_minutes, cutoff_pct, aggregate_cutoff_pct, "
    "sections_json, syllabus_units_json, descriptive_components_json, notes"
)

# The 7 rows a user can actually start an exam from, in catalogue order.
EXPECTED_ORDER = [
    "CUSTOM",
    "IFSCA_PH1_P1",
    "IFSCA_PH1_P2_GENERAL",
    "IFSCA_PH2_P2_GENERAL",
    "SEBI_PH1_P1",
    "SEBI_PH1_P2_GENERAL",
    "SEBI_PH2_P2_GENERAL",
]


def _seed_templates(db_path: str, rows: list[dict[str, Any]] | None = None) -> None:
    """Create exam_templates via migration 005 and insert `rows` (default: all 10 live rows)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        db._run_migration_005(conn)
        conn.commit()
        for row in rows if rows is not None else LIVE_TEMPLATES:
            conn.execute(
                f"INSERT INTO exam_templates ({_COLUMNS}) VALUES ({','.join('?' * 15)})",
                tuple(row[column] for column in _COLUMNS.split(", ")),
            )
        conn.commit()
    finally:
        conn.close()


def test_list_exam_templates_returns_the_seven_generatable_rows(test_db: str) -> None:
    _seed_templates(test_db)
    templates = db.list_exam_templates()
    assert [t["template_id"] for t in templates] == EXPECTED_ORDER


def test_list_exam_templates_excludes_rows_whose_allocation_is_empty(test_db: str) -> None:
    """SUBJECT_DRILL declares 20 questions but no sections and no syllabus units,
    and is not a TEMPLATE_UNIT_TOPICS key, so _template_allocation returns {} and
    generate_smart_mock raises "Mock allocation is empty" -> HTTP 500. The two
    descriptive papers are the same shape. Offering any of the three in the picker
    would hand the user a guaranteed error, so they are not catalogue rows."""
    _seed_templates(test_db)
    ids = {t["template_id"] for t in db.list_exam_templates()}
    assert "SUBJECT_DRILL" not in ids
    assert "IFSCA_PH2_P1_DESC" not in ids
    assert "SEBI_PH2_P1_DESC" not in ids


def test_list_exam_templates_orders_by_exam_then_phase_then_paper(test_db: str) -> None:
    """CUSTOM (exam='ANY', phase NULL) sorts first so the picker's default option
    is the current behaviour; then IFSCA before SEBI, phase 1 before phase 2,
    paper 1 before paper 2. COALESCE(phase, 0) keeps NULL out of the sort."""
    _seed_templates(test_db)
    templates = db.list_exam_templates()
    ifsca_rows = [t for t in templates if t["exam"] == "IFSCA"]
    sebi_rows = [t for t in templates if t["exam"] == "SEBI"]
    assert [t["template_id"] for t in ifsca_rows] == [
        "IFSCA_PH1_P1", "IFSCA_PH1_P2_GENERAL", "IFSCA_PH2_P2_GENERAL"
    ]
    assert [t["template_id"] for t in sebi_rows] == [
        "SEBI_PH1_P1", "SEBI_PH1_P2_GENERAL", "SEBI_PH2_P2_GENERAL"
    ]
    assert templates[0]["template_id"] == "CUSTOM"


def test_list_exam_templates_carries_the_fields_the_picker_renders(test_db: str) -> None:
    _seed_templates(test_db)
    sebi_p2 = next(
        t for t in db.list_exam_templates() if t["template_id"] == "SEBI_PH1_P2_GENERAL"
    )
    assert sebi_p2["name"] == "SEBI Phase 1 Paper 2 (General stream)"
    assert sebi_p2["phase"] == 1
    assert sebi_p2["paper"] == 2
    assert sebi_p2["total_questions"] == 50
    assert sebi_p2["time_limit_minutes"] == 40
    assert sebi_p2["cutoff_pct"] == 40.0


def test_list_exam_templates_on_an_empty_table_returns_an_empty_list(test_db: str) -> None:
    """Migration 005 creates the table but seeds nothing -- seeding only happens in
    bootstrap_from_knowledge (database.py:1473). An unseeded install must yield an
    empty catalogue, not an OperationalError."""
    _seed_templates(test_db, rows=[])
    assert db.list_exam_templates() == []


@pytest.mark.parametrize(
    "template, expected",
    [
        ({"template_id": "CUSTOM", "sections_json": "[]", "syllabus_units_json": "[]"}, True),
        ({"template_id": "IFSCA_PH1_P1",
          "sections_json": '[{"name": "Reasoning", "questions": 25}]',
          "syllabus_units_json": "[]"}, True),
        ({"template_id": "IFSCA_PH2_P2_GENERAL",
          "sections_json": "[]", "syllabus_units_json": "[]"}, True),
        ({"template_id": "SEBI_PH1_P2_GENERAL", "sections_json": "[]",
          "syllabus_units_json": '["Finance"]'}, True),
        ({"template_id": "SUBJECT_DRILL",
          "sections_json": "[]", "syllabus_units_json": "[]"}, False),
        ({"template_id": "IFSCA_PH2_P1_DESC",
          "sections_json": "[]", "syllabus_units_json": "[]"}, False),
        ({"template_id": "X", "sections_json": None, "syllabus_units_json": None}, False),
    ],
)
def test_template_is_objective_ready_predicate(
    template: dict[str, Any], expected: bool
) -> None:
    """The third case passes on the TEMPLATE_UNIT_TOPICS key alone: no sections,
    no units in the row. The last case proves the `or "[]"` guards against NULL
    columns, which migration 005 permits."""
    assert db._template_is_objective_ready(template) is expected


def test_get_exam_templates_returns_the_catalogue(test_db: str, client) -> None:
    _seed_templates(test_db)
    response = client.get("/api/exam-templates")
    assert response.status_code == 200
    body = response.json()
    assert [t["template_id"] for t in body["templates"]] == EXPECTED_ORDER


def test_get_exam_templates_declares_every_field_the_picker_renders(test_db: str, client) -> None:
    """response_model strips undeclared keys silently (HTTP 200, key absent), so a
    field missing from ExamTemplateModel shows up in the UI as undefined rather
    than as an error. This asserts the wire contract explicitly."""
    _seed_templates(test_db)
    body = client.get("/api/exam-templates").json()
    ifsca_p1 = next(t for t in body["templates"] if t["template_id"] == "IFSCA_PH1_P1")
    for field in (
        "template_id", "exam", "name", "phase", "paper",
        "total_questions", "time_limit_minutes", "cutoff_pct",
    ):
        assert field in ifsca_p1, f"{field} was stripped by response_model"
    assert ifsca_p1["exam"] == "IFSCA"
    assert ifsca_p1["phase"] == 1
    assert ifsca_p1["paper"] == 1
    assert ifsca_p1["total_questions"] == 100
    assert ifsca_p1["time_limit_minutes"] == 60
    assert ifsca_p1["cutoff_pct"] == 30.0


def test_get_exam_templates_survives_null_phase_and_paper(test_db: str, client) -> None:
    """CUSTOM has phase=NULL, paper=NULL and cutoff_pct=NULL. A non-nullable
    declaration on any of those makes FastAPI raise a 500 during response
    validation, so this is the regression test for the nullable annotations."""
    _seed_templates(test_db)
    body = client.get("/api/exam-templates").json()
    custom = next(t for t in body["templates"] if t["template_id"] == "CUSTOM")
    assert custom["phase"] is None
    assert custom["paper"] is None
    assert custom["cutoff_pct"] is None
    assert custom["total_questions"] == 50


def test_get_exam_templates_does_not_leak_the_json_blobs(test_db: str, client) -> None:
    """sections_json / syllabus_units_json / descriptive_components_json are raw
    JSON strings meant for _template_allocation, not for the browser."""
    _seed_templates(test_db)
    body = client.get("/api/exam-templates").json()
    for template in body["templates"]:
        assert "sections_json" not in template
        assert "syllabus_units_json" not in template
        assert "descriptive_components_json" not in template


def test_get_exam_templates_on_an_unseeded_install_returns_an_empty_list(test_db: str, client) -> None:
    _seed_templates(test_db, rows=[])
    response = client.get("/api/exam-templates")
    assert response.status_code == 200
    assert response.json() == {"templates": []}


def test_exam_templates_route_does_not_shadow_or_get_shadowed(test_db: str, client) -> None:
    """/api/exam-templates must stay distinct from /api/exams/start and from
    /api/documents. FastAPI matches in declaration order, so a later
    /api/{something} catch-all would swallow it -- this pins the observable
    behaviour rather than the registration order."""
    _seed_templates(test_db)
    assert client.get("/api/exam-templates").status_code == 200
    assert client.get("/api/documents").status_code == 200
    assert client.get("/api/exams/start").status_code in (404, 405)


# --- /api/exams/start: the chosen template must reach the generator ----------


def _install_generate_spy(
    monkeypatch, result: dict[str, Any]
) -> list[dict[str, Any]]:
    """Swap db.generate_smart_mock for a recorder and return the call log.

    main.py does `import database as db` and calls `db.generate_smart_mock(...)`,
    so patching the attribute on the database module is enough. monkeypatch undoes
    it at teardown, so nothing else in the 186-test suite sees the fake.
    """
    calls: list[dict[str, Any]] = []

    def spy(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return result

    monkeypatch.setattr(db, "generate_smart_mock", spy)
    return calls


def _answer_key_question(sample_question: dict[str, Any]) -> dict[str, Any]:
    """conftest's sample_question plus every field exam_start must strip.

    sample_question already carries correct_option, explanation and
    source_chunk_id; the seven added here complete the ten-field answer key so
    the strip test asserts on all of them rather than on a convenient subset.
    Every added key is a declared QuestionModel field, so model_validate accepts
    it and _coerce_question does not blow up before the strip loop runs.
    """
    question = dict(sample_question)
    question.update(
        {
            "source": "IFSCA Act 2019, Section 10",
            "source_document_id": "doc_001",
            "page_start": 5,
            "page_end": 6,
            "citation_note": "As amended by the 2023 notification.",
            "tested_fact": "fact_001",
            "trap_logic": "Confuses Section 10 with Section 15.",
        }
    )
    return question


def _fake_mock_result(
    question: dict[str, Any], time_limit_minutes: int | None = None
) -> dict[str, Any]:
    """Shaped like generate_smart_mock's return (database.py:4850-4870).

    `time_limit_minutes` is present only when a template was used, which mirrors
    the real `if template:` guard. Omitting it is therefore how the CUSTOM
    fallback gets exercised -- not by passing a sentinel value.
    """
    result: dict[str, Any] = {
        "mock_id": "SM_20260903_120000_abcd",
        "template_id": "CUSTOM",
        "allocation": {"PH2_IFSCA_ACT": 1},
        "allocation_summary": {
            "weak_topics_focused": 1,
            "medium_topics": 0,
            "strong_topics": 0,
            "weak_pct": "100.0%",
            "medium_pct": "0.0%",
            "strong_pct": "0.0%",
        },
        "weakness_analysis": [],
        "questions": [question],
    }
    if time_limit_minutes is not None:
        result["time_limit_minutes"] = time_limit_minutes
    return result


def test_exams_start_forwards_the_chosen_template_id(
    test_db: str, client, monkeypatch, sample_question
) -> None:
    """The regression test for the silent-drop defect: exam.js posts fields the
    model does not declare, they are ignored, and generate_smart_mock is called
    with its own defaults. Asserting on the spy's kwargs is the only way to see
    the value actually arrive."""
    _seed_templates(test_db)
    calls = _install_generate_spy(monkeypatch, _fake_mock_result(sample_question))
    response = client.post("/api/exams/start", json={"template": "IFSCA_PH2_P2_GENERAL"})
    assert response.status_code == 200
    assert calls[0]["template_id"] == "IFSCA_PH2_P2_GENERAL"


def test_exams_start_defaults_to_custom_when_no_template_is_chosen(
    test_db: str, client, monkeypatch, sample_question
) -> None:
    """Both an empty JSON body and no body at all must land on CUSTOM, which is
    what the endpoint does today. Verified on the installed FastAPI: an
    `X | None = None` body parameter yields None for a bodiless POST rather than
    a 422, and `request = request or SmartMockRequestModel()` supplies defaults."""
    _seed_templates(test_db)
    calls = _install_generate_spy(monkeypatch, _fake_mock_result(sample_question))
    assert client.post("/api/exams/start", json={}).status_code == 200
    assert calls[0]["template_id"] == "CUSTOM"
    assert client.post("/api/exams/start").status_code == 200
    assert calls[1]["template_id"] == "CUSTOM"


def test_exams_start_still_forwards_count_and_mode(
    test_db: str, client, monkeypatch, sample_question
) -> None:
    """Collateral-damage guard, not a red-green test: this passes before and after
    the fix. total_questions and mode were already forwarded correctly; adding
    template_id must not disturb them."""
    _seed_templates(test_db)
    calls = _install_generate_spy(monkeypatch, _fake_mock_result(sample_question))
    response = client.post(
        "/api/exams/start",
        json={"total_questions": 40, "mode": "amendment-heavy", "template": "SEBI_PH1_P1"},
    )
    assert response.status_code == 200
    assert calls[0]["total_questions"] == 40
    assert calls[0]["mode"] == "amendment-heavy"
    assert calls[0]["use_gemini"] is True


def test_exams_start_time_limit_comes_from_the_chosen_paper(
    test_db: str, client, monkeypatch, sample_question
) -> None:
    """SEBI Phase 1 Paper 2 is a 40-minute paper. The hardcoded 3600 gave every
    exam an hour, so the clock lied for every paper except one."""
    _seed_templates(test_db)
    _install_generate_spy(
        monkeypatch, _fake_mock_result(sample_question, time_limit_minutes=40)
    )
    response = client.post("/api/exams/start", json={"template": "SEBI_PH1_P2_GENERAL"})
    assert response.status_code == 200
    assert response.json()["time_limit_seconds"] == 2400


def test_exams_start_time_limit_falls_back_to_an_hour_for_custom(
    test_db: str, client, monkeypatch, sample_question
) -> None:
    """CUSTOM never resolves a template row inside generate_smart_mock, so the
    result carries no time_limit_minutes and the previous 3600 must survive
    unchanged. This is the no-behaviour-change half of the fix."""
    _seed_templates(test_db)
    _install_generate_spy(monkeypatch, _fake_mock_result(sample_question))
    response = client.post("/api/exams/start", json={"template": "CUSTOM"})
    assert response.status_code == 200
    assert response.json()["time_limit_seconds"] == 3600


def test_exams_start_still_strips_every_answer_key_field(
    test_db: str, client, monkeypatch, sample_question
) -> None:
    """The response is deliberately blind: an exam that ships its own answer key
    can be passed by reading the payload. Ten fields are popped and two Phase 3
    fields are added. Editing the return dict for the time limit must not disturb
    either half."""
    _seed_templates(test_db)
    _install_generate_spy(
        monkeypatch, _fake_mock_result(_answer_key_question(sample_question))
    )
    body = client.post("/api/exams/start", json={"template": "IFSCA_PH1_P1"}).json()
    question = body["questions"][0]
    for answer_key_field in (
        "correct_option",
        "explanation",
        "source",
        "source_document_id",
        "source_chunk_id",
        "page_start",
        "page_end",
        "citation_note",
        "tested_fact",
        "trap_logic",
    ):
        assert answer_key_field not in question, f"{answer_key_field} leaked"
    assert question["expected_time_sec"] == 180
    assert question["negative_marking"] == -1
    assert question["question_text"] == sample_question["question_text"]
    assert body["question_count"] == 1
    assert body["exam_id"] == "EXAM_" + body["mock_id"]


@pytest.mark.parametrize(
    "payload",
    [
        {"total_questions": 200},
        {"total_questions": 4},
        {"mode": "targeting_weighted"},
    ],
)
def test_exams_start_rejects_values_the_model_does_not_accept(
    test_db: str, client, monkeypatch, sample_question, payload: dict[str, Any]
) -> None:
    """Pins the two constraints that forced spec corrections 1 and 2, so the
    frontend cannot drift back into them. Verified on the installed FastAPI:
    total_questions is ge=5 le=100 (200 and 4 both 422, 100 is accepted) and mode
    is a four-value Literal that does not include "targeting_weighted".

    The index.html number input still says max="200" at this point in the plan;
    Task 11 corrects it to max="100". If that task is skipped, a user who drags
    the slider to the top gets a 422 and the exam never starts.
    """
    _seed_templates(test_db)
    _install_generate_spy(monkeypatch, _fake_mock_result(sample_question))
    assert client.post("/api/exams/start", json=payload).status_code == 422
