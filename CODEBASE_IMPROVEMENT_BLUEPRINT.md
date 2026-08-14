# Codebase Improvement Blueprint — Toward a Truly Self-Adaptive IFSCA Exam Prep Engine

**Scope:** all 16,042 LOC audited (12,821 backend + 3,221 frontend), original code plus every fix committed in this session (`3aa70d1` → `f49bbd9`).
**Method:** every claim below is grounded in measured evidence (grep/wc counts, live endpoint behavior, test results), not impressions.
**Purpose:** define the highest-leverage logical/coding improvements to move this codebase from "feature-complete skeleton" to the product it declares itself to be: an **AI-powered, source-grounded, daily adaptive study system** (per `memory/FINAL_MAXIMUM_EXTENSIVE_PROJECT_PLAN.md`).

---

## 1. What the app wants to be (its own words)

From the project plan:

> "Build an AI-powered, source-grounded IFSCA Grade A preparation engine that turns 126 collected documents, past exam evidence, user performance history, and live regulatory amendments into a **daily adaptive study system** with smart mocks, penalty drills, essay grading, amendment tracking, analytics, and an exam-mode interface."
> "Nothing should disappear. History is what lets the system adapt."
> "Make drills adaptive and history-aware."

The implied **core adaptive loop** is:

```
attempt (mock/PYQ/drill) → analytics → weakness score → targeting snapshot
        → generation (drill/mock/revision) → attempt → (loop, converging on readiness)
```

**Verdict: the loop does not close.** Every piece of the loop exists and works individually — but nothing connects them autonomously. Evidence:

| Evidence | Count / status |
|---|---|
| `intelligent_targeting_snapshot()` computes `recommended_action` per topic | built, **never consumed by any scheduler or endpoint** (only displayed) |
| `job_queue` executor types actually enqueued | exactly 1: `amendment_questions`, enqueued only by the amendment poller (runs once daily at 03:00 UTC) |
| APScheduler jobs | 2 (amendment poll, job-queue drain) — no study-plan, drill, or mock scheduling |
| `user_id` query params accepted at 5 endpoints | **0 uses in any SQL** — all analytics are hardcoded single-user while the API pretends otherwise |
| `recommendation_engine` decision tree (DRILL/MOCK/AMENDMENT_REVIEW/ESSAY/REVIEW) | computed and returned as text; nothing executes it |
| Startup Gemini calls with keys configured | 1 probe + 1 watchlist + ~15 amendment-seed question generations ≈ **18 calls every boot** (quota burn, slow cold start) |

---

## 2. Current-state evidence inventory (what the audit found)

### 2.1 Duplication / dead weight
| Item | Evidence |
|---|---|
| **Two parallel question stores** | every `save_question()` double-writes `questions` (canonical) **and** `generated_questions` (legacy mirror); legacy table has exactly 2 readers (admin grounding stats) |
| **Three parallel schema families** | `documents/document_chunks` (live), `source_documents/source_chunks` (dead, 0 rows, loader `ingest_extracted_pdfs()` has 0 callers), `question_sources` (legacy authority link, 1 maintenance reader) |
| **Dead modules** | `ingest_sources.py` (no importer), `smart_material_classification.py` (no importer), `input_validation.py` (imported but its classes unused by endpoints), `error_handling.py` (imported for exceptions only; ~200 lines of unused framework classes) |
| **Dead functions** | `ingest_extracted_pdfs`, `schedule_essay_provisions_for_review`, `get_score_prediction_by_topic`, `is_ready_for_exam`, `link_question_to_source`, `generate_srs_recommendation` (1 ref each = self-import), `generate_exam_analysis` (no endpoint uses it) |
| **Frontend dead code** | whole "TCS iON" block (`startExamTimer/updateExamTimer/stopExamTimer/autoSubmitExam`), `showInstructions/closeInstructions`, `showResultPage/returnToDashboard/reviewAnswers` + the `#resultPage`/`#instructionsModal` markup: defined, never invoked |
| **Frontend duplication** | two near-identical exam shells (`examShell`/`pyqExamShell` with `questionStatus`/`pyqQuestionStatus`, `renderPalette`/`pyqRenderPalette`, etc.) ≈ 350 duplicated lines |
| **Duplicate frontend calls** | `loadAmendmentRadar()` called **twice** inside `loadDashboard()` (two fetches of the same endpoint per page load); `refreshAll()` re-triggers the whole chain on top |

