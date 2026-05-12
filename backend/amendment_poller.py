"""Amendment polling system: Daily autonomous monitoring of IFSCA, RBI, ICSI sources.

Polls regulatory sources → deduplicates → extracts via Gemini → queues questions.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

BACKEND_DIR = Path(__file__).resolve().parent
DB_PATH = BACKEND_DIR / "ifsca_exam.db"

# Polling configuration
POLL_SOURCES = {
    "IFSCA": "https://www.ifsca.gov.in/announcements",
    "RBI": "https://www.rbi.org.in/CommonMan/English/Scripts/Notification.aspx",
    "ICSI": "https://www.icsi.edu/",
}

MAX_POLLS_PER_DAY = 100
MAX_CIRCULARS_PER_POLL = 5
GEMINI_EXTRACTION_TIMEOUT = 30  # seconds
POLL_TIMEOUT = 10  # seconds per source


class AmendmentPoller:
    """Autonomous amendment polling and extraction."""

    def __init__(self):
        self.db_path = DB_PATH
        self.client = httpx.AsyncClient(timeout=POLL_TIMEOUT)

    async def poll_and_process(self) -> dict[str, Any]:
        """Main polling loop: fetch → dedup → extract → queue."""
        result = {
            "polled_at": datetime.now().isoformat(),
            "sources_checked": 0,
            "new_circulars_found": 0,
            "amendments_extracted": 0,
            "jobs_queued": 0,
            "errors": [],
        }

        for source_name, source_url in POLL_SOURCES.items():
            try:
                circulars = await self._fetch_circulars(source_name, source_url)
                result["sources_checked"] += 1
                result["new_circulars_found"] += len(circulars)

                for circular in circulars:
                    try:
                        amendment = await self._extract_amendment(circular)
                        if amendment:
                            amendment_id = await self._save_amendment(amendment)
                            await self._queue_questions(amendment_id, amendment)
                            result["amendments_extracted"] += 1
                            result["jobs_queued"] += 1
                    except Exception as e:
                        result["errors"].append(f"Extraction failed for {source_name}: {str(e)}")

            except Exception as e:
                result["errors"].append(f"Polling {source_name} failed: {str(e)}")

        # Log poll result
        self._record_poll_result(result)
        return result

    async def _fetch_circulars(self, source: str, url: str) -> list[dict[str, Any]]:
        """Fetch circular links from source."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            circulars = []
            # Extract links based on source-specific patterns
            for link in soup.find_all("a"):
                href = link.get("href", "")
                text = link.get_text(strip=True)

                # Filter for regulatory/circular content
                if any(
                    keyword in text.lower() or keyword in href.lower()
                    for keyword in ["circular", "notification", "amendment", "regulation", "directive"]
                ):
                    full_url = urljoin(url, href)
                    if full_url.startswith("http"):
                        circulars.append(
                            {
                                "source": source,
                                "url": full_url,
                                "title": text[:200],
                                "fetched_at": datetime.now().isoformat(),
                            }
                        )

            return circulars[:MAX_CIRCULARS_PER_POLL]

        except Exception as e:
            raise RuntimeError(f"Failed to fetch from {source}: {str(e)}")

    async def _extract_amendment(self, circular: dict[str, Any]) -> dict[str, Any] | None:
        """Extract amendment from circular using Gemini."""
        from gemini_integration import extract_and_verify_amendment

        # Check cache first (SHA256 dedup)
        sha256 = hashlib.sha256(circular["url"].encode()).hexdigest()
        if self._sha256_exists(sha256):
            return None  # Already processed

        try:
            # Fetch circular content
            response = await self.client.get(circular["url"])
            response.raise_for_status()

            # Extract text
            soup = BeautifulSoup(response.text, "html.parser")
            text_content = soup.get_text(separator="\n", strip=True)[:5000]

            # Extract via Gemini
            amendment = extract_and_verify_amendment(text_content, circular["url"])

            # Cache SHA256
            self._cache_extraction(sha256, circular["source"], amendment)

            return amendment

        except Exception as e:
            # Log but don't fail entire poll
            print(f"Gemini extraction failed for {circular['url']}: {str(e)}")
            return None

    async def _save_amendment(self, amendment: dict[str, Any]) -> str:
        """Save amendment to database."""
        import database as db
        import uuid

        amendment_id = str(uuid.uuid4())
        amendment["amendment_id"] = amendment_id

        db.record_amendment(amendment)
        return amendment_id

    async def _queue_questions(self, amendment_id: str, amendment: dict[str, Any]) -> None:
        """Queue 3 question generation jobs for amendment."""
        from job_queue import enqueue_job

        topic_id = self._map_topic_id(amendment.get("topic", "PH2_CURRENT_AFFAIRS"))

        for i in range(3):
            enqueue_job(
                "amendment_questions",
                target_resource=amendment_id,
                payload={"topic_id": topic_id, "count": 1},
                max_retries=2,
            )

    def _sha256_exists(self, sha256: str) -> bool:
        """Check if SHA256 already cached."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM amendment_extraction_cache WHERE sha256 = ? LIMIT 1",
                (sha256,),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def _cache_extraction(self, sha256: str, source: str, amendment: dict[str, Any]) -> None:
        """Cache extraction result."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO amendment_extraction_cache
                (sha256, source, extraction_status)
                VALUES (?, ?, ?)
                """,
                (sha256, source, "complete"),
            )
            conn.commit()
        finally:
            conn.close()

    def _record_poll_result(self, result: dict[str, Any]) -> None:
        """Record poll result for auditing."""
        conn = sqlite3.connect(self.db_path)
        try:
            import uuid
            poll_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO amendment_source_polls
                (poll_id, source, polled_at, new_circulars_found, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    poll_id,
                    "AGGREGATE",
                    datetime.now().isoformat(),
                    result["new_circulars_found"],
                    "success" if not result["errors"] else "partial_failure",
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _map_topic_id(self, topic: str) -> str:
        """Map amendment topic to TOPIC_DEFINITIONS entry."""
        topic_lower = topic.lower()
        mapping = {
            "capital": "PH2_FM_REGS",
            "leverage": "PH2_FM_REGS",
            "exposure": "PH2_FM_REGS",
            "ifsca": "PH2_IFSCA_ACT",
            "ifsc": "PH2_GIFT_IFSC",
            "gift": "PH2_GIFT_IFSC",
        }
        for key, value in mapping.items():
            if key in topic_lower:
                return value
        return "PH2_CURRENT_AFFAIRS"


async def run_amendment_poller() -> dict[str, Any]:
    """Run the amendment poller (called by APScheduler)."""
    poller = AmendmentPoller()
    return await poller.poll_and_process()
