"""FastAPI backend for the source-grounded IFSCA exam prep engine."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import json
import os
from pathlib import Path as PathLib
import re
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import BackgroundTasks, FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import database as db
import amendment_poller
import job_queue
import essay_grader
import law_revision_engine
import recommendation_engine
import readiness_engine
import error_handling
import gemini_integration
import pyq_parser
import pyq_cache
from gemini_integration import (
    PROMPT_CONTRACT_VERSION,
    USE_CASE_CATALOG,
    extract_and_verify_amendment,
    gemini_available,
    generate_amendment_watchlist,
    generate_exam_analysis,
    generate_focus_plan,
    generate_law_revision_plan,
    generate_mock_blueprint,
    generate_personalized_study_path,
    generate_product_gap_analysis,
    generate_pyq_calibration,
    generate_study_session,
    generate_srs_recommendation,
    generate_topic_source_brief,
    get_gemini_health,
    grade_essay,
    initialize_gemini_runtime,
)
from models import (
    AmendmentExtractRequestModel,
    AmendmentModel,
    AmendmentResponseModel,
    AnalyticsTimelineModel,
    DashboardStatsModel,
    EssayGradingResponseModel,
    EssayPromptModel,
    EssaySubmissionModel,
    ExamAnalyticsModel,
    ExamAnalyticsResponseModel,
    HealthResponseModel,
    IngestResponseModel,
    IngestionStatusModel,
    MockSubmitRequestModel,
    MockSubmitResponseModel,
    MockUploadModel,
    PenaltyDrillRequestModel,
    PenaltyDrillResponseModel,
    QuestionGenerationRequestModel,
    QuestionModel,
    SmartMockRequestModel,
    SmartMockResponseModel,
    SourceSearchResponseModel,
    SRSScheduleRequestModel,
    SRSTopicModel,
    StudyPathModel,
    StudyPathProgressModel,
    StudyPathWeekModel,
    StudySessionRequestModel,
    TopicModel,
    TopicStatsModel,
    WeakTopicsResponseModel,
    LawRevisionModel,
    SpacedReviewItemModel,
    HighYieldProvisionModel,
    RecentAmendmentModel,
    WeakLegalAreaModel,
)


PROJECT_ROOT = PathLib(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DIGEST_PATH = PROJECT_ROOT / "COMPLETE_PDF_DIGEST.txt"
PLAN_PATH = PROJECT_ROOT / "memory" / "FINAL_MAXIMUM_EXTENSIVE_PROJECT_PLAN.md"


def _run_startup_amendment_scan(force_local: bool = False) -> dict[str, Any]:
    candidates = db.startup_amendment_radar_chunks(limit=30)
    watchlist = generate_amendment_watchlist(
        candidates,
        force_local=force_local,
        operation="startup_amendment_scan",
    )
    return {
        "generated_at": datetime.now().isoformat(),
        "candidate_count": len(candidates),
        "watchlist_count": len(watchlist),
        "model": get_gemini_health().get("model"),
        "thinking_level": get_gemini_health().get("thinking_level"),
        "watchlist": watchlist,
        "candidate_sources": [
            {
                "chunk_id": item.get("chunk_id"),
                "title": item.get("title"),
                "category": item.get("category"),
                "page_start": item.get("page_start"),
                "exam_source_score": item.get("exam_source_score"),
            }
            for item in candidates[:12]
        ],
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    db.init_db()
    job_queue.init_job_queue_schema()

    if db.table_count("documents") == 0:
        db.ingest_documents(force=False)
    app.state.gemini = initialize_gemini_runtime(run_probe=True)
    db.seed_critical_amendments()
    app.state.question_quarantine = db.quarantine_low_quality_questions()

    try:
        app.state.startup_amendment_scan = _run_startup_amendment_scan(force_local=False)
    except Exception as exc:
        app.state.startup_amendment_scan = {
            "generated_at": datetime.now().isoformat(),
            "error": str(exc),
            "watchlist": [],
            "candidate_sources": [],
        }

    # Initialize and start APScheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        amendment_poller.run_amendment_poller,
        CronTrigger(hour=3, minute=0, timezone="UTC"),
        id="amendment_daily_poll",
        name="Daily Amendment Poll (3am UTC)",
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        job_queue.process_queue,
        CronTrigger(minute="*/15", timezone="UTC"),
        id="job_queue_processor",
        name="Job Queue Processor (every 15 min)",
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    app.state.scheduler = scheduler

    yield

    # Shutdown
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown(wait=True)


app = FastAPI(
    title="IFSCA Exam Prep Engine",
    description="Source-grounded, amendment-first, weakness-adaptive IFSCA Grade A preparation platform.",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS is restricted to the local dev origins the app is served from. The previous
# wildcard + allow_credentials=True combination is rejected by browsers anyway, and it
# left every localhost:8000 endpoint open to cross-site requests from any website.
DEFAULT_CORS_ORIGINS = "http://localhost:8000,http://127.0.0.1:8000"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static frontend mount. (Previously this line sat inside handle_value_error's body
# after an unconditional raise, so it was dead code and /app never registered.)
if FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="app")


# ============================================================================
# GLOBAL ERROR HANDLING MIDDLEWARE - Applies to all 67 endpoints
# ============================================================================

@app.exception_handler(error_handling.GeminiRateLimitError)
async def handle_gemini_rate_limit(request, exc):
    """Handle 429 rate limit with graceful message."""
    raise HTTPException(status_code=503, detail="Gemini API temporarily rate-limited. Please retry in a moment.")


@app.exception_handler(error_handling.GeminiAuthError)
async def handle_gemini_auth(request, exc):
    """Handle 401/403 auth failure."""
    raise HTTPException(status_code=503, detail="Gemini authentication failed. System administrator notified.")


@app.exception_handler(error_handling.GeminiServerError)
async def handle_gemini_server(request, exc):
    """Handle 500+ server error from Gemini."""
    raise HTTPException(status_code=503, detail="Gemini service temporarily unavailable. Please retry shortly.")


@app.exception_handler(error_handling.DatabaseError)
async def handle_database_error(request, exc):
    """Handle database operation failures."""
    raise HTTPException(status_code=503, detail="Database operation failed. Please retry.")


@app.exception_handler(asyncio.TimeoutError)
async def handle_timeout(request, exc):
    """Handle timeout errors (essay grading, mock generation, etc)."""
    raise HTTPException(status_code=504, detail="Request timed out. Please try again.")


@app.exception_handler(ValueError)
async def handle_value_error(request, exc):
    """Handle value validation errors."""
    raise HTTPException(status_code=422, detail=f"Invalid input: {str(exc)}")


def _coerce_question(question: dict[str, Any]) -> QuestionModel:
    return QuestionModel.model_validate(question)


def _resolve_mock_id(exam_id: str) -> str:
    return exam_id.removeprefix("EXAM_")


def _digest_profile() -> dict[str, Any]:
    profile: dict[str, Any] = {
        "path": str(DIGEST_PATH),
        "exists": DIGEST_PATH.exists(),
        "lines": 0,
        "digest_document_headers": 0,
        "appended_source_files": 0,
        "categories": [],
        "keyword_counts": {},
    }
    if not DIGEST_PATH.exists():
        return profile
    needles = [
        "syllabus",
        "phase",
        "paper",
        "essay",
        "precis",
        "question",
        "memory",
        "pyq",
        "amendment",
        "regulation",
        "circular",
        "effective",
        "techfin",
        "banking handbook",
        "bullion",
        "fund management",
        "payment services",
        "insurance",
        "capital market",
        "current affairs",
    ]
    keyword_counts = {needle: 0 for needle in needles}
    categories: list[str] = []
    with DIGEST_PATH.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            lower = stripped.lower()
            if stripped.startswith("[FILE]"):
                profile["digest_document_headers"] += 1
            if stripped.startswith("SOURCE FILE:"):
                profile["appended_source_files"] += 1
            if re_match_category(stripped):
                categories.append(stripped)
            for needle in needles:
                if needle in lower:
                    keyword_counts[needle] += 1
            profile["lines"] = line_number
    profile["categories"] = categories
    profile["keyword_counts"] = keyword_counts
    return profile


def re_match_category(value: str) -> bool:
    if not value.endswith("files)"):
        return False
    return any(value.startswith(prefix) for prefix in ("ANNUAL", "BULLETINS", "CONSULTING", "CURRENT", "ICSI", "OTHER", "RECRUITMENT", "REGULATIONS"))


def _plan_excerpt() -> str:
    if not PLAN_PATH.exists():
        return ""
    text = PLAN_PATH.read_text(encoding="utf-8", errors="replace")
    anchors = ["## 6. What Claude Got Wrong or Underspecified", "## 8. Final Architecture", "### Layer 4: AI Layer"]
    snippets = []
    for anchor in anchors:
        index = text.find(anchor)
        if index >= 0:
            snippets.append(text[index : index + 2200])
    return "\n\n".join(snippets) or text[:5000]


def _app_inventory() -> dict[str, Any]:
    ingestion = db.get_ingestion_status()
    return {
        "prompt_contract_version": PROMPT_CONTRACT_VERSION,
        "ingestion": ingestion,
        "topics": [topic["topic_id"] for topic in db.list_topics()],
        "implemented_endpoint_groups": [
            "health",
            "ingestion",
            "documents",
            "topics",
            "source_search",
            "mock_upload",
            "weak_topics",
            "penalty_drill",
            "smart_mock",
            "mock_submit",
            "essay_grading",
            "essay_history",
            "amendment_seed_record_list",
            "amendment_intelligence",
            "startup_amendment_scan",
            "daily_law_revision",
            "full_ifsca_act",
            "ai_status",
        ],
        "known_missing_or_partial": [
            "full TCS iON exam mode",
            "wrong-answer replay drill",
            "spaced review scheduler",
            "inline essay rewrite lab",
            "automatic web amendment monitor",
            "source contradiction detector",
            "bulk background question generation",
            "topic sub-taxonomy",
        ],
    }


def _function_improvement_audit() -> list[dict[str, Any]]:
    snapshot = db.intelligent_targeting_snapshot()
    low_bank_topics = [item for item in snapshot["question_bank"] if item.get("bank_status") != "READY"]
    thin_coverage_topics = [item for item in snapshot["coverage"] if item.get("coverage_status") == "THIN"]
    return [
        {
            "function": "search_sources",
            "status": "improved",
            "reason": "Now ranks chunks by official-source authority, exam-signal density, topic match, recency, and duplicate suppression.",
            "next_upgrade": "Add vector retrieval for semantic paraphrases after enough validated questions exist.",
        },
        {
            "function": "chunks_for_topic",
            "status": "improved",
            "reason": "Now returns high-authority, exam-scored topic chunks instead of first keyword matches.",
            "next_upgrade": "Add subtopic-level retrieval once taxonomy is split below the 18 current topics.",
        },
        {
            "function": "existing_questions_for_topic",
            "status": "improved",
            "reason": "Now filters rejected and low-quality fallback stems before reuse so mocks prefer Gemini/source-valid questions.",
            "next_upgrade": f"Regenerate banks for {len(low_bank_topics)} topics that do not yet have 20 reusable questions.",
        },
        {
            "function": "quarantine_low_quality_questions",
            "status": "new",
            "reason": "Marks old filler/generated questions as REJECTED_LOW_QUALITY instead of letting them quietly pollute the bank.",
            "next_upgrade": "Add a UI review table for rejected questions and allow manual promote/delete decisions.",
        },
        {
            "function": "generate_topic_questions",
            "status": "high_priority",
            "reason": "This is the central source-to-question function. It should remain Gemini-first and fallback-only when API fails.",
            "next_upgrade": "Add post-generation validator that rejects weak stems before saving.",
        },
        {
            "function": "build_question_bank",
            "status": "new",
            "reason": "Creates an executable bank-building loop over the current target snapshot instead of leaving thin topic banks as a manual task.",
            "next_upgrade": "Run as a background job until high-priority topics reach 50 validated source-grounded questions.",
        },
        {
            "function": "generate_smart_mock",
            "status": "improved",
            "reason": "Allocation now uses target_score, not weakness alone: weak performance, exam priority, source gaps, question-bank gaps, attempts, and pending amendments.",
            "next_upgrade": "Use PYQ calibration output to vary question styles per topic.",
        },
        {
            "function": "calculate_weakness_score",
            "status": "needs_next_pass",
            "reason": "It handles performance, recency, attempt confidence, time pressure, and amendment backlog, but not confidence intervals.",
            "next_upgrade": "Add Bayesian accuracy smoothing and time-normalized penalty per topic.",
        },
        {
            "function": "generate_study_session",
            "status": "needs_next_pass",
            "reason": "It creates a useful session, but should directly schedule actions from the targeting snapshot.",
            "next_upgrade": "Make it consume top_targets and emit executable API calls for drill/mock/essay generation.",
        },
        {
            "function": "generate_amendment_watchlist",
            "status": "improved",
            "reason": "Now runs during app startup over official legal/regulatory chunks and remains available through the Amendments tab.",
            "next_upgrade": "Add per-source document diffing and official-link polling.",
        },
        {
            "function": "daily_ifsca_act_revision",
            "status": "new",
            "reason": "Creates a daily slice from the actual IndiaCode IFSCA Act text for separate law revision.",
            "next_upgrade": "Track line-level completion and spaced repetition over Act sections.",
        },
        {
            "function": "generate_law_revision_plan",
            "status": "new",
            "reason": "Uses Gemini by default to convert the daily Act slice into traps, key points, descriptive angles, and self-test prompts.",
            "next_upgrade": "Generate one Act-based MCQ and one descriptive micro-prompt per daily slice.",
        },
        {
            "function": "dashboard_data",
            "status": "improved",
            "reason": "Now includes the intelligence snapshot and Gemini focus planning is default through include_ai=true.",
            "next_upgrade": "Render these gaps as actionable buttons in the UI.",
        },
        {
            "function": "Gemini runtime functions",
            "status": "improved",
            "reason": "Custom GeminiKeyManager class removed. Runtime state is now plain dict plus functions. Default model is gemini-flash-latest with thinking_level=high.",
            "next_upgrade": "Persist key health to SQLite if long-running automation is added.",
        },
        {
            "function": "source_coverage_by_topic",
            "status": "new",
            "reason": f"Identifies whether topics have enough official source material. Thin coverage topics now detected: {len(thin_coverage_topics)}.",
            "next_upgrade": "Use thin coverage to produce missing-document acquisition tasks.",
        },
        {
            "function": "question_bank_quality_by_topic",
            "status": "new",
            "reason": "Measures reusable vs low-quality questions per topic instead of trusting raw question count.",
            "next_upgrade": "Add automated bank-building jobs until each high-priority topic has 50 validated questions.",
        },
    ]


@app.get("/")
async def root():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"name": "IFSCA Exam Prep Engine", "version": "2.0.0", "docs": "/docs"}


@app.get("/health", response_model=HealthResponseModel)
async def health_check():
    try:
        ingestion = IngestionStatusModel(**db.get_ingestion_status())
        db_ok = True
    except Exception:
        ingestion = None
        db_ok = False
    gemini = get_gemini_health()
    return HealthResponseModel(
        status="healthy" if db_ok else "degraded",
        api_keys_loaded=gemini["total_keys"],
        gemini_available=gemini_available(),
        central_ai_ready=bool(gemini.get("startup_probe_ok") and gemini.get("available_keys", 0)),
        gemini=gemini,
        database_initialized=db_ok,
        ingestion=ingestion,
        timestamp=datetime.now().isoformat(),
    )


@app.get("/health/gemini")
async def gemini_health():
    return get_gemini_health()


@app.post("/api/ai/reinitialize")
async def reinitialize_ai():
    return initialize_gemini_runtime(run_probe=True)


@app.get("/api/ai/status")
async def ai_status():
    return get_gemini_health()


@app.get("/api/ai/usecases")
async def ai_usecases():
    return {
        "prompt_contract_version": PROMPT_CONTRACT_VERSION,
        "usecases": USE_CASE_CATALOG,
        "ai_status": get_gemini_health(),
    }


@app.post("/api/ai/study-session")
async def ai_study_session(request: StudySessionRequestModel | None = None):
    request = request or StudySessionRequestModel()
    dashboard_data = db.dashboard_data()
    weak = dashboard_data.get("weak_topics", [])
    amendments_data = dashboard_data.get("recent_amendments", [])
    watchlist = generate_amendment_watchlist(db.amendment_candidate_chunks(limit=10))
    session = generate_study_session(
        dashboard_data,
        weak,
        amendments_data,
        watchlist,
        minutes=request.minutes,
        focus=request.focus,
    )
    return {
        "ai_status": get_gemini_health(),
        "session": session,
        "inputs": {
            "minutes": request.minutes,
            "focus": request.focus,
            "weak_topics": len(weak),
            "amendment_watchlist": len(watchlist),
        },
    }


@app.get("/api/ai/topic-brief")
async def ai_topic_brief(topic_id: str = Query(..., min_length=1), limit: int = Query(default=10, ge=3, le=25)):
    normalized = topic_id.upper()
    topic_name = db.topic_display(normalized)
    chunks = db.chunks_for_topic(normalized, limit=limit)
    if not chunks:
        chunks = db.search_sources(topic_name, limit=limit)
    brief = generate_topic_source_brief(normalized, topic_name, chunks)
    return {"ai_status": get_gemini_health(), "brief": brief, "sources": chunks}


@app.get("/api/ai/pyq-calibration")
async def ai_pyq_calibration(limit: int = Query(default=18, ge=5, le=40)):
    chunks = db.pyq_candidate_chunks(limit=limit)
    calibration = generate_pyq_calibration(chunks, _digest_profile())
    return {"ai_status": get_gemini_health(), "calibration": calibration, "sources": chunks}


@app.get("/api/ai/product-gap-analysis")
async def ai_product_gap_analysis():
    analysis = generate_product_gap_analysis(_digest_profile(), _app_inventory(), _plan_excerpt())
    return {"ai_status": get_gemini_health(), "analysis": analysis}


@app.get("/api/ai/mock-blueprint")
async def ai_mock_blueprint(
    total_questions: int = Query(default=50, ge=5, le=100),
    mode: str = Query(default="balanced", pattern="^(balanced|weakness-heavy|amendment-heavy|pyq-like)$"),
):
    config = db.get_smart_mock_config(total_questions=total_questions, mode=mode)
    dashboard_data = db.dashboard_data()
    watchlist = generate_amendment_watchlist(db.amendment_candidate_chunks(limit=10))
    blueprint = generate_mock_blueprint(config, dashboard_data.get("weak_topics", []), watchlist)
    return {
        "ai_status": get_gemini_health(),
        "blueprint": blueprint,
        "allocation": config["allocation"],
        "difficulty_curve": config["difficulty_curve"],
    }


@app.get("/api/intelligence/targeting-snapshot")
async def targeting_snapshot():
    return db.intelligent_targeting_snapshot()


@app.get("/api/intelligence/function-audit")
async def function_audit():
    return {
        "generated_at": datetime.now().isoformat(),
        "architecture": "function_based_business_logic",
        "note": "Pydantic BaseModel classes remain only as FastAPI validation schemas; custom service/OOP runtime classes are avoided.",
        "functions": _function_improvement_audit(),
    }


@app.post("/api/admin/ingest-documents", response_model=IngestResponseModel)
async def ingest_documents(
    background_tasks: BackgroundTasks,
    force: bool = Query(default=False),
    limit: int | None = Query(default=None, ge=1, le=500),
    background: bool = Query(default=False),
):
    if background:
        background_tasks.add_task(db.ingest_documents, force, limit)
        return IngestResponseModel(
            status="queued",
            documents_seen=0,
            documents_indexed=0,
            chunks_indexed=0,
            skipped_existing=0,
            errors=[],
        )
    return IngestResponseModel(**db.ingest_documents(force=force, limit=limit))


@app.get("/api/admin/ingestion-status", response_model=IngestionStatusModel)
async def ingestion_status():
    return IngestionStatusModel(**db.get_ingestion_status())


@app.get("/api/documents")
async def list_documents(limit: int = Query(default=200, ge=1, le=500)):
    return {"documents": db.list_documents(limit=limit)}


@app.get("/api/topics", response_model=list[TopicModel])
async def list_topics():
    return [TopicModel.model_validate(topic) for topic in db.list_topics()]


@app.get("/api/topics/{topic_id}/sources", response_model=SourceSearchResponseModel)
async def topic_sources(topic_id: str, limit: int = Query(default=10, ge=1, le=50)):
    results = db.chunks_for_topic(topic_id.upper(), limit=limit)
    return SourceSearchResponseModel(query=db.topic_display(topic_id.upper()), topic_id=topic_id.upper(), total=len(results), results=results)


@app.get("/api/source-search", response_model=SourceSearchResponseModel)
async def source_search(
    q: str = Query(..., min_length=1),
    topic_id: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
):
    topic = topic_id.upper() if topic_id else None
    results = db.search_sources(q, topic_id=topic, limit=limit)
    return SourceSearchResponseModel(query=q, topic_id=topic, total=len(results), results=results)


@app.post("/api/upload-mock")
async def upload_mock(mock_data: MockUploadModel, background_tasks: BackgroundTasks):
    try:
        db.record_mock(mock_data.model_dump())
        background_tasks.add_task(db.calculate_topic_accuracy)
        weak_topics = db.get_weak_topics(threshold=60.0)
        return {
            "status": "success",
            "mock_id": mock_data.mock_id,
            "questions_processed": len(mock_data.questions),
            "weak_topics_detected": len(weak_topics),
            "weak_topics": [topic["topic"] for topic in weak_topics],
            "penalty_drill_recommended": bool(weak_topics),
            "message": f"Mock recorded. {len(weak_topics)} weak topics detected.",
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/weak-topics", response_model=WeakTopicsResponseModel)
async def weak_topics():
    topics = [TopicStatsModel.model_validate(topic) for topic in db.get_weak_topics(threshold=60.0)]
    return WeakTopicsResponseModel(
        weak_topics=topics,
        penalty_drill_needed=bool(topics),
        recommended_topic=topics[0].topic if topics else None,
    )


@app.get("/api/topics/weak")
async def get_weak_topics_by_user(user_id: str = Query(default="default")):
    """Get weak topics for a user (topics with accuracy < 60%).

    Per Context7 docs for SQLite: Use aggregate functions for accuracy calculation.
    """
    try:
        topics = db.get_weak_topics(threshold=60.0)
        return [{"topic": t.get("topic"), "accuracy": t.get("accuracy_pct"), "attempts": t.get("total_seen")} for t in topics]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/topics/stats")
async def get_topic_stats_by_user(
    user_id: str = Query(default="default"),
    topic: str | None = Query(default=None),
):
    """Get aggregate topic accuracy from production question_attempts."""
    try:
        stats = db.get_topic_stats_for_user(user_id)
        if topic:
            selected = next((item for item in stats if item.get("topic_id") == topic), None)
            return selected or {"topic_id": topic, "accuracy_pct": 0.0, "total_attempts": 0}
        return stats
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/dashboard", response_model=DashboardStatsModel)
async def dashboard(include_ai: bool = Query(default=True)):
    data = db.dashboard_data()
    weak = data.get("weak_topics", [])
    amendments_data = data.get("recent_amendments", [])
    data["focus_plan"] = generate_focus_plan(data, weak, amendments_data, force_local=not include_ai)
    data["amendment_watchlist"] = generate_amendment_watchlist(
        db.startup_amendment_radar_chunks(limit=30) if include_ai else db.amendment_candidate_chunks(limit=12),
        force_local=not include_ai,
        operation="dashboard_live_amendment_watchlist",
    )
    data["ai_status"] = get_gemini_health()
    return DashboardStatsModel.model_validate(data)


@app.get("/api/dashboard/next-action")
async def get_next_action(user_id: str = Query(default="default")):
    """Get next recommended action for default user (Phase 4 autonomy).

    Per PROJECT_REFACTOR_PLAN.xml Week 4: Auto-recommend next action based on accuracy.
    Decision tree:
    - accuracy < 40% AND attempts >= 5 → DRILL (critical)
    - 40% <= accuracy < 60% AND no improvement 3 days → MOCK
    - 60% <= accuracy < 75% AND amendments exist → AMENDMENT_REVIEW
    - 75% <= accuracy < 90% → ESSAY
    - else → REVIEW
    """
    try:
        recommendation = recommendation_engine.get_next_action_for_dashboard(user_id=user_id)
        if recommendation is None:
            return {
                "action": "NO_DATA",
                "topic": None,
                "reason": "Insufficient performance data. Start with a mock exam.",
                "priority": 1,
                "estimated_duration_minutes": 60,
                "estimated_question_count": 50,
            }
        return {
            "action": recommendation.action.value,
            "topic": recommendation.topic,
            "reason": recommendation.reason,
            "priority": recommendation.priority,
            "estimated_duration_minutes": recommendation.estimated_duration_minutes,
            "estimated_question_count": recommendation.estimated_question_count,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate next action: {str(e)}"
        )


@app.get("/api/dashboard/readiness")
async def get_readiness(
    user_id: str = Query(default="default"),
    target_score: int = Query(default=130, ge=0, le=200),
    days_to_exam: int = Query(default=28, ge=1, le=365),
):
    """Get readiness estimate for exam at current performance trajectory (Phase 4 autonomy).

    Per PROJECT_REFACTOR_PLAN.xml Week 4: Estimate probability of achieving target score.
    Returns: readiness_percentage (0-100), final_score_estimate (0-200), weak_areas_count.
    """
    try:
        if not 0 <= target_score <= 200:
            raise HTTPException(
                status_code=422,
                detail="target_score must be between 0 and 200"
            )

        estimate = readiness_engine.calculate_readiness_estimate(
            user_id=user_id,
            target_score=target_score,
            days_to_exam=days_to_exam,
        )
        estimate.validate()

        return {
            "readiness_percentage": estimate.readiness_percentage,
            "final_score_estimate": estimate.final_score_estimate,
            "days_to_exam": estimate.days_to_exam,
            "weak_areas_count": estimate.weak_areas_count,
            "confidence": estimate.confidence,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid readiness parameters: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate readiness: {str(e)}"
        )



@app.get("/api/law/ifsca-act")
async def ifsca_act():
    return db.ifsca_act_full_text()


@app.get("/api/law/daily-revision", response_model=LawRevisionModel)
async def get_daily_law_revision(
    include_ai: bool = Query(default=True),
    days_back: int = Query(default=30, ge=7, le=90),
    lines_per_day: int = Query(default=80, ge=30, le=180),
):
    """Get daily law revision plan: high-yield provisions, amendments, weak areas, spaced review due."""
    return law_revision_engine.daily_law_revision(
        user_id="default",
        days_back=days_back,
        lines_per_day=lines_per_day,
        force_local=not include_ai,
    )


@app.post("/api/questions/generate-from-source")
async def generate_questions_from_source(request: QuestionGenerationRequestModel):
    questions = db.generate_topic_questions(
        request.topic,
        request.count,
        difficulty=request.difficulty,
        query=request.query,
        question_type="manual_source_generation",
        use_gemini=True,
        strict_gemini=True,
        allow_local_fallback=False,
        reuse_existing=False,
        source_policy="exam_material",
    )
    if not questions:
        raise HTTPException(status_code=503, detail="Gemini did not return usable source-grounded questions from the exam/material corpus.")
    return {"questions": [_coerce_question(question) for question in questions]}


@app.post("/api/questions/build-bank")
async def build_question_bank(
    topic_ids: str | None = Query(default=None, description="Comma-separated topic ids; omit to target current weakest/thinnest topics."),
    target_per_topic: int = Query(default=20, ge=5, le=100),
    max_new_questions: int = Query(default=30, ge=1, le=200),
    use_gemini: bool = Query(default=True),
):
    selected = [item.strip().upper() for item in topic_ids.split(",") if item.strip()] if topic_ids else None
    return db.build_question_bank(
        topic_ids=selected,
        target_per_topic=target_per_topic,
        max_new_questions=max_new_questions,
        use_gemini=use_gemini,
    )


@app.post("/api/questions/quarantine-low-quality")
async def quarantine_low_quality_questions(min_quality: float = Query(default=0.48, ge=0.0, le=1.0)):
    result = db.quarantine_low_quality_questions(min_quality=min_quality)
    app.state.question_quarantine = result
    return result


@app.get("/api/questions/{question_id}", response_model=QuestionModel)
async def get_question(question_id: str):
    question = db.get_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return QuestionModel.model_validate(question)


@app.post("/api/penalty-drill", response_model=PenaltyDrillResponseModel)
async def generate_penalty_drill(request: PenaltyDrillRequestModel):
    try:
        questions = db.generate_topic_questions(
            request.topic.upper(),
            request.question_count,
            difficulty=request.difficulty,
            question_type=request.drill_type,
            use_gemini=True,
            strict_gemini=True,
            allow_local_fallback=False,
            reuse_existing=False,
            source_policy="exam_material",
        )
        drill_id = f"DRILL_{request.topic.upper()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return PenaltyDrillResponseModel(
            drill_id=drill_id,
            topic=request.topic.upper(),
            questions=[_coerce_question(question) for question in questions],
            time_limit_minutes=max(10, request.question_count * 2),
            source_grounded=any(question.get("source_chunk_id") for question in questions),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/generate-smart-mock", response_model=SmartMockResponseModel)
async def generate_smart_mock(request: SmartMockRequestModel | None = None):
    request = request or SmartMockRequestModel()
    try:
        if not request.use_gemini:
            raise HTTPException(status_code=400, detail="Gemini is mandatory for every mock; local generation is disabled.")
        result = db.generate_smart_mock(total_questions=request.total_questions, mode=request.mode, use_gemini=True)
        questions = [_coerce_question(question) for question in result["questions"]]
        gemini_questions = sum(1 for question in result["questions"] if question.get("created_by") == "gemini" or str(question.get("question_id", "")).startswith("Q_AI_"))
        local_questions = len(result["questions"]) - gemini_questions
        marks_per_question = round(100 / max(1, len(questions)), 4)
        return SmartMockResponseModel(
            status="success",
            mock_id=result["mock_id"],
            total_questions=len(questions),
            allocation=result["allocation"],
            allocation_summary=result["allocation_summary"],
            weakness_analysis=[TopicStatsModel.model_validate(item) for item in result["weakness_analysis"]],
            questions=questions,
            source_grounded=any(question.source_chunk_id for question in questions),
            message=f"Smart mock generated with Gemini structured output: {gemini_questions} Gemini questions, {local_questions} local fallback questions.",
            time_limit_minutes=60,
            marks_per_question=marks_per_question,
            negative_marking_per_wrong=round(marks_per_question * 0.25, 4),
            exam_rules={
                "timer": "60 minutes",
                "navigation": "one question at a time with review palette",
                "marking": "+marks_per_question for correct, one-fourth negative for wrong",
                "source_policy": "PYQ/phase-paper/information-handout/study-material/official IFSCA corpus only",
                "generation": "Gemini structured JSON output; no local fallback for mocks",
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/mocks/generate", response_model=SmartMockResponseModel)
async def generate_mock_alias(request: SmartMockRequestModel | None = None):
    return await generate_smart_mock(request)


@app.post("/api/mocks/{mock_id}/submit", response_model=MockSubmitResponseModel)
async def submit_mock(mock_id: str, request: MockSubmitRequestModel):
    try:
        result = db.submit_mock(mock_id, [answer.model_dump() for answer in request.answers])
        return MockSubmitResponseModel.model_validate(result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/exams/start")
async def exam_start(request: SmartMockRequestModel | None = None):
    """Start a new exam session with adaptive mock generation.

    Per PROJECT_REFACTOR_PLAN.xml Phase 3: Return 50 questions with:
    - Standard fields (question_text, options, difficulty)
    - expected_time_sec: Time user should spend (~3 min default)
    - negative_marking: Penalty for wrong answer (-1 points)
    """
    try:
        request = request or SmartMockRequestModel()
        # Generate adaptive mock
        result = db.generate_smart_mock(total_questions=request.total_questions, mode=request.mode, use_gemini=True)

        # exam_id = mock_id for simplicity and consistency
        mock_id = result["mock_id"]
        exam_id = f"EXAM_{mock_id}"

        questions = [_coerce_question(q) for q in result["questions"]]

        # Add missing Phase 3 fields per audit.
        # NOTE: item assignment (question["expected_time_sec"] = ...) on a Pydantic
        # model raises TypeError, which made /api/exams/start fail with 500 every time.
        # The response is BLIND: the answer key (correct_option/explanation/source
        # citation) is stripped so the exam cannot be answered from the payload.
        question_payload = []
        for question in questions:
            payload = question.model_dump()
            payload["expected_time_sec"] = 180  # 3 minutes per question
            payload["negative_marking"] = -1    # -1 for wrong answer
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
                payload.pop(answer_key_field, None)
            question_payload.append(payload)

        return {
            "exam_id": exam_id,
            "mock_id": mock_id,
            "started_at": datetime.now().isoformat(),
            "time_limit_seconds": 3600,
            "question_count": len(question_payload),
            "questions": question_payload,
            "allocation_summary": result.get("allocation_summary", {}),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/exams/{exam_id}/time-remaining")
async def exam_time_remaining(exam_id: str):
    """Get remaining time for exam (server-side timer validation)."""
    try:
        conn = db.get_connection()
        try:
            mock_id = _resolve_mock_id(exam_id)
            row = conn.execute(
                "SELECT started_at FROM mock_sessions WHERE mock_id = ? LIMIT 1",
                (mock_id,),
            ).fetchone()

            if not row or not row["started_at"]:
                return {
                    "exam_id": exam_id,
                    "time_remaining_seconds": 3600,
                    "status": "not_found",
                }

            started_at = datetime.fromisoformat(row["started_at"])
            elapsed = (datetime.now() - started_at).total_seconds()
            remaining = max(0, 3600 - elapsed)

            return {
                "exam_id": exam_id,
                "time_remaining_seconds": int(remaining),
                "elapsed_seconds": int(elapsed),
                "status": "active" if remaining > 0 else "expired",
            }
        finally:
            conn.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/exams/{exam_id}/submit")
async def exam_submit(exam_id: str, request: MockSubmitRequestModel):
    """Submit exam with server-side time validation and scoring."""
    try:
        mock_id = _resolve_mock_id(exam_id)
        elapsed = 0.0
        conn = db.get_connection()
        try:
            # Look up mock session to get started_at and questions
            session_row = conn.execute(
                "SELECT * FROM mock_sessions WHERE mock_id = ? LIMIT 1",
                (mock_id,),
            ).fetchone()

            if not session_row:
                raise HTTPException(status_code=404, detail="Exam session not found")

            started_at_str = session_row["started_at"]
            if not started_at_str:
                raise HTTPException(status_code=400, detail="Exam session not started")

            started_at = datetime.fromisoformat(started_at_str)
            elapsed = (datetime.now() - started_at).total_seconds()

            # Server-side timer enforcement - CRITICAL SECURITY CHECK
            if elapsed > 3600:
                return {
                    "exam_id": exam_id,
                    "status": "error",
                    "reason": "EXAM_TIME_EXPIRED",
                    "code": 403,
                    "message": f"Exam expired {elapsed - 3600:.0f} seconds ago",
                }

        finally:
            conn.close()

        result = db.submit_mock(mock_id, [answer.model_dump() for answer in request.answers])
        weak_areas = [
            {
                "topic": item["topic"],
                "accuracy_pct": item["accuracy_pct"],
                "correct": item["total_correct"],
                "total": item["total_seen"],
            }
            for item in result.get("topic_breakdown", [])
            if item.get("accuracy_pct", 100) < 60
        ]
        return {
            "exam_id": exam_id,
            "mock_id": mock_id,
            "status": "submitted",
            "code": 200,
            "final_score": result["final_score"],
            "raw_score": result["raw_score"],
            "negative_marks": result["negative_marks"],
            "total_questions": result["total_questions"],
            "total_correct": result["total_correct"],
            "total_wrong": result["total_wrong"],
            "total_unanswered": result["total_unanswered"],
            "accuracy_pct": result["accuracy_pct"],
            "weak_areas": weak_areas,
            "elapsed_seconds": int(elapsed),
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except ValueError as exc:
        # Duplicate submission / validation failures surfaced from db.submit_mock
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ========== PYQ (PREVIOUS YEAR QUESTIONS) ENDPOINTS ==========

@app.get("/api/pyq/list")
async def list_pyq_papers():
    """List available previous year question papers for attempt."""
    try:
        conn = db.get_connection()
        try:
            # The legacy source_documents table is never populated by current
            # ingestion (which writes to `documents`), so PYQ papers were invisible
            # on fresh installations. Query the canonical documents table instead.
            pyq_docs = conn.execute(
                "SELECT document_id, title FROM documents WHERE source_role = 'pyq_phase_paper' ORDER BY title"
            ).fetchall()

            papers = []
            for doc in pyq_docs:
                # Extract metadata from document title
                name = doc["title"]
                year_match = re.search(r"(?:19|20)\d{2}", name)
                phase_match = re.search(r"[Pp]hase[\s_-]*(\d)", name)
                paper_match = re.search(r"[Pp]aper[\s_-]*(\d)", name)
                papers.append({
                    "pyq_doc_id": doc["document_id"],
                    "title": name,
                    "year": int(year_match.group(0)) if year_match else None,
                    "phase": int(phase_match.group(1)) if phase_match else None,
                    "paper": int(paper_match.group(1)) if paper_match else None,
                })

            return {"status": "ok", "papers": papers}
        finally:
            conn.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/pyq/{doc_id}/load")
async def load_pyq_paper(doc_id: str):
    """Load a previous year question paper with its parsed questions."""
    conn = None
    try:
        conn = db.get_connection()

        # Get PYQ document metadata from the canonical documents table
        doc = conn.execute(
            "SELECT * FROM documents WHERE document_id = ? AND source_role = 'pyq_phase_paper' LIMIT 1",
            (doc_id,)
        ).fetchone()

        if not doc:
            raise HTTPException(status_code=404, detail="PYQ paper not found")

        # Fetch all chunks for this document in order
        chunks = conn.execute(
            "SELECT text FROM document_chunks WHERE document_id = ? ORDER BY line_start, chunk_id",
            (doc_id,)
        ).fetchall()

        if not chunks:
            raise HTTPException(status_code=400, detail="No content available for this PYQ paper")

        # Combine all chunks into full text
        # Per Context7 docs for Python: use ''.join() for efficient string concatenation
        full_text = ''.join([chunk['text'] for chunk in chunks])

        # Parse questions from full text
        # Per Context7 docs: wrap in try/except for proper error handling
        try:
            parsed_questions = pyq_parser.parse_pyq_paper(full_text)
        except ValueError as parse_err:
            raise HTTPException(status_code=400, detail=f"Failed to parse PYQ paper: {str(parse_err)}")

        if not parsed_questions:
            raise HTTPException(status_code=400, detail="No valid questions found in PYQ paper")

        # Create PYQ session ID and cache questions
        pyq_id = f"PYQ_DOC{doc_id}"

        # Cache ONLY the questions actually shown to the user (capped at 50).
        # Previously the full parsed set was cached while only 50 were displayed,
        # so submissions could score hidden questions, and the displayed count and
        # the scoring denominator could diverge.
        displayed_questions = parsed_questions[:50]
        pyq_cache.cache_pyq_questions(pyq_id, displayed_questions)

        # Format questions for frontend response
        # Note: Correct answers are stored in cache, not sent to frontend (blind submission)
        formatted_questions = []
        for pq in displayed_questions:
            formatted_questions.append({
                "question_id": f"PYQ_DOC{doc_id}_Q{pq.question_number}",
                "question_number": pq.question_number,
                "question_text": pq.question_text,
                "options": [
                    {"label": label, "text": text}
                    for label, text in pq.options.items()
                ],
                # Correct answer NOT sent to frontend (blind submission)
            })

        return {
            "status": "ok",
            "pyq_id": pyq_id,
            "title": doc["title"],
            "total_questions": len(formatted_questions),
            "time_limit_minutes": 60,
            "marks_per_question": 2,
            "negative_marking_per_wrong": 0.67,
            "questions": formatted_questions,
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error loading PYQ paper: {str(exc)}") from exc
    finally:
        # Per Context7 docs for SQLite: use try/finally to ensure connection cleanup
        if conn:
            conn.close()


@app.post("/api/pyq/{pyq_id}/submit")
async def submit_pyq_attempt(pyq_id: str, request: MockSubmitRequestModel):
    """Submit a previous year question paper attempt.

    Scoring is computed against the DISPLAYED question set (the 50-question cap
    cached at load time), not against however many answers the client chose to send:
    - unanswered questions count toward the denominator but not as wrong answers,
    - negative marking (0.67 per wrong answer, as advertised at load time) applies,
    - re-submitting the same attempt replaces the previous attempt instead of
      duplicating rows or 500ing on a primary-key conflict.
    """
    conn = None
    try:
        # Retrieve cached parsed questions
        cached_questions = pyq_cache.get_pyq_questions(pyq_id)
        if not cached_questions:
            raise HTTPException(
                status_code=400,
                detail="PYQ session expired or not found. Please reload the paper and try again."
            )

        # Build a map of question_number -> correct_answer for quick validation
        # Format of question_id from frontend is: "PYQ_DOC{doc_id}_Q{question_number}"
        answer_map = {q.question_number: q.correct_answer for q in cached_questions}
        total_questions = len(cached_questions)

        conn = db.get_connection()

        try:
            # Create PYQ session record.
            # pyq_source_doc_id stays 0 (placeholder): the legacy FK to
            # source_documents was removed by _repair_pyq_schema in database.py.
            session_id = pyq_id
            # Carry the paper title into the session row (PYQ_DOC{doc_id} -> documents.title)
            doc_id = pyq_id.removeprefix("PYQ_DOC")
            title_row = conn.execute(
                "SELECT title FROM documents WHERE document_id = ? LIMIT 1",
                (doc_id,),
            ).fetchone()
            pyq_title = title_row["title"] if title_row else pyq_id
            conn.execute(
                """
                INSERT INTO pyq_sessions
                (pyq_id, pyq_source_doc_id, pyq_title, started_at, submitted_at, status)
                VALUES (?, 0, ?, datetime('now'), datetime('now'), 'completed')
                ON CONFLICT DO UPDATE SET status = 'completed'
                """,
                (session_id, pyq_title)
            )

            # Idempotency: replace any previous attempt rows for this session
            # (attempt_id is the PK; a plain INSERT would 500 on re-submission).
            conn.execute("DELETE FROM pyq_question_attempts WHERE pyq_id = ?", (pyq_id,))

            # Process answers and calculate score
            # Per Context7 docs for Python: use proper exception handling in loops
            total_correct = 0
            total_answered = 0
            total_wrong = 0

            # request.answers is a list of AnswerModel (Pydantic) objects, not dicts
            for answer in request.answers:
                question_id = answer.question_id
                selected = answer.selected_answer
                time_spent = answer.time_spent_seconds or 0
                marked_for_review = answer.marked_for_review

                # Extract question_number from question_id (PYQ_DOC1_Q5 -> 5)
                try:
                    q_num_str = question_id.split("_Q")[-1]
                    q_number = int(q_num_str)
                except (ValueError, IndexError):
                    # Skip malformed question IDs
                    continue

                # Get the correct answer from cache (only displayed questions exist here)
                correct_answer = answer_map.get(q_number)
                if not correct_answer:
                    # Question not in the displayed set - skip
                    continue

                answered = bool(selected)
                if answered:
                    total_answered += 1

                # Validate selected answer against real correct answer
                is_correct = answered and (selected == correct_answer)
                if is_correct:
                    total_correct += 1
                elif answered:
                    total_wrong += 1

                # Record attempt with actual answer comparison
                # Per Context7 docs for SQLite: use parameterized queries for safety
                conn.execute(
                    """
                    INSERT INTO pyq_question_attempts
                    (attempt_id, pyq_id, question_id, question_number, selected_answer, official_answer, is_correct, time_spent_seconds, marked_for_review)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"{pyq_id}_{question_id}",
                        pyq_id,
                        question_id,
                        q_number,
                        selected,
                        correct_answer,
                        is_correct,
                        time_spent,
                        marked_for_review
                    )
                )

            # 2 marks per correct answer, -0.67 per wrong answer (as advertised at load)
            raw_score = total_correct * 2
            negative_marks = round(total_wrong * 0.67, 2)
            final_score = round(max(0.0, raw_score - negative_marks), 2)
            total_unanswered = max(0, total_questions - total_answered)
            accuracy = round((total_correct / total_questions * 100), 2) if total_questions > 0 else 0.0

            # Update session with results
            conn.execute(
                """
                UPDATE pyq_sessions
                SET score = ?, accuracy = ?, status = 'completed', submitted_at = datetime('now'),
                    total_questions = ?
                WHERE pyq_id = ?
                """,
                (final_score, accuracy, total_questions, session_id)
            )

            conn.commit()

            # Clear from cache after successful submission
            pyq_cache.clear_pyq_cache(pyq_id)

            return {
                "pyq_id": pyq_id,
                "status": "submitted",
                "final_score": final_score,
                "raw_score": raw_score,
                "negative_marks": negative_marks,
                "total_questions": total_questions,
                "total_answered": total_answered,
                "total_correct": total_correct,
                "total_wrong": total_wrong,
                "total_unanswered": total_unanswered,
                "accuracy_pct": accuracy,
            }

        finally:
            # Per Context7 docs for SQLite: use try/finally for connection cleanup
            if conn:
                conn.close()

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error submitting PYQ attempt: {str(exc)}") from exc


