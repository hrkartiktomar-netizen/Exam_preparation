"""Plan v6 Phase 6 verification (V6): intelligence-layer behaviors.

Covers 6.1 coverage-gap weakness, 6.2 readiness aggregate + gating, 6.4 SM-2
unification + post-submit SRS auto-scheduling, 6.5 law revision progress and
slice drills, 6.6 pack amendment seeding, 6.7 targeting cache, and 6.8
analytics auto-save / IRT-lite / history search extension.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import database as db
import law_revision_engine
import readiness_engine
from main import app, _cached_targeting_snapshot, _TARGETING_CACHE

from fastapi.testclient import TestClient


def _seed_mock(mock_id: str, questions: list[dict]) -> None:
    conn = db.get_connection()
    try:
        conn.execute(
            "INSERT INTO mock_sessions (mock_id, mock_type, generated_at, started_at, total_questions, status) VALUES (?, ?, ?, ?, ?, ?)",
            (mock_id, "smart", datetime.now().isoformat(), datetime.now().isoformat(), len(questions), "active"),
        )
        conn.commit()
    finally:
        conn.close()
    for index, question in enumerate(questions, start=1):
        db.save_question(
            {
                "question_id": question["question_id"],
                "topic": question["topic_id"],
                "question_text": question["question_text"],
                "options": [
                    {"label": "A", "text": question.get("option_a", "Alpha")},
                    {"label": "B", "text": question.get("option_b", "Beta")},
                    {"label": "C", "text": question.get("option_c", "Gamma")},
                    {"label": "D", "text": question.get("option_d", "Delta")},
                ],
                "correct_option": question["correct_answer"],
                "explanation": "explanation",
                "difficulty": "medium",
                "question_type": "smart_mock",
                "source_policy": "exam_material",
            },
            created_by="test",
        )
        conn = db.get_connection()
        try:
            conn.execute(
                "INSERT INTO mock_questions (mock_id, question_id, question_number) VALUES (?, ?, ?)",
                (mock_id, question["question_id"], index),
            )
            conn.commit()
        finally:
            conn.close()


def test_submit_auto_saves_analytics_and_schedules_weak_topics(test_db):
    questions = []
    for index in range(6):
        questions.append(
            {
                "question_id": f"Q_WEAK_{index}",
                "topic_id": "PH2_FM_REGS",
                "question_text": f"Weak topic question {index}?",
                "correct_answer": "A",
            }
        )
    for index in range(4):
        questions.append(
            {
                "question_id": f"Q_STRONG_{index}",
                "topic_id": "PH2_BANKING",
                "question_text": f"Strong topic question {index}?",
                "correct_answer": "B",
            }
        )
    _seed_mock("MOCK_V6_ANALYTICS", questions)

    answers = []
    # Weak topic: 1/6 correct (16.7% -> hard rating + SRS interval 1)
    for index in range(6):
        answers.append({"question_id": f"Q_WEAK_{index}", "selected_answer": "A" if index == 0 else "C", "time_spent_seconds": 90})
    # Strong topic: 4/4 correct (100% -> easy rating)
    for index in range(4):
        answers.append({"question_id": f"Q_STRONG_{index}", "selected_answer": "B", "time_spent_seconds": 60})

    result = db.submit_mock("MOCK_V6_ANALYTICS", answers)
    assert result["total_correct"] == 5

    analytics = db.get_exam_analytics("MOCK_V6_ANALYTICS")
    by_topic = {row["topic_id"]: row for row in analytics}
    assert set(by_topic) == {"PH2_FM_REGS", "PH2_BANKING"}, "analytics must auto-save per topic"
    assert by_topic["PH2_FM_REGS"]["difficulty_rating"] == "hard"
    assert by_topic["PH2_BANKING"]["difficulty_rating"] == "easy"
    assert by_topic["PH2_FM_REGS"]["time_spent_seconds"] == 540
    assert by_topic["PH2_BANKING"]["comparison_to_avg"] > 0

    conn = db.get_connection()
    try:
        scheduled = {
            row["topic_id"]: row["interval_days"]
            for row in conn.execute(
                "SELECT topic_id, interval_days FROM review_items WHERE item_type = 'topic'"
            ).fetchall()
        }
    finally:
        conn.close()
    assert "PH2_FM_REGS" in scheduled, "weak topic (<40%) must be auto-scheduled for SRS"
    assert scheduled["PH2_FM_REGS"] == 1, "<40% accuracy maps to a 1-day review interval"


def test_sm2_unified_topic_review_progression(test_db):
    review_id = db.schedule_topic_review("PH2_AML_KYC", interval_days=1)
    db.mark_topic_reviewed("PH2_AML_KYC", success=True)
    conn = db.get_connection()
    try:
        row = conn.execute("SELECT ease, interval_days FROM review_items WHERE review_id = ?", (review_id,)).fetchone()
    finally:
        conn.close()
    # SM-2: ease 2.5 -> 2.6, interval round(1 * 2.6) = 3 (not the old fixed jump to 3 via ease 2.8)
    assert abs(row["ease"] - 2.6) < 1e-9
    assert row["interval_days"] == 3
    db.mark_topic_reviewed("PH2_AML_KYC", success=True)
    conn = db.get_connection()
    try:
        row = conn.execute("SELECT ease, interval_days FROM review_items WHERE review_id = ?", (review_id,)).fetchone()
    finally:
        conn.close()
    assert abs(row["ease"] - 2.7) < 1e-9
    assert row["interval_days"] == 8  # round(3 * 2.7)


def test_pack_amendment_events_merge_with_constants(test_db):
    events = db._pack_amendment_events()
    assert len(events) == 13
    assert all(event["verify_status"] == "PACK_SEEDED" for event in events)
    assert all(event["topic"].startswith(("PH2_", "SUBJ_")) for event in events)

    db.record_amendment(events[0])
    db.record_amendment(
        {
            "amendment_id": "AMN_FM_2025_KMP",
            "topic": "PH2_FM_REGS",
            "rule_name": "Fund Management Regulations 2025 - KMP eligibility",
            "effective_date": "2025-02-19",
            "old_value": None,
            "new_value": "KMP eligibility update",
            "source_url": "seed",
            "verify_status": "SEEDED",
            "priority": "CRITICAL",
            "questions_needed": 3,
        }
    )
    conn = db.get_connection()
    try:
        pack_rows = conn.execute("SELECT COUNT(*) AS c FROM amendments WHERE verify_status = 'PACK_SEEDED'").fetchone()
        event_row = conn.execute("SELECT mastery_status FROM amendment_events WHERE amendment_id = 'AMN_FM_2025_KMP'").fetchone()
        pack_event = conn.execute("SELECT COUNT(*) AS c FROM amendment_events WHERE amendment_id IN ({})".format(
            ",".join("?" for _ in events)
        ), [event["amendment_id"] for event in events]).fetchone()
    finally:
        conn.close()
    assert pack_rows["c"] == 1
    assert pack_event["c"] >= 1, "pack-seeded amendment must also create an amendment_event"
    assert event_row["mastery_status"] == "NEW"


def test_amendment_mastered_toggle_persists(test_db):
    db.record_amendment(
        {
            "amendment_id": "AMN_TEST_MASTER",
            "topic": "PH2_FM_REGS",
            "rule_name": "Mastery toggle test",
            "effective_date": "2026-01-01",
            "old_value": None,
            "new_value": "value",
            "source_url": "seed",
            "verify_status": "SEEDED",
            "priority": "HIGH",
            "questions_needed": 3,
        }
    )
    client = TestClient(app)
    response = client.post("/api/amendments/AMN_TEST_MASTER/mastered")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "mastered" and body["events_updated"] == 1

    conn = db.get_connection()
    try:
        event = conn.execute("SELECT mastery_status FROM amendment_events WHERE amendment_id = 'AMN_TEST_MASTER'").fetchone()
        amendment = conn.execute("SELECT drilled FROM amendments WHERE amendment_id = 'AMN_TEST_MASTER'").fetchone()
    finally:
        conn.close()
    assert event["mastery_status"] == "MASTERED"
    assert amendment["drilled"] == 1

    missing = client.post("/api/amendments/AMN_DOES_NOT_EXIST/mastered")
    assert missing.status_code == 404


def test_history_search_extended_to_pyq_and_descriptive(test_db):
    db.bootstrap_from_knowledge()
    client = TestClient(app)
    response = client.get("/api/history/search", params={"query": "IFSCA", "limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert "pyqs" in body and "descriptive" in body
    assert len(body["pyqs"]) > 0, "compiled bank must be searchable"
    assert body["total"] >= len(body["pyqs"]) + len(body["descriptive"])

    pyq = body["pyqs"][0]
    assert pyq["exam"] in {"IFSCA", "SEBI"}
    assert pyq["question_text"]


def test_irt_lite_observed_difficulty_overlays_reuse(test_db):
    question = {
        "question_id": "Q_IRT_1",
        "topic": "PH2_PAYMENT",
        "question_text": "Which payment service requires escrow?",
        "options": [
            {"label": "A", "text": "one"}, {"label": "B", "text": "two"},
            {"label": "C", "text": "three"}, {"label": "D", "text": "four"},
        ],
        "correct_option": "A",
        "explanation": "escrow",
        "difficulty": "easy",
        "source": "test",
        "created_by": "gemini",
        "question_type": "smart_mock",
        "verification_status": "VERIFIED",
        "source_policy": "exam_material",
    }
    db.save_question(question, created_by="gemini")

    conn = db.get_connection()
    try:
        now = datetime.now()
        for index, correct in enumerate([0, 0, 1, 0]):  # p-value 0.25 -> hard
            conn.execute(
                """
                INSERT INTO question_attempts
                (mock_id, question_id, topic, question_text, correct_option, your_option, is_correct, time_spent_seconds, attempt_date, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("MOCK_IRT", "Q_IRT_1", "PH2_PAYMENT", "text", "A", "B" if not correct else "A",
                 correct, 40 + index * 10, now.date().isoformat(), "SMART_MOCK"),
            )
        conn.commit()
    finally:
        conn.close()

    stats = db.irt_lite_question_stats()
    assert "Q_IRT_1" in stats
    assert stats["Q_IRT_1"]["p_value"] == 0.25
    assert stats["Q_IRT_1"]["observed_difficulty"] == "hard"
    assert stats["Q_IRT_1"]["median_time_seconds"] is not None

    reused = db.existing_questions_for_topic("PH2_PAYMENT", limit=5)
    target = [q for q in reused if q["question_id"] == "Q_IRT_1"]
    assert target, "saved question must be reusable"
    assert target[0]["difficulty"] == "hard", "empirical difficulty must drive reuse"
    assert target[0]["labeled_difficulty"] == "easy"


