"""
Smart Material Classification & Previous Year Question Support

Ensures:
- No blind ingestion of coaching material
- Questions grounded only in official + ICSI sources
- Separate PYQ feature for memory-based papers
- Complete source authority tracking
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import database


def apply_smart_material_schema(conn: sqlite3.Connection | None = None) -> None:
    """Apply migration 003: Smart material classification schema."""

    owns_conn = conn is None
    if conn is None:
        conn = database.get_connection()

    try:
        # Migrations live beside this module, at backend/migrations/.
        migration_path = Path(__file__).resolve().parent / "migrations" / "003_smart_material_classification.sql"

        if not migration_path.exists():
            print(f"⚠️  Migration file not found: {migration_path}")
            return

        migration_sql = migration_path.read_text()

        # Execute migration
        conn.executescript(migration_sql)
        conn.commit()
        print("✅ Smart material classification schema applied successfully")

    except Exception as e:
        print(f"⚠️  Migration error (may be already applied): {e}")
        if owns_conn:
            conn.rollback()
    finally:
        if owns_conn:
            conn.close()


def populate_pdf_classifications(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """
    Populate all source_documents with purpose_category, authority_score, eligibility flags.

    Returns: Statistics on reclassification
    """

    owns_conn = conn is None
    if conn is None:
        conn = database.get_connection()

    try:
        # Classification rules (doc_name pattern -> classification)
        classifications = {
            # TIER 1: Official Regulatory
            'Annual Report 2020': ('OFFICIAL_REGULATORY', 0.95, True, True, False, 'GREEN'),
            'Annual Report 2021': ('OFFICIAL_REGULATORY', 0.95, True, True, False, 'GREEN'),
            'Annual Report 2022': ('OFFICIAL_REGULATORY', 0.95, True, True, False, 'GREEN'),
            'Annual Report 2023': ('OFFICIAL_REGULATORY', 0.95, True, True, False, 'GREEN'),
            'Annual Report 2024': ('OFFICIAL_REGULATORY', 0.95, True, True, False, 'GREEN'),
            'Bulletin': ('OFFICIAL_REGULATORY', 1.0, True, True, False, 'GREEN'),
            'Regulations': ('OFFICIAL_REGULATORY', 1.0, True, True, False, 'GREEN'),
            'Payment Services': ('OFFICIAL_REGULATORY', 1.0, True, True, False, 'GREEN'),
            'Listing Regulations': ('OFFICIAL_REGULATORY', 1.0, True, True, False, 'GREEN'),
            'TAS': ('OFFICIAL_REGULATORY', 1.0, True, True, False, 'GREEN'),

            # TIER 2: ICSI Study Material
            'Paper 4.6': ('ICSI_STUDY_MATERIAL', 0.95, True, True, False, 'GREEN'),
            'ICSI__CSJ': ('ICSI_STUDY_MATERIAL', 0.85, True, True, False, 'GREEN'),
            'ICSI Info Capsule': ('ICSI_STUDY_MATERIAL', 0.90, True, True, False, 'GREEN'),
            'Supplement': ('ICSI_STUDY_MATERIAL', 0.95, True, True, False, 'GREEN'),
            'ICSI Earlier': ('ICSI_STUDY_MATERIAL', 0.60, False, True, True, 'YELLOW'),

            # TIER 3: Exam Structure/Meta
            'Recruitment': ('EXAM_STRUCTURE_META', 0.0, False, True, True, 'GREEN'),
            'Results': ('EXAM_STRUCTURE_META', 0.0, False, True, True, 'GREEN'),
            'Cutoff': ('EXAM_STRUCTURE_META', 0.0, False, True, True, 'GREEN'),
            'Handout': ('EXAM_STRUCTURE_META', 0.0, False, True, True, 'GREEN'),
            'Syllabus': ('EXAM_STRUCTURE_META', 0.0, False, True, True, 'GREEN'),

            # TIER 4: Memory Papers (PYQ)
            'Memory-Based': ('MEMORY_PAPERS', 1.0, False, True, True, 'GREEN'),

            # TIER 5: Consulting
            'PwC': ('CONSULTING_INTELLIGENCE', 0.50, False, True, True, 'YELLOW'),
            'EY': ('CONSULTING_INTELLIGENCE', 0.40, False, True, True, 'YELLOW'),
            'Grant Thornton': ('CONSULTING_INTELLIGENCE', 0.35, False, True, True, 'YELLOW'),
            'KPMG': ('CONSULTING_INTELLIGENCE', 0.40, False, True, True, 'YELLOW'),

            # TIER 6: Current Affairs
            'Current-Affairs': ('CURRENT_AFFAIRS', 0.40, False, True, True, 'YELLOW'),
            'CurrentTap': ('CURRENT_AFFAIRS', 0.40, False, True, True, 'YELLOW'),

            # TIER 7: Coaching/Unverified
            'Scribd': ('COACHING_UNVERIFIED', 0.20, False, False, True, 'RED'),
            'IFSCA Banking Handbook': ('COACHING_UNVERIFIED', 0.20, False, False, True, 'RED'),
            'Compliance Handbook': ('COACHING_UNVERIFIED', 0.20, False, False, True, 'RED'),
            'Coaching': ('COACHING_UNVERIFIED', 0.20, False, False, True, 'RED'),
        }

        # Update source_documents
        docs = conn.execute("SELECT doc_id, name FROM source_documents").fetchall()

        updated = 0
        for doc_id, doc_name in docs:
            # Match document name to classification
            category = None
            authority_score = 0.5
            use_qgen = False
            use_study = False
            use_ref = False
            risk = 'GREEN'

            for pattern, (cat, auth, qgen, study, ref, r) in classifications.items():
                if pattern in doc_name or pattern.lower() in doc_name.lower():
                    category = cat
                    authority_score = auth
                    use_qgen = qgen
                    use_study = study
                    use_ref = ref
                    risk = r
                    break

            if category:
                conn.execute(
                    """
                    UPDATE source_documents
                    SET purpose_category = ?, authority_score = ?, is_qgen_eligible = ?,
                        is_study_eligible = ?, is_reference_only = ?, risk_level = ?
                    WHERE doc_id = ?
                    """,
                    (category, authority_score, use_qgen, use_study, use_ref, risk, doc_id)
                )
                updated += 1

        conn.commit()

        # Propagate to source_chunks
        chunk_updated = conn.execute(
            """
            UPDATE source_chunks
            SET purpose_category = (SELECT purpose_category FROM source_documents WHERE doc_id = source_chunks.doc_id),
                authority_score = (SELECT authority_score FROM source_documents WHERE doc_id = source_chunks.doc_id),
                is_qgen_eligible = (SELECT is_qgen_eligible FROM source_documents WHERE doc_id = source_chunks.doc_id)
            """
        ).rowcount

        conn.commit()

        return {
            "documents_classified": updated,
            "chunks_updated": chunk_updated,
            "status": "ok"
        }

    finally:
        if owns_conn:
            conn.close()


def query_qgen_eligible_chunks(topic_id: str | None = None, conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    """
    Query chunks that ARE ELIGIBLE for question generation.

    Filters:
    - is_qgen_eligible = TRUE (excludes coaching)
    - authority_score >= 0.5
    - Prioritizes OFFICIAL_REGULATORY, then ICSI_STUDY_MATERIAL

    Returns: Ordered list of eligible chunks
    """

    owns_conn = conn is None
    if conn is None:
        conn = database.get_connection()

    try:
        query = """
            SELECT sc.chunk_id, sc.chunk_text, sc.doc_id, sc.purpose_category, sc.authority_score,
                   sd.name as doc_name, sd.purpose_category as doc_category
            FROM source_chunks sc
            JOIN source_documents sd ON sc.doc_id = sd.doc_id
            WHERE sc.is_qgen_eligible = 1
            AND sc.authority_score >= 0.5
            AND sd.purpose_category IN ('OFFICIAL_REGULATORY', 'ICSI_STUDY_MATERIAL')
            ORDER BY
              CASE
                WHEN sd.purpose_category = 'OFFICIAL_REGULATORY' THEN 1
                WHEN sd.purpose_category = 'ICSI_STUDY_MATERIAL' THEN 2
                ELSE 9
              END,
              sc.authority_score DESC
            LIMIT 500
        """

        rows = conn.execute(query).fetchall()
        return [dict(row) for row in rows]

    finally:
        if owns_conn:
            conn.close()


def get_pyq_by_year_phase(
    year: int,
    phase: int,
    *,
    exam: str | None = None,
    paper: int | None = None,
    limit: int | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    """Get every bank question for one sitting (year + phase).

    A sitting is wider than a paper: 2024 Phase 1 spans two exams and two
    papers. Rows are grouped by exam, paper and subject rather than ordered by
    question_number alone, because question_number restarts per subject and
    ordering by it interleaves subjects into something that no longer reads as
    the paper that was actually sat. Grouping uses subject_id, not section:
    section holds 55 free-text variants including mojibake range markers, while
    subject_id is a small enum.

    Incomplete rows are excluded -- they lack options or a correct answer, so
    they cannot be presented as a blind attempt.
    """

    owns_conn = conn is None
    if conn is None:
        conn = database.get_connection()

    try:
        sql = """
            SELECT * FROM previous_year_questions
            WHERE year = ? AND phase = ? AND incomplete = 0
            """
        params: list[Any] = [year, phase]
        if exam:
            sql += " AND exam = ?"
            params.append(exam)
        if paper is not None:
            sql += " AND paper = ?"
            params.append(paper)
        sql += " ORDER BY exam, paper, COALESCE(subject_id, ''), question_number, rowid"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        rows = conn.execute(sql, params).fetchall()

        return [dict(row) for row in rows]

    finally:
        if owns_conn:
            conn.close()


def record_pyq_attempt(pyq_id: str, user_answer: str, is_correct: bool, time_spent_seconds: int, conn: sqlite3.Connection | None = None) -> bool:
    """Track user's attempt on a previous year question.

    Deliberately not wired into /api/pyq/{pyq_id}/submit. That endpoint records
    attempts in pyq_sessions + pyq_question_attempts, and /api/pyq/analytics
    reads only those tables. Writing here as well would fork attempt state into
    two stores nothing reconciles, so the bank columns this updates
    (attempted/user_answer/is_correct/time_spent_seconds/attempt_date) stay
    unwritten rather than disagreeing with the analytics source of truth.
    """

    owns_conn = conn is None
    if conn is None:
        conn = database.get_connection()

    try:
        conn.execute(
            """
            UPDATE previous_year_questions
            SET attempted = 1, user_answer = ?, is_correct = ?, time_spent_seconds = ?, attempt_date = CURRENT_TIMESTAMP
            WHERE pyq_id = ?
            """,
            (user_answer, is_correct, time_spent_seconds, pyq_id)
        )
        conn.commit()
        return True

    except Exception as e:
        print(f"Error recording PYQ attempt: {e}")
        return False

    finally:
        if owns_conn:
            conn.close()


def get_pyq_accuracy_by_topic(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Analyze PYQ attempts by topic."""

    owns_conn = conn is None
    if conn is None:
        conn = database.get_connection()

    try:
        rows = conn.execute(
            """
            SELECT topic_id, COUNT(*) as total, SUM(is_correct) as correct
            FROM previous_year_questions
            WHERE attempted = 1
            GROUP BY topic_id
            """
        ).fetchall()

        result = {}
        for row in rows:
            topic_id = row["topic_id"]
            total = row["total"]
            correct = row["correct"] or 0
            accuracy = (correct / total * 100) if total else 0
            result[topic_id] = {
                "total_attempted": total,
                "correct": correct,
                "accuracy_pct": accuracy
            }

        return result

    finally:
        if owns_conn:
            conn.close()