@app.get("/api/pyq/analytics")
async def get_pyq_analytics():
    """Get analytics for all PYQ attempts."""
    try:
        conn = db.get_connection()
        try:
            attempts = conn.execute(
                """
                SELECT
                    pyq.pyq_id,
                    pyq.pyq_title,
                    pyq.score,
                    pyq.accuracy,
                    COUNT(att.attempt_id) as questions_attempted,
                    SUM(CASE WHEN att.is_correct = 1 THEN 1 ELSE 0 END) as correct_count
                FROM pyq_sessions pyq
                LEFT JOIN pyq_question_attempts att ON pyq.pyq_id = att.pyq_id
                WHERE pyq.status = 'completed'
                GROUP BY pyq.pyq_id
                ORDER BY pyq.submitted_at DESC
                LIMIT 10
                """
            ).fetchall()

            return {
                "status": "ok",
                "attempts": [dict(att) for att in attempts],
                "total_pyq_attempts": len(attempts),
            }
        finally:
            conn.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ========== ADMIN: MATERIAL MANAGEMENT ENDPOINTS ==========

@app.get("/api/admin/materials")
async def list_materials():
    """List all source materials with their categorization."""
    try:
        conn = db.get_connection()
        try:
            # Canonical documents table: source_documents is a legacy table that
            # current ingestion never populates, so listing it showed empty on
            # fresh installations while /api/documents had 150 entries.
            materials = conn.execute(
                "SELECT document_id AS doc_id, title AS name, source_role FROM documents ORDER BY source_role, title"
            ).fetchall()
            return {
                "status": "ok",
                "materials": [dict(mat) for mat in materials],
                "total": len(materials),
            }
        finally:
            conn.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/admin/materials/{doc_id}/role")
