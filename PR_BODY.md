# fix: critical bug fixes for exam, PYQ, law-revision, schema-init and frontend tool flows

**Branch:** `arena/019fffa6-exam-preparation` → **base:** `main`

This PR bundles three consecutive audit passes over the IFSCA exam-prep codebase
(FastAPI + SQLite backend, single-file frontend). Every finding was reproduced
against a live server / fresh database before being fixed, and re-verified after.
The bundle also incorporates the cross-checked fixes from PR #1 (independent
audit of the same base) — every claim in PR #1 was re-verified in this tree;
several were already fixed here, the rest are fixed in this branch.

## Commit 1 — `258c5a0` (pass 1: critical endpoint bugs)

| # | Bug | Symptom → fix |
|---|-----|---------------|
| 1 | `POST /api/exams/start` assigned to a frozen Pydantic model | 500 `'QuestionModel' object does not support item assignment` → dict payloads, Phase-3 fields present |
| 2 | `TopicModel.phase/paper` required but seed rows leave them NULL | `GET /api/topics` 422 on fresh DB → fields optional; frontend bootstrap unblocked |
| 3 | PYQ list/load read never-populated legacy `source_documents`/`source_chunks` | 0 papers on fresh installs → rewired to canonical `documents`/`document_chunks`; roles categorized |
| 4 | PYQ submit FK failures (`pyq_source_doc_id=0`, cached-only `question_id`) | every submit 500 `FOREIGN KEY constraint failed` → tables rebuilt FK-free (idempotent, row-preserving) |
| 5 | PYQ scoring integrity | denominator was `len(answers)` (partial submit → 100%), `unanswered` hardcoded 0, −0.67/wrong never applied, hidden questions gradeable → scored against displayed set; idempotent resubmit |
| 6 | PYQ submit `.get()` on Pydantic `AnswerModel` | crash masked by FK bug → attribute access |
| 7 | `submit_mock` no resubmission guard | double submit duplicated `question_attempts` rows (stats corruption) → 400 on resubmit |
| 8 | `/api/srs/schedule-topic` response model `dict[str,str]` | 500 on int `interval_days` → `dict[str, Any]` |
| 9 | `get_weak_legal_areas` selected nonexistent `topic_stats.display_name` | daily law revision silently empty → LEFT JOIN `topics` |
| 10 | `app.mount("/app")` dead code inside ValueError handler | `/app` 404 → moved to module level |
| 11 | Migration 004 non-idempotent `ALTER ADD COLUMN` | `duplicate column name` on every startup → skip when column exists |
| 12 | CORS `*` + `allow_credentials=True` | invalid combo; cross-site reachable → restricted to local origins (`CORS_ORIGINS` overridable) |
| 13 | `start.bat` opened frontend via `file://` | `fetch('/api')` cannot reach backend → opens `http://localhost:8000` |

## Commit 2 — `7f0eef0` (pass 2: full-coverage, migration ordering, perf)

- `_categorize_materials` per-request overhead (150-row scan + UPDATEs + 10 prints
  per `init_db()` call) → fast path: 3 COUNTs, zero UPDATEs when fully categorized.
- Migration ordering: `_populate_source_role_on_documents` ran before 004 on fresh
  DBs (`no such column: sd.source_role`) and NULLed `supporting_material` roles via
  empty scalar subquery on every init → 004 first, legacy bridge only when the
  legacy table has rows.
- `documents.source_role` created in `_ensure_runtime_schema` (idempotent) so the
  first `init_db()` on a fresh DB fully succeeds.
- `ingest_documents` categorizes immediately after indexing.
- `_create_performance_indexes` log spam → logs only when indexes are created.
- `amendment_poller` leaked its `httpx.AsyncClient` per daily poll → closed.
- Removed dead `input_validation` import; runtime logs untracked + gitignored.

## Commit 3 — `0768f1f` (PR #1 cross-check: frontend handlers, study-path, SRS, recency, key rotation)

Every PR #1 claim re-verified in this tree. Already-fixed equivalents (topics 422,
PYQ FKs, PYQ rewiring, weak-areas JOIN, `/app` mount, mock idempotency, role
categorization, `_populate` NULL-guard) confirmed. Newly fixed here:

**Frontend (2 of these were introduced by this branch's pass-1 rewiring):**
- PYQ cards interpolated string `doc_id` unquoted → `ReferenceError` on every
  click; index-based handlers (apostrophe-safe), proven by executing the generated
  handlers in node.
- `startPYQPaper` called POST-only `/api/pyq/{id}/load` with GET → 405; now POST.
- `updateMaterialRole` unquoted string id → `ReferenceError`; now quoted.
- Removed duplicate `/api/amendments/status` fetch per dashboard load.
- Dashboard metric label "Est. Score" → "Mock Accuracy %".

**Backend:**
- Study-path generate returned Gemini weeks but persisted a different
  deterministic plan → `/api/study-paths/current` now matches what was generated.
- SRS: one row per topic; completion updates only the soonest-due row and drops
  stale duplicates (previously bulk-updated every row).
- Amendment recency cutoffs now use SQLite TIMESTAMP format (ISO 'T' strings
  excluded boundary rows) — 3 sites.
- Amendment ordering CASE-based (lexical `priority DESC` put NORMAL above
  CRITICAL) — 2 sites.
- Gemini key rotation respects 429/401/403 cooldowns (was `available or keys`).
- PYQ cache TTL 15 min → 2 h (expired mid-exam); session rows carry real title.
- `/api/exams/start` payload is blind: answer key stripped.
- `PRAGMA busy_timeout = 30000` on connections.
- `init_db()` guarded per DB path (with exists() check).
- `estimated_score` is performance-only; corpus health reported as
  `resource_health` (DashboardStatsModel field added).
- Strong topics no longer practice 100% easy questions (difficulty confound);
  attempt-rich topics get an exam-like easy/medium/hard mix.
- `pytest-asyncio` added to requirements (suite went 30 failed → 2 failed).

## Verification

- **Regression tests:** `backend/tests/test_regressions.py` — 19 tests, all
  passing, hermetic (no Gemini needed). Full suite: **61 passed / 2 failed** —
  the 2 remaining require Gemini API keys (they call `/api/generate-smart-mock`
  without keys; the app deliberately 500s rather than falling back to local
  filler — a documented design decision).
- **Fresh-DB cold start:** clean boot (single index line, single categorization
  line), 0 NULL roles, PYQ list → load → submit → analytics round trip with real
  paper titles, study-path generate/current identical, SRS double-schedule → 1
  row and mark-reviewed → success/3, amendments ordered CRITICAL first.
- **Frontend handlers:** generated inline handlers executed in node — no
  ReferenceError, correct arguments, apostrophe-safe titles.
- **Legacy-DB upgrade:** schema repair and role backfill paths verified
  idempotent and row-preserving.

## Known leftovers (documented, not critical)

- 2 e2e tests require Gemini keys to pass (design mismatch, not app bugs).
- Startup makes ~15 Gemini calls when keys are configured (probe + amendment
  seeding + watchlist) — consider backgrounding.
- `smart_material_classification.py`, `input_validation.py` classes, and the
  legacy `source_documents`/`source_chunks`/`question_sources` tables remain
  unused (dead code, kept for migration safety).
- Mock generation still issues one Gemini call per question (slow, rate-limit
  prone) — batching was proposed in PR #1; not included to keep this PR focused.
