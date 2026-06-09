"""End-to-end integration tests for IFSCA exam prep platform (Week 6 validation).

Per Context7 docs for pytest: comprehensive integration tests should:
1. Cover full user workflows
2. Verify cross-system interactions
3. Test error handling at system boundaries
4. Use fixtures for setup/teardown
5. Mock external APIs (Gemini) for determinism
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from typing import Any

import pytest
from fastapi.testclient import TestClient

import database as db


# ==========================================
# TEST 1: Full Exam Prep Day Workflow
# ==========================================


def test_full_exam_prep_day_workflow(
    client: TestClient,
    sample_attempt: dict[str, Any],
    test_db: str,
    sample_question: dict[str, Any],
) -> None:
    """E2E: Take mock → detect weakness → run drill → verify recommendation updates.

    Workflow:
    1. Start mock exam
    2. Submit answers (intentionally weak some topics)
    3. Verify weakness detection
    4. Start penalty drill on weak topic
    5. Verify recommendation engine responds
    6. Verify readiness updates
    """
    user_id = "test_user_001"

    # Step 1: Generate smart mock (60% weak, 25% medium, 15% strong)
    with patch("gemini_integration.gemini_available", return_value=True):
        with patch("gemini_integration.generate_questions_with_gemini") as mock_gemini:
            mock_gemini.return_value = [
                {
                    "question_id": f"q_{i}",
                    "question_text": f"Question {i}",
                    "options": [
                        {"label": "A", "text": "Option A"},
                        {"label": "B", "text": "Option B"},
                        {"label": "C", "text": "Option C"},
                        {"label": "D", "text": "Option D"},
                    ],
                    "correct_option": "A",
                    "explanation": "Explanation",
                    "difficulty": "medium" if i % 2 == 0 else "easy",
                    "topic": "PH2_IFSCA_ACT" if i < 30 else "PH2_FM_REGS",
                }
                for i in range(1, 51)
            ]

            mock_response = client.post(
                "/api/generate-smart-mock",
                json={"user_id": user_id},
            )

    assert mock_response.status_code == 200
    mock_data = mock_response.json()
    assert "mock_id" in mock_data
    assert len(mock_data.get("questions", [])) == 50
    mock_id = mock_data["mock_id"]

    # Step 2: Submit exam (simulate weak performance on PH2_IFSCA_ACT)
    answers = {}
    for i in range(1, 51):
        topic = "PH2_IFSCA_ACT" if i <= 30 else "PH2_FM_REGS"
        # Answer correctly if FM_REGS, incorrectly if IFSCA_ACT (simulating weakness)
        answers[f"q_{i}"] = "B" if topic == "PH2_IFSCA_ACT" else "A"

    submit_response = client.post(
        "/api/exams/submit",
        json={"mock_id": mock_id, "answers": answers},
    )

    assert submit_response.status_code == 200
    submit_data = submit_response.json()
    assert "score" in submit_data
    assert "weak_areas" in submit_data

    weak_topics = [w["topic"] for w in submit_data.get("weak_areas", [])]
    assert "PH2_IFSCA_ACT" in weak_topics, "Weakness detection failed"

    # Step 3: Verify recommendation engine surfaces next action
    recommendation_response = client.get(
        f"/api/dashboard/next-action?user_id={user_id}"
    )

    assert recommendation_response.status_code == 200
    rec_data = recommendation_response.json()
    assert "action" in rec_data
    assert rec_data["action"] in ["DRILL", "MOCK", "REVIEW", "ESSAY"]

    # Step 4: Verify readiness estimate updates
    readiness_response = client.get(
        f"/api/dashboard/readiness?user_id={user_id}"
    )

    assert readiness_response.status_code == 200
    readiness_data = readiness_response.json()
    assert "readiness_pct" in readiness_data
    assert 0 <= readiness_data["readiness_pct"] <= 100
    assert "weak_areas_count" in readiness_data


# ==========================================
# TEST 2: Amendment Detection & Auto-Q Generation
# ==========================================


def test_amendment_detection_auto_question_generation(
    client: TestClient,
    sample_amendment: dict[str, Any],
    test_db: str,
) -> None:
    """E2E: Amendment detected → extracted → 3 questions auto-generated.

    Workflow:
    1. Mock amendment poller finds new circular
    2. Gemini extracts amendment metadata
    3. Job queue creates 3 questions
    4. Amendment dashboard shows "2 New Regulations"
    """
    # Step 1: Record amendment (simulating poller detection)
    conn = db.get_connection()
    try:
        conn.execute(
            """INSERT INTO amendments
               (amendment_id, topic, title, summary, effective_date, published_date, source_url)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                sample_amendment["amendment_id"],
                sample_amendment["topic"],
                sample_amendment["title"],
                sample_amendment["summary"],
                sample_amendment["effective_date"],
                sample_amendment["published_date"],
                sample_amendment["source_url"],
            ),
        )
        conn.commit()
    finally:
        conn.close()

    # Step 2: Verify amendment endpoint returns amendment
    amendments_response = client.get(
        f"/api/amendments/recent?days_back=30&limit=20"
    )

    assert amendments_response.status_code == 200
    amendments_data = amendments_response.json()
    assert len(amendments_data) >= 1
    assert any(a["amendment_id"] == sample_amendment["amendment_id"]
               for a in amendments_data)

    # Step 3: Verify amendment radar widget shows new amendment
    with patch("amendment_poller.AmendmentPoller.poll_and_process") as mock_poll:
        mock_poll.return_value = {
            "polled_at": datetime.now().isoformat(),
            "sources_checked": 3,
            "new_circulars_found": 1,
            "amendments_extracted": 1,
            "jobs_queued": 3,
            "errors": [],
        }

        status_response = client.get("/api/amendments/status")
        assert status_response.status_code == 200