async def update_material_role(doc_id: str, request: dict):
    """Update the categorization role for a source material."""
    try:
        new_role = request.get("source_role", "supporting_material")
        valid_roles = ["pyq_phase_paper", "regulatory_core", "amendment_tracking", "essay_examples", "supporting_material"]

        if new_role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {valid_roles}")

        conn = db.get_connection()
        try:
            updated = conn.execute(
                "UPDATE documents SET source_role = ? WHERE document_id = ?",
                (new_role, doc_id)
            )
            if updated.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Material {doc_id} not found")
            conn.commit()
            return {"status": "ok", "doc_id": doc_id, "new_role": new_role}
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/admin/analysis/grounding")
async def material_grounding_analysis():
    """Analyze source material grounding and categorization statistics."""
    try:
        conn = db.get_connection()
        try:
            # Count by role from the canonical documents table
            by_role = {}
            for role in ["pyq_phase_paper", "regulatory_core", "amendment_tracking", "essay_examples", "supporting_material"]:
                count = conn.execute(
                    "SELECT COUNT(*) FROM documents WHERE source_role = ?",
                    (role,)
                ).fetchone()[0]
                by_role[role] = count

            # Count grounded questions: the current flow writes question_citations;
            # question_sources is only used by the legacy source_chunks flow.
            grounded = conn.execute(
                """
                SELECT COUNT(*) FROM generated_questions
                WHERE question_id IN (SELECT question_id FROM question_citations)
                   OR question_id IN (SELECT question_id FROM question_sources)
                """
            ).fetchone()[0]
            total_questions = conn.execute(
                "SELECT COUNT(*) FROM generated_questions"
            ).fetchone()[0]

            grounding_rate = (grounded / total_questions * 100) if total_questions > 0 else 0

            return {
                "status": "ok",
                "by_role": by_role,
                "total_documents": sum(by_role.values()),
                "grounded_questions": grounded,
                "total_questions": total_questions,
                "grounding_rate_pct": round(grounding_rate, 1),
            }
        finally:
            conn.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/essays/prompts", response_model=list[EssayPromptModel])
