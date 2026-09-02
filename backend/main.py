"""FastAPI backend for the source-grounded IFSCA exam prep engine."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import json
import os
from pathlib import Path as PathLib
import re
import threading
import time as _time
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Path, Query, Request
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
import update_tracker
import pyq_parser
import pyq_cache
import smart_material_classification
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
    DescriptiveStartRequestModel,
    DescriptiveGradeRequestModel,
    DescriptiveComponentGradeModel,
    DescriptiveGradeResponseModel,
    ExamAggregateResponseModel,
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


async def _idle_validate_questions() -> None:
    """Plan v6 4.6: verify a batch of unverified questions against their cited facts.

    Runs on the scheduler as an idle job. verify_unverified_questions is quota-aware
    and stops when Gemini is unavailable; wrap so a failure never crashes the scheduler.
    """
    try:
        result = db.verify_unverified_questions(limit=10)
        print(f"[validator] verified={result.get('verified')} rejected={result.get('rejected')} skipped={result.get('skipped')}")
    except Exception as exc:
        print(f"[validator] idle validation error: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    db.init_db()
    job_queue.init_job_queue_schema()

    # Knowledge-layer bootstrap: loads the committed knowledge pack (facts, PYQ
    # banks, descriptive items, exam templates, Act full text) into SQLite.
    # Runtime never reads md/pdf files after this (plan v6, WS-1).
    app.state.knowledge_bootstrap = db.bootstrap_from_knowledge()
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
        misfire_grace_time=300,
    )
    scheduler.add_job(
        job_queue.process_queue,
        CronTrigger(minute="*/15", timezone="UTC"),
        id="job_queue_processor",
        name="Job Queue Processor (every 15 min)",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    # Plan v6 4.6: idle verifier. verify_unverified_questions is quota-aware and
    # stops safely when Gemini is unavailable, so it is safe to schedule.
    scheduler.add_job(
        _idle_validate_questions,
        CronTrigger(minute="*/30", timezone="UTC"),
        id="question_validator",
        name="Question Verifier (every 30 min)",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    # Autonomous agentic update tracker (plan v6, multi-model phase B)
    _tracker_interval_hours = int(os.getenv("UPDATE_TRACK_INTERVAL_HOURS", "6"))
    scheduler.add_job(
        update_tracker.run_update_tracker,
        IntervalTrigger(hours=_tracker_interval_hours, jitter=300),
        id="update_tracker_agent",
        name="Update Tracker Agent",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
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
    snapshot = _cached_targeting_snapshot()
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


# A route that can reach a model call bills an API key, and the generator
# endpoints also write rows, so a double-clicked button or a frontend retry pays
# twice for one result. The guard below claims a key for the duration of the
# work and refuses an overlapping duplicate with 409. Keying on the query string
# keeps genuinely different requests (two topics, two limits) independent; only
# a true duplicate is rejected, so sequential callers never see the 409.
_SPEND_GUARD_LOCK = threading.Lock()
_SPEND_IN_FLIGHT: set[str] = set()


def spend_guard_key(base: str, query: str) -> str:
    return f"{base}|{query}"


def _begin_spend_guard(key: str) -> bool:
    """Claim `key`. False means the same operation is already running."""
    with _SPEND_GUARD_LOCK:
        if key in _SPEND_IN_FLIGHT:
            return False
        _SPEND_IN_FLIGHT.add(key)
        return True


def _end_spend_guard(key: str) -> None:
    with _SPEND_GUARD_LOCK:
        _SPEND_IN_FLIGHT.discard(key)


def gemini_spend_guard(base_key: str):
    """Route dependency that makes a Gemini-spending request idempotent.

    The claim spans the request only. A handler that hands its work to a thread
    returns long before the spend ends, so it must bracket the job with
    _begin_spend_guard/_end_spend_guard itself instead of using this.
    """

    def guard(request: Request):
        key = spend_guard_key(base_key, request.url.query)
        if not _begin_spend_guard(key):
            raise HTTPException(
                status_code=409,
                detail="That AI request is still running. Wait for it to finish before starting another.",
            )
        try:
            yield
        finally:
            _end_spend_guard(key)

    guard.spend_guard_key = base_key
    return guard


@app.get("/")
def root():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"name": "IFSCA Exam Prep Engine", "version": "2.0.0", "docs": "/docs"}


@app.get("/health", response_model=HealthResponseModel)
def health_check():
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
def gemini_health():
    return get_gemini_health()


@app.post("/api/ai/reinitialize", dependencies=[Depends(gemini_spend_guard("ai:reinitialize"))])
def reinitialize_ai():
    return initialize_gemini_runtime(run_probe=True)


@app.get("/api/ai/status")
def ai_status():
    return get_gemini_health()


@app.get("/api/ai/usecases")
def ai_usecases():
    return {
        "prompt_contract_version": PROMPT_CONTRACT_VERSION,
        "usecases": USE_CASE_CATALOG,
        "ai_status": get_gemini_health(),
    }


@app.post("/api/ai/study-session", dependencies=[Depends(gemini_spend_guard("ai:study-session"))])
def ai_study_session(request: StudySessionRequestModel | None = None):
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


@app.get("/api/ai/topic-brief", dependencies=[Depends(gemini_spend_guard("ai:topic-brief"))])
def ai_topic_brief(topic_id: str = Query(..., min_length=1), limit: int = Query(default=10, ge=3, le=25)):
    normalized = topic_id.upper()
    topic_name = db.topic_display(normalized)
    chunks = db.chunks_for_topic(normalized, limit=limit)
    if not chunks:
        chunks = db.search_sources(topic_name, limit=limit)
    brief = generate_topic_source_brief(normalized, topic_name, chunks)
    return {"ai_status": get_gemini_health(), "brief": brief, "sources": chunks}


@app.get("/api/ai/pyq-calibration", dependencies=[Depends(gemini_spend_guard("ai:pyq-calibration"))])
def ai_pyq_calibration(limit: int = Query(default=18, ge=5, le=40)):
    chunks = db.pyq_candidate_chunks(limit=limit)
    calibration = generate_pyq_calibration(chunks, _digest_profile())
    return {"ai_status": get_gemini_health(), "calibration": calibration, "sources": chunks}


@app.get("/api/ai/product-gap-analysis", dependencies=[Depends(gemini_spend_guard("ai:product-gap-analysis"))])
def ai_product_gap_analysis():
    analysis = generate_product_gap_analysis(_digest_profile(), _app_inventory(), _plan_excerpt())
    return {"ai_status": get_gemini_health(), "analysis": analysis}


@app.get("/api/ai/mock-blueprint", dependencies=[Depends(gemini_spend_guard("ai:mock-blueprint"))])
def ai_mock_blueprint(
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
def targeting_snapshot():
    return _cached_targeting_snapshot()


@app.get("/api/intelligence/function-audit")
def function_audit():
    return {
        "generated_at": datetime.now().isoformat(),
        "architecture": "function_based_business_logic",
        "note": "Pydantic BaseModel classes remain only as FastAPI validation schemas; custom service/OOP runtime classes are avoided.",
        "functions": _function_improvement_audit(),
    }


@app.post("/api/admin/ingest-documents", response_model=IngestResponseModel)
def ingest_documents(
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
def ingestion_status():
    return IngestionStatusModel(**db.get_ingestion_status())


@app.get("/api/documents")
def list_documents(limit: int = Query(default=200, ge=1, le=500)):
    return {"documents": db.list_documents(limit=limit)}


@app.get("/api/topics", response_model=list[TopicModel])
def list_topics():
    return [TopicModel.model_validate(topic) for topic in db.list_topics()]


@app.get("/api/topics/{topic_id}/sources", response_model=SourceSearchResponseModel)
def topic_sources(topic_id: str, limit: int = Query(default=10, ge=1, le=50)):
    results = db.chunks_for_topic(topic_id.upper(), limit=limit)
    return SourceSearchResponseModel(query=db.topic_display(topic_id.upper()), topic_id=topic_id.upper(), total=len(results), results=results)


@app.get("/api/source-search", response_model=SourceSearchResponseModel)
def source_search(
    q: str = Query(..., min_length=1),
    topic_id: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
):
    topic = topic_id.upper() if topic_id else None
    results = db.search_sources(q, topic_id=topic, limit=limit)
    return SourceSearchResponseModel(query=q, topic_id=topic, total=len(results), results=results)


@app.post("/api/upload-mock")
def upload_mock(mock_data: MockUploadModel, background_tasks: BackgroundTasks):
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
def weak_topics():
    topics = [TopicStatsModel.model_validate(topic) for topic in db.get_weak_topics(threshold=60.0)]
    return WeakTopicsResponseModel(
        weak_topics=topics,
        penalty_drill_needed=bool(topics),
        recommended_topic=topics[0].topic if topics else None,
    )


@app.get("/api/topics/weak")
def get_weak_topics_by_user(user_id: str = Query(default="default")):
    """Get weak topics for a user (topics with accuracy < 60%).

    Per Context7 docs for SQLite: Use aggregate functions for accuracy calculation.
    """
    try:
        topics = db.get_weak_topics(threshold=60.0)
        return [
            {
                "topic": t.get("topic"),
                "topic_name": db.TOPIC_BY_ID.get(t.get("topic"), {}).get("display_name"),
                # "UNKNOWN" means never sat, not sat-and-failed; without it the
                # tracker paints both as a red critical 0%.
                "status": t.get("status"),
                "accuracy": t.get("accuracy_pct"),
                "attempts": t.get("total_seen"),
            }
            for t in topics
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/topics/stats")
def get_topic_stats_by_user(
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


# Plan v6 6.7: TTL cache for the expensive dashboard_data() / targeting snapshot.
# dashboard_data() runs intelligent_targeting_snapshot() on every call; caching it
# for 60s removes that churn. A shallow copy is returned so the endpoint's in-place
# additions (focus_plan, amendment_watchlist) do not mutate the cached dict.
_DASHBOARD_CACHE: dict[str, Any] = {"data": None, "ts": 0.0}
_DASHBOARD_TTL_SECONDS = 60.0
_TARGETING_CACHE: dict[str, Any] = {"data": None, "ts": 0.0}
_DASHBOARD_FULL_CACHE: dict[str, Any] = {"ai": {"data": None, "ts": 0.0}, "local": {"data": None, "ts": 0.0}}
_DASHBOARD_WARMING: set[str] = set()
_DASHBOARD_WARM_LOCK = threading.Lock()



def _cached_dashboard_data() -> dict[str, Any]:
    now = _time.time()
    if _DASHBOARD_CACHE["data"] is None or (now - _DASHBOARD_CACHE["ts"]) > _DASHBOARD_TTL_SECONDS:
        _DASHBOARD_CACHE["data"] = db.dashboard_data()
        _DASHBOARD_CACHE["ts"] = now
    return dict(_DASHBOARD_CACHE["data"])


def _build_dashboard_enrichment(include_ai: bool) -> dict[str, Any]:
    """Compose one fully enriched dashboard payload (blocking; Gemini if allowed)."""
    data = _cached_dashboard_data()
    weak = data.get("weak_topics", [])
    amendments_data = data.get("recent_amendments", [])
    data["focus_plan"] = generate_focus_plan(data, weak, amendments_data, force_local=not include_ai)
    data["amendment_watchlist"] = generate_amendment_watchlist(
        db.startup_amendment_radar_chunks(limit=30) if include_ai else db.amendment_candidate_chunks(limit=12),
        force_local=not include_ai,
        operation="dashboard_live_amendment_watchlist",
    )
    data["ai_status"] = get_gemini_health()
    return data


def _warm_dashboard_ai(mode: str, include_ai: bool) -> None:
    """Refresh the AI-enriched dashboard in the background (never blocks requests)."""
    with _DASHBOARD_WARM_LOCK:
        if mode in _DASHBOARD_WARMING:
            return
        _DASHBOARD_WARMING.add(mode)

    def _work() -> None:
        try:
            enriched = _build_dashboard_enrichment(include_ai)
            slot = _DASHBOARD_FULL_CACHE[mode]
            slot["data"] = enriched
            slot["ts"] = _time.time()
        except Exception as exc:
            print(f"[dashboard] background AI warm failed: {exc}")
        finally:
            with _DASHBOARD_WARM_LOCK:
                _DASHBOARD_WARMING.discard(mode)

    threading.Thread(target=_work, daemon=True).start()


def _cached_targeting_snapshot() -> dict[str, Any]:
    now = _time.time()
    if _TARGETING_CACHE["data"] is None or (now - _TARGETING_CACHE["ts"]) > _DASHBOARD_TTL_SECONDS:
        _TARGETING_CACHE["data"] = db.intelligent_targeting_snapshot()
        _TARGETING_CACHE["ts"] = now
    return dict(_TARGETING_CACHE["data"])


@app.get("/api/dashboard", response_model=DashboardStatsModel)
def dashboard(include_ai: bool = Query(default=True)):
    # Plan v6 6.7 + V6.9: the dashboard must stay fast (<0.5s) even with live
    # Gemini. Fresh cache serves at once; stale cache serves while refreshing in
    # the background; a cold AI cache returns fast local enrichment immediately
    # and warms the Gemini version in the background for subsequent loads.
    mode = "ai" if include_ai else "local"
    slot = _DASHBOARD_FULL_CACHE[mode]
    now = _time.time()
    if slot["data"] is not None and (now - slot["ts"]) <= _DASHBOARD_TTL_SECONDS:
        return DashboardStatsModel.model_validate(dict(slot["data"]))

    if not include_ai:
        data = _build_dashboard_enrichment(False)
        slot["data"] = dict(data)
        slot["ts"] = _time.time()
        return DashboardStatsModel.model_validate(data)

    if slot["data"] is not None:
        # Stale-while-revalidate: serve the last enriched payload, refresh async.
        _warm_dashboard_ai(mode, True)
        return DashboardStatsModel.model_validate(dict(slot["data"]))

    # Cold AI cache: serve a fast local enrichment now; warm Gemini in background.
    data = _build_dashboard_enrichment(False)
    _warm_dashboard_ai(mode, True)
    return DashboardStatsModel.model_validate(data)


@app.get("/api/dashboard/next-action")
def get_next_action(user_id: str = Query(default="default")):
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
def get_readiness(
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
def ifsca_act():
    return db.ifsca_act_full_text()


@app.get("/api/law/daily-revision", response_model=LawRevisionModel)
def get_daily_law_revision(
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


@app.get("/api/law/daily-revision/progress")
def get_law_revision_progress():
    """Completion-driven Act revision progress (plan v6 6.5)."""
    return db.get_law_revision_progress()


@app.post("/api/law/daily-revision/complete-day")
def complete_law_revision_day(
    day_index: int | None = Query(default=None, ge=0),
    lines_per_day: int = Query(default=80, ge=30, le=180),
):
    """Mark today's Act slice completed; the resume day index then advances."""
    return law_revision_engine.complete_law_revision_day(day_index=day_index, lines_per_day=lines_per_day)