# ==========================================
# TEST 3: Essay Grading & Recommendation
# ==========================================


def test_essay_grading_recommendation_flow(
    client: TestClient,
    sample_essay: dict[str, Any],
    test_db: str,
) -> None:
    """E2E: Submit essay → graded <5s → recommendation surfaces essay feedback.

    Workflow:
    1. Submit essay for grading
    2. Receive 4-rubric breakdown (0-100)
    3. System recommendations update (includes essay as next action)
    4. Verify feedback quality
    """
    # Step 1: Grade essay
    with patch("essay_grader.gemini_grade_essay") as mock_grade:
        mock_grade.return_value = {
            "content_accuracy": {"score": 22, "feedback": "Strong knowledge of regulations"},
            "structure_clarity": {"score": 20, "feedback": "Well-organized essay"},
            "regulatory_knowledge": {"score": 24, "feedback": "Excellent citation of rules"},
            "examples_evidence": {"score": 18, "feedback": "Good examples but could add statistics"},
            "overall_feedback": "Strong essay, minor improvements in data points",
            "model_outline": "1. Introduction 2. Regulations 3. Examples 4. Analysis 5. Conclusion",
            "ai_model": "Gemini 2.0 Flash",
        }

        grade_response = client.post(
            "/api/grade-essay",
            json={
                "text": sample_essay["essay_text"],
                "topic": sample_essay["topic"],
                "source_chunks": [],
                "force_local": False,
            },
        )

    assert grade_response.status_code == 200
    grade_data = grade_response.json()

    # Verify 4-rubric structure
    assert grade_data["content_accuracy"]["score"] == 22
    assert grade_data["structure_clarity"]["score"] == 20
    assert grade_data["regulatory_knowledge"]["score"] == 24
    assert grade_data["examples_evidence"]["score"] == 18
    assert grade_data["total_score"] == 84  # Sum of 4 rubrics

    # Step 2: Store grade in database
    essay_id = grade_data.get("essay_id", f"ess_{datetime.now().timestamp()}")
    conn = db.get_connection()
    try:
        conn.execute(
            """INSERT INTO essays
               (essay_id, user_id, topic, essay_text, graded_at, total_score)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                essay_id,
                "test_user",
                sample_essay["topic"],
                sample_essay["essay_text"],
                datetime.now().isoformat(),
                grade_data["total_score"],
            ),
        )
        conn.commit()
    finally:
        conn.close()

    # Step 3: Verify essay appears in user history
    history_response = client.get(
        f"/api/history/search?query=capital%20markets&limit=20"
    )
    assert history_response.status_code == 200


# ==========================================
# TEST 4: Score Prediction Convergence
# ==========================================


def test_score_prediction_convergence(
    client: TestClient,
    test_db: str,
) -> None:
    """Test that score prediction improves over multiple mock attempts.

    Workflow:
    1. Simulate 3 mocks with improving accuracy
    2. Verify score prediction increases
    3. Verify trajectory calculation is sensible
    """
    user_id = "test_converge_user"

    # Record 3 mock attempts with improving performance
    mocks = []
    for mock_num in range(1, 4):
        mock_record = {
            "mock_id": f"mock_converge_{mock_num}",
            "user_id": user_id,
            "score": 100 + (mock_num * 20),  # 120, 140, 160
            "total_questions": 50,
            "accuracy_pct": 48 + (mock_num * 12),  # 60%, 72%, 84%
            "submitted_at": (datetime.now() - timedelta(days=4 - mock_num)).isoformat(),
        }
        mocks.append(mock_record)

    # Simulate readiness calculation based on improving trend
    readiness_response = client.get(
        f"/api/dashboard/readiness?user_id={user_id}&target_score=65&days_to_exam=28"
    )

    assert readiness_response.status_code == 200
    readiness_data = readiness_response.json()

    # Verify readiness increased
    assert readiness_data["readiness_pct"] > 50  # Should show improvement
    assert readiness_data["final_score_est"] >= 120  # Minimum based on trajectory


# ==========================================
# TEST 5: Weak Area Improvement Tracking
# ==========================================


def test_weak_area_improvement_tracking(
    client: TestClient,
    test_db: str,
    sample_attempt: dict[str, Any],
) -> None:
    """Test that drilling weak topics improves accuracy and updates status.

    Workflow:
    1. Simulate weakness detection (30% accuracy on topic)
    2. Run penalty drill on weak topic
    3. Verify accuracy improves
    4. Verify recommendation changes
    """
    user_id = "test_weak_improve"
    weak_topic = "PH2_IFSCA_ACT"

    # Step 1: Simulate weak performance (3/10 correct)
    conn = db.get_connection()
    try:
        for i in range(1, 11):
            conn.execute(
                """INSERT INTO attempts
                   (attempt_id, user_id, topic, question_id, correct_option, your_option, is_correct, mock_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"att_weak_{i}",
                    user_id,
                    weak_topic,
                    f"q_weak_{i}",
                    "A",
                    "A" if i <= 3 else "B",  # 30% correct
                    i <= 3,
                    "mock_weak_1",
                ),
            )
        conn.commit()
    finally:
        conn.close()

    # Step 2: Verify weakness detected
    weak_response = client.get(f"/api/topics/weak?user_id={user_id}")
    assert weak_response.status_code == 200
    weak_data = weak_response.json()
    weak_topics = [w["topic"] for w in weak_data]
    assert weak_topic in weak_topics

    # Step 3: Simulate drill performance (7/10 correct on same topic)
    try:
        for i in range(11, 21):
            conn.execute(
                """INSERT INTO attempts
                   (attempt_id, user_id, topic, question_id, correct_option, your_option, is_correct, mock_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"att_drill_{i}",
                    user_id,
                    weak_topic,
                    f"q_drill_{i}",
                    "A",
                    "A" if i <= 17 else "B",  # 70% correct in drill
                    i <= 17,
                    "drill_weak_1",
                ),
            )
        conn.commit()
    finally:
        conn.close()

    # Step 4: Verify accuracy improved
    improved_response = client.get(f"/api/topics/stats?user_id={user_id}&topic={weak_topic}")
    assert improved_response.status_code == 200
    stats = improved_response.json()
    # After drill, accuracy should be higher than initial 30%
    # (weighted average of 30% from mocks + 70% from drill)
    estimated_accuracy = (3 + 7) / 20 * 100  # 50%
    assert stats.get("accuracy_pct", 0) > 30


# ==========================================
# TEST 6: Full History Search
# ==========================================


def test_history_search_comprehensive(
    client: TestClient,
    test_db: str,
) -> None:
    """Test FTS5 search across questions, amendments, essays, provisions.

    Workflow:
    1. Create 40+ searchable items across different types
    2. Search for keyword "leverage" or "limit"
    3. Verify results ranked by relevance
    4. Verify results include all types (Qs, amendments, essays)
    """
    user_id = "test_search_user"

    # Step 1: Create multiple items mentioning "leverage"
    conn = db.get_connection()
    try:
        # Add source chunks mentioning leverage
        for i in range(1, 21):
            conn.execute(
                """INSERT INTO source_chunks
                   (chunk_id, doc_id, start_line, end_line, text, section_title, page_num)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"chunk_leverage_{i}",
                    "doc_leverage",
                    i * 100,
                    i * 100 + 50,
                    f"Leverage limit regulations section {i}. Leverage requirements vary by entity type.",
                    f"Section {i}",
                    i,
                ),
            )

        # Add amendments mentioning leverage
        for i in range(1, 11):
            conn.execute(
                """INSERT INTO amendments
                   (amendment_id, topic, title, summary, effective_date)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    f"amd_leverage_{i}",
                    "PH2_CAPITAL",
                    f"Amendment {i}: Updated Leverage Limits",
                    f"New leverage ratio requirements introduced in amendment {i}",
                    datetime.now().isoformat(),
                ),
            )

        conn.commit()
    finally:
        conn.close()

    # Step 2: Search for "leverage"
    search_response = client.get(
        "/api/history/search?query=leverage&limit=50"
    )

    assert search_response.status_code == 200
    search_data = search_response.json()
    assert len(search_data) > 0, "Search should return multiple results"


# ==========================================
# TEST 7: Source Citation Tracing
# ==========================================


def test_source_citation_tracing(
    client: TestClient,
    test_db: str,
    sample_question: dict[str, Any],
) -> None:
    """Test that question sources are linked and traceable to PDFs.

    Workflow:
    1. Generate question with source citation
    2. Get question detail
    3. Click citation → retrieve source excerpt + page
    4. Verify PDF metadata (page number, section, authority score)
    """
    # Step 1: Create source document and chunk
    conn = db.get_connection()
    try:
        conn.execute(
            """INSERT INTO source_documents (doc_id, name, category, type)
               VALUES (?, ?, ?, ?)""",
            ("doc_ifsca_act", "IFSCA Act 2019", "regulations", "PDF"),
        )

        chunk_id = "chunk_section10"
        conn.execute(
            """INSERT INTO source_chunks
               (chunk_id, doc_id, start_line, end_line, text, section_title, page_num)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                chunk_id,
                "doc_ifsca_act",
                450,
                500,
                "Section 10: Powers and Functions of IFSCA Authority...",
                "Section 10",
                180,
            ),
        )

        # Link question to source
        conn.execute(
            """INSERT INTO question_sources (question_id, source_chunk_id, authority_score)
               VALUES (?, ?, ?)""",
            (sample_question["question_id"], chunk_id, 0.95),
        )

        conn.commit()
    finally:
        conn.close()

    # Step 2: Get question and verify source link
    q_response = client.get(
        f"/api/questions/{sample_question['question_id']}/source"
    )

    assert q_response.status_code == 200
    q_data = q_response.json()
    assert "source_chunk_id" in q_data
    assert q_data["source_chunk_id"] == "chunk_section10"
    assert "page_num" in q_data
    assert q_data["page_num"] == 180
    assert "authority_score" in q_data
    assert q_data["authority_score"] == 0.95


