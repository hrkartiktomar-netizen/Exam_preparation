"""Central Gemini runtime for the adaptive IFSCA prep engine.

Gemini is the primary intelligence layer. Local deterministic logic remains
available as failure handling so the app stays usable if quota/network fails.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from google import genai
from google.genai import errors, types


BACKEND_DIR = Path(__file__).resolve().parent
ENV_PATH = BACKEND_DIR / ".env"
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
DEFAULT_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "high").strip().upper() or "HIGH"
PROMPT_CONTRACT_VERSION = "gemini_exam_contract_v2"


IFSCA_EXAM_CONTRACT = """
You are the central intelligence layer of a single-user IFSCA Grade A exam preparation app.

Non-negotiable operating rules:
- Treat Gemini as an exam-prep engine, not a generic chatbot.
- Use retrieved source context for regulatory facts. If the source does not support a claim, mark it as uncertain or omit it.
- Prefer IFSCA, IFSC, GIFT IFSC, ICSI, official handout, bulletin, annual-report, regulation, circular, and memory-paper evidence.
- Distinguish official regulatory material from coaching/memory material.
- Never invent section numbers, dates, thresholds, marks, eligibility conditions, or amendment effects.
- Keep outputs operational: what to study, what to test, what to revise, and why it affects score.
- Use exact topic ids where requested.

Exam anchors from the local corpus:
- Phase I Paper 1: 100 questions, 100 marks, 60 minutes, 30 percent cut-off.
- Phase I Paper 2 General Stream: 50 questions, 100 marks, 60 minutes, 40 percent cut-off.
- Phase II Paper 1: English descriptive, 100 marks, 60 minutes; Precis 35, Essay 30, Comprehension 35.
- Phase II Paper 2 General Stream: 50 objective questions, 100 marks, 60 minutes, 40 percent cut-off.
- Phase II aggregate uses Paper 1 and Paper 2 with 1/3 and 2/3 weightage.
- Objective wrong answers carry one-fourth negative marking where applicable.
"""


TOPIC_ID_GUIDE = """
Allowed topic ids:
PH2_IFSCA_ACT, PH2_GIFT_IFSC, PH2_FM_REGS, PH2_BANKING, PH2_CAPITAL, PH2_CMI,
PH2_LISTING, PH2_PAYMENT, PH2_TECHFIN_TAS, PH2_BULLION, PH2_INSURANCE,
PH2_AIRCRAFT_SHIP_LEASING, PH2_AML_KYC, PH2_COMMODITY_TRADE, PH2_TAX,
PH2_CURRENT_AFFAIRS, PH2_MANAGEMENT_ORG, PH2_ESSAY.
"""


USE_CASE_CATALOG: list[dict[str, str]] = [
    {
        "id": "startup_probe",
        "endpoint": "app lifespan / /health",
        "purpose": "Verify that Gemini keys, model, JSON mode, and rotation are usable before the app is trusted.",
    },
    {
        "id": "question_generation",
        "endpoint": "POST /api/questions/generate-from-source, POST /api/generate-smart-mock, POST /api/penalty-drill",
        "purpose": "Generate source-cited MCQs using exam difficulty and amendment sensitivity rules.",
    },
    {
        "id": "essay_grading",
        "endpoint": "POST /api/grade-essay",
        "purpose": "Grade Phase II descriptive writing with rubric scores, missing-evidence feedback, and source suggestions.",
    },
    {
        "id": "focus_plan",
        "endpoint": "GET /api/dashboard",
        "purpose": "Convert performance, weak topics, amendments, and source health into next-session actions.",
    },
    {
        "id": "amendment_watchlist",
        "endpoint": "app lifespan, GET /api/amendments/intelligence, GET /api/amendments/startup-scan",
        "purpose": "Run Gemini amendment radar over IFSCA/ICSI/legal chunks and identify updates worth drilling.",
    },
    {
        "id": "daily_law_revision",
        "endpoint": "GET /api/law/daily-revision",
        "purpose": "Turn the IndiaCode IFSCA Act text into a daily revision slice with traps, self-test prompts, and source lines.",
    },
    {
        "id": "study_session",
        "endpoint": "POST /api/ai/study-session",
        "purpose": "Create a timed adaptive study session with mock, drill, essay, and amendment tasks.",
    },
    {
        "id": "topic_source_brief",
        "endpoint": "GET /api/ai/topic-brief",
        "purpose": "Summarize high-yield source facts and likely question angles for one topic.",
    },
    {
        "id": "pyq_calibration",
        "endpoint": "GET /api/ai/pyq-calibration",
        "purpose": "Extract question-style patterns from local memory/PYQ material and convert them into generation rules.",
    },
    {
        "id": "product_gap_analysis",
        "endpoint": "GET /api/ai/product-gap-analysis",
        "purpose": "Audit the app against the digest and plan to find missing software capabilities.",
    },
    {
        "id": "mock_blueprint",
        "endpoint": "GET /api/ai/mock-blueprint",
        "purpose": "Explain and refine the next mock allocation before questions are generated.",
    },
]


def load_env_file(path: Path = ENV_PATH) -> None:
    """Load simple KEY=VALUE pairs without logging secret values."""

    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def gemini_keys_from_env() -> list[str]:
    load_env_file()
    keys = [os.getenv("GEMINI_KEY")]
    keys.extend(os.getenv(f"GEMINI_KEY_{index}") for index in range(1, 51))
    deduped: list[str] = []
    seen: set[str] = set()
    for key in keys:
        if key and key not in seen:
            deduped.append(key)
            seen.add(key)
    return deduped


GEMINI_STATE: dict[str, Any] = {
    "keys": gemini_keys_from_env(),
    "rate_limited_until": {},
    "calls": {},
    "errors_seen": {},
    "initialized_at": None,
    "startup_probe_ok": False,
    "last_error": None,
    "last_operation": None,
    "last_model_response_at": None,
}


def refresh_gemini_keys() -> None:
    new_keys = gemini_keys_from_env()
    if new_keys != GEMINI_STATE["keys"]:
        GEMINI_STATE["keys"] = new_keys
        GEMINI_STATE["rate_limited_until"] = {}
        GEMINI_STATE["calls"] = {}
        GEMINI_STATE["errors_seen"] = {}


def available_gemini_keys() -> list[str]:
    refresh_gemini_keys()
    now = time.time()
    keys = GEMINI_STATE["keys"]
    available = [key for key in keys if GEMINI_STATE["rate_limited_until"].get(key, 0) <= now]
    # Do NOT fall back to rate-limited keys: returning them would bypass the
    # per-key cooldown and hammer the API with calls that will 429 again.
    # Callers treat an empty list as "no keys available" and use local fallbacks.
    return available


def next_gemini_key() -> str | None:
    keys = available_gemini_keys()
    if not keys:
        return None
    key = min(keys, key=lambda value: GEMINI_STATE["calls"].get(value, 0))
    GEMINI_STATE["calls"][key] = GEMINI_STATE["calls"].get(key, 0) + 1
    return key


def mark_gemini_success(operation: str) -> None:
    GEMINI_STATE["last_operation"] = operation
    GEMINI_STATE["last_error"] = None
    GEMINI_STATE["last_model_response_at"] = datetime.now().isoformat()


def mark_gemini_error(key: str | None, code: int | None = None, message: str | None = None, operation: str | None = None) -> None:
    if key:
        GEMINI_STATE["errors_seen"][key] = GEMINI_STATE["errors_seen"].get(key, 0) + 1
        if code == 429:
            GEMINI_STATE["rate_limited_until"][key] = time.time() + 60
        elif code in {401, 403}:
            GEMINI_STATE["rate_limited_until"][key] = time.time() + 24 * 60 * 60
    GEMINI_STATE["last_operation"] = operation or GEMINI_STATE["last_operation"]
    GEMINI_STATE["last_error"] = message or (f"Gemini API error {code}" if code else "Gemini call failed")


def gemini_available() -> bool:
    refresh_gemini_keys()
    return bool(GEMINI_STATE["keys"])


def get_gemini_health() -> dict[str, Any]:
    refresh_gemini_keys()
    now = time.time()
    available = [key for key in GEMINI_STATE["keys"] if GEMINI_STATE["rate_limited_until"].get(key, 0) <= now]
    return {
        "central_ai": "gemini",
        "initialized": bool(GEMINI_STATE["initialized_at"]),
        "initialized_at": GEMINI_STATE["initialized_at"],
        "startup_probe_ok": GEMINI_STATE["startup_probe_ok"],
        "total_keys": len(GEMINI_STATE["keys"]),
        "available_keys": len(available),
        "model": DEFAULT_GEMINI_MODEL,
        "thinking_level": DEFAULT_THINKING_LEVEL.lower(),
        "fallback_mode": not bool(available),
        "calls_total": sum(GEMINI_STATE["calls"].values()),
        "errors_total": sum(GEMINI_STATE["errors_seen"].values()),
        "last_operation": GEMINI_STATE["last_operation"],
        "last_model_response_at": GEMINI_STATE["last_model_response_at"],
        "last_error": GEMINI_STATE["last_error"],
    }


def generation_config(schema: Any | None = None, temperature: float = 0.2) -> types.GenerateContentConfig:
    thinking_level = getattr(types.ThinkingLevel, DEFAULT_THINKING_LEVEL, types.ThinkingLevel.HIGH)
    config_kwargs: dict[str, Any] = {
        "response_mime_type": "application/json",
        "temperature": temperature,
        "thinking_config": types.ThinkingConfig(thinking_level=thinking_level),
    }
    if schema is not None:
        config_kwargs["response_json_schema"] = schema
    return types.GenerateContentConfig(**config_kwargs)


def _client_for_next_key() -> tuple[genai.Client | None, str | None]:
    key = next_gemini_key()
    if not key:
        return None, None
    return genai.Client(api_key=key), key


def _safe_json_loads(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    return json.loads(cleaned)


def call_json(prompt: str, schema: Any | None = None, temperature: float = 0.2, operation: str = "generic") -> Any | None:
    refresh_gemini_keys()
    if not GEMINI_STATE["keys"]:
        mark_gemini_error(None, message="No Gemini API keys loaded", operation=operation)
        return None
    max_attempts = max(1, min(len(GEMINI_STATE["keys"]), 5))
    for _ in range(max_attempts):
        client, key = _client_for_next_key()
        if client is None:
            mark_gemini_error(None, message="No Gemini API keys currently available", operation=operation)
            return None
        try:
            response = client.models.generate_content(
                model=DEFAULT_GEMINI_MODEL,
                contents=prompt,
                config=generation_config(schema=schema, temperature=temperature),
            )
            mark_gemini_success(operation)
            return _safe_json_loads(response.text or "{}")
        except errors.APIError as exc:
            code = getattr(exc, "code", None)
            mark_gemini_error(key, code, str(exc), operation)
            if code in {401, 403, 429, 500, 502, 503, 504}:
                continue
            return None
        except Exception as exc:
            mark_gemini_error(key, None, str(exc), operation)
            return None
    return None


def _contract_prompt(use_case: str, task: str, body: str) -> str:
    return f"""
{IFSCA_EXAM_CONTRACT}

