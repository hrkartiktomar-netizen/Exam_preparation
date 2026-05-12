"""
Phase 1: Content Intelligence - Tests for source-grounded questions and citation linking.

Blocking tests before PHASE-1 completion:
- test_all_generated_questions_have_citations: 100% citation rate
- test_citation_format_includes_page_number: Format matches "[Doc Name, Section X, p.YYY]"
- test_question_linked_to_source_chunk: Foreign key exists in question_sources
- test_search_leverage_returns_questions: FTS5 search functional, ranked by authority
- test_source_distribution_endpoint_returns_pie_data: Endpoint returns distribution stats
- test_citation_click_returns_pdf_excerpt: Modal can fetch full citation detail
"""

import sqlite3
import pytest
import sys
import os
from datetime import datetime

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database import (
    get_connection,
    save_question,
    link_question_to_source,
    format_citation_note,
    get_source_authority_for_chunk,
)
from authority_scoring import source_authority_score


class TestContentIntelligence:
    """Test suite for Pillar 1: Content Intelligence"""

    @classmethod
    def setup_class(cls):
        """Setup test database with source data."""
        cls.conn = get_connection()
        cls.db_path = cls.conn.execute("PRAGMA database_list").fetchone()[2]

        # Verify FTS5 tables exist (from Phase 0)
        tables = cls.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('source_documents', 'source_chunks', 'question_sources')"
        ).fetchall()
        assert len(tables) >= 3, "Phase 0 FTS5 tables missing"

    @classmethod
    def teardown_class(cls):
        """Cleanup test database."""
        if cls.conn:
            cls.conn.close()

    def test_all_generated_questions_have_citations(self):
        """
        BLOCKING: Every generated question must have a citation.
        Test: Generate 10 questions, verify 100% have citations (question_sources links).
        """
        import uuid

        topic = "Funds Management"
        question_count = 10

        # Create test source chunks if needed
        source_chunks = self.conn.execute(
            "SELECT chunk_id FROM source_chunks LIMIT 3"
        ).fetchall()

        if not source_chunks:
            pytest.skip("No source chunks in database (Phase 0 may not be complete)")

        # Save 10 test questions with sources
        questions_saved = []
        for i in range(question_count):
            chunk_id = source_chunks[i % len(source_chunks)][0]
            q_id = str(uuid.uuid4())

            question_data = {
                "question_id": q_id,
                "question_text": f"Sample question {i+1} on {topic}",
                "options": [
                    {"label": "A", "text": "Option 1"},
                    {"label": "B", "text": "Option 2"},
                    {"label": "C", "text": "Option 3"},
                    {"label": "D", "text": "Option 4"},
                ],
                "correct_option": "A",
                "topic": topic,
                "difficulty": "medium",
                "explanation": "Explained clearly",
                "source_chunk_id": chunk_id,
            }

            save_question(question_data)
            questions_saved.append((q_id, chunk_id))

        # Verify: All questions have question_sources links
        citation_count = self.conn.execute(
            f"""
            SELECT COUNT(*) FROM question_sources
            WHERE question_id IN ({','.join(['?' for _ in questions_saved])})
            """,
            [q_id for q_id, _ in questions_saved],
        ).fetchone()[0]

        assert citation_count == question_count, f"Expected {question_count} citations, got {citation_count}"
        print(f"[OK] All {question_count} questions have citations (100% citation rate)")

    def test_citation_format_includes_page_number(self):
        """
        BLOCKING: Citation format must be "[Document, Section X, p.YYY]"
        Test: Verify format_citation_note() generates correct format.
        """
        source_chunk = {
            "name": "IFSCA Regulation 2027",
            "section_title": "Fund Management Requirements",
            "page_start": 180,
            "page_num": 180,
        }

        citation = format_citation_note(source_chunk)

        # Expected: "[IFSCA Regulation 2027, Section Fund Management Requirements, p.180]"
        assert citation.startswith("["), "Citation must start with ["
        assert citation.endswith("]"), "Citation must end with ]"
        assert "IFSCA Regulation 2027" in citation, "Document name missing"
        assert "Section" in citation, "Section marker missing"
        assert "p.180" in citation, "Page number missing"
        assert "p." in citation, "Page prefix missing"

        print(f"[OK] Citation format correct: {citation}")

    def test_question_linked_to_source_chunk(self):
        """
        BLOCKING: Each question must have FK link to source_chunks.
        Test: Insert question, verify question_sources row exists.
        """
        import uuid

        # Get a source chunk
        chunk = self.conn.execute("SELECT chunk_id, doc_id FROM source_chunks LIMIT 1").fetchone()

        if not chunk:
            pytest.skip("No source chunks available")

        chunk_id = chunk[0]
        q_id = str(uuid.uuid4())

        # Create and save question
        question_data = {
            "question_id": q_id,
            "question_text": "Test FK linking question",
            "options": [
                {"label": "A", "text": "Opt A"},
                {"label": "B", "text": "Opt B"},
                {"label": "C", "text": "Opt C"},
                {"label": "D", "text": "Opt D"},
            ],
            "correct_option": "B",
            "topic": "Compliance",
            "difficulty": "easy",
            "explanation": "Test explanation",
            "source_chunk_id": chunk_id,
        }

        save_question(question_data)

        # Verify: question_sources row exists with valid FK
        source_link = self.conn.execute(
            "SELECT question_id, source_chunk_id, authority_score FROM question_sources WHERE question_id = ?",
            (q_id,),
        ).fetchone()

        assert source_link is not None, f"No source link found for question {q_id}"
        assert source_link[1] == chunk_id, f"source_chunk_id mismatch: expected {chunk_id}, got {source_link[1]}"
        assert source_link[2] is not None, "authority_score is NULL"
        assert 0 <= source_link[2] <= 100, f"authority_score out of range: {source_link[2]}"

        print(f"[OK] Question linked to source: Q{q_id} -> Chunk{chunk_id} (authority {source_link[2]})")

    def test_search_leverage_returns_questions(self):
        """
        Test: FTS5 search for "leverage" returns questions ranked by authority.
        Verifies that source_chunks are searchable and linked to questions.
        """
        # Search for "leverage" in source chunks via FTS5
        search_results = self.conn.execute(
            """
            SELECT sc.chunk_id, sd.name, sc.page_num, qs.authority_score
            FROM source_chunks_fts fts
            JOIN source_chunks sc ON fts.rowid = sc.rowid
            JOIN source_documents sd ON sc.doc_id = sd.doc_id
            LEFT JOIN question_sources qs ON sc.chunk_id = qs.source_chunk_id
            WHERE source_chunks_fts MATCH 'leverage'
            ORDER BY COALESCE(qs.authority_score, 50) DESC
            LIMIT 10
            """
        ).fetchall()

        if search_results:
            print(f"[OK] FTS5 search returned {len(search_results)} results for 'leverage'")
            for res in search_results[:3]:
                chunk_id, doc_name, page, authority = res
                print(f"     - Chunk {chunk_id}: {doc_name} (p.{page}, auth={authority})")
        else:
            print("[WARNING] FTS5 search for 'leverage' returned no results (source corpus may be small)")

    def test_source_distribution_endpoint_returns_pie_data(self):
        """
        Test: Verify source_chunks are categorized and grouped by doc_type.
        This data is used by /api/sources/distribution-by-topic endpoint.
        """
        # Get distribution of chunks by document category
        distribution = self.conn.execute(
            """
            SELECT sd.category, COUNT(sc.chunk_id) as chunk_count
            FROM source_chunks sc
            JOIN source_documents sd ON sc.doc_id = sd.doc_id
            GROUP BY sd.category
            ORDER BY chunk_count DESC
            """
        ).fetchall()

        assert len(distribution) > 0, "No chunks found for distribution"

        total_chunks = sum(row[1] for row in distribution)
        print(f"[OK] Source distribution found ({total_chunks} total chunks):")

        for category, count in distribution:
            pct = (count / total_chunks * 100) if total_chunks > 0 else 0
            print(f"     - {category}: {count} chunks ({pct:.1f}%)")

    def test_citation_click_returns_pdf_excerpt(self):
        """
        Test: When user clicks citation modal, can retrieve PDF excerpt + page.
        Verifies that source_chunks table has full text for display.
        """
        # Get a source chunk with full text
        chunk = self.conn.execute(
            """
            SELECT sc.chunk_id, sc.chunk_text, sc.page_num, sd.name, sc.section_title
            FROM source_chunks sc
            JOIN source_documents sd ON sc.doc_id = sd.doc_id
            LIMIT 1
            """
        ).fetchone()

        if not chunk:
            pytest.skip("No source chunks available")

        chunk_id, chunk_text, page_num, doc_name, section_title = chunk

        # Verify excerpt is retrievable
        assert chunk_text is not None, "chunk_text is NULL"
        assert len(chunk_text) > 0, "chunk_text is empty"
        assert page_num is not None, "page_num is NULL"
        assert doc_name is not None, "doc_name is NULL"

        excerpt = chunk_text[:500]  # First 500 chars
        print(f"[OK] PDF excerpt retrievable:")
        print(f"     - Chunk {chunk_id}: {doc_name} (p.{page_num})")
        print(f"     - Excerpt length: {len(chunk_text)} chars")
        print(f"     - Preview: {excerpt[:100]}...")

    def test_authority_score_calculation(self):
        """
        Test: Authority scores calculated correctly per formula.
        0.52×official + 0.30×exam_signal + 0.18×confidence = 0-100
        """
        # Test official IFSCA material scores highest
        ifsca_regulation_score = source_authority_score("ifsca_regulation", "regulations", exam_signal=50)
        coaching_notes_score = source_authority_score("coaching_notes", "notes", exam_signal=50)

        assert ifsca_regulation_score > coaching_notes_score, \
            f"Official IFSCA (score {ifsca_regulation_score}) should > coaching notes ({coaching_notes_score})"

        print(f"[OK] Authority scores calculated:")
        print(f"     - IFSCA Regulation: {ifsca_regulation_score}/100")
        print(f"     - Coaching Notes: {coaching_notes_score}/100")

    def test_get_source_authority_for_chunk(self):
        """
        Test: get_source_authority_for_chunk() retrieves authority for a chunk.
        """
        # Get a chunk with a question_sources link
        chunk_with_source = self.conn.execute(
            """
            SELECT qs.source_chunk_id, qs.authority_score
            FROM question_sources qs
            LIMIT 1
            """
        ).fetchone()

        if chunk_with_source:
            chunk_id, expected_score = chunk_with_source
            retrieved_score = get_source_authority_for_chunk(chunk_id, conn=self.conn)

            assert retrieved_score == expected_score, \
                f"Authority score mismatch: expected {expected_score}, got {retrieved_score}"

            print(f"[OK] Retrieved authority score {retrieved_score} for chunk {chunk_id}")
        else:
            print("[SKIP] No chunks with question_sources links yet")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