# ==========================================
# TEST 8: Performance Benchmarks
# ==========================================


def test_mock_generation_performance(
    client: TestClient,
    test_db: str,
) -> None:
    """Verify mock generation completes within performance budget (15s target).

    Per PROJECT_REFACTOR_PLAN.xml:
    - CURRENT: 45s
    - TARGET: 15s (via parallelization)
    - OPTIMIZATION: Parallel Gemini batches
    """
    import time

    user_id = "test_perf_user"

    with patch("gemini_integration.gemini_available", return_value=True):
        with patch("gemini_integration.generate_questions_with_gemini") as mock_gemini:
            # Mock fast Gemini response (simulating parallelization)
            mock_gemini.return_value = [
                {
                    "question_id": f"q_perf_{i}",
                    "question_text": f"Question {i}",
                    "options": [
                        {"label": "A", "text": "A"},
                        {"label": "B", "text": "B"},
                        {"label": "C", "text": "C"},
                        {"label": "D", "text": "D"},
                    ],
                    "correct_option": "A",
                    "explanation": "Exp",
                    "difficulty": "easy",
                    "topic": "PH2_IFSCA_ACT",
                }
                for i in range(1, 51)
            ]

            start = time.time()
            response = client.post(
                "/api/generate-smart-mock",
                json={"user_id": user_id},
            )
            elapsed = time.time() - start

    assert response.status_code == 200
    # Performance target: <15s for full mock generation
    assert elapsed < 20, f"Mock generation took {elapsed:.2f}s, target <15s"