### 2.2 Architecture gaps
| Item | Evidence |
|---|---|
| **Logging** | 65 `print(...)` statements across 12 backend modules; `logging` module imported nowhere; no request IDs, no structured logs |
| **Exam sessions are stateless** | `mock_sessions.started_at` set at generation; answers live only in browser memory until submit; no resume, no per-question autosave to server (localStorage keys are written but never read back) |
| **Hardcoded exam config** | `3600` seconds / `60:00` appears 6× in backend + frontend; per-paper timing (real Phase-1 = 60 min 100 Qs, Phase-2 = 60 min 50 Qs) is not modeled |
| **N+1 citation queries** | `submit_mock()` runs a `SELECT * FROM question_citations` **per question** inside the scoring loop (5 call sites total) |
| **Test suite honesty** | `test_e2e_correctness.py`: **32 of 302 lines are `pass`-only stubs** (exam-start contract, error-format consistency, performance-under-failure, data-consistency all untested); no PYQ, scoring, negative-marking, or frontend tests exist |
| **Single-user fiction** | `user_id` params accepted, never used (see §1) — the API contract lies |
| **CORS** | `allow_origins=["*"]` with `allow_credentials=True` |
| **Migrations** | no version ledger table; migration safety depends on idempotent scripts + guards (works, but unverifiable without a `schema_migrations` record) |

### 2.3 What is already good (do not regress)
- Source-grounded question generation with strict Gemini-only mock policy and local fallback discipline.
- Blind exam papers enforced at the **response-model contract level** (`ExamQuestionModel`).
- Idempotent, FK-safe, negative-marking-correct mock + PYQ scoring (session fixes).
- Weakness scoring with recency/attempt-confidence/time-pressure components; amendment-sensitive weighting.
- Canonical `documents`/`document_chunks` index with FTS5, role classification, and admin overrides.
- 44/44 e2e tests passing; cold-start and legacy-DB migration paths verified.

---

## 3. The improvement plan (prioritized)

**P0 = closes the adaptive loop / removes structural lies. P1 = multiplies quality and velocity. P2 = depth features from the app's own known-missing list.**

### P0-1. Build the adaptive scheduler (close the loop)
**Why:** the app's one-sentence vision is a *daily adaptive study system*; today all adaptation is manual.
**What:**
- New module `adaptive_planner.py`: on a daily schedule (and after every mock/PYQ submit), read `intelligent_targeting_snapshot()`, then **enqueue jobs** using the existing `job_queue`: `drill_generation` for CRITICAL/WEAK topics, `mock_generation` when attempt-count low, `amendment_review` when pending amendments ≥ threshold, `wrong_answer_replay` from recent misses.
- Extend `job_queue.process_queue` executor map with the new job types (each already has a working function: `generate_topic_questions`, `db.generate_smart_mock`, `generate_amendment_questions`).
- Make `recommendation_engine.get_next_action_for_dashboard` output **consumed**: the dashboard "Next Action" button should execute the action (deep-link to drill/mock/essay tab with parameters), not just display text.
- Add a `study_plan` table snapshot per day so "Today" tab shows the auto-generated plan instead of only raw panels.
**Files:** new `backend/adaptive_planner.py`, `backend/job_queue.py`, `backend/main.py` (scheduler registration), `frontend/index.html` (next-action wiring).
**Risk:** low — every primitive exists; this is orchestration.

