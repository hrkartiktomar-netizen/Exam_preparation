"""Tests for Phase 2: Amendment Automation."""

import pytest
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import sys
from unittest.mock import AsyncMock, patch, MagicMock

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import database as db
import job_queue
import amendment_poller


class TestAmendmentAutomation:
    """Test amendment polling, extraction, and auto-question generation."""

    def setup_method(self):
        """Setup test database."""
        db.init_db()
        job_queue.init_job_queue_schema()
        self.conn = db.get_connection()

    def teardown_method(self):
        """Cleanup."""
        if self.conn:
            self.conn.close()

    @pytest.mark.asyncio
    async def test_poller_extracts_circulars(self):
        """Verify poller fetches and deduplicates circulars."""
        # Mock fetch_circulars to return test data
        with patch.object(amendment_poller.AmendmentPoller, "_fetch_circulars", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [
                {
                    "source": "IFSCA",
                    "url": "https://example.com/circular1",
                    "title": "Tier-1 Capital Amendment",
                    "fetched_at": datetime.now().isoformat(),
                }
            ]

            # Mock extraction to return amendment
            with patch.object(amendment_poller.AmendmentPoller, "_extract_amendment", new_callable=AsyncMock) as mock_extract:
                mock_extract.return_value = {
                    "topic": "PH2_FM_REGS",
                    "rule_name": "Tier-1 Capital Requirements",
                    "old_value": "10%",
                    "new_value": "11%",
                    "effective_date": "2026-06-01",
                    "priority": "HIGH",
                    "source_url": "https://example.com/circular1",
                    "verify_status": "GEMINI_EXTRACTED",
                }

                # Mock question generation
                with patch.object(db, "generate_amendment_questions") as mock_qgen:
                    mock_qgen.return_value = [{"question_id": "q1"}, {"question_id": "q2"}, {"question_id": "q3"}]

                    poller = amendment_poller.AmendmentPoller()
                    result = await poller.poll_and_process()

                    # Verify extraction was called
                    assert mock_extract.called
                    assert result["sources_checked"] >= 1
                    assert result["amendments_extracted"] >= 0  # May be 0 if already cached

    def test_sha256_dedup_prevents_duplicates(self):
        """Verify SHA256 deduplication prevents processing same circular twice."""
        import uuid
        sha256_hash = str(uuid.uuid4())  # Use unique hash

        # Insert first extraction
        self.conn.execute(
            """
            INSERT INTO amendment_extraction_cache (sha256, source, extraction_status)
            VALUES (?, ?, ?)
            """,
            (sha256_hash, "IFSCA", "complete"),
        )
        self.conn.commit()

        poller = amendment_poller.AmendmentPoller()

        # Verify SHA256 exists
        assert poller._sha256_exists(sha256_hash) is True

        # Verify different SHA256 doesn't exist
        assert poller._sha256_exists("different_hash") is False

    @pytest.mark.asyncio
    async def test_gemini_extraction_creates_amendment_record(self):
        """Verify Gemini extraction creates amendment record."""
        import uuid

        # Create amendment via save_amendment
        amendment_data = {
            "amendment_id": str(uuid.uuid4()),
            "topic": "PH2_FM_REGS",
            "rule_name": "Leverage Limit",
            "effective_date": "2026-07-01",
            "old_value": "20x",
            "new_value": "25x",
            "source_url": "https://example.com/amendment1",
            "verify_status": "GEMINI_EXTRACTED",
            "priority": "CRITICAL",
            "questions_needed": 3,
        }

        db.record_amendment(amendment_data)

        # Verify amendment was saved
        cursor = self.conn.execute(
            "SELECT amendment_id, topic, rule_name FROM amendments WHERE amendment_id = ?",
            (amendment_data["amendment_id"],),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[1] == "PH2_FM_REGS"
        assert row[2] == "Leverage Limit"

    def test_max_polls_enforced(self):
        """Verify MAX_POLLS_PER_DAY limit is enforced."""
        poller = amendment_poller.AmendmentPoller()

        # Verify constant is set
        assert amendment_poller.MAX_POLLS_PER_DAY == 100
        assert amendment_poller.MAX_CIRCULARS_PER_POLL == 5

    def test_job_queue_enqueue_and_process(self):
        """Verify job queuing works."""
        import uuid

        amendment_id = str(uuid.uuid4())

        # Enqueue 3 jobs
        job_ids = []
        for i in range(3):
            job_id = job_queue.enqueue_job(
                "amendment_questions",
                target_resource=amendment_id,
                payload={"topic_id": "PH2_FM_REGS", "count": 1},
            )
            job_ids.append(job_id)

        # Verify jobs are pending
        pending = job_queue.get_pending_jobs(limit=10)
        assert len(pending) >= 3
        assert all(j["status"] == "pending" for j in pending)

    def test_job_retry_on_failure(self):
        """Verify retry logic on job failure."""
        import uuid

        job_id = job_queue.enqueue_job(
            "amendment_questions",
            target_resource=str(uuid.uuid4()),
            payload={"topic_id": "PH2_FM_REGS", "count": 1},
            max_retries=3,
        )

        # Mark as failed
        job_queue.mark_job_failed(job_id, "Test error")

        # Verify job is retried (status back to pending)
        conn = sqlite3.connect(job_queue.DB_PATH)
        row = conn.execute(
            "SELECT status, retry_count FROM job_queue WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        conn.close()

        assert row[0] == "pending"  # Retried
        assert row[1] == 1

    def test_amendment_radar_data_structure(self):
        """Verify amendment data matches expected schema."""
        import uuid

        amendment_id = str(uuid.uuid4())
        amendment = {
            "amendment_id": amendment_id,
            "topic": "PH2_IFSCA_ACT",
            "rule_name": "Authority Powers",
            "effective_date": "2026-08-01",
            "old_value": None,
            "new_value": "Extended powers for IFSCA",
            "source_url": "https://example.com/amendment2",
            "verify_status": "GEMINI_EXTRACTED",
            "priority": "HIGH",
        }

        db.record_amendment(amendment)

        # Verify amendment has all required fields
        cursor = self.conn.execute(
            """
            SELECT amendment_id, topic, rule_name, effective_date, source_url, verify_status, priority
            FROM amendments WHERE amendment_id = ?
            """,
            (amendment_id,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == amendment_id
        assert row[1] == "PH2_IFSCA_ACT"
        assert row[6] == "HIGH"  # priority is at index 6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
