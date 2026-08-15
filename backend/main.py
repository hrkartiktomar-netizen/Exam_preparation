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
    available_gemini_keys,
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