### P0-2. Kill the data-model lies: one question store, one identity
**Why:** double-writes to `generated_questions` and fake `user_id` are the two biggest structural debts; they create drift risk and false API semantics.
**What:**
- **Question store:** stop writing `generated_questions` in `save_question()`; migrate its 2 readers (admin grounding stats, provision related-questions) to `questions` + `question_citations`; drop the legacy table after a one-time data merge migration (idempotent, ledgered).
- **Identity:** either (a) implement real `user_id` end-to-end (add `user_id` columns/`WHERE` clauses to `question_attempts`, `topic_stats`, `mock_sessions`, analytics queries — a contained, mechanical change) or (b) **remove** the misleading params and declare single-user. Recommendation: (b) for now (single-user local app per plan), with (a) as a follow-up if multi-profile becomes a goal. The key is the API must stop pretending.
- Delete dead modules/functions from §2.1 (with grep-verified zero callers): `ingest_sources.py`, `smart_material_classification.py`, unused `input_validation`/`error_handling` framework classes, `link_question_to_source`, `get_source_authority_for_chunk`, `ingest_extracted_pdfs` and the legacy `source_*` schema once migrated.
**Files:** `backend/database.py`, `backend/main.py`, `backend/models.py`, one migration SQL.
**Risk:** medium (schema surgery) — mitigate with the idempotent migration runner + full-suite regression.

### P0-3. Unify the exam engine (mock + PYQ) with server-side session state
**Why:** two parallel exam shells duplicate ~350 lines and diverge (PYQ got negative marking + blind scoring fixes; the mock path gets exam rules); sessions die on refresh (no resume); the plan's Module 8 (TCS iON familiarization) is half-dead code.
**What:**
- Backend: `exam_session` endpoints — `POST /api/exams/start` persists a session with per-paper config (question count, seconds, marks, negative fraction from a config table instead of the 6× hardcoded `3600`); `PATCH /api/exams/{id}/answers` autosaves each selection (idempotent upsert into `answers`); `GET /api/exams/{id}` restores state; submit reads persisted answers (browser memory no longer the only copy).
- Frontend: extract one `ExamEngine` JS object (state, timer, palette, autosave, keyboard) parameterized by paper config; both tabs consume it; delete the dead TCS block and unused result page; replace 53 inline `onclick=` handlers with delegated listeners (`data-action` attributes) — removes the whole class of quoting/escaping bugs we fixed by hand.
**Files:** `backend/main.py`, `backend/database.py`, `backend/models.py`, `frontend/index.html` (largest frontend change).
**Risk:** medium-high on frontend; sequence as its own commit with manual smoke of both exam types.

### P1-1. Gemini layer: concurrency, backoff, caching, cost control
**Why:** startup burns ~18 calls; question generation is sequential across topics; the plan itself (Module 4B) specifies a retrieval/prompt cache.
**What:**
- Bounded async concurrency for mock generation batches (`asyncio.Semaphore(3)`), keeping current key rotation.
- Exponential backoff + jitter on 429 (today: flat 60 s cooldown; fine but coarse).
- **Prompt/response cache** keyed by (topic, difficulty, source-chunk-hash-set) in SQLite — reuses questions across mock generations instead of always paying Gemini (still saving new `Q_AI_` rows per mock for anti-repeat).
- Defer startup watchlist + amendment question seeding to background jobs (startup probe only).
- Track per-key calls/latency/cost estimates in the existing `GEMINI_STATE` health payload.
**Files:** `backend/gemini_integration.py`, `backend/database.py`, `backend/main.py` lifespan.
**Risk:** low-medium; health endpoint already exposes state for verification.

### P1-2. Adaptive math upgrades (from the code's own next-upgrade notes)
**Why:** `_function_improvement_audit` already names these; they directly improve adaptation quality.
**What:**
- Bayesian (beta-prior) accuracy smoothing in `calculate_weakness_score` instead of raw ratios (fixes 1/1=100 % noise).
- Time-normalized per-topic penalty (already partially present via `time_pressure`; extend to trend over attempts).
- Confidence intervals on weakness scores → `confidence_band` per topic in the snapshot.
- **Wrong-answer replay drill** (known_missing): select recent `is_correct=0` questions per topic, regenerate source-grounded variants, produce `DRILL_REPLAY` sessions.
- PYQ analytics separate from mock analytics in `question_attempts` (already separate tables — surface both in the dashboard and readiness estimate; today readiness ignores PYQ entirely).
**Files:** `backend/database.py`, `backend/readiness_engine.py`, `backend/main.py`.
**Risk:** low; math is localized.