Use case: {use_case}
Prompt contract version: {PROMPT_CONTRACT_VERSION}

Task:
{task}

{body}
"""


def _source_context(chunks: list[dict[str, Any]], max_chunks: int = 8, chars_per_chunk: int = 1200) -> str:
    lines = []
    for idx, chunk in enumerate(chunks[:max_chunks], start=1):
        excerpt = re.sub(r"\s+", " ", str(chunk.get("excerpt", ""))).strip()[:chars_per_chunk]
        lines.append(
            "\n".join(
                [
                    f"[{idx}] chunk_id={chunk.get('chunk_id')} document_id={chunk.get('document_id')}",
                    f"title={chunk.get('title')} category={chunk.get('category')} page={chunk.get('page_start')}",
                    f"text={excerpt}",
                ]
            )
        )
    return "\n\n".join(lines)


def initialize_gemini_runtime(run_probe: bool = True) -> dict[str, Any]:
    """Initialize Gemini at app startup and optionally run a tiny probe."""

    refresh_gemini_keys()
    GEMINI_STATE["initialized_at"] = datetime.now().isoformat()
    GEMINI_STATE["startup_probe_ok"] = False
    if not GEMINI_STATE["keys"]:
        GEMINI_STATE["last_error"] = "No Gemini API keys loaded"
        return get_gemini_health()
    if run_probe:
        schema = {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "purpose": {"type": "string"},
            },
            "required": ["status", "purpose"],
        }
        result = call_json(
            _contract_prompt(
                "startup_probe",
                "Confirm readiness for structured JSON responses in the IFSCA exam preparation application.",
                "Return a compact JSON object with status=ready or status=ok and a purpose string.",
            ),
            schema=schema,
            temperature=0.0,
            operation="startup_probe",
        )
        GEMINI_STATE["startup_probe_ok"] = isinstance(result, dict) and str(result.get("status", "")).lower() in {"ok", "ready", "healthy"}
        if not GEMINI_STATE["startup_probe_ok"] and GEMINI_STATE["last_error"] is None:
            GEMINI_STATE["last_error"] = "Startup probe returned an unexpected response"
    return get_gemini_health()


QUESTION_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "question_text": {"type": "string"},
            "option_a": {"type": "string"},
            "option_b": {"type": "string"},
            "option_c": {"type": "string"},
            "option_d": {"type": "string"},
            "correct_answer": {"type": "string"},
            "explanation": {"type": "string"},
            "source_index": {"type": "integer"},
            "tested_fact": {"type": "string"},
            "trap_logic": {"type": "string"},
            "exam_rationale": {"type": "string"},
        },
        "required": ["question_text", "option_a", "option_b", "option_c", "option_d", "correct_answer", "explanation", "source_index"],
    },
}


def generate_questions_with_gemini(
    topic: str,
    count: int,
    difficulty: str,
    chunks: list[dict[str, Any]],
    question_type: str = "source_grounded",
    is_amendment_based: bool = False,
    source_policy: str = "general",
) -> list[dict[str, Any]]:
    if not gemini_available() or not chunks or count <= 0:
        return []
    context = _source_context(chunks, max_chunks=8, chars_per_chunk=1400)
    prompt = _contract_prompt(
        "question_generation",
        f"Generate {count} source-grounded IFSCA Grade A MCQs for topic {topic}.",
        f"""
{TOPIC_ID_GUIDE}

