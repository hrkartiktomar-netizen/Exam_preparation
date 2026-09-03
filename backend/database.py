"""SQLite persistence, ingestion, search, and local generation logic."""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import sqlite3
import threading
import uuid
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import knowledge
from gemini_integration import generate_questions_with_gemini, gemini_available
from authority_scoring import source_authority_score as calculate_source_authority


BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
DB_PATH = BACKEND_DIR / "ifsca_exam.db"
EXTRACTED_DIR = PROJECT_ROOT / "extracted_pdfs"
SOURCE_PDF_DIR = PROJECT_ROOT / "source_documents" / "pdfs"
INDEX_PATH = EXTRACTED_DIR / "COMPREHENSIVE_INDEX.json"

# Runtime grounding source: "knowledge" reads the committed knowledge pack
# (zero file dependence); "chunks" keeps the legacy md/txt FTS path for research.
SOURCE_MODE = os.getenv("SOURCE_MODE", "knowledge")

# Every smart mock is normalised to this many marks regardless of question count,
# so marks_per_question is derived rather than fixed. Published in the submit
# response so clients can render "score / max" without assuming the scale.
MOCK_EXAM_MAX_SCORE = 100.0


TOPIC_DEFINITIONS: list[dict[str, Any]] = [
    {
        "topic_id": "PH2_IFSCA_ACT",
        "display_name": "IFSCA Act and Authority",
        "description": "IFSCA Act, 2019, powers, functions, authority structure, unified regulator model.",
        "base_weight": 0.90,
        "exam_priority": 9,
        "is_amendment_sensitive": True,
        "keywords": ["ifsca act", "international financial services centres authority act", "section 10", "authority", "unified regulator"],
    },
    {
        "topic_id": "PH2_GIFT_IFSC",
        "display_name": "GIFT IFSC Ecosystem",
        "description": "GIFT City, IFSC purpose, entity types, ecosystem growth, global financial centre positioning.",
        "base_weight": 0.85,
        "exam_priority": 8,
        "is_amendment_sensitive": False,
        "keywords": ["gift city", "gift ifsc", "ifsc ecosystem", "global financial centre", "gandhinagar", "gihc", "global in-house centre", "foreign university", "swit"],
    },
    {
        "topic_id": "PH2_FM_REGS",
        "display_name": "Fund Management Regulations",
        "description": "FME categories, AIFs, schemes, KMP, PPM, ESG funds, fund management amendments.",
        "base_weight": 1.00,
        "exam_priority": 10,
        "is_amendment_sensitive": True,
        "keywords": ["fund management", "fme", "aif", "alternative investment fund", "kmp", "private placement memorandum", "ppm"],
    },
    {
        "topic_id": "PH2_BANKING",
        "display_name": "Banking and IBUs",
        "description": "IFSC Banking Units, Banking Handbook, prudential norms, conduct of business, credit directions.",
        "base_weight": 0.95,
        "exam_priority": 10,
        "is_amendment_sensitive": True,
        "keywords": ["banking", "ibu", "ifsc banking unit", "banking handbook", "prudential", "conduct of business", "credit"],
    },
    {
        "topic_id": "PH2_CAPITAL",
        "display_name": "Capital Markets",
        "description": "Exchanges, depositories, FPIs, capital market ecosystem, India INX, NSE IFSC.",
        "base_weight": 0.95,
        "exam_priority": 10,
        "is_amendment_sensitive": True,
        "keywords": ["capital market", "securities market", "fpi", "foreign portfolio investor", "exchange", "depository", "india inx", "nse ifsc"],
    },
    {
        "topic_id": "PH2_CMI",
        "display_name": "Capital Market Intermediaries",
        "description": "CMI Regulations, principal officer, compliance officer, certification, registration obligations.",
        "base_weight": 0.85,
        "exam_priority": 8,
        "is_amendment_sensitive": True,
        "keywords": ["capital market intermediaries", "cmi", "principal officer", "compliance officer", "certification course"],
    },
    {
        "topic_id": "PH2_LISTING",
        "display_name": "Listing, ESG, SPACs and Bonds",
        "description": "Listing Regulations, direct listing, SPACs, ESG bonds, SGrBs, transition bonds, LEAP.",
        "base_weight": 0.88,
        "exam_priority": 8,
        "is_amendment_sensitive": True,
        "keywords": ["listing", "direct listing", "spac", "esg", "sgrb", "transition bond", "leap", "issb"],
    },
    {
        "topic_id": "PH2_PAYMENT",
        "display_name": "Payment Services",
        "description": "Payment Services Regulations, PSP, RPSP, significant PSP, Payments Regulatory Board.",
        "base_weight": 0.82,
        "exam_priority": 8,
        "is_amendment_sensitive": True,
        "keywords": ["payment services", "payment service provider", "psp", "rpsp", "payments regulatory board", "remittance"],
    },
    {
        "topic_id": "PH2_TECHFIN_TAS",
        "display_name": "TechFin and Ancillary Services",
        "description": "TechFin, ancillary services, TAS Regulations 2025, sandbox and innovation framework.",
        "base_weight": 0.90,
        "exam_priority": 9,
        "is_amendment_sensitive": True,
        "keywords": ["techfin", "ancillary services", "tas", "sandbox", "innovation sandbox", "fintech"],
    },
    {
        "topic_id": "PH2_BULLION",
        "display_name": "Bullion and IIBX",
        "description": "India International Bullion Exchange, qualified jewellers, authorized persons, vaulting.",
        "base_weight": 0.78,
        "exam_priority": 7,
        "is_amendment_sensitive": True,
        "keywords": ["bullion", "iibx", "qualified jeweller", "vault", "authorized persons", "precious metals"],
    },
    {
        "topic_id": "PH2_INSURANCE",
        "display_name": "Insurance and Reinsurance",
        "description": "IFSC Insurance Offices, reinsurance, insurance intermediaries, insurance regulatory framework.",
        "base_weight": 0.75,
        "exam_priority": 7,
        "is_amendment_sensitive": True,
        "keywords": ["insurance", "reinsurance", "ifsc insurance office", "iio", "irda", "irdai"],
    },
    {
        "topic_id": "PH2_AIRCRAFT_SHIP_LEASING",
        "display_name": "Aircraft and Ship Leasing",
        "description": "Aircraft leasing, ship leasing, tax and entity framework, asset finance structures.",
        "base_weight": 0.70,
        "exam_priority": 6,
        "is_amendment_sensitive": False,
        "keywords": ["aircraft leasing", "ship leasing", "lessor", "lease", "asset leasing", "aviation"],
    },
    {
        "topic_id": "PH2_AML_KYC",
        "display_name": "AML, CFT, KYC and KRA",
        "description": "AML/CFT/KYC Guidelines, KRA Regulations, onboarding, beneficial ownership, certification.",
        "base_weight": 0.88,
        "exam_priority": 9,
        "is_amendment_sensitive": True,
        "keywords": ["aml", "cft", "kyc", "kra", "beneficial ownership", "nism-ifsca", "anti money laundering"],
    },
    {
        "topic_id": "PH2_COMMODITY_TRADE",
        "display_name": "Commodity Trade Hub",
        "description": "Commodity trading hub, expert committee, global commodity trade via GIFT City.",
        "base_weight": 0.72,
        "exam_priority": 7,
        "is_amendment_sensitive": True,
        "keywords": ["commodity", "commodity trading", "global commodity", "trading hub"],
    },
    {
        "topic_id": "PH2_TAX",
        "display_name": "IFSC Tax Benefits",
        "description": "Income-tax holiday, MAT, GST, customs, specified funds, IFSC tax framework.",
        "base_weight": 0.80,
        "exam_priority": 7,
        "is_amendment_sensitive": True,
        "keywords": ["tax", "income tax", "mat", "gst", "customs", "tax holiday", "specified fund"],
    },
    {
        "topic_id": "PH2_CURRENT_AFFAIRS",
        "display_name": "Current Affairs and Data",
        "description": "Current affairs, budget, financial services policy, annual report data and statistics.",
        "base_weight": 0.84,
        "exam_priority": 8,
        "is_amendment_sensitive": True,
        "keywords": ["current affairs", "annual report", "statistics", "turnover", "employment", "gfcI", "market update"],
    },
    {
        "topic_id": "PH2_MANAGEMENT_ORG",
        "display_name": "Management and Organization",
        "description": "Management, leadership, HR, communication, governance syllabus areas.",
        "base_weight": 0.62,
        "exam_priority": 5,
        "is_amendment_sensitive": False,
        "keywords": ["management", "leadership", "organization", "communication", "human resource", "motivation"],
    },
    {
        "topic_id": "PH2_ESSAY",
        "display_name": "Essay Evidence and Themes",
        "description": "Essay prompts, structure, evidence, examples, current data points.",
        "base_weight": 0.90,
        "exam_priority": 9,
        "is_amendment_sensitive": True,
        "keywords": ["essay", "write", "discuss", "explain", "critically examine", "currenttap", "booster"],
    },
    {
        "topic_id": "PH2_PENSION",
        "display_name": "Pension Sector",
        "description": "Pension sector in India, retirement schemes, NPS, APY, annuity plans, basics of investment.",
        "base_weight": 0.72,
        "exam_priority": 7,
        "is_amendment_sensitive": False,
        "keywords": ["pension", "pfrda", "nps", "national pension system", "atal pension", "apy", "annuity", "retirement scheme", "unified pension"],
    },
    {
        "topic_id": "PH2_BUDGET_ECON_SURVEY",
        "display_name": "Union Budget and Economic Survey",
        "description": "Union Budget concepts, approach, broad trends, and Economic Survey highlights.",
        "base_weight": 0.76,
        "exam_priority": 8,
        "is_amendment_sensitive": True,
        "keywords": ["union budget", "budget", "economic survey", "fiscal deficit", "finance commission", "budget allocation", "frbm"],
    },
    {
        "topic_id": "SUBJ_QUANT",
        "display_name": "Quantitative Aptitude",
        "description": "Shared aptitude subject (IFSCA Phase I P1 / SEBI P1): DI, series, arithmetic.",
        "base_weight": 0.50, "exam_priority": 5, "is_amendment_sensitive": False,
        "keywords": ["quantitative aptitude", "quant", "data interpretation", "number series", "percentage", "ratio", "profit", "time and work"],
    },
    {
        "topic_id": "SUBJ_REASONING",
        "display_name": "Reasoning Ability",
        "description": "Shared aptitude subject: seating, puzzles, syllogism, coding, direction.",
        "base_weight": 0.50, "exam_priority": 5, "is_amendment_sensitive": False,
        "keywords": ["reasoning", "seating", "puzzle", "syllogism", "coding", "direction", "blood relation", "inequality"],
    },
    {
        "topic_id": "SUBJ_ENGLISH",
        "display_name": "English Language",
        "description": "Shared aptitude subject: reading comprehension, error spotting, vocabulary.",
        "base_weight": 0.50, "exam_priority": 5, "is_amendment_sensitive": False,
        "keywords": ["english", "comprehension", "synonym", "antonym", "error detection", "cloze", "para jumble"],
    },
    {
        "topic_id": "SUBJ_GA",
        "display_name": "General Awareness",
        "description": "Shared aptitude subject: current affairs, schemes, awards, static GK.",
        "base_weight": 0.50, "exam_priority": 5, "is_amendment_sensitive": False,
        "keywords": ["general awareness", "current affairs", "scheme", "award", "appointment", "sports", "summit"],
    },
    {
        "topic_id": "SUBJ_FINANCE",
        "display_name": "Finance (Stream)",
        "description": "Shared stream subject (Phase I P2 / SEBI): financial system, markets, derivatives.",
        "base_weight": 0.60, "exam_priority": 6, "is_amendment_sensitive": False,
        "keywords": ["finance", "financial markets", "derivatives", "money market", "capital market", "time value"],
    },
    {
        "topic_id": "SUBJ_MANAGEMENT",
        "display_name": "Management (Stream)",
        "description": "Shared stream subject: management processes, leadership, HR, motivation.",
        "base_weight": 0.55, "exam_priority": 5, "is_amendment_sensitive": False,
        "keywords": ["management", "leadership", "motivation", "organizational", "human resource"],
    },
    {
        "topic_id": "SUBJ_COMMERCE_ACCOUNTS",
        "display_name": "Commerce and Accounts (Stream)",
        "description": "Shared stream subject: accounting standards, ratios, share capital.",
        "base_weight": 0.55, "exam_priority": 5, "is_amendment_sensitive": False,
        "keywords": ["commerce", "accounts", "accounting", "accounting standards", "ratio analysis", "share capital"],
    },
    {
        "topic_id": "SUBJ_COSTING",
        "display_name": "Costing (Stream)",
        "description": "Shared stream subject: costing methods, standard/marginal costing, lean systems.",
        "base_weight": 0.50, "exam_priority": 5, "is_amendment_sensitive": False,
        "keywords": ["costing", "marginal costing", "standard costing", "budget", "lean", "kaizen"],
    },
    {
        "topic_id": "SUBJ_ECONOMICS",
        "display_name": "Economics (Stream)",
        "description": "Shared stream subject: macro/micro economics, IS-LM, inflation, BoP.",
        "base_weight": 0.55, "exam_priority": 5, "is_amendment_sensitive": False,
        "keywords": ["economics", "inflation", "phillips", "is-lm", "national income", "balance of payments", "monetary policy"],
    },
    {
        "topic_id": "SUBJ_COMPANIES_ACT",
        "display_name": "Companies Act (Stream)",
        "description": "Shared stream subject (SEBI-heavy): Companies Act 2013 chapters and procedures.",
        "base_weight": 0.50, "exam_priority": 5, "is_amendment_sensitive": False,
        "keywords": ["companies act", "company law", "prospectus", "dividend", "nclt"],
    },
    {
        "topic_id": "SUBJ_ESSAY",
        "display_name": "Essay (Descriptive)",
        "description": "Shared descriptive component across IFSCA and SEBI Phase-II papers.",
        "base_weight": 0.55, "exam_priority": 6, "is_amendment_sensitive": False,
        "keywords": ["essay writing", "essay"],
    },
    {
        "topic_id": "SUBJ_PRECIS",
        "display_name": "Precis (Descriptive)",
        "description": "Shared descriptive component: precis writing with title.",
        "base_weight": 0.55, "exam_priority": 6, "is_amendment_sensitive": False,
        "keywords": ["precis", "precis writing"],
    },
    {
        "topic_id": "SUBJ_RC",
        "display_name": "Reading Comprehension (Descriptive)",
        "description": "Shared descriptive component: passage-based questions answered in own words.",
        "base_weight": 0.55, "exam_priority": 6, "is_amendment_sensitive": False,
        "keywords": ["reading comprehension", "comprehension passage"],
    },
]

TOPIC_BY_ID = {topic["topic_id"]: topic for topic in TOPIC_DEFINITIONS}
TOPIC_IDS = [topic["topic_id"] for topic in TOPIC_DEFINITIONS]
OBJECTIVE_MOCK_TOPIC_IDS = [
    topic_id for topic_id in TOPIC_IDS
    if topic_id != "PH2_ESSAY" and not topic_id.startswith("SUBJ_")
]


SOURCE_CATEGORY_PRIORITY = {
    "IFSCA Regulations (TAS/PSR/RI)": 1.00,
    "IFSCA Publications (Reports/Bulletins)": 0.95,
    "IFSCA Career": 0.92,
    "ICSI Materials": 0.88,
    "Scribd Login Required": 0.72,
    "Exam Papers (Memory-based)": 0.70,
    "Big4 Consulting (PwC/EY/GT/KPMG)": 0.62,
    "Study Materials": 0.58,
    "Current Affairs": 0.52,
    "Other": 0.40,
}

OFFICIAL_TITLE_HINTS = (
    "ifsca",
    "icsi",
    "indiacode",
    "annual report",
    "bulletin",
    "regulations",
    "circular",
    "handbook",
    "notification",
    "information handout",
)

EXAM_SIGNAL_TERMS = (
    "regulation",
    "regulations",
    "circular",
    "framework",
    "effective",
    "amendment",
    "eligibility",
    "registration",
    "principal officer",
    "compliance officer",
    "cut-off",
    "phase",
    "paper",
    "marks",
)

QUESTION_FOCUS_BY_TOPIC = {
    "PH2_IFSCA_ACT": "statutory power, function, or regulatory mandate",
    "PH2_GIFT_IFSC": "GIFT IFSC ecosystem role or institutional positioning",
    "PH2_FM_REGS": "fund management eligibility, structure, or compliance requirement",
    "PH2_BANKING": "IBU prudential, conduct, or handbook requirement",
    "PH2_CAPITAL": "market infrastructure, FPI, exchange, or securities-market rule",
    "PH2_CMI": "capital market intermediary registration or officer obligation",
    "PH2_LISTING": "listing, ESG, SPAC, SGrB, or transition-bond requirement",
    "PH2_PAYMENT": "payment service provider authorisation or regulatory requirement",
    "PH2_TECHFIN_TAS": "TechFin, ancillary services, or sandbox requirement",
    "PH2_BULLION": "bullion exchange, qualified jeweller, vaulting, or IIBX requirement",
    "PH2_INSURANCE": "IFSC insurance office or reinsurance regulatory requirement",
    "PH2_AIRCRAFT_SHIP_LEASING": "aircraft, ship leasing, or asset-finance treatment",
    "PH2_AML_KYC": "AML, CFT, KYC, KRA, or beneficial-ownership obligation",
    "PH2_COMMODITY_TRADE": "commodity trading hub or global commodity-market positioning",
    "PH2_TAX": "IFSC tax treatment, exemption, or fiscal incentive",
    "PH2_CURRENT_AFFAIRS": "current data point, market trend, or policy development",
    "PH2_MANAGEMENT_ORG": "management principle or organisational governance concept",
    "PH2_ESSAY": "evidence point usable in a Phase 2 essay answer",
}

EXAM_MATERIAL_CATEGORIES = {
    "Exam Papers (Memory-based)",
    "Study Materials",
    "ICSI Materials",
    "IFSCA Career",
    "IFSCA Regulations (TAS/PSR/RI)",
    "IFSCA Publications (Reports/Bulletins)",
    "Scribd Login Required",
    "Other",
    "Current Affairs",
}

PYQ_PHASE_SOURCE_TERMS = (
    "pyq",
    "previous year",
    "memory",
    "memory based",
    "question paper",
    "question-paper",
    "paper 1",
    "paper 2",
    "phase 1",
    "phase 2",
    "information handout",
    "exam handout",
    "syllabus",
    "study material",
    "grade a",
    "icsi",
    "regulations listing and compliances",
)

