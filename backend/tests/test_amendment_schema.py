"""Tests for Phase 2: Amendment Automation Schema and Polling."""

import sqlite3
import pytest
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import database as db


class TestAmendmentSchema:
    """Test amendment polling schema creation and constraints."""

    def setup_method(self):
        """Setup test database."""
        self.conn = db.get_connection()
        # Ensure schema tables exist
        db.init_db()

    def teardown_method(self):
        """Cleanup."""
        if self.conn:
            self.conn.close()

    def test_amendment_source_polls_table_exists(self):
        """Verify amendment_source_polls table created."""
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='amendment_source_polls'"
        )
        assert cursor.fetchone() is not None, "amendment_source_polls table does not exist"

    def test_amendment_extraction_cache_table_exists(self):
        """Verify amendment_extraction_cache table created."""
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='amendment_extraction_cache'"
        )
        assert cursor.fetchone() is not None, "amendment_extraction_cache table does not exist"

    def test_amendment_source_polls_columns(self):
        """Verify all required columns in amendment_source_polls."""
        cursor = self.conn.execute("PRAGMA table_info(amendment_source_polls)")
        columns = {row[1] for row in cursor.fetchall()}
        required = {"poll_id", "source", "polled_at", "new_circulars_found", "status", "error_message", "created_at", "updated_at"}
        assert required.issubset(columns), f"Missing columns: {required - columns}"

    def test_amendment_extraction_cache_columns(self):
        """Verify all required columns in amendment_extraction_cache."""
        cursor = self.conn.execute("PRAGMA table_info(amendment_extraction_cache)")
        columns = {row[1] for row in cursor.fetchall()}
        required = {"sha256", "source", "published_date", "extracted_at", "raw_content", "extraction_status", "amendment_id"}
        assert required.issubset(columns), f"Missing columns: {required - columns}"

    def test_sha256_unique_constraint(self):
        """Verify SHA256 is unique in amendment_extraction_cache."""
        from datetime import datetime
        import uuid
        sha256_test = str(uuid.uuid4())  # Use unique ID for this test

        # Insert first record
        self.conn.execute(
            """
            INSERT INTO amendment_extraction_cache (sha256, source, extraction_status)
            VALUES (?, ?, ?)
            """,
            (sha256_test, "IFSCA", "complete"),
        )
        self.conn.commit()

        # Try inserting duplicate SHA256
        with pytest.raises(sqlite3.IntegrityError):
            self.conn.execute(
                """
                INSERT INTO amendment_extraction_cache (sha256, source, extraction_status)
                VALUES (?, ?, ?)
                """,
                (sha256_test, "IFSCA", "complete"),
            )
            self.conn.commit()

    def test_amendment_source_polls_insert(self):
        """Verify we can insert into amendment_source_polls."""
        from datetime import datetime
        import uuid
        poll_id = str(uuid.uuid4())  # Use unique ID
        self.conn.execute(
            """
            INSERT INTO amendment_source_polls (poll_id, source, polled_at, status)
            VALUES (?, ?, ?, ?)
            """,
            (poll_id, "IFSCA", datetime.now().isoformat(), "success"),
        )
        self.conn.commit()

        # Verify insertion
        cursor = self.conn.execute(
            "SELECT poll_id, source FROM amendment_source_polls WHERE poll_id = ?",
            (poll_id,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == poll_id
        assert row[1] == "IFSCA"

    def test_amendment_extraction_cache_insert(self):
        """Verify we can insert into amendment_extraction_cache."""
        import uuid
        sha256 = str(uuid.uuid4())  # Use unique ID
        self.conn.execute(
            """
            INSERT INTO amendment_extraction_cache (sha256, source, extraction_status)
            VALUES (?, ?, ?)
            """,
            (sha256, "IFSCA", "pending"),
        )
        self.conn.commit()

        # Verify insertion
        cursor = self.conn.execute(
            "SELECT sha256, source FROM amendment_extraction_cache WHERE sha256 = ?",
            (sha256,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == sha256

    def test_amendment_extraction_cache_fk_reference(self):
        """Verify amendment_id can reference amendments table."""
        from datetime import datetime
        import uuid

        # Create an amendment first
        amendment_id = str(uuid.uuid4())
        self.conn.execute(
            """
            INSERT INTO amendments (amendment_id, topic, rule_name, effective_date)
            VALUES (?, ?, ?, ?)
            """,
            (amendment_id, "Tier-1 Capital", "Capital Requirements", "2026-06-01"),
        )
        self.conn.commit()

        # Insert extraction cache with FK reference
        sha256_unique = str(uuid.uuid4())  # Unique for this test
        self.conn.execute(
            """
            INSERT INTO amendment_extraction_cache (sha256, source, extraction_status, amendment_id)
            VALUES (?, ?, ?, ?)
            """,
            (sha256_unique, "IFSCA", "complete", amendment_id),
        )
        self.conn.commit()

        # Verify insertion
        cursor = self.conn.execute(
            "SELECT amendment_id FROM amendment_extraction_cache WHERE sha256 = ?",
            (sha256_unique,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == amendment_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