Topic id: {topic}
Difficulty: {difficulty}
Question type: {question_type}
Amendment based: {is_amendment_based}
Source policy: {source_policy}

Material sourcing context:
- Easy/weak questions use ONLY regulatory_core and official study materials (laws, regulations, ICSI)
- Medium questions may include amendment_tracking and recent regulatory updates
- Hard/advanced questions can use consulting reports, case studies, and scenario-based materials
- All questions MUST be grounded in the provided source context below.

Question design rules:
- Use **ONLY** the retrieved source context below. Do NOT add external knowledge.
- For smart_mock/exam_material generation, every question must be grounded in PYQ, phase paper, information handout, syllabus, ICSI/study material, or official IFSCA material supplied in the retrieved context.
- Use PYQ/memory-paper chunks for exam style, trap shape, and intensity; use official/ICSI/study-material chunks for regulatory facts.
- Do not copy a full PYQ stem verbatim unless the supplied context itself is a question paper and the question is clearly useful as prior-year practice.
- Do not ask "which topic is tested" or source-title trivia.
- For easy questions, test exact definitions, eligibility, authority, timelines, or permitted/prohibited actions.
- For medium questions, test comparison, exception, compliance consequence, or correct regulatory sequence.
- For hard questions, test scenario application, amendment effect, cross-document distinction, or trap-prone wording.
- Keep each stem self-contained and exam-like.
- Exactly four options: A, B, C, D. correct_answer must be one of A/B/C/D.
- Every distractor must be plausible to a serious candidate but contradicted or unsupported by the cited source.
- explanation must cite the source index and explain the trap.
- source_index must match the single strongest supporting context block (1-based index from list below).
- tested_fact should be the exact regulatory fact being tested.
- trap_logic should state why the wrong options are tempting.

IMPORTANT: Each question MUST reference one chunk from the list below via source_index.
Chunks are numbered [1], [2], [3], etc. in the source context.
If a question cannot be grounded in the provided sources, skip it.

Retrieved source context:
{context}

Return JSON array only.
""",
    )
    data = call_json(prompt, schema=QUESTION_SCHEMA, temperature=0.25, operation=f"question_generation:{topic}")
    if not isinstance(data, list):
        return []
    questions: list[dict[str, Any]] = []
    for item in data[:count]:
        try:
            source_index = int(item.get("source_index", 1)) - 1
            chunk = chunks[source_index] if 0 <= source_index < len(chunks) else chunks[0]
            correct = str(item["correct_answer"]).strip().upper()[:1]
            if correct not in {"A", "B", "C", "D"}:
                continue
            questions.append(
                {
                    "question_id": f"Q_AI_{uuid.uuid4().hex[:12]}",
                    "topic": topic,
                    "question_text": item["question_text"],
                    "options": [
                        {"label": "A", "text": item["option_a"]},
                        {"label": "B", "text": item["option_b"]},
                        {"label": "C", "text": item["option_c"]},
                        {"label": "D", "text": item["option_d"]},
                    ],
                    "correct_option": correct,
                    "explanation": item["explanation"],
                    "source": chunk["title"],
                    "source_document_id": chunk["document_id"],
                    "source_chunk_id": chunk["chunk_id"],
                    "page_start": chunk.get("page_start"),
                    "page_end": chunk.get("page_end"),
                    "citation_note": item.get("exam_rationale") or "Gemini-generated from retrieved source context",
                    "difficulty": difficulty,
                    "question_type": question_type,
                    "is_amendment_based": is_amendment_based,
                    "recency_score": 90 if is_amendment_based else 60,
                    "source_policy": source_policy,
                    "tested_fact": item.get("tested_fact"),
                    "trap_logic": item.get("trap_logic"),
                }
            )
        except Exception:
            continue
    return questions


def local_essay_grade(essay_text: str, source_count: int = 0) -> dict[str, Any]:
    words = essay_text.split()
    word_count = len(words)
    lower = essay_text.lower()
    paragraphs = [part for part in essay_text.split("\n") if part.strip()]
    regulatory_terms = [
        "ifsca",
        "gift",
        "ifsc",
        "regulation",
        "compliance",
        "fund",
        "banking",
        "capital market",
        "aml",
        "kyc",
        "techfin",
        "bullion",
        "listing",
        "insurance",
    ]
    term_hits = sum(1 for term in regulatory_terms if term in lower)
    numeric_evidence = len(set(re.findall(r"\b(?:20\d{2}|\d+(?:\.\d+)?%|\d+\s*(?:bn|million|crore|lakh))\b", lower)))

    content_score = min(25, 10 + min(10, term_hits) + min(5, word_count // 180))
    structure_score = min(25, 8 + min(8, len(paragraphs) * 2) + (5 if any(marker in lower for marker in ["first", "second", "therefore", "conclusion"]) else 0))
    regulatory_score = min(25, 8 + min(12, term_hits) + min(5, source_count))
    evidence_score = min(25, 7 + min(8, numeric_evidence * 2) + min(5, source_count) + (5 if "2025" in lower or "2026" in lower else 0))
    total = content_score + structure_score + regulatory_score + evidence_score
    return {
        "content_accuracy": {
            "score": content_score,
            "feedback": "Covers relevant IFSCA themes. Improve by tying each claim to a specific regulation, circular, or official data point.",
        },
        "structure_clarity": {
            "score": structure_score,
            "feedback": "Use a clearer intro, 3-4 analytical headings, and a concise conclusion.",
        },
        "regulatory_knowledge": {
            "score": regulatory_score,
            "feedback": "Add exact regulation names, current circulars, and recent amendments.",
        },
        "examples_evidence": {
            "score": evidence_score,
            "feedback": "Use dates, statistics, annual-report data, and concrete amendment examples.",
        },
        "total_score": total,
        "overall_feedback": "Local fallback grading used because Gemini was unavailable for this call.",
        "model_outline": "Intro -> regulatory context -> sector examples -> amendment/current data -> risks and compliance -> conclusion.",
        "ai_model": None,
    }


ESSAY_SCHEMA = {
    "type": "object",
    "properties": {
        "content_accuracy": {"type": "object", "properties": {"score": {"type": "integer"}, "feedback": {"type": "string"}}, "required": ["score", "feedback"]},
        "structure_clarity": {"type": "object", "properties": {"score": {"type": "integer"}, "feedback": {"type": "string"}}, "required": ["score", "feedback"]},
        "regulatory_knowledge": {"type": "object", "properties": {"score": {"type": "integer"}, "feedback": {"type": "string"}}, "required": ["score", "feedback"]},
        "examples_evidence": {"type": "object", "properties": {"score": {"type": "integer"}, "feedback": {"type": "string"}}, "required": ["score", "feedback"]},
        "total_score": {"type": "integer"},
        "overall_feedback": {"type": "string"},
        "model_outline": {"type": "string"},
    },
    "required": ["content_accuracy", "structure_clarity", "regulatory_knowledge", "examples_evidence", "total_score", "overall_feedback", "model_outline"],
}


def grade_essay(essay_text: str, topic: str, source_chunks: list[dict[str, Any]]) -> dict[str, Any]:
    if gemini_available():
        context = _source_context(source_chunks, max_chunks=8, chars_per_chunk=1000)
        prompt = _contract_prompt(
            "essay_grading",
            "Grade an IFSCA Grade A Phase II descriptive essay using the app rubric.",
            f"""