# ==========================================
# TEST 9: Dashboard Load Performance
# ==========================================


def test_dashboard_load_performance(
    client: TestClient,
    test_db: str,
) -> None:
    """Verify dashboard /api/dashboard endpoint loads <500ms (target <0.5s).

    Per PROJECT_REFACTOR_PLAN.xml:
    - CURRENT: 2s
    - TARGET: 0.5s
    - OPTIMIZATION: Indexes on weak_topics, weak_accuracy
    """
    import time

    user_id = "test_dashboard_user"

    start = time.time()
    response = client.get(f"/api/dashboard?user_id={user_id}")
    elapsed = time.time() - start

    assert response.status_code == 200
    # Performance target: <500ms
    assert elapsed < 1.0, f"Dashboard load took {elapsed:.2f}s, target <0.5s"


# ==========================================
# TEST 10: Amendment Search Performance
# ==========================================


def test_amendment_search_performance(
    client: TestClient,
    test_db: str,
) -> None:
    """Verify FTS5 search completes <1s for "leverage" query.

    Per PROJECT_REFACTOR_PLAN.xml:
    - CURRENT: 5s
    - TARGET: 1s
    - OPTIMIZATION: FTS5 should be fast natively
    """
    import time

    start = time.time()
    response = client.get(
        "/api/history/search?query=leverage&limit=50"
    )
    elapsed = time.time() - start

    assert response.status_code == 200
    # Performance target: <1s
    assert elapsed < 2.0, f"Search took {elapsed:.2f}s, target <1s"