async def essay_prompts():
    return [EssayPromptModel.model_validate(prompt) for prompt in db.essay_prompts()]


@app.post("/api/grade-essay", response_model=EssayGradingResponseModel)
async def grade_essay_endpoint(submission: EssaySubmissionModel):
    """Grade essay using automated 4-rubric system with source grounding."""
    try:
        source_chunks = db.chunks_for_topic(submission.topic.upper(), limit=6, query=submission.prompt)
        # Use essay_grader module (thin wrapper with validation + fallback)
        grade_response = essay_grader.grade_essay_with_sources(
            submission.essay_text,
            submission.topic.upper(),
            source_chunks,
            force_local=False
        )
        # Save to database
        essay_id = db.save_essay(submission.model_dump(), grade_response.model_dump(), source_chunks)
        grade_response.essay_id = essay_id
        return grade_response
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/essays/history")
async def essay_history(limit: int = Query(default=25, ge=1, le=100)):
    return {"essays": db.list_essays(limit=limit)}


@app.get("/api/history/search")
async def history_search(query: str = Query(..., min_length=1), limit: int = Query(default=20, ge=1, le=100)):
    """Search the local study history and indexed source corpus."""
    source_results = db.search_sources(query, limit=min(limit, 50))
    essays = [
        item for item in db.list_essays(limit=limit)
        if query.lower() in f"{item.get('prompt', '')} {item.get('essay_text', '')} {item.get('topic_tags', '')}".lower()
    ]
    amendments = [
        item for item in db.list_amendments(limit=limit)
        if query.lower() in f"{item.get('title', '')} {item.get('topic_id', '')} {item.get('new_value', '')}".lower()
    ]
    return {
        "query": query,
        "total": len(source_results) + len(essays) + len(amendments),
        "sources": source_results[:limit],
        "essays": essays[:limit],
        "amendments": amendments[:limit],
    }