def get_material_authority_report(conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Generate report on material source authority distribution."""

    owns_conn = conn is None
    if conn is None:
        conn = database.get_connection()

    try:
        # Docs by category
        docs_by_cat = conn.execute(
            """
            SELECT purpose_category, COUNT(*) as count, AVG(authority_score) as avg_authority
            FROM source_documents
            GROUP BY purpose_category
            """
        ).fetchall()

        # Chunks by category
        chunks_by_cat = conn.execute(
            """
            SELECT purpose_category, COUNT(*) as count, AVG(authority_score) as avg_authority
            FROM source_chunks
            GROUP BY purpose_category
            """
        ).fetchall()

        # Qgen-eligible breakdown
        qgen_eligible = conn.execute(
            """
            SELECT purpose_category, COUNT(*) as count
            FROM source_chunks
            WHERE is_qgen_eligible = 1
            GROUP BY purpose_category
            """
        ).fetchall()

        # Risk distribution
        risk_dist = conn.execute(
            """
            SELECT risk_level, COUNT(*) as count
            FROM source_documents
            GROUP BY risk_level
            """
        ).fetchall()

        return {
            "documents_by_category": [dict(row) for row in docs_by_cat],
            "chunks_by_category": [dict(row) for row in chunks_by_cat],
            "qgen_eligible_chunks": [dict(row) for row in qgen_eligible],
            "risk_distribution": [dict(row) for row in risk_dist],
        }

    finally:
        if owns_conn:
            conn.close()


if __name__ == "__main__":
    print("Applying smart material classification...")
    apply_smart_material_schema()

    print("\nPopulating PDF classifications...")
    result = populate_pdf_classifications()
    print(f"Result: {result}")

    print("\nMaterial Authority Report:")
    report = get_material_authority_report()
    import json
    print(json.dumps(report, indent=2))
