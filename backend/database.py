"""SQLite persistence, ingestion, search, and local generation logic."""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from gemini_integration import generate_questions_with_gemini, gemini_available
from authority_scoring import source_authority_score as calculate_source_authority


BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
DB_PATH = BACKEND_DIR / "ifsca_exam.db"
EXTRACTED_DIR = PROJECT_ROOT / "extracted_pdfs"
SOURCE_PDF_DIR = PROJECT_ROOT / "source_documents" / "pdfs"
INDEX_PATH = EXTRACTED_DIR / "COMPREHENSIVE_INDEX.json"


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
        "keywords": ["gift city", "gift ifsc", "ifsc ecosystem", "global financial centre", "gandhinagar"],
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
        "keywords": ["current affairs", "budget", "annual report", "statistics", "turnover", "employment", "gfcI", "market update"],
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
]

TOPIC_BY_ID = {topic["topic_id"]: topic for topic in TOPIC_DEFINITIONS}
TOPIC_IDS = [topic["topic_id"] for topic in TOPIC_DEFINITIONS]
OBJECTIVE_MOCK_TOPIC_IDS = [topic_id for topic_id in TOPIC_IDS if topic_id != "PH2_ESSAY"]


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
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.executescript(SCHEMA)
    seed_topics(conn)
    conn.commit()

    # Run Phase 2 migration (amendment automation)
    try:
        _run_migration_002(conn)
    except Exception as e:
        print(f"Phase 2 migration already applied or error: {e}")

    conn.close()


def seed_topics(conn: sqlite3.Connection | None = None) -> None:
    owns_conn = conn is None
    if conn is None:
        conn = get_connection()
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
    if owns_conn:
        conn.commit()
        conn.close()


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
            conn.close()
        raise


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


def chunks_for_topic(topic_id: str, limit: int = 8, query: str | None = None) -> list[dict[str, Any]]:
    if query:
        results = search_sources(query, topic_id=topic_id, limit=limit)
        if results:
            return results
    conn = get_connection()
    try:
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
            (topic_id, limit),
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


def rank_exam_material_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for item in results:
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