# ============================================================================
# PHASE 5: Law Revision & Spaced Review Endpoints
# ============================================================================

@app.get("/api/law/review/due", response_model=list[SpacedReviewItemModel])
async def get_law_review_due(limit: int = Query(default=20, ge=1, le=50)):
    """Get law review items due today for spaced revision."""
    return law_revision_engine.get_spaced_review_due(limit=limit)


@app.post("/api/law/review/{review_id}/complete")
async def mark_law_review_complete(
    review_id: str,
    success: bool = Query(default=True),
):
    """Mark a law review item as complete (success/failure) and update SM-2 scheduling."""
    try:
        result = law_revision_engine.mark_review_complete(review_id, success=success)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/provisions/{provision_id}")
async def get_provision_detail(provision_id: str = Path(..., description="Provision ID")):
    """Get provision detail with sources and related questions (Phase 5 completeness).

    Per PROJECT_REFACTOR_PLAN.xml Phase 5: Returns:
    - provision_id, text, source_chunk_id
    - source_document detail (title, page_num, authority_score)
    - related_questions: recent questions mentioning this provision
    - recent_amendments: amendments affecting this provision
    """
    try:
        # Query provision from source chunks or review items
        conn = db.get_connection()
        conn.row_factory = __import__("sqlite3").Row

        # Get provision text and source
        provision = conn.execute(
            """SELECT chunk_id, document_id, text, page_start
               FROM document_chunks
               WHERE chunk_id = ?""",
            (provision_id,)
        ).fetchone()

        if not provision:
            raise HTTPException(status_code=404, detail=f"Provision {provision_id} not found")

        # Get document metadata
        doc = conn.execute(
            """SELECT document_id, title, category
               FROM documents
               WHERE document_id = ?""",
            (provision["document_id"],)
        ).fetchone()

        # Get authority score
        authority_score = db.get_source_authority_for_chunk(provision_id)

        # Get related questions mentioning this provision
        related_questions = conn.execute(
            """SELECT DISTINCT q.question_id, q.question_text
               FROM generated_questions q
               JOIN question_sources qs ON q.question_id = qs.question_id
               WHERE qs.source_chunk_id = ?
               LIMIT 5""",
            (provision_id,)
        ).fetchall()

        # Get amendments affecting this topic (rough: from title keywords)
        recent_amendments = db.get_recent_amendments(days_back=30, limit=3)

        conn.close()

        return {
            "provision_id": provision_id,
            "text": provision["text"],
            "source": {
                "document_id": provision["document_id"],
                "title": doc["title"] if doc else "",
                "category": doc["category"] if doc else "",
                "page_num": provision["page_start"],
                "authority_score": authority_score,
            },
            "related_questions": [dict(q) for q in related_questions],
            "recent_amendments": recent_amendments[:3],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve provision: {str(exc)}") from exc


@app.get("/api/law/weak-areas", response_model=list[WeakLegalAreaModel])
async def get_weak_legal_areas(limit: int = Query(default=10, ge=1, le=20)):
    """Get legal areas where user's accuracy is weak (<60%)."""
    return law_revision_engine.get_weak_legal_areas(limit=limit)


@app.get("/api/amendments/recent", response_model=list[RecentAmendmentModel])
async def get_recent_amendments_endpoint(
    days_back: int = Query(default=30, ge=7, le=90),
    limit: int = Query(default=20, ge=1, le=50),
):
    """Get recent amendments from past N days (highest exam relevance)."""
    return law_revision_engine.get_recent_amendments(days_back=days_back, limit=limit)


@app.get("/api/law/high-yield", response_model=list[HighYieldProvisionModel])
async def get_high_yield_provisions(limit: int = Query(default=15, ge=1, le=30)):
    """Get high-yield provisions most likely to appear in exam."""
    return law_revision_engine.get_high_yield_provisions(limit=limit)


@app.post("/api/record-amendment", response_model=AmendmentResponseModel)
async def record_amendment(amendment: AmendmentModel, auto_generate_questions: bool = Query(default=True)):
    try:
        db.record_amendment(amendment.model_dump())
        generated = 0
        if auto_generate_questions and amendment.questions_needed:
            questions = db.generate_amendment_questions(
                amendment.amendment_id,
                amendment.topic.upper(),
                count=amendment.questions_needed,
                query=f"{amendment.rule_name} {amendment.new_value or ''}",
            )
            generated = len(questions)
        return AmendmentResponseModel(status="recorded", amendment_id=amendment.amendment_id, questions_generated=generated)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/amendments/seed")
async def seed_amendments():
    if db.table_count("documents") == 0:
        db.ingest_documents(force=False)
    return db.seed_critical_amendments()


@app.get("/api/amendments")
async def amendments(limit: int = Query(default=100, ge=1, le=500)):
    return {"amendments": db.list_amendments(limit=limit)}


@app.get("/api/amendments/intelligence")
async def amendment_intelligence(limit: int = Query(default=12, ge=1, le=50)):
    candidates = db.amendment_candidate_chunks(limit=max(limit, 15))
    watchlist = generate_amendment_watchlist(candidates)
    return {"ai_status": get_gemini_health(), "watchlist": watchlist[:limit], "candidate_count": len(candidates)}


@app.get("/api/amendments/startup-scan")
async def startup_amendment_scan(refresh: bool = Query(default=False)):
    if refresh or not hasattr(app.state, "startup_amendment_scan"):
        app.state.startup_amendment_scan = _run_startup_amendment_scan(force_local=False)
    return {
        "ai_status": get_gemini_health(),
        "scan": app.state.startup_amendment_scan,
    }


@app.post("/api/amendments/extract")
async def extract_amendment(request: AmendmentExtractRequestModel):
    extracted = extract_and_verify_amendment(request.amendment_text, request.amendment_url)
    saved = False
    questions_generated = 0
    if request.save:
        amendment_id = f"AMN_AI_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        db.record_amendment(
            {
                "amendment_id": amendment_id,
                "topic": str(extracted.get("topic") or "PH2_CURRENT_AFFAIRS").upper(),
                "rule_name": extracted.get("rule_name") or "Gemini extracted amendment",
                "effective_date": extracted.get("effective_date") or datetime.now().date().isoformat(),
                "old_value": extracted.get("old_value"),
                "new_value": extracted.get("new_value"),
                "source_url": extracted.get("source_url") or request.amendment_url,
                "verify_status": extracted.get("verify_status") or "GEMINI_EXTRACTED",
                "priority": str(extracted.get("priority") or "NORMAL").upper(),
                "questions_needed": 3,
            }
        )
        questions_generated = len(
            db.generate_amendment_questions(
                amendment_id,
                str(extracted.get("topic") or "PH2_CURRENT_AFFAIRS").upper(),
                count=3,
                query=f"{extracted.get('rule_name', '')} {extracted.get('new_value', '')}",
            )
        )
        extracted["amendment_id"] = amendment_id
        saved = True
    return {
        "ai_status": get_gemini_health(),
        "extracted": extracted,
        "saved": saved,
        "questions_generated": questions_generated,
    }


