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

    Per Context7 docs for pytest: use real production schema, not mock schemas.
    Uses tempfile for automatic cleanup after test completes.
    Initializes full schema including migrations.
    """
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        temp_db_path = f.name

    try:
        # Override database module's DB_PATH temporarily
        original_db_path = db.DB_PATH
        db.DB_PATH = Path(temp_db_path)

        # Initialize database with PRODUCTION schema and migrations
        conn = sqlite3.connect(temp_db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")

        # Execute production schema
        conn.executescript(db.SCHEMA)

        # Create performance indexes
        db._create_performance_indexes(conn)

        # Seed topics
        db.seed_topics(conn)

        # Run Phase 1 migration (FTS5)
        try:
            db.create_fts5_index(conn)
        except Exception:
            pass  # Migration may already exist

        # Run Phase 2 migration (amendments)
        try:
            db._run_migration_002(conn)
        except Exception:
            pass  # Migration may already exist

        # Explicitly close connection before yield
        conn.close()

        yield temp_db_path

        # Restore original path
        db.DB_PATH = original_db_path

    finally:
        # Ensure all connections are closed before cleanup
        import gc
        gc.collect()

        # Try to cleanup temp file (may fail on Windows due to locks)
        try:
            Path(temp_db_path).unlink(missing_ok=True)
        except PermissionError:
            pass  # File may still be locked on Windows


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