@app.post("/api/questions/generate-from-source", dependencies=[Depends(gemini_spend_guard("questions:generate-from-source"))])
def generate_questions_from_source(request: QuestionGenerationRequestModel):
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


@app.post("/api/questions/build-bank", dependencies=[Depends(gemini_spend_guard("questions:build-bank"))])
def build_question_bank(
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
def quarantine_low_quality_questions(min_quality: float = Query(default=0.48, ge=0.0, le=1.0)):
    result = db.quarantine_low_quality_questions(min_quality=min_quality)
    app.state.question_quarantine = result
    return result


# Must stay registered BEFORE "/api/questions/{question_id}": Starlette matches
# routes in registration order, so a later literal /search would be captured as
# question_id="search" and answer 404 "Question not found".
@app.get("/api/questions/search", response_model=SourceSearchResponseModel)
def search_questions(
    query: str,
    topic_id: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
):
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


@app.get("/api/questions/{question_id}", response_model=QuestionModel)
def get_question(question_id: str):
    question = db.get_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return QuestionModel.model_validate(question)


@app.post("/api/penalty-drill", response_model=PenaltyDrillResponseModel, dependencies=[Depends(gemini_spend_guard("penalty-drill"))])
def generate_penalty_drill(request: PenaltyDrillRequestModel):
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


@app.get("/api/drills/wrong-queue")
def wrong_answer_queue(
    topic: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Plan v6 7.7: recent wrong answers feeding the replay drill UI."""
    conn = db.get_connection()
    try:
        # LEFT JOIN, not INNER: question_attempts.question_id is nullable and a
        # replayed drill can reference a question that is no longer in the bank.
        # An inner join would silently drop those rows from the queue.
        sql = """
            SELECT qa.question_id, qa.topic, qa.question_text, qa.correct_option,
                   qa.your_option, qa.attempt_date, q.source AS source_document
            FROM question_attempts qa
            LEFT JOIN questions q ON q.question_id = qa.question_id
            WHERE qa.is_correct = 0
        """
        params: list[Any] = []
        if topic:
            sql += " AND qa.topic = ?"
            params.append(topic.upper())
        sql += " ORDER BY qa.created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return {"wrong_answers": [dict(row) for row in rows]}
    finally:
        conn.close()


@app.post("/api/drills/replay", dependencies=[Depends(gemini_spend_guard("drills:replay"))])
def replay_wrong_answers(
    topic: str = Query(..., min_length=1),
    question_count: int = Query(default=5, ge=1, le=20),
):
    """Plan v6 6.8: wrong-answer replay drill (completes the REPLAY_WRONG loop).

    Finds the user's recently missed questions for a topic and regenerates similar
    practice questions grounded in the same source chunks, so the candidate retries
    the exact concepts they got wrong.
    """
    topic_id = topic.upper()
    conn = db.get_connection()
    try:
        wrong_rows = conn.execute(
            """
            SELECT DISTINCT qa.question_id, qc.chunk_id, qc.document_id, q.topic_id
            FROM question_attempts qa
            LEFT JOIN question_citations qc ON qc.question_id = qa.question_id
            LEFT JOIN questions q ON q.question_id = qa.question_id
            WHERE qa.topic = ? AND qa.is_correct = 0
            ORDER BY qa.created_at DESC
            LIMIT ?
            """,
            (topic_id, question_count),
        ).fetchall()
    finally:
        conn.close()

    if not wrong_rows:
        return {
            "status": "no_wrong_answers",
            "topic": topic_id,
            "message": "No wrong answers recorded for this topic yet. Take a mock or drill first.",
            "questions": [],
        }

    # Build source queries from the missed questions' source chunks / topics.
    query_terms = []
    for row in wrong_rows:
        if row["chunk_id"]:
            query_terms.append(str(row["chunk_id"]))
    query = " ".join(query_terms[:5]) or topic_display(topic_id)

    questions = db.generate_topic_questions(
        topic_id,
        question_count,
        difficulty="medium",
        query=query,
        question_type="replay_wrong",
        use_gemini=True,
        strict_gemini=False,
        allow_local_fallback=True,
        reuse_existing=False,
        source_policy="exam_material",
    )

    return {
        "status": "ok",
        "topic": topic_id,
        "replayed_from_wrong": len(wrong_rows),
        "questions": [_coerce_question(question) for question in questions],
        "source_grounded": any(question.get("source_chunk_id") for question in questions),
    }


@app.post("/api/generate-smart-mock", response_model=SmartMockResponseModel, dependencies=[Depends(gemini_spend_guard("mock:generate"))])
def generate_smart_mock(request: SmartMockRequestModel | None = None):
    request = request or SmartMockRequestModel()
    try:
        if not request.use_gemini:
            raise HTTPException(status_code=400, detail="Gemini is mandatory for every mock; local generation is disabled.")
        result = db.generate_smart_mock(
            total_questions=request.total_questions,
            mode=request.mode,
            use_gemini=True,
            template_id=request.template,
        )
        questions = [_coerce_question(question) for question in result["questions"]]
        gemini_questions = sum(1 for question in result["questions"] if question.get("created_by") == "gemini" or str(question.get("question_id", "")).startswith("Q_AI_"))
        local_questions = len(result["questions"]) - gemini_questions
        marks_per_question = round(result.get("marks_per_question") or (100 / max(1, len(questions))), 4)
        time_limit = result.get("time_limit_minutes") or 60
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
            time_limit_minutes=time_limit,
            marks_per_question=marks_per_question,
            negative_marking_per_wrong=round(marks_per_question * 0.25, 4),
            exam_rules={
                "timer": f"{time_limit} minutes",
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


@app.post("/api/mocks/generate", response_model=SmartMockResponseModel, dependencies=[Depends(gemini_spend_guard("mock:generate"))])
def generate_mock_alias(request: SmartMockRequestModel | None = None):
    return generate_smart_mock(request)


@app.post("/api/mocks/{mock_id}/submit", response_model=MockSubmitResponseModel)
def submit_mock(mock_id: str, request: MockSubmitRequestModel):
    try:
        result = db.submit_mock(mock_id, [answer.model_dump() for answer in request.answers])
        return MockSubmitResponseModel.model_validate(result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/exams/start", dependencies=[Depends(gemini_spend_guard("exams:start"))])
def exam_start(request: SmartMockRequestModel | None = None):
    """Start a new exam session with adaptive mock generation.

    Per PROJECT_REFACTOR_PLAN.xml Phase 3: Return 50 questions with:
    - Standard fields (question_text, options, difficulty)
    - expected_time_sec: Time user should spend (~3 min default)
    - negative_marking: Penalty for wrong answer (-1 points)
    """
    try:
        request = request or SmartMockRequestModel()
        result = db.generate_smart_mock(
            total_questions=request.total_questions,
            mode=request.mode,
            use_gemini=True,
        )

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
def exam_time_remaining(exam_id: str):
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
def exam_submit(exam_id: str, request: MockSubmitRequestModel):
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
        topic_breakdown = [
            {
                "topic": item["topic"],
                "accuracy_pct": item["accuracy_pct"],
                "correct": item["total_correct"],
                "total": item["total_seen"],
            }
            for item in result.get("topic_breakdown", [])
        ]
        weak_areas = [row for row in topic_breakdown if row["accuracy_pct"] < 60]
        return {
            "exam_id": exam_id,
            "mock_id": mock_id,
            "status": "submitted",
            "code": 200,
            "final_score": result["final_score"],
            "max_score": result["max_score"],
            "raw_score": result["raw_score"],
            "negative_marks": result["negative_marks"],
            "total_questions": result["total_questions"],
            "total_correct": result["total_correct"],
            "total_wrong": result["total_wrong"],
            "total_unanswered": result["total_unanswered"],
            "accuracy_pct": result["accuracy_pct"],
            "topic_breakdown": topic_breakdown,
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
def list_pyq_papers():
    """List available previous year papers from the compiled bank store."""
    try:
        conn = db.get_connection()
        try:
            rows = conn.execute(
                """
                SELECT exam, year, phase, paper,
                       COUNT(*) AS question_count,
                       SUM(CASE WHEN incomplete = 1 THEN 1 ELSE 0 END) AS incomplete_count
                FROM previous_year_questions
                GROUP BY exam, year, phase, paper
                ORDER BY exam, year, phase, paper
                """
            ).fetchall()

            papers = []
            for row in rows:
                doc_id = f"{row['exam']}_{row['year']}_P{row['phase']}_PAPER{row['paper']}"
                papers.append({
                    "pyq_doc_id": doc_id,
                    "title": f"{row['exam']} Grade A {row['year']} - Phase {row['phase']} Paper {row['paper']}",
                    "exam": row["exam"],
                    "year": row["year"],
                    "phase": row["phase"],
                    "paper": row["paper"],
                    "question_count": row["question_count"],
                    "incomplete_count": row["incomplete_count"],
                })

            # /api/pyq/drill requires a subject_id but nothing published the valid
            # values, so a client could only reach it by hardcoding the enum.
            # Complete rows only -- that is what the drill serves, so advertising a
            # subject whose questions are all incomplete would offer a picker entry
            # that 404s. NULL/empty subject_id is excluded because the drill filters
            # with `subject_id = ?`, which can never match NULL; /api/pyq/sitting is
            # the route to those rows.
            subject_rows = conn.execute(
                """
                SELECT subject_id, COUNT(*) AS question_count
                FROM previous_year_questions
                WHERE incomplete = 0 AND COALESCE(subject_id, '') <> ''
                GROUP BY subject_id
                ORDER BY question_count DESC, subject_id
                """
            ).fetchall()
            subjects = [
                {
                    "subject_id": row["subject_id"],
                    "question_count": row["question_count"],
                }
                for row in subject_rows
            ]

            return {"status": "ok", "papers": papers, "subjects": subjects}
        finally:
            conn.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _parse_pyq_doc_id(doc_id: str) -> dict[str, Any] | None:
    """Parse '{EXAM}_{year}_P{phase}_PAPER{paper}' into components."""
    match = re.match(r"^(IFSCA|SEBI)_(\d{4})_P(\d+)_PAPER(\d+)$", doc_id)
    if not match:
        return None
    return {
        "exam": match.group(1),
        "year": int(match.group(2)),
        "phase": int(match.group(3)),
        "paper": int(match.group(4)),
    }


def _load_bank_questions(doc: dict[str, Any], conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    """Fetch complete bank questions for a paper, ordered by section then number."""
    rows = conn.execute(
        """
        SELECT * FROM previous_year_questions
        WHERE exam = ? AND year = ? AND phase = ? AND paper = ? AND incomplete = 0
        ORDER BY COALESCE(section, subject_id, ''), question_number, rowid
        LIMIT ?
        """,
        (doc["exam"], doc["year"], doc["phase"], doc["paper"], limit),
    ).fetchall()
    return [dict(row) for row in rows]


def _format_bank_session(doc: dict[str, Any], rows: list[dict[str, Any]], title: str) -> dict[str, Any]:
    """Build a blind attempt session from bank rows and cache the answers."""
    pyq_id = f"PYQ_DOC{doc['exam']}_{doc['year']}_P{doc['phase']}_PAPER{doc['paper']}"

    parsed = []
    for index, row in enumerate(rows, start=1):
        options = {
            letter: row[f"option_{letter.lower()}"]
            for letter in "ABCDE"
            if row.get(f"option_{letter.lower()}")
        }
        parsed.append(
            pyq_parser.ParsedQuestion(
                question_number=index,
                question_text=row["question_text"],
                options=options,
                correct_answer=row["correct_option"] or "A",
                direction_text=row.get("direction_text"),
            )
        )
    marks = rows[0].get("marks") if rows else 1
    negative = round((marks or 1) * 0.25, 4)
    pyq_cache.cache_pyq_questions(
        pyq_id,
        parsed,
        marks_per_question=marks,
        negative_marking_per_wrong=negative,
        title=title,
    )

    formatted_questions = []
    for pq in parsed:
        formatted_questions.append({
            "question_id": f"{pyq_id}_Q{pq.question_number}",
            "question_number": pq.question_number,
            "question_text": pq.question_text,
            "direction_text": pq.direction_text,
            "options": [{"label": label, "text": text} for label, text in pq.options.items()],
            # Correct answer NOT sent to frontend (blind submission)
        })

    return {
        "status": "ok",
        "pyq_id": pyq_id,
        "title": title,
        "exam": doc["exam"],
        "total_questions": len(formatted_questions),
        "time_limit_minutes": max(20, len(formatted_questions)),
        "marks_per_question": marks,
        "negative_marking_per_wrong": negative,
        "questions": formatted_questions,
    }


@app.post("/api/pyq/{doc_id}/load")
def load_pyq_paper(doc_id: str):
    """Load a previous year paper from the compiled bank (blind, capped at 50)."""
    conn = None
    try:
        doc = _parse_pyq_doc_id(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="PYQ paper not found")

        conn = db.get_connection()
        rows = _load_bank_questions(doc, conn, limit=50)
        if not rows:
            raise HTTPException(status_code=400, detail="No complete questions available for this PYQ paper")

        title = f"{doc['exam']} Grade A {doc['year']} - Phase {doc['phase']} Paper {doc['paper']}"
        return _format_bank_session(doc, rows, title)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error loading PYQ paper: {str(exc)}") from exc
    finally:
        if conn:
            conn.close()


@app.get("/api/pyq/drill")
def pyq_subject_drill(
    subject_id: str = Query(..., min_length=1),
    exam: str | None = Query(default=None, pattern="^(IFSCA|SEBI)$"),
    limit: int = Query(default=20, ge=5, le=50),
):
    """Cross-exam drill: random complete bank questions for one subject."""
    conn = None
    try:
        conn = db.get_connection()
        if exam:
            rows = conn.execute(
                """
                SELECT * FROM previous_year_questions
                WHERE subject_id = ? AND exam = ? AND incomplete = 0
                ORDER BY RANDOM() LIMIT ?
                """,
                (subject_id, exam, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM previous_year_questions
                WHERE subject_id = ? AND incomplete = 0
                ORDER BY RANDOM() LIMIT ?
                """,
                (subject_id, limit),
            ).fetchall()
        rows = [dict(row) for row in rows]
        if not rows:
            raise HTTPException(status_code=404, detail=f"No bank questions for subject {subject_id}")

        # The cache key must be a function of the REQUEST, not of the rows drawn.
        # This query is ORDER BY RANDOM(), so keying off rows[0] gave one
        # subject's drill the same pyq_id as another's whenever their first
        # random rows shared (exam, phase, paper) -- observed live as
        # PYQ_DOCSEBI_0_P1_PAPER1. The second drill overwrote the first's cached
        # answers, and because _format_bank_session renumbers from 1 the
        # question_ids matched too, so submitting the attempt already in flight
        # graded it against the other subject's key. /api/pyq/sitting keeps its
        # own SITTING namespace for exactly this reason.
        doc = {
            "exam": f"DRILL_{subject_id}" + (f"_{exam}" if exam else ""),
            "year": 0,
            "phase": 0,
            "paper": 0,
        }
        title = f"{exam or 'IFSCA+SEBI'} drill - {subject_id}"
        session = _format_bank_session(doc, rows, title)
        # doc["exam"] is a cache-key fragment; publish a real exam label instead.
        session["exam"] = exam or "MIXED"
        session["time_limit_minutes"] = max(10, len(rows))
        return session

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error building drill: {str(exc)}") from exc
    finally:
        if conn:
            conn.close()


@app.get("/api/pyq/sitting")
def pyq_sitting_drill(
    year: int = Query(..., ge=2000, le=2100),
    phase: int = Query(..., ge=1, le=4),
    exam: str | None = Query(default=None, pattern="^(IFSCA|SEBI)$"),
    paper: int | None = Query(default=None, ge=1, le=9),
    limit: int = Query(default=50, ge=5, le=100),
):
    """Whole-sitting drill: every bank question from one year and phase.

    A sitting is not a paper. 2024 Phase 1 spans two exams and two papers (280
    bank rows), but /api/pyq/{doc_id}/load only ever serves one
    (exam, year, phase, paper) tuple, and /api/pyq/drill filters on subject_id
    -- NULL on 109 real rows, which it therefore cannot reach at all.
    """
    conn = None
    try:
        conn = db.get_connection()
        rows = smart_material_classification.get_pyq_by_year_phase(
            year, phase, exam=exam, paper=paper, limit=limit, conn=conn
        )
        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"No bank questions for {year} Phase {phase}",
            )

        exams = {row.get("exam") for row in rows if row.get("exam")}
        exam_label = next(iter(exams)) if len(exams) == 1 else "MIXED"

        # "SITTING" keeps this session out of the PYQ_DOC{EXAM}_..._PAPER{n} key
        # space that /api/pyq/{doc_id}/load owns. The two order rows differently,
        # so sharing a key would let a sitting narrowed to one paper overwrite
        # the cached answers of an attempt already in flight and misgrade it.
        doc = {"exam": "SITTING", "year": year, "phase": phase, "paper": 0}
        title = f"{exam_label} Grade A {year} - Phase {phase} sitting"
        session = _format_bank_session(doc, rows, title)
        session["exam"] = exam_label
        return session

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error building sitting: {str(exc)}") from exc
    finally:
        if conn:
            conn.close()


