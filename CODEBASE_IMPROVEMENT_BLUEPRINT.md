# Codebase Improvement Blueprint — Toward a Truly Self-Adaptive IFSCA Exam Prep Engine

**Scope:** all 16,042 LOC audited (12,821 backend + 3,221 frontend), original code plus every fix committed in this session (`3aa70d1` → `f49bbd9`).
**Method:** every claim below is grounded in measured evidence (grep/wc counts, live endpoint behavior, test results), not impressions.
**Purpose:** define the highest-leverage logical/coding improvements to move this codebase from "feature-complete skeleton" to the product it declares itself to be: an **AI-powered, source-grounded, daily adaptive study system** (per `memory/FINAL_MAXIMUM_EXTENSIVE_PROJECT_PLAN.md`).

> **v2 addendum (deep re-analysis)** — see §6: three flaws in the *adaptive core itself* (difficulty-confounded weakness, readiness scale conflation, wrong penalty factor) that the first pass missed, with the corrected plan.

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
- **Difficulty-adjusted accuracy FIRST** (the deepest adaptive flaw — see §6.1 Flaw 1): compute per-difficulty accuracy from the newly recorded `question_attempts.difficulty`, compare topics only within the same difficulty band, and rebalance the difficulty curve so "strong" topics stop being measured exclusively on easy questions.
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
3. No feature removal without a grep-verified zero-caller audit (the discipline that caught several of this session's own regressions).
4. When a measurement reveals a policy defect, fix the policy in the same breath — or state explicitly why not (see §7.6).

## 6. Deep re-analysis addendum (v2) — findings the first pass missed, and why

This section is the result of re-interrogating the blueprint *and my own earlier fixes* with the same adversarial standard applied to the original code. It is the most important part of this document: it corrects the plan where the first pass was wrong.

### 6.1 What the first pass missed (self-criticism)

Three critical flaws survived three rounds of bug-hunting because my hunting method was *path-tracing* (does this endpoint crash / return wrong values?) rather than *systems-tracing* (do the units and feedback loops compose?). All three are now fixed in code (see the `fix: adaptive-core correctness` commit) and verified live:

**Flaw 1 — the adaptive loop has a confirmatory difficulty bias (fixed in code).**
Measured on a fresh database: "weak" topics (pre-ranked by exam weight before any user data exists) are served **6 easy / 12 medium / 12 hard** questions per mock, while "strong" topics get **8 easy / 0 medium / 0 hard**. Accuracy is computed **difficulty-blind** (`question_attempts` had no difficulty column). Consequence: the engine measures weak topics under a harder question mix and strong topics under a trivially easy mix — so the weakness ranking *self-confirms and amplifies* regardless of true ability. This is a flaw in the app's core purpose, more consequential than any crash fixed in rounds 1–3.
Fix shipped: `question_attempts.difficulty` now records per-question difficulty at attempt time (both smart-mock and uploaded-mock paths). This is the data foundation; §3 P1-2 now leads with difficulty-adjusted accuracy (per-difficulty scoring, or compare only within difficulty) before any Bayesian smoothing.

**Flaw 2 — readiness engine conflated score scales (fixed in code).**
`submit_mock` stores scores on a **0–100** scale (marks normalized to 100), but `get_user_performance_history` mixed that with a `+4/−1` formula (a **0–200** scale), and `calculate_readiness_estimate` projected the mixture directly against a **0–200** target. Measured: a user scoring 80–82/100 in every mock was told `final_score_estimate: 88/200, readiness: 34%, LOW` — an excellent user systematically told they were failing. Tests were green because no test asserted numeric correctness.
Fix shipped: history is now uniformly 0–100 (stored scores, or session accuracy percentage as fallback), projected in 0–100 space, and scaled ×2 only at the 0–200 output boundary. Re-verified: the same strong user now gets `176/200, 100%, HIGH`.

**Flaw 3 — PYQ negative marking applied a wrong constant (fixed in code).**
Round 3 "fixed" PYQ scoring to apply the hardcoded `0.67` penalty — but the app's own exam contract says negative marking is **one-fourth**, and with `marks_per_question = 2` the correct penalty is **0.5**. I had made the code consistent with its own wrong constant instead of with the exam rule — exactly the "ignore the root problem" failure the audit was meant to prevent. Fix shipped: `0.5` advertised and applied (live-verified: 41 wrong → −20.5).

### 6.2 Corrections to the plan

- **§3 P1-2 reordered:** difficulty-adjusted accuracy is now item #1 (the confirmatory bias is the deepest adaptive flaw), ahead of Bayesian smoothing and wrong-answer replay.
- **§4 sequencing corrected:** cost control (P1-1) must land **before** the adaptive scheduler (P0-1). Autonomous nightly generation without a prompt/response cache and backoff would silently drain API quota — autonomy without cost guardrails is a regression, not a feature.
- **§2.3 "what is already good" amended:** readiness scoring and PYQ penalty math are no longer "good" — they were broken in ways the original test suite could not see (see Flaws 2–3).

### 6.3 Known imprecisions that remain (honest, unfixed)

- **`last_improved_at` semantics** in `get_weakest_topic_for_user` returns the date of the last *correct* answer, not the last accuracy improvement — an acceptable recency proxy but not what the field name claims; the MOCK decision rule inherits this imprecision.
- **`mock_sessions.started_at` is set at generation**, not when the attempt begins; the `/api/exams/{id}/submit` timer (403 path) can therefore expire a mock that was generated but never started. Belongs to the P0-3 session-state work.
- **PYQ attempts do not feed readiness/weakness** (separate tables by design); a candidate who only practices PYQs looks like a no-data user.
- **Score display inconsistencies** (result page shows /200, dashboard estimate is 0–100, exam modal says +4/−1) remain cosmetic until P0-3's per-paper config lands.
- **`answers` and `question_attempts` duplicate each other** for smart mocks; consolidation is bundled with P0-2.

### 6.4 Method correction for future rounds

Any future pass must, before shipping, trace **units and feedback loops** end-to-end (score scale → history → projection; difficulty allocation → difficulty-blind metrics → ranking), not just endpoints. The three flaws above were each one unit-trace away and each survived because the tests assert *shape*, not *numbers*.

### 6.5 Deepest layer: the adaptive planner had only ONE live sensor (fixed in code)

The next level below units and loops is *sensor wiring*: which signals actually reach the planner (`intelligent_targeting_snapshot` → weakness → allocation). The audit found the planner consumes exactly one live signal — `question_attempts` from mock submits — while **four advertised sensors were dead or frozen** (each verified with decisive greps, fixed, and re-verified):

1. **Amendment mastery was frozen.** `amendment_events.mastery_status` had **zero UPDATE statements** in the codebase — seeded "NEW" once, never changed. The `amendment_recency` term in weakness scoring and `pending_amendments` in the targeting snapshot were therefore constants; the app could never adapt to a shrinking amendment backlog. Fixed: `POST /api/amendments/{id}/master` + `db.set_amendment_mastery` (writes `MASTERED`/`NEW` and `last_reviewed_at`), with a "Mark Mastered" button in the amendment table. Verified: 15 pending → 14 pending, DB row MASTERED.
2. **The Penalty Drill Engine wrote nothing.** `penalty_drills` had **zero INSERTs** — the headline Module 3 generated questions, displayed them, and produced no data, so drills were invisible to the planner. Fixed: drill rows are persisted at generation, a new `POST /api/penalty-drill/{id}/submit` scores server-side against the recorded bank and writes attempts with `source=PENALTY_DRILL` (idempotent), `penalty_drills.completed/accuracy_after` are updated, and `calculate_topic_accuracy()` runs after submit so the drill immediately moves the weakness signal. Frontend: drills are now answerable with a submit flow and post-submit review. Verified: 4/4 attempts recorded, `topic_stats.total_seen` updated from the drill.
3. **Essay scores never reached the planner** — `essay_scores` feeds only history and a bonus term. Documented as a P0 wiring item (essay rubric → topic evidence signal), not yet built (needs rubric→topic mapping design).
4. **PYQ attempts never reached the planner** (separate tables by design). Documented: readiness/weakness must consume `pyq_question_attempts` in addition to `question_attempts`.
5. **The dashboard headline metric summed incommensurables.** `estimated_score = 0.7×accuracy + library_bonus + amendment_count_bonus + essay_bonus` — a fresh user with zero attempts displayed an "Est. Score" of 19/100. Fixed: `estimated_score` is now performance-only (equals `overall_accuracy`, capped 100), resource health is reported separately as `resource_health` (and surfaced through `DashboardStatsModel`, which previously stripped it), and the UI metric now honestly reads "Mock Accuracy %".
6. **SRS storage model contradicted the SM-2 algorithm.** `schedule_topic_review` appended a new row per call and `mark_topic_reviewed` bulk-updated *all* rows for the topic — one click destroyed the per-item scheduling state. Fixed: one row per topic (INSERT OR REPLACE), completion updates only the soonest-due row and removes stale duplicates. Verified: double-schedule → 1 row; completion → single `('success', 3)`.

Also confirmed and left documented (data-quality, not wiring): the question bank has **no duplicate detection** — every mock writes ~50 new rows and near-duplicate stems accumulate forever; a `stem_hash` dedup column is the designed fix (P0-2 bundle). And `_sqlite_now_minus` uses local time vs SQLite UTC timestamps (boundary skew of a few hours in recency filters).

### 6.6 The corrected mental model

The app is best understood as: **sensors → planner → generators → sensors**. Auditing any layer in isolation gives false confidence. Round 5's method — list every table the planner reads, grep for its writers, and treat zero-writer tables as dead sensors — found five real defects that endpoint tracing could never surface. This is now the standing checklist for any future pass.

## 7. The policy layer — the missing middle (v3)

### 7.1 Diagnosis: a heuristic pile without an objective

Auditing the levels below endpoints revealed the deepest structural truth about this app: **the system has no objective function.** Every component optimizes its own hand-tuned scalar:

- weakness score: a weighted sum of error rate, recency, attempt-confidence, exam weight, amendment count, and time pressure — coefficients chosen by intuition (`0.35/0.25/0.15/0.10/0.10/0.05`).
- allocation: 60/25/15 weak/medium/strong split — ratio never derived from anything.
- difficulty: previously conditioned on weakness rank (now fixed — see below).
- SRS: SM-2 applied to topics it was never designed for (content-agnostic).

"Self-adaptive" so far meant "self-reallocating by fixed heuristics." A self-adaptive system requires a *stated objective* and policies chosen to optimize it. This is not a polish item — it is the definition of the product.

### 7.2 The formal model

**Objective.** Maximize expected exam score subject to a practice-time budget:

> E[exam score] = Σ_topics w_t · P_t(correct | exam difficulty)
> maximize over weekly policies π: (allocation_t, difficulty_t, revision_t) for each topic
> subject to Σ practice minutes ≤ budget

This is a **restless multi-armed bandit**: each topic's state decays without practice (forgetting), so the optimal policy is not "drill the weakest" but "allocate where marginal expected-score gain per minute is highest."

**State per topic** (all derivable from data already recorded): accuracy estimate with uncertainty (from `question_attempts` incl. difficulty and `time_spent_seconds`), attempts, exam weight `w_t`, amendment sensitivity, days-since-last-attempt.

**Policy hierarchy** (what each control variable may depend on):
1. **Difficulty** — depends on *attempt history only* (exogenous: the exam doesn't get easier for your strengths). ✅ FIXED in commit `d1c3b21` (this round): `_difficulty_mix_for_topic`; locked in by `tests/test_adaptive_policy.py`.
2. **Allocation** — depends on (uncertainty, weight, decay, remaining budget). Currently a fixed 60/25/15; a per-topic minimum-observation floor is required for measurement sufficiency (see the 1-question-per-topic evidence below) but its value must come from the simulator, not from another hand-tuned constant.
3. **Revision timing** — depends on a fitted forgetting curve per topic, not generic SM-2 intervals.
4. **Content selection** — amendment/contradiction injection into the topics the policy selects.

### 7.3 The five policy primitives and their status

| # | Primitive | Status |
|---|---|---|
| P1 | Exogenous difficulty (attempt-conditioned scaffolding → exam-like mix) | **FIXED this round**, with contract tests |
| P2 | Allocation floor for measurement sufficiency (currently strong topics get 1 question — binary accuracy, max variance, zero maintenance) | Deferred to simulator (parameter, not intuition) |
| P3 | Per-topic forgetting curves — fit λ_t from existing `created_at` timestamps; readiness and revision timing should consume decay, not linear extrapolation | Designed, data already present |
| P4 | Time-based difficulty calibration — `time_spent_seconds` is the most reliable *per-user* difficulty signal (single user ⇒ classical IRT can't calibrate items); use time-normalized accuracy and per-question time distributions | Designed |
| P5 | Difficulty-label validation — verify easy<medium<hard pass rates in recorded data once attempts exist; if labels don't validate, fall back to P4's time signal | Designed |

### 7.4 Simulator-first methodology (the next engineering stage)

**Why a simulator before any more heuristics:** the current policy's cost has never been quantified. A simulator turns "this heuristic looks biased" into "this heuristic costs the user X projected marks."

1. **Learner model per topic** (fit from the user's own history, which is already in the DB):
   - knowledge k_t ∈ [0,1]; decay k ← k·exp(−λ_t·days_since)
   - practice gain k ← k + η_t·(1−k)·g(difficulty), where g(hard) > g(medium) > g(easy)
   - answer model: P(correct | k, difficulty) = k · base(difficulty)
2. **Fit:** λ_t, η_t by maximum likelihood over the recorded attempt sequence (timestamps + is_correct + difficulty are all logged since round 4).
3. **Backtest:** replay history; compare (a) current heuristic policy vs (b) simulator-optimal allocation/difficulty/revision on projected E[exam score]. The delta is the quantified cost of the heuristics — and the budget justification for every subsequent policy change.
4. **Deploy:** weekly planner runs the simulator over candidate policies (grid search over allocation vectors is trivially cheap at 17 topics, 1 user) and schedules the winner through the job queue (P0-1).

### 7.5 Sequencing correction (v3 — supersedes v1/v2 ordering)

Correct build order is: **policy correctness → measurement → simulation → autonomy.** The adaptive scheduler (blueprint P0-1) must ship only *after* the policy it automates is simulator-validated — automating a biased policy makes the bias autonomous. (v2 already fixed the cost-guardrail order; v3 fixes the policy order.)

### 7.6 Self-critique log (entry #5)

Round 4 found the difficulty confounding and shipped **only the measurement half** (recording difficulty), leaving the difficulty *policy* biased — strong topics were still practiced 100% easy until this round. The rule this violated: *when a measurement reveals a policy defect, fix the policy in the same breath, or state explicitly why not.* The audit's own discipline must apply to the audit's fixes, not only to the original code.

---

*Blueprint version: v3 (policy layer). Next engineering stage per §7.4: fit the learner model from recorded history and backtest the heuristic policy — every subsequent policy change gets a quantified projected-score delta before it ships.*
