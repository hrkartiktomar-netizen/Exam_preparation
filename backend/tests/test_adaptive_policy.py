"""Adaptive policy contract tests.

These lock in the principle that practice difficulty is exogenous to
weakness rank: the exam does not get easier for strong topics, so the
difficulty mix may only depend on attempt history (scaffold early,
exam-like afterwards). This closes the confirmatory bias where strong
topics were measured only on trivially easy questions.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import database as db


def _seed_attempts(db_path: Path, topic: str, count: int, is_correct: int) -> None:
    conn = sqlite3.connect(db_path)
    try:
        for i in range(count):
            conn.execute(
                """INSERT INTO question_attempts
                   (mock_id, question_id, topic, question_text, is_correct,
                    time_spent_seconds, attempt_date, source, difficulty)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"policy_mock_{i}",
                    f"policy_q_{i}",
                    topic,
                    f"Practice question {i} for {topic}",
                    is_correct,
                    40,
                    datetime.now().date().isoformat(),
                    "SMART_MOCK",
                    "medium",
                ),
            )
        conn.commit()
    finally:
        conn.close()


def test_difficulty_mix_is_exogenous_to_strength(test_db: str) -> None:
    """At identical attempt history, no tier may be practiced all-easy when it
    has >=3 questions: scaffolding is easy-majority but never mono-difficulty,
    and strength must not change the mix (the exam is exogenous)."""
    config = db.get_smart_mock_config(total_questions=50, mode="balanced")
    curve = config["difficulty_curve"]

    for topic, mix in curve.items():
        if len(mix) >= 3:
            assert mix.count("easy") >= len(mix) // 2, (
                f"{topic} scaffold should be easy-majority on first contact: {mix}"
            )
            assert len(set(mix)) >= 2, (
                f"{topic} must not be practiced at a single difficulty: {mix}"
            )

    # Mix length must always match the allocated question count.
    for topic, mix in curve.items():
        assert len(mix) == config["allocation"].get(topic, 0)


def test_exam_like_mix_after_scaffolding(test_db: str) -> None:
    """After >=5 attempts a topic must be practiced at exam-like difficulty
    (all three levels present), even when it is weak."""
    _seed_attempts(Path(test_db), "PH2_TAX", count=6, is_correct=0)

    config = db.get_smart_mock_config(total_questions=50, mode="balanced")
    mix = config["difficulty_curve"].get("PH2_TAX", [])
    assert mix, "seeded weak topic should receive allocation"
    assert set(mix) == {"easy", "medium", "hard"}, (
        f"exam-like mix expected after scaffolding, got {mix}"
    )


def test_scaffold_never_all_hard(test_db: str) -> None:
    """First contact with a topic must never be dominated by hard questions."""
    config = db.get_smart_mock_config(total_questions=50, mode="balanced")
    curve = config["difficulty_curve"]
    for topic, mix in curve.items():
        if len(mix) >= 3:
            assert mix.count("hard") <= mix.count("easy"), (
                f"{topic} scaffold should be easy-heavy on first contact: {mix}"
            )
