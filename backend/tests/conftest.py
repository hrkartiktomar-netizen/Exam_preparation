"""Pytest fixtures and configuration for IFSCA exam prep integration tests.

Per Context7 docs for pytest: use fixtures for database isolation and test client setup.
Fixtures provide dependency injection, automatic cleanup, and test parallelization support.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

import pytest
from fastapi.testclient import TestClient

import database as db
from main import app


@pytest.fixture(scope="function")
def test_db() -> Generator[str, None, None]:
    """Create isolated temporary SQLite database for each test.

    Uses tempfile for automatic cleanup after test completes.
    Initializes schema but starts with empty data tables.
    """
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        temp_db_path = f.name

    try:
        # Initialize schema in temp database
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()

        # Create core tables (schema initialization)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                topic_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                description TEXT,
                base_weight REAL DEFAULT 1.0,
                exam_priority INTEGER DEFAULT 5,
                is_amendment_sensitive BOOLEAN DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attempts (
                attempt_id TEXT PRIMARY KEY,
                user_id TEXT DEFAULT 'default',
                topic TEXT NOT NULL,
                question_id TEXT,
                correct_option TEXT,
                your_option TEXT,
                is_correct BOOLEAN,
                time_spent_seconds INTEGER DEFAULT 0,
                attempt_at TEXT DEFAULT CURRENT_TIMESTAMP,
                mock_id TEXT,
                penalty INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS amendments (
                amendment_id TEXT PRIMARY KEY,
                topic TEXT,
                title TEXT,
                summary TEXT,
                effective_date TEXT,
                published_date TEXT,
                source_url TEXT,
                extracted_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS essays (
                essay_id TEXT PRIMARY KEY,
                user_id TEXT DEFAULT 'default',
                topic TEXT,
                essay_text TEXT,
                submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                graded_at TEXT,
                total_score INTEGER,
                content_accuracy_score INTEGER,
                structure_clarity_score INTEGER,
                regulatory_knowledge_score INTEGER,
                examples_evidence_score INTEGER,
                ai_model TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS source_documents (
                doc_id TEXT PRIMARY KEY,
                name TEXT,
                category TEXT,
                type TEXT,
                extracted_date TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS source_chunks (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT,
                start_line INTEGER,
                end_line INTEGER,
                text TEXT,
                section_title TEXT,
                page_num INTEGER,
                FOREIGN KEY (doc_id) REFERENCES source_documents(doc_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS question_sources (
                question_id TEXT,
                source_chunk_id TEXT,
                authority_score REAL,
                extraction_date TEXT,
                PRIMARY KEY (question_id, source_chunk_id),
                FOREIGN KEY (source_chunk_id) REFERENCES source_chunks(chunk_id)
            )
        """)

        # Insert static topic definitions
        topics = [
            ("PH2_IFSCA_ACT", "IFSCA Act and Authority", "IFSCA Act provisions", 0.90, 9, 1),
            ("PH2_FM_REGS", "Fund Management Regulations", "FME regulations", 1.00, 10, 1),
            ("PH2_BANKING", "Banking and IBUs", "Banking regulations", 0.95, 10, 1),
            ("PH2_CAPITAL", "Capital Markets", "Capital market rules", 0.95, 10, 1),
        ]

        for topic_id, display_name, description, weight, priority, sensitive in topics:
            cursor.execute(
                """INSERT OR IGNORE INTO topics
                   (topic_id, display_name, description, base_weight, exam_priority, is_amendment_sensitive)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (topic_id, display_name, description, weight, priority, sensitive)
            )

        conn.commit()
        conn.close()

        # Override database module's DB_PATH
        original_db_path = db.DB_PATH
        db.DB_PATH = Path(temp_db_path)

        yield temp_db_path

        # Restore original path
        db.DB_PATH = original_db_path

    finally:
        # Cleanup temp file
        Path(temp_db_path).unlink(missing_ok=True)


@pytest.fixture(scope="function")
def client(test_db: str) -> TestClient:
    """FastAPI test client with isolated database.

    Per Context7 docs for FastAPI testing: TestClient provides synchronous
    interface to async endpoints, suitable for integration tests.
    """
    return TestClient(app)


@pytest.fixture
def sample_attempt() -> dict[str, Any]:
    """Sample attempt data for mock testing."""
    return {
        "attempt_id": "att_test_001",
        "user_id": "test_user",
        "topic": "PH2_IFSCA_ACT",
        "question_id": "q_001",
        "correct_option": "A",
        "your_option": "A",
        "is_correct": True,
        "time_spent_seconds": 45,
        "mock_id": "mock_20260514_001",
        "penalty": 0,
    }


@pytest.fixture
def sample_amendment() -> dict[str, Any]:
    """Sample amendment for testing amendment workflow."""
    return {
        "amendment_id": f"amd_{int(datetime.now().timestamp())}",
        "topic": "PH2_FM_REGS",
        "title": "Amendment to FME Regulations",
        "summary": "Updated KMP requirements effective immediately",
        "effective_date": datetime.now().strftime("%Y-%m-%d"),
        "published_date": datetime.now().strftime("%Y-%m-%d"),
        "source_url": "https://example.com/circular",
        "extracted_at": datetime.now().isoformat(),
    }


@pytest.fixture
def sample_essay() -> dict[str, Any]:
    """Sample essay for testing essay grading workflow."""
    return {
        "essay_id": "ess_test_001",
        "user_id": "test_user",
        "topic": "PH2_CAPITAL",
        "essay_text": (
            "Capital markets in GIFT IFSC serve as a platform for "
            "international securities trading. The regulatory framework "
            "ensures investor protection and market integrity. "
            "Key regulations include the IFSCA Listing Rules. "
            "Examples: India INX, NSE IFSC serve institutional investors globally."
        ),
        "submitted_at": datetime.now().isoformat(),
    }


@pytest.fixture
def sample_question() -> dict[str, Any]:
    """Sample question for testing."""
    return {
        "question_id": "q_test_001",
        "topic": "PH2_IFSCA_ACT",
        "question_text": "Which section of the IFSCA Act defines the authority's powers?",
        "options": [
            {"label": "A", "text": "Section 10"},
            {"label": "B", "text": "Section 5"},
            {"label": "C", "text": "Section 15"},
            {"label": "D", "text": "Section 20"},
        ],
        "correct_option": "A",
        "explanation": "Section 10 outlines the powers and functions of IFSCA.",
        "difficulty": "medium",
        "source_chunk_id": "chunk_001",
    }