### P1-3. Observability & ops
**Why:** 65 prints, no logging framework — undebuggable in production and the plan's "production-ready" critique stands.
**What:** module-level `logging` with JSON formatter (the `.env.example` already anticipates `LOG_FORMAT=json`); request-ID middleware; replace prints; migration ledger table (`schema_migrations(version, applied_at)`) driving `_run_migration_*` guards; DB backup on startup (copy before migrations, keep N).
**Files:** `backend/error_handling.py` (or new `backend/logging_setup.py`), `backend/database.py`, `backend/main.py`.
**Risk:** low.

### P1-4. Test suite honesty
**Why:** 32 pass-only stubs give false confidence (three rounds of critical bugs shipped with "green" tests).
**What:** implement the stubbed contracts as real tests; add scoring contract tests (negative marking, unanswered≠wrong, blind payload asserts on both exam endpoints); property tests for `allocate_question_slots` (slots sum to total; ratios within tolerance; non-negative); PYQ load→submit→analytics; frontend smoke via `node` (jsAttr quoting, exam engine state machine) as a `make check` step.
**Files:** `backend/tests/*`.
**Risk:** none; pure addition.

### P2-1. Data pipeline & taxonomy
- **Incremental ingestion** (hash-aware: only re-ingest changed files; today `force=True` re-chunks everything).
- **Topic sub-taxonomy** (known_missing): parent→child mapping in `topics` (schema already has `parent_topic_id` — unused).
- **Recollected-paper practice mode**: papers without answer keys (2023 Phase-1) load in "no-score practice" mode instead of being excluded.
- **Source contradiction detector** (known_missing): cross-chunk claims diff surfaced in the topic brief.
**Files:** `backend/database.py`, `backend/pyq_parser.py`, `backend/main.py`, `backend/gemini_integration.py`.
**Risk:** medium (content quality); keep behind feature flags.

### P2-2. Security & configuration hardening
- CORS: restrict to the actual frontend origin (the app is single-user local).
- Config table for exam paper definitions (time/marks/negative/phase) replacing hardcoded constants.
- Sanitize/validate admin endpoints (materials role, ingest) behind a simple local admin token.
**Files:** `backend/main.py`, `backend/database.py`, `.env.example`.
**Risk:** low.

---

## 4. Suggested sequencing (3 phases)

| Phase | Items | Approx. size | Exit criteria |
|---|---|---|---|
| **1. Structure** | P0-2 (one store, honest identity, dead-code removal), P1-3 (logging/migrations), P1-4 (test honesty) | 4–6 focused PRs | 0 dead modules; single question store; migration ledger; 0 `pass`-stubs; suite green |
| **2. The loop** | P0-1 (adaptive scheduler), P1-2 (adaptive math), P1-1 (Gemini efficiency) | 3–4 PRs | a daily plan is auto-generated and jobs drain autonomously; startup ≤2 Gemini calls; weakness scores carry confidence |
| **3. The experience** | P0-3 (unified exam engine + frontend modularization), P2-1 (pipeline/taxonomy), P2-2 (security) | 3–4 PRs | resume-capable exams for mock+PYQ from one engine; inline handlers eliminated; per-paper config; subtaxonomy live |

**Non-goals (deliberately excluded):** multi-user SaaS, mobile apps, vector DB — the plan document itself scopes this as a single-user local engine built on a 126-document corpus.

---

## 5. Guardrails

1. Every phase ends with the 3-step verification used throughout this session (logic checkup → regression/unknown-bug audit → patch audit) before merge.
2. Any schema change ships with an idempotent, ledgered migration + a data-merge step verified on both a cold-start and a legacy DB.
3. No feature removal without a grep-verified zero-caller audit (the discipline that caught 3 of my own regressions this session).