@app.post("/api/admin/ingest-pyq-bank")
def ingest_pyq_bank(force: bool = Query(default=False)):
    """Re-seed the compiled knowledge pack (facts, banks, templates) into SQLite.

    Reads only the committed backend/knowledge pack - never md/pdf files.
    """
    try:
        result = db.bootstrap_from_knowledge(force=force)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/pyq/{pyq_id}/submit")
def submit_pyq_attempt(pyq_id: str, request: MockSubmitRequestModel):
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
            # The title the handler minted when it built this session is the only
            # readable name for it. It used to be looked up in documents, but
            # documents.document_id holds ids like 'doc_ifsca_act_2019' -- a
            # different namespace from PYQ ids like 'IFSCA_2024_P2_PAPER2' -- so
            # that query never matched and pyq_title silently stored the cache
            # key, which /api/pyq/analytics then published as the display name.
            pyq_title = pyq_cache.get_pyq_title(pyq_id) or pyq_id
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

            # Plan v6 2.3: score with the session's real marking scheme
            # (marks x correct, 1/4 x marks per wrong). Fall back to the
            # common 2-mark paper with 0.5 negative; never the legacy 0.67.
            marking = pyq_cache.get_pyq_marking(pyq_id) or {}
            marks_each = marking.get("marks_per_question") or 2
            neg_each = marking.get("negative_marking_per_wrong")
            if neg_each is None:
                neg_each = round(marks_each * 0.25, 4)
            raw_score = round(total_correct * marks_each, 2)
            negative_marks = round(total_wrong * neg_each, 2)
            final_score = round(max(0.0, raw_score - negative_marks), 2)
            total_unanswered = max(0, total_questions - total_answered)
            accuracy = round((total_correct / total_questions * 100), 2) if total_questions > 0 else 0.0
            # The paper's ceiling is marks x questions, not the question count:
            # bank marks are 1, 1.25 or 2, so a client that divides final_score
            # by len(questions) reports "4 / 3" on a 2-mark paper.
            max_score = round(total_questions * marks_each, 2)

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
                "max_score": max_score,
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


