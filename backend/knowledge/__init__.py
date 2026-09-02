"""Committed knowledge pack for the IFSCA/SEBI exam engine.

Runtime bootstrap loads ONLY from this package (JSON below) into SQLite.
Zero md/pdf reads, zero sourcing, zero chunking at runtime: the corpus was
compiled once into these files, and provenance-checked against source files
before being frozen (plan v6, Contract §B).

Fact entry schema (facts/*.json):
    fact_id, domain, module, topic_ids[], subject_ids[], statement, detail,
    numbers{}, effective_date, authority, yield, source_doc, source_ref, tags[]
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PACK_DIR = Path(__file__).resolve().parent
FACTS_DIR = PACK_DIR / "facts"

SCHEMA_VERSION = 1

AUTHORITIES = {
    "OFFICIAL_REGULATORY",
    "ICSI_STUDY",
    "IFSCA_PUBLICATION",
    "CONSULTING",
    "CURRENT_AFFAIRS",
    "COACHING",
}
YIELDS = {"HIGH", "MED", "LOW"}

# Canonical taxonomy — single source of truth. database.py imports these.
TOPIC_IDS = [
    # Phase II regulatory topics (existing 18)
    "PH2_IFSCA_ACT",
    "PH2_GIFT_IFSC",
    "PH2_FM_REGS",
    "PH2_BANKING",
    "PH2_CAPITAL",
    "PH2_CMI",
    "PH2_LISTING",
    "PH2_PAYMENT",
    "PH2_TECHFIN_TAS",
    "PH2_BULLION",
    "PH2_INSURANCE",
    "PH2_AIRCRAFT_SHIP_LEASING",
    "PH2_AML_KYC",
    "PH2_COMMODITY_TRADE",
    "PH2_TAX",
    "PH2_CURRENT_AFFAIRS",
    "PH2_MANAGEMENT_ORG",
    "PH2_ESSAY",
    # Additions (plan v6, sub-phase 1.2)
    "PH2_PENSION",
    "PH2_BUDGET_ECON_SURVEY",
]

SUBJECT_IDS = [
    "SUBJ_QUANT",
    "SUBJ_REASONING",
    "SUBJ_ENGLISH",
    "SUBJ_GA",
    "SUBJ_FINANCE",
    "SUBJ_MANAGEMENT",
    "SUBJ_COMMERCE_ACCOUNTS",
    "SUBJ_COSTING",
    "SUBJ_ECONOMICS",
    "SUBJ_COMPANIES_ACT",
    "SUBJ_ESSAY",
    "SUBJ_PRECIS",
    "SUBJ_RC",
]


def _load(name: str) -> Any:
    return json.loads((PACK_DIR / name).read_text(encoding="utf-8"))


def load_all_facts() -> list[dict[str, Any]]:
    """All fact entries across facts/*.json, in filename order."""
    facts: list[dict[str, Any]] = []
    if not FACTS_DIR.exists():
        return facts
    for path in sorted(FACTS_DIR.glob("facts_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        file_domain = payload.get("domain") or path.stem.removeprefix("facts_")
        for fact in payload.get("facts", []):
            fact.setdefault("domain", file_domain)
            facts.append(fact)
    return facts


def load_objective() -> list[dict[str, Any]]:
    return _load("pyq_objective.json").get("questions", [])


def load_descriptive() -> list[dict[str, Any]]:
    return _load("descriptive_items.json").get("items", [])


def load_papers() -> list[dict[str, Any]]:
    return _load("pyq_objective.json").get("papers", [])


def load_act_text() -> dict[str, Any]:
    return _load("act_text.json")


def load_syllabus() -> dict[str, Any]:
    return _load("syllabus.json")


def load_exam_patterns() -> dict[str, Any]:
    return _load("exam_patterns.json")


def load_sebi_pattern() -> dict[str, Any]:
    return _load("facts_sebi_pattern.json")


def load_manifest() -> dict[str, Any]:
    return _load("knowledge_meta.json")
