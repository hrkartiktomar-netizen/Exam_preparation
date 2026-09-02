"""Autonomous agentic amendment/Act update tracker (plan v6, multi-model phase B).

Multi-step pipeline using Gemini with Google Search grounding:
1. Discovery: search for new IFSCA/SEBI regulatory updates
2. Corroboration: independent verification of each candidate
3. Reason extraction: for verified items, research change reason
4. Persistence: save to amendment_updates + flow VERIFIED into amendments + job queue

All Gemini calls use profile="accuracy" and google_search=True.
Never raises — all errors caught, logged, and recorded in tracker_runs.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Any

import database as db
import knowledge
from gemini_integration import call_json, gemini_available, get_gemini_health

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON schemas for Gemini structured output
# ---------------------------------------------------------------------------

DISCOVERY_SCHEMA = {
    "type": "object",
    "properties": {
        "updates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": ["AMENDMENT", "CIRCULAR", "ACT_CHANGE", "REGULATION", "CONSULTATION", "RESULT"],
                    },
                    "exam": {"type": "string", "enum": ["IFSCA", "SEBI"]},
                    "topic_id": {"type": "string"},
                    "update_date": {"type": "string"},
                    "old_value": {"type": "string"},
                    "new_value": {"type": "string"},
                    "candidate_sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "summary", "category", "exam"],
            },
        },
    },
    "required": ["updates"],
}

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["VERIFIED", "CONTRADICTED"]},
        "rationale": {"type": "string"},
        "sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdict", "rationale"],
}

REASON_SCHEMA = {
    "type": "object",
    "properties": {
        "change_reason": {"type": "string"},
        "exam_impact": {"type": "string"},
    },
    "required": ["change_reason"],
}

MAX_CANDIDATES_PER_RUN = 8


def _valid_topic_id(topic_id: str | None) -> str | None:
    """Return topic_id if it exists in the canonical list, else None."""
    if not topic_id:
        return None
    return topic_id if topic_id in db.TOPIC_IDS else None


def _build_known_digest() -> set[str]:
    """Build a normalized-title digest of known amendments + existing updates."""
    digest: set[str] = set()
    try:
        for item in db.list_amendments(limit=40):
            title = item.get("title") or item.get("rule_name") or ""
            if title:
                digest.add(re.sub(r"\s+", " ", title.strip().lower()))
    except Exception:
        pass
    try:
        for item in db.list_amendment_updates(limit=200):
            title = item.get("title", "")
            if title:
                digest.add(re.sub(r"\s+", " ", title.strip().lower()))
    except Exception:
        pass
    return digest


def _extract_grounding(result: Any) -> tuple[list[str], list[dict[str, str]]]:
    """Extract search queries and source URLs from Gemini grounding metadata."""
    queries: list[str] = []
    sources: list[dict[str, str]] = []
    if isinstance(result, dict):
        grounding = result.get("_grounding")
        if isinstance(grounding, dict):
            queries = list(grounding.get("web_search_queries") or [])
            sources = list(grounding.get("sources") or [])
    return queries, sources


def run_update_tracker() -> dict[str, Any]:
    """Run the full discovery-verification-reason pipeline.

    Returns a summary dict. Never raises.
    """
    if not gemini_available():
        return {
            "status": "gemini_unavailable",
            "run_id": None,
            "started_at": datetime.now().isoformat(),
            "finished_at": datetime.now().isoformat(),
            "discovered": 0,
            "verified": 0,
            "contradicted": 0,
            "error": "Gemini API keys not available",
            "search_queries_count": 0,
        }

    started_at = datetime.now().isoformat()
    run_id = f"RUN_{uuid.uuid4().hex[:12]}"
    model_used = get_gemini_health().get("model")
    all_search_queries: list[str] = []
    discovered = 0
    verified_count = 0
    contradicted_count = 0
    error_msg: str | None = None

    try:
        known = _build_known_digest()

        # --- Step 1: Discovery ---
        discovery_prompt = (
            "You are an IFSCA/SEBI exam-prep regulatory update scanner.\n\n"
            "Use Google Search to find the LATEST regulatory updates across these angles:\n"
            "- IFSCA circulars and amendments (2025-2026)\n"
            "- GIFT IFSC notifications and framework changes\n"
            "- IFSCA Act changes and new regulations\n"
            "- SEBI Grade A exam pattern or syllabus changes\n"
            "- New IFSCA consultation papers and results\n\n"
            "Return ONLY items that are genuinely NEW regulatory developments.\n"
            "Each item must have: title, summary, category (AMENDMENT|CIRCULAR|ACT_CHANGE|REGULATION|CONSULTATION|RESULT),\n"
            "exam (IFSCA|SEBI), topic_id (use valid IFSCA topic ids like PH2_FM_REGS, PH2_BANKING etc.),\n"
            "update_date (YYYY-MM-DD or empty), old_value, new_value, candidate_sources (URLs).\n\n"
            "Already-known items (skip these):\n"
            + "\n".join(f"- {t}" for t in sorted(known)[:30])
            + "\n\nReturn JSON with an 'updates' array."
        )

        discovery_result = call_json(
            discovery_prompt,
            schema=DISCOVERY_SCHEMA,
            temperature=0.1,
            operation="tracker_discovery",
            profile="accuracy",
            google_search=True,
        )

        disc_queries, _ = _extract_grounding(discovery_result)
        all_search_queries.extend(disc_queries)

        candidates: list[dict[str, Any]] = []
        if isinstance(discovery_result, dict):
            raw_updates = discovery_result.get("updates") or []
            if isinstance(raw_updates, list):
                candidates = raw_updates[:MAX_CANDIDATES_PER_RUN]

        discovered = len(candidates)

        # --- Step 2 & 3: Corroboration + Reason per candidate ---
        for candidate in candidates:
            try:
                title = candidate.get("title", "")
                if not title:
                    continue

                # Check against known digest
                norm_title = re.sub(r"\s+", " ", title.strip().lower())
                if norm_title in known:
                    continue

                # Step 2: Independent corroboration
                verify_prompt = (
                    f"Verify this regulatory update claim using Google Search:\n\n"
                    f"Title: {title}\n"
                    f"Summary: {candidate.get('summary', '')}\n"
                    f"Category: {candidate.get('category', '')}\n"
                    f"Exam: {candidate.get('exam', 'IFSCA')}\n\n"
                    f"Search for official sources confirming this update. "
                    f"Return verdict as VERIFIED only if you find corroborating official evidence. "
                    f"Return CONTRADICTED if the claim is wrong or unverifiable.\n"
                    f"Provide a detailed verification_rationale citing what you found."
                )

                verdict_result = call_json(
                    verify_prompt,
                    schema=VERDICT_SCHEMA,
                    temperature=0.05,
                    operation="tracker_verify",
                    profile="accuracy",
                    google_search=True,
                )

                v_queries, v_sources = _extract_grounding(verdict_result)
                all_search_queries.extend(v_queries)

                verdict = "CONTRADICTED"
                rationale = "Verification call returned no result"
                if isinstance(verdict_result, dict):
                    verdict = verdict_result.get("verdict", "CONTRADICTED")
                    rationale = verdict_result.get("rationale") or verdict_result.get("verification_rationale", "")

                if verdict not in ("VERIFIED", "CONTRADICTED"):
                    verdict = "CONTRADICTED"

                # Collect source URLs
                candidate_sources = candidate.get("candidate_sources") or []
                source_urls = [s.get("uri") for s in v_sources if s.get("uri")]
                if not source_urls:
                    source_urls = [s for s in candidate_sources if isinstance(s, str)]

                # Build update record
                update_record = {
                    "title": title,
                    "summary": candidate.get("summary"),
                    "category": candidate.get("category", "AMENDMENT"),
                    "exam": candidate.get("exam", "IFSCA"),
                    "topic_id": _valid_topic_id(candidate.get("topic_id")),
                    "update_date": candidate.get("update_date") or None,
                    "old_value": candidate.get("old_value"),
                    "new_value": candidate.get("new_value"),
                    "verification_status": verdict,
                    "verification_rationale": rationale,
                    "source_urls": source_urls,
                    "search_queries": v_queries or disc_queries,
                    "model_used": model_used,
                    "status": "ACTIVE",
                }

                # Step 3: For VERIFIED, get change_reason
                if verdict == "VERIFIED":
                    reason_prompt = (
                        f"Research WHY this regulatory change was made using Google Search:\n\n"
                        f"Title: {title}\n"
                        f"Summary: {candidate.get('summary', '')}\n\n"
                        f"Return a concise change_reason explaining the motivation or trigger for this change."
                    )
                    reason_result = call_json(
                        reason_prompt,
                        schema=REASON_SCHEMA,
                        temperature=0.1,
                        operation="tracker_reason",
                        profile="accuracy",
                        google_search=True,
                    )
                    r_queries, _ = _extract_grounding(reason_result)
                    all_search_queries.extend(r_queries)
                    if isinstance(reason_result, dict):
                        update_record["change_reason"] = reason_result.get("change_reason")

                # Persist
                db.save_amendment_update(update_record)

                if verdict == "VERIFIED":
                    verified_count += 1
                    # Flow into amendments table for question generation
                    try:
                        amendment_id = f"AMN_TRACKER_{uuid.uuid4().hex[:10]}"
                        db.record_amendment({
                            "amendment_id": amendment_id,
                            "topic": update_record.get("topic_id") or "PH2_CURRENT_AFFAIRS",
                            "rule_name": title,
                            "effective_date": update_record.get("update_date"),
                            "old_value": update_record.get("old_value"),
                            "new_value": update_record.get("new_value"),
                            "source_url": source_urls[0] if source_urls else "tracker_discovery",
                            "verify_status": "TRACKER_VERIFIED",
                            "priority": "HIGH" if update_record.get("category") in ("AMENDMENT", "ACT_CHANGE") else "NORMAL",
                            "questions_needed": 3,
                        })
                        # Enqueue question generation
                        try:
                            import job_queue
                            job_queue.enqueue_job(
                                job_type="amendment_questions",
                                target_resource=amendment_id,
                                payload={
                                    "topic_id": update_record.get("topic_id") or "PH2_CURRENT_AFFAIRS",
                                    "count": 3,
                                },
                            )
                        except Exception as jq_exc:
                            logger.warning("Failed to enqueue question generation: %s", jq_exc)
                    except Exception as am_exc:
                        logger.warning("Failed to record amendment from tracker: %s", am_exc)
                else:
                    contradicted_count += 1

            except Exception as cand_exc:
                logger.warning("Error processing candidate '%s': %s", candidate.get("title", "?"), cand_exc)
                continue

    except Exception as exc:
        error_msg = str(exc)
        logger.error("Update tracker run failed: %s", exc)

    # Record the run
    try:
        db.record_tracker_run({
            "run_id": run_id,
            "started_at": started_at,
            "finished_at": datetime.now().isoformat(),
            "model_used": model_used,
            "searches": list(set(all_search_queries)),
            "discovered": discovered,
            "verified": verified_count,
            "contradicted": contradicted_count,
            "error": error_msg,
        })
    except Exception as rec_exc:
        logger.error("Failed to record tracker run: %s", rec_exc)

    return {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(),
        "discovered": discovered,
        "verified": verified_count,
        "contradicted": contradicted_count,
        "error": error_msg,
        "search_queries_count": len(all_search_queries),
    }


def enrich_past_amendment_reasons(limit: int = 8) -> dict[str, Any]:
    """For known amendments lacking an amendment_updates row, research reason-for-change.

    One grounded call per item. Saves rows with category='ACT_CHANGE'.
    Only marks VERIFIED when sources returned, else NEW. Caps calls; never raises.
    """
    if not gemini_available():
        return {
            "status": "gemini_unavailable",
            "enriched": 0,
            "skipped": 0,
            "errors": 0,
        }

    enriched = 0
    skipped = 0
    errors = 0

    try:
        # Collect known amendment titles that already have update rows
        existing_titles: set[str] = set()
        try:
            for upd in db.list_amendment_updates(limit=500):
                t = upd.get("title", "")
                if t:
                    existing_titles.add(re.sub(r"\s+", " ", t.strip().lower()))
        except Exception:
            pass

        # Candidates from amendments table
        candidates: list[dict[str, Any]] = []
        try:
            for am in db.list_amendments(limit=40):
                title = am.get("title") or am.get("rule_name") or ""
                if not title:
                    continue
                norm = re.sub(r"\s+", " ", title.strip().lower())
                if norm in existing_titles:
                    continue
                candidates.append(am)
        except Exception:
            pass

        # Also check knowledge pack amendment facts
        try:
            for fact in knowledge.load_all_facts():
                if fact.get("domain") != "amendments":
                    continue
                title = fact.get("statement", "")[:120]
                if not title:
                    continue
                norm = re.sub(r"\s+", " ", title.strip().lower())
                if norm in existing_titles:
                    continue
                # Avoid duplicates from amendments table
                if any(re.sub(r"\s+", " ", (c.get("title") or c.get("rule_name") or "").strip().lower()) == norm for c in candidates):
                    continue
                candidates.append({
                    "title": title,
                    "rule_name": title,
                    "topic": (fact.get("topic_ids") or ["PH2_CURRENT_AFFAIRS"])[0],
                    "effective_date": fact.get("effective_date"),
                })
        except Exception:
            pass

        for item in candidates[:limit]:
            try:
                title = item.get("title") or item.get("rule_name") or ""
                if not title:
                    skipped += 1
                    continue

                prompt = (
                    f"Research WHY this IFSCA/SEBI regulatory change was made using Google Search:\n\n"
                    f"Title: {title}\n"
                    f"Effective date: {item.get('effective_date', 'unknown')}\n\n"
                    f"Return a concise change_reason explaining the motivation or trigger for this change."
                )

                result = call_json(
                    prompt,
                    schema=REASON_SCHEMA,
                    temperature=0.1,
                    operation="enrich_reason",
                    profile="accuracy",
                    google_search=True,
                )

                _, sources = _extract_grounding(result)
                source_urls = [s.get("uri") for s in sources if s.get("uri")]

                status = "VERIFIED" if source_urls else "NEW"
                change_reason = ""
                if isinstance(result, dict):
                    change_reason = result.get("change_reason", "")

                db.save_amendment_update({
                    "title": title,
                    "summary": change_reason[:300] if change_reason else None,
                    "category": "ACT_CHANGE",
                    "exam": "IFSCA",
                    "topic_id": _valid_topic_id(item.get("topic") or item.get("topic_id")),
                    "update_date": item.get("effective_date"),
                    "change_reason": change_reason,
                    "verification_status": status,
                    "source_urls": source_urls,
                    "model_used": get_gemini_health().get("model"),
                    "status": "ACTIVE",
                })
                enriched += 1

            except Exception as item_exc:
                logger.warning("enrich_past_amendment_reasons item error: %s", item_exc)
                errors += 1
                continue

    except Exception as exc:
        logger.error("enrich_past_amendment_reasons failed: %s", exc)
        errors += 1

    return {
        "enriched": enriched,
        "skipped": skipped,
        "errors": errors,
    }
