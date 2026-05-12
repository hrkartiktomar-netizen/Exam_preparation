"""FastAPI backend for the source-grounded IFSCA exam prep engine."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import database as db
import amendment_poller
import job_queue
from gemini_integration import (
    PROMPT_CONTRACT_VERSION,
    USE_CASE_CATALOG,
    extract_and_verify_amendment,
    gemini_available,
    generate_amendment_watchlist,
    generate_focus_plan,
    generate_law_revision_plan,
    generate_mock_blueprint,
    generate_product_gap_analysis,
    generate_pyq_calibration,
    generate_study_session,
    generate_topic_source_brief,
    get_gemini_health,
    grade_essay,
    initialize_gemini_runtime,
)
from models import (
    AmendmentExtractRequestModel,
    AmendmentModel,
    AmendmentResponseModel,
    DashboardStatsModel,
    EssayGradingResponseModel,
    EssayPromptModel,
    EssaySubmissionModel,
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
    StudySessionRequestModel,
    TopicModel,
    TopicStatsModel,
    WeakTopicsResponseModel,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="app")


def _coerce_question(question: dict[str, Any]) -> QuestionModel:
    return QuestionModel.model_validate(question)


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


@app.get("/api/law/ifsca-act")
async def ifsca_act():
    return db.ifsca_act_full_text()


@app.get("/api/law/daily-revision")
async def daily_law_revision(
    lines_per_day: int = Query(default=80, ge=30, le=180),
    day_index: int | None = Query(default=None, ge=0),
    include_ai: bool = Query(default=True),
):
    revision = db.daily_ifsca_act_revision(lines_per_day=lines_per_day, day_index=day_index)
    revision["ai_revision"] = generate_law_revision_plan(revision, force_local=not include_ai)
    revision["ai_status"] = get_gemini_health()
    return revision


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


@app.get("/api/essays/prompts", response_model=list[EssayPromptModel])
async def essay_prompts():
    return [EssayPromptModel.model_validate(prompt) for prompt in db.essay_prompts()]


@app.post("/api/grade-essay", response_model=EssayGradingResponseModel)
async def grade_essay_endpoint(submission: EssaySubmissionModel):
    try:
        source_chunks = db.chunks_for_topic(submission.topic.upper(), limit=6, query=submission.prompt)
        grade = grade_essay(submission.essay_text, submission.topic.upper(), source_chunks)
        essay_id = db.save_essay(submission.model_dump(), grade, source_chunks)
        grade["essay_id"] = essay_id
        grade["suggested_sources"] = source_chunks
        return EssayGradingResponseModel.model_validate(grade)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/essays/history")
async def essay_history(limit: int = Query(default=25, ge=1, le=100)):
    return {"essays": db.list_essays(limit=limit)}


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

        # Count new amendments this week
        from datetime import datetime, timedelta
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
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
        # Get question source link from question_sources table (Phase 0)
        source_link = conn.execute(
            """
            SELECT qs.source_chunk_id, qs.authority_score
            FROM question_sources qs
            WHERE qs.question_id = ? LIMIT 1
            """,
            (question_id,),
        ).fetchone()

        if not source_link:
            return {"status": "not_found", "question_id": question_id}

        chunk_id = source_link["source_chunk_id"]
        authority_score = source_link["authority_score"] or 50

        # Get source chunk and document details
        chunk = conn.execute(
            """
            SELECT sc.chunk_id, sc.doc_id, sc.chunk_text, sc.page_num, sc.section_title,
                   sd.name as document_name, sd.category, sd.doc_type
            FROM source_chunks sc
            JOIN source_documents sd ON sc.doc_id = sd.doc_id
            WHERE sc.chunk_id = ? LIMIT 1
            """,
            (chunk_id,),
        ).fetchone()

        if not chunk:
            return {"status": "not_found", "question_id": question_id}

        # Format citation note
        citation_note = db.format_citation_note(dict(chunk), page_num=chunk["page_num"])

        return {
            "status": "found",
            "question_id": question_id,
            "source": dict(chunk),
            "authority_score": authority_score,
            "page_start": chunk["page_num"],
            "page_end": chunk["page_num"],
            "citation_note": citation_note,
        }
    finally:
        conn.close()


@app.get("/api/questions/search", response_model=SourceSearchResponseModel)
async def search_questions(query: str, topic_id: str | None = None, limit: int = 10):
    """Full-text search questions and return by authority score."""
    results = []
    conn = db.get_connection()
    try:
        # Validate query
        if not query or not query.strip():
            return {"query": query, "topic_id": topic_id, "total": 0, "results": []}

        # FTS5 search on source chunks, ranked by authority
        fts_results = conn.execute(
            """
            SELECT DISTINCT sc.chunk_id, sd.doc_id, sd.name, sd.category, sd.doc_type,
                   sc.page_num, sc.chunk_text, COALESCE(qs.authority_score, 50) as authority_score
            FROM source_chunks_fts fts
            JOIN source_chunks sc ON fts.rowid = sc.rowid
            JOIN source_documents sd ON sc.doc_id = sd.doc_id
            LEFT JOIN question_sources qs ON sc.chunk_id = qs.source_chunk_id
            WHERE source_chunks_fts MATCH ?
            ORDER BY authority_score DESC, sc.page_num ASC
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()

        for row in fts_results:
            results.append({
                "chunk_id": str(row["chunk_id"]),
                "document_id": str(row["doc_id"]),
                "title": row["name"],
                "category": row["category"],
                "page_start": row["page_num"],
                "excerpt": row["chunk_text"][:500] if row["chunk_text"] else "",
                "authority_score": row["authority_score"],
            })
    finally:
        conn.close()

    return {
        "query": query,
        "topic_id": topic_id,
        "total": len(results),
        "results": results,
    }


@app.get("/api/sources/distribution-by-topic", response_model=dict[str, Any])
async def source_distribution_by_topic():
    """Get pie chart data for source distribution by topic."""
    conn = db.get_connection()
    try:
        distribution = conn.execute(
            """
            SELECT
                COALESCE(sd.category, 'Unknown') as source_type,
                COUNT(DISTINCT sc.chunk_id) as chunk_count,
                COUNT(DISTINCT qs.question_id) as question_count,
                AVG(CAST(qs.authority_score AS REAL)) as avg_authority
            FROM source_documents sd
            LEFT JOIN source_chunks sc ON sd.doc_id = sc.doc_id
            LEFT JOIN question_sources qs ON sc.chunk_id = qs.source_chunk_id
            GROUP BY source_type
            ORDER BY chunk_count DESC
            """
        ).fetchall()

        pie_data = [
            {
                "label": row["source_type"],
                "chunks": row["chunk_count"],
                "questions": row["question_count"] or 0,
                "avg_authority": round(row["avg_authority"] or 50, 1),
            }
            for row in distribution
        ]

        total_chunks = sum(item["chunks"] for item in pie_data)

        return {
            "status": "success",
            "total_chunks": total_chunks,
            "distribution": pie_data,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