@app.get("/api/amendments/pending-review")
async def pending_amendments():
    amendments_data = [item for item in db.list_amendments(limit=500) if item.get("mastery_status") != "MASTERED"]
    return {"amendments": amendments_data}


@app.get("/api/amendments/status")
async def amendments_status():
    """Return amendment polling status and new amendments."""
    conn = db.get_connection()
    try:
        # Get last poll timestamp
        last_poll = conn.execute(
            "SELECT MAX(polled_at) as last_polled FROM amendment_source_polls WHERE status = 'success'"
        ).fetchone()

        # Count new amendments this week.
        # created_at is a SQLite TIMESTAMP ('YYYY-MM-DD HH:MM:SS'); an ISO 'T'
        # cutoff string excluded boundary rows ('T' > ' ' in string comparison).
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        new_count = conn.execute(
            "SELECT COUNT(*) as count FROM amendments WHERE created_at > ?",
            (week_ago,),
        ).fetchone()[0]

        # Get recent amendments
        recent = conn.execute(
            """
            SELECT amendment_id, topic, rule_name, effective_date, source_url, priority, created_at
            FROM amendments
            ORDER BY created_at DESC
            LIMIT 10
            """,
        ).fetchall()

        amendments_list = [
            {
                "amendment_id": row[0],
                "topic": row[1],
                "rule_name": row[2],
                "effective_date": row[3],
                "source_url": row[4],
                "priority": row[5],
                "created_at": row[6],
            }
            for row in recent
        ]

        return {
            "enabled": True,
            "last_poll_at": last_poll[0] if last_poll[0] else "Never",
            "next_poll_at": "Today at 3am UTC (estimated)",
            "new_count_this_week": new_count,
            "auto_questions_count": new_count * 3,
            "amendments": amendments_list,
        }
    finally:
        conn.close()