def test_law_revision_progress_and_drills(test_db):
    db.bootstrap_from_knowledge()
    first = db.daily_ifsca_act_revision(lines_per_day=80)
    assert first["day_index"] == 0
    assert first["daily_text"], "act slice must come from the compiled document_fulltext"

    result = law_revision_engine.complete_law_revision_day(lines_per_day=80)
    assert result["status"] == "completed" and result["completed_sessions"] == 1

    second = db.daily_ifsca_act_revision(lines_per_day=80)
    assert second["day_index"] == 1, "day index must be completion-driven"

    plan = law_revision_engine.daily_law_revision(force_local=True)
    assert plan.act_mcq is not None, "local slice drill must produce a grounded act_mcq"
    assert plan.act_mcq["correct_option"] in plan.act_mcq["options"]
    assert plan.micro_descriptive["word_limit"] == 120
    assert plan.completed_sessions == 1


def test_readiness_aggregate_gating_mapping(test_db):
    conn = db.get_connection()
    try:
        base = datetime.now() - timedelta(days=2)
        for offset, score in ((0, 55.0), (1, 70.0)):
            when = (base + timedelta(days=offset)).isoformat()
            conn.execute(
                "INSERT INTO mock_sessions (mock_id, generated_at, submitted_at, score, accuracy, status) VALUES (?, ?, ?, ?, ?, ?)",
                (f"MOCK_READ_{offset}", when, when, score, score, "submitted"),
            )
        conn.commit()
    finally:
        conn.close()

    # Objective only: paper2 projection (>= 70) clears the 40 gate; aggregate = paper2.
    estimate = readiness_engine.calculate_readiness_estimate("default", days_to_exam=1)
    assert estimate.readiness_percentage > 25, "no gate failure expected with paper2 above 40"

    # Paper-1 below its 30 cut-off must gate readiness to <=25 with LOW confidence.
    db.record_descriptive_score(
        exam="IFSCA", year=2023,
        components=[{"component": "essay", "score": 6.0, "max_marks": 30.0}],
        total_score=6.0, total_max_marks=30.0, cutoff_pct=30.0, cleared_cutoff=False,
    )
    gated = readiness_engine.calculate_readiness_estimate("default", days_to_exam=1)
    assert gated.readiness_percentage <= 25
    assert gated.confidence == "LOW"

    # A strong descriptive sitting restores the aggregate (paper1 90, paper2 ~71).
    db.record_descriptive_score(
        exam="IFSCA", year=2023,
        components=[{"component": "essay", "score": 27.0, "max_marks": 30.0}],
        total_score=90.0, total_max_marks=100.0, cutoff_pct=30.0, cleared_cutoff=True,
    )
    restored = readiness_engine.calculate_readiness_estimate("default", days_to_exam=1)
    assert restored.readiness_percentage > gated.readiness_percentage
    assert restored.confidence in {"MEDIUM", "HIGH"}


