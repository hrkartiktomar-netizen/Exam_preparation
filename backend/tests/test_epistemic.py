"""Epistemic-layer tests: the ground-truth instrument and its calibration.

Locks in:
- Phase-1 PYQ questions are labeled with phase-level pseudo topics, never
  forced into Phase-2 domain topics.
- Phase-2 PYQ questions get their best domain match; unmatched questions
  stay UNCLASSIFIED rather than being misattributed.
- The calibration endpoint compares the internal instrument (generated
  mocks) against the ground-truth instrument (real papers) per topic.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

import database as db
from main import app


def test_label_pyq_phase1_quant_not_phase2(test_db: str) -> None:
    label = db.label_pyq_question_topic(
        "55.55% of 305.98 + 6.08 x 11.98 = ? What is the approximate value?",
        paper_phase=1,
    )
    assert label == "PHASE1_QUANT"


def test_label_pyq_phase1_english(test_db: str) -> None:
    label = db.label_pyq_question_topic(
        "Choose the word that is a SYNONYM of 'ABDICATE'.",
        paper_phase=1,
    )
    assert label == "PHASE1_ENGLISH"


def test_label_pyq_phase2_domain_match(test_db: str) -> None:
    label = db.label_pyq_question_topic(
        "Fund management entities in the IFSC must comply with which regulatory requirement?",
        paper_phase=2,
    )
    # "fund management" is a PH2_FM_REGS keyword; no other topic matches.
    assert label == "PH2_FM_REGS", label


def test_label_pyq_unmatched_stays_unclassified(test_db: str) -> None:
    label = db.label_pyq_question_topic(
        "Zzz quux florb gleep.", paper_phase=2,
    )
    assert label == "UNCLASSIFIED"


def test_calibration_endpoint_compares_instruments(test_db: str) -> None:
    # The test fixture builds only the base SCHEMA; migration 004 (PYQ tables)
    # is required by the calibration query. Force a full idempotent init.
    db.init_db(force=True)
    conn = sqlite3.connect(test_db)
    try:
        # Internal instrument: 8 mock attempts at 75% on a topic
        for i in range(8):
            conn.execute(
                """INSERT INTO question_attempts
                   (mock_id, question_id, topic, question_text, is_correct, attempt_date, source, difficulty)
                   VALUES (?, ?, ?, ?, ?, '2026-08-01', 'SMART_MOCK', 'medium')""",
                (f"cal_m{i}", f"cal_q{i}", "PH2_TAX", f"mock q {i}", 1 if i % 4 else 0),
            )
        # Ground-truth instrument: 8 PYQ attempts at 25% on the same topic
        for i in range(8):
            conn.execute(
                """INSERT OR REPLACE INTO pyq_question_attempts
                   (attempt_id, pyq_id, question_id, question_number, topic_id,
                    selected_answer, official_answer, is_correct)
                   VALUES (?, ?, ?, ?, ?, 'A', 'B', ?)""",
                (f"pyq_att_{i}", "PYQ_X", f"PYQ_X_Q{i}", i + 1, "PH2_TAX", 1 if i % 4 == 0 else 0),
            )
        conn.commit()
    finally:
        conn.close()

    client = TestClient(app)
    response = client.get("/api/analytics/calibration")
    assert response.status_code == 200
    data = response.json()
    topics = {row["topic_id"]: row for row in data["topics"]}
    assert "PH2_TAX" in topics
    row = topics["PH2_TAX"]
    assert row["mock_accuracy"] == 75.0
    assert row["pyq_accuracy"] == 25.0
    assert row["gap_points"] == 50.0