@app.get("/api/pyq/{pyq_id}/answers")
def pyq_attempt_answers(pyq_id: str):
    """Plan v6 7.4: post-attempt model-answer reveal from persisted attempt rows."""
    conn = db.get_connection()
    try:
        rows = conn.execute(
            """
            SELECT question_number, selected_answer, official_answer, is_correct, time_spent_seconds
            FROM pyq_question_attempts
            WHERE pyq_id = ?
            ORDER BY question_number
            """,
            (pyq_id,),
        ).fetchall()
        return {"pyq_id": pyq_id, "answers": [dict(row) for row in rows]}
    finally:
        conn.close()


@app.get("/api/pyq/analytics")
def get_pyq_analytics():
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
def list_materials():
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
def update_material_role(doc_id: str, request: dict):
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
def material_grounding_analysis():
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
def essay_prompts():
    return [EssayPromptModel.model_validate(prompt) for prompt in db.essay_prompts()]


@app.post("/api/grade-essay", response_model=EssayGradingResponseModel)
def grade_essay_endpoint(submission: EssaySubmissionModel):
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
def essay_history(limit: int = Query(default=25, ge=1, le=100)):
    return {"essays": db.list_essays(limit=limit)}


# ============================================================================
# PHASE 5: Descriptive lab (Paper 1) endpoints
# ============================================================================