@app.get("/api/questions/{question_id}/source", response_model=dict[str, Any])
async def get_question_source(question_id: str):
    """Retrieve source citation details for a specific question."""
    conn = db.get_connection()
    try:
        citation = conn.execute(
            "SELECT * FROM question_citations WHERE question_id = ? LIMIT 1",
            (question_id,),
        ).fetchone()
        if citation:
            source = db.get_source_chunk_detail(citation["chunk_id"])
            if not source:
                return {"status": "not_found", "question_id": question_id}
            return {
                "status": "found",
                "question_id": question_id,
                "source": source,
                "authority_score": source.get("authority_score"),
                "page_start": citation["page_start"],
                "page_end": citation["page_end"],
                "citation_note": citation["citation_note"] or source.get("citation_note"),
            }

        legacy_link = conn.execute(
            """
            SELECT source_chunk_id, authority_score
            FROM question_sources
            WHERE question_id = ? LIMIT 1
            """,
            (question_id,),
        ).fetchone()
        if not legacy_link:
            return {"status": "not_found", "question_id": question_id}
        source = db.get_source_chunk_detail(str(legacy_link["source_chunk_id"]))
        if not source:
            return {"status": "not_found", "question_id": question_id}
        return {
            "status": "found",
            "question_id": question_id,
            "source": source,
            "authority_score": legacy_link["authority_score"] or source.get("authority_score"),
            "page_start": source.get("page_start"),
            "page_end": source.get("page_end"),
            "citation_note": source.get("citation_note"),
        }
    finally:
        conn.close()


@app.get("/api/source-chunks/{chunk_id}", response_model=dict[str, Any])
async def get_source_chunk(chunk_id: str):
    """Retrieve a source chunk directly from the canonical document index."""
    source = db.get_source_chunk_detail(chunk_id)
    if not source:
        return {"status": "not_found", "chunk_id": chunk_id}
    return {"status": "found", "chunk_id": chunk_id, "source": source, "citation_note": source.get("citation_note")}