Topic id: {topic}
Essay word count: {len(essay_text.split())}

Essay:
{essay_text}

Retrieved source context for evidence suggestions:
{context}

Rubrics are 0-25 each:
1. Content accuracy: correct facts, relevant arguments, no regulatory mistakes.
2. Structure and clarity: intro, flow, paragraphing, headings, conclusion, coherence.
3. Regulatory knowledge: correct IFSCA/IFSC/GIFT/regulation depth.
4. Examples and evidence: official data, dates, circulars, annual-report facts, amendments, sector examples.

Grading rules:
- Grade strictly. Do not inflate marks for fluent but generic writing.
- Penalize unsupported claims, outdated facts, missing IFSC/IFSCA linkages, and vague evidence.
- Feedback must include exact next edits the candidate should make.
- model_outline must be a concise high-scoring outline the candidate can rewrite from.
- If the prompt is non-regulatory, still reward structure but identify where IFSCA/current evidence can improve the essay if relevant.

Return JSON only.
""",
        )
        result = call_json(prompt, schema=ESSAY_SCHEMA, temperature=0.15, operation="essay_grading")
        if isinstance(result, dict):
            try:
                for key in ("content_accuracy", "structure_clarity", "regulatory_knowledge", "examples_evidence"):
                    result[key]["score"] = max(0, min(25, int(result[key]["score"])))
                result["total_score"] = sum(result[key]["score"] for key in ("content_accuracy", "structure_clarity", "regulatory_knowledge", "examples_evidence"))
                result["ai_model"] = DEFAULT_GEMINI_MODEL
                return result
            except Exception:
                pass
    return local_essay_grade(essay_text, source_count=len(source_chunks))


FOCUS_SCHEMA = {
    "type": "object",
    "properties": {
        "primary_action": {"type": "string"},
        "reason": {"type": "string"},
        "next_90_minutes": {"type": "array", "items": {"type": "string"}},
        "risk_flags": {"type": "array", "items": {"type": "string"}},
        "amendment_focus": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["primary_action", "reason", "next_90_minutes", "risk_flags", "amendment_focus"],
}


def generate_focus_plan(
    dashboard: dict[str, Any],
    weak_topics: list[dict[str, Any]],
    amendments: list[dict[str, Any]],
    force_local: bool = False,
) -> dict[str, Any]:
    local_plan = {
        "primary_action": dashboard.get("next_recommended_action", "Generate a balanced smart mock."),
        "reason": "Local fallback plan based on weak topic and amendment status.",
        "next_90_minutes": [
            "Take a 25-question smart mock.",
            "Review every cited source for wrong answers.",
            "Run one 10-question penalty drill on the weakest topic.",
        ],
        "risk_flags": [f"{item.get('display_name') or item.get('topic')} needs attempts" for item in weak_topics[:3]],
        "amendment_focus": [item.get("title") or item.get("rule_name") for item in amendments[:3]],
        "ai_model": None,
    }
    if force_local or not gemini_available():
        return local_plan
    prompt = _contract_prompt(
        "focus_plan",
        "Create the next-session control-center recommendation.",
        f"""
Dashboard:
{json.dumps(dashboard, ensure_ascii=False)[:5000]}

Weak topics:
{json.dumps(weak_topics, ensure_ascii=False)[:3000]}

Recent amendments:
{json.dumps(amendments, ensure_ascii=False)[:3000]}

Rules:
- Prioritize high-weight weak topics, recent unmastered amendments, and low-attempt topics.
- Use a 90-minute action plan unless the dashboard clearly requires a full mock.
- Include measurable success criteria inside the action text where possible.
- Avoid motivational filler.

Return JSON only. Keep actions short and executable.
""",
    )
    result = call_json(prompt, schema=FOCUS_SCHEMA, temperature=0.2, operation="focus_plan")
    if isinstance(result, dict):
        result["ai_model"] = DEFAULT_GEMINI_MODEL
        return result
    return local_plan


AMENDMENT_WATCHLIST_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "topic": {"type": "string"},
            "priority": {"type": "string"},
            "why_it_matters": {"type": "string"},
            "source_title": {"type": "string"},
            "source_chunk_id": {"type": "string"},
        },
        "required": ["title", "topic", "priority", "why_it_matters", "source_title", "source_chunk_id"],
    },
}


def generate_amendment_watchlist(candidates: list[dict[str, Any]], force_local: bool = False, operation: str = "amendment_watchlist") -> list[dict[str, Any]]:
    if not candidates:
        return []
    local = [
        {
            "title": item.get("title"),
            "topic": ",".join(item.get("topic_tags", [])[:3]) or "PH2_CURRENT_AFFAIRS",
            "priority": "REVIEW",
            "why_it_matters": item.get("excerpt", "")[:260],
            "source_title": item.get("title"),
            "source_chunk_id": item.get("chunk_id"),
            "page_start": item.get("page_start"),
            "ai_model": None,
        }
        for item in candidates[:10]
    ]
    if force_local or not gemini_available():
        return local
    context = _source_context(candidates, max_chunks=15, chars_per_chunk=1000)
    prompt = _contract_prompt(
        "amendment_watchlist",
        "Identify regulatory update items that deserve exam drilling.",
        f"""
{TOPIC_ID_GUIDE}

