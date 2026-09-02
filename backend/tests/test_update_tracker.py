"""Tests for the autonomous amendment/Act update tracker (plan v6, phase B).

All tests use a temporary SQLite database and monkeypatched Gemini calls.
No live Gemini in tests.
"""

from __future__ import annotations

import gc
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

import database as db


@pytest.fixture()
def temp_db():
    """Fresh temporary database with the full production schema + migrations."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".db") as f:
        temp_db_path = f.name
    original_db_path = db.DB_PATH
    db.DB_PATH = Path(temp_db_path)
    try:
        db.init_db()
        yield Path(temp_db_path)
    finally:
        db.DB_PATH = original_db_path
        gc.collect()
        for attempt in range(5):
            try:
                Path(temp_db_path).unlink(missing_ok=True)
                break
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))


# ---------------------------------------------------------------------------
# save_amendment_update + list deduplication
# ---------------------------------------------------------------------------


def test_save_and_list_dedupe_same_title(temp_db):
    """Same title saved twice should result in one row (INSERT OR REPLACE)."""
    uid1 = db.save_amendment_update({
        "title": "IFSCA Fund Management Amendment 2025",
        "summary": "Updated KMP requirements",
        "category": "AMENDMENT",
        "exam": "IFSCA",
        "verification_status": "VERIFIED",
    })
    uid2 = db.save_amendment_update({
        "title": "IFSCA Fund Management Amendment 2025",
        "summary": "Updated KMP requirements (updated)",
        "category": "AMENDMENT",
        "exam": "IFSCA",
        "verification_status": "VERIFIED",
    })
    assert uid1 == uid2  # deterministic ID from same title
    rows = db.list_amendment_updates(limit=100)
    matching = [r for r in rows if r["title"] == "IFSCA Fund Management Amendment 2025"]
    assert len(matching) == 1
    # Second save should have updated the summary
    assert matching[0]["summary"] == "Updated KMP requirements (updated)"


def test_save_different_titles_produce_different_ids(temp_db):
    uid1 = db.save_amendment_update({"title": "Alpha Update", "category": "AMENDMENT"})
    uid2 = db.save_amendment_update({"title": "Beta Update", "category": "CIRCULAR"})
    assert uid1 != uid2
    rows = db.list_amendment_updates(limit=100)
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


def test_sort_date_asc_vs_desc(temp_db):
    db.save_amendment_update({
        "title": "Older Update",
        "update_date": "2025-01-15",
        "category": "AMENDMENT",
    })
    db.save_amendment_update({
        "title": "Newer Update",
        "update_date": "2025-06-01",
        "category": "CIRCULAR",
    })

    desc = db.list_amendment_updates(sort="date_desc")
    assert desc[0]["title"] == "Newer Update"
    assert desc[1]["title"] == "Older Update"

    asc = db.list_amendment_updates(sort="date_asc")
    assert asc[0]["title"] == "Older Update"
    assert asc[1]["title"] == "Newer Update"


def test_sort_priority_order(temp_db):
    db.save_amendment_update({"title": "Circular A", "category": "CIRCULAR", "update_date": "2025-06-01"})
    db.save_amendment_update({"title": "Amendment B", "category": "AMENDMENT", "update_date": "2025-01-01"})
    db.save_amendment_update({"title": "Act Change C", "category": "ACT_CHANGE", "update_date": "2025-03-01"})

    priority = db.list_amendment_updates(sort="priority")
    categories = [r["category"] for r in priority]
    assert categories.index("AMENDMENT") < categories.index("ACT_CHANGE")
    assert categories.index("ACT_CHANGE") < categories.index("CIRCULAR")


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


def test_status_transition(temp_db):
    uid = db.save_amendment_update({"title": "Status Test", "category": "AMENDMENT"})
    assert db.set_amendment_update_status(uid, "REVIEWED") is True
    rows = db.list_amendment_updates(status="REVIEWED")
    assert len(rows) == 1
    assert rows[0]["status"] == "REVIEWED"

    assert db.set_amendment_update_status(uid, "DISMISSED") is True
    rows = db.list_amendment_updates(status="DISMISSED")
    assert len(rows) == 1


def test_invalid_status_rejected(temp_db):
    uid = db.save_amendment_update({"title": "Invalid Status Test", "category": "AMENDMENT"})
    with pytest.raises(ValueError, match="Invalid status"):
        db.set_amendment_update_status(uid, "BOGUS")


def test_set_status_nonexistent_returns_false(temp_db):
    assert db.set_amendment_update_status("UPD_nonexistent_999", "REVIEWED") is False


# ---------------------------------------------------------------------------
# Tracker pipeline with monkeypatched Gemini
# ---------------------------------------------------------------------------


def _mock_call_json_discovery_two_items(prompt, **kwargs):
    """Return two candidates for discovery calls; verdict/reason for others."""
    operation = kwargs.get("operation", "")
    if "discovery" in operation:
        return {
            "updates": [
                {
                    "title": "IFSCA New Circular on FME Eligibility 2026",
                    "summary": "New eligibility criteria for fund management entities",
                    "category": "CIRCULAR",
                    "exam": "IFSCA",
                    "topic_id": "PH2_FM_REGS",
                    "update_date": "2026-01-15",
                    "old_value": "Prior eligibility rules",
                    "new_value": "Updated eligibility with experience requirement",
                    "candidate_sources": ["https://ifsca.gov.in/circular/example"],
                },
                {
                    "title": "SEBI Grade A Pattern Change Fake Claim",
                    "summary": "Completely fabricated pattern change",
                    "category": "RESULT",
                    "exam": "SEBI",
                    "topic_id": "SUBJ_QUANT",
                    "update_date": "",
                    "old_value": "",
                    "new_value": "Pattern changed to 200 questions",
                    "candidate_sources": [],
                },
            ],
            "_grounding": {
                "web_search_queries": ["IFSCA circulars 2026", "SEBI pattern changes"],
                "sources": [{"title": "IFSCA Official", "uri": "https://ifsca.gov.in"}],
            },
        }
    elif "verify" in operation:
        title_in_prompt = "FME Eligibility" in prompt
        if title_in_prompt:
            return {
                "verdict": "VERIFIED",
                "rationale": "Confirmed via IFSCA official circular dated Jan 2026.",
                "sources": ["https://ifsca.gov.in/fme"],
                "_grounding": {
                    "web_search_queries": ["IFSCA FME eligibility 2026"],
                    "sources": [{"title": "IFSCA Circular", "uri": "https://ifsca.gov.in/fme"}],
                },
            }
        else:
            return {
                "verdict": "CONTRADICTED",
                "rationale": "No evidence found for SEBI pattern change claim.",
                "sources": [],
                "_grounding": {
                    "web_search_queries": ["SEBI Grade A pattern 2026"],
                    "sources": [],
                },
            }
    elif "reason" in operation:
        return {
            "change_reason": "Alignment with global fund management standards and GIFT IFSC competitiveness.",
            "exam_impact": "Medium - affects fund management entity eligibility questions.",
            "_grounding": {
                "web_search_queries": ["IFSCA FME eligibility reason"],
                "sources": [{"title": "IFSCA Rationale", "uri": "https://ifsca.gov.in/rationale"}],
            },
        }
    return None


@patch("update_tracker.call_json", side_effect=_mock_call_json_discovery_two_items)
def test_tracker_pipeline(mock_call, temp_db):
    """Discovery returns 2 items -> one VERIFIED, one CONTRADICTED.
    Only VERIFIED persisted as VERIFIED; CONTRADICTED persisted with its status.
    Run row recorded.
    """
    import update_tracker

    result = update_tracker.run_update_tracker()

    assert result["discovered"] == 2
    assert result["verified"] == 1
    assert result["contradicted"] == 1
    assert result["error"] is None

    # Check persisted updates
    updates = db.list_amendment_updates(limit=100)
    assert len(updates) == 2

    verified = [u for u in updates if u["verification_status"] == "VERIFIED"]
    contradicted = [u for u in updates if u["verification_status"] == "CONTRADICTED"]
    assert len(verified) == 1
    assert len(contradicted) == 1
    assert "FME Eligibility" in verified[0]["title"]
    assert "Fake Claim" in contradicted[0]["title"]

    # Verified item should have change_reason
    assert verified[0].get("change_reason")

    # Run row should exist
    runs = db.get_tracker_runs(limit=5)
    assert len(runs) >= 1
    latest = runs[0]
    assert latest["discovered"] == 2
    assert latest["verified"] == 1
    assert latest["contradicted"] == 1


# ---------------------------------------------------------------------------
# enrich_past_amendment_reasons with monkeypatched call_json
# ---------------------------------------------------------------------------


def _mock_call_json_enrich(prompt, **kwargs):
    """Return a change_reason for enrich calls."""
    return {
        "change_reason": "Regulatory alignment with international best practices.",
        "_grounding": {
            "web_search_queries": ["amendment reason research"],
            "sources": [{"title": "Source", "uri": "https://example.com/source"}],
        },
    }


@patch("update_tracker.call_json", side_effect=_mock_call_json_enrich)
def test_enrich_past_amendment_reasons(mock_call, temp_db):
    """enrich_past_amendment_reasons creates update rows for known amendments."""
    import update_tracker

    # Seed an amendment so there's something to enrich
    db.record_amendment({
        "amendment_id": "AMN_TEST_ENRICH_001",
        "topic": "PH2_FM_REGS",
        "rule_name": "Test Enrichment Amendment",
        "effective_date": "2025-06-01",
        "old_value": None,
        "new_value": "New rule for testing enrichment",
        "source_url": "test",
        "verify_status": "SEEDED",
        "priority": "NORMAL",
        "questions_needed": 3,
    })

    result = update_tracker.enrich_past_amendment_reasons(limit=8)
    assert result["enriched"] >= 1
    assert result["errors"] == 0

    # Should have created at least one update row
    updates = db.list_amendment_updates(limit=100)
    assert len(updates) >= 1
    # At least one should be ACT_CHANGE category
    act_changes = [u for u in updates if u["category"] == "ACT_CHANGE"]
    assert len(act_changes) >= 1


# ---------------------------------------------------------------------------
# JSON column parsing
# ---------------------------------------------------------------------------


def test_source_urls_and_queries_parsed_as_lists(temp_db):
    db.save_amendment_update({
        "title": "JSON Parse Test",
        "category": "AMENDMENT",
        "source_urls": ["https://a.com", "https://b.com"],
        "search_queries": ["query1", "query2"],
    })
    rows = db.list_amendment_updates(limit=10)
    assert len(rows) == 1
    assert isinstance(rows[0]["source_urls_json"], list)
    assert rows[0]["source_urls_json"] == ["https://a.com", "https://b.com"]
    assert isinstance(rows[0]["search_queries_json"], list)
    assert rows[0]["search_queries_json"] == ["query1", "query2"]


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def test_filter_by_category_and_exam(temp_db):
    db.save_amendment_update({"title": "IFSCA One", "category": "AMENDMENT", "exam": "IFSCA"})
    db.save_amendment_update({"title": "SEBI One", "category": "CIRCULAR", "exam": "SEBI"})

    ifsca_only = db.list_amendment_updates(exam="IFSCA")
    assert len(ifsca_only) == 1
    assert ifsca_only[0]["exam"] == "IFSCA"

    circular_only = db.list_amendment_updates(category="CIRCULAR")
    assert len(circular_only) == 1
    assert circular_only[0]["category"] == "CIRCULAR"


# ---------------------------------------------------------------------------
# Gemini unavailable guard
# ---------------------------------------------------------------------------


@patch("update_tracker.gemini_available", return_value=False)
def test_run_update_tracker_gemini_unavailable(mock_avail, temp_db):
    """run_update_tracker returns gemini_unavailable status without DB writes."""
    import update_tracker

    result = update_tracker.run_update_tracker()
    assert result["status"] == "gemini_unavailable"
    assert result["discovered"] == 0
    assert result["verified"] == 0
    # No tracker_runs row should be created
    runs = db.get_tracker_runs(limit=5)
    assert len(runs) == 0


@patch("update_tracker.gemini_available", return_value=False)
def test_enrich_gemini_unavailable(mock_avail, temp_db):
    """enrich_past_amendment_reasons returns gemini_unavailable without DB writes."""
    import update_tracker

    result = update_tracker.enrich_past_amendment_reasons(limit=5)
    assert result["status"] == "gemini_unavailable"
    assert result["enriched"] == 0


# ---------------------------------------------------------------------------
# record_amendment spy: VERIFIED calls it, CONTRADICTED does not
# ---------------------------------------------------------------------------


@patch("update_tracker.call_json", side_effect=_mock_call_json_discovery_two_items)
def test_verified_calls_record_amendment_contradicted_does_not(mock_call, temp_db):
    """VERIFIED candidates flow into db.record_amendment; CONTRADICTED do not."""
    import update_tracker

    with patch("database.record_amendment") as mock_record:
        update_tracker.run_update_tracker()

        # record_amendment should have been called exactly once (for VERIFIED only)
        assert mock_record.call_count == 1
        call_args = mock_record.call_args[0][0]
        assert call_args["verify_status"] == "TRACKER_VERIFIED"
        assert "FME Eligibility" in call_args["rule_name"]


# ---------------------------------------------------------------------------
# Dedupe on second pipeline run
# ---------------------------------------------------------------------------


@patch("update_tracker.call_json", side_effect=_mock_call_json_discovery_two_items)
def test_dedupe_on_second_run(mock_call, temp_db):
    """Running the pipeline twice with same discovery results should not duplicate rows."""
    import update_tracker

    result1 = update_tracker.run_update_tracker()
    count_after_first = len(db.list_amendment_updates(limit=100))

    result2 = update_tracker.run_update_tracker()
    count_after_second = len(db.list_amendment_updates(limit=100))

    # Same titles discovered -> upserted, not duplicated
    assert count_after_second == count_after_first
    # Both runs recorded
    runs = db.get_tracker_runs(limit=10)
    assert len(runs) >= 2


# ---------------------------------------------------------------------------
# tracker_runs record + latest
# ---------------------------------------------------------------------------


def test_tracker_runs_record_and_latest(temp_db):
    """record_tracker_run persists and latest_tracker_run retrieves it."""
    db.record_tracker_run({
        "run_id": "RUN_test001",
        "started_at": "2026-01-01T10:00:00",
        "finished_at": "2026-01-01T10:05:00",
        "model_used": "test-model",
        "searches": ["q1", "q2"],
        "discovered": 3,
        "verified": 2,
        "contradicted": 1,
        "error": None,
    })
    latest = db.latest_tracker_run()
    assert latest is not None
    assert latest["run_id"] == "RUN_test001"
    assert latest["discovered"] == 3
    assert latest["verified"] == 2

    runs = db.list_tracker_runs(limit=5)
    assert len(runs) == 1
    assert isinstance(runs[0].get("searches_json"), list)


# ---------------------------------------------------------------------------
# Filter by status
# ---------------------------------------------------------------------------


def test_filter_by_status(temp_db):
    uid1 = db.save_amendment_update({"title": "Active One", "category": "AMENDMENT", "status": "ACTIVE"})
    uid2 = db.save_amendment_update({"title": "Reviewed One", "category": "AMENDMENT", "status": "ACTIVE"})
    db.set_amendment_update_status(uid2, "REVIEWED")

    active = db.list_amendment_updates(status="ACTIVE")
    assert len(active) == 1
    assert active[0]["title"] == "Active One"

    reviewed = db.list_amendment_updates(status="REVIEWED")
    assert len(reviewed) == 1
    assert reviewed[0]["title"] == "Reviewed One"
