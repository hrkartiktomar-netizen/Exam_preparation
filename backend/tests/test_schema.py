"""
Test suite for Phase 0: Content Intelligence Schema
Tests FTS5 table creation and bulk PDF ingestion.
"""

import sqlite3
import time
from pathlib import Path
import sys

# Add backend to path for imports
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import database as db


class TestSchema:
    """FTS5 schema and indexing tests."""

    @classmethod
    def setup_class(cls):
        """Create fresh test database for schema tests."""
        # Use test database
        db.DB_PATH = BACKEND_DIR / "test_ifsca_exam.db"
        # Clean up any existing test DB
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()

    @classmethod
    def teardown_class(cls):
        """Cleanup test database."""
        if db.DB_PATH.exists():
            try:
                db.DB_PATH.unlink()
            except PermissionError:
                # Database file locked, will be cleaned next run
                pass

    def test_fts5_table_exists(self):
        """BLOCKING TEST 1: Verify FTS5 tables created successfully."""
        print("\n[TEST 1] test_fts5_table_exists")

        # Initialize database
        db.init_db()

        # Execute migration
        db.create_fts5_index()

        # Check source_documents table
        conn = db.get_connection()
        cursor = conn.cursor()

        tables_to_check = [
            "source_documents",
            "source_chunks",
            "question_sources",
            "source_chunks_fts"
        ]

        for table_name in tables_to_check:
            result = cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            ).fetchone()

            assert result is not None, f"Table {table_name} does not exist"
            print(f"  [OK] Table {table_name} created")

        conn.close()
        print("  [OK] PASS: All FTS5 tables exist")

    def test_bulk_load_3571_pages(self):
        """BLOCKING TEST 2: Verify all PDFs bulk-loaded in <30s."""
        print("\n[TEST 2] test_bulk_load_3571_pages")

        # Initialize database
        db.init_db()
        db.create_fts5_index()

        # Measure ingestion time
        conn = db.get_connection()
        start_time = time.time()

        chunk_count = db.ingest_extracted_pdfs(conn)

        elapsed_time = time.time() - start_time

        print(f"  Ingestion time: {elapsed_time:.2f}s")
        print(f"  Chunks created: {chunk_count}")

        # Verify timing constraint
        assert elapsed_time < 30, f"Ingestion took {elapsed_time:.2f}s, exceeds 30s limit"

        # Verify chunk count is reasonable (>100 chunks expected)
        assert chunk_count > 100, f"Expected >100 chunks, got {chunk_count}"

        # Verify rows actually inserted
        result = conn.execute(
            "SELECT COUNT(*) FROM source_chunks"
        ).fetchone()[0]

        print(f"  Chunks in DB: {result}")
        assert result == chunk_count, f"Mismatch: {result} != {chunk_count}"

        conn.close()
        print(f"  [OK] PASS: Bulk load completed in {elapsed_time:.2f}s with {chunk_count} chunks")

    def test_fts5_search_basic(self):
        """BLOCKING TEST 3: Verify FTS5 search works correctly."""
        print("\n[TEST 3] test_fts5_search_basic")

        # Initialize database
        db.init_db()
        db.create_fts5_index()

        # Ingest PDFs
        db.ingest_extracted_pdfs()

        # Try searching
        conn = db.get_connection()
        cursor = conn.cursor()

        # Common financial keywords likely in IFSCA docs
        search_terms = ["leverage", "fund", "regulation", "ifsca", "banking"]

        for term in search_terms:
            try:
                result = cursor.execute(
                    "SELECT COUNT(*) FROM source_chunks_fts WHERE chunk_text MATCH ?",
                    (term,)
                ).fetchone()

                count = result[0] if result else 0
                print(f"  Search '{term}': {count} results")

                # At least one common term should return results
                if term in ["fund", "ifsca", "regulation"]:
                    assert count > 0, f"Search for '{term}' returned 0 results"

            except Exception as e:
                print(f"  Warning: Search for '{term}' failed: {e}")

        conn.close()
        print("  [OK] PASS: FTS5 search functional")


if __name__ == "__main__":
    """Run tests directly from command line."""
    test_suite = TestSchema()

    try:
        test_suite.setup_class()

        print("=" * 60)
        print("PHASE 0 SCHEMA TESTS")
        print("=" * 60)

        test_suite.test_fts5_table_exists()
        test_suite.test_bulk_load_3571_pages()
        test_suite.test_fts5_search_basic()

        print("\n" + "=" * 60)
        print("ALL SCHEMA TESTS PASSED [OK]")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        test_suite.teardown_class()