OFFICIAL_MATERIAL_TERMS = (
    "ifsca",
    "regulation",
    "regulations",
    "circular",
    "handbook",
    "guidelines",
    "annual report",
    "bulletin",
    "indiacode",
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS question_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mock_id TEXT NOT NULL,
    question_id TEXT,
    topic TEXT NOT NULL,
    question_text TEXT,
    correct_option TEXT,
    your_option TEXT,
    is_correct BOOLEAN,
    time_spent_seconds INTEGER,
    attempt_date TEXT,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS topic_stats (
    topic TEXT PRIMARY KEY,
    total_seen INTEGER DEFAULT 0,
    total_correct INTEGER DEFAULT 0,
    accuracy_pct REAL DEFAULT 0.0,
    last_tested TEXT,
    status TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS amendments (
    amendment_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    effective_date TEXT,
    old_value TEXT,
    new_value TEXT,
    source_url TEXT,
    verify_status TEXT,
    priority TEXT,
    questions_needed INTEGER,
    drilled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS generated_questions (
    question_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    question_text TEXT,
    options TEXT,
    correct_option TEXT,
    explanation TEXT,
    source TEXT,
    is_amendment_based BOOLEAN,
    difficulty TEXT,
    recency_score INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mocks (
    mock_id TEXT PRIMARY KEY,
    date TEXT,
    phase TEXT,
    paper TEXT,
    total_questions INTEGER,
    total_correct INTEGER,
    total_skipped INTEGER,
    overall_accuracy REAL,
    time_taken_minutes INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS penalty_drills (
    drill_id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    weak_threshold REAL NOT NULL,
    current_accuracy REAL NOT NULL,
    questions_in_drill INTEGER DEFAULT 10,
    completed BOOLEAN DEFAULT FALSE,
    accuracy_after REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS smart_mocks (
    mock_id TEXT PRIMARY KEY,
    generated_at TIMESTAMP,
    total_questions INTEGER,
    weakness_analysis TEXT,
    allocation TEXT,
    difficulty_curve TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT,
    source_type TEXT,
    source_url TEXT,
    local_pdf_path TEXT,
    local_text_path TEXT,
    sha256 TEXT UNIQUE,
    pages INTEGER DEFAULT 0,
    line_count INTEGER DEFAULT 0,
    publication_date TEXT,
    downloaded_at TEXT,
    ingested_at TEXT,
    status TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    line_start INTEGER,
    line_end INTEGER,
    text TEXT NOT NULL,
    token_estimate INTEGER,
    chunk_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(document_id) REFERENCES documents(document_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS document_chunk_fts USING fts5(
    chunk_id UNINDEXED,
    document_id UNINDEXED,
    title,
    text,
    topic_tags,
    source_type
);

CREATE TABLE IF NOT EXISTS topics (
    topic_id TEXT PRIMARY KEY,
    parent_topic_id TEXT,
    phase TEXT,
    paper TEXT,
    display_name TEXT,
    description TEXT,
    base_weight REAL,
    exam_priority INTEGER,
    is_amendment_sensitive BOOLEAN
);

CREATE TABLE IF NOT EXISTS chunk_topics (
    chunk_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    confidence REAL,
    method TEXT,
    PRIMARY KEY (chunk_id, topic_id)
);

CREATE TABLE IF NOT EXISTS amendment_events (
    amendment_id TEXT PRIMARY KEY,
    title TEXT,
    topic_id TEXT,
    source_document_id TEXT,
    source_chunk_id TEXT,
    old_value TEXT,
    new_value TEXT,
    effective_date TEXT,
    publication_date TEXT,
    exam_priority INTEGER,
    mastery_status TEXT,
    questions_generated INTEGER DEFAULT 0,
    last_reviewed_at TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS questions (
    question_id TEXT PRIMARY KEY,
    source TEXT,
    topic_id TEXT,
    subtopic_id TEXT,
    question_text TEXT,
    option_a TEXT,
    option_b TEXT,
    option_c TEXT,
    option_d TEXT,
    correct_answer TEXT,
    explanation TEXT,
    difficulty TEXT,
    question_type TEXT,
    is_amendment_based BOOLEAN,
    amendment_id TEXT,
    created_by TEXT,
    prompt_version TEXT,
    verification_status TEXT,
    tested_fact TEXT,
    trap_logic TEXT,
    source_policy TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS question_citations (
    question_id TEXT,
    document_id TEXT,
    chunk_id TEXT,
    page_start INTEGER,
    page_end INTEGER,
    citation_note TEXT,
    PRIMARY KEY (question_id, chunk_id)
);

CREATE TABLE IF NOT EXISTS mock_sessions (
    mock_id TEXT PRIMARY KEY,
    mock_type TEXT,
    generated_at TEXT,
    started_at TEXT,
    submitted_at TEXT,
    total_questions INTEGER,
    score REAL,
    accuracy REAL,
    allocation_json TEXT,
    difficulty_curve_json TEXT,
    status TEXT
);

CREATE TABLE IF NOT EXISTS mock_questions (
    mock_id TEXT,
    question_id TEXT,
    question_number INTEGER,
    source_reason TEXT,
    PRIMARY KEY (mock_id, question_id)
);

CREATE TABLE IF NOT EXISTS answers (
    answer_id TEXT PRIMARY KEY,
    mock_id TEXT,
    drill_id TEXT,
    question_id TEXT,
    selected_answer TEXT,
    is_correct BOOLEAN,
    time_spent_seconds INTEGER,
    marked_for_review BOOLEAN,
    answered_at TEXT
);

CREATE TABLE IF NOT EXISTS essay_submissions (
    essay_id TEXT PRIMARY KEY,
    prompt TEXT,
    essay_text TEXT,
    submitted_at TEXT,
    time_limit_minutes INTEGER,
    word_count INTEGER,
    topic_tags TEXT,
    overall_score INTEGER
);

CREATE TABLE IF NOT EXISTS essay_scores (
    essay_id TEXT PRIMARY KEY,
    content_accuracy INTEGER,
    structure_clarity INTEGER,
    regulatory_knowledge INTEGER,
    examples_evidence INTEGER,
    feedback_json TEXT,
    model_outline TEXT,
    source_suggestions_json TEXT
);

CREATE TABLE IF NOT EXISTS review_items (
    review_id TEXT PRIMARY KEY,
    item_type TEXT,
    item_id TEXT,
    topic_id TEXT,
    due_at TEXT,
    interval_days INTEGER,
    ease REAL,
    last_result TEXT
);

CREATE TABLE IF NOT EXISTS recommendation_log (
    recommendation_id TEXT PRIMARY KEY,
    created_at TEXT,
    recommendation_type TEXT,
    message TEXT,
    reason_json TEXT,
    accepted BOOLEAN,
    completed BOOLEAN
);

CREATE TABLE IF NOT EXISTS exam_analytics (
    analytics_id TEXT PRIMARY KEY,
    exam_id TEXT NOT NULL,
    topic_id TEXT,
    accuracy_pct REAL,
    time_spent_seconds INTEGER,
    difficulty_rating TEXT,
    comparison_to_avg REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(exam_id) REFERENCES mock_sessions(mock_id)
);

CREATE TABLE IF NOT EXISTS study_paths (
    path_id TEXT PRIMARY KEY,
    exam_date TEXT NOT NULL,
    weeks_json TEXT NOT NULL,
    milestone_count INTEGER DEFAULT 12,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS study_path_progress (
    progress_id TEXT PRIMARY KEY,
    path_id TEXT NOT NULL,
    week_number INTEGER,
    completed_topics_json TEXT,
    score_history_json TEXT,
    status TEXT DEFAULT 'not_started',
    completed_at TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(path_id) REFERENCES study_paths(path_id)
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Avoid immediate "database is locked" errors under concurrent request handling
    # (background job queue + scheduler + request handlers share one SQLite file).
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def seed_topics(conn: sqlite3.Connection) -> None:
    """Seed initial topics into the database.

    Per Context7 docs for SQLite: use parameterized queries (?) to prevent
    injection and ON CONFLICT IGNORE for safe idempotent re-seeding.
    """
    try:
        for topic in TOPIC_DEFINITIONS:
            conn.execute(
                """
                INSERT INTO topics (
                    topic_id, parent_topic_id, phase, paper, display_name,
                    description, base_weight, exam_priority, is_amendment_sensitive
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(topic_id) DO NOTHING
                """,
                (
                    topic.get("topic_id"),
                    topic.get("parent_topic_id"),
                    topic.get("phase"),
                    topic.get("paper"),
                    topic.get("display_name"),
                    topic.get("description"),
                    topic.get("base_weight"),
                    topic.get("exam_priority"),
                    topic.get("is_amendment_sensitive", False),
                ),
            )
        conn.commit()
    except Exception as e:
        print(f"Error seeding topics: {e}")
        conn.rollback()
        raise


def _populate_source_role_on_documents(conn: sqlite3.Connection) -> None:
    """Populate source_role column on documents table from source_documents.

    This bridges the documents and source_documents parallel tables
    by matching titles and populating source_role on documents.
    Per Context7 docs for SQLite: use UPDATE with JOIN for bulk operations.
    """
    try:
        cursor = conn.cursor()

        # Step 1: Check if source_role column exists, add if not
        cols = _table_columns(conn, "documents")
        if "source_role" not in cols:
            cursor.execute("ALTER TABLE documents ADD COLUMN source_role TEXT DEFAULT 'supporting_material'")
            conn.commit()

        # Step 2: Update documents.source_role from source_documents by title matching
        # Use a simple substring match since titles vary slightly
        # Update rule: if documents.title contains source_documents.name (or vice versa), match them
        cursor.execute("""
        UPDATE documents
        SET source_role = (
            SELECT sd.source_role
            FROM source_documents sd
            WHERE sd.name IS NOT NULL AND documents.title IS NOT NULL
            AND (
                LOWER(documents.title) LIKE '%' || LOWER(SUBSTR(sd.name, 1, 40)) || '%'
                OR LOWER(sd.name) LIKE '%' || LOWER(SUBSTR(documents.title, 1, 40)) || '%'
            )
            LIMIT 1
        )
        WHERE source_role = 'supporting_material'  -- Only update defaults
        """)

        conn.commit()

        # Log results
        dist = cursor.execute("""
        SELECT source_role, COUNT(*) as cnt FROM documents GROUP BY source_role
        """).fetchall()
        print("  documents.source_role distribution:")
        for role, cnt in dist:
            print(f"    {role}: {cnt}")

    except Exception as e:
        print(f"  Warning: Could not populate source_role on documents: {e}")
        conn.rollback()


def _source_role_for_name(name: str) -> str:
    """Assign a source_role based on document name markers.

    - pyq_phase_paper: Memory-based question papers (Grade A + Memory + Question + Paper)
    - regulatory_core: Official regulations, acts, ICSI materials
    - amendment_tracking: Recent regulatory amendments
    - essay_examples: Consulting reports, case studies
    - supporting_material: General reads (default)
    """
    name = (name or "").lower()
    regulatory_markers = ("Regulation", "IFSCA", "ICSI", "Indiacode", "Act",  "Guidelines", "Circular")
    amendment_markers = ("Amendment", "Notification", "Draft", "Consultation", "2025", "2026")
    consulting_markers = ("PwC", "EY", "Grant Thornton", "KPMG", "Deloitte", "Analysis", "Report")

    role = "supporting_material"  # default

    if all(marker.lower() in name for marker in ["memory", "grade", "question", "paper"]):
        role = "pyq_phase_paper"
    elif any(m.lower() in name for m in regulatory_markers):
        role = "regulatory_core"
    elif any(m.lower() in name for m in amendment_markers):
        role = "amendment_tracking"
    elif any(m.lower() in name for m in consulting_markers):
        role = "essay_examples"
    return role


def _categorize_materials(conn: sqlite3.Connection) -> None:
    """Categorize all source materials by role for smart Gemini routing.

    Categorizes BOTH the legacy source_documents table (if it has rows) and the
    canonical documents table, because ingestion only populates `documents` and
    source_documents stays empty on fresh installations.
    """
    try:
        cursor = conn.cursor()

        # Fast path: this function runs inside init_db(), which is invoked by many
        # endpoints (search_sources, save_question, record_mock, dashboard_data, ...).
        # When nothing is uncategorized, the no-op cost must stay at three COUNTs and
        # zero UPDATEs, otherwise every request pays a 150-row scan plus updates.
        #
        # A pass is needed when:
        #  - any document has no role (NULL/''), or
        #  - documents exist but NONE has a non-default role. Fresh ingestion inserts
        #    rows with the column DEFAULT 'supporting_material', so on a brand-new
        #    database every document is 'supporting_material' and the first pass must
        #    still run to assign the real roles (pyq papers, regulatory core, ...).
        unset = cursor.execute(
            "SELECT COUNT(*) FROM documents WHERE source_role IS NULL OR source_role = ''"
        ).fetchone()[0]
        total = cursor.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        non_default = cursor.execute(
            "SELECT COUNT(*) FROM documents WHERE source_role IN ('pyq_phase_paper', 'regulatory_core', 'amendment_tracking', 'essay_examples')"
        ).fetchone()[0]
        legacy_count = cursor.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0]
        if unset == 0 and legacy_count == 0 and not (total > 0 and non_default == 0):
            return

        # Legacy table (only populated on databases created by the old ingestion path)
        cursor.execute("SELECT doc_id, name FROM source_documents")
        docs = cursor.fetchall()

        for doc in docs:
            doc_id = doc["doc_id"]
            role = _source_role_for_name(doc["name"])
            cursor.execute(
                "UPDATE source_documents SET source_role = ? WHERE doc_id = ?",
                (role, doc_id)
            )

        # Canonical table used by ingestion, search, mock generation and citations.
        # Only default/unset roles are overwritten so manual assignments made through
        # POST /api/admin/materials/{doc_id}/role survive the next init_db() run.
        cursor.execute(
            "SELECT document_id, title, source_role FROM documents"
        )
        doc_rows = cursor.fetchall()
        for doc in doc_rows:
            current_role = doc["source_role"]
            if current_role not in (None, "", "supporting_material"):
                continue
            role = _source_role_for_name(doc["title"])
            cursor.execute(
                "UPDATE documents SET source_role = ? WHERE document_id = ?",
                (role, doc["document_id"]),
            )

        conn.commit()

        # Log categorization summary (only reached when a real pass ran)
        print("  Material categorization complete:")
        for role in ["pyq_phase_paper", "regulatory_core", "amendment_tracking", "essay_examples", "supporting_material"]:
            cursor.execute("SELECT COUNT(*) FROM documents WHERE source_role = ?", (role,))
            count = cursor.fetchone()[0]
            print(f"  documents.{role}: {count}")

    except Exception as e:
        print(f"Material categorization error: {e}")
        conn.rollback()
        raise


def _run_migration_004(conn: sqlite3.Connection | None = None) -> None:
    """Execute Phase 4 material categorization migration."""
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()

    try:
        migration_path = BACKEND_DIR / "migrations" / "004_material_categorization.sql"

        if not migration_path.exists():
            return  # Migration file optional

        with open(migration_path, "r") as f:
            migration_sql = f.read()

        # SQLite has no "ADD COLUMN IF NOT EXISTS"; on databases where the column was
        # already added (or where documents.source_role already exists from
        # _populate_source_role_on_documents), re-running the ALTER raises
        # "duplicate column name: source_role" on every init_db() call.
        if "source_role" in _table_columns(conn, "source_documents"):
            migration_sql = "\n".join(
                line
                for line in migration_sql.splitlines()
                if "ADD COLUMN source_role" not in line
            )

        conn.executescript(migration_sql)

        # Run categorization logic
        _categorize_materials(conn)

        if owns_conn:
            conn.commit()

    except Exception as e:
        print(f"Phase 4 migration error: {e}")
        if owns_conn:
            conn.rollback()
            conn.close()


_INITIALIZED_DB_PATHS: set[str] = set()
# Re-entrant: init_db() is called from request handlers, the APScheduler jobs and
# the daemon threads main.py spawns, all sharing one SQLite file.
_INIT_LOCK = threading.RLock()


def init_db() -> None:
    # Guard: migrations/schema work only needs to run once per database file.
    # init_db() is called by many endpoints (search_sources, save_question,
    # record_mock, dashboard_data, ...); without this guard every request re-ran
    # migration scripts, index creation and topic seeding. If the DB file is
    # deleted while the process lives, the exists() check forces a full re-init.
    db_key = str(DB_PATH.resolve())
    if db_key in _INITIALIZED_DB_PATHS and DB_PATH.exists():
        return
    with _INIT_LOCK:
        # _INITIALIZED_DB_PATHS is only published at the END of the init below, so two
        # concurrent first-time callers both passed the unlocked check and both ran
        # _ensure_runtime_schema; the loser died on "duplicate column name: option_e".
        db_key = str(DB_PATH.resolve())
        if db_key in _INITIALIZED_DB_PATHS and DB_PATH.exists():
            return
        _init_db_uncached(db_key)


def _init_db_uncached(db_key: str) -> None:
    conn = get_connection()
    conn.executescript(SCHEMA)
    _ensure_runtime_schema(conn)
    _create_performance_indexes(conn)
    seed_topics(conn)
    conn.commit()

    # Run Phase 1 migration (FTS5 content intelligence)
    try:
        create_fts5_index(conn)
    except Exception as e:
        print(f"Phase 1 migration already applied or error: {e}")

    # Run Phase 2 migration (amendment automation)
    try:
        _run_migration_002(conn)
    except Exception as e:
        print(f"Phase 2 migration already applied or error: {e}")

    # Run Phase 4 migration (material categorization)
    try:
        # Order matters: _run_migration_004 creates source_documents.source_role and
        # categorizes BOTH tables. Running _populate_source_role_on_documents first
        # used to fail on fresh databases ("no such column: sd.source_role"), roll
        # back the ALTER it had just made, and leave documents uncategorized until
        # the second init_db() call.
        _run_migration_004(conn)
        # Legacy bridge: only meaningful when the legacy table actually has rows.
        # On fresh installs source_documents is empty, and running it would NULL out
        # documents.source_role for every doc still marked 'supporting_material'
        # (empty scalar subquery -> NULL) on every init_db() call.
        legacy_docs = conn.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0]
        if legacy_docs:
            _populate_source_role_on_documents(conn)
    except Exception as e:
        print(f"Phase 4 migration error: {e}")

    # Rebuild PYQ attempt tables if they still carry the legacy unsatisfiable FKs.
    try:
        _repair_pyq_schema(conn)
        conn.commit()
    except Exception as e:
        print(f"PYQ schema repair error: {e}")

    # Knowledge layer: five-option PYQ rebuild + facts/templates/fulltext tables.
    try:
        _migrate_pyq_table_v2(conn)
        conn.commit()
    except Exception as e:
        print(f"PYQ table v2 migration error: {e}")

    try:
        _run_migration_005(conn)
        conn.commit()
    except Exception as e:
        print(f"Phase 5 migration already applied or error: {e}")

    try:
        _run_migration_006(conn)
        conn.commit()
    except Exception as e:
        print(f"Phase 6 update-tracker migration already applied or error: {e}")

    conn.close()
    _INITIALIZED_DB_PATHS.add(db_key)


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _ensure_runtime_schema(conn: sqlite3.Connection) -> None:
    """Apply additive schema fixes needed by existing local SQLite databases."""

    question_columns = _table_columns(conn, "questions")
    additions = {
        "tested_fact": "TEXT",
        "trap_logic": "TEXT",
        "source_policy": "TEXT",
        # Knowledge layer (plan v6): five options, verification, fact linkage
        "option_e": "TEXT",
        "verified_at": "TEXT",
        "verification_details": "TEXT",
        "subject_id": "TEXT",
        "fact_id": "TEXT",
    }
    for column, column_type in additions.items():
        if column not in question_columns:
            conn.execute(f"ALTER TABLE questions ADD COLUMN {column} {column_type}")

    # documents.source_role is consumed by _categorize_materials / the PYQ and admin
    # endpoints. Creating it here (before the Phase 4 migration runs) makes the first
    # init_db() on a fresh database fully successful instead of erroring once and
    # self-healing only on the second call.
    doc_columns = _table_columns(conn, "documents")
    if "source_role" not in doc_columns:
        conn.execute("ALTER TABLE documents ADD COLUMN source_role TEXT DEFAULT 'supporting_material'")

    # Plan v6 6.2: persisted descriptive grading results feed the readiness
    # aggregate mapping (Paper-1 descriptive × 1/3 + Paper-2 objective × 2/3).
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS descriptive_scores (
            score_id TEXT PRIMARY KEY,
            exam TEXT NOT NULL,
            year INTEGER,
            components_json TEXT NOT NULL,
            total_score REAL NOT NULL,
            total_max_marks REAL NOT NULL,
            total_pct REAL NOT NULL,
            cutoff_pct REAL,
            cleared_cutoff INTEGER,
            ai_status_json TEXT,
            graded_at TEXT NOT NULL
        )
        """
    )


def _repair_pyq_schema(conn: sqlite3.Connection) -> None:
    """Rebuild the PYQ attempt tables without unsatisfiable foreign keys.

    The legacy migration 001/004 schema declared:
    - pyq_sessions.pyq_source_doc_id  -> source_documents(doc_id)
    - pyq_question_attempts.question_id -> questions(question_id)

    Neither can be satisfied by the canonical flow:
    - submit_pyq_attempt inserts pyq_source_doc_id = 0, and source_documents is not
      populated on fresh installations (ingestion writes to documents), so the FK
      fails on every submission.
    - PYQ question ids (PYQ_DOC{id}_Q{n}) are never inserted into `questions`, so
      the second FK also fails on every attempt row.

    Rebuild both tables without those FKs. Rows (if any) are preserved. The rebuild
    uses a scratch table (create -> copy -> drop old -> rename) so a failure in the
    middle never strands the original table under a legacy name.
    """
    fk = conn.execute("PRAGMA foreign_key_list(pyq_sessions)").fetchall()
    if fk:
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            conn.execute("DROP TABLE IF EXISTS pyq_sessions_new")
            conn.executescript(
                """
                CREATE TABLE pyq_sessions_new (
                    pyq_id TEXT PRIMARY KEY,
                    pyq_source_doc_id INTEGER NOT NULL,
                    pyq_title TEXT NOT NULL,
                    phase_number INTEGER,
                    year INTEGER,
                    paper_number INTEGER,
                    started_at TEXT,
                    submitted_at TEXT,
                    total_questions INTEGER,
                    score INTEGER,
                    accuracy REAL,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                INSERT INTO pyq_sessions_new
                (pyq_id, pyq_source_doc_id, pyq_title, phase_number, year, paper_number,
                 started_at, submitted_at, total_questions, score, accuracy, status, created_at)
                SELECT pyq_id, pyq_source_doc_id, pyq_title, phase_number, year, paper_number,
                       started_at, submitted_at, total_questions, score, accuracy, status, created_at
                FROM pyq_sessions
                """
            )
            conn.execute("DROP TABLE pyq_sessions")
            conn.execute("ALTER TABLE pyq_sessions_new RENAME TO pyq_sessions")
        finally:
            conn.execute("PRAGMA foreign_keys = ON")

    fk = conn.execute("PRAGMA foreign_key_list(pyq_question_attempts)").fetchall()
    if fk:
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            conn.execute("DROP TABLE IF EXISTS pyq_question_attempts_new")
            conn.executescript(
                """
                CREATE TABLE pyq_question_attempts_new (
                    attempt_id TEXT PRIMARY KEY,
                    pyq_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    question_number INTEGER,
                    selected_answer TEXT,
                    official_answer TEXT,
                    is_correct BOOLEAN,
                    time_spent_seconds INTEGER,
                    marked_for_review BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                INSERT INTO pyq_question_attempts_new
                (attempt_id, pyq_id, question_id, question_number, selected_answer,
                 official_answer, is_correct, time_spent_seconds, marked_for_review, created_at)
                SELECT attempt_id, pyq_id, question_id, question_number, selected_answer,
                       official_answer, is_correct, time_spent_seconds, marked_for_review, created_at
                FROM pyq_question_attempts
                """
            )
            conn.execute("DROP TABLE pyq_question_attempts")
            conn.execute("ALTER TABLE pyq_question_attempts_new RENAME TO pyq_question_attempts")
        finally:
            conn.execute("PRAGMA foreign_keys = ON")


def _migrate_pyq_table_v2(conn: sqlite3.Connection) -> None:
    """Rebuild previous_year_questions for five options + exam discriminator.

    Migration 003 created the table with CHECK(correct_option IN ('A','B','C','D'))
    which cannot be ALTERed; rebuild via scratch table preserving rows (same
    pattern as _repair_pyq_schema). Skipped when option_e already exists.
    """
    columns = _table_columns(conn, "previous_year_questions")
    v2_schema = """
            CREATE TABLE {table} (
                pyq_id TEXT PRIMARY KEY,
                exam TEXT NOT NULL DEFAULT 'IFSCA',
                year INTEGER NOT NULL,
                phase INTEGER NOT NULL,
                paper INTEGER NOT NULL,
                section TEXT,
                subject_id TEXT,
                question_number INTEGER,
                question_text TEXT NOT NULL,
                direction_text TEXT,
                option_a TEXT,
                option_b TEXT,
                option_c TEXT,
                option_d TEXT,
                option_e TEXT,
                correct_option TEXT CHECK(correct_option IN ('A', 'B', 'C', 'D', 'E')),
                hint TEXT,
                marks INTEGER NOT NULL DEFAULT 1,
                negative_marking REAL DEFAULT 0.25,
                topic_id TEXT,
                difficulty TEXT CHECK(difficulty IN ('EASY', 'MEDIUM', 'HARD')),
                incomplete BOOLEAN DEFAULT 0,
                incomplete_reason TEXT,
                attempted BOOLEAN DEFAULT 0,
                user_answer TEXT,
                is_correct BOOLEAN,
                time_spent_seconds INTEGER,
                attempt_date TEXT,
                source_pdf TEXT NOT NULL DEFAULT 'question_bank',
                source_line_start INTEGER,
                source_line_end INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
    """
    if not columns:
        # Fresh DB: migration 003 is not wired into init_db, so create v2 directly.
        conn.executescript(v2_schema.format(table="previous_year_questions"))
        return
    if "option_e" in columns:
        return
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("DROP TABLE IF EXISTS previous_year_questions_v2")
        conn.executescript(v2_schema.format(table="previous_year_questions_v2"))
        old_columns = _table_columns(conn, "previous_year_questions")
        copy_columns = [
            name for name in (
                "pyq_id", "year", "phase", "paper", "section", "question_number",
                "question_text", "option_a", "option_b", "option_c", "option_d",
                "correct_option", "marks", "negative_marking", "topic_id",
                "difficulty", "attempted", "user_answer", "is_correct",
                "time_spent_seconds", "attempt_date", "source_pdf",
                "source_line_start", "source_line_end", "created_at",
            ) if name in old_columns
        ]
        selection = ", ".join(copy_columns)
        conn.execute(
            f"INSERT INTO previous_year_questions_v2 ({selection}) SELECT {selection} FROM previous_year_questions"
        )
        conn.execute("DROP TABLE previous_year_questions")
        conn.execute("ALTER TABLE previous_year_questions_v2 RENAME TO previous_year_questions")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _run_migration_005(conn: sqlite3.Connection | None = None) -> None:
    """Execute Phase 5 knowledge-layer migration (additive + FTS5 virtual table)."""
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()
    try:
        migration_path = BACKEND_DIR / "migrations" / "005_knowledge_layer.sql"
        if not migration_path.exists():
            return
        conn.executescript(migration_path.read_text(encoding="utf-8"))
        if owns_conn:
            conn.commit()
    except Exception as e:
        print(f"Phase 5 migration error: {e}")
        if owns_conn:
            conn.rollback()
            conn.close()


def _run_migration_006(conn: sqlite3.Connection | None = None) -> None:
    """Execute update-tracker migration (amendment_updates + tracker_runs)."""
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()
    try:
        migration_path = BACKEND_DIR / "migrations" / "006_update_tracker.sql"
        if not migration_path.exists():
            return
        conn.executescript(migration_path.read_text(encoding="utf-8"))
        if owns_conn:
            conn.commit()
    except Exception as e:
        print(f"Update-tracker migration error: {e}")
        if owns_conn:
            conn.rollback()
            conn.close()


def _create_performance_indexes(conn: sqlite3.Connection) -> None:
    """Create indexes for performance optimization (Week 6).

    Per Context7 docs for SQLite: indexes dramatically improve query performance
    for WHERE clauses, JOIN conditions, and ORDER BY operations. We index:
    - topic + accuracy for weak area detection (dashboard load optimization)
    - is_correct for score calculations
    - created_at for time-based filtering
    - question_id for source lookups
    """
    try:
        before = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_%'"
        ).fetchone()[0]
        # Dashboard load optimization: weak area detection
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_attempts_topic_correct "
            "ON question_attempts(topic, is_correct) "
            "WHERE is_correct IS NOT NULL"
        )

        # Mock submission optimization: find all attempts for scoring
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_attempts_mock_id "
            "ON question_attempts(mock_id)"
        )

        # Amendment tracking optimization: Recent amendments filtering
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_amendments_created_at "
            "ON amendments(created_at)"
        )

        # Amendment topic drilling optimization
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_amendments_topic "
            "ON amendments(topic)"
        )

        # Generated questions optimization: fetch by topic/difficulty
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_generated_questions_topic_difficulty "
            "ON generated_questions(topic, difficulty)"
        )

        # Essay scoring optimization: find essays by topic tags
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_essay_submissions_topic_tags "
            "ON essay_submissions(topic_tags)"
        )

        # Review items scheduling optimization: spaced repetition due items
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_review_items_due_at "
            "ON review_items(due_at)"
        )

        # Topic stats optimization: weak area ranking
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_topic_stats_accuracy "
            "ON topic_stats(accuracy_pct)"
        )

        conn.commit()
        # Only log when new indexes were actually created; this function runs inside
        # init_db() which is called by many endpoints, so unconditional logging
        # spammed one line per request.
        after = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_%'"
        ).fetchone()[0]
        if after > before:
            print(f"[OK] Created {after - before} performance indexes")
    except sqlite3.OperationalError as e:
        # Indexes may already exist; this is not an error
        if "already exists" in str(e).lower():
            pass
        else:
            print(f"[WARNING] Index creation warning: {e}")


def _seed_topics_fallback(conn: sqlite3.Connection) -> None:
    """Fallback topic seeding if migration path doesn't use seed_topics.

    Per Context7 docs for SQLite: idempotent inserts with ON CONFLICT IGNORE.
    """
    for topic in TOPIC_DEFINITIONS:
        conn.execute(
            """
            INSERT OR REPLACE INTO topics
            (topic_id, parent_topic_id, phase, paper, display_name, description, base_weight, exam_priority, is_amendment_sensitive)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                topic["topic_id"],
                None,
                "phase_2",
                "paper_2",
                topic["display_name"],
                topic["description"],
                topic["base_weight"],
                topic["exam_priority"],
                int(topic["is_amendment_sensitive"]),
            ),
        )
    conn.commit()


FACT_AUTHORITY_RANK = {
    "OFFICIAL_REGULATORY": 5,
    "ICSI_STUDY": 4,
    "IFSCA_PUBLICATION": 4,
    "CONSULTING": 2,
    "CURRENT_AFFAIRS": 2,
    "COACHING": 1,
}
FACT_YIELD_RANK = {"HIGH": 2, "MED": 1, "LOW": 0}

ROLE_TO_AUTHORITIES = {
    "regulatory_core": {"OFFICIAL_REGULATORY", "ICSI_STUDY"},
    "amendment_tracking": {"OFFICIAL_REGULATORY", "IFSCA_PUBLICATION"},
    "essay_examples": {"IFSCA_PUBLICATION", "CONSULTING"},
    "consulting_case": {"CONSULTING"},
    "supporting_material": set(FACT_AUTHORITY_RANK),
}

PYQ_MARKS_BY_PAPER = {
    ("IFSCA", 1, 1): 1,
    ("IFSCA", 1, 2): 2,
    ("IFSCA", 2, 2): 2,
    ("SEBI", 1, 1): 1.25,
    ("SEBI", 1, 2): 2,
    ("SEBI", 2, 2): 1,
}


def bootstrap_from_knowledge(force: bool = False) -> dict[str, Any]:
    """Load the committed knowledge pack into SQLite (zero file dependence).

    Idempotent: skipped when knowledge_meta.bootstrapped is set unless force.
    """
    init_db()
    conn = get_connection()
    try:
        already = conn.execute(
            "SELECT value FROM knowledge_meta WHERE key = 'bootstrapped'"
        ).fetchone()
        if already and not force:
            return {"status": "skipped", "reason": "already bootstrapped"}

        facts = knowledge.load_all_facts()
        for fact in facts:
            conn.execute(
                """
                INSERT OR REPLACE INTO facts
                (fact_id, domain, module, statement, detail, numbers_json, effective_date,
                 authority, yield, source_doc, source_page, source_ref, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fact["fact_id"], fact.get("domain"), fact.get("module"),
                    fact["statement"], fact.get("detail"),
                    json.dumps(fact.get("numbers") or {}),
                    fact.get("effective_date"), fact["authority"], fact["yield"],
                    fact["source_doc"], fact.get("source_page"), fact.get("source_ref"),
                    json.dumps(fact.get("tags") or []),
                ),
            )
            conn.execute("DELETE FROM fact_topics WHERE fact_id = ?", (fact["fact_id"],))
            conn.execute("DELETE FROM fact_subjects WHERE fact_id = ?", (fact["fact_id"],))
            for topic_id in fact.get("topic_ids") or []:
                conn.execute(
                    "INSERT OR REPLACE INTO fact_topics (fact_id, topic_id) VALUES (?, ?)",
                    (fact["fact_id"], topic_id),
                )
            for subject_id in fact.get("subject_ids") or []:
                conn.execute(
                    "INSERT OR REPLACE INTO fact_subjects (fact_id, subject_id) VALUES (?, ?)",
                    (fact["fact_id"], subject_id),
                )
        conn.execute("DELETE FROM fact_fts")
        for fact in facts:
            conn.execute(
                "INSERT INTO fact_fts (fact_id, statement, detail, tags) VALUES (?, ?, ?, ?)",
                (
                    fact["fact_id"],
                    fact["statement"],
                    fact.get("detail") or "",
                    " ".join(fact.get("tags") or []),
                ),
            )

        patterns = knowledge.load_exam_patterns()
        for template in patterns.get("templates", []):
            conn.execute(
                """
                INSERT OR REPLACE INTO exam_templates
                (template_id, exam, name, phase, paper, total_questions, marks_per_question,
                 total_marks, time_limit_minutes, cutoff_pct, aggregate_cutoff_pct,
                 sections_json, syllabus_units_json, descriptive_components_json, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template["template_id"], template.get("exam"), template.get("name"),
                    template.get("phase"), template.get("paper"),
                    template.get("total_questions"), template.get("marks_per_question"),
                    template.get("total_marks"), template.get("time_limit_minutes"),
                    template.get("cutoff_pct"), template.get("aggregate_cutoff_pct"),
                    json.dumps(template.get("sections") or []),
                    json.dumps(template.get("syllabus_units") or []),
                    json.dumps(template.get("descriptive_components") or []),
                    template.get("notes"),
                ),
            )

        objective = knowledge.load_objective()
        for question in objective:
            exam = question.get("exam") or "IFSCA"
            phase = question.get("phase") or 0
            paper = question.get("paper") or 0
            marks = PYQ_MARKS_BY_PAPER.get((exam, phase, paper), 1)
            options = question.get("options") or {}
            conn.execute(
                """
                INSERT OR REPLACE INTO previous_year_questions
                (pyq_id, exam, year, phase, paper, section, subject_id, question_number,
                 question_text, direction_text, option_a, option_b, option_c, option_d,
                 option_e, correct_option, hint, marks, negative_marking, topic_id,
                 incomplete, incomplete_reason, source_pdf)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    question["pyq_key"], exam, question.get("year") or 0, phase, paper,
                    question.get("section"), question.get("subject_id"),
                    question.get("qnum"), question.get("question_text"),
                    question.get("direction_text"),
                    options.get("A"), options.get("B"), options.get("C"),
                    options.get("D"), options.get("E"),
                    question.get("answer"), question.get("hint") or None,
                    marks, round(marks * 0.25, 4),
                    question.get("subject_id"),
                    1 if question.get("incomplete") else 0,
                    question.get("incomplete_reason"),
                    "question_bank",
                ),
            )

        descriptive = knowledge.load_descriptive()
        for item in descriptive:
            conn.execute(
                """
                INSERT OR REPLACE INTO descriptive_items
                (item_id, exam, item_type, year, phase, paper, section, subject_id,
                 question_number, prompt_text, topics_json, passage_text, model_answer,
                 model_answers_json, sub_questions_json, marks, word_limit_min,
                 word_limit_max, title_required, incomplete, incomplete_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["item_key"], item.get("exam"), item.get("item_type"),
                    item.get("year"), item.get("phase"), item.get("paper"),
                    item.get("section"), item.get("subject_id"),
                    str(item.get("qnum")) if item.get("qnum") is not None else None,
                    item.get("prompt_text") or "",
                    json.dumps(item.get("topics") or []),
                    item.get("passage_text") or "",
                    item.get("model_answer") or "",
                    json.dumps(item.get("model_answers") or {}),
                    json.dumps(item.get("sub_questions") or []),
                    item.get("marks"), item.get("word_limit_min"),
                    item.get("word_limit_max"),
                    1 if item.get("title_required") else 0,
                    1 if item.get("incomplete") else 0,
                    item.get("incomplete_reason"),
                ),
            )

        act = knowledge.load_act_text()
        conn.execute(
            """
            INSERT OR REPLACE INTO document_fulltext
            (document_id, title, source_doc, line_count, full_text)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("doc_ifsca_act_2019", act["title"], act["source_doc"], act["line_count"], act["text"]),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO documents
            (document_id, title, category, source_type, local_pdf_path, local_text_path,
             sha256, pages, line_count, status, notes)
            VALUES (?, ?, ?, ?, NULL, NULL, NULL, 0, ?, 'indexed', 'knowledge pack')
            """,
            ("doc_ifsca_act_2019", "IndiaCode IFSCA Act 2019 current", "Regulations", "knowledge_pack", act["line_count"]),
        )

        meta = knowledge.load_manifest()
        for key, value in (
            ("bootstrapped", "1"),
            ("schema_version", str(meta.get("schema_version", knowledge.SCHEMA_VERSION))),
            ("total_facts", str(len(facts))),
            ("objective_questions", str(len(objective))),
            ("descriptive_items", str(len(descriptive))),
        ):
            conn.execute(
                "INSERT OR REPLACE INTO knowledge_meta (key, value) VALUES (?, ?)",
                (key, value),
            )
        conn.commit()
        return {
            "status": "ok",
            "facts": len(facts),
            "objective_questions": len(objective),
            "descriptive_items": len(descriptive),
            "exam_templates": len(patterns.get("templates", [])),
        }
    finally:
        conn.close()


def _fact_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    fact = dict(row)
    fact_id = fact["fact_id"]
    conn = get_connection()
    try:
        fact["topic_ids"] = [
            item["topic_id"]
            for item in conn.execute("SELECT topic_id FROM fact_topics WHERE fact_id = ?", (fact_id,))
        ]
        fact["subject_ids"] = [
            item["subject_id"]
            for item in conn.execute("SELECT subject_id FROM fact_subjects WHERE fact_id = ?", (fact_id,))
        ]
    finally:
        conn.close()
    try:
        fact["numbers"] = json.loads(fact.get("numbers_json") or "{}")
    except json.JSONDecodeError:
        fact["numbers"] = {}
    try:
        fact["tags"] = json.loads(fact.get("tags_json") or "[]")
    except json.JSONDecodeError:
        fact["tags"] = []
    return fact


def _fact_rank(fact: dict[str, Any]) -> tuple[int, int, str]:
    return (
        FACT_AUTHORITY_RANK.get(fact.get("authority") or "", 0),
        FACT_YIELD_RANK.get(fact.get("yield") or "", 0),
        fact.get("effective_date") or "",
    )


def facts_for_topic(
    topic_id: str,
    limit: int = 8,
    authority_filter: set[str] | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """Facts tagged with the topic (or shared subject), best authority/yield first."""
    init_db()
    conn = get_connection()
    try:
        if topic_id.startswith("SUBJ_"):
            rows = conn.execute(
                """
                SELECT f.* FROM facts f
                JOIN fact_subjects fs ON fs.fact_id = f.fact_id
                WHERE fs.subject_id = ?
                """,
                (topic_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT f.* FROM facts f
                JOIN fact_topics ft ON ft.fact_id = f.fact_id
                WHERE ft.topic_id = ?
                """,
                (topic_id,),
            ).fetchall()
    finally:
        conn.close()
    facts = [_fact_row_to_dict(row) for row in rows]
    if authority_filter:
        filtered = [fact for fact in facts if fact.get("authority") in authority_filter]
        if filtered:
            facts = filtered
    if query:
        tokens = [token for token in re.findall(r"[a-z0-9]+", query.lower()) if len(token) > 2]
        if tokens:
            scored = [
                (sum(1 for token in tokens if token in (fact["statement"] + " " + (fact.get("detail") or "")).lower()), fact)
                for fact in facts
            ]
            matched = [item for hits, item in scored if hits > 0]
            if matched:
                facts = matched
    facts.sort(key=_fact_rank, reverse=True)
    return facts[: max(1, min(limit, 25))]


def search_facts(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """FTS over committed facts with LIKE fallback; ranked by authority/yield."""
    init_db()
    tokens = re.findall(r"[A-Za-z0-9_]+", query or "")[:12]
    conn = get_connection()
    try:
        rows: list[sqlite3.Row] = []
        if tokens:
            try:
                expression = " OR ".join(tokens)
                rows = conn.execute(
                    """
                    SELECT f.* FROM facts f
                    JOIN fact_fts x ON x.fact_id = f.fact_id
                    WHERE fact_fts MATCH ?
                    LIMIT ?
                    """,
                    (expression, max(1, min(limit * 3, 60))),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
        if not rows and tokens:
            like = f"%{query.strip()}%"
            rows = conn.execute(
                "SELECT * FROM facts WHERE statement LIKE ? OR detail LIKE ? LIMIT ?",
                (like, like, max(1, min(limit * 3, 60))),
            ).fetchall()
    finally:
        conn.close()
    facts = [_fact_row_to_dict(row) for row in rows]
    facts.sort(key=_fact_rank, reverse=True)
    return facts[: max(1, min(limit, 25))]


def fact_as_chunk(fact: dict[str, Any]) -> dict[str, Any]:
    """Shape a fact like a legacy source chunk so the generation stack works unchanged."""
    excerpt = fact["statement"]
    if fact.get("detail"):
        excerpt = f"{excerpt} {fact['detail']}"
    tags = list(fact.get("tags") or [])
    return {
        "chunk_id": fact["fact_id"],
        "document_id": f"fact:{fact.get('domain') or 'knowledge'}",
        "title": fact.get("source_doc") or "Knowledge pack",
        "category": fact.get("authority") or "OFFICIAL_REGULATORY",
        "page_start": fact.get("source_page"),
        "page_end": fact.get("source_page"),
        "line_start": None,
        "line_end": None,
        "topic_tags": list(fact.get("topic_ids") or []) + list(fact.get("subject_ids") or []),
        "excerpt": excerpt[:1200],
        "rank": 0.0,
        "authority_score": round(FACT_AUTHORITY_RANK.get(fact.get("authority") or "", 0) / 5.0, 3),
        "exam_signal_score": round(FACT_YIELD_RANK.get(fact.get("yield") or "", 0) / 2.0, 3),
        "exam_material_score": 0.5,
        "exam_source_score": round(FACT_AUTHORITY_RANK.get(fact.get("authority") or "", 0) / 5.0, 3),
        "citation_note": f"[{fact.get('source_doc') or 'knowledge pack'}{', ' + str(fact['source_ref']) if fact.get('source_ref') else ''}]",
        "source_ref": fact.get("source_ref"),
        "tags": tags,
    }


def ingest_extracted_pdfs(conn: sqlite3.Connection | None = None) -> int:
    """
    Bulk load all extracted PDF files from /extracted_pdfs/ into source_chunks table.
    Chunks text by line groups (~100 lines per chunk) for optimal search performance.

    Returns: Total number of chunks created
    """
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        chunk_count = 0
        lines_per_chunk = 100  # Chunk size for FTS5 optimization

        # Get list of all extracted PDF files
        extracted_files = sorted(EXTRACTED_DIR.glob("*.txt"))

        for file_path in extracted_files:
            # Extract doc name from filename (remove numbering prefix if present)
            doc_name = file_path.stem

            # Insert document metadata
            doc_result = conn.execute(
                """
                INSERT OR IGNORE INTO source_documents (name, doc_type, source_file_path)
                VALUES (?, ?, ?)
                """,
                (doc_name, "extracted_pdf", str(file_path))
            )
            doc_id = doc_result.lastrowid

            # If document was already inserted, fetch its ID
            if doc_id == 0:
                doc_id = conn.execute(
                    "SELECT doc_id FROM source_documents WHERE name = ?",
                    (doc_name,)
                ).fetchone()[0]

            # Read file and chunk it
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"Warning: Failed to read {file_path}: {e}")
                continue

            # Create chunks from lines
            chunk_sequence = 0
            for start_idx in range(0, len(lines), lines_per_chunk):
                end_idx = min(start_idx + lines_per_chunk, len(lines))
                chunk_text = "".join(lines[start_idx:end_idx])

                # Skip empty chunks
                if not chunk_text.strip():
                    continue

                # Extract potential section title from first line of chunk
                section_title = lines[start_idx].strip()[:100] if start_idx < len(lines) else ""

                # Estimate page number (rough: ~50 lines per page)
                page_num = (start_idx // 50) + 1

                # Insert chunk
                conn.execute(
                    """
                    INSERT INTO source_chunks
                    (doc_id, start_line, end_line, chunk_text, section_title, page_num, chunk_sequence)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (doc_id, start_idx, end_idx, chunk_text, section_title, page_num, chunk_sequence)
                )
                chunk_sequence += 1
                chunk_count += 1

        if owns_conn:
            conn.commit()

        return chunk_count

    except Exception as e:
        print(f"Error during PDF ingestion: {e}")
        if owns_conn:
            conn.rollback()
        raise
    finally:
        if owns_conn:
            conn.close()


def create_fts5_index(conn: sqlite3.Connection | None = None) -> None:
    """
    Execute migration to create FTS5 tables and triggers.
    Reads and executes 001_content_intelligence.sql migration script.
    """
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        migration_path = BACKEND_DIR / "migrations" / "001_content_intelligence.sql"

        if not migration_path.exists():
            raise FileNotFoundError(f"Migration file not found: {migration_path}")

        with open(migration_path, "r") as f:
            migration_sql = f.read()

        # Execute migration script
        conn.executescript(migration_sql)

        if owns_conn:
            conn.commit()

    except Exception as e:
        print(f"FTS5 migration error: {e}")
        if owns_conn:
            conn.rollback()
        raise
    finally:
        if owns_conn:
            conn.close()


def _run_migration_002(conn: sqlite3.Connection | None = None) -> None:
    """Execute Phase 2 amendment automation migration."""
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        migration_path = BACKEND_DIR / "migrations" / "002_amendment_automation.sql"

        if not migration_path.exists():
            return  # Migration file optional

        with open(migration_path, "r") as f:
            migration_sql = f.read()

        conn.executescript(migration_sql)

        if owns_conn:
            conn.commit()

    except Exception as e:
        print(f"Phase 2 migration error: {e}")
        if owns_conn:
            conn.close()
        print(f"Error during FTS5 index creation: {e}")
        if owns_conn:
            conn.rollback()
        raise
    finally:
        if owns_conn:
            conn.close()


def format_citation_note(source_chunk: dict[str, Any], page_num: int | None = None) -> str:
    """
    Format a citation note in academic format: [Document Name, Section X, p.YYY]

    Args:
        source_chunk: Dict with keys: 'name'/'title', 'section_title', 'page_start', 'page_end'
        page_num: Override page number if provided

    Returns:
        Formatted citation string like "[IFSCA Reg 2027, Section 5.2, p.180]"
    """
    title = source_chunk.get("name") or source_chunk.get("title") or "Source Document"
    section = source_chunk.get("section_title") or ""
    page = page_num or source_chunk.get("page_start") or source_chunk.get("page_num") or "?"

    citation_parts = [title.strip()]
    if section and section.strip():
        citation_parts.append(f"Section {section.strip()}")

    citation = ", ".join(citation_parts)
    return f"[{citation}, p.{page}]"


def link_question_to_source(
    question_id: str,
    source_chunk_id: int,
    authority_score: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> None:
    """
    Link a question to its authoritative source chunk.

    Creates a record in question_sources table with authority score.

    Args:
        question_id: ID of the question being linked
        source_chunk_id: ID of the source chunk providing authority
        authority_score: Authority score (0-100), auto-calculated if None
        conn: Optional database connection (creates new if None)
    """
    owns_conn = conn is None
    if owns_conn:
        conn = get_connection()

    try:
        # Auto-calculate authority score if not provided
        if authority_score is None:
            # Retrieve chunk's source document info
            chunk_row = conn.execute(
                """
                SELECT sd.doc_type, sd.category
                FROM source_chunks sc
                JOIN source_documents sd ON sc.doc_id = sd.doc_id
                WHERE sc.chunk_id = ? LIMIT 1
                """,
                (source_chunk_id,),
            ).fetchone()

            if chunk_row:
                doc_type = chunk_row["doc_type"] or "extracted_pdf"
                category = chunk_row["category"] or "default"
                authority_score = int(calculate_source_authority(doc_type, category, exam_signal=0))
            else:
                authority_score = 50  # Default if chunk not found

        # Insert or replace the link
        conn.execute(
            """
            INSERT OR REPLACE INTO question_sources
            (question_id, source_chunk_id, authority_score)
            VALUES (?, ?, ?)
            """,
            (question_id, source_chunk_id, authority_score),
        )
        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def get_source_authority_for_chunk(chunk_id: int, conn: sqlite3.Connection | None = None) -> int:
    """
    Retrieve authority score for a specific source chunk.

    Args:
        chunk_id: ID of the source chunk
        conn: Database connection (optional)

    Returns:
        Authority score (0-100), or 50 if not found
    """
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        result = conn.execute(
            """
            SELECT authority_score
            FROM question_sources
            WHERE source_chunk_id = ?
            ORDER BY authority_score DESC
            LIMIT 1
            """,
            (chunk_id,)
        ).fetchone()

        score = result[0] if result else 50  # Default score if not found

        # Verify score is in valid range
        return max(0, min(100, int(score)))

    finally:
        if owns_conn:
            conn.close()


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def table_count(table_name: str) -> int:
    conn = get_connection()
    try:
        value = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        return int(value or 0)
    finally:
        conn.close()


def get_ingestion_status() -> dict[str, int]:
    init_db()
    return {
        "documents": table_count("documents"),
        "chunks": table_count("document_chunks"),
        "fts_rows": table_count("document_chunk_fts"),
        "topics": table_count("topics"),
        "chunk_topic_links": table_count("chunk_topics"),
        "questions": table_count("questions"),
        "amendments": table_count("amendment_events"),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def slugify(value: str, max_len: int = 72) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return value[:max_len] or "item"


def load_index() -> dict[str, Any]:
    if not INDEX_PATH.exists():
        return {}
    with INDEX_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data.get("index", data)


def infer_source_type(category: str, title: str) -> str:
    text = f"{category} {title}".lower()
    if "career" in text or "result" in text or "handout" in text or "syllabus" in text:
        return "exam_official"
    if "icsi" in text:
        return "icsi_study"
    if "bulletin" in text or "annual report" in text or "ifsca publications" in text:
        return "ifsca_publication"
    if "pwc" in text or "ey" in text or "grant thornton" in text or "kpmg" in text:
        return "professional_report"
    if "current" in text or "booster" in text:
        return "current_affairs"
    return "source_document"


def find_pdf_path(pdf_name: str) -> str | None:
    direct = SOURCE_PDF_DIR / pdf_name
    if direct.exists():
        return str(direct)
    matches = list((PROJECT_ROOT / "source_documents").rglob(pdf_name))
    return str(matches[0]) if matches else None


def estimate_page(line_number: int, total_lines: int, pages: int) -> int:
    if pages <= 0 or total_lines <= 0:
        return 1
    return max(1, min(pages, math.ceil((line_number / total_lines) * pages)))


def chunk_lines(lines: list[str], pages: int, target_words: int = 900) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    current: list[str] = []
    start_line = 1
    words = 0
    total_lines = len(lines)

    for index, line in enumerate(lines, start=1):
        current.append(line.rstrip())
        words += len(line.split())
        if words >= target_words:
            text = "\n".join(current).strip()
            if text:
                chunks.append(
                    {
                        "text": text,
                        "line_start": start_line,
                        "line_end": index,
                        "page_start": estimate_page(start_line, total_lines, pages),
                        "page_end": estimate_page(index, total_lines, pages),
                    }
                )
            current = []
            start_line = index + 1
            words = 0

    text = "\n".join(current).strip()
    if text:
        chunks.append(
            {
                "text": text,
                "line_start": start_line,
                "line_end": total_lines,
                "page_start": estimate_page(start_line, total_lines, pages),
                "page_end": estimate_page(total_lines, total_lines, pages),
            }
        )
    return chunks


def topic_tags_for_text(text: str, title: str = "", category: str = "") -> list[tuple[str, float]]:
    haystack = f"{title}\n{category}\n{text}".lower()
    scored: list[tuple[str, float]] = []
    for topic in TOPIC_DEFINITIONS:
        score = 0
        for keyword in topic["keywords"]:
            if keyword.lower() in haystack:
                score += 3 if keyword.lower() in f"{title} {category}".lower() else 1
        if score:
            confidence = min(1.0, 0.25 + (score / 10.0))
            scored.append((topic["topic_id"], round(confidence, 3)))
    scored.sort(key=lambda item: item[1], reverse=True)
    if not scored:
        return [("PH2_CURRENT_AFFAIRS", 0.2)]
    return scored[:4]


def topic_display(topic_id: str) -> str:
    return TOPIC_BY_ID.get(topic_id, {}).get("display_name", topic_id)


def ingest_documents(force: bool = False, limit: int | None = None) -> dict[str, Any]:
    init_db()
    index = load_index()
    txt_files = sorted(EXTRACTED_DIR.glob("*.txt"))
    if limit is not None:
        txt_files = txt_files[:limit]

    documents_seen = len(txt_files)
    documents_indexed = 0
    chunks_indexed = 0
    skipped_existing = 0
    errors: list[str] = []

    conn = get_connection()
    try:
        for txt_path in txt_files:
            try:
                meta = index.get(txt_path.name, {})
                title = meta.get("source") or txt_path.stem
                category = meta.get("category") or "Uncategorized"
                pages = int(meta.get("pages") or 0)
                source_type = infer_source_type(category, title)
                file_hash = sha256_file(txt_path)
                document_id = f"doc_{slugify(txt_path.stem, 56)}_{file_hash[:8]}"

                existing = conn.execute("SELECT document_id FROM documents WHERE document_id = ?", (document_id,)).fetchone()
                if existing and not force:
                    skipped_existing += 1
                    continue

                if force:
                    old = conn.execute("SELECT document_id FROM documents WHERE document_id = ?", (document_id,)).fetchone()
                    if old:
                        chunk_ids = [row["chunk_id"] for row in conn.execute("SELECT chunk_id FROM document_chunks WHERE document_id = ?", (document_id,))]
                        conn.execute("DELETE FROM chunk_topics WHERE chunk_id IN (%s)" % ",".join("?" for _ in chunk_ids), chunk_ids) if chunk_ids else None
                        conn.execute("DELETE FROM question_citations WHERE document_id = ?", (document_id,))
                        conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))
                        conn.execute("DELETE FROM document_chunk_fts WHERE document_id = ?", (document_id,))
                        conn.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))

                lines = txt_path.read_text(encoding="utf-8", errors="replace").splitlines()
                local_pdf_path = find_pdf_path(title)
                now = datetime.now().isoformat()
                conn.execute(
                    """
                    INSERT OR REPLACE INTO documents
                    (document_id, title, category, source_type, source_url, local_pdf_path, local_text_path,
                     sha256, pages, line_count, publication_date, downloaded_at, ingested_at, status, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        title,
                        category,
                        source_type,
                        None,
                        local_pdf_path,
                        str(txt_path),
                        file_hash,
                        pages,
                        len(lines),
                        None,
                        None,
                        now,
                        "indexed",
                        None,
                    ),
                )

                for chunk_number, chunk in enumerate(chunk_lines(lines, pages), start=1):
                    chunk_hash = hashlib.sha256(chunk["text"].encode("utf-8", errors="replace")).hexdigest()
                    chunk_id = f"{document_id}_chunk_{chunk_number:04d}"
                    tags = topic_tags_for_text(chunk["text"], title=title, category=category)
                    tag_ids = [topic_id for topic_id, _ in tags]
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO document_chunks
                        (chunk_id, document_id, page_start, page_end, line_start, line_end, text, token_estimate, chunk_hash)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chunk_id,
                            document_id,
                            chunk["page_start"],
                            chunk["page_end"],
                            chunk["line_start"],
                            chunk["line_end"],
                            chunk["text"],
                            max(1, len(chunk["text"]) // 4),
                            chunk_hash,
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO document_chunk_fts
                        (chunk_id, document_id, title, text, topic_tags, source_type)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (chunk_id, document_id, title, chunk["text"], " ".join(tag_ids), source_type),
                    )
                    for topic_id, confidence in tags:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO chunk_topics (chunk_id, topic_id, confidence, method)
                            VALUES (?, ?, ?, ?)
                            """,
                            (chunk_id, topic_id, confidence, "deterministic_keyword"),
                        )
                    chunks_indexed += 1

                documents_indexed += 1
                if documents_indexed % 10 == 0:
                    conn.commit()
            except Exception as exc:
                errors.append(f"{txt_path.name}: {exc}")
        conn.commit()

        # Categorize immediately so roles (pyq_phase_paper, regulatory_core, ...) are
        # correct right after ingestion instead of waiting for the next init_db().
        try:
            _categorize_materials(conn)
        except Exception as exc:
            errors.append(f"material categorization: {exc}")
    finally:
        conn.close()

    return {
        "status": "ok" if not errors else "partial",
        "documents_seen": documents_seen,
        "documents_indexed": documents_indexed,
        "chunks_indexed": chunks_indexed,
        "skipped_existing": skipped_existing,
        "errors": errors[:25],
    }


def fts_query(query: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9_]+", query)
    if not tokens:
        return ""
    return " OR ".join(tokens[:12])


def source_authority_score(category: str | None, title: str | None) -> float:
    category_score = SOURCE_CATEGORY_PRIORITY.get(category or "", 0.45)
    lower_title = (title or "").lower()
    title_bonus = 0.10 if any(hint in lower_title for hint in OFFICIAL_TITLE_HINTS) else 0.0
    recency_bonus = 0.08 if "2026" in lower_title else 0.06 if "2025" in lower_title else 0.03 if "2024" in lower_title else 0.0
    memory_penalty = -0.08 if any(token in lower_title for token in ["memory", "scribd", "coaching"]) else 0.0
    return round(max(0.0, min(1.0, category_score + title_bonus + recency_bonus + memory_penalty)), 3)


def exam_material_source_score(category: str | None, title: str | None, excerpt: str | None = "") -> float:
    """Score whether a source is acceptable for actual mock-question generation."""

    category = category or ""
    haystack = f"{title or ''}\n{excerpt or ''}".lower()
    score = 0.0
    if category == "Exam Papers (Memory-based)":
        score += 0.65
    elif category in {"Study Materials", "ICSI Materials"}:
        score += 0.45
    elif category == "IFSCA Career":
        score += 0.25
    elif category in {"IFSCA Regulations (TAS/PSR/RI)", "IFSCA Publications (Reports/Bulletins)"}:
        score += 0.38
    elif category in {"Scribd Login Required", "Other", "Current Affairs"}:
        score += 0.22
    elif category.startswith("Big4"):
        score += 0.08

    score += min(0.28, 0.045 * sum(1 for term in PYQ_PHASE_SOURCE_TERMS if term in haystack))
    score += min(0.18, 0.030 * sum(1 for term in OFFICIAL_MATERIAL_TERMS if term in haystack))
    if category not in EXAM_MATERIAL_CATEGORIES:
        score -= 0.30
    if any(term in haystack for term in ["result", "cut-off", "cutoff", "interview marks", "legal stream marks", "vacancy", "recruitment notification", "holiday list"]):
        score -= 0.35
    return round(max(0.0, min(1.0, score)), 3)


def is_exam_material_source(item: dict[str, Any], min_score: float = 0.32) -> bool:
    return exam_material_source_score(item.get("category"), item.get("title"), item.get("excerpt")) >= min_score


def exam_signal_score(text: str, query: str = "", topic_id: str | None = None, topic_tags: list[str] | None = None) -> float:
    haystack = re.sub(r"\s+", " ", text).lower()
    query_tokens = [token for token in re.findall(r"[a-z0-9]+", query.lower()) if len(token) > 2]
    query_hits = sum(1 for token in query_tokens[:10] if token in haystack)
    signal_hits = sum(1 for token in EXAM_SIGNAL_TERMS if token in haystack)
    topic_bonus = 0.12 if topic_id and topic_id in (topic_tags or []) else 0.0
    length_bonus = 0.06 if 350 <= len(haystack) <= 2500 else 0.0
    garble_penalty = 0.12 if haystack.count("â") > 8 or haystack.count("�") > 4 else 0.0
    return round(max(0.0, min(1.0, 0.06 * query_hits + 0.035 * signal_hits + topic_bonus + length_bonus - garble_penalty)), 3)


def enrich_source_result(row: sqlite3.Row, query: str = "", topic_id: str | None = None) -> dict[str, Any]:
    text = re.sub(r"\s+", " ", row["text"]).strip()
    topic_tags = (row["topic_tags"] or "").split()
    authority = source_authority_score(row["category"], row["title"])
    signal = exam_signal_score(text, query=query, topic_id=topic_id, topic_tags=topic_tags)
    material = exam_material_source_score(row["category"], row["title"], text)
    bm25_rank = float(row["rank"] or 0)
    retrieval_bonus = max(0.0, min(0.2, 0.2 / (1.0 + max(0.0, bm25_rank))))
    exam_score = round(max(0.0, min(1.0, (0.58 * authority) + (0.32 * signal) + retrieval_bonus)), 3)
    return {
        "chunk_id": row["chunk_id"],
        "document_id": row["document_id"],
        "title": row["title"],
        "category": row["category"],
        "page_start": row["page_start"],
        "page_end": row["page_end"],
        "line_start": row["line_start"],
        "line_end": row["line_end"],
        "topic_tags": topic_tags,
        "excerpt": text[:1200],
        "rank": row["rank"],
        "authority_score": authority,
        "exam_signal_score": signal,
        "exam_material_score": material,
        "exam_source_score": exam_score,
    }


def rank_source_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_hashes: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in results:
        fingerprint = hashlib.sha256(re.sub(r"\s+", " ", item.get("excerpt", "")[:500]).lower().encode("utf-8", errors="replace")).hexdigest()
        if fingerprint in seen_hashes:
            continue
        seen_hashes.add(fingerprint)
        unique.append(item)
    return sorted(unique, key=lambda item: (item.get("exam_source_score", 0), item.get("authority_score", 0), -(item.get("rank") or 0)), reverse=True)


def search_sources(query: str, topic_id: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    if SOURCE_MODE == "knowledge":
        facts = search_facts(query, limit=max(limit, 10))
        if topic_id:
            tagged = [
                fact for fact in facts
                if topic_id in (fact.get("topic_ids") or []) or topic_id in (fact.get("subject_ids") or [])
            ]
            if tagged:
                facts = tagged
        if facts:
            return [fact_as_chunk(fact) for fact in facts][:limit]
        # No fact matched: fall through to the dormant chunk path so databases
        # without a bootstrapped knowledge pack still get search results.
    init_db()
    limit = max(1, min(limit, 50))
    conn = get_connection()
    try:
        query_expr = fts_query(query)
        params: list[Any] = []
        if query_expr:
            sql = """
                SELECT c.chunk_id, c.document_id, d.title, d.category, c.page_start, c.page_end,
                       c.line_start, c.line_end, c.text, f.topic_tags, bm25(document_chunk_fts) AS rank
                FROM document_chunk_fts f
                JOIN document_chunks c ON c.chunk_id = f.chunk_id
                JOIN documents d ON d.document_id = c.document_id
                WHERE document_chunk_fts MATCH ?
            """
            params.append(query_expr)
        else:
            sql = """
                SELECT c.chunk_id, c.document_id, d.title, d.category, c.page_start, c.page_end,
                       c.line_start, c.line_end, c.text, '' AS topic_tags, 0.0 AS rank
                FROM document_chunks c
                JOIN documents d ON d.document_id = c.document_id
                WHERE 1 = 1
            """
        if topic_id:
            sql += " AND EXISTS (SELECT 1 FROM chunk_topics ct WHERE ct.chunk_id = c.chunk_id AND ct.topic_id = ?)"
            params.append(topic_id)
        sql += " ORDER BY rank ASC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        like = f"%{query}%"
        sql = """
            SELECT c.chunk_id, c.document_id, d.title, d.category, c.page_start, c.page_end,
                   c.line_start, c.line_end, c.text, '' AS topic_tags, 0.0 AS rank
            FROM document_chunks c
            JOIN documents d ON d.document_id = c.document_id
            WHERE c.text LIKE ?
        """
        params = [like]
        if topic_id:
            sql += " AND EXISTS (SELECT 1 FROM chunk_topics ct WHERE ct.chunk_id = c.chunk_id AND ct.topic_id = ?)"
            params.append(topic_id)
        sql += " LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    return rank_source_results([enrich_source_result(row, query=query, topic_id=topic_id) for row in rows])[:limit]


def search_pyqs(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Plan v6 6.8: search the compiled PYQ bank by question text/hint."""
    init_db()
    limit = max(1, min(limit, 100))
    like = f"%{query}%"
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT pyq_id, exam, year, phase, paper, section, subject_id, question_number,
                   question_text, hint, marks, incomplete
            FROM previous_year_questions
            WHERE question_text LIKE ? OR COALESCE(hint, '') LIKE ?
            ORDER BY exam, year DESC, phase, paper, question_number
            LIMIT ?
            """,
            (like, like, limit),
        ).fetchall()
        return rows_to_dicts(rows)
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def search_descriptive_items(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Plan v6 6.8: search descriptive prompts/passages in the compiled pack."""
    init_db()
    limit = max(1, min(limit, 100))
    like = f"%{query}%"
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT item_id, exam, item_type, year, phase, paper, question_number,
                   prompt_text, marks, word_limit_min, word_limit_max, incomplete
            FROM descriptive_items
            WHERE prompt_text LIKE ? OR COALESCE(passage_text, '') LIKE ?
            ORDER BY exam, year DESC, item_type
            LIMIT ?
            """,
            (like, like, limit),
        ).fetchall()
        return rows_to_dicts(rows)
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def record_descriptive_score(
    exam: str,
    year: int | None,
    components: list[dict[str, Any]],
    total_score: float,
    total_max_marks: float,
    cutoff_pct: float,
    cleared_cutoff: bool,
    ai_status: dict[str, Any] | None = None,
) -> str:
    """Plan v6 6.2: persist a graded descriptive sitting for readiness mapping."""
    init_db()
    score_id = f"DESC_SCORE_{uuid.uuid4().hex[:12]}"
    total_pct = round(total_score / total_max_marks * 100, 2) if total_max_marks else 0.0
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO descriptive_scores
            (score_id, exam, year, components_json, total_score, total_max_marks,
             total_pct, cutoff_pct, cleared_cutoff, ai_status_json, graded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                score_id, exam, year, json.dumps(components),
                total_score, total_max_marks, total_pct, cutoff_pct,
                1 if cleared_cutoff else 0,
                json.dumps(ai_status) if ai_status else None,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return score_id


def latest_descriptive_performance(exam: str | None = None) -> dict[str, Any] | None:
    """Most recent graded descriptive sitting (plan v6 6.2 readiness mapping)."""
    init_db()
    conn = get_connection()
    try:
        if exam:
            row = conn.execute(
                "SELECT * FROM descriptive_scores WHERE exam = ? ORDER BY graded_at DESC LIMIT 1",
                (exam,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM descriptive_scores ORDER BY graded_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def list_descriptive_scores(exam: str | None = None, limit: int = 25) -> list[dict[str, Any]]:
    init_db()
    limit = max(1, min(limit, 100))
    conn = get_connection()
    try:
        if exam:
            rows = conn.execute(
                "SELECT * FROM descriptive_scores WHERE exam = ? ORDER BY graded_at DESC LIMIT ?",
                (exam, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM descriptive_scores ORDER BY graded_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return rows_to_dicts(rows)
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def get_source_chunk_detail(chunk_id: str) -> dict[str, Any] | None:
    """Return canonical document chunk detail from the active document_chunks index."""

    init_db()
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT c.chunk_id, c.document_id, d.title, d.category, c.page_start, c.page_end,
                   c.line_start, c.line_end, c.text, GROUP_CONCAT(ct.topic_id, ' ') AS topic_tags,
                   0.0 AS rank
            FROM document_chunks c
            JOIN documents d ON d.document_id = c.document_id
            LEFT JOIN chunk_topics ct ON ct.chunk_id = c.chunk_id
            WHERE c.chunk_id = ?
            GROUP BY c.chunk_id
            LIMIT 1
            """,
            (chunk_id,),
        ).fetchone()
        if row:
            detail = enrich_source_result(row)
            detail["citation_note"] = format_citation_note(
                {
                    "title": detail.get("title"),
                    "page_start": detail.get("page_start"),
                    "section_title": None,
                },
                page_num=detail.get("page_start"),
            )
            linked = conn.execute(
                """
                SELECT question_id
                FROM question_citations
                WHERE chunk_id = ?
                ORDER BY question_id
                LIMIT 25
                """,
                (chunk_id,),
            ).fetchall()
            detail["linked_question_ids"] = [item["question_id"] for item in linked]
            return detail

        if str(chunk_id).isdigit():
            legacy = conn.execute(
                """
                SELECT sc.chunk_id, CAST(sc.doc_id AS TEXT) AS document_id, sd.name AS title,
                       sd.category, sc.page_num AS page_start, sc.page_num AS page_end,
                       sc.start_line AS line_start, sc.end_line AS line_end,
                       sc.chunk_text AS text, '' AS topic_tags, 0.0 AS rank
                FROM source_chunks sc
                JOIN source_documents sd ON sd.doc_id = sc.doc_id
                WHERE sc.chunk_id = ?
                LIMIT 1
                """,
                (int(chunk_id),),
            ).fetchone()
            if legacy:
                detail = enrich_source_result(legacy)
                detail["citation_note"] = format_citation_note(
                    {
                        "title": detail.get("title"),
                        "page_start": detail.get("page_start"),
                        "section_title": None,
                    },
                    page_num=detail.get("page_start"),
                )
                detail["linked_question_ids"] = []
                return detail
        return None
    finally:
        conn.close()


def source_distribution_by_category() -> dict[str, Any]:
    """Summarize source coverage from the canonical documents/document_chunks index."""

    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT COALESCE(d.category, 'Unknown') AS source_type,
                   COUNT(DISTINCT c.chunk_id) AS chunk_count,
                   COUNT(DISTINCT qc.question_id) AS question_count
            FROM documents d
            LEFT JOIN document_chunks c ON d.document_id = c.document_id
            LEFT JOIN question_citations qc ON c.chunk_id = qc.chunk_id
            GROUP BY source_type
            ORDER BY chunk_count DESC, source_type ASC
            """
        ).fetchall()
    finally:
        conn.close()

    distribution = []
    for row in rows:
        source_type = row["source_type"] or "Unknown"
        distribution.append(
            {
                "label": source_type,
                "chunks": row["chunk_count"] or 0,
                "questions": row["question_count"] or 0,
                "avg_authority": round(source_authority_score(source_type, None) * 100, 1),
            }
        )
    return {
        "distribution": distribution,
        "total_chunks": sum(item["chunks"] for item in distribution),
        "total_questions": sum(item["questions"] for item in distribution),
    }


def chunks_for_topic(topic_id: str, limit: int = 8, query: str | None = None, source_role_filter: list[str] | None = None) -> list[dict[str, Any]]:
    if SOURCE_MODE == "knowledge":
        authorities: set[str] | None = None
        if source_role_filter:
            authorities = set()
            for role in source_role_filter:
                authorities |= ROLE_TO_AUTHORITIES.get(role, set(FACT_AUTHORITY_RANK))
        facts = facts_for_topic(topic_id, limit=limit, authority_filter=authorities, query=query)
        if not facts:
            facts = search_facts(query or topic_display(topic_id), limit=limit)
        return [fact_as_chunk(fact) for fact in facts][:limit]
    if query:
        results = search_sources(query, topic_id=topic_id, limit=limit)
        if results:
            return results
    conn = get_connection()
    try:
        # Per Context7 docs for SQLite: use parametrized queries with conditional filtering
        params: list[Any] = [topic_id]

        # Build WHERE clause conditionally based on source_role_filter
        # material_role filtering (documents table has source_role column populated from source_documents)
        if source_role_filter and len(source_role_filter) > 0:
            # Filter by source_role (if documents.source_role column exists and is populated)
            where_part = f"WHERE ct.topic_id = ? AND (d.source_role IS NOT NULL AND d.source_role IN ({','.join('?' * len(source_role_filter))}))"
            params.extend(source_role_filter)
            params.append(limit)
        else:
            # Without source_role filter
            where_part = "WHERE ct.topic_id = ?"
            params.append(limit)

        # Safe query - will work with or without source_role column in documents table
        rows = conn.execute(
            f"""
            SELECT c.chunk_id, c.document_id, d.title, d.category, c.page_start, c.page_end,
                   c.line_start, c.line_end, c.text, GROUP_CONCAT(ct.topic_id, ' ') AS topic_tags,
                   MAX(ct.confidence) AS confidence
            FROM chunk_topics ct
            JOIN document_chunks c ON c.chunk_id = ct.chunk_id
            JOIN documents d ON d.document_id = c.document_id
            {where_part}
            GROUP BY c.chunk_id
            ORDER BY confidence DESC, c.line_start ASC
            LIMIT ?
            """,
            params,
        ).fetchall()

        # Graceful fallback if source_role filter returned no results
        if not rows and source_role_filter:
            params = [topic_id, limit]
            rows = conn.execute(
                """
                SELECT c.chunk_id, c.document_id, d.title, d.category, c.page_start, c.page_end,
                       c.line_start, c.line_end, c.text, GROUP_CONCAT(ct.topic_id, ' ') AS topic_tags,
                       MAX(ct.confidence) AS confidence
                FROM chunk_topics ct
                JOIN document_chunks c ON c.chunk_id = ct.chunk_id
                JOIN documents d ON d.document_id = c.document_id
                WHERE ct.topic_id = ?
                GROUP BY c.chunk_id
                ORDER BY confidence DESC, c.line_start ASC
                LIMIT ?
                """,
                params,
            ).fetchall()
    finally:
        conn.close()
    results = []
    for row in rows:
        text = re.sub(r"\s+", " ", row["text"]).strip()
        topic_tags = (row["topic_tags"] or "").split()
        authority = source_authority_score(row["category"], row["title"])
        signal = exam_signal_score(text, query=query or topic_display(topic_id), topic_id=topic_id, topic_tags=topic_tags)
        material = exam_material_source_score(row["category"], row["title"], text)
        confidence = float(row["confidence"] or 0.0)
        results.append(
            {
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "title": row["title"],
                "category": row["category"],
                "page_start": row["page_start"],
                "page_end": row["page_end"],
                "line_start": row["line_start"],
                "line_end": row["line_end"],
                "topic_tags": topic_tags,
                "excerpt": text[:1200],
                "rank": 0.0,
                "authority_score": authority,
                "exam_signal_score": signal,
                "exam_material_score": material,
                "exam_source_score": round(max(0.0, min(1.0, (0.52 * authority) + (0.30 * signal) + (0.18 * confidence))), 3),
            }
        )
    return rank_source_results(results)[:limit]


def _is_pack_fact_chunk(item: dict[str, Any]) -> bool:
    """True for knowledge-pack fact chunks (document_id 'fact:<domain>').

    Compiled facts are curated, provenance-backed exam material (plan v6
    Phase 0), so they must not be filtered by the legacy document-category
    heuristic in is_exam_material_source — their category carries the authority
    label, not a corpus category, which made the heuristic drop every fact.
    """
    return str(item.get("document_id") or "").startswith("fact:")


def rank_exam_material_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for item in results:
        if _is_pack_fact_chunk(item):
            # Curated pack facts are exam material by construction; keep the
            # existing score if fact_as_chunk set one, else a solid default.
            item.setdefault("exam_material_score", 0.5)
            ranked.append(item)
            continue
        item["exam_material_score"] = exam_material_source_score(item.get("category"), item.get("title"), item.get("excerpt"))
        if is_exam_material_source(item):
            ranked.append(item)
    return sorted(
        rank_source_results(ranked),
        key=lambda item: (
            item.get("exam_material_score", 0),
            item.get("topic_relevance_score", 0),
            item.get("exam_source_score", 0),
            item.get("authority_score", 0),
        ),
        reverse=True,
    )


def exam_source_role(item: dict[str, Any]) -> str:
    haystack = f"{item.get('category', '')}\n{item.get('title', '')}\n{item.get('excerpt', '')}".lower()
    if item.get("category") == "Exam Papers (Memory-based)" or any(term in haystack for term in ["pyq", "memory based", "question paper", "question-paper", "information handout", "exam handout"]):
        return "pyq_phase_paper"
    if any(term in haystack for term in ["syllabus", "study material", "phase 2"]):
        return "phase_study_material"
    if item.get("category") in {"ICSI Materials", "IFSCA Regulations (TAS/PSR/RI)", "IFSCA Publications (Reports/Bulletins)", "Scribd Login Required"}:
        return "official_or_primary_material"
    return "supporting_material"


def diversify_exam_context(results: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    ranked = rank_exam_material_results(results)
    for item in ranked:
        item["source_role"] = exam_source_role(item)

    pyq_items = [item for item in ranked if item["source_role"] == "pyq_phase_paper"]
    material_items = [item for item in ranked if item["source_role"] != "pyq_phase_paper"]
    pyq_target = min(max(1, limit // 3), len(pyq_items))
    material_target = max(0, limit - pyq_target)

    selected: list[dict[str, Any]] = []
    seen_chunks: set[str] = set()
    doc_counts: dict[str, int] = defaultdict(int)

    def add_from(pool: list[dict[str, Any]], target: int) -> None:
        for item in pool:
            if len(selected) >= limit or target <= 0:
                return
            chunk_id = item.get("chunk_id")
            doc_id = item.get("document_id")
            if not chunk_id or chunk_id in seen_chunks:
                continue
            if doc_counts.get(doc_id, 0) >= 3:
                continue
            selected.append(item)
            seen_chunks.add(chunk_id)
            doc_counts[doc_id] += 1
            target -= 1

    add_from(material_items, material_target)
    add_from(pyq_items, pyq_target)
    add_from(ranked, limit - len(selected))
    return selected[:limit]


def mock_source_chunks(topic_id: str, limit: int = 10, query: str | None = None, source_role_filter: list[str] | None = None) -> list[dict[str, Any]]:
    """Retrieve only local exam/PYQ/phase/material corpus chunks for mock generation.

    Per Context7 docs for database queries: supports optional source_role_filter parameter
    to restrict chunks to specific material roles (e.g., regulatory_core, amendment_tracking).
    """

    topic_name = topic_display(topic_id)
    queries = [
        query or topic_name,
        f"{topic_name} IFSCA Grade A Phase 2 question paper memory PYQ",
        f"{topic_name} IFSCA Grade A syllabus study material ICSI",
        f"{topic_name} information handout phase paper exam",
        f"{topic_name} IFSCA regulations material compliance",
    ]
    by_chunk: dict[str, dict[str, Any]] = {}
    for item in chunks_for_topic(topic_id, limit=30, source_role_filter=source_role_filter):
        if item.get("chunk_id"):
            by_chunk[item["chunk_id"]] = item
    for source_query in queries:
        for item in search_sources(source_query, topic_id=topic_id, limit=30):
            if item.get("chunk_id"):
                by_chunk[item["chunk_id"]] = item
        for item in search_sources(source_query, limit=20):
            if item.get("chunk_id") and (topic_id in item.get("topic_tags", []) or _is_pack_fact_chunk(item) or is_exam_material_source(item, min_score=0.45)):
                by_chunk[item["chunk_id"]] = item
    topic_keywords = [topic_name.lower(), *[keyword.lower() for keyword in TOPIC_BY_ID.get(topic_id, {}).get("keywords", [])]]
    for item in by_chunk.values():
        haystack = f"{item.get('title', '')}\n{item.get('excerpt', '')}".lower()
        item["topic_relevance_score"] = (
            0.25
            if topic_id in item.get("topic_tags", [])
            else min(0.25, 0.05 * sum(1 for keyword in topic_keywords if keyword and keyword in haystack))
        )
    return diversify_exam_context(list(by_chunk.values()), limit)


def list_documents(limit: int = 200) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT d.*,
                   (SELECT COUNT(*) FROM document_chunks c WHERE c.document_id = d.document_id) AS chunk_count
            FROM documents d
            ORDER BY category, title
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return rows_to_dicts(rows)
    finally:
        conn.close()


def ifsca_act_document() -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT *
            FROM documents
            WHERE lower(title) LIKE '%indiacode%ifsca act%'
               OR lower(title) LIKE '%ifsca act 2019 current%'
               OR lower(title) LIKE '%international financial services centres authority act%'
            ORDER BY
              CASE WHEN lower(title) LIKE '%indiacode%' THEN 0 ELSE 1 END,
              line_count DESC
            LIMIT 1
            """
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def read_document_lines(document: dict[str, Any] | None) -> list[str]:
    if not document:
        return []
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT full_text FROM document_fulltext WHERE document_id = ?",
            (document.get("document_id"),),
        ).fetchone()
    finally:
        conn.close()
    if row and row["full_text"]:
        return row["full_text"].splitlines()
    text_path = document.get("local_text_path") or ""
    path = Path(text_path) if text_path else None
    if path is not None and path.is_file():
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    return []


def ifsca_act_full_text() -> dict[str, Any]:
    document = ifsca_act_document()
    if document is None:
        bootstrap_from_knowledge()
        document = ifsca_act_document()
    lines = read_document_lines(document)
    return {
        "document": document,
        "line_count": len(lines),
        "full_text": "\n".join(lines),
    }


def get_law_revision_progress() -> dict[str, Any]:
    """Completion-driven IFSCA Act revision progress (plan v6 6.5).

    Each row in law_revision_progress is one completed daily session.
    The day index advances with completions instead of the calendar, so the
    user always picks up where they left off.
    """
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT day_index, completed_at FROM law_revision_progress ORDER BY rowid"
        ).fetchall()
    finally:
        conn.close()
    events = [{"day_index": int(row["day_index"]), "completed_at": row["completed_at"]} for row in rows]
    return {
        "completed_sessions": len(events),
        "completed_day_indexes": sorted({event["day_index"] for event in events}),
        "last_day_index": events[-1]["day_index"] if events else None,
        "last_completed_at": events[-1]["completed_at"] if events else None,
    }


def next_law_revision_day_index(total_days: int) -> int:
    if total_days <= 0:
        return 0
    progress = get_law_revision_progress()
    return progress["completed_sessions"] % total_days


def complete_law_revision_day(day_index: int, total_days: int | None = None) -> dict[str, Any]:
    init_db()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO law_revision_progress (day_index, completed_at) VALUES (?, ?)",
            (int(day_index), datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    progress = get_law_revision_progress()
    result = {
        "status": "completed",
        "day_index": int(day_index),
        "next_day_index": progress["completed_sessions"] % total_days if total_days else None,
        **progress,
    }
    return result


def daily_ifsca_act_revision(lines_per_day: int = 80, day_index: int | None = None) -> dict[str, Any]:
    act = ifsca_act_full_text()
    document = act["document"]
    raw_lines = act["full_text"].splitlines()
    content_lines = [(index + 1, line) for index, line in enumerate(raw_lines) if line.strip()]
    if not content_lines:
        return {
            "title": "IFSCA Act 2019",
            "document": document,
            "line_start": 0,
            "line_end": 0,
            "daily_text": "",
            "full_text": "",
            "total_lines": 0,
            "day_index": 0,
            "total_days": 0,
        }
    lines_per_day = max(30, min(lines_per_day, 180))
    total_days = max(1, math.ceil(len(content_lines) / lines_per_day))
    if day_index is None:
        day_index = next_law_revision_day_index(total_days)
    day_index = max(0, min(total_days - 1, day_index))
    selected = content_lines[day_index * lines_per_day : (day_index + 1) * lines_per_day]
    line_start = selected[0][0]
    line_end = selected[-1][0]
    daily_text = "\n".join(f"{line_no}: {line}" for line_no, line in selected)
    return {
        "title": document.get("title") if document else "IFSCA Act 2019",
        "document": document,
        "line_start": line_start,
        "line_end": line_end,
        "daily_text": daily_text,
        "full_text": act["full_text"],
        "total_lines": len(raw_lines),
        "day_index": day_index,
        "total_days": total_days,
    }


def list_topics() -> list[dict[str, Any]]:
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM topics ORDER BY exam_priority DESC, display_name").fetchall()
        return rows_to_dicts(rows)
    finally:
        conn.close()


def source_coverage_by_topic(conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    rows = conn.execute(
        """
        SELECT t.topic_id, t.display_name, t.exam_priority,
               COUNT(DISTINCT ct.chunk_id) AS chunks,
               COUNT(DISTINCT d.document_id) AS documents,
               SUM(CASE WHEN d.category LIKE 'IFSCA%' OR d.category = 'ICSI Materials' THEN 1 ELSE 0 END) AS official_chunks,
               AVG(ct.confidence) AS avg_confidence
        FROM topics t
        LEFT JOIN chunk_topics ct ON ct.topic_id = t.topic_id
        LEFT JOIN document_chunks c ON c.chunk_id = ct.chunk_id
        LEFT JOIN documents d ON d.document_id = c.document_id
        GROUP BY t.topic_id
        ORDER BY t.exam_priority DESC, chunks DESC
        """
    ).fetchall()
    coverage = []
    for row in rows:
        chunks = int(row["chunks"] or 0)
        documents = int(row["documents"] or 0)
        official_chunks = int(row["official_chunks"] or 0)
        avg_confidence = float(row["avg_confidence"] or 0.0)
        source_depth = min(1.0, chunks / 120)
        document_breadth = min(1.0, documents / 30)
        official_ratio = official_chunks / chunks if chunks else 0.0
        coverage_score = round((0.42 * source_depth) + (0.24 * document_breadth) + (0.24 * official_ratio) + (0.10 * avg_confidence), 3)
        coverage.append(
            {
                "topic_id": row["topic_id"],
                "display_name": row["display_name"],
                "exam_priority": row["exam_priority"],
                "chunks": chunks,
                "documents": documents,
                "official_chunks": official_chunks,
                "official_ratio": round(official_ratio, 3),
                "avg_confidence": round(avg_confidence, 3),
                "coverage_score": coverage_score,
                "coverage_status": "STRONG" if coverage_score >= 0.72 else "MEDIUM" if coverage_score >= 0.45 else "THIN",
            }
        )
    if owns_conn:
        conn.close()
    return coverage


def question_bank_quality_by_topic(conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    rows = conn.execute(
        """
        SELECT t.topic_id, t.display_name,
               q.question_id, q.question_text, q.created_by,
               q.verification_status, qc.chunk_id
        FROM topics t
        LEFT JOIN questions q ON q.topic_id = t.topic_id
        LEFT JOIN question_citations qc ON qc.question_id = q.question_id
        ORDER BY t.topic_id
        """
    ).fetchall()
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        topic_id = row["topic_id"]
        item = grouped.setdefault(
            topic_id,
            {
                "topic_id": topic_id,
                "display_name": row["display_name"],
                "total_questions": 0,
                "reusable_questions": 0,
                "gemini_questions": 0,
                "low_quality_questions": 0,
                "rejected_questions": 0,
                "avg_quality": 0.0,
                "quality_sum": 0.0,
            },
        )
        if row["question_id"] is None:
            continue
        quality = question_quality_score(row["question_text"], row["created_by"], has_citation=bool(row["chunk_id"]))
        item["total_questions"] += 1
        item["quality_sum"] += quality
        if row["verification_status"] == "REJECTED_LOW_QUALITY":
            item["rejected_questions"] += 1
        if row["verification_status"] != "REJECTED_LOW_QUALITY" and quality >= 0.48:
            item["reusable_questions"] += 1
        else:
            item["low_quality_questions"] += 1
        if row["created_by"] == "gemini":
            item["gemini_questions"] += 1
    for item in grouped.values():
        total = item["total_questions"]
        item["avg_quality"] = round(item["quality_sum"] / total, 3) if total else 0.0
        item["bank_status"] = "READY" if item["reusable_questions"] >= 20 else "THIN" if item["reusable_questions"] >= 5 else "EMPTY"
        del item["quality_sum"]
    if owns_conn:
        conn.close()
    return list(grouped.values())


def intelligent_targeting_snapshot() -> dict[str, Any]:
    conn = get_connection()
    try:
        topic_stats = get_topic_stats(conn=conn)
        coverage = {item["topic_id"]: item for item in source_coverage_by_topic(conn=conn)}
        bank = {item["topic_id"]: item for item in question_bank_quality_by_topic(conn=conn)}
        amendments = rows_to_dicts(
            conn.execute(
                """
                SELECT topic_id, COUNT(*) AS pending
                FROM amendment_events
                WHERE mastery_status != 'MASTERED'
                GROUP BY topic_id
                """
            ).fetchall()
        )
    finally:
        conn.close()
    amendment_pending = {item["topic_id"]: item["pending"] for item in amendments}
    targets = []
    for stat in topic_stats:
        topic_id = stat["topic"]
        topic_def = TOPIC_BY_ID.get(topic_id, {})
        cov = coverage.get(topic_id, {})
        qbank = bank.get(topic_id, {})
        pending_amendments = int(amendment_pending.get(topic_id, 0))
        bank_gap = max(0.0, 1.0 - min(1.0, float(qbank.get("reusable_questions", 0)) / 20))
        source_gap = max(0.0, 1.0 - float(cov.get("coverage_score", 0)))
        priority = float(topic_def.get("base_weight", 0.7))
        target_score = round(
            min(
                1.0,
                (0.35 * stat.get("weakness_score", 0.4))
                + (0.18 * bank_gap)
                + (0.12 * source_gap)
                + (0.15 * priority)
                + (0.15 * min(1.0, pending_amendments / 4))
                + (0.05 if stat.get("total_seen", 0) < 10 else 0.0),
            ),
            3,
        )
        targets.append(
            {
                "topic_id": topic_id,
                "display_name": stat.get("display_name"),
                "target_score": target_score,
                "weakness_score": stat.get("weakness_score"),
                "accuracy_pct": stat.get("accuracy_pct"),
                "attempts": stat.get("total_seen"),
                "source_coverage": cov,
                "question_bank": qbank,
                "pending_amendments": pending_amendments,
                "recommended_action": (
                    "generate_gemini_questions"
                    if bank_gap >= 0.75 and float(cov.get("coverage_score", 0)) >= 0.35
                    else "source_review"
                    if source_gap >= 0.65
                    else "penalty_drill"
                    if stat.get("status") in {"UNKNOWN", "CRITICAL", "WEAK"}
                    else "maintenance_mock"
                ),
            }
        )
    targets.sort(key=lambda item: item["target_score"], reverse=True)
    coverage_items = list(coverage.values())
    bank_items = list(bank.values())
    return {
        "generated_at": datetime.now().isoformat(),
        "targets": targets,
        "top_targets": targets[:8],
        "coverage": coverage_items,
        "question_bank": bank_items,
        "thin_question_banks": [item for item in bank_items if item.get("bank_status") != "READY"],
        "thin_source_coverage": [item for item in coverage_items if item.get("coverage_status") == "THIN"],
        "total_topics": len(targets),
    }


def status_from_accuracy(accuracy: float, attempts: int = 0) -> str:
    if attempts == 0:
        return "UNKNOWN"
    if accuracy < 40:
        return "CRITICAL"
    if accuracy < 60:
        return "WEAK"
    if accuracy < 75:
        return "MEDIUM"
    return "STRONG"


def record_mock(mock_data: dict[str, Any]) -> None:
    init_db()
    conn = get_connection()
    try:
        mock_id = mock_data["mock_id"]
        conn.execute("DELETE FROM question_attempts WHERE mock_id = ?", (mock_id,))
        conn.execute("DELETE FROM mocks WHERE mock_id = ?", (mock_id,))
        for question in mock_data["questions"]:
            conn.execute(
                """
                INSERT INTO question_attempts
                (mock_id, question_id, topic, question_text, correct_option, your_option,
                 is_correct, time_spent_seconds, attempt_date, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mock_id,
                    str(question.get("id")),
                    question.get("topic"),
                    question.get("question_text", ""),
                    question.get("correct_option"),
                    question.get("your_option"),
                    int(bool(question.get("is_correct"))),
                    question.get("time_spent_seconds", 0),
                    mock_data.get("date"),
                    mock_data.get("source", "QRE"),
                ),
            )
        total = len(mock_data["questions"])
        correct = sum(1 for q in mock_data["questions"] if q.get("is_correct"))
        skipped = sum(1 for q in mock_data["questions"] if not q.get("your_option"))
        accuracy = (correct / total * 100) if total else 0.0
        conn.execute(
            """
            INSERT INTO mocks
            (mock_id, date, phase, paper, total_questions, total_correct, total_skipped, overall_accuracy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mock_id,
                mock_data.get("date"),
                mock_data.get("phase"),
                mock_data.get("paper"),
                total,
                correct,
                skipped,
                accuracy,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    calculate_topic_accuracy()


def calculate_topic_accuracy() -> list[dict[str, Any]]:
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT topic,
                   COUNT(*) AS total_seen,
                   SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS total_correct,
                   ROUND(100.0 * SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS accuracy_pct,
                   MAX(COALESCE(attempt_date, created_at)) AS last_tested
            FROM question_attempts
            GROUP BY topic
            """
        ).fetchall()
        for row in rows:
            status = status_from_accuracy(float(row["accuracy_pct"] or 0), int(row["total_seen"] or 0))
            conn.execute(
                """
                INSERT OR REPLACE INTO topic_stats
                (topic, total_seen, total_correct, accuracy_pct, status, last_tested, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (row["topic"], row["total_seen"], row["total_correct"], row["accuracy_pct"], status, row["last_tested"]),
            )
        conn.commit()
        return get_topic_stats(conn=conn)
    finally:
        conn.close()


def _coverage_gap_for_topic(topic_id: str, conn: sqlite3.Connection) -> float:
    """Plan v6 6.1: how thin the study corpus is for a topic.

    High coverage gap = almost no source chunks or compiled facts back the
    topic, so mocks have little grounded material and the user cannot study it
    adequately. Normalized against a depth target of 120 items to mirror
    source_coverage_by_topic's source_depth. In knowledge mode (file-free) the
    chunk tables may be empty, in which case compiled facts carry the signal.
    """
    try:
        chunk_row = conn.execute(
            "SELECT COUNT(*) AS count FROM chunk_topics WHERE topic_id = ?", (topic_id,)
        ).fetchone()
        fact_row = conn.execute(
            "SELECT COUNT(*) AS count FROM fact_topics WHERE topic_id = ?", (topic_id,)
        ).fetchone()
    except sqlite3.OperationalError:
        return 0.0
    chunks = chunk_row["count"] if chunk_row else 0
    facts = fact_row["count"] if fact_row else 0
    depth = min(1.0, (chunks + facts) / 120)
    return round(1.0 - depth, 3)


def calculate_weakness_score(topic_id: str, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    topic_def = TOPIC_BY_ID.get(topic_id, {})
    rows = conn.execute(
        """
        SELECT is_correct, time_spent_seconds, created_at
        FROM question_attempts
        WHERE topic = ?
        ORDER BY created_at DESC
        """,
        (topic_id,),
    ).fetchall()
    attempts = len(rows)
    exam_weight = float(topic_def.get("base_weight", 0.7))
    # Plan v6 6.1: coverage-gap term applies to both untried and attempted topics.
    coverage_gap = _coverage_gap_for_topic(topic_id, conn)
    amendment_recency = 0.0
    if topic_def.get("is_amendment_sensitive"):
        amendment_row = conn.execute(
            "SELECT COUNT(*) AS count FROM amendment_events WHERE topic_id = ? AND mastery_status != 'MASTERED'",
            (topic_id,),
        ).fetchone()
        amendment_recency = min(1.0, (amendment_row["count"] or 0) / 5)

    if attempts == 0:
        low_attempt_confidence = 1.0
        weakness = (
            0.15 * low_attempt_confidence
            + 0.10 * exam_weight
            + 0.10 * amendment_recency
            + 0.05 * coverage_gap
            + 0.20
        )
        result = {
            "topic": topic_id,
            "display_name": topic_display(topic_id),
            "total_seen": 0,
            "total_correct": 0,
            "accuracy_pct": 0.0,
            "status": "UNKNOWN",
            "last_tested": None,
            "weakness_score": round(min(1.0, weakness), 3),
            "recent_accuracy": None,
            "trend": "UNKNOWN",
        }
        if owns_conn:
            conn.close()
        return result

    correct = sum(1 for row in rows if row["is_correct"])
    historical_accuracy = correct / attempts
    recent_rows = rows[: min(20, attempts)]
    recent_correct = sum(1 for row in recent_rows if row["is_correct"])
    recent_accuracy = recent_correct / len(recent_rows)
    avg_time = sum((row["time_spent_seconds"] or 0) for row in rows) / attempts
    # Plan v6 6.1: topic-aware time baseline. Phase-I aptitude (SUBJ_*) questions are
    # fast (~60s); Phase-II regulatory questions are slower (~180s). Pressure measures
    # how far the average exceeds the expected baseline for that topic class.
    time_baseline = 60 if topic_id.startswith("SUBJ_") else 180
    time_pressure = min(1.0, max(0.0, (avg_time - time_baseline) / 120))
    low_attempt_confidence = max(0.0, 1.0 - min(1.0, attempts / 30))
    # Plan v6 6.1: Bayesian smoothing pulls small-sample accuracy toward 50% so a
    # topic with 1-2 attempts does not dominate weakness from a single lucky/unlucky run.
    smoothed_accuracy = (correct + 3) / (attempts + 6)
    historical_error = 1 - smoothed_accuracy
    recent_error = 1 - recent_accuracy
    # Plan v6 6.1: weights renormalized to include the coverage-gap term (sum = 1.0).
    weakness = (
        0.30 * historical_error
        + 0.25 * recent_error
        + 0.15 * low_attempt_confidence
        + 0.10 * exam_weight
        + 0.10 * amendment_recency
        + 0.05 * time_pressure
        + 0.05 * coverage_gap
    )
    trend = "IMPROVING" if recent_accuracy > historical_accuracy + 0.05 else "DECLINING" if recent_accuracy < historical_accuracy - 0.05 else "STABLE"
    accuracy_pct = round((0.7 * historical_accuracy + 0.3 * recent_accuracy) * 100, 2)
    result = {
        "topic": topic_id,
        "display_name": topic_display(topic_id),
        "total_seen": attempts,
        "total_correct": correct,
        "accuracy_pct": accuracy_pct,
        "status": status_from_accuracy(accuracy_pct, attempts),
        "last_tested": rows[0]["created_at"],
        "weakness_score": round(min(1.0, max(0.0, weakness)), 3),
        "recent_accuracy": round(recent_accuracy * 100, 2),
        "trend": trend,
    }
    if owns_conn:
        conn.close()
    return result


def get_topic_stats(conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    stats = [calculate_weakness_score(topic_id, conn=conn) for topic_id in TOPIC_IDS]
    stats.sort(key=lambda item: item["weakness_score"], reverse=True)
    for index, item in enumerate(stats):
        item["tier"] = 1 if index < max(1, len(stats) // 3) else 2 if index < max(2, (len(stats) * 2) // 3) else 3
    if owns_conn:
        conn.close()
    return stats


def get_weak_topics(threshold: float = 60.0, limit: int = 8) -> list[dict[str, Any]]:
    stats = get_topic_stats()
    weak = [
        item
        for item in stats
        if item["status"] in {"UNKNOWN", "CRITICAL", "WEAK"} or item["accuracy_pct"] < threshold
    ]
    return weak[:limit]


def rank_topics_by_weakness() -> list[dict[str, Any]]:
    return get_topic_stats()


def weighted_distribution(topics: list[dict[str, Any]], slots: int) -> dict[str, int]:
    if not topics or slots <= 0:
        return {}
    weights = [max(0.05, item.get("weakness_score", 0.2) + (TOPIC_BY_ID.get(item["topic"], {}).get("base_weight", 0.7) * 0.2)) for item in topics]
    total_weight = sum(weights)
    raw = [(item["topic"], (weight / total_weight) * slots) for item, weight in zip(topics, weights)]
    allocation = {topic: max(0, math.floor(value)) for topic, value in raw}
    remainder = slots - sum(allocation.values())
    ranked_remainders = sorted(raw, key=lambda item: item[1] - math.floor(item[1]), reverse=True)
    for topic, _ in ranked_remainders[:remainder]:
        allocation[topic] += 1
    return {topic: count for topic, count in allocation.items() if count > 0}


def allocate_question_slots(ranked_topics: list[dict[str, Any]], total_questions: int = 50, mode: str = "balanced") -> dict[str, int]:
    total_questions = max(1, total_questions)
    weak_ratio, medium_ratio, strong_ratio = (0.60, 0.25, 0.15)
    if mode == "weakness-heavy":
        weak_ratio, medium_ratio, strong_ratio = (0.70, 0.20, 0.10)
    elif mode == "amendment-heavy":
        weak_ratio, medium_ratio, strong_ratio = (0.55, 0.25, 0.20)
    elif mode == "pyq-like":
        weak_ratio, medium_ratio, strong_ratio = (0.45, 0.35, 0.20)

    weak = ranked_topics[: max(1, math.ceil(len(ranked_topics) * 0.33))]
    medium = ranked_topics[len(weak) : max(len(weak) + 1, math.ceil(len(ranked_topics) * 0.67))]
    strong = ranked_topics[len(weak) + len(medium) :]
    weak_slots = round(total_questions * weak_ratio)
    medium_slots = round(total_questions * medium_ratio)
    strong_slots = total_questions - weak_slots - medium_slots

    allocation: dict[str, int] = {}
    for group, slots in ((weak, weak_slots), (medium, medium_slots), (strong, strong_slots)):
        for topic, count in weighted_distribution(group, slots).items():
            allocation[topic] = allocation.get(topic, 0) + count

    diff = total_questions - sum(allocation.values())
    ordered = [item["topic"] for item in ranked_topics if item["topic"] in allocation]
    while diff > 0 and ordered:
        for topic in ordered:
            if diff <= 0:
                break
            allocation[topic] += 1
            diff -= 1
    while diff < 0 and ordered:
        for topic in reversed(ordered):
            if diff >= 0:
                break
            if allocation.get(topic, 0) > 0:
                allocation[topic] -= 1
                diff += 1
    return {topic: count for topic, count in allocation.items() if count > 0}


def get_smart_mock_config(total_questions: int = 50, mode: str = "balanced") -> dict[str, Any]:
    ranked = [item for item in rank_topics_by_weakness() if item["topic"] in OBJECTIVE_MOCK_TOPIC_IDS]
    targeting = intelligent_targeting_snapshot()
    target_scores = {item["topic_id"]: item["target_score"] for item in targeting["targets"]}
    target_actions = {item["topic_id"]: item["recommended_action"] for item in targeting["targets"]}
    for item in ranked:
        item["target_score"] = target_scores.get(item["topic"], item.get("weakness_score", 0.0))
        item["recommended_action"] = target_actions.get(item["topic"], "penalty_drill")
    ranked.sort(key=lambda item: item.get("target_score", item.get("weakness_score", 0.0)), reverse=True)
    allocation = allocate_question_slots(ranked, total_questions=total_questions, mode=mode)

    # Calculate weak/medium/strong groups for difficulty scaffolding
    weak_count = int(round(total_questions * 0.60))
    medium_count = int(round(total_questions * 0.25))
    strong_count = total_questions - weak_count - medium_count

    weak_topics = ranked[: max(1, math.ceil(len(ranked) * 0.33))]
    medium_topics = ranked[len(weak_topics) : max(len(weak_topics) + 1, math.ceil(len(ranked) * 0.67))]
    strong_topics = ranked[len(weak_topics) + len(medium_topics) :]

    # Build difficulty progression per topic
    difficulty_curve: dict[str, list[str]] = {}
    for item in weak_topics:
        topic = item["topic"]
        # For weak topics: scaffold difficulty progression
        topic_qs = allocation.get(topic, 0)
        if topic_qs >= 3:
            # Distribute: ~1/3 easy, ~1/3 medium, ~1/3 hard
            easy_count = topic_qs // 3
            medium_mid = (topic_qs * 2) // 3
            hard_count = topic_qs - medium_mid
            difficulty_curve[topic] = ["easy"] * easy_count + ["medium"] * (medium_mid - easy_count) + ["hard"] * hard_count
        elif topic_qs == 2:
            difficulty_curve[topic] = ["easy", "hard"]
        else:
            difficulty_curve[topic] = ["medium"]

    for item in medium_topics:
        topic = item["topic"]
        topic_qs = allocation.get(topic, 0)
        if topic_qs >= 2:
            # For medium topics: half easy, half hard
            easy_count = topic_qs // 2
            difficulty_curve[topic] = ["easy"] * easy_count + ["hard"] * (topic_qs - easy_count)
        else:
            difficulty_curve[topic] = ["medium"]

    for item in strong_topics:
        topic = item["topic"]
        topic_qs = allocation.get(topic, 0)
        # For strong topics: practice only "easy" questions confounds the weakness
        # signal (accuracy looks high because the items are trivial). Topics with
        # enough attempt history get an exam-like easy/medium/hard mix; low-attempt
        # topics keep light scaffolding so measurement stays meaningful.
        attempts = int(item.get("total_seen", 0) or 0)
        if attempts >= 10:
            easy_count = round(topic_qs * 0.3)
            hard_count = round(topic_qs * 0.3)
            medium_count = topic_qs - easy_count - hard_count
            difficulty_curve[topic] = (
                ["easy"] * easy_count
                + ["medium"] * medium_count
                + ["hard"] * hard_count
            )
        elif attempts >= 3:
            easy_count = topic_qs // 2
            difficulty_curve[topic] = ["easy"] * easy_count + ["medium"] * (topic_qs - easy_count)
        else:
            difficulty_curve[topic] = ["medium"] * topic_qs

    return {
        "ranked_topics": ranked,
        "allocation": allocation,
        "difficulty_curve": difficulty_curve,
        "targeting_snapshot": targeting,
        "weak_topics": [item["topic"] for item in weak_topics],
        "medium_topics": [item["topic"] for item in medium_topics],
        "strong_topics": [item["topic"] for item in strong_topics],
    }


def correct_label(options: list[dict[str, str]], correct_text: str) -> str:
    for option in options:
        if option["text"] == correct_text:
            return option["label"]
    return "A"


def question_quality_score(
    question_text: str | None,
    created_by: str | None = None,
    has_citation: bool = False,
    verified: bool = False,
    option_count: int = 5,
) -> float:
    text = (question_text or "").strip()
    lower = text.lower()
    if not text:
        return 0.0
    score = 0.35
    if created_by == "gemini":
        score += 0.22
    if has_citation:
        score += 0.18
    if verified:
        score += 0.25  # verifier re-answered from the cited fact (plan v6 4.7)
    if option_count < 5:
        score -= 0.30  # real exam questions carry five options
    if any(term in lower for term in ["which statement", "what is", "which of the following", "scenario", "effective", "regulation"]):
        score += 0.08
    if lower.startswith("based on the cited source excerpt, which ifsca exam topic"):
        score -= 0.50
    if lower.startswith("which statement is best supported by the cited source on"):
        score -= 0.20
    if re.search(r"\bon (a|an|the)\s+(undertake|provide|establish|include|require|shall|must)\b", lower):
        score -= 0.30
    if " viz?" in lower or lower.endswith(" viz"):
        score -= 0.20
    if len(text) < 35 or len(text) > 900:
        score -= 0.08
    return round(max(0.0, min(1.0, score)), 3)


def reusable_question_row(row: sqlite3.Row, citation: sqlite3.Row | None = None) -> bool:
    if row["verification_status"] == "REJECTED_LOW_QUALITY":
        return False
    return question_quality_score(row["question_text"], row["created_by"], has_citation=bool(citation)) >= 0.48


def quarantine_low_quality_questions(min_quality: float = 0.48) -> dict[str, Any]:
    conn = get_connection()
    scanned = 0
    rejected = 0
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM questions
            WHERE COALESCE(verification_status, '') != 'REJECTED_LOW_QUALITY'
            """
        ).fetchall()
        for row in rows:
            citation = conn.execute("SELECT * FROM question_citations WHERE question_id = ? LIMIT 1", (row["question_id"],)).fetchone()
            score = question_quality_score(row["question_text"], row["created_by"], has_citation=bool(citation))
            scanned += 1
            if score < min_quality:
                conn.execute(
                    """
                    UPDATE questions
                    SET verification_status = 'REJECTED_LOW_QUALITY'
                    WHERE question_id = ?
                    """,
                    (row["question_id"],),
                )
                rejected += 1
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok", "scanned": scanned, "rejected": rejected, "min_quality": min_quality}


def sentence_from_excerpt(excerpt: str) -> str:
    clean = re.sub(r"\s+", " ", excerpt).strip()
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    for sentence in sentences:
        if 80 <= len(sentence) <= 260:
            return sentence
    return clean[:220]


def compact_focus_phrase(text: str, topic_id: str) -> str:
    topic = TOPIC_BY_ID.get(topic_id, {})
    lower = text.lower()
    for keyword in topic.get("keywords", []):
        idx = lower.find(keyword.lower())
        if idx >= 0:
            start = idx
            end = min(len(text), idx + len(keyword) + 85)
            phrase = text[start:end].strip(" ,.;:-")
            phrase = re.sub(r"\s+", " ", phrase)
            phrase = re.sub(r"\bviz\.?$", "", phrase, flags=re.IGNORECASE).strip(" ,.;:-")
            return re.sub(r"^(The|A|An)\s+", lambda match: f"{match.group(1).lower()} ", phrase)
    return QUESTION_FOCUS_BY_TOPIC.get(topic_id, topic_display(topic_id))


def source_grounded_stem(topic_id: str, source_sentence: str, difficulty: str, question_type: str) -> str:
    topic_name = topic_display(topic_id)
    focus = compact_focus_phrase(source_sentence, topic_id)
    if question_type == "amendment":
        return (
            f"For an amendment drill on {topic_name}, which option correctly captures the cited requirement "
            f"or change relating to {focus}?"
        )
    if difficulty == "hard":
        return (
            f"While advising an IFSC entity on {topic_name}, which option is the most defensible inference "
            f"from the cited source on {focus}?"
        )
    if difficulty == "easy":
        return f"In {topic_name}, what does the cited source establish about {focus}?"
    return f"For {topic_name}, which statement correctly applies the cited source on {focus}?"


def local_question_from_chunk(topic_id: str, chunk: dict[str, Any], number: int, difficulty: str = "medium", question_type: str = "source_grounded") -> dict[str, Any]:
    source_sentence = sentence_from_excerpt(chunk["excerpt"])
    correct_text = source_sentence
    distractors = [
        f"The cited source treats {topic_display(topic_id)} as outside the IFSC regulatory perimeter.",
        "The cited source removes registration, authorisation, and continuing compliance obligations.",
        "The cited source applies only to domestic financial services outside GIFT IFSC.",
        "The cited source transfers these powers to the state government instead of IFSCA.",
    ]
    options_text = [correct_text] + distractors
    random.shuffle(options_text)
    options = [{"label": label, "text": text} for label, text in zip(["A", "B", "C", "D", "E"], options_text)]
    question_id = f"Q_{slugify(topic_id)}_{uuid.uuid4().hex[:10]}"
    return {
        "question_id": question_id,
        "topic": topic_id,
        "question_text": source_grounded_stem(topic_id, source_sentence, difficulty, question_type),
        "options": options,
        "correct_option": correct_label(options, correct_text),
        "explanation": (
            f"The supported statement is drawn from the cited excerpt. Review {chunk['title']} around "
            f"page {chunk.get('page_start') or 1}, lines {chunk.get('line_start') or 1}-{chunk.get('line_end') or 1}."
        ),
        "source": chunk["title"],
        "source_document_id": chunk["document_id"],
        "source_chunk_id": chunk["chunk_id"],
        "page_start": chunk.get("page_start"),
        "page_end": chunk.get("page_end"),
        "citation_note": f"Deterministic source-grounded question from {chunk['title']}",
        "is_amendment_based": topic_id in {"PH2_FM_REGS", "PH2_TECHFIN_TAS", "PH2_CMI", "PH2_AML_KYC", "PH2_PAYMENT"},
        "difficulty": difficulty,
        "recency_score": 80 if "2025" in chunk["title"] or "2026" in chunk["title"] else 40,
        "question_type": question_type,
    }


def save_question(question: dict[str, Any], created_by: str = "local_source_engine", prompt_version: str = "local_v1") -> None:
    init_db()
    options = question.get("options", [])
    option_map = {option["label"]: option["text"] for option in options}
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO questions
            (question_id, source, topic_id, subtopic_id, question_text, option_a, option_b, option_c, option_d, option_e,
             correct_answer, explanation, difficulty, question_type, is_amendment_based, amendment_id,
             created_by, prompt_version, verification_status, tested_fact, trap_logic, source_policy,
             subject_id, fact_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                question["question_id"],
                question.get("source"),
                question.get("topic"),
                None,
                question.get("question_text"),
                option_map.get("A", ""),
                option_map.get("B", ""),
                option_map.get("C", ""),
                option_map.get("D", ""),
                option_map.get("E"),
                question.get("correct_option"),
                question.get("explanation"),
                question.get("difficulty", "medium"),
                question.get("question_type", "source_grounded"),
                int(bool(question.get("is_amendment_based"))),
                question.get("amendment_id"),
                created_by,
                prompt_version,
                "VERIFIED_SOURCE_CITED" if question.get("source_chunk_id") else "LOCAL_FALLBACK",
                question.get("tested_fact"),
                question.get("trap_logic"),
                question.get("source_policy"),
                question.get("subject_id"),
                question.get("fact_id") or (
                    question.get("source_chunk_id")
                    if str(question.get("source_document_id") or "").startswith("fact:")
                    else None
                ),
            ),
        )
        if question.get("source_chunk_id"):
            conn.execute(
                """
                INSERT OR REPLACE INTO question_citations
                (question_id, document_id, chunk_id, page_start, page_end, citation_note)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    question["question_id"],
                    question.get("source_document_id"),
                    question.get("source_chunk_id"),
                    question.get("page_start"),
                    question.get("page_end"),
                    question.get("citation_note"),
                ),
            )
            # Link question to source with authority score (only for migration 001 source_chunks)
            authority_score = question.get("authority_score")
            if authority_score is None:
                # Calculate authority score based on source metadata
                doc_type = question.get("source", "extracted_pdf")
                category = question.get("source_category", "default")
                authority_score = int(calculate_source_authority(doc_type, category, exam_signal=0))

            # Only write to question_sources if source_chunk_id is actually from source_chunks
            # (migration 001 flow). For document_chunks (main flow), use question_citations above.
            if isinstance(question.get("source_chunk_id"), int):
                # Likely from source_chunks (INT PK), not document_chunks (TEXT PK)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO question_sources
                    (question_id, source_chunk_id, authority_score)
                    VALUES (?, ?, ?)
                    """,
                    (
                        question["question_id"],
                        question.get("source_chunk_id"),
                        authority_score,
                    ),
                )
        conn.execute(
            """
            INSERT OR REPLACE INTO generated_questions
            (question_id, topic, question_text, options, correct_option, explanation, source,
             is_amendment_based, difficulty, recency_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                question["question_id"],
                question.get("topic"),
                question.get("question_text"),
                json.dumps(options),
                question.get("correct_option"),
                question.get("explanation"),
                question.get("source"),
                int(bool(question.get("is_amendment_based"))),
                question.get("difficulty", "medium"),
                question.get("recency_score", 0),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def row_to_question(row: sqlite3.Row, citation: sqlite3.Row | None = None) -> dict[str, Any]:
    options = [
        {"label": "A", "text": row["option_a"]},
        {"label": "B", "text": row["option_b"]},
        {"label": "C", "text": row["option_c"]},
        {"label": "D", "text": row["option_d"]},
    ]
    try:
        if row["option_e"]:
            options.append({"label": "E", "text": row["option_e"]})
    except (IndexError, KeyError):
        pass
    return {
        "question_id": row["question_id"],
        "topic": row["topic_id"],
        "question_text": row["question_text"],
        "options": options,
        "correct_option": row["correct_answer"],
        "explanation": row["explanation"],
        "source": row["source"],
        "source_document_id": citation["document_id"] if citation else None,
        "source_chunk_id": citation["chunk_id"] if citation else None,
        "page_start": citation["page_start"] if citation else None,
        "page_end": citation["page_end"] if citation else None,
        "citation_note": citation["citation_note"] if citation else None,
        "is_amendment_based": bool(row["is_amendment_based"]),
        "difficulty": row["difficulty"],
        "recency_score": 0,
        "created_by": row["created_by"],
        "quality_score": question_quality_score(row["question_text"], row["created_by"], has_citation=bool(citation)),
        "tested_fact": row["tested_fact"],
        "trap_logic": row["trap_logic"],
        "source_policy": row["source_policy"] or ("exam_material" if row["question_type"] == "smart_mock" else "source_grounded"),
    }


def get_question(question_id: str, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    row = conn.execute("SELECT * FROM questions WHERE question_id = ?", (question_id,)).fetchone()
    if not row:
        if owns_conn:
            conn.close()
        return None
    citation = conn.execute("SELECT * FROM question_citations WHERE question_id = ? LIMIT 1", (question_id,)).fetchone()
    question = row_to_question(row, citation)
    if owns_conn:
        conn.close()
    return question


def irt_lite_question_stats(min_attempts: int = 3) -> dict[str, dict[str, Any]]:
    """Plan v6 6.8: IRT-lite per-question stats from observed attempts.

    p-value (proportion correct) and median answer time come from
    question_attempts; they feed empirical difficulty when questions are
    reused so mocks calibrate to real performance instead of the label alone.
    """
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT question_id,
                   COUNT(*) AS attempts,
                   SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct
            FROM question_attempts
            WHERE question_id IS NOT NULL
            GROUP BY question_id
            HAVING COUNT(*) >= ?
            """,
            (min_attempts,),
        ).fetchall()
        time_rows = conn.execute(
            """
            SELECT question_id, time_spent_seconds
            FROM question_attempts
            WHERE question_id IS NOT NULL AND time_spent_seconds > 0
            """
        ).fetchall()
    finally:
        conn.close()
    time_map: dict[str, list[float]] = defaultdict(list)
    for row in time_rows:
        time_map[row["question_id"]].append(float(row["time_spent_seconds"]))
    stats: dict[str, dict[str, Any]] = {}
    for row in rows:
        p_value = (row["correct"] or 0) / row["attempts"]
        if p_value < 0.4:
            observed = "hard"
        elif p_value > 0.8:
            observed = "easy"
        else:
            observed = "medium"
        values = sorted(time_map.get(row["question_id"], []))
        stats[row["question_id"]] = {
            "attempts": row["attempts"],
            "p_value": round(p_value, 3),
            "median_time_seconds": values[len(values) // 2] if values else None,
            "observed_difficulty": observed,
        }
    return stats


def existing_questions_for_topic(topic_id: str, limit: int, created_by: str | None = None) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        created_filter = "AND created_by = ?" if created_by else ""
        rows = conn.execute(
            f"""
            SELECT * FROM questions
            WHERE topic_id = ?
              AND question_text NOT LIKE 'Based on the cited source excerpt, which IFSCA exam topic is most directly tested by this statement:%'
              AND COALESCE(verification_status, '') != 'REJECTED_LOW_QUALITY'
              {created_filter}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (topic_id, created_by, limit) if created_by else (topic_id, limit),
        ).fetchall()
        questions = []
        for row in rows:
            citation = conn.execute("SELECT * FROM question_citations WHERE question_id = ? LIMIT 1", (row["question_id"],)).fetchone()
            if reusable_question_row(row, citation):
                questions.append(row_to_question(row, citation))
    finally:
        conn.close()
    # Plan v6 6.8: IRT-lite — empirical difficulty from observed attempts drives
    # reuse selection; the stored label is preserved as labeled_difficulty.
    stats = irt_lite_question_stats()
    for question in questions:
        observed = stats.get(question.get("question_id"))
        if observed:
            question["labeled_difficulty"] = question.get("difficulty")
            question["difficulty"] = observed["observed_difficulty"]
            question["p_value"] = observed["p_value"]
            question["median_time_seconds"] = observed["median_time_seconds"]
    return questions


def generate_local_questions(topic_id: str, count: int, difficulty: str = "medium", query: str | None = None, question_type: str = "source_grounded") -> list[dict[str, Any]]:
    if table_count("documents") == 0:
        ingest_documents(force=False)
    chunks = chunks_for_topic(topic_id, limit=max(count, 3), query=query)
    if not chunks:
        chunks = search_sources(topic_display(topic_id), limit=max(count, 3))
    questions = []
    for index in range(count):
        if chunks:
            chunk = chunks[index % len(chunks)]
        else:
            chunk = {
                "chunk_id": None,
                "document_id": None,
                "title": "Local fallback",
                "excerpt": f"{topic_display(topic_id)} is part of the IFSCA Grade A syllabus.",
                "page_start": 1,
                "page_end": 1,
                "line_start": 1,
                "line_end": 1,
            }
        question = local_question_from_chunk(topic_id, chunk, index + 1, difficulty=difficulty, question_type=question_type)
        question["created_by"] = "local_source_engine"
        save_question(question)
        questions.append(question)
    return questions


def _source_role_filter_for_difficulty(difficulty: str) -> list[str]:
    """Map question difficulty to appropriate source material roles.

    Per Context7 docs for SQLite: routing difficulty levels to curated material types.
    - easy (weak topics): regulatory_core ONLY - test fundamentals from official sources
    - medium (balanced): regulatory_core + amendment_tracking - test both basics and updates
    - hard (strong topics): any except pyq_phase_paper - advanced scenario/case application
    """
    difficulty_lower = difficulty.lower()
    if difficulty_lower in {"easy", "basic", "weak"}:
        return ["regulatory_core"]
    elif difficulty_lower in {"medium", "balanced", "normal"}:
        return ["regulatory_core", "amendment_tracking"]
    else:  # hard, advanced, expert
        # Prioritize amendment_tracking and essay_examples for strong candidates
        return ["amendment_tracking", "essay_examples", "consulting_case", "supporting_material"]


def generate_gemini_questions(
    topic_id: str,
    count: int,
    difficulty: str = "medium",
    query: str | None = None,
    question_type: str = "source_grounded",
    is_amendment_based: bool = False,
    amendment_id: str | None = None,
    source_policy: str = "general",
) -> list[dict[str, Any]]:
    if count <= 0 or not gemini_available():
        return []

    # Per Context7 docs: calculate source_role_filter based on difficulty
    source_role_filter = _source_role_filter_for_difficulty(difficulty) if difficulty else None

    if source_policy == "exam_material" or question_type == "smart_mock":
        chunks = mock_source_chunks(topic_id, limit=max(count * 2, 8), query=query, source_role_filter=source_role_filter)
    else:
        chunks = chunks_for_topic(topic_id, limit=max(count * 2, 6), query=query, source_role_filter=source_role_filter)
    if not chunks and source_policy != "exam_material":
        chunks = search_sources(query or topic_display(topic_id), limit=max(count * 2, 6))
    if not chunks:
        return []
    # PYQ style calibration (plan v6 sub-phase 4.4): sample real bank stems.
    # Enriched per user intent: Gemini sees past stems WITH their correct answer so
    # it internalizes real exam style + answer shape as grounding context (never
    # copied verbatim into new questions).
    style_anchors: list[str] = []
    try:
        conn = get_connection()
        try:
            anchor_rows = conn.execute(
                """
                SELECT question_text, correct_option, hint FROM previous_year_questions
                WHERE incomplete = 0 AND (subject_id = ? OR topic_id = ?)
                ORDER BY RANDOM() LIMIT 6
                """,
                (topic_id, topic_id),
            ).fetchall()
            style_anchors = [
                f"{row['question_text']} [Answer: {row['correct_option'] or '?'}]"
                + (f" (note: {row['hint']})" if row["hint"] else "")
                for row in anchor_rows
            ]
        finally:
            conn.close()
    except Exception:
        style_anchors = []
    questions = generate_questions_with_gemini(
        topic_id,
        count,
        difficulty,
        chunks,
        question_type=question_type,
        is_amendment_based=is_amendment_based,
        source_policy=source_policy,
        style_anchors=style_anchors,
    )
    saved: list[dict[str, Any]] = []
    for question in questions[:count]:
        if amendment_id:
            question["amendment_id"] = amendment_id
            question["is_amendment_based"] = True
        question["source_policy"] = source_policy
        question["created_by"] = "gemini"
        save_question(question, created_by="gemini", prompt_version="gemini_exam_contract_v2")
        saved.append(question)
    return saved


def generate_topic_questions(
    topic_id: str,
    count: int,
    difficulty: str = "medium",
    query: str | None = None,
    question_type: str = "source_grounded",
    use_gemini: bool = True,
    strict_gemini: bool = False,
    allow_local_fallback: bool = False,
    reuse_existing: bool = True,
    source_policy: str = "general",
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    if use_gemini and gemini_available():
        if reuse_existing:
            for question in existing_questions_for_topic(topic_id, limit=count, created_by="gemini"):
                selected.append(question)
                seen.add(question["question_id"])
        missing = count - len(selected)
        if missing > 0:
            for question in generate_gemini_questions(
                topic_id,
                missing,
                difficulty=difficulty,
                query=query,
                question_type=question_type,
                source_policy=source_policy,
            ):
                if question["question_id"] not in seen:
                    selected.append(question)
                    seen.add(question["question_id"])
        if len(selected) >= count:
            return selected[:count]
        if strict_gemini:
            raise RuntimeError(
                f"Gemini produced {len(selected)}/{count} usable {source_policy} questions for {topic_id}; local fallback is disabled for accuracy."
            )
    elif strict_gemini:
        raise RuntimeError("Gemini is not available; mock/drill question generation is disabled rather than falling back to local filler.")

    if reuse_existing and not use_gemini:
        for question in existing_questions_for_topic(topic_id, limit=count * 2):
            if question["question_id"] not in seen:
                selected.append(question)
                seen.add(question["question_id"])
            if len(selected) >= count:
                return selected[:count]

    missing = count - len(selected)
    if missing > 0 and allow_local_fallback:
        for question in generate_local_questions(topic_id, missing, difficulty=difficulty, query=query, question_type=question_type):
            question["created_by"] = "local_source_engine"
            if question["question_id"] not in seen:
                selected.append(question)
                seen.add(question["question_id"])
    return selected[:count]


def verify_unverified_questions(limit: int = 10) -> dict[str, Any]:
    """Re-answer unverified Gemini questions against their cited fact (plan v6 4.6).

    Questions with a fact citation are re-answered from that fact alone via
    gemini_integration.verify_question_against_fact. Matches are stamped
    VERIFIED_AI_CHECKED; mismatches are stamped REJECTED_UNGROUNDED so they are
    excluded from mock assembly. Quota-aware: stops when Gemini is unavailable.
    """
    from gemini_integration import verify_question_against_fact, gemini_available

    verified = 0
    rejected = 0
    skipped = 0
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT q.question_id, q.question_text, q.correct_answer AS correct_option, q.option_a,
                   q.option_b, q.option_c, q.option_d, q.option_e, q.fact_id,
                   f.statement, f.detail
            FROM questions q
            LEFT JOIN facts f ON f.fact_id = q.fact_id
            WHERE q.created_by = 'gemini'
              AND COALESCE(q.verification_status, '') NOT IN ('VERIFIED_AI_CHECKED', 'REJECTED_UNGROUNDED', 'REJECTED_LOW_QUALITY')
              AND q.fact_id IS NOT NULL
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    for row in rows:
        if not gemini_available():
            skipped += len(rows) - rows.index(row)
            break
        options = []
        for letter in "ABCDE":
            text = row["option_a"] if letter == "A" else row["option_b"] if letter == "B" else row["option_c"] if letter == "C" else row["option_d"] if letter == "D" else row["option_e"]
            if text:
                options.append({"label": letter, "text": text})
        fact_excerpt = ((row["statement"] or "") + " " + (row["detail"] or "")).strip()
        verdict = verify_question_against_fact(
            {"question_text": row["question_text"], "correct_option": row["correct_option"], "options": options},
            fact_excerpt,
        )
        conn = get_connection()
        try:
            if verdict is None:
                skipped += 1
                continue
            if verdict["correct"]:
                conn.execute(
                    "UPDATE questions SET verification_status = 'VERIFIED_AI_CHECKED', verified_at = ?, verification_details = ? WHERE question_id = ?",
                    (datetime.now().isoformat(), verdict.get("issue") or "grounded", row["question_id"]),
                )
                verified += 1
            else:
                conn.execute(
                    "UPDATE questions SET verification_status = 'REJECTED_UNGROUNDED', verified_at = ?, verification_details = ? WHERE question_id = ?",
                    (datetime.now().isoformat(), f"verifier answered {verdict['correct_letter']}: {verdict.get('issue') or ''}", row["question_id"]),
                )
                rejected += 1
            conn.commit()
        finally:
            conn.close()

    return {"verified": verified, "rejected": rejected, "skipped": skipped, "considered": len(rows)}


def build_question_bank(
    topic_ids: list[str] | None = None,
    target_per_topic: int = 20,
    max_new_questions: int = 30,
    use_gemini: bool = True,
) -> dict[str, Any]:
    if not use_gemini:
        return {
            "generated_at": datetime.now().isoformat(),
            "target_per_topic": target_per_topic,
            "max_new_questions": max_new_questions,
            "use_gemini": False,
            "remaining_capacity": max_new_questions,
            "results": [],
            "thin_question_banks_remaining": len(intelligent_targeting_snapshot()["thin_question_banks"]),
            "error": "Gemini is mandatory for question-bank generation; local fallback is disabled.",
        }
    snapshot = intelligent_targeting_snapshot()
    selected = {topic.upper() for topic in topic_ids} if topic_ids else None
    remaining = max(0, max_new_questions)
    results = []
    for target in snapshot["targets"]:
        topic_id = target["topic_id"]
        if selected and topic_id not in selected:
            continue
        qbank = target["question_bank"]
        reusable = int(qbank.get("reusable_questions", 0))
        if reusable >= target_per_topic or remaining <= 0:
            results.append(
                {
                    "topic_id": topic_id,
                    "display_name": target["display_name"],
                    "generated": 0,
                    "reusable_before": reusable,
                    "reusable_after": reusable,
                    "status": "ready" if reusable >= target_per_topic else "skipped_limit_reached",
                }
            )
            continue
        desired_count = min(target_per_topic, reusable + remaining)
        before_ids = {question["question_id"] for question in existing_questions_for_topic(topic_id, limit=target_per_topic)}
        try:
            questions = generate_topic_questions(
                topic_id,
                desired_count,
                difficulty="hard" if float(target.get("target_score", 0)) >= 0.65 else "medium",
                query=topic_display(topic_id),
                question_type="bank_build",
                use_gemini=use_gemini,
                strict_gemini=True,
                allow_local_fallback=False,
                reuse_existing=True,
                source_policy="exam_material",
            )
        except RuntimeError as exc:
            results.append(
                {
                    "topic_id": topic_id,
                    "display_name": target["display_name"],
                    "generated": 0,
                    "reusable_before": reusable,
                    "reusable_after": reusable,
                    "bank_status": "gemini_required_failed",
                    "recommended_action": target["recommended_action"],
                    "error": str(exc),
                }
            )
            continue
        generated = max(0, len({question["question_id"] for question in questions} - before_ids))
        remaining -= generated
        after = next(
            (item for item in question_bank_quality_by_topic() if item["topic_id"] == topic_id),
            {"reusable_questions": reusable, "bank_status": "UNKNOWN"},
        )
        results.append(
            {
                "topic_id": topic_id,
                "display_name": target["display_name"],
                "generated": generated,
                "reusable_before": reusable,
                "reusable_after": after.get("reusable_questions", reusable),
                "bank_status": after.get("bank_status"),
                "recommended_action": target["recommended_action"],
            }
        )
        if remaining <= 0:
            break
    refreshed = intelligent_targeting_snapshot()
    return {
        "generated_at": datetime.now().isoformat(),
        "target_per_topic": target_per_topic,
        "max_new_questions": max_new_questions,
        "use_gemini": use_gemini,
        "remaining_capacity": remaining,
        "results": results,
        "thin_question_banks_remaining": len(refreshed["thin_question_banks"]),
    }


def generate_amendment_questions(amendment_id: str, topic_id: str, count: int = 3, query: str | None = None) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM questions
            WHERE amendment_id = ? AND created_by = 'gemini'
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (amendment_id, count),
        ).fetchall()
        existing = []
        for row in rows:
            citation = conn.execute("SELECT * FROM question_citations WHERE question_id = ? LIMIT 1", (row["question_id"],)).fetchone()
            existing.append(row_to_question(row, citation))
        if len(existing) >= count:
            conn.execute(
                """
                UPDATE amendment_events
                SET questions_generated = ?
                WHERE amendment_id = ?
                """,
                (len(existing), amendment_id),
            )
            conn.commit()
            return existing[:count]
    finally:
        conn.close()

    missing = count - len(existing)
    questions = generate_gemini_questions(
        topic_id,
        missing,
        difficulty="hard",
        query=query,
        question_type="amendment",
        is_amendment_based=True,
        amendment_id=amendment_id,
        source_policy="exam_material",
    )
    conn = get_connection()
    try:
        for question in questions:
            question["amendment_id"] = amendment_id
            question["is_amendment_based"] = True
            conn.execute(
                """
                UPDATE questions
                SET amendment_id = ?, is_amendment_based = 1, question_type = 'amendment'
                WHERE question_id = ?
                """,
                (amendment_id, question["question_id"]),
            )
            conn.execute(
                """
                UPDATE generated_questions
                SET is_amendment_based = 1, recency_score = 95
                WHERE question_id = ?
                """,
                (question["question_id"],),
            )
        conn.execute(
            """
            UPDATE amendment_events
            SET questions_generated = ?
            WHERE amendment_id = ?
            """,
            (len(existing) + len(questions), amendment_id),
        )
        conn.commit()
    finally:
        conn.close()
    return existing + questions


def save_smart_mock(mock_id: str, ranked_topics: list[dict[str, Any]], allocation: dict[str, int], difficulty_curve: dict[str, str], questions: list[dict[str, Any]] | None = None) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO smart_mocks
            (mock_id, generated_at, total_questions, weakness_analysis, allocation, difficulty_curve)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                mock_id,
                datetime.now().isoformat(),
                sum(allocation.values()),
                json.dumps(ranked_topics),
                json.dumps(allocation),
                json.dumps(difficulty_curve),
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO mock_sessions
            (mock_id, mock_type, generated_at, started_at, total_questions, allocation_json, difficulty_curve_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mock_id,
                "smart",
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                sum(allocation.values()),
                json.dumps(allocation),
                json.dumps(difficulty_curve),
                "generated",
            ),
        )
        if questions:
            for number, question in enumerate(questions, start=1):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO mock_questions (mock_id, question_id, question_number, source_reason)
                    VALUES (?, ?, ?, ?)
                    """,
                    (mock_id, question["question_id"], number, f"{question['topic']} allocation"),
                )
        conn.commit()
    finally:
        conn.close()


def _recently_cited_fact_ids(hours: int = 48) -> set[str]:
    """Fact ids cited by questions created within the last N hours (cooldown)."""
    conn = get_connection()
    try:
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        rows = conn.execute(
            """
            SELECT DISTINCT fact_id FROM questions
            WHERE fact_id IS NOT NULL AND created_at >= ?
            """,
            (cutoff,),
        ).fetchall()
        return {row["fact_id"] for row in rows if row["fact_id"]}
    except Exception:
        return set()
    finally:
        conn.close()


def get_exam_template(template_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM exam_templates WHERE template_id = ?", (template_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


TEMPLATE_UNIT_TOPICS: dict[str, list[str]] = {
    "IFSCA_PH1_P2_GENERAL": [
        "SUBJ_GA", "SUBJ_ECONOMICS", "SUBJ_COMMERCE_ACCOUNTS",
        "SUBJ_MANAGEMENT", "SUBJ_FINANCE", "SUBJ_COSTING",
    ],
    "IFSCA_PH2_P2_GENERAL": [
        "PH2_IFSCA_ACT", "PH2_GIFT_IFSC", "PH2_BUDGET_ECON_SURVEY",
        "PH2_BANKING", "PH2_CAPITAL", "PH2_INSURANCE", "PH2_PENSION",
    ],
    "SEBI_PH1_P2_GENERAL": [
        "SUBJ_COMMERCE_ACCOUNTS", "SUBJ_MANAGEMENT", "SUBJ_FINANCE",
        "SUBJ_COSTING", "SUBJ_COMPANIES_ACT", "SUBJ_ECONOMICS",
    ],
    "SEBI_PH2_P2_GENERAL": [
        "SUBJ_COMMERCE_ACCOUNTS", "SUBJ_MANAGEMENT", "SUBJ_FINANCE",
        "SUBJ_COSTING", "SUBJ_COMPANIES_ACT", "SUBJ_ECONOMICS",
    ],
}


def _template_allocation(template: dict[str, Any], total_questions: int) -> dict[str, int]:
    """Distribute questions across a template's syllabus units/sections.

    Weights come from weakness scores (falling back to exam_priority), with a
    guaranteed minimum of 2 questions per unit so every syllabus area appears.
    """
    template_id = template["template_id"]
    sections = json.loads(template.get("sections_json") or "[]")
    if sections:
        # Section-based paper (Phase I Paper 1): fixed per-section counts,
        # scaled proportionally when total_questions differs from the template.
        section_total = sum(section.get("questions", 0) for section in sections) or total_questions
        allocation: dict[str, int] = {}
        section_subjects = {"General Awareness (Financial Sector)": "SUBJ_GA", "General Awareness": "SUBJ_GA",
                            "English Language": "SUBJ_ENGLISH",
                            "Quantitative Aptitude": "SUBJ_QUANT", "Reasoning": "SUBJ_REASONING"}
        for section in sections:
            subject = section_subjects.get(section.get("name"), "SUBJ_GA")
            scaled = max(1, round(section.get("questions", 0) * total_questions / section_total))
            allocation[subject] = allocation.get(subject, 0) + scaled
        return allocation

    units = TEMPLATE_UNIT_TOPICS.get(template_id) or [
        unit for unit in json.loads(template.get("syllabus_units_json") or "[]")
    ]
    if not units:
        return {}

    weights: dict[str, float] = {}
    stats_by_topic = {item["topic"]: item for item in get_topic_stats()}
    for unit in units:
        if unit in stats_by_topic:
            weights[unit] = 0.4 + stats_by_topic[unit].get("weakness_score", 0.4)
        else:
            weights[unit] = 0.6  # unknown units get moderate weight

    minimum = 2
    remaining = total_questions - minimum * len(units)
    if remaining < 0:
        minimum = max(1, total_questions // len(units))
        remaining = total_questions - minimum * len(units)

    total_weight = sum(weights.values()) or 1.0
    allocation = {unit: minimum for unit in units}
    distributed = 0
    shares: list[tuple[str, float]] = []
    for unit, weight in weights.items():
        exact = remaining * weight / total_weight
        floored = int(exact)
        allocation[unit] += floored
        distributed += floored
        shares.append((unit, exact - floored))
    leftover = remaining - distributed
    for unit, _fraction in sorted(shares, key=lambda item: item[1], reverse=True):
        if leftover <= 0:
            break
        allocation[unit] += 1
        leftover -= 1
    return {unit: count for unit, count in allocation.items() if count > 0}


def _template_is_objective_ready(template: dict[str, Any]) -> bool:
    """True when this template can actually drive generate_smart_mock.

    Mirrors _template_allocation above: that function returns {} unless the
    template declares sections, is a TEMPLATE_UNIT_TOPICS key, or declares
    syllabus units. An empty allocation makes generate_smart_mock raise
    "Mock allocation is empty; ingest the knowledge pack first.", which
    exam_start's blanket except turns into an HTTP 500 whose message blames a
    knowledge pack that is already ingested. SUBJECT_DRILL and the two
    descriptive papers are all three shapes of that dead end, so they are
    catalogue rows but not generatable exams. CUSTOM bypasses the template path
    entirely (generate_smart_mock only looks the template up when
    template_id != "CUSTOM") and is always ready.
    """
    template_id = template["template_id"]
    if template_id == "CUSTOM":
        return True
    if template_id in TEMPLATE_UNIT_TOPICS:
        return True
    if json.loads(template.get("sections_json") or "[]"):
        return True
    return bool(json.loads(template.get("syllabus_units_json") or "[]"))


def list_exam_templates() -> list[dict[str, Any]]:
    """Every exam template a user can actually start, ordered for a picker.

    No init_db() here: get_exam_template does not call it either, and lifespan
    (main.py:152) has already run it by the time any request is served. Tests
    create the table themselves with _run_migration_005, which is the same
    pattern conftest uses for migration 002.

    COALESCE(phase, 0) / COALESCE(paper, 0) sort CUSTOM's NULLs first rather
    than last, so the picker's top option is the current default behaviour and
    the IFSCA/SEBI papers follow in exam -> phase -> paper order.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM exam_templates
            ORDER BY exam,
                     COALESCE(phase, 0),
                     COALESCE(paper, 0),
                     template_id
            """
        ).fetchall()
    finally:
        conn.close()
    templates = [dict(row) for row in rows]
    return [template for template in templates if _template_is_objective_ready(template)]


def generate_smart_mock(
    total_questions: int = 50,
    mode: str = "balanced",
    use_gemini: bool = True,
    template_id: str = "CUSTOM",
) -> dict[str, Any]:
    if not use_gemini:
        raise RuntimeError("Gemini is mandatory for every smart mock. Local/source-bank fallback is disabled.")
    if not gemini_available():
        raise RuntimeError("Gemini is not available, so a serious smart mock cannot be generated.")

    template = get_exam_template(template_id) if template_id and template_id != "CUSTOM" else None
    if template:
        allocation = _template_allocation(template, total_questions)
        config = get_smart_mock_config(total_questions=total_questions, mode=mode)
        # Gemini generates every question; the knowledge bank (facts + PYQ stems)
        # is supplied as retrieval context downstream, not reused verbatim.
        difficulty_curve = {
            topic: (["easy"] * (count // 3) + ["medium"] * (count - 2 * (count // 3)) + ["hard"] * (count // 3))
            if count >= 3 else ["medium"] * count
            for topic, count in allocation.items()
        }
    else:
        config = get_smart_mock_config(total_questions=total_questions, mode=mode)
        allocation = config["allocation"]
        difficulty_curve = config["difficulty_curve"]  # dict[topic] -> list[difficulty]

    if not allocation:
        raise RuntimeError("Mock allocation is empty; ingest the knowledge pack first.")

    # Bucket by (topic, difficulty): one Gemini call per bucket, executed in
    # parallel (plan v6 sub-phase 4.3) instead of one sequential call per question.
    buckets: list[tuple[str, str, int]] = []
    for topic_id, count in allocation.items():
        difficulties = difficulty_curve.get(topic_id, ["medium"] * count)
        difficulties = (difficulties[:count] + ["medium"] * count)[:count]
        for difficulty, bucket_count in Counter(difficulties).items():
            buckets.append((topic_id, difficulty, bucket_count))

    def _generate_bucket(bucket: tuple[str, str, int]) -> list[dict[str, Any]]:
        topic_id, difficulty, bucket_count = bucket
        try:
            return generate_topic_questions(
                topic_id,
                count=bucket_count,
                difficulty=difficulty,
                question_type="smart_mock",
                use_gemini=True,
                strict_gemini=False,
                allow_local_fallback=False,
                reuse_existing=False,
                source_policy="exam_material",
            )
        except Exception as exc:
            print(f"Bucket generation failed for {topic_id}/{difficulty}: {exc}")
            return []

    questions: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        for bucket_questions in executor.map(_generate_bucket, buckets):
            questions.extend(bucket_questions)

    # De-duplicate (plan v6 sub-phase 4.5): normalized stem, <=1 question per
    # fact per mock, and a 48-hour cooldown on facts cited by recent questions.
    recent_fact_ids = _recently_cited_fact_ids(hours=48)
    seen_stems: set[str] = set()
    seen_fact_ids: set[str] = set()
    unique_questions: list[dict[str, Any]] = []
    for question in questions:
        stem = re.sub(r"[^a-z0-9]+", "", (question.get("question_text") or "").lower())
        if stem in seen_stems:
            continue
        # A fact-sourced question has document_id like 'fact:banking' and the
        # fact id in source_chunk_id. Enforce <=1 per fact per mock + cooldown.
        is_fact_sourced = str(question.get("source_document_id") or "").startswith("fact:")
        if is_fact_sourced:
            fact_key = str(question.get("source_chunk_id") or "")
            if fact_key and (fact_key in seen_fact_ids or fact_key in recent_fact_ids):
                continue
            if fact_key:
                seen_fact_ids.add(fact_key)
        seen_stems.add(stem)
        unique_questions.append(question)
    questions = unique_questions

    # Exact allocation enforcement: top up shortfall from the weakest allocated
    # topics, then trim to the requested total.
    if len(questions) < total_questions:
        shortfall = total_questions - len(questions)
        top_up_topics = sorted(allocation.keys(), key=lambda topic: -allocation[topic])
        for topic_id in top_up_topics:
            if shortfall <= 0:
                break
            try:
                extra = generate_topic_questions(
                    topic_id,
                    count=shortfall,
                    difficulty="medium",
                    question_type="smart_mock",
                    use_gemini=True,
                    strict_gemini=False,
                    allow_local_fallback=False,
                    reuse_existing=False,
                    source_policy="exam_material",
                )
            except Exception:
                extra = []
            for question in extra:
                stem = re.sub(r"[^a-z0-9]+", "", (question.get("question_text") or "").lower())
                if stem in seen_stems:
                    continue
                is_fact_sourced = str(question.get("source_document_id") or "").startswith("fact:")
                if is_fact_sourced:
                    fact_key = str(question.get("source_chunk_id") or "")
                    if fact_key and (fact_key in seen_fact_ids or fact_key in recent_fact_ids):
                        continue
                    if fact_key:
                        seen_fact_ids.add(fact_key)
                seen_stems.add(stem)
                questions.append(question)
                shortfall -= 1
                if shortfall <= 0:
                    break
    questions = questions[:total_questions]

    # Verify allocation accuracy within 1%
    weak_topics_set = set(config["weak_topics"])
    medium_topics_set = set(config["medium_topics"])
    strong_topics_set = set(config["strong_topics"])

    weak_actual = sum(1 for q in questions if q.get("topic") in weak_topics_set)
    medium_actual = sum(1 for q in questions if q.get("topic") in medium_topics_set)
    strong_actual = sum(1 for q in questions if q.get("topic") in strong_topics_set)

    total = len(questions) or 1
    weak_pct = weak_actual / total
    medium_pct = medium_actual / total
    strong_pct = strong_actual / total

    if not template and (abs(weak_pct - 0.60) > 0.01 or abs(medium_pct - 0.25) > 0.01 or abs(strong_pct - 0.15) > 0.01):
        # Log warning but don't fail - proceed with best effort
        print(f"WARNING: Allocation deviation - weak {weak_pct:.2%}, medium {medium_pct:.2%}, strong {strong_pct:.2%}")

    # Shuffle questions (don't reveal allocation to user)
    random.shuffle(questions)

    # Save mock
    mock_id = f"SM_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    save_smart_mock(mock_id, config["ranked_topics"], allocation, difficulty_curve, questions=questions)

    result = {
        "mock_id": mock_id,
        "template_id": template_id,
        "allocation": allocation,
        "allocation_summary": {
            "weak_topics_focused": weak_actual,
            "medium_topics": medium_actual,
            "strong_topics": strong_actual,
            "weak_pct": f"{weak_pct:.1%}",
            "medium_pct": f"{medium_pct:.1%}",
            "strong_pct": f"{strong_pct:.1%}",
        },
        "weakness_analysis": config["ranked_topics"],
        "questions": questions,
    }
    if template:
        result["time_limit_minutes"] = template.get("time_limit_minutes") or 60
        result["marks_per_question"] = template.get("marks_per_question") or (MOCK_EXAM_MAX_SCORE / max(1, len(questions)))
        result["negative_marking_per_wrong"] = round(float(result["marks_per_question"]) * 0.25, 4)
    return result


def _auto_schedule_srs_from_session(topic_counts: dict[str, list[int]]) -> None:
    """Plan v6 6.4: schedule topics that scored <60% this session for spaced review.

    Never raises into submit_mock; a scheduling failure must not break submission.
    """
    try:
        for topic, (seen, correct) in topic_counts.items():
            if not seen:
                continue
            pct = correct / seen * 100
            if pct < 60:
                interval = 1 if pct < 40 else 2
                schedule_topic_review(topic, interval_days=interval)
    except Exception as exc:
        print(f"[srs] auto-schedule after submit failed: {exc}")


def submit_mock(mock_id: str, answers: list[dict[str, Any]]) -> dict[str, Any]:
    conn = get_connection()
    try:
        # Idempotency guard: re-submitting the same mock used to insert duplicate
        # question_attempts rows on every call, silently double-counting attempts in
        # topic accuracy/weakness calculations and skewing every downstream
        # recommendation (next-action, readiness, mock allocation).
        session = conn.execute(
            "SELECT status FROM mock_sessions WHERE mock_id = ? LIMIT 1",
            (mock_id,),
        ).fetchone()
        if session and session["status"] == "submitted":
            raise ValueError(f"Mock {mock_id} has already been submitted; duplicate submissions are rejected to protect accuracy data.")

        question_rows = conn.execute(
            """
            SELECT mq.question_number, q.*
            FROM mock_questions mq
            JOIN questions q ON q.question_id = mq.question_id
            WHERE mq.mock_id = ?
            ORDER BY mq.question_number
            """,
            (mock_id,),
        ).fetchall()
        answer_map = {answer["question_id"]: answer for answer in answers}
        total_correct = 0
        total_answered = 0
        total_wrong = 0
        question_analysis: list[dict[str, Any]] = []
        topic_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for row in question_rows:
            answer = answer_map.get(row["question_id"], {})
            selected = answer.get("selected_answer")
            is_correct = bool(selected and selected == row["correct_answer"])
            is_answered = bool(selected)
            if selected:
                total_answered += 1
            if is_answered and not is_correct:
                total_wrong += 1
            if is_correct:
                total_correct += 1
            topic_counts[row["topic_id"]][0] += 1
            topic_counts[row["topic_id"]][1] += int(is_correct)
            citation = conn.execute("SELECT * FROM question_citations WHERE question_id = ? LIMIT 1", (row["question_id"],)).fetchone()
            question_analysis.append(
                {
                    "question_number": row["question_number"],
                    "question_id": row["question_id"],
                    "topic": row["topic_id"],
                    "question_text": row["question_text"],
                    "selected_answer": selected,
                    "correct_answer": row["correct_answer"],
                    "is_correct": is_correct,
                    "marked_for_review": bool(answer.get("marked_for_review")),
                    "time_spent_seconds": int(answer.get("time_spent_seconds", 0) or 0),
                    "explanation": row["explanation"],
                    "source": row["source"],
                    "source_document_id": citation["document_id"] if citation else None,
                    "source_chunk_id": citation["chunk_id"] if citation else None,
                    "page_start": citation["page_start"] if citation else None,
                    "page_end": citation["page_end"] if citation else None,
                    "citation_note": citation["citation_note"] if citation else None,
                    "options": [
                        {"label": letter, "text": row[f"option_{letter}"]}
                        for letter in "ABCDE"
                        if row[f"option_{letter}"]
                    ],
                }
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO answers
                (answer_id, mock_id, question_id, selected_answer, is_correct, time_spent_seconds, marked_for_review, answered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"ANS_{mock_id}_{row['question_id']}",
                    mock_id,
                    row["question_id"],
                    selected,
                    int(is_correct),
                    answer.get("time_spent_seconds", 0),
                    int(bool(answer.get("marked_for_review", False))),
                    datetime.now().isoformat(),
                ),
            )
            conn.execute(
                """
                INSERT INTO question_attempts
                (mock_id, question_id, topic, question_text, correct_option, your_option, is_correct, time_spent_seconds, attempt_date, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mock_id,
                    row["question_id"],
                    row["topic_id"],
                    row["question_text"],
                    row["correct_answer"],
                    selected,
                    int(is_correct),
                    answer.get("time_spent_seconds", 0),
                    datetime.now().date().isoformat(),
                    "SMART_MOCK",
                ),
            )
        total_questions = len(question_rows)
        accuracy = round((total_correct / total_questions * 100), 2) if total_questions else 0.0
        total_unanswered = max(0, total_questions - total_answered)
        marks_per_question = round(MOCK_EXAM_MAX_SCORE / total_questions, 4) if total_questions else 0.0
        negative_marking_per_wrong = round(marks_per_question * 0.25, 4)
        raw_score = round(total_correct * marks_per_question, 2)
        negative_marks = round(total_wrong * negative_marking_per_wrong, 2)
        final_score = round(max(0.0, raw_score - negative_marks), 2)
        conn.execute(
            """
            UPDATE mock_sessions
            SET submitted_at = ?, score = ?, accuracy = ?, status = ?
            WHERE mock_id = ?
            """,
            (datetime.now().isoformat(), final_score, accuracy, "submitted", mock_id),
        )
        conn.commit()
    finally:
        conn.close()
    calculate_topic_accuracy()
    # Plan v6 6.4: auto-schedule weak topics from this session for spaced review.
    _auto_schedule_srs_from_session(topic_counts)
    breakdown = []
    for topic, (seen, correct) in topic_counts.items():
        pct = round(correct / seen * 100, 2) if seen else 0.0
        breakdown.append(
            {
                "topic": topic,
                "display_name": topic_display(topic),
                "total_seen": seen,
                "total_correct": correct,
                "accuracy_pct": pct,
                "status": status_from_accuracy(pct, seen),
                "last_tested": datetime.now().isoformat(),
                "weakness_score": round(1 - (pct / 100), 3),
                "recent_accuracy": pct,
                "trend": "SESSION",
            }
        )
    # Plan v6 6.8: auto-save per-topic analytics post-submit so the timeline
    # endpoint has data without a separate frontend POST. Never breaks submit.
    try:
        topic_time: dict[str, int] = defaultdict(int)
        for entry in question_analysis:
            topic_time[entry["topic"]] += int(entry.get("time_spent_seconds") or 0)
        save_exam_analytics(
            mock_id,
            [
                {
                    "topic_id": entry["topic"],
                    "accuracy_pct": entry["accuracy_pct"],
                    "time_spent_seconds": topic_time.get(entry["topic"], 0),
                    "difficulty_rating": "hard" if entry["accuracy_pct"] < 40 else "medium" if entry["accuracy_pct"] < 70 else "easy",
                    "comparison_to_avg": round(entry["accuracy_pct"] - accuracy, 2),
                }
                for entry in breakdown
            ],
        )
    except Exception as exc:
        print(f"[analytics] auto-save after submit failed: {exc}")
    return {
        "mock_id": mock_id,
        "total_questions": total_questions,
        "total_answered": total_answered,
        "total_correct": total_correct,
        "total_wrong": total_wrong,
        "total_unanswered": total_unanswered,
        "accuracy_pct": accuracy,
        "raw_score": raw_score,
        "negative_marks": negative_marks,
        "final_score": final_score,
        "max_score": MOCK_EXAM_MAX_SCORE,
        "topic_breakdown": breakdown,
        "question_analysis": question_analysis,
    }


def record_amendment(amendment: dict[str, Any]) -> None:
    init_db()
    amendment_id = amendment["amendment_id"]
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO amendments
            (amendment_id, topic, rule_name, effective_date, old_value, new_value, source_url,
             verify_status, priority, questions_needed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                amendment_id,
                amendment.get("topic"),
                amendment.get("rule_name"),
                amendment.get("effective_date"),
                amendment.get("old_value"),
                amendment.get("new_value"),
                amendment.get("source_url", "manual"),
                amendment.get("verify_status", "UNVERIFIED"),
                amendment.get("priority", "NORMAL"),
                amendment.get("questions_needed", 3),
            ),
        )
        priority_map = {"CRITICAL": 10, "HIGH": 8, "NORMAL": 5, "LOW": 2}
        conn.execute(
            """
            INSERT OR REPLACE INTO amendment_events
            (amendment_id, title, topic_id, source_document_id, source_chunk_id, old_value, new_value,
             effective_date, publication_date, exam_priority, mastery_status, questions_generated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    COALESCE((SELECT mastery_status FROM amendment_events WHERE amendment_id = ?), 'NEW'),
                    COALESCE((SELECT questions_generated FROM amendment_events WHERE amendment_id = ?), 0))
            """,
            (
                amendment_id,
                amendment.get("rule_name"),
                amendment.get("topic"),
                amendment.get("source_document_id"),
                amendment.get("source_chunk_id"),
                amendment.get("old_value"),
                amendment.get("new_value"),
                amendment.get("effective_date"),
                None,
                priority_map.get(amendment.get("priority", "NORMAL"), 5),
                amendment_id,
                amendment_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


CRITICAL_AMENDMENTS = [
    ("AMN_FM_2025_KMP", "PH2_FM_REGS", "Fund Management Regulations 2025 - KMP eligibility", "2025-02-19", None, "KMP eligibility and experience requirements under the updated Fund Management framework.", "CRITICAL"),
    ("AMN_FM_2025_PPM", "PH2_FM_REGS", "PPM validity and fund management transition", "2025-12-24", None, "PPM validity and fund-management transition requirements from late 2025 updates.", "HIGH"),
    ("AMN_CMI_2025_REGS", "PH2_CMI", "Capital Market Intermediaries Regulations 2025", "2025-03-27", None, "New CMI framework with registration, principal officer and compliance officer requirements.", "CRITICAL"),
    ("AMN_CMI_2026_CERT", "PH2_CMI", "CMI certification course deadline", "2026-09-30", None, "CMI employees/KMPs must complete relevant mandatory certification within prescribed timeline.", "HIGH"),
    ("AMN_KRA_2025", "PH2_AML_KYC", "KYC Registration Agency Regulations 2025", "2025-04-21", None, "KRA framework for IFSC regulated entities and KYC record uploading obligations.", "CRITICAL"),
    ("AMN_PAYMENT_2025_PRB", "PH2_PAYMENT", "Payments Regulatory Board and payment services updates", "2025-09-22", None, "Payments Regulatory Board and payment-service regulatory updates affecting PSPs.", "HIGH"),
    ("AMN_TAS_2025_FINAL", "PH2_TECHFIN_TAS", "TechFin and Ancillary Services Regulations 2025", "2025-07-08", None, "Final TAS/TechFin framework for TechFin and Ancillary Services providers in IFSC.", "CRITICAL"),
    ("AMN_TAS_2025_FAQ", "PH2_TECHFIN_TAS", "TAS transition circular and FAQs", "2025-12-12", None, "Transition, registration and compliance clarifications under TAS Regulations.", "HIGH"),
    ("AMN_BULLION_2025_AP", "PH2_BULLION", "Bullion Exchange authorized persons market access", "2025-09-12", None, "Bullion Exchange market-access expansion for authorized persons.", "HIGH"),
    ("AMN_AML_2026_GUIDELINES", "PH2_AML_KYC", "AML/CFT/KYC Guidelines update", "2026-01-06", None, "Updated consolidated AML, CFT and KYC guidelines for IFSC regulated entities.", "CRITICAL"),
    ("AMN_LISTING_2025_SPAC_ESG", "PH2_LISTING", "SPAC, ESG, LEAP and listing updates", "2025-05-01", None, "Listing updates covering SPACs, ESG bonds, direct listing and LEAP-related rules.", "HIGH"),
    ("AMN_TRANSITION_BONDS_2026", "PH2_LISTING", "Transition Bonds and ISSB S2 at IFSC", "2026-01-01", None, "Transition finance and ISSB S2 related developments for IFSC markets.", "HIGH"),
    ("AMN_STEWARDSHIP_2025", "PH2_LISTING", "Stewardship Code framework in IFSC", "2025-10-23", None, "Stewardship Code framework for investment activities by regulated entities.", "NORMAL"),
    ("AMN_GUARANTEES_2026", "PH2_IFSCA_ACT", "IFSCA Guarantees Regulations 2026", "2026-01-12", None, "Guarantees regulatory framework introduced in 2026.", "HIGH"),
    ("AMN_COMMODITY_2026", "PH2_COMMODITY_TRADE", "Global Commodity Trading Hub framework", "2026-02-28", None, "GIFT IFSC positioning as global commodity trading hub.", "HIGH"),
]


def _pack_amendment_events() -> list[dict[str, Any]]:
    """Plan v6 6.6: amendment events compiled into the knowledge pack."""
    yield_priority = {"HIGH": "HIGH", "MED": "NORMAL", "LOW": "LOW"}
    events = []
    for fact in knowledge.load_all_facts():
        if fact.get("domain") != "amendments":
            continue
        events.append(
            {
                "amendment_id": fact["fact_id"],
                "topic": (fact.get("topic_ids") or ["PH2_CURRENT_AFFAIRS"])[0],
                "rule_name": fact["statement"][:120],
                "effective_date": fact.get("effective_date"),
                "old_value": None,
                "new_value": fact["statement"],
                "source_url": fact.get("source_doc") or "knowledge_pack",
                "source_document_id": None,
                "source_chunk_id": None,
                "verify_status": "PACK_SEEDED",
                "priority": yield_priority.get(fact.get("yield"), "NORMAL"),
                "questions_needed": 3,
            }
        )
    return events


def seed_critical_amendments() -> dict[str, Any]:
    seeded = 0
    questions_generated = 0
    # Plan v6 6.6: pack-seeded amendment events merged with the constants below.
    pack_seeded = 0
    for amendment in _pack_amendment_events():
        record_amendment(amendment)
        pack_seeded += 1
    for amendment_id, topic, title, effective_date, old_value, new_value, priority in CRITICAL_AMENDMENTS:
        chunks = chunks_for_topic(topic, limit=1, query=title)
        chunk = chunks[0] if chunks else None
        record_amendment(
            {
                "amendment_id": amendment_id,
                "topic": topic,
                "rule_name": title,
                "effective_date": effective_date,
                "old_value": old_value,
                "new_value": new_value,
                "source_url": chunk["title"] if chunk else "seeded_from_project_research",
                "source_document_id": chunk["document_id"] if chunk else None,
                "source_chunk_id": chunk["chunk_id"] if chunk else None,
                "verify_status": "SEEDED",
                "priority": priority,
                "questions_needed": 3,
            }
        )
        generated = generate_amendment_questions(amendment_id, topic, count=3, query=f"{title} {new_value}")
        questions_generated += len(generated)
        seeded += 1
    return {"status": "ok", "seeded": seeded, "pack_seeded": pack_seeded, "questions_generated": questions_generated}


def list_amendments(limit: int = 100) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM amendment_events
            ORDER BY exam_priority DESC, effective_date DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return rows_to_dicts(rows)
    finally:
        conn.close()


def amendment_candidate_chunks(limit: int = 25) -> list[dict[str, Any]]:
    """Return source chunks that look like new regulatory update/amendment material."""

    queries = [
        "amendment circular regulations 2025 2026 effective",
        "master circular directions framework deadline compliance",
        "fee circular April 2025 KYC CMI TechFin payment services",
        "Banking Handbook amendments additions deletions",
        "Guarantees Regulations 2026 Global In House Centres Regulations 2025",
    ]
    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for query in queries:
        for item in search_sources(query, limit=limit):
            chunk_id = item.get("chunk_id")
            if not chunk_id or chunk_id in seen:
                continue
            seen.add(chunk_id)
            title = str(item.get("title", ""))
            excerpt = str(item.get("excerpt", ""))
            haystack = f"{title}\n{excerpt}".lower()
            if not any(token in haystack for token in ["ifsca", "ifsc", "gift", "banking handbook", "bullion", "techfin", "payment services"]):
                continue
            score = 0
            for token in ["amendment", "circular", "regulation", "directions", "framework", "effective", "deadline", "2025", "2026"]:
                if token in haystack:
                    score += 1
            item["candidate_score"] = score
            candidates.append(item)
    candidates.sort(key=lambda row: (row.get("candidate_score", 0), row.get("page_start") or 0), reverse=True)
    return candidates[:limit]


def startup_amendment_radar_chunks(limit: int = 30) -> list[dict[str, Any]]:
    """Prioritize official legal/regulatory chunks for Gemini startup amendment radar."""

    candidates = amendment_candidate_chunks(limit=max(limit, 20))
    legal_queries = [
        ("IFSCA Act amendment Authority powers notification effective", "PH2_IFSCA_ACT"),
        ("International Financial Services Centres Authority Act current law section amendment", "PH2_IFSCA_ACT"),
        ("IFSCA regulation circular guideline direction effective 2026", None),
        ("Banking Handbook amendments additions deletions IFSCA", "PH2_BANKING"),
        ("TechFin Ancillary Services Regulations 2025 effective", "PH2_TECHFIN_TAS"),
    ]
    by_chunk = {item["chunk_id"]: item for item in candidates if item.get("chunk_id")}
    for query, topic_id in legal_queries:
        for item in search_sources(query, topic_id=topic_id, limit=8):
            if item.get("chunk_id"):
                by_chunk[item["chunk_id"]] = item
    return rank_source_results(list(by_chunk.values()))[:limit]


def pyq_candidate_chunks(limit: int = 25) -> list[dict[str, Any]]:
    """Return local memory/PYQ chunks for pattern calibration, not official law."""

    queries = [
        "memory based previous year question phase 1 phase 2 essay",
        "Write an Essay of about 250 270 words model essay",
        "Phase 2 Paper 1 memory questions precis comprehension",
        "IFSCA Grade A 2024 memory based question paper",
        "exam strategy questions pattern difficulty PYQ",
    ]
    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for query in queries:
        for item in search_sources(query, limit=limit):
            chunk_id = item.get("chunk_id")
            if not chunk_id or chunk_id in seen:
                continue
            seen.add(chunk_id)
            haystack = f"{item.get('title', '')}\n{item.get('excerpt', '')}".lower()
            if not any(token in haystack for token in ["memory", "previous year", "pyq", "question", "essay", "phase"]):
                continue
            item["candidate_score"] = sum(
                1
                for token in ["memory", "previous", "pyq", "question", "essay", "phase", "answer", "marks", "difficulty"]
                if token in haystack
            )
            candidates.append(item)
    candidates.sort(key=lambda row: (row.get("candidate_score", 0), row.get("page_start") or 0), reverse=True)
    return candidates[:limit]


def save_essay(submission: dict[str, Any], grade: dict[str, Any], source_suggestions: list[dict[str, Any]]) -> str:
    essay_id = grade.get("essay_id") or f"ESSAY_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    conn = get_connection()
    try:
        word_count = len(submission.get("essay_text", "").split())
        conn.execute(
            """
            INSERT OR REPLACE INTO essay_submissions
            (essay_id, prompt, essay_text, submitted_at, time_limit_minutes, word_count, topic_tags, overall_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                essay_id,
                submission.get("prompt"),
                submission.get("essay_text"),
                datetime.now().isoformat(),
                submission.get("time_limit_minutes"),
                word_count,
                submission.get("topic"),
                grade.get("total_score"),
            ),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO essay_scores
            (essay_id, content_accuracy, structure_clarity, regulatory_knowledge, examples_evidence,
             feedback_json, model_outline, source_suggestions_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                essay_id,
                grade["content_accuracy"]["score"],
                grade["structure_clarity"]["score"],
                grade["regulatory_knowledge"]["score"],
                grade["examples_evidence"]["score"],
                json.dumps(
                    {
                        "content_accuracy": grade["content_accuracy"]["feedback"],
                        "structure_clarity": grade["structure_clarity"]["feedback"],
                        "regulatory_knowledge": grade["regulatory_knowledge"]["feedback"],
                        "examples_evidence": grade["examples_evidence"]["feedback"],
                        "overall_feedback": grade.get("overall_feedback"),
                    }
                ),
                grade.get("model_outline"),
                json.dumps(source_suggestions),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return essay_id


def list_essays(limit: int = 25) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT e.*, s.content_accuracy, s.structure_clarity, s.regulatory_knowledge, s.examples_evidence, s.feedback_json
            FROM essay_submissions e
            LEFT JOIN essay_scores s ON s.essay_id = e.essay_id
            ORDER BY e.submitted_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return rows_to_dicts(rows)
    finally:
        conn.close()


def dashboard_data() -> dict[str, Any]:
    """Optimized dashboard data retrieval (Week 6 performance optimization).

    Per Context7 docs for SQLite: combine queries to reduce round-trips,
    leverage indexes for WHERE/ORDER BY, avoid N+1 queries.
    """
    init_db()
    conn = get_connection()
    try:
        # Combine multiple COUNT queries into single aggregation query (reduced round-trips)
        agg_row = conn.execute("""
            SELECT
                (SELECT COUNT(*) FROM mock_sessions WHERE status = 'submitted') AS mocks_completed,
                (SELECT COUNT(*) FROM mocks) AS uploaded_mocks,
                (SELECT COUNT(*) FROM smart_mocks) AS smart_mocks_count,
                (SELECT COUNT(*) FROM question_attempts) AS total_attempts,
                (SELECT SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) FROM question_attempts) AS total_correct,
                (SELECT AVG(overall_score) FROM essay_submissions WHERE overall_score IS NOT NULL) AS essay_avg
        """).fetchone()

        mocks_completed = agg_row["mocks_completed"] or 0
        uploaded_mocks = agg_row["uploaded_mocks"] or 0
        smart_mocks = agg_row["smart_mocks_count"] or 0
        total_attempts = agg_row["total_attempts"] or 0
        total_correct = agg_row["total_correct"] or 0
        essay_avg = agg_row["essay_avg"] or 0

        overall_accuracy = round((total_correct / total_attempts * 100), 2) if total_attempts else 0.0

        # Use indexed query for weak topics
        topic_heatmap = get_topic_stats(conn=conn)
        weak_topics = [item for item in topic_heatmap if item["status"] in {"UNKNOWN", "CRITICAL", "WEAK"}][:5]

        # Fetch amendments using indexed created_at
        amendments = rows_to_dicts(
            conn.execute(
                "SELECT * FROM amendment_events ORDER BY exam_priority DESC, effective_date DESC LIMIT 5"
            ).fetchall()
        )
    finally:
        conn.close()

    ingestion = get_ingestion_status()
    # estimated_score must be performance-only: the old formula summed accuracy
    # with library/amendment/essay bonuses, so a user with ZERO attempts saw an
    # "Est. Score" of ~19/100 purely from corpus size. Resource health is
    # reported separately so the dashboard can distinguish the two.
    estimated_score = round(overall_accuracy, 2)
    source_readiness = 10 if ingestion["documents"] >= 100 else 5 if ingestion["documents"] else 0
    amendment_bonus = min(10, len(amendments) * 0.6)
    essay_bonus = min(10, essay_avg * 0.10)
    resource_health = {
        "source_readiness": source_readiness,
        "amendment_bonus": round(amendment_bonus, 2),
        "essay_bonus": round(essay_bonus, 2),
        "documents_indexed": ingestion["documents"],
        "amendments_tracked": len(amendments),
    }

    if ingestion["documents"] == 0:
        action = "Ingest the source corpus before generating serious mocks."
    elif weak_topics:
        action = f"Take a penalty drill on {weak_topics[0]['display_name'] or weak_topics[0]['topic']}."
    elif not amendments:
        action = "Seed critical amendments and drill them."
    else:
        action = "Generate a 50-question smart mock in exam mode."

    targeting = intelligent_targeting_snapshot()

    return {
        "status": "ok",
        "total_mocks_completed": mocks_completed + uploaded_mocks,
        "smart_mocks_generated": smart_mocks,
        "total_questions_attempted": total_attempts,
        "overall_accuracy": overall_accuracy,
        "estimated_score": estimated_score,
        "resource_health": resource_health,
        "confidence_band": "low" if total_attempts < 100 else "medium" if total_attempts < 500 else "higher",
        "weak_topics": weak_topics,
        "topic_heatmap": topic_heatmap,
        "recent_amendments": amendments,
        "ingestion": ingestion,
        "next_recommended_action": action,
        "intelligence": {
            "top_targets": targeting["top_targets"][:5],
            "thin_question_banks": [item for item in targeting["question_bank"] if item.get("bank_status") != "READY"][:8],
            "thin_source_coverage": [item for item in targeting["coverage"] if item.get("coverage_status") == "THIN"][:8],
        },
    }


def essay_prompts() -> list[dict[str, str]]:
    return [
        {"prompt_id": "essay_gift_growth", "topic": "PH2_GIFT_IFSC", "prompt": "Discuss the role of GIFT IFSC in positioning India as a global financial services hub."},
        {"prompt_id": "essay_techfin", "topic": "PH2_TECHFIN_TAS", "prompt": "Evaluate the importance of the TechFin and Ancillary Services framework for the IFSC ecosystem."},
        {"prompt_id": "essay_fund_management", "topic": "PH2_FM_REGS", "prompt": "Explain how fund management reforms can deepen capital formation at GIFT IFSC."},
        {"prompt_id": "essay_aml", "topic": "PH2_AML_KYC", "prompt": "Why are AML, CFT and KYC controls central to the credibility of an international financial centre?"},
        {"prompt_id": "essay_transition_bonds", "topic": "PH2_LISTING", "prompt": "Assess the role of ESG, SGrBs and transition bonds in IFSC capital markets."},
    ]


def save_exam_analytics(exam_id: str, topic_analytics: list[dict[str, Any]]) -> int:
    """Save detailed analytics after exam completion. Per Context7 docs for SQLite: use try/finally for connection cleanup."""
    conn = get_connection()
    try:
        analytics_count = 0
        for topic in topic_analytics:
            analytics_id = f"ANALYTICS_{exam_id}_{topic['topic_id']}"
            conn.execute(
                """INSERT OR REPLACE INTO exam_analytics
                   (analytics_id, exam_id, topic_id, accuracy_pct, time_spent_seconds, difficulty_rating, comparison_to_avg)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (analytics_id, exam_id, topic["topic_id"], topic["accuracy_pct"], topic.get("time_spent_seconds", 0),
                 topic.get("difficulty_rating", "medium"), topic.get("comparison_to_avg", 0.0))
            )
            analytics_count += 1
        conn.commit()
        return analytics_count
    finally:
        conn.close()


def get_exam_analytics(exam_id: str) -> list[dict[str, Any]]:
    """Retrieve analytics for specific exam."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM exam_analytics WHERE exam_id = ? ORDER BY created_at DESC",
            (exam_id,)
        ).fetchall()
        return rows_to_dicts(rows)
    finally:
        conn.close()


def get_analytics_timeline(limit: int = 10) -> list[dict[str, Any]]:
    """Get analytics timeline (score trending across all mocks)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT e.mock_id AS exam_id, e.score, e.accuracy, AVG(a.accuracy_pct) as avg_topic_accuracy,
                      COUNT(DISTINCT a.topic_id) as topics_analyzed, e.generated_at as created_at
               FROM mock_sessions e
               LEFT JOIN exam_analytics a ON e.mock_id = a.exam_id
               WHERE e.score IS NOT NULL
               GROUP BY e.mock_id
               ORDER BY e.generated_at DESC
               LIMIT ?""",
            (limit,)
        ).fetchall()
        return rows_to_dicts(rows)
    finally:
        conn.close()


def schedule_topic_review(topic_id: str, interval_days: int = 1) -> str:
    """Schedule topic for spaced repetition review.

    Keeps exactly ONE row per topic: re-scheduling replaces the previous row.
    Previously every call appended a row, so repeated scheduling accumulated
    duplicate review items for the same topic.
    """
    conn = get_connection()
    try:
        review_id = f"SRS_{topic_id}_{int(datetime.now().timestamp())}"
        due_at = (datetime.now() + timedelta(days=interval_days)).isoformat()
        conn.execute(
            "DELETE FROM review_items WHERE item_type = 'topic' AND topic_id = ?",
            (topic_id,),
        )
        conn.execute(
            """INSERT INTO review_items (review_id, item_type, item_id, topic_id, due_at, interval_days, ease)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (review_id, "topic", topic_id, topic_id, due_at, interval_days, 2.5)
        )
        conn.commit()
        return review_id
    finally:
        conn.close()


def get_due_topics(conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    """Get topics due for SRS review today."""
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
    try:
        today = datetime.now().isoformat()[:10]
        rows = conn.execute(
            """SELECT r.*, t.display_name FROM review_items r
               LEFT JOIN topics t ON r.topic_id = t.topic_id
               WHERE r.item_type = 'topic' AND DATE(r.due_at) <= DATE(?)
               ORDER BY r.due_at ASC""",
            (today,)
        ).fetchall()
        return rows_to_dicts(rows)
    finally:
        if owns_conn:
            conn.close()


def _sm2_update(ease: float, interval_days: int, success: bool) -> tuple[float, int]:
    """Plan v6 6.4: one SM-2 step shared by topic and law review scheduling.

    Success raises ease (+0.1) and multiplies the interval; failure lowers ease
    (-0.2) and resets the interval to 1 day. Ease is clamped to [1.3, 4.0] and
    the interval to [1, 365] so SQLite date math never overflows.
    """
    ease = ease or 2.5
    interval_days = interval_days or 1
    if success:
        new_ease = min(4.0, max(1.3, ease + 0.1))
        new_interval = max(1, int(round(interval_days * new_ease)))
    else:
        new_ease = max(1.3, ease - 0.2)
        new_interval = 1
    return new_ease, min(new_interval, 365)


def mark_topic_reviewed(topic_id: str, success: bool = True) -> None:
    """Mark topic as reviewed and reschedule if needed.

    Only the soonest-due row for the topic is updated, and stale duplicate rows
    are removed. Previously the UPDATE touched EVERY row for the topic, so one
    completion wiped the per-item scheduling state of all duplicates.
    Plan v6 6.4: rescheduling now uses the shared SM-2 step, so topic reviews
    graduate intervals exactly like law reviews instead of a fixed 1→3 jump.
    """
    conn = get_connection()
    try:
        target = conn.execute(
            """SELECT review_id, ease, interval_days FROM review_items
               WHERE topic_id = ? AND item_type = 'topic'
               ORDER BY due_at ASC LIMIT 1""",
            (topic_id,),
        ).fetchone()
        if target:
            new_ease, new_interval = _sm2_update(
                target["ease"] or 2.5,
                target["interval_days"] or 1,
                success,
            )
            next_due = (datetime.now() + timedelta(days=new_interval)).isoformat()
            conn.execute(
                """UPDATE review_items SET due_at = ?, ease = ?, last_result = ?, interval_days = ?
                   WHERE review_id = ?""",
                (next_due, new_ease, "success" if success else "retry", new_interval, target["review_id"])
            )
            conn.execute(
                """DELETE FROM review_items
                   WHERE topic_id = ? AND item_type = 'topic' AND review_id != ?""",
                (topic_id, target["review_id"]),
            )
        conn.commit()
    finally:
        conn.close()


def create_study_path(exam_date: str, weak_topics: list[str], amendments_count: int = 0, weeks: list[dict[str, Any]] | None = None) -> str:
    """Generate personalized 12-week study path based on weakness and exam date.

    When `weeks` is provided (e.g. the plan returned by Gemini), it is persisted
    EXACTLY as given so GET /api/study-paths/current matches what the generate
    endpoint returned. Previously the endpoint returned Gemini weeks but the DB
    stored a separate deterministic plan, so the dashboard showed a different
    plan than the one just generated.
    """
    conn = get_connection()
    try:
        path_id = f"PATH_{uuid.uuid4().hex[:12]}"
        if weeks:
            weeks_data = []
            for week in weeks:
                normalized = dict(week)
                normalized.setdefault("status", "not_started")
                weeks_data.append(normalized)
        else:
            weeks_data = []
            weak_list = list(weak_topics[:3])  # Convert to list, not set

            for week_number in range(1, 13):
                if week_number <= 4:
                    focus = weak_list + ["PH2_IFSCA_ACT", "PH2_BANKING"]
                elif week_number <= 8:
                    focus = weak_list + ["PH2_FM_REGS", "PH2_CAPITAL"]
                else:
                    focus = weak_list if weak_list else ["PH2_PAYMENT", "PH2_AML_KYC"]

                weeks_data.append({
                    "week": week_number,
                    "focus_topics": focus[:5],
                    "daily_questions": 20 + (week_number % 3) * 5,
                    "milestone": f"Complete {5 - (week_number // 3)} topics" if week_number < 12 else "Final revision",
                    "status": "not_started"
                })

        conn.execute(
            "INSERT INTO study_paths (path_id, exam_date, weeks_json, milestone_count) VALUES (?, ?, ?, ?)",
            (path_id, exam_date, json.dumps(weeks_data), 12)
        )
        conn.commit()
        return path_id
    finally:
        conn.close()


def get_active_study_path() -> dict[str, Any] | None:
    """Get current active study path with progress."""
    conn = get_connection()
    try:
        sp = conn.execute(
            "SELECT * FROM study_paths ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if not sp:
            return None

        sp_dict = dict(sp)
        sp_dict["weeks_json"] = json.loads(sp["weeks_json"]) if isinstance(sp["weeks_json"], str) else sp["weeks_json"]

        progress = conn.execute(
            "SELECT * FROM study_path_progress WHERE path_id = ? ORDER BY week_number",
            (sp["path_id"],)
        ).fetchall()
        sp_dict["progress"] = [dict(p) for p in progress]
        return sp_dict
    finally:
        conn.close()


# ============================================================================
# PHASE 5: Essay Autonomy & Law Revision (Spaced Review Scheduling)
# ============================================================================

def schedule_law_review(item_type: str, item_id: str, topic_id: str, essay_id: str | None = None, interval_days: int = 1) -> str:
    """Schedule a law review item (provision, amendment, regulation) for spaced study using SM-2."""
    conn = get_connection()
    try:
        review_id = f"LAW_REV_{item_type}_{item_id}_{uuid.uuid4().hex[:6]}"
        due_at = (datetime.now() + timedelta(days=interval_days)).isoformat()

        conn.execute(
            """INSERT INTO review_items
               (review_id, item_type, item_id, topic_id, due_at, interval_days, ease)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (review_id, f"provision_{item_type}", item_id, topic_id, due_at, interval_days, 2.5)
        )
        conn.commit()
        return review_id
    finally:
        conn.close()


def get_law_review_due(limit: int = 20) -> list[dict[str, Any]]:
    """Get law review items due today or earlier (for daily revision)."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        today = datetime.now().isoformat()[:10]
        rows = conn.execute(
            """SELECT r.*, t.display_name FROM review_items r
               LEFT JOIN topics t ON r.topic_id = t.topic_id
               WHERE r.item_type LIKE 'provision_%' AND DATE(r.due_at) <= DATE(?)
               ORDER BY r.due_at ASC, r.ease DESC
               LIMIT ?""",
            (today, limit)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def mark_law_review_complete(review_id: str, success: bool = True) -> dict[str, Any]:
    """Mark law review complete and update ease/interval using SM-2 algorithm."""
    conn = get_connection()
    try:
        # Get current review item
        row = conn.execute(
            "SELECT * FROM review_items WHERE review_id = ?",
            (review_id,)
        ).fetchone()

        if not row:
            raise ValueError(f"Review item {review_id} not found")

        ease = row["ease"] or 2.5
        interval = row["interval_days"] or 1

        # Plan v6 6.4: shared SM-2 step (identical to topic review scheduling).
        new_ease, new_interval = _sm2_update(ease, interval, success)
        next_due = (datetime.now() + timedelta(days=new_interval)).isoformat()

        conn.execute(
            """UPDATE review_items
               SET ease = ?, interval_days = ?, due_at = ?, last_result = ?
               WHERE review_id = ?""",
            (new_ease, new_interval, next_due, "success" if success else "failure", review_id)
        )
        conn.commit()

        return {
            "review_id": review_id,
            "success": success,
            "new_ease": new_ease,
            "new_interval": new_interval,
            "next_due": next_due
        }
    finally:
        conn.close()


def get_high_yield_provisions(limit: int = 15) -> list[dict[str, Any]]:
    """Get high-yield provisions: amendments + frequently tested topics."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        # Get recent amendments (most exam-relevant)
        rows = conn.execute(
            """SELECT
                   amendment_id as item_id,
                   'amendment' as item_type,
                   topic as topic_id,
                   rule_name as title,
                   effective_date,
                   source_url,
                   priority,
                   questions_needed
               FROM amendments
               WHERE drilled = FALSE
               ORDER BY created_at DESC,
                 CASE priority WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1
                               WHEN 'NORMAL' THEN 2 WHEN 'LOW' THEN 3 ELSE 4 END
               LIMIT ?""",
            (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_weak_legal_areas(limit: int = 10) -> list[dict[str, Any]]:
    """Get legal areas where user scoring is weak (<60% accuracy)."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        # topic_stats has no display_name column; resolve it via the topics table
        # (previously this query failed with "no such column: display_name").
        rows = conn.execute(
            """SELECT
                   ts.topic,
                   COALESCE(t.display_name, ts.topic) AS display_name,
                   ts.total_seen,
                   ts.total_correct,
                   ts.accuracy_pct,
                   ts.status,
                   ts.last_tested
               FROM topic_stats ts
               LEFT JOIN topics t ON t.topic_id = ts.topic
               WHERE ts.accuracy_pct < 60.0 AND ts.total_seen >= 3
               ORDER BY ts.accuracy_pct ASC
               LIMIT ?""",
            (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_recent_amendments(days_back: int = 30, limit: int = 20) -> list[dict[str, Any]]:
    """Get recent amendments from the past N days, sorted by exam relevance."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        # created_at is a SQLite TIMESTAMP ('YYYY-MM-DD HH:MM:SS'); comparing against
        # an ISO 'T' cutoff string used to exclude boundary rows ('T' > ' ').
        cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d %H:%M:%S")
        rows = conn.execute(
            """SELECT
                   amendment_id,
                   topic,
                   rule_name,
                   effective_date,
                   old_value,
                   new_value,
                   source_url,
                   priority,
                   questions_needed,
                   created_at
               FROM amendments
               WHERE created_at >= ?
               ORDER BY
                 CASE priority WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1
                               WHEN 'NORMAL' THEN 2 WHEN 'LOW' THEN 3 ELSE 4 END,
                 created_at DESC
               LIMIT ?""",
            (cutoff_date, limit)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ============================================================================
# PHASE 4: RECOMMENDATION ENGINE SUPPORT FUNCTIONS
# ============================================================================


def get_amendments_for_topic_count(topic: str) -> int:
    """Get count of recent amendments for a topic (past 30 days).

    Per Context7 docs for SQLite: Use COUNT aggregate for performance.
    """
    conn = get_connection()
    try:
        # Match SQLite TIMESTAMP format ('YYYY-MM-DD HH:MM:SS'); ISO 'T' cutoffs
        # excluded boundary rows created on the cutoff instant.
        cutoff_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM amendments WHERE topic = ? AND created_at >= ?",
            (topic, cutoff_date)
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def get_weakest_topic_for_user(user_id: str) -> dict[str, Any] | None:
    """Get the weakest topic (lowest accuracy) for user.

    Per Context7 docs for SQLite: Use aggregate functions to calculate
    accuracy from is_correct boolean. Since the app doesn't implement multi-user
    tracking, this queries across all attempts.

    Returns: {topic, accuracy_pct, total_attempts, last_improved_at} or None if no data.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """SELECT
                   topic,
                   ROUND(100.0 * SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) /
                                     CAST(COUNT(*) AS FLOAT), 1) as accuracy_pct,
                   COUNT(*) as total_attempts,
                   MAX(CASE WHEN is_correct = 1 THEN attempt_date ELSE NULL END) as last_improved_at
               FROM question_attempts
               GROUP BY topic
               ORDER BY accuracy_pct ASC
               LIMIT 1""",
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_performance_history(user_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Get user's historical mock performance (scores over time).

    Returns: list of {tested_at, total_score} ordered by date.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT
                   ms.submitted_at as tested_at,
                   COALESCE(
                       ms.score,
                       SUM(CASE WHEN qa.is_correct = 1 THEN 4 WHEN qa.is_correct = 0 THEN -1 ELSE 0 END),
                       0
                   ) as total_score
               FROM mock_sessions ms
               LEFT JOIN question_attempts qa ON ms.mock_id = qa.mock_id
               WHERE ms.submitted_at IS NOT NULL
               GROUP BY ms.mock_id
               ORDER BY tested_at ASC
               LIMIT ?""",
            (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_weak_topics_for_user(user_id: str, threshold: float = 60.0) -> list[dict[str, Any]]:
    """Get all topics where user accuracy is below threshold (default 60%).

    Returns: list of {topic, accuracy_pct, total_attempts}.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT
                   topic,
                   ROUND(100.0 * SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) /
                                     CAST(COUNT(*) AS FLOAT), 1) as accuracy_pct,
                   COUNT(*) as total_attempts
               FROM question_attempts
               GROUP BY topic
               HAVING accuracy_pct < ?
               ORDER BY accuracy_pct ASC""",
            (threshold,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_topic_stats_for_user(user_id: str) -> list[dict[str, Any]]:
    """Get all topic stats for user (accuracy, attempts).

    Returns: list of {topic_id, accuracy_pct, total_attempts}.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT
                   topic as topic_id,
                   ROUND(100.0 * SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) /
                                     CAST(COUNT(*) AS FLOAT), 1) as accuracy_pct,
                   COUNT(*) as total_attempts
               FROM question_attempts
               GROUP BY topic
               ORDER BY accuracy_pct DESC""",
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ============================================================================
# AMENDMENT UPDATE TRACKER CRUD (plan v6, multi-model phase B)
# ============================================================================


def _normalize_update_title(title: str) -> str:
    """Lowercase + collapse whitespace for deterministic update_id hashing."""
    return re.sub(r"\s+", " ", title.strip().lower())


def save_amendment_update(update: dict[str, Any]) -> str:
    """Persist an amendment update row. Deterministic update_id from exam+title hash.

    INSERT OR REPLACE so identical discoveries de-duplicate automatically.
    update_id = "UPD_" + sha256(normalized(exam + "|" + title))[:12].
    Returns the update_id.
    """
    init_db()
    title = update.get("title", "")
    exam = update.get("exam", "IFSCA")
    normalized = _normalize_update_title(f"{exam}|{title}")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    update_id = f"UPD_{digest}"

    source_urls = update.get("source_urls") or update.get("source_urls_json") or []
    search_queries = update.get("search_queries") or update.get("search_queries_json") or []
    if isinstance(source_urls, str):
        source_urls = json.loads(source_urls) if source_urls else []
    if isinstance(search_queries, str):
        search_queries = json.loads(search_queries) if search_queries else []

    discovered_at = update.get("discovered_at") or datetime.now().isoformat()

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO amendment_updates
            (update_id, exam, category, title, summary, old_value, new_value,
             change_reason, verification_rationale, verification_status,
             topic_id, update_date, discovered_at, source_urls_json,
             search_queries_json, model_used, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                update_id,
                update.get("exam", "IFSCA"),
                update.get("category", "AMENDMENT"),
                title,
                update.get("summary"),
                update.get("old_value"),
                update.get("new_value"),
                update.get("change_reason"),
                update.get("verification_rationale"),
                update.get("verification_status", "NEW"),
                update.get("topic_id"),
                update.get("update_date"),
                discovered_at,
                json.dumps(source_urls) if source_urls else None,
                json.dumps(search_queries) if search_queries else None,
                update.get("model_used"),
                update.get("status", "ACTIVE"),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return update_id


def list_amendment_updates(
    sort: str = "date_desc",
    category: str | None = None,
    exam: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List amendment updates with sorting and filtering. Parse JSON columns back to lists."""
    init_db()
    order_clause = "ORDER BY COALESCE(update_date, discovered_at) DESC"
    if sort == "date_asc":
        order_clause = "ORDER BY COALESCE(update_date, discovered_at) ASC"
    elif sort == "priority":
        order_clause = (
            "ORDER BY CASE category "
            "WHEN 'AMENDMENT' THEN 1 WHEN 'ACT_CHANGE' THEN 2 "
            "WHEN 'REGULATION' THEN 3 WHEN 'CIRCULAR' THEN 4 "
            "WHEN 'CONSULTATION' THEN 5 WHEN 'RESULT' THEN 6 "
            "ELSE 7 END, COALESCE(update_date, discovered_at) DESC"
        )

    conditions: list[str] = []
    params: list[Any] = []
    if category:
        conditions.append("category = ?")
        params.append(category)
    if exam:
        conditions.append("exam = ?")
        params.append(exam)
    if status:
        conditions.append("status = ?")
        params.append(status)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT * FROM amendment_updates {where} {order_clause} LIMIT ?",
            params,
        ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            for json_col in ("source_urls_json", "search_queries_json"):
                raw = item.get(json_col)
                if raw:
                    try:
                        item[json_col] = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        item[json_col] = []
                else:
                    item[json_col] = []
            results.append(item)
        return results
    finally:
        conn.close()


def list_curated_amendments(sort: str = "date_desc", limit: int = 100) -> list[dict[str, Any]]:
    """Serve the curated amendments ledger in the amendment_updates shape.

    amendment_updates is written only by the tracker, so a tracker that has
    discovered nothing leaves §06 empty even though the amendments table holds
    real, verified rows from the committed corpus. Mapping into the existing
    update shape keeps the frontend contract single.
    """
    init_db()
    direction = "ASC" if sort == "date_asc" else "DESC"

    conn = get_connection()
    try:
        rows = conn.execute(
            f"""
            SELECT amendment_id, topic, rule_name, effective_date, old_value,
                   new_value, source_url, verify_status, created_at
            FROM amendments
            ORDER BY COALESCE(effective_date, created_at) {direction}
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                "update_id": row["amendment_id"],
                "title": row["rule_name"],
                "summary": row["new_value"],
                "old_value": row["old_value"],
                "new_value": row["new_value"],
                "verification_status": row["verify_status"] or "VERIFIED",
                "topic_id": row["topic"],
                "update_date": row["effective_date"],
                "discovered_at": row["created_at"],
                "category": "AMENDMENT",
                "status": "curated",
                "source_urls_json": [row["source_url"]] if row["source_url"] else [],
                "search_queries_json": [],
            }
            for row in rows
        ]
    finally:
        conn.close()


_VALID_UPDATE_STATUSES = {"ACTIVE", "REVIEWED", "DISMISSED"}


def set_amendment_update_status(update_id: str, status: str) -> bool:
    """Update the status of an amendment update row. Returns True if updated."""
    if status not in _VALID_UPDATE_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of {_VALID_UPDATE_STATUSES}")
    conn = get_connection()
    try:
        cursor = conn.execute(
            "UPDATE amendment_updates SET status = ? WHERE update_id = ?",
            (status, update_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def record_tracker_run(run: dict[str, Any]) -> str:
    """Persist a tracker run row. Returns run_id."""
    init_db()
    run_id = run.get("run_id") or f"RUN_{uuid.uuid4().hex[:12]}"
    searches = run.get("searches") or run.get("searches_json") or []
    if isinstance(searches, str):
        searches = json.loads(searches) if searches else []
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO tracker_runs
            (run_id, started_at, finished_at, model_used, searches_json,
             discovered, verified, contradicted, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                run.get("started_at"),
                run.get("finished_at"),
                run.get("model_used"),
                json.dumps(searches) if searches else None,
                run.get("discovered", 0),
                run.get("verified", 0),
                run.get("contradicted", 0),
                run.get("error"),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return run_id


def get_tracker_runs(limit: int = 10) -> list[dict[str, Any]]:
    """Return recent tracker runs, newest first."""
    init_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM tracker_runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            raw = item.get("searches_json")
            if raw:
                try:
                    item["searches_json"] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    item["searches_json"] = []
            else:
                item["searches_json"] = []
            results.append(item)
        return results
    finally:
        conn.close()


def get_latest_tracker_run() -> dict[str, Any] | None:
    """Return the most recent tracker run, or None."""
    runs = get_tracker_runs(limit=1)
    return runs[0] if runs else None


# Aliases matching plan v6 spec naming
list_tracker_runs = get_tracker_runs
latest_tracker_run = get_latest_tracker_run