Return JSON array only. Use the provided chunk_id exactly.
Selection rules:
- Include IFSCA regulations, circulars, guidelines, directions, consultations, FAQs, handbooks, and ICSI capsules only when exam-useful.
- Do not include generic SEBI/RBI/MCA/TRAI/IBBI updates unless the source text explicitly connects them to IFSC, IFSCA, GIFT IFSC, or the IFSCA syllabus.
- Prioritize new obligations, effective dates, eligibility changes, certification requirements, transition/migration rules, fee changes, and amended restrictions.
- Priority should be CRITICAL, HIGH, NORMAL, or LOW.
- why_it_matters must say how to drill it: fact recall, scenario, comparison, or amendment delta.

Candidate chunks:
{context}
""",
    )
    result = call_json(prompt, schema=AMENDMENT_WATCHLIST_SCHEMA, temperature=0.15, operation=operation)
    if isinstance(result, list):
        by_chunk = {item.get("chunk_id"): item for item in candidates}
        enriched = []
        for item in result[:12]:
            chunk = by_chunk.get(item.get("source_chunk_id"), {})
            item["page_start"] = chunk.get("page_start")
            item["ai_model"] = DEFAULT_GEMINI_MODEL
            enriched.append(item)
        return enriched or local
    return local


STUDY_SESSION_SCHEMA = {
    "type": "object",
    "properties": {
        "primary_goal": {"type": "string"},
        "readiness_summary": {"type": "string"},
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "order": {"type": "integer"},
                    "task_type": {"type": "string"},
                    "topic_id": {"type": "string"},
                    "minutes": {"type": "integer"},
                    "action": {"type": "string"},
                    "success_metric": {"type": "string"},
                    "source_query": {"type": "string"},
                },
                "required": ["order", "task_type", "topic_id", "minutes", "action", "success_metric"],
            },
        },
        "drills_to_generate": {"type": "array", "items": {"type": "string"}},
        "essay_prompt": {"type": "string"},
        "amendment_actions": {"type": "array", "items": {"type": "string"}},
        "stop_conditions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["primary_goal", "readiness_summary", "tasks", "drills_to_generate", "essay_prompt", "amendment_actions", "stop_conditions"],
}


def generate_study_session(
    dashboard: dict[str, Any],
    weak_topics: list[dict[str, Any]],
    amendments: list[dict[str, Any]],
    amendment_watchlist: list[dict[str, Any]],
    minutes: int = 90,
    focus: str | None = None,
) -> dict[str, Any]:
    local = {
        "primary_goal": dashboard.get("next_recommended_action", "Generate and review one smart mock."),
        "readiness_summary": "Local fallback session based on weak topics and amendment status.",
        "tasks": [
            {
                "order": 1,
                "task_type": "drill",
                "topic_id": weak_topics[0]["topic"] if weak_topics else "PH2_FM_REGS",
                "minutes": min(30, minutes),
                "action": "Take a targeted penalty drill and review cited sources for every miss.",
                "success_metric": "At least 70 percent accuracy or all errors converted into notes.",
                "source_query": "weak topic source review",
            }
        ],
        "drills_to_generate": [weak_topics[0]["topic"]] if weak_topics else ["PH2_FM_REGS"],
        "essay_prompt": "Write a 250-270 word essay using at least three official IFSCA facts.",
        "amendment_actions": [item.get("title") or item.get("rule_name") for item in amendments[:3]],
        "stop_conditions": ["Stop when review notes exist for every wrong answer."],
        "ai_model": None,
    }
    if not gemini_available():
        return local
    prompt = _contract_prompt(
        "study_session",
        f"Create a {minutes}-minute adaptive study session.",
        f"""
User focus override: {focus or "None"}

Dashboard:
{json.dumps(dashboard, ensure_ascii=False)[:5000]}

Weak topics:
{json.dumps(weak_topics, ensure_ascii=False)[:3500]}

Recent amendments:
{json.dumps(amendments, ensure_ascii=False)[:2500]}

AI amendment watchlist:
{json.dumps(amendment_watchlist, ensure_ascii=False)[:3000]}

Rules:
- Split time into 2-5 concrete tasks.
- Include at least one measurable output: mock score, drill score, rewritten paragraph, amendment cards, or source notes.
- If attempts are low, collect signal before prescribing heavy revision.
- If a weak topic is amendment-sensitive, schedule amendment drill before generic reading.
- Use task_type values from: mock, drill, essay, source_review, amendment_review, wrong_answer_review.

Return JSON only.
""",
    )
    result = call_json(prompt, schema=STUDY_SESSION_SCHEMA, temperature=0.2, operation="study_session")
    if isinstance(result, dict):
        result["ai_model"] = DEFAULT_GEMINI_MODEL
        result["prompt_version"] = PROMPT_CONTRACT_VERSION
        return result
    return local


TOPIC_BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "topic_id": {"type": "string"},
        "executive_summary": {"type": "string"},
        "high_yield_facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string"},
                    "source_index": {"type": "integer"},
                    "exam_angle": {"type": "string"},
                },
                "required": ["fact", "source_index", "exam_angle"],
            },
        },
        "likely_question_angles": {"type": "array", "items": {"type": "string"}},
        "confusion_pairs": {"type": "array", "items": {"type": "string"}},
        "amendment_sensitivity": {"type": "string"},
        "must_read_sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["topic_id", "executive_summary", "high_yield_facts", "likely_question_angles", "confusion_pairs", "amendment_sensitivity", "must_read_sources"],
}


def generate_topic_source_brief(topic_id: str, topic_name: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    local = {
        "topic_id": topic_id,
        "executive_summary": f"Local fallback brief for {topic_name}. Review the cited source chunks first.",
        "high_yield_facts": [
            {"fact": item.get("excerpt", "")[:220], "source_index": index + 1, "exam_angle": "Direct source recall"}
            for index, item in enumerate(chunks[:5])
        ],
        "likely_question_angles": ["Definition", "eligibility", "compliance obligation", "exception", "recent update"],
        "confusion_pairs": [],
        "amendment_sensitivity": "High if recent circulars or regulations are present in the source results.",
        "must_read_sources": [item.get("title") for item in chunks[:5]],
        "ai_model": None,
    }
    if not gemini_available() or not chunks:
        return local
    prompt = _contract_prompt(
        "topic_source_brief",
        f"Create a high-yield source brief for {topic_name}.",
        f"""
{TOPIC_ID_GUIDE}