def _descriptive_items_for(exam: str, year: int | None = None) -> list[dict[str, Any]]:
    conn = db.get_connection()
    try:
        if year:
            rows = conn.execute(
                "SELECT * FROM descriptive_items WHERE exam = ? AND year = ? ORDER BY item_type, year",
                (exam, year),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM descriptive_items WHERE exam = ? ORDER BY year DESC, item_type",
                (exam,),
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _pick_complete_year_set(items: list[dict[str, Any]], year: int | None) -> tuple[int | None, list[dict[str, Any]]]:
    """Select one year's items, preferring the set with the most gradable components.

    A component is gradable when it has a model answer (essay/précis) or sub-question
    model answers (RC). This prefers a fully-gradable sitting (e.g. IFSCA 2023, where
    the essay has a model answer) over a newer but partially-gradable year.
    """
    if year:
        return year, [i for i in items if i.get("year") == year]

    def gradable(item: dict[str, Any]) -> bool:
        if item.get("item_type") == "RC":
            return (item.get("sub_questions_json") or "") not in ("", "[]")
        return bool(item.get("model_answer"))

    years = sorted({i.get("year") for i in items if i.get("year")}, reverse=True)
    best_year = None
    best_count = -1
    for candidate in years:
        subset = [i for i in items if i.get("year") == candidate]
        count = sum(1 for i in subset if gradable(i))
        if count > best_count:
            best_count = count
            best_year = candidate
    if best_year is None:
        return (years[0] if years else None), items
    return best_year, [i for i in items if i.get("year") == best_year]


@app.post("/api/descriptive/start")
def descriptive_start(request: DescriptiveStartRequestModel):
    """Return blind descriptive items (essay + précis + RC) for a Paper-1 sitting."""
    items = _descriptive_items_for(request.exam, request.year)
    if not items:
        raise HTTPException(status_code=404, detail=f"No descriptive items for {request.exam}")

    selected_year, subset = _pick_complete_year_set(items, request.year)
    by_type: dict[str, dict[str, Any]] = {}
    for item in subset:
        by_type.setdefault(item["item_type"], item)

    # Blind: never ship model answers to the client.
    def blind(item: dict[str, Any] | None) -> dict[str, Any] | None:
        if not item:
            return None
        sub_questions = []
        try:
            for sq in json.loads(item.get("sub_questions_json") or "[]"):
                sub_questions.append({"qnum": sq.get("qnum"), "question": sq.get("question")})
        except (json.JSONDecodeError, TypeError):
            sub_questions = []
        topics = []
        try:
            topics = json.loads(item.get("topics_json") or "[]")
        except (json.JSONDecodeError, TypeError):
            topics = []
        return {
            "item_id": item.get("item_id"),
            "item_type": item.get("item_type"),
            "prompt_text": item.get("prompt_text"),
            "passage_text": item.get("passage_text") or "",
            "topics": topics,
            "sub_questions": sub_questions,
            "marks": item.get("marks"),
            "word_limit_min": item.get("word_limit_min"),
            "word_limit_max": item.get("word_limit_max"),
            "title_required": bool(item.get("title_required")),
            "gradable": bool(item.get("model_answer") or sub_questions),
        }

    cutoff = 30.0
    return {
        "exam": request.exam,
        "year": selected_year,
        "time_limit_minutes": 60,
        "cutoff_pct": cutoff,
        "components": {
            "essay": blind(by_type.get("ESSAY")),
            "precis": blind(by_type.get("PRECIS")),
            "rc": blind(by_type.get("RC")),
        },
    }


@app.post("/api/descriptive/grade", response_model=DescriptiveGradeResponseModel, dependencies=[Depends(gemini_spend_guard("descriptive:grade"))])
def descriptive_grade(request: DescriptiveGradeRequestModel):
    """Grade essay + précis + RC against stored model answers (blind grading)."""
    from precis_grader import grade_precis
    from rc_grader import grade_rc

    items = _descriptive_items_for(request.exam, request.year)
    if not items:
        raise HTTPException(status_code=404, detail=f"No descriptive items for {request.exam}")
    selected_year, subset = _pick_complete_year_set(items, request.year)
    by_type: dict[str, dict[str, Any]] = {}
    for item in subset:
        by_type.setdefault(item["item_type"], item)

    components: list[DescriptiveComponentGradeModel] = []

    # Essay (reuse the existing 4-rubric essay grader, scaled to 30 marks).
    essay_item = by_type.get("ESSAY")
    if request.essay_text.strip():
        essay_grade = essay_grader.grade_essay_with_sources(
            request.essay_text,
            (essay_item or {}).get("subject_id") or "PH2_ESSAY",
            [],
            force_local=False,
        )
        # 4 rubrics x 25 = 100; scale to the essay's marks (30).
        essay_marks = (essay_item or {}).get("marks") or 30
        scaled = round(essay_grade.total_score / 100.0 * essay_marks, 2)
        components.append(DescriptiveComponentGradeModel(
            component="essay",
            score=scaled,
            max_marks=float(essay_marks),
            feedback=essay_grade.overall_feedback,
            ai_model=essay_grade.ai_model,
        ))

    # Précis.
    precis_item = by_type.get("PRECIS")
    if request.precis_text.strip() and precis_item:
        p = grade_precis(
            request.precis_text,
            precis_item.get("passage_text") or "",
            precis_item.get("model_answer") or "",
            precis_item.get("word_limit_min") or 120,
            precis_item.get("word_limit_max") or 130,
            title_required=bool(precis_item.get("title_required")),
            max_marks=precis_item.get("marks") or 35,
        )
        components.append(DescriptiveComponentGradeModel(
            component="precis",
            score=p["score"],
            max_marks=float(p["max_marks"]),
            feedback=p["feedback"],
            ai_model=p["ai_model"],
        ))

    # Reading comprehension.
    rc_item = by_type.get("RC")
    if request.rc_answers and rc_item:
        sub_questions = []
        try:
            sub_questions = json.loads(rc_item.get("sub_questions_json") or "[]")
        except (json.JSONDecodeError, TypeError):
            sub_questions = []
        questions = [sq.get("question", "") for sq in sub_questions]
        model_answers = [sq.get("model_answer", "") for sq in sub_questions]
        rc = grade_rc(
            request.rc_answers,
            questions,
            model_answers,
            rc_item.get("passage_text") or "",
            max_marks=rc_item.get("marks") or 35,
        )
        components.append(DescriptiveComponentGradeModel(
            component="rc",
            score=rc["score"],
            max_marks=float(rc["max_marks"]),
            feedback=rc.get("overall_feedback", ""),
            ai_model=rc.get("ai_model"),
        ))

    total_score = round(sum(c.score for c in components), 2)
    total_max = round(sum(c.max_marks for c in components), 2) or 100.0
    cutoff_pct = 30.0
    cleared = total_score >= (cutoff_pct / 100.0 * total_max)

    # Plan v6 6.2: persist the sitting so readiness can map Paper-1 performance.
    try:
        db.record_descriptive_score(
            exam=request.exam,
            year=selected_year,
            components=[c.model_dump() for c in components],
            total_score=total_score,
            total_max_marks=total_max,
            cutoff_pct=cutoff_pct,
            cleared_cutoff=cleared,
            ai_status=get_gemini_health(),
        )
    except Exception as exc:
        print(f"[descriptive] score persistence failed: {exc}")

    return DescriptiveGradeResponseModel(
        exam=request.exam,
        year=selected_year,
        components=components,
        total_score=total_score,
        total_max_marks=total_max,
        cutoff_pct=cutoff_pct,
        cleared_cutoff=cleared,
        ai_status=get_gemini_health(),
    )


@app.get("/api/descriptive/history")
def descriptive_history(limit: int = Query(default=25, ge=1, le=100)):
    """Return descriptive items (prompt catalogue) for review."""
    return {
        "IFSCA": _descriptive_items_for("IFSCA")[:limit],
        "SEBI": _descriptive_items_for("SEBI")[:limit],
    }


@app.get("/api/descriptive/scores")
def descriptive_scores(
    exam: str | None = Query(default=None, pattern="^(IFSCA|SEBI)$"),
    limit: int = Query(default=25, ge=1, le=100),
):
    """Plan v6 7.3: graded descriptive sittings (feed aggregate panels)."""
    rows = db.list_descriptive_scores(exam=exam, limit=limit)
    for row in rows:
        for field in ("components_json", "ai_status_json"):
            if isinstance(row.get(field), str):
                try:
                    row[field] = json.loads(row[field]) if row[field] else None
                except json.JSONDecodeError:
                    row[field] = None
    return {"scores": rows}


@app.get("/api/exams/{exam_id}/aggregate", response_model=ExamAggregateResponseModel)
def exam_aggregate(
    exam_id: str,
    exam: str = Query(default="IFSCA", pattern="^(IFSCA|SEBI)$"),
    paper1_score: float = Query(..., ge=0, le=100),
    paper2_score: float = Query(..., ge=0, le=100),
):
    """Compute Phase-II aggregate with Paper-2 gating.

    Paper 1 is counted ONLY if Paper 2 clears its cut-off (IFSCA 40%, SEBI 40%).
    Aggregate = Paper1 x 1/3 + Paper2 x 2/3. Aggregate cut-off: IFSCA 40%, SEBI 50%.
    """
    paper2_cutoff = 40.0
    aggregate_cutoff = 50.0 if exam == "SEBI" else 40.0

    paper2_cleared = paper2_score >= paper2_cutoff
    paper1_counted = paper2_cleared  # gating: Paper 1 counts only if Paper 2 cleared

    if paper1_counted:
        aggregate = round(paper1_score * (1.0 / 3.0) + paper2_score * (2.0 / 3.0), 2)
    else:
        aggregate = 0.0  # Paper 1 not evaluated/counted because Paper 2 failed

    return ExamAggregateResponseModel(
        exam=exam,
        paper1_score=paper1_score,
        paper2_score=paper2_score,
        paper2_cutoff_pct=paper2_cutoff,
        paper2_cleared=paper2_cleared,
        paper1_counted=paper1_counted,
        aggregate_score=aggregate,
        aggregate_cutoff_pct=aggregate_cutoff,
        aggregate_cleared=aggregate >= aggregate_cutoff,
    )


@app.get("/api/history/search")
def history_search(query: str = Query(..., min_length=1), limit: int = Query(default=20, ge=1, le=100)):
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
    # Plan v6 6.8: history search extended to the unified PYQ bank + descriptive lab.
    pyqs = db.search_pyqs(query, limit=limit)
    descriptive = db.search_descriptive_items(query, limit=limit)
    return {
        "query": query,
        "total": len(source_results) + len(essays) + len(amendments) + len(pyqs) + len(descriptive),
        "sources": source_results[:limit],
        "essays": essays[:limit],
        "amendments": amendments[:limit],
        "pyqs": pyqs,
        "descriptive": descriptive,
    }


# ============================================================================
# PHASE 5: Law Revision & Spaced Review Endpoints
# ============================================================================

@app.get("/api/law/review/due", response_model=list[SpacedReviewItemModel])
def get_law_review_due(limit: int = Query(default=20, ge=1, le=50)):
    """Get law review items due today for spaced revision."""
    return law_revision_engine.get_spaced_review_due(limit=limit)


@app.post("/api/law/review/{review_id}/complete")
def mark_law_review_complete(
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
def get_provision_detail(provision_id: str = Path(..., description="Provision ID")):
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
def get_weak_legal_areas(limit: int = Query(default=10, ge=1, le=20)):
    """Get legal areas where user's accuracy is weak (<60%)."""
    return law_revision_engine.get_weak_legal_areas(limit=limit)


@app.get("/api/amendments/recent", response_model=list[RecentAmendmentModel])
def get_recent_amendments_endpoint(
    days_back: int = Query(default=30, ge=7, le=90),
    limit: int = Query(default=20, ge=1, le=50),
):
    """Get recent amendments from past N days (highest exam relevance)."""
    return law_revision_engine.get_recent_amendments(days_back=days_back, limit=limit)


@app.get("/api/law/high-yield", response_model=list[HighYieldProvisionModel])
def get_high_yield_provisions(limit: int = Query(default=15, ge=1, le=30)):
    """Get high-yield provisions most likely to appear in exam."""
    return law_revision_engine.get_high_yield_provisions(limit=limit)


@app.post("/api/record-amendment", response_model=AmendmentResponseModel, dependencies=[Depends(gemini_spend_guard("amendments:record"))])
def record_amendment(amendment: AmendmentModel, auto_generate_questions: bool = Query(default=True)):
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


@app.post("/api/amendments/seed", dependencies=[Depends(gemini_spend_guard("amendments:seed"))])
def seed_amendments():
    if db.table_count("documents") == 0:
        db.ingest_documents(force=False)
    return db.seed_critical_amendments()


@app.get("/api/amendments")
def amendments(limit: int = Query(default=100, ge=1, le=500)):
    return {"amendments": db.list_amendments(limit=limit)}


@app.post("/api/amendments/{amendment_id}/mastered")
def mark_amendment_mastered(amendment_id: str):
    """Plan v6 6.6: close the drill loop by marking an amendment mastered."""
    conn = db.get_connection()
    try:
        now = datetime.now().isoformat()
        events = conn.execute(
            "UPDATE amendment_events SET mastery_status = 'MASTERED', last_reviewed_at = ? WHERE amendment_id = ?",
            (now, amendment_id),
        ).rowcount
        drilled = conn.execute(
            "UPDATE amendments SET drilled = 1 WHERE amendment_id = ?",
            (amendment_id,),
        ).rowcount
        conn.commit()
        if events == 0 and drilled == 0:
            raise HTTPException(status_code=404, detail=f"Amendment {amendment_id} not found")
        return {"status": "mastered", "amendment_id": amendment_id, "events_updated": events, "amendments_drilled": drilled}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        conn.close()


@app.get("/api/amendments/intelligence", dependencies=[Depends(gemini_spend_guard("amendments:intelligence"))])
def amendment_intelligence(limit: int = Query(default=12, ge=1, le=50)):
    candidates = db.amendment_candidate_chunks(limit=max(limit, 15))
    watchlist = generate_amendment_watchlist(candidates)
    return {"ai_status": get_gemini_health(), "watchlist": watchlist[:limit], "candidate_count": len(candidates)}


@app.get("/api/amendments/startup-scan", dependencies=[Depends(gemini_spend_guard("amendments:startup-scan"))])
def startup_amendment_scan(refresh: bool = Query(default=False)):
    if refresh or not hasattr(app.state, "startup_amendment_scan"):
        app.state.startup_amendment_scan = _run_startup_amendment_scan(force_local=False)
    return {
        "ai_status": get_gemini_health(),
        "scan": app.state.startup_amendment_scan,
    }


@app.post("/api/amendments/extract", dependencies=[Depends(gemini_spend_guard("amendments:extract"))])
def extract_amendment(request: AmendmentExtractRequestModel):
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
def pending_amendments():
    amendments_data = [item for item in db.list_amendments(limit=500) if item.get("mastery_status") != "MASTERED"]
    return {"amendments": amendments_data}


@app.get("/api/amendments/status")
def amendments_status():
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

        # Get recent amendments (with mastery state so the radar can render it).
        recent = conn.execute(
            """
            SELECT a.amendment_id, a.topic, a.rule_name, a.effective_date, a.source_url,
                   a.priority, a.created_at, COALESCE(e.mastery_status, 'NEW') AS mastery_status
            FROM amendments a
            LEFT JOIN amendment_events e ON e.amendment_id = a.amendment_id
            ORDER BY a.created_at DESC
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
                "mastery_status": row[7],
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
def get_question_source(question_id: str):
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
def get_source_chunk(chunk_id: str):
    """Retrieve a source chunk directly from the canonical document index."""
    source = db.get_source_chunk_detail(chunk_id)
    if not source:
        return {"status": "not_found", "chunk_id": chunk_id}
    return {"status": "found", "chunk_id": chunk_id, "source": source, "citation_note": source.get("citation_note")}


@app.get("/api/sources/distribution-by-topic", response_model=dict[str, Any])
def source_distribution_by_topic():
    """Get pie chart data for source distribution by topic."""
    data = db.source_distribution_by_category()
    return {"status": "success", **data}


@app.post("/api/exams/{exam_id}/analytics", response_model=ExamAnalyticsResponseModel)
def post_exam_analytics(exam_id: str, analytics: list[ExamAnalyticsModel]):
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
def get_analytics_timeline(limit: int = Query(default=10, ge=1, le=50)):
    """Get score progression timeline across all mocks."""
    try:
        timeline = db.get_analytics_timeline(limit)
        return [AnalyticsTimelineModel(**item) for item in timeline]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/analytics/comparison/{topic_id}")
def compare_topic_performance(topic_id: str):
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
def get_srs_due_topics():
    """Get topics due for spaced repetition review today."""
    try:
        due = db.get_due_topics()
        return [SRSTopicModel(**item) for item in due]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/srs/schedule-topic", response_model=dict[str, Any])
def schedule_srs_topic(request: SRSScheduleRequestModel):
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
def mark_srs_reviewed(topic_id: str, success: bool = Query(default=True)):
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
def get_srs_stats():
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


@app.post("/api/study-paths/generate", response_model=StudyPathModel, dependencies=[Depends(gemini_spend_guard("study-paths:generate"))])
def generate_study_path_endpoint(weak_topics: list[str] = Query(default=[])):
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
def get_active_study_path():
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
def get_study_path_progress(path_id: str):
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
def get_study_path_week(path_id: str, week: int = Path(ge=1, le=12)):
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
def mark_week_complete(path_id: str, week: int = Path(ge=1, le=12)):
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


# ============================================================================
# UPDATE TRACKER ENDPOINTS (plan v6, multi-model phase B)
# ============================================================================


@app.get("/api/updates")
def get_updates(
    sort: str = Query("date_desc", pattern="^(date_desc|date_asc|priority|category)$"),
    category: str | None = Query(None),
    exam: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """List amendment updates with sorting/filtering + recent tracker runs."""
    try:
        updates = db.list_amendment_updates(
            sort=sort, category=category, exam=exam, status=status, limit=limit,
        )
        source = "tracker"
        # amendment_updates is written only by the tracker. When it has discovered
        # nothing the curated corpus still holds real verified amendments, but that
        # ledger has no exam/category/status columns to narrow by, so a filtered
        # request must not silently widen into unfiltered corpus rows.
        if not updates and not (category or exam or status):
            updates = db.list_curated_amendments(sort=sort, limit=limit)
            source = "corpus"
        runs = db.get_tracker_runs(limit=5)
        return {"updates": updates, "runs": runs, "source": source}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/updates/status")
def get_updates_status():
    """Latest run + counts by verification_status and status + tracker interval."""
    try:
        latest = db.get_latest_tracker_run()
        all_updates = db.list_amendment_updates(limit=1000)
        by_verification: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for u in all_updates:
            vs = u.get("verification_status", "UNKNOWN")
            by_verification[vs] = by_verification.get(vs, 0) + 1
            st = u.get("status", "ACTIVE")
            by_status[st] = by_status.get(st, 0) + 1
        interval_hours = int(os.getenv("UPDATE_TRACK_INTERVAL_HOURS", "6"))
        next_run = None
        if latest and latest.get("finished_at"):
            try:
                from datetime import datetime as _dt
                finished = _dt.fromisoformat(latest["finished_at"])
                next_run = (finished + timedelta(hours=interval_hours)).isoformat()
            except Exception:
                pass
        return {
            "latest_run": latest,
            "counts_by_verification_status": by_verification,
            "counts_by_status": by_status,
            "tracker_interval_hours": interval_hours,
            "next_run": next_run,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


_JOB_UPDATE_TRACKER = "job:update-tracker"
_JOB_ENRICH_REASONS = "job:enrich-reasons"


def _spawn_guarded_job(key: str, target, label: str) -> dict[str, str]:
    """Start `target` in a daemon thread that owns `key` until it finishes.

    The request returns long before the spend ends, so the thread has to hold
    the guard rather than a request-scoped dependency. Without it a second POST
    starts a duplicate job that bills again and writes duplicate rows, and a
    manual trigger can collide with the scheduler's own run.
    """
    if not _begin_spend_guard(key):
        raise HTTPException(
            status_code=409,
            detail=f"{label} is still running. Wait for it to finish before starting another.",
        )

    def run():
        try:
            target()
        finally:
            _end_spend_guard(key)

    threading.Thread(target=run, daemon=True).start()
    return {"status": "started"}


@app.post("/api/updates/run")
def trigger_update_tracker():
    """Spawn the update tracker in a background thread; return immediately."""
    return _spawn_guarded_job(
        _JOB_UPDATE_TRACKER, update_tracker.run_update_tracker, "The amendment update tracker"
    )


@app.post("/api/updates/enrich-reasons")
def trigger_enrich_reasons():
    """Spawn enrich_past_amendment_reasons in a background thread; return immediately."""
    return _spawn_guarded_job(
        _JOB_ENRICH_REASONS,
        update_tracker.enrich_past_amendment_reasons,
        "The amendment reason enrichment",
    )


@app.post("/api/updates/{update_id}/status")
def set_update_status(
    update_id: str,
    status: str = Query(..., pattern="^(REVIEWED|DISMISSED)$"),
):
    """Set an amendment update's status to REVIEWED or DISMISSED."""
    try:
        updated = db.set_amendment_update_status(update_id, status)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Update {update_id} not found")
        return {"update_id": update_id, "status": status}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# Serve frontend assets at root so index.html's relative css/app.css and js/app.js
# resolve whether the app is opened at / or /app. Registered after all API routes so
# these mounts only catch /css/* and /js/* and never shadow API routes.
if FRONTEND_DIR.exists():
    if (FRONTEND_DIR / "css").exists():
        app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    if (FRONTEND_DIR / "js").exists():
        app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")


if __name__ == "__main__":
    import uvicorn


    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