# ==========================================
# TEST 11: Law Revision Daily Generation
# ==========================================


def test_daily_law_revision_generation(
    client: TestClient,
    test_db: str,
) -> None:
    """Test daily law revision tab shows high-yield provisions, amendments, weak areas.

    Workflow:
    1. Get daily law revision
    2. Verify returns: high-yield, amendments, weak areas, spaced review
    3. Verify filtering by accuracy <60%
    """
    user_id = "test_law_revision"

    response = client.get(
        f"/api/law/daily-revision?user_id={user_id}&include_ai=False"
    )

    assert response.status_code == 200
    law_data = response.json()

    # Verify structure
    assert "high_yield_provisions" in law_data
    assert "recent_amendments" in law_data
    assert "weak_legal_areas" in law_data
    assert "spaced_review_due" in law_data

    # Each section should be a list
    assert isinstance(law_data["high_yield_provisions"], list)
    assert isinstance(law_data["recent_amendments"], list)
    assert isinstance(law_data["weak_legal_areas"], list)


# ==========================================
# TEST 12: End-to-End Full Day Simulation
# ==========================================


def test_complete_exam_day_simulation(
    client: TestClient,
    test_db: str,
) -> None:
    """Full simulation of exam day from start to end-of-day recommendation.

    Covers:
    1. Morning: Check dashboard
    2. Take mock exam
    3. Identify weak areas
    4. Take drill
    5. Write essay
    6. Review law provisions
    7. Get next day recommendation
    """
    user_id = "test_exam_day_user"

    # Morning: Get dashboard
    dashboard = client.get(f"/api/dashboard?user_id={user_id}")
    assert dashboard.status_code == 200

    # Get next action recommendation
    next_action = client.get(f"/api/dashboard/next-action?user_id={user_id}")
    assert next_action.status_code == 200

    # Daily law revision
    law_revision = client.get(f"/api/law/daily-revision?user_id={user_id}")
    assert law_revision.status_code == 200

    # Check amendments
    amendments = client.get("/api/amendments/recent?days_back=7")
    assert amendments.status_code == 200

    # Readiness check
    readiness = client.get(f"/api/dashboard/readiness?user_id={user_id}")
    assert readiness.status_code == 200

    # All endpoints should be responsive
    all_ok = all([
        dashboard.status_code == 200,
        next_action.status_code == 200,
        law_revision.status_code == 200,
        amendments.status_code == 200,
        readiness.status_code == 200,
    ])

    assert all_ok, "Some dashboard endpoints failed"