Topic id: {topic_id}
Topic name: {topic_name}

Retrieved source context:
{_source_context(chunks, max_chunks=10, chars_per_chunk=1200)}

Rules:
- Summarize only source-supported facts.
- Identify facts that can become MCQ traps.
- Identify confusion pairs, such as old/new framework, eligible/ineligible entity, PO/CO, registered/authorised/recognised.
- must_read_sources should name the strongest documents from the provided context.

Return JSON only.
""",
    )
    result = call_json(prompt, schema=TOPIC_BRIEF_SCHEMA, temperature=0.18, operation=f"topic_brief:{topic_id}")
    if isinstance(result, dict):
        result["ai_model"] = DEFAULT_GEMINI_MODEL
        result["prompt_version"] = PROMPT_CONTRACT_VERSION
        return result
    return local


PYQ_CALIBRATION_SCHEMA = {
    "type": "object",
    "properties": {
        "pattern_summary": {"type": "string"},
        "objective_patterns": {"type": "array", "items": {"type": "string"}},
        "descriptive_patterns": {"type": "array", "items": {"type": "string"}},
        "generation_guidelines": {"type": "array", "items": {"type": "string"}},
        "difficulty_rules": {"type": "array", "items": {"type": "string"}},
        "missing_pyq_risks": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["pattern_summary", "objective_patterns", "descriptive_patterns", "generation_guidelines", "difficulty_rules", "missing_pyq_risks"],
}


def generate_pyq_calibration(pyq_chunks: list[dict[str, Any]], digest_profile: dict[str, Any]) -> dict[str, Any]:
    local = {
        "pattern_summary": "Local fallback: use memory/PYQ chunks to calibrate question style, not official law.",
        "objective_patterns": ["Quant/reasoning memory papers show direct timed objective practice patterns."],
        "descriptive_patterns": ["Phase II Paper 1 memory material includes 250-270 word essay prompts and model essays."],
        "generation_guidelines": ["Use official sources for facts and memory papers for style only."],
        "difficulty_rules": ["Hard questions should require scenario application or trap discrimination."],
        "missing_pyq_risks": ["The local PYQ set is incomplete and may be coaching-derived."],
        "ai_model": None,
    }
    if not gemini_available() or not pyq_chunks:
        return local
    prompt = _contract_prompt(
        "pyq_calibration",
        "Convert local memory/PYQ evidence into question-generation calibration rules.",
        f"""
Digest profile:
{json.dumps(digest_profile, ensure_ascii=False)[:3000]}

Memory/PYQ source context:
{_source_context(pyq_chunks, max_chunks=14, chars_per_chunk=1200)}

Rules:
- Treat memory/PYQ/coaching documents as pattern evidence, not as official law.
- Extract style: stem length, option count, essay word range, common traps, time pressure, and difficulty.
- Convert findings into rules that the question_generation prompt should follow.
- Explicitly state missing or weak PYQ coverage.

Return JSON only.
""",
    )
    result = call_json(prompt, schema=PYQ_CALIBRATION_SCHEMA, temperature=0.2, operation="pyq_calibration")
    if isinstance(result, dict):
        result["ai_model"] = DEFAULT_GEMINI_MODEL
        result["prompt_version"] = PROMPT_CONTRACT_VERSION
        return result
    return local


PRODUCT_GAP_SCHEMA = {
    "type": "object",
    "properties": {
        "critical_gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gap": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "evidence_from_digest": {"type": "string"},
                    "current_app_status": {"type": "string"},
                    "recommended_endpoint_or_module": {"type": "string"},
                    "priority": {"type": "string"},
                },
                "required": ["gap", "why_it_matters", "evidence_from_digest", "current_app_status", "recommended_endpoint_or_module", "priority"],
            },
        },
        "prompt_upgrades": {"type": "array", "items": {"type": "string"}},
        "endpoints_to_add_next": {"type": "array", "items": {"type": "string"}},
        "unplanned_opportunities": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["critical_gaps", "prompt_upgrades", "endpoints_to_add_next", "unplanned_opportunities"],
}


def generate_product_gap_analysis(digest_profile: dict[str, Any], app_inventory: dict[str, Any], plan_excerpt: str = "") -> dict[str, Any]:
    local = {
        "critical_gaps": [
            {
                "gap": "Prompt contracts are not visible as product capabilities.",
                "why_it_matters": "Central Gemini behavior must be auditable by endpoint and use case.",
                "evidence_from_digest": "Digest contains official handouts, regulations, amendments, and memory papers that need different handling.",
                "current_app_status": "Core AI endpoints exist but need use-case separation.",
                "recommended_endpoint_or_module": "GET /api/ai/usecases and targeted AI endpoints",
                "priority": "HIGH",
            }
        ],
        "prompt_upgrades": ["Separate official-source prompts from memory/PYQ calibration prompts."],
        "endpoints_to_add_next": ["/api/ai/study-session", "/api/ai/topic-brief", "/api/ai/pyq-calibration"],
        "unplanned_opportunities": ["Use digest composition to warn when a topic lacks official source coverage."],
        "ai_model": None,
    }
    if not gemini_available():
        return local
    prompt = _contract_prompt(
        "product_gap_analysis",
        "Audit the current app against the source digest and maximum plan; identify missing capabilities beyond the original plan.",
        f"""
Digest profile:
{json.dumps(digest_profile, ensure_ascii=False)[:5000]}

Current app inventory:
{json.dumps(app_inventory, ensure_ascii=False)[:5000]}

Relevant plan excerpt:
{plan_excerpt[:5000]}

Rules:
- Be concrete. Name missing modules, endpoints, database state, UI flows, or prompt contracts.
- Prioritize capabilities that improve score: source grounding, adaptive diagnosis, amendment radar, PYQ calibration, descriptive writing, review scheduling.
- Include items not originally planned if the digest reveals the need.
- Do not recommend unrelated enterprise features.

