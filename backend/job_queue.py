"""Simple SQLite-based job queue for autonomous amendment polling and question generation.

Single-user, local execution. No distributed requirements.
"""

from __future__ import annotations

import database as db
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent
DB_PATH = BACKEND_DIR / "ifsca_exam.db"

# Job types and their executors
JOB_TYPES = {
    "amendment_questions": "Generate questions for amendment",
    "amendment_extraction": "Extract amendment metadata",
}

# Job status constants
JOB_STATUS_PENDING = "pending"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_COMPLETE = "complete"
JOB_STATUS_FAILED = "failed"


def init_job_queue_schema() -> None:
    """Create job queue tables if not exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS job_queue (
                job_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                target_resource TEXT,
                payload TEXT,
                result TEXT,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_job_queue_status_type
                ON job_queue(status, job_type);
            CREATE INDEX IF NOT EXISTS idx_job_queue_created_at
                ON job_queue(created_at DESC);
        """)
        conn.commit()
    finally:
        conn.close()


def enqueue_job(
    job_type: str,
    target_resource: str | None = None,
    payload: dict[str, Any] | None = None,
    max_retries: int = 3,
) -> str:
    """Enqueue a new job."""
    job_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            INSERT INTO job_queue (job_id, job_type, target_resource, payload, max_retries, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                job_type,
                target_resource,
                json.dumps(payload) if payload else None,
                max_retries,
                JOB_STATUS_PENDING,
            ),
        )
        conn.commit()
        return job_id
    finally:
        conn.close()


def get_pending_jobs(limit: int = 10) -> list[dict[str, Any]]:
    """Get pending jobs."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT * FROM job_queue
            WHERE status = ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (JOB_STATUS_PENDING, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def mark_job_running(job_id: str) -> None:
    """Mark job as running."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            UPDATE job_queue
            SET status = ?, started_at = ?
            WHERE job_id = ?
            """,
            (JOB_STATUS_RUNNING, datetime.now().isoformat(), job_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_job_complete(job_id: str, result: dict[str, Any]) -> None:
    """Mark job as complete."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            UPDATE job_queue
            SET status = ?, result = ?, completed_at = ?
            WHERE job_id = ?
            """,
            (JOB_STATUS_COMPLETE, json.dumps(result), datetime.now().isoformat(), job_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_job_failed(job_id: str, error_message: str) -> None:
    """Mark job as failed."""
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT retry_count, max_retries FROM job_queue WHERE job_id = ?",
            (job_id,),
        ).fetchone()

        if row:
            retry_count = row[0] + 1
            if retry_count < row[1]:
                # Retry: reset to pending
                conn.execute(
                    """
                    UPDATE job_queue
                    SET status = ?, error_message = ?, retry_count = ?, started_at = NULL
                    WHERE job_id = ?
                    """,
                    (JOB_STATUS_PENDING, error_message, retry_count, job_id),
                )
            else:
                # Max retries exceeded
                conn.execute(
                    """
                    UPDATE job_queue
                    SET status = ?, error_message = ?, retry_count = ?, completed_at = ?
                    WHERE job_id = ?
                    """,
                    (JOB_STATUS_FAILED, error_message, retry_count, datetime.now().isoformat(), job_id),
                )
        conn.commit()
    finally:
        conn.close()


async def execute_amendment_questions(target_resource: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Execute amendment question generation job.

    Args:
        target_resource: amendment_id
        payload: {topic_id, count}

    Returns:
        {amendment_id, questions_generated, drill_id}
    """
    amendment_id = target_resource
    topic_id = payload.get("topic_id", "PH2_CURRENT_AFFAIRS")
    count = payload.get("count", 3)

    try:
        questions = db.generate_amendment_questions(amendment_id, topic_id, count=count)
        return {
            "amendment_id": amendment_id,
            "questions_generated": len(questions),
            "question_ids": [q.get("question_id") for q in questions],
        }
    except Exception as e:
        raise RuntimeError(f"Amendment question generation failed: {str(e)}")


async def process_queue() -> dict[str, Any]:
    """Process all pending jobs."""
    pending = get_pending_jobs(limit=10)
    results = {
        "processed": 0,
        "completed": 0,
        "failed": 0,
        "jobs": [],
    }

    for job in pending:
        job_id = job["job_id"]
        mark_job_running(job_id)

        try:
            job_type = job["job_type"]
            target = job["target_resource"]
            payload = json.loads(job["payload"]) if job["payload"] else {}

            if job_type == "amendment_questions":
                result = await execute_amendment_questions(target, payload)
                mark_job_complete(job_id, result)
                results["completed"] += 1
            else:
                raise ValueError(f"Unknown job type: {job_type}")

            results["processed"] += 1
            results["jobs"].append({"job_id": job_id, "status": "complete"})

        except Exception as e:
            error_msg = str(e)
            mark_job_failed(job_id, error_msg)
            results["failed"] += 1
            results["jobs"].append({"job_id": job_id, "status": "failed", "error": error_msg})

    return results
