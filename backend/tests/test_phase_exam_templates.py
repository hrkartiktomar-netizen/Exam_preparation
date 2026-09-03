"""Tests for the phase/paper exam-template catalogue behind GET /api/exam-templates.

The conftest `test_db` fixture runs SCHEMA plus migrations 002 only, and
TestClient is built without a context manager so `lifespan` (and therefore
db.init_db) never runs. exam_templates is created by migration 005, so every
test here creates and seeds the table itself via db._run_migration_005 -- the
same house pattern conftest uses for migration 002.
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