Return JSON only.
""",
    )
    result = call_json(prompt, schema=PRODUCT_GAP_SCHEMA, temperature=0.18, operation="product_gap_analysis")
    if isinstance(result, dict):
        result["ai_model"] = DEFAULT_GEMINI_MODEL
        result["prompt_version"] = PROMPT_CONTRACT_VERSION
        return result
    return local


MOCK_BLUEPRINT_SCHEMA = {
    "type": "object",
    "properties": {
        "blueprint_summary": {"type": "string"},
        "allocation_rationale": {"type": "array", "items": {"type": "string"}},
        "topic_instructions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic_id": {"type": "string"},
                    "question_count": {"type": "integer"},
                    "difficulty": {"type": "string"},
                    "question_styles": {"type": "array", "items": {"type": "string"}},
                    "source_queries": {"type": "array", "items": {"type": "string"}},
                    "risk": {"type": "string"},
                },
                "required": ["topic_id", "question_count", "difficulty", "question_styles", "source_queries", "risk"],
            },
        },
        "review_plan_after_mock": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["blueprint_summary", "allocation_rationale", "topic_instructions", "review_plan_after_mock"],
}


def generate_mock_blueprint(
    mock_config: dict[str, Any],
    weak_topics: list[dict[str, Any]],
    amendment_watchlist: list[dict[str, Any]],
) -> dict[str, Any]:
    local = {
        "blueprint_summary": "Local fallback blueprint generated from weakness allocation.",
        "allocation_rationale": [f"{topic}: {count} questions" for topic, count in mock_config.get("allocation", {}).items()],
        "topic_instructions": [
            {
                "topic_id": topic,
                "question_count": count,
                "difficulty": mock_config.get("difficulty_curve", {}).get(topic, "medium"),
                "question_styles": ["source-grounded MCQ", "scenario trap"],
                "source_queries": [topic],
                "risk": "Review cited sources after the mock.",
            }
            for topic, count in mock_config.get("allocation", {}).items()
        ],
        "review_plan_after_mock": ["Review every wrong answer with its source citation."],
        "ai_model": None,
    }
    if not gemini_available():
        return local
    prompt = _contract_prompt(
        "mock_blueprint",
        "Explain and refine the next smart mock blueprint before generation.",
        f"""
Smart mock config:
{json.dumps(mock_config, ensure_ascii=False)[:5000]}

Weak topics:
{json.dumps(weak_topics, ensure_ascii=False)[:3500]}

Amendment watchlist:
{json.dumps(amendment_watchlist, ensure_ascii=False)[:3000]}

Rules:
- Respect the provided allocation counts.
- For each allocated topic, specify question styles and source queries that should guide generation.
- Highlight amendment-sensitive topics and likely traps.
- Include a post-mock review plan.

Return JSON only.
""",
    )
    result = call_json(prompt, schema=MOCK_BLUEPRINT_SCHEMA, temperature=0.18, operation="mock_blueprint")
    if isinstance(result, dict):
        result["ai_model"] = DEFAULT_GEMINI_MODEL
        result["prompt_version"] = PROMPT_CONTRACT_VERSION
        return result
    return local


LAW_REVISION_SCHEMA = {
    "type": "object",
    "properties": {
        "revision_focus": {"type": "string"},
        "key_points": {"type": "array", "items": {"type": "string"}},
        "mcq_traps": {"type": "array", "items": {"type": "string"}},
        "descriptive_angles": {"type": "array", "items": {"type": "string"}},
        "self_test": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["revision_focus", "key_points", "mcq_traps", "descriptive_angles", "self_test"],
}


def generate_law_revision_plan(revision: dict[str, Any], force_local: bool = False) -> dict[str, Any]:
    local = {
        "revision_focus": revision.get("title") or "IFSCA Act daily revision",
        "key_points": ["Read the cited lines, mark powers/functions, definitions, and exam-trap wording."],
        "mcq_traps": ["Do not confuse IFSC Authority powers with domestic regulator powers unless the Act assigns them."],
        "descriptive_angles": ["Use statutory mandate and unified-regulator framing in essays."],
        "self_test": ["State the core legal effect of today's Act slice without looking at the text."],
        "ai_model": None,
    }
    if force_local or not gemini_available():
        return local
    excerpt = revision.get("daily_text", "")[:6000]
    prompt = _contract_prompt(
        "daily_law_revision",
        "Create a daily IFSCA Act revision plan from the exact IndiaCode Act slice.",
        f"""
Source title: {revision.get("title")}
Line range: {revision.get("line_start")} to {revision.get("line_end")}

Act slice:
{excerpt}

Rules:
- Use only the supplied Act text.
- Focus on exam recall, MCQ trap wording, and Phase II descriptive evidence.
- Do not invent sections or legal effects absent from the slice.
- Keep the plan concise and revision-ready.

Return JSON only.
""",
    )
    result = call_json(prompt, schema=LAW_REVISION_SCHEMA, temperature=0.12, operation="daily_law_revision")
    if isinstance(result, dict):
        result["ai_model"] = DEFAULT_GEMINI_MODEL
        result["prompt_version"] = PROMPT_CONTRACT_VERSION
        return result
    return local


def extract_and_verify_amendment(amendment_text: str, amendment_url: str) -> dict[str, Any]:
    schema = {
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "rule_name": {"type": "string"},
            "old_value": {"type": "string"},
            "new_value": {"type": "string"},
            "effective_date": {"type": "string"},
            "priority": {"type": "string"},
        },
        "required": ["topic", "rule_name", "new_value", "effective_date", "priority"],
    }
    prompt = _contract_prompt(
        "amendment_extraction",
        "Extract one IFSCA amendment/update from user-provided text.",
        f"""
{TOPIC_ID_GUIDE}

Source: {amendment_url}
Text:
{amendment_text[:5000]}

Rules:
- If old value is absent, set old_value to an empty string.
- effective_date must be an explicit date from the text when available; otherwise use the publication date if clear.
- priority must be CRITICAL, HIGH, NORMAL, or LOW.

Return JSON with topic, rule_name, old_value, new_value, effective_date, priority.
""",
    )
    result = call_json(prompt, schema=schema, temperature=0.1, operation="amendment_extraction")
    if isinstance(result, dict):
        result["source_url"] = amendment_url
        result["verify_status"] = "GEMINI_EXTRACTED"
        result["ai_model"] = DEFAULT_GEMINI_MODEL
        return result
    return {
        "topic": "PH2_CURRENT_AFFAIRS",
        "rule_name": "Manual review required",
        "old_value": None,
        "new_value": amendment_text[:500],
        "effective_date": datetime.now().date().isoformat(),
        "priority": "NORMAL",
        "source_url": amendment_url,
        "verify_status": "LOCAL_FALLBACK",
        "ai_model": None,
    }


def generate_exam_analysis(
    exam_id: str,
    mock_id: str,
    topic_accuracies: dict[str, float],
    overall_score: float,
    time_spent: int,
) -> dict[str, Any]:
    """Generate detailed post-exam analysis with insights. Per Context7 docs: structured JSON output with error fallbacks."""
    if not gemini_available():
        weak = [t for t, acc in topic_accuracies.items() if acc < 0.60][:3]
        return {
            "exam_id": exam_id,
            "overall_assessment": f"Score {overall_score:.0f}/100.",
            "weak_topics": weak,
            "improvement_areas": ["Review weak topics", "Increase practice time"],
            "next_focus": weak[0] if weak else "PH2_IFSCA_ACT",
            "estimated_days_to_master": 14,
            "ai_model": None,
        }

    schema = {
        "type": "object",
        "properties": {
            "overall_assessment": {"type": "string"},
            "weak_topics": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            "strength_topics": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            "improvement_areas": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            "next_focus": {"type": "string"},
            "estimated_days_to_master": {"type": "integer", "minimum": 1, "maximum": 365},
        },
        "required": ["overall_assessment", "weak_topics", "improvement_areas"],
    }

    topic_str = "\n".join([f"- {t}: {acc:.1%}" for t, acc in list(topic_accuracies.items())[:10]])
    prompt = _contract_prompt(
        "exam_analysis",
        "Analyze IFSCA exam performance and recommend improvements.",
        f"""Score: {overall_score}/100 | Time: {time_spent} min | Topics:
{topic_str}