def mock_source_chunks(topic_id: str, limit: int = 10, query: str | None = None) -> list[dict[str, Any]]:
    """Retrieve only local exam/PYQ/phase/material corpus chunks for mock generation."""

    topic_name = topic_display(topic_id)
    queries = [
        query or topic_name,
        f"{topic_name} IFSCA Grade A Phase 2 question paper memory PYQ",
        f"{topic_name} IFSCA Grade A syllabus study material ICSI",
        f"{topic_name} information handout phase paper exam",
        f"{topic_name} IFSCA regulations material compliance",
    ]
    by_chunk: dict[str, dict[str, Any]] = {}
    for item in chunks_for_topic(topic_id, limit=30):
        if item.get("chunk_id"):
            by_chunk[item["chunk_id"]] = item
    for source_query in queries:
        for item in search_sources(source_query, topic_id=topic_id, limit=30):
            if item.get("chunk_id"):
                by_chunk[item["chunk_id"]] = item
        for item in search_sources(source_query, limit=20):
            if item.get("chunk_id") and (topic_id in item.get("topic_tags", []) or is_exam_material_source(item, min_score=0.45)):
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
    path = Path(document.get("local_text_path") or "")
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def ifsca_act_full_text() -> dict[str, Any]:
    if table_count("documents") == 0:
        ingest_documents(force=False)
    document = ifsca_act_document()
    lines = read_document_lines(document)
    return {
        "document": document,
        "line_count": len(lines),
        "full_text": "\n".join(lines),
    }


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
        day_index = datetime.now().toordinal() % total_days
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
    amendment_recency = 0.0
    if topic_def.get("is_amendment_sensitive"):
        amendment_row = conn.execute(
            "SELECT COUNT(*) AS count FROM amendment_events WHERE topic_id = ? AND mastery_status != 'MASTERED'",
            (topic_id,),
        ).fetchone()
        amendment_recency = min(1.0, (amendment_row["count"] or 0) / 5)

    if attempts == 0:
        low_attempt_confidence = 1.0
        weakness = 0.15 * low_attempt_confidence + 0.10 * exam_weight + 0.10 * amendment_recency + 0.25
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
    time_pressure = min(1.0, max(0.0, (avg_time - 60) / 120))
    low_attempt_confidence = max(0.0, 1.0 - min(1.0, attempts / 30))
    historical_error = 1 - historical_accuracy
    recent_error = 1 - recent_accuracy
    weakness = (
        0.35 * historical_error
        + 0.25 * recent_error
        + 0.15 * low_attempt_confidence
        + 0.10 * exam_weight
        + 0.10 * amendment_recency
        + 0.05 * time_pressure
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
        # For strong topics: all easy (confidence building)
        difficulty_curve[topic] = ["easy"] * topic_qs

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


def question_quality_score(question_text: str | None, created_by: str | None = None, has_citation: bool = False) -> float:
    text = (question_text or "").strip()
    lower = text.lower()
    if not text:
        return 0.0
    score = 0.35
    if created_by == "gemini":
        score += 0.22
    if has_citation:
        score += 0.18
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
    ]
    options_text = [correct_text] + distractors
    random.shuffle(options_text)
    options = [{"label": label, "text": text} for label, text in zip(["A", "B", "C", "D"], options_text)]
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
            (question_id, source, topic_id, subtopic_id, question_text, option_a, option_b, option_c, option_d,
             correct_answer, explanation, difficulty, question_type, is_amendment_based, amendment_id,
             created_by, prompt_version, verification_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                question.get("correct_option"),
                question.get("explanation"),
                question.get("difficulty", "medium"),
                question.get("question_type", "source_grounded"),
                int(bool(question.get("is_amendment_based"))),
                question.get("amendment_id"),
                created_by,
                prompt_version,
                "VERIFIED_SOURCE_CITED" if question.get("source_chunk_id") else "LOCAL_FALLBACK",
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
            # Link question to source with authority score
            authority_score = question.get("authority_score")
            if authority_score is None:
                # Calculate authority score based on source metadata
                doc_type = question.get("source", "extracted_pdf")
                category = question.get("source_category", "default")
                authority_score = int(calculate_source_authority(doc_type, category, exam_signal=0))
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
        "source_policy": "exam_material" if row["question_type"] == "smart_mock" else "source_grounded",
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
        return questions
    finally:
        conn.close()


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
    if source_policy == "exam_material" or question_type == "smart_mock":
        chunks = mock_source_chunks(topic_id, limit=max(count * 2, 8), query=query)
    else:
        chunks = chunks_for_topic(topic_id, limit=max(count * 2, 6), query=query)
    if not chunks and source_policy != "exam_material":
        chunks = search_sources(query or topic_display(topic_id), limit=max(count * 2, 6))
    if not chunks:
        return []
    questions = generate_questions_with_gemini(
        topic_id,
        count,
        difficulty,
        chunks,
        question_type=question_type,
        is_amendment_based=is_amendment_based,
        source_policy=source_policy,
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

    if reuse_existing:
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
        questions = generate_topic_questions(
            topic_id,
            desired_count,
            difficulty="hard" if float(target.get("target_score", 0)) >= 0.65 else "medium",
            query=topic_display(topic_id),
            question_type="bank_build",
            use_gemini=use_gemini,
            strict_gemini=False,
            allow_local_fallback=False,
            reuse_existing=True,
            source_policy="exam_material",
        )
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
            WHERE amendment_id = ?
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
            (mock_id, mock_type, generated_at, total_questions, allocation_json, difficulty_curve_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mock_id,
                "smart",
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


def generate_smart_mock(total_questions: int = 50, mode: str = "balanced", use_gemini: bool = True) -> dict[str, Any]:
    if not use_gemini:
        raise RuntimeError("Gemini is mandatory for every smart mock. Local/source-bank fallback is disabled.")
    if not gemini_available():
        raise RuntimeError("Gemini is not available, so a serious smart mock cannot be generated.")

    config = get_smart_mock_config(total_questions=total_questions, mode=mode)
    allocation = config["allocation"]
    difficulty_curve = config["difficulty_curve"]  # Now: dict[topic] → list[difficulty]
    questions: list[dict[str, Any]] = []

    # Generate questions per topic with difficulty progression
    for topic_id, count in allocation.items():
        difficulties = difficulty_curve.get(topic_id, ["medium"] * count)
        # Ensure we have exactly 'count' difficulties
        if len(difficulties) != count:
            difficulties = difficulties[:count] + ["medium"] * (count - len(difficulties))

        # Generate questions with specific difficulties
        for i, difficulty in enumerate(difficulties):
            topic_questions = generate_topic_questions(
                topic_id,
                count=1,
                difficulty=difficulty,
                question_type="smart_mock",
                use_gemini=True,
                strict_gemini=True,
                allow_local_fallback=False,
                reuse_existing=False,
                source_policy="exam_material",
            )
            questions.extend(topic_questions)

    questions = questions[:total_questions]

    # Verify allocation accuracy within 1%
    weak_topics_set = set(config["weak_topics"])
    medium_topics_set = set(config["medium_topics"])
    strong_topics_set = set(config["strong_topics"])

    weak_actual = sum(1 for q in questions if q.get("topic") in weak_topics_set)
    medium_actual = sum(1 for q in questions if q.get("topic") in medium_topics_set)
    strong_actual = sum(1 for q in questions if q.get("topic") in strong_topics_set)

    # Verify percentages are within ±1% of target
    weak_pct = weak_actual / len(questions)
    medium_pct = medium_actual / len(questions)
    strong_pct = strong_actual / len(questions)

    if abs(weak_pct - 0.60) > 0.01 or abs(medium_pct - 0.25) > 0.01 or abs(strong_pct - 0.15) > 0.01:
        # Log warning but don't fail - proceed with best effort
        print(f"WARNING: Allocation deviation - weak {weak_pct:.2%}, medium {medium_pct:.2%}, strong {strong_pct:.2%}")

    # Shuffle questions (don't reveal allocation to user)
    random.shuffle(questions)

    # Save mock
    mock_id = f"SM_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
    save_smart_mock(mock_id, config["ranked_topics"], allocation, difficulty_curve, questions=questions)

    return {
        "mock_id": mock_id,
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


def submit_mock(mock_id: str, answers: list[dict[str, Any]]) -> dict[str, Any]:
    conn = get_connection()
    try:
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
                        {"label": "A", "text": row["option_a"]},
                        {"label": "B", "text": row["option_b"]},
                        {"label": "C", "text": row["option_c"]},
                        {"label": "D", "text": row["option_d"]},
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
        marks_per_question = round(100 / total_questions, 4) if total_questions else 0.0
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT questions_generated FROM amendment_events WHERE amendment_id = ?), 0))
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
                "NEW",
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


def seed_critical_amendments() -> dict[str, Any]:
    seeded = 0
    questions_generated = 0
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
    return {"status": "ok", "seeded": seeded, "questions_generated": questions_generated}


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
    init_db()
    conn = get_connection()
    try:
        mocks_completed = conn.execute("SELECT COUNT(*) FROM mock_sessions WHERE status = 'submitted'").fetchone()[0] or 0
        uploaded_mocks = conn.execute("SELECT COUNT(*) FROM mocks").fetchone()[0] or 0
        smart_mocks = conn.execute("SELECT COUNT(*) FROM smart_mocks").fetchone()[0] or 0
        attempts_row = conn.execute(
            "SELECT COUNT(*) AS total, SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct FROM question_attempts"
        ).fetchone()
        total_attempts = attempts_row["total"] or 0
        total_correct = attempts_row["correct"] or 0
        overall_accuracy = round((total_correct / total_attempts * 100), 2) if total_attempts else 0.0
        topic_heatmap = get_topic_stats(conn=conn)
        weak_topics = [item for item in topic_heatmap if item["status"] in {"UNKNOWN", "CRITICAL", "WEAK"}][:5]
        amendments = rows_to_dicts(
            conn.execute(
                "SELECT * FROM amendment_events ORDER BY exam_priority DESC, effective_date DESC LIMIT 5"
            ).fetchall()
        )
        essay_avg = conn.execute("SELECT AVG(overall_score) FROM essay_submissions WHERE overall_score IS NOT NULL").fetchone()[0] or 0
    finally:
        conn.close()
    ingestion = get_ingestion_status()
    source_readiness = 10 if ingestion["documents"] >= 100 else 5 if ingestion["documents"] else 0
    amendment_bonus = min(10, len(amendments) * 0.6)
    essay_bonus = min(10, essay_avg * 0.10)
    estimated_score = min(100, round((overall_accuracy * 0.70) + source_readiness + amendment_bonus + essay_bonus, 2))
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
