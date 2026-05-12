"""Test suite for Phase 1: Content Intelligence (Source-Grounded Questions)"""

import sys
import sqlite3
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from database import DB_PATH, init_db, get_connection, save_question
from authority_scoring import source_authority_score as calculate_source_authority


class TestContentIntelligence:
    """Test content intelligence and source citation functionality."""

    @classmethod
    def setup_class(cls):
        """Setup test database."""
        init_db()

    def test_all_generated_questions_have_citations(self):
        """TEST 1: All generated questions should have citation links."""
        print("\n[TEST 1] test_all_generated_questions_have_citations")

        # Create a test question with source data
        test_question = {
            "question_id": "Q_TEST_CITE_001",
            "topic": "PH2_FM_REGS",
            "source": "ifsca_regulation",
            "source_category": "regulations",
            "source_document_id": 1,
            "source_chunk_id": 1,
            "page_start": 10,
            "page_end": 12,
            "citation_note": "IFSCA Reg 2027, Section 5.2",
            "question_text": "What is the scope of fund management?",
            "options": [
                {"label": "A", "text": "Option A"},
                {"label": "B", "text": "Option B"},
                {"label": "C", "text": "Option C"},
                {"label": "D", "text": "Option D"},
            ],
            "correct_option": "B",
            "explanation": "Because it says so in the regulation.",
            "difficulty": "medium",
        }

        # Save the question
        save_question(test_question, created_by="test_source_engine")

        # Verify question exists in question_citations
        conn = get_connection()
        try:
            citation_row = conn.execute(
                "SELECT * FROM question_citations WHERE question_id = ?",
                (test_question["question_id"],),
            ).fetchone()
            assert citation_row is not None, "Question citation not found"
            print(f"  Citation found: {dict(citation_row)}")

            # Verify question exists in question_sources
            source_row = conn.execute(
                "SELECT * FROM question_sources WHERE question_id = ?",
                (test_question["question_id"],),
            ).fetchone()
            assert source_row is not None, "Question source link not found"
            print(f"  Source link found: {dict(source_row)}")

            print("  [OK] PASS: All questions have citation links")
        finally:
            conn.close()

    def test_citation_format_includes_page_number(self):
        """TEST 2: Citation format should include page numbers."""
        print("\n[TEST 2] test_citation_format_includes_page_number")

        conn = get_connection()
        try:
            citations = conn.execute(
                """
                SELECT question_id, page_start, page_end, citation_note
                FROM question_citations
                WHERE question_id LIKE 'Q_TEST_CITE_%'
                LIMIT 5
                """
            ).fetchall()

            assert len(citations) > 0, "No test citations found"

            for citation in citations:
                page_start = citation["page_start"]
                page_end = citation["page_end"]
                citation_note = citation["citation_note"]

                # Verify page numbers are present
                if page_start is not None:
                    assert page_start > 0, f"Invalid page_start: {page_start}"
                    print(f"  Citation for {citation['question_id']}: page {page_start}-{page_end}")

            print("  [OK] PASS: Citation format includes page numbers")
        finally:
            conn.close()

    def test_question_linked_to_source_chunk(self):
        """TEST 3: Questions should be linked to source chunks via FK."""
        print("\n[TEST 3] test_question_linked_to_source_chunk")

        conn = get_connection()
        try:
            # Verify FK constraint: question_sources.source_chunk_id → source_chunks.chunk_id
            source_links = conn.execute(
                """
                SELECT qs.question_id, qs.source_chunk_id, qs.authority_score, sc.chunk_id
                FROM question_sources qs
                LEFT JOIN source_chunks sc ON qs.source_chunk_id = sc.chunk_id
                WHERE qs.question_id LIKE 'Q_TEST_CITE_%'
                """
            ).fetchall()

            assert len(source_links) > 0, "No source links found"

            for link in source_links:
                question_id = link["question_id"]
                source_chunk_id = link["source_chunk_id"]
                authority_score = link["authority_score"]
                chunk_id = link["chunk_id"]

                # Verify FK exists
                if chunk_id is not None:
                    assert source_chunk_id == chunk_id, (
                        f"FK mismatch: source_chunk_id={source_chunk_id}, chunk_id={chunk_id}"
                    )
                    assert (
                        authority_score is not None
                    ), f"Authority score missing for {question_id}"
                    print(
                        f"  {question_id}: source_chunk_id={source_chunk_id}, "
                        f"authority_score={authority_score}"
                    )

            print("  [OK] PASS: Questions linked to source chunks with authority scores")
        finally:
            conn.close()

    def test_authority_score_calculated_correctly(self):
        """TEST 4: Authority scores should be calculated from doc_type and category."""
        print("\n[TEST 4] test_authority_score_calculated_correctly")

        test_question = {
            "question_id": "Q_TEST_AUTHORITY_001",
            "topic": "PH2_FM_REGS",
            "source": "ifsca_regulation",
            "source_category": "regulations",
            "source_document_id": 1,
            "source_chunk_id": 2,
            "page_start": 5,
            "page_end": 7,
            "citation_note": "IFSCA Regulation, Sec 3",
            "question_text": "Test authority score",
            "options": [
                {"label": "A", "text": "A"},
                {"label": "B", "text": "B"},
                {"label": "C", "text": "C"},
                {"label": "D", "text": "D"},
            ],
            "correct_option": "C",
            "explanation": "Authority test",
            "difficulty": "easy",
        }

        save_question(test_question, created_by="test_source_engine")

        conn = get_connection()
        try:
            source_row = conn.execute(
                "SELECT authority_score FROM question_sources WHERE question_id = ?",
                (test_question["question_id"],),
            ).fetchone()

            assert source_row is not None, "Source record not found"
            authority_score = source_row["authority_score"]

        # Manually calculate expected score
            expected = calculate_source_authority("ifsca_regulation", "regulations", exam_signal=0)

            assert authority_score == expected, (
                f"Authority score mismatch: got {authority_score}, expected {expected}"
            )

            print(
                f"  Authority score calculated correctly: {authority_score} == {expected}"
            )
            print("  [OK] PASS: Authority scores calculated correctly")
        finally:
            conn.close()

    def test_search_returns_questions_by_authority(self):
        """TEST 5: FTS5 search should return results ranked by authority score."""
        print("\n[TEST 5] test_search_returns_questions_by_authority")

        conn = get_connection()
        try:
            # Test FTS5 search on source chunks
            results = conn.execute(
                """
                SELECT DISTINCT sc.chunk_id, qs.authority_score
                FROM source_chunks_fts fts
                JOIN source_chunks sc ON fts.chunk_id = sc.chunk_id
                LEFT JOIN question_sources qs ON sc.chunk_id = qs.source_chunk_id
                WHERE source_chunks_fts MATCH 'ifsca OR regulation'
                ORDER BY qs.authority_score DESC
                LIMIT 5
                """
            ).fetchall()

            # Should have results
            assert len(results) > 0, "No FTS5 search results found"

            # Verify sorted by authority score descending
            scores = [row["authority_score"] for row in results if row["authority_score"] is not None]
            if len(scores) > 1:
                for i in range(len(scores) - 1):
                    assert scores[i] >= scores[i + 1], "Results not sorted by authority score"

            print(f"  Found {len(results)} results, top authority: {scores[0] if scores else 'N/A'}")
            print("  [OK] PASS: Search results ranked by authority")
        finally:
            conn.close()

    def test_source_distribution_pie_chart(self):
        """TEST 6: Source distribution should return pie chart data by category."""
        print("\n[TEST 6] test_source_distribution_pie_chart")

        conn = get_connection()
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

            assert len(distribution) > 0, "No source distribution data"

            total_chunks = sum(row["chunk_count"] for row in distribution)
            print(f"  Total chunks: {total_chunks}")

            for row in distribution:
                print(
                    f"    {row['source_type']}: {row['chunk_count']} chunks, "
                    f"{row['question_count'] or 0} Qs, avg authority {row['avg_authority'] or 50}"
                )

            print("  [OK] PASS: Source distribution pie chart data generated")
        finally:
            conn.close()


if __name__ == "__main__":
    """Run content intelligence tests directly."""
    test_suite = TestContentIntelligence()

    try:
        print("=" * 60)
        print("PHASE 1 - CONTENT INTELLIGENCE TESTS")
        print("=" * 60)

        test_suite.setup_class()
        test_suite.test_all_generated_questions_have_citations()
        test_suite.test_citation_format_includes_page_number()
        test_suite.test_question_linked_to_source_chunk()
        test_suite.test_authority_score_calculated_correctly()
        test_suite.test_search_returns_questions_by_authority()
        test_suite.test_source_distribution_pie_chart()

        print("\n" + "=" * 60)
        print("ALL CONTENT INTELLIGENCE TESTS PASSED [OK]")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