Return JSON with: overall_assessment, weak_topics (array), strength_topics (array), improvement_areas (array), next_focus (string), estimated_days_to_master (int).""",
    )

    result = call_json(prompt, schema=schema, temperature=0.3, operation="exam_analysis")
    if isinstance(result, dict) and isinstance(result.get("weak_topics"), list):
        result["exam_id"] = exam_id
        result["ai_model"] = DEFAULT_GEMINI_MODEL
        return result

    weak = [t for t, acc in topic_accuracies.items() if acc < 0.60][:3]
    strong = [t for t, acc in topic_accuracies.items() if acc >= 0.80][:2]
    return {
        "exam_id": exam_id,
        "overall_assessment": f"Score {overall_score:.0f}/100 achieved.",
        "weak_topics": weak,
        "strength_topics": strong,
        "improvement_areas": ["Drill weak topics", "Practice time management"],
        "next_focus": weak[0] if weak else "PH2_BANKING",
        "estimated_days_to_master": 14,
        "ai_model": None,
    }


def generate_personalized_study_path(weak_topics: list[str], exam_date: str, amendments_count: int = 0) -> dict[str, Any]:
    """Generate 12-week personalized study roadmap. Per Context7: with local fallback."""
    if not gemini_available():
        weeks = []
        for i in range(1, 13):
            if i <= 4:
                focus = weak_topics[:3] + ["PH2_IFSCA_ACT", "PH2_BANKING"]
            elif i <= 8:
                focus = ["PH2_FM_REGS", "PH2_CAPITAL"]
            else:
                focus = ["PH2_PAYMENT", "PH2_AML_KYC"]
            weeks.append({
                "week": i,
                "focus_topics": focus[:4],
                "daily_questions": 20 + (i % 3) * 5,
                "milestone": "Revision" if i >= 10 else f"Week {i} topics",
            })
        return {"path_id": f"PATH_LOCAL_{int(datetime.now().timestamp())}", "weeks": weeks, "ai_model": None}

    schema = {
        "type": "object",
        "properties": {
            "weeks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "week": {"type": "integer"},
                        "focus_topics": {"type": "array", "items": {"type": "string"}},
                        "daily_questions": {"type": "integer"},
                        "milestone": {"type": "string"},
                    },
                },
            },
            "study_strategy": {"type": "string"},
        },
    }

    weak_desc = ", ".join(weak_topics[:2]) if weak_topics else "Phase 2 topics"
    prompt = _contract_prompt(
        "study_path",
        "Generate 12-week IFSCA exam study plan.",
        f"""Weak topics: {weak_desc} | Exam: {exam_date} | Amendments: {amendments_count}
Return JSON: weeks array (12 items with week, focus_topics, daily_questions, milestone), study_strategy (string).""",
    )

    result = call_json(prompt, schema=schema, temperature=0.4, operation="study_path_generation")
    if isinstance(result, dict) and isinstance(result.get("weeks"), list) and len(result["weeks"]) == 12:
        result["path_id"] = f"PATH_{int(datetime.now().timestamp())}"
        result["ai_model"] = DEFAULT_GEMINI_MODEL
        return result

    weeks = []
    for i in range(1, 13):
        focus = weak_topics[:2] if i <= 6 else ["PH2_CAPITAL", "PH2_AML_KYC"]
        weeks.append({
            "week": i,
            "focus_topics": focus,
            "daily_questions": 20 + min(i, 8) * 3,
            "milestone": "Final revision" if i >= 10 else f"Master topics",
        })
    return {
        "path_id": f"PATH_LOCAL_{int(datetime.now().timestamp())}",
        "weeks": weeks,
        "study_strategy": "Weak topics weeks 1-6, amendments weeks 6-9, final revision weeks 10-12.",
        "ai_model": None,
    }


def generate_srs_recommendation(topic_id: str, current_accuracy: float, last_reviewed: str | None = None) -> dict[str, Any]:
    """Recommend SRS review interval using Ebbinghaus forgetting curve."""
    if not gemini_available():
        if current_accuracy >= 0.80:
            interval = 30
        elif current_accuracy >= 0.65:
            interval = 14
        elif current_accuracy >= 0.55:
            interval = 7
        else:
            interval = 1
        return {"topic_id": topic_id, "interval_days": interval, "confidence": 0.5, "ai_model": None}

    schema = {
        "type": "object",
        "properties": {
            "interval_days": {"type": "integer", "minimum": 1, "maximum": 30},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reasoning": {"type": "string"},
        },
    }

    prompt = _contract_prompt(
        "srs_recommendation",
        "Recommend optimal review interval (Ebbinghaus curve).",
        f"""Topic: {topic_id} | Accuracy: {current_accuracy:.0%} | Last reviewed: {last_reviewed or 'Never'}
Ebbinghaus: <60%→1d, 60-75%→3d, 75-85%→7d, >85%→30d.
Return JSON: interval_days (int 1-30), confidence (0-1), reasoning (str).""",
    )

    result = call_json(prompt, schema=schema, temperature=0.2, operation="srs_recommendation")
    if isinstance(result, dict) and isinstance(result.get("interval_days"), int):
        result["topic_id"] = topic_id
        result["ai_model"] = DEFAULT_GEMINI_MODEL
        return result

    if current_accuracy >= 0.85:
        interval = 30
    elif current_accuracy >= 0.75:
        interval = 14
    elif current_accuracy >= 0.60:
        interval = 7
    else:
        interval = 1

    return {
        "topic_id": topic_id,
        "interval_days": interval,
        "confidence": 0.6,
        "reasoning": f"Ebbinghaus: {current_accuracy:.0%} suggests {interval}-day interval.",
        "ai_model": None,
    }