def test_targeting_snapshot_cache_reuses_within_ttl(test_db):
    _TARGETING_CACHE["data"] = None
    _TARGETING_CACHE["ts"] = 0.0
    first = _cached_targeting_snapshot()
    ts_first = _TARGETING_CACHE["ts"]
    assert first and ts_first > 0

    _cached_targeting_snapshot()
    assert _TARGETING_CACHE["ts"] == ts_first, "second call within TTL must not recompute"


def test_weakness_coverage_gap_term_present(test_db):
    db.bootstrap_from_knowledge()
    conn = db.get_connection()
    try:
        gap_thin = db._coverage_gap_for_topic("SUBJ_QUANT", conn)
        gap_facts = db._coverage_gap_for_topic("PH2_FM_REGS", conn)
    finally:
        conn.close()
    assert 0.0 <= gap_thin <= 1.0
    assert gap_facts < gap_thin, "topics backed by pack facts must have a smaller coverage gap"

    stats = {item["topic"]: item for item in db.get_topic_stats()}
    assert all(0.0 <= item["weakness_score"] <= 1.0 for item in stats.values())


def test_dashboard_endpoint_timing_cached(test_db):
    client = TestClient(app)
    client.get("/api/dashboard", params={"include_ai": False})  # warm the cache
    start = time.perf_counter()
    response = client.get("/api/dashboard", params={"include_ai": False})
    elapsed = time.perf_counter() - start
    assert response.status_code == 200
    assert elapsed < 0.5, f"cached dashboard must serve in <0.5s, took {elapsed:.3f}s"