@app.get("/api/questions/search", response_model=SourceSearchResponseModel)
async def search_questions(query: str, topic_id: str | None = None, limit: int = 10):
    """Full-text search questions and return by authority score."""
    if not query or not query.strip():
        return {"query": query, "topic_id": topic_id, "total": 0, "results": []}
    topic = topic_id.upper() if topic_id else None
    results = db.search_sources(query, topic_id=topic, limit=limit)
    return {
        "query": query,
        "topic_id": topic,
        "total": len(results),
        "results": results,
    }


@app.get("/api/sources/distribution-by-topic", response_model=dict[str, Any])
async def source_distribution_by_topic():
    """Get pie chart data for source distribution by topic."""
    data = db.source_distribution_by_category()
    return {"status": "success", **data}


@app.post("/api/exams/{exam_id}/analytics", response_model=ExamAnalyticsResponseModel)
async def post_exam_analytics(exam_id: str, analytics: list[ExamAnalyticsModel]):
    """Save detailed analytics after exam completion. Per Context7 docs for FastAPI: proper error handling."""
    try:
        count = db.save_exam_analytics(exam_id, [a.model_dump() for a in analytics])
        overall_acc = sum(a.accuracy_pct for a in analytics) / len(analytics) if analytics else 0.0
        weak = [a.topic_id for a in analytics if a.accuracy_pct < 60]
        return ExamAnalyticsResponseModel(
            exam_id=exam_id,
            total_topics_analyzed=len(analytics),
            overall_accuracy=overall_acc,
            topic_analytics=analytics,
            weak_topics=weak[:5],
            improvement_areas=["Review weak topics", "Practice time management"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc



@app.get("/api/analytics/timeline", response_model=list[AnalyticsTimelineModel])
async def get_analytics_timeline(limit: int = Query(default=10, ge=1, le=50)):
    """Get score progression timeline across all mocks."""
    try:
        timeline = db.get_analytics_timeline(limit)
        return [AnalyticsTimelineModel(**item) for item in timeline]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/analytics/comparison/{topic_id}")
async def compare_topic_performance(topic_id: str):
    """Compare topic performance across all exams (trending)."""
    try:
        analytics = db.get_analytics_timeline(50)
        topic_data = [a for a in analytics if a.get("topic_id") == topic_id or topic_id in str(a)]
        return {
            "topic_id": topic_id,
            "exam_count": len(topic_data),
            "avg_accuracy": sum(a.get("avg_topic_accuracy", 0) or 0 for a in topic_data) / len(topic_data) if topic_data else 0,
            "trend": "improving" if len(topic_data) > 1 and (topic_data[-1].get("avg_topic_accuracy", 0) or 0) > (topic_data[0].get("avg_topic_accuracy", 0) or 0) else "stable",
            "history": topic_data[:5],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/srs/due-topics", response_model=list[SRSTopicModel])
async def get_srs_due_topics():
    """Get topics due for spaced repetition review today."""
    try:
        due = db.get_due_topics()
        return [SRSTopicModel(**item) for item in due]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/srs/schedule-topic", response_model=dict[str, Any])
async def schedule_srs_topic(request: SRSScheduleRequestModel):
    """Schedule a topic for spaced repetition review."""
    try:
        review_id = db.schedule_topic_review(request.topic_id, request.interval_days)
        return {
            "status": "scheduled",
            "review_id": review_id,
            "topic_id": request.topic_id,
            "interval_days": request.interval_days,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/srs/mark-reviewed/{topic_id}", response_model=dict[str, Any])
async def mark_srs_reviewed(topic_id: str, success: bool = Query(default=True)):
    """Mark topic as reviewed and reschedule for next interval."""
    try:
        db.mark_topic_reviewed(topic_id, success)
        next_interval = 3 if success else 1
        return {
            "status": "reviewed",
            "topic_id": topic_id,
            "success": success,
            "next_review_in_days": next_interval,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/srs/stats", response_model=dict[str, Any])
async def get_srs_stats():
    """Get SRS system statistics."""
    try:
        conn = db.get_connection()
        try:
            total_topics = conn.execute("SELECT COUNT(DISTINCT topic_id) FROM review_items WHERE item_type = 'topic'").fetchone()[0] or 0
            due_today = conn.execute("SELECT COUNT(*) FROM review_items WHERE item_type = 'topic' AND DATE(due_at) <= DATE('now')").fetchone()[0] or 0
            completed = conn.execute("SELECT COUNT(*) FROM review_items WHERE item_type = 'topic' AND last_result = 'success'").fetchone()[0] or 0
        finally:
            conn.close()
        return {
            "total_topics_in_srs": total_topics,
            "due_today": due_today,
            "completed_reviews": completed,
            "retention_estimate": round(100 * completed / max(total_topics, 1), 1) if total_topics else 0,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/study-paths/generate", response_model=StudyPathModel)
async def generate_study_path_endpoint(weak_topics: list[str] = Query(default=[])):
    """Generate personalized 12-week study path."""
    try:
        exam_date = (datetime.now() + timedelta(days=84)).isoformat()[:10]
        # Generate study path via Gemini
        path_data = gemini_integration.generate_personalized_study_path(weak_topics, exam_date)

        # Persist the EXACT weeks being returned (previously the deterministic
        # fallback weeks were persisted while the Gemini weeks were returned, so
        # /api/study-paths/current showed a different plan than the one generated).
        weeks_data = path_data.get("weeks", [])
        path_id = db.create_study_path(exam_date, weak_topics, weeks=weeks_data)

        weeks = [StudyPathWeekModel(**w) for w in weeks_data]
        return StudyPathModel(
            path_id=path_id,
            exam_date=exam_date,
            weeks=weeks,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/study-paths/current", response_model=StudyPathModel | None)
async def get_active_study_path():
    """Get currently active study path."""
    try:
        path_data = db.get_active_study_path()
        if not path_data:
            return None
        weeks = [StudyPathWeekModel(**w) for w in path_data.get("weeks_json", [])]
        return StudyPathModel(
            path_id=path_data["path_id"],
            exam_date=path_data["exam_date"],
            weeks=weeks,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/study-paths/{path_id}/progress")
async def get_study_path_progress(path_id: str):
    """Get progress tracking for a study path."""
    try:
        conn = db.get_connection()
        try:
            path = conn.execute("SELECT * FROM study_paths WHERE path_id = ?", (path_id,)).fetchone()
            progress = conn.execute("SELECT * FROM study_path_progress WHERE path_id = ? ORDER BY week_number", (path_id,)).fetchall()
        finally:
            conn.close()

        if not path:
            raise HTTPException(status_code=404, detail="Study path not found")

        return {
            "path_id": path_id,
            "exam_date": path["exam_date"],
            "total_weeks": path["milestone_count"],
            "weeks_completed": len([p for p in progress if p["status"] == "completed"]),
            "progress_items": [dict(p) for p in progress],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/study-paths/{path_id}/week/{week}")
async def get_study_path_week(path_id: str, week: int = Path(ge=1, le=12)):
    """Get specific week details from study path."""
    try:
        conn = db.get_connection()
        try:
            path = conn.execute("SELECT weeks_json FROM study_paths WHERE path_id = ?", (path_id,)).fetchone()
        finally:
            conn.close()

        if not path:
            raise HTTPException(status_code=404, detail="Study path not found")

        try:
            weeks_data = json.loads(path["weeks_json"]) if isinstance(path["weeks_json"], str) else path["weeks_json"]
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(status_code=500, detail=f"Corrupted study path data: {str(e)}") from e

        week_data = next((w for w in weeks_data if w["week"] == week), None)

        if not week_data:
            raise HTTPException(status_code=404, detail=f"Week {week} not found")

        return week_data
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/study-paths/{path_id}/week/{week}/mark-complete")
async def mark_week_complete(path_id: str, week: int = Path(ge=1, le=12)):
    """Mark a week of study path as completed."""
    try:
        conn = db.get_connection()
        try:
            progress = conn.execute(
                "SELECT * FROM study_path_progress WHERE path_id = ? AND week_number = ?",
                (path_id, week)
            ).fetchone()

            if progress:
                conn.execute(
                    "UPDATE study_path_progress SET status = 'completed', completed_at = ? WHERE path_id = ? AND week_number = ?",
                    (datetime.now().isoformat(), path_id, week)
                )
            else:
                progress_id = f"PROGRESS_{path_id}_{week}"
                conn.execute(
                    "INSERT INTO study_path_progress (progress_id, path_id, week_number, status, completed_at) VALUES (?, ?, ?, ?, ?)",
                    (progress_id, path_id, week, "completed", datetime.now().isoformat())
                )
            conn.commit()
        finally:
            conn.close()

        return {
            "status": "marked_complete",
            "path_id": path_id,
            "week": week,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn


    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
