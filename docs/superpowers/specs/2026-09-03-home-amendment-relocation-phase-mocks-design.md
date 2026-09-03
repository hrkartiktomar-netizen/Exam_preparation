# Design: Home amendment relocation, readable sources, phase mocks, and a tree-aware start.bat

Date: 2026-09-03
Branch: `feature/ledger-award-pass` (worktree `D:\Exam_preparation\.worktrees\ledger-award-pass`)
Base commit: `bcabdb48`
Status: approved section-by-section by the user; awaiting spec review

## Origin

The user's request, verbatim:

> Don't want the amendment update on home page, give me a button that takes me to amendment
> intelligence tab, list latest act updates there, for me to manually read. Mock section should
> also contain option to generate separate phase exams, read md files for context, fix, after
> that when everything is verified fixed and running, fix and update start.bat from scratch.

A follow-up screenshot of the **§ DAILY ACT REVISION · DAY 2 · 121 LINES** block — raw OCR
statute text containing `(*d*)`, `*[Page 5 of 21]*`, `**Terms of office...**` — with the note
"i dont want to see this on homepage" identified the precise home-page target.

And, twice: "continue, also finally after all error verification update start.bat end to end."

## Constraints carried into this work

- All edits land in the worktree. The main tree stays dirty by design. No local merges.
- Never print the git origin URL unredacted. Do not touch the leaked PAT.
- Never `--amend`. Stage by explicit path. Commit with inline `-c user.name` / `-c user.email`.
- There is no dead code, ever: re-point orphans rather than deleting capability.
- Do not delete lines of code unnecessarily.
- Zero-regression priority over feature completeness.
- TDD with a watched RED before each implementation.
- Verification claims require fresh evidence in the current message.

---

## Section 1 — Scope and architecture

### In scope, in the user's order

1. Remove the § DAILY ACT REVISION quiet-beat block from the home page entirely.
2. Add a button on the §01 NOTIFY statute panel that navigates to the Amendment Intelligence tab.
3. In that tab: a clean ledger, per-row old→new detail, and a **READ SOURCE** action that opens
   the actual `.md` document.
4. Mock section: generate separate phase exams by threading the existing `exam_templates`
   through `/api/exams/start`.
5. Rewrite `start.bat` from scratch — worktree-only, tree-aware — **strictly last**, after
   everything else is verified fixed and running.

### Architecture

No new services, no new tables, no migrations.

- Two new read-only `GET` endpoints: `/api/exam-templates` and `/api/documents/{name}`.
- One behavioural fix to an existing endpoint: `/api/exams/start`.
- One filter change inside an existing handler: `get_updates`.
- Frontend edits confined to five existing files: `index.html`, `js/today.js`, `js/views.js`,
  `js/exam.js`, `js/api.js`, plus CSS deletions in `css/today.css` and `css/motion.css` and one
  new rule.
- Environment: the nine Gemini keys move to Windows user-level environment variables so every
  tree resolves them identically.

The document route resolves a **basename only** against an allowlist built by walking
`source_documents/md/**`. Anything else is a 404. No path traversal surface, no corpus mount.

### Out of scope — disclosed, not forgotten

- `exam_submit` returning an error body with HTTP 200, which the frontend reads as a score of zero.
- `renderConstellation` painting invented labels.
- `renderProof` scatter (needs a new endpoint).
- CSS/JS cache-busters.
- Orphaned `API.aggregate`, `API.examAnalytics`, `API.amendmentsRecent`.
- The leaked PAT.
- The dropped reset-data button.
- `latest_descriptive_performance()` not being user-scoped.
- Per-template marks and negative marking in submit scoring (see Section 4).

---

## Section 2 — Home page

### 2a. Remove the quiet-beat block

Evidence: the block is the `.quiet-beat` section at `index.html:153-160`, rendered by
`renderQuietBeat` (`today.js:406-449`), called at `today.js:787`, fed by `API.lawDaily()`
(`api.js:59` → `GET /api/law/daily-revision?include_ai=false`, `main.py:1013`).

Delete:

- `index.html:153-160` — the `.quiet-beat` markup including `.quiet-beat__eyebrow`,
  `.quiet-beat__text`, and both `.quiet-beat__btn` elements.
- `today.js:406-449` — `renderQuietBeat`.
- `today.js:787` — its call site.
- `today.css:476-553` — the `.quiet-beat*` and `.ghost-word` rule block.
- `today.css:684` — the responsive `.quiet-beat__actions` rule.
- `today.css:809` — `.quiet-beat__text .ghost-word:first-child::first-letter`.
- `today.css:818-822` — the `.quiet-beat.is-visible` animation **and** the
  `@keyframes quiet-settle` block it references. Deleting 818 alone would orphan the keyframes,
  which the no-dead-code rule forbids.
- `motion.css:56`, `63` — quiet-beat motion and reduced-motion rules.

Keep — explicitly, because they are shared or still consumed:

- The `lawData` fetch at `today.js:738`. It is **not** orphaned: the finale stamp button
  (`today.js:810-824`) calls `API.lawComplete(lawData.day_index, dayLines)` and needs it.
- `tokens.css:81` — it is a comment only, not a rule.
- `today.css:805-806` — `.mask-reveal` / `.mask-reveal__inner`. These belong to the generic
  line-mask utility, not to quiet-beat.
- `motion.css:55` — the `.mask-reveal__inner` reduced-motion override, same reason.
- `today.js:697-725` — `attachMaskReveals`. Generic utility; see the orphan decision below.

Note: the two `.quiet-beat__btn` elements already have no handlers anywhere in the codebase.
They are dead today; removing them deletes no capability. The live completion action is the
finale stamp, which is untouched.

### Orphan decision disclosed: `mask-reveal`

`index.html:155` is the **only** markup in the entire frontend carrying `.mask-reveal` /
`.mask-reveal__inner`. After the quiet-beat removal, `attachMaskReveals` has zero consumers.

It does not break: `today.js:701` already guards with `if (!inners.length) return;`, so the
utility no-ops cleanly.

Three possible resolutions:

- **(a) Keep it as a self-guarding generic utility with no current consumer.** Recommended, and
  the default this spec assumes. It deletes no LOC, changes no other section's visuals, and
  preserves a working animation primitive for the next eyebrow that wants it. Cost: it is
  technically an orphan, which tensions against "there is no dead code, ever."
- **(b) Re-point it** by adding `mask-reveal` to another existing eyebrow. Cost: invents visual
  scope the user never asked for and risks a regression on a page the user is happy with.
- **(c) Delete** `attachMaskReveals`, `today.css:805-806`, and `motion.css:55`. Cost: violates
  "do not delete any LOC unnecessarily" and destroys a working primitive.

This is surfaced for an explicit decision at spec review rather than resolved silently. If no
redirect is given, (a) is implemented.

Untouched: the statute narrative, ticker, constellation, proof, burst, finale.

### 2b. Add the Amendment Intelligence button to §01 NOTIFY

The §01 NOTIFY panel is `STATUTES[0]` (`today.js:247-258`), inside a five-step ScrollTrigger
narrative where `STATUTES.length` drives the ring mathematics and `initStatutePath`
(`today.js:260-337`) animates `activePanel.children`.

Design:

- `STATUTES[0]` gains `cta: { label: "OPEN AMENDMENT INTELLIGENCE", view: "updates" }`.
- `initStatutePath` appends the button only when `s.cta` exists, wired to
  `LedgerRouter.navigate(s.cta.view)`.
- §02–§05 gain no `cta`, so `STATUTES.length` stays 5 and the ring math is untouched.
- The existing `activePanel.children` reveal animates the new button for free.
- Styling is one new `.statute-path__cta` rule. It borrows the *appearance* of
  `.quiet-beat__btn--primary` (`today.css:547-553`), but it must be **self-contained** — the
  declarations are copied into the new rule, because 2a deletes that class. The new rule must not
  reference the deleted selector.

The panel stays. The five-step narrative stays intact.

---

## Section 3 — Amendment Intelligence tab

### State of the data

Live DB `backend/ifsca_exam.db` (3,293,184 bytes):

- `amendment_updates` = **0 rows**.
- `amendments` = **39 rows** = 15 `SEEDED` + 13 `PACK_SEEDED` (real: titles, dates
  2024-06-04 → 2026-09-30, topics, `new_value`) + **11 `LOCAL_FALLBACK` junk** rows, all titled
  "Manual review required", with summaries that are raw RBI HTML navigation menus or `%PDF-1.6%`
  binary. Sorted `date_desc`, rows 2–12 are junk.

`/api/updates` (`main.py:3029-3053`) returns `{updates, runs, source}` and falls back to
`db.list_curated_amendments` (`source="corpus"`) only when the tracker feed is empty **and** no
category/exam/status filter is set.

Every real row's source resolves: `list_curated_amendments` (`database.py:6137-6177`) maps
`source_url` → `source_urls_json: [row["source_url"]]`, and all 14 distinct `.md` basenames
glob-resolve under `source_documents/md/**`.

Nothing currently serves those documents. `ingest_extracted_pdfs` (`database.py:1802`) reads
`extracted_pdfs/*.txt` only; `amendments` is fed by `seed_critical_amendments`
(`database.py:5172`), `update_tracker.py:287`, `amendment_poller.py:150`, and the manual POST at
`main.py:2543`. No mount exposes the corpus, so a new read-only route is required.

### 3a. Clean the ledger

In `get_updates` (`main.py:3029-3053`), drop rows whose `verification_status == "LOCAL_FALLBACK"`
**after both sources resolve**, so the filter covers the tracker feed and the corpus fallback
alike.

Rows stay in the database — this is a read filter, not a deletion. `/api/updates/status` still
counts them. The eyebrow count becomes honest (28 rather than 39).

### 3b. `GET /api/documents/{name}`

- Accepts a **basename only**, must end in `.md`.
- Any separator, `..`, absolute path, or other extension → **404**.
- Resolved against a dict built by walking allowlisted `source_documents/md/**` — 211 files
  confirmed across 10 bucket directories, with **zero basename collisions** (verified with
  `sort | uniq -d`), so a basename is a safe unique key.
- Returns `{name, bucket, lines, bytes, text}`.
- Largest corpus file is ~4068 lines / ~330KB — acceptable for local serving.

Conformance details added at self-review:

- **Response model is mandatory.** `main.py` declares `response_model=` 35 times, and this
  project has already shipped four frontend bugs caused by a handler returning a key its Pydantic
  model never declared — FastAPI strips it silently. Add `CorpusDocumentModel` to `models.py`
  declaring `name`, `bucket`, `lines`, `bytes`, and `text`.
  The name **cannot** be `DocumentModel`: that already exists at `models.py:96-111` and models
  ingestion *metadata* (`document_id`, `sha256`, `pages`, `status`) for the `documents` table, not
  file content. Verified free of collision.
- **Handler is `def`, not `async def`.** Reading up to 330KB from disk is blocking I/O. FastAPI
  runs sync handlers in a threadpool, so `def` is correct; `async def` would block the event loop.
  This also matches the codebase, which is 121 sync handlers to 8 async.
- **Allowlist logic does not live in the controller.** `main.py` is already 3168 lines, and
  walking the corpus is a filesystem concern, not an HTTP one. Add a small module
  `backend/document_store.py` exposing `resolve(name) -> Path | None` and
  `read_document(name) -> dict | None`, so the handler does only: parse, call, map.
  The index is built lazily and cached at module level, following the existing
  `_INITIALIZED_DB_PATHS` precedent (`database.py:986`). Trade-off disclosed: a newly added `.md`
  file needs a server restart to appear. Rejected alternative: putting these functions in
  `database.py` — wrong module, this is not database access.
- **Uniform 404 is deliberate, not laziness.** Malformed input (`..`, absolute path) could
  reasonably be 400 and only unknown names 404. Returning 404 for both avoids an existence
  oracle: a 400/404 split tells a prober which input shapes are valid and lets them enumerate the
  allowlist. Recorded as ADR-0001.

### 3c. Reader UI

- `api.js` gains `API.document(name)`.
- `loadUpdates` rows (`views.js:491`, running to just before `loadReview` at `567`) gain an
  expandable `old_value → new_value` section and
  a **READ SOURCE** button when `source_urls_json` holds an `.md` basename. External URLs render
  as plain links.
- The reader is an in-view, scrollable, pre-wrap serif panel.
- The three existing action buttons and the empty-state behaviour are unchanged.

Corpus texture worth knowing: no front matter; line 1 is `# <filename> — OCR transcription
(Gemini)`; page markers are `*[Page N of M]*`; dates live in the body in varied formats. The
`03_` bucket holds 22 files, 65–4068 lines, ~3.6KB–~330KB, of which only ~6–8 are genuinely
datable circulars. There are exact duplicate files (`_copy2`, identical md5).
`GIHC_Regulations_2025_Article.md` is third-party commentary and the `md_sebi` files are PYQs.

---

## Section 4 — Mock section: separate phase exams

### The machinery already exists and is never reached

- `backend/knowledge/exam_patterns.json` defines 9 templates with `phase`, `paper`,
  `total_questions`, `marks_per_question`, `time_limit_minutes`, `cutoff_pct`, `sections`,
  `syllabus_units`, plus exam rules (`negative_marking_fraction: 0.25`, `option_count: 5`) and
  `exam_mode_rules`. They are loaded into the live `exam_templates` table — 10 rows confirmed.
- `db.generate_smart_mock(total_questions, mode, use_gemini, template_id)` (`database.py:4701`)
  already honours `template_id` via `_template_allocation` (`4640`), which resolves
  `TEMPLATE_UNIT_TOPICS` (`4620-4637`, only the four `*_P2_GENERAL` keys) and falls back to
  `syllabus_units_json`, then `{}`.
- But `/api/exams/start` (`main.py:1296-1354`) calls it **without** `template_id` and hardcodes
  `"time_limit_seconds": 3600`.
- And `exam.js:61-65` posts `{exam_type, question_count, allocation_mode}` while
  `SmartMockRequestModel` (`models.py:237-241`) declares `{total_questions, mode, use_gemini,
  template}` with extra=ignore. **Zero field overlap.** Every value the user sets in the exam
  form is silently discarded; the endpoint always runs `total_questions=50, mode=default,
  template="CUSTOM"`.

This is a wiring fix, not a feature build. `/api/generate-smart-mock` (`main.py:1238`) and its
alias `/api/mocks/generate` (`1282`) already forward `template_id` correctly and already return
`time_limit_minutes`, `marks_per_question`, `negative_marking_per_wrong`, and `exam_rules`.

### 4a. Backend read path

No `list_exam_templates` db function exists — only `get_exam_template` (`4609`) and
`_template_allocation` (`4640`). Add `db.list_exam_templates()` returning objective templates
only, excluding `IFSCA_PH2_P1_DESC` and `SEBI_PH2_P1_DESC`, whose `total_questions` is NULL
because they are descriptive papers.

New `GET /api/exam-templates` returns
`[{template_id, exam, name, phase, paper, total_questions, marks_per_question,
time_limit_minutes, cutoff_pct}]`, ordered exam → phase → paper, with `CUSTOM` last.

Conformance details added at self-review:

- Add `ExamTemplateModel` to `models.py` (name verified free) and declare it as the endpoint's
  `response_model=list[ExamTemplateModel]`. Without it, FastAPI strips whatever the model omits —
  the exact defect class that already caused four frontend bugs here.
- `phase`, `paper`, `total_questions`, and `cutoff_pct` must be **Optional/nullable** in the
  model. The live rows prove they can be NULL: `SUBJECT_DRILL` and `CUSTOM` have `phase=None` and
  `paper=None`, and the two `*_DESC` templates have `total_questions=None`. A non-nullable field
  would raise a validation error on rows that legitimately exist.
- Handler is `def`, not `async def` — `list_exam_templates()` does blocking sqlite access, same as
  the existing `get_exam_template`.

### 4b. `/api/exams/start` behavioural fix

- Forward `template_id=request.template` into `generate_smart_mock`.
- Replace the hardcoded `3600` with `int((result.get("time_limit_minutes") or 60) * 60)`.

`exam.js:74` already divides seconds by 60, so the clock path needs no change. This alone makes
SEBI Phase 1 Paper 2 run at 40 minutes instead of 60.

### 4c. Exam form

- `index.html` gains a `#exam-paper` select beside `#exam-type`, populated from
  `API.examTemplates()`.
- The Examination select filters Paper options client-side. The request model has no exam field
  and none is being added — `template_id` already encodes exam + phase + paper.
- Choosing a paper seeds the Questions input from `total_questions`.
- `exam.js startExam` posts the model-real names: `{total_questions, mode: "targeting_weighted",
  template}`.

### Disclosed

- Template `marks_per_question` and `cutoff_pct` are **display-only**. Submit scoring
  (`exam_submit`) is untouched and applies neither per-template marks nor negative marking.
  Wiring that is a separate change to the scoring path and is not folded in here.
- The two descriptive templates stay out of the picker; descriptive practice has its own view.
- Gemini spend now scales with the chosen template's question count (SEBI Phase 2 Paper 2 is 100
  questions versus today's fixed 50). The existing `gemini_spend_guard("exams:start")` still
  gates it.

### Untouched

`beginSession`, the palette, the submit flow, `/api/generate-smart-mock` and its alias,
`TEMPLATE_UNIT_TOPICS`, `exam_patterns.json`.

---

## Section 5 — `start.bat`, rewritten from scratch

### Current defects, all verified

The existing 52-line `start.bat` is **non-functional in the worktree**:

1. **Hard-fails at line 19.** `if not exist "backend\.env"` → `exit /b 1`. The worktree has no
   `backend/.env`, only `.env.example`. Double-clicking dies instantly. The main tree has a real
   one.
2. **`.env.example` is stale and actively misleading.** It documents `GEMINI_API_KEY_1..5`; the
   code reads `GEMINI_KEY` and `GEMINI_KEY_1..50` (`gemini_integration.py:137-138`). Following
   the template yields a key-less app with **no startup error** — `gemini_available()` simply
   returns False. It also calls `PORT` a "Flask server port"; this is FastAPI, and `main.py`
   never reads `PORT` at all.
3. **venv existence is used as a dependency-health proxy, and it is wrong.** No `venv` in the
   worktree — the only one is `D:/Exam_preparation/venv`, in the main tree — so line 27 triggers
   a second full install of 11 pinned deps including PyMuPDF and google-genai, while the server
   that actually works runs on system Python 3.12.10 with no venv at all.
4. **Browser opens before uvicorn binds** (line 50 before line 51), so the first launch lands on
   connection-refused. `--host 0.0.0.0` also publishes the DB-writing API to the whole LAN.
5. **Port 8000 hardcoded, two trees, no collision detection.** `DB_PATH = BACKEND_DIR /
   "ifsca_exam.db"` (`database.py:27`) is tree-relative, so launching the wrong tree silently
   reads and writes the wrong database. Nothing today reports which tree was started.

### Global Gemini keys

Per the user's decision — "use the same 9 keys env globally for everything" — there is no
per-tree `.env` copy. The nine keys plus `GEMINI_MODEL`, `GEMINI_MODEL_MOCK`,
`GEMINI_MODEL_ACCURACY`, `GEMINI_THINKING_LEVEL`, `GEMINI_MOCK_THINKING`,
`GEMINI_ACCURACY_THINKING`, and `UPDATE_TRACK_INTERVAL_HOURS` are published as **Windows
user-level environment variables** (`HKCU\Environment`), so the main tree, this worktree, and any
future worktree resolve them identically.

- **Mechanism:** a one-shot Python step using `winreg` that reads the main tree's `backend/.env`
  and writes each entry, then broadcasts `WM_SETTINGCHANGE`. Only key names and value lengths are
  printed — never a value. `setx` is rejected because it would place secrets on the command line
  and in shell history.
- **Precedence is already correct:** `gemini_integration.py:131-132` loads `.env` into
  `os.environ` only if the key is not already set, so global variables win and main-tree
  behaviour is unchanged (identical values).
- **Consequence for `start.bat`:** the `if not exist "backend\.env"` hard-fail must be deleted —
  with global keys there is legitimately no `.env` in the worktree. The semantic `/health` check
  replaces it.
- **Already-running processes will not see the change** until restarted, including the server on
  :8020. Verification therefore requires a fresh launch.
- **Disclosed:** user-level environment variables are readable by every process running as this
  user — slightly broader exposure than a file in the repo directory, though not world-readable.
  Registry-backed, persistent across reboots, reversible by deleting those values.
- `.gitignore:18` covers `backend/.env` and `.gitignore:21` covers `*.db`, so no secret or
  database file can be committed by this work.

### The rewrite

- **Self-locating and tree-loud.** Resolve `%~dp0`, `cd` there, and print the resolved tree path
  plus the DB file it will use, so a wrong-tree launch is visible before it does damage.
- **Real dependency probe.** `python -c "import fastapi, uvicorn, genai, fitz, apscheduler"` —
  test what is actually imported, not whether a folder exists. Only on failure, offer to create
  and populate a venv.
- **Semantic key check.** Do not test file existence. After startup read `GET /health`
  (`main.py:581-599`), which already returns `api_keys_loaded`, `gemini_available`,
  `central_ai_ready`, and `database_initialized`. Print the key count; if zero, name the endpoints
  that will fail (`/api/exams/start`, smart mocks, essay/precis/RC grading) instead of passing
  silently.
- **Readiness gate before the browser.** Launch uvicorn, poll `/health` on a bounded retry loop,
  and only then `start "" http://127.0.0.1:<port>`. On timeout, print the failure and exit
  non-zero.
- **Collision detection.** If the port is already bound, report the owning PID from `netstat` and
  stop, rather than serving a different tree on the same URL.
- **Bind `127.0.0.1`**, not `0.0.0.0`.
- **Port as a parameter.** `start.bat 8020` or a `PORT` environment variable, default 8000.
- **Drop `--reload` from the default path.** It re-runs `lifespan`, which restarts all four
  APScheduler jobs (`main.py:177-217`) and re-seeds the banks on every file edit. Keep it behind
  an explicit dev flag.

Also fixed while in there, because it is the same lie: `.env.example` is corrected to the
`GEMINI_KEY_N` names the code actually reads, the bogus Flask/`PORT` lines are removed, and it is
documented as optional now that global environment variables are the primary path.

Frontend serving is already correct and needs no change: `GET /` returns
`FileResponse(FRONTEND_DIR / "index.html")` (`main.py:573-577`), with `/app`, `/css`, and `/js`
mounts (`250-253`, `3154-3161`).

### Sequencing

This section is implemented and verified **strictly last**, after Sections 1–4 are fixed, tested,
and confirmed running.

---

## Section 6 — Testing and verification

TDD, with a watched RED before each implementation. Tests live in `backend/tests/` against the
existing `test_db` and `client` fixtures (`conftest.py:23-93`) and `sample_amendment`
(`conftest.py:112`). Existing modules: `test_e2e_correctness.py`, `test_e2e_workflows.py`,
`test_phase6_intelligence.py`, `test_regressions.py`, `test_update_tracker.py`.

1. `/api/updates` drops `LOCAL_FALLBACK` rows — seed one real and one junk row, assert only the
   real one is returned; assert the junk row **still exists in the DB** (filtered, not deleted);
   assert `/api/updates/status` still counts it.
2. `GET /api/documents/{name}` traversal table-test — the security-critical case: `..`, absolute
   path, backslash separator, non-`.md` extension, and unknown basename each → 404; happy path
   returns `name`, `bucket`, `lines`, `bytes`, `text`.
3. `db.list_exam_templates()` excludes both `*_DESC` rows (NULL `total_questions`), includes the
   8 objective templates plus `CUSTOM`, ordered exam → phase → paper.
4. `GET /api/exam-templates` shape and ordering.
5. `/api/exams/start` returns `time_limit_seconds == template_minutes * 60` — SEBI_PH1_P2_GENERAL
   must yield 2400, not the hardcoded 3600. Gemini stubbed, since `generate_smart_mock` raises
   without it.
6. `/api/exams/start` no longer silently drops input — `total_questions=20,
   template="SUBJECT_DRILL"` must actually reach `generate_smart_mock`.

**Frontend has no JS test harness**, so verification is a browser-walk via the browser-use MCP
against a freshly started server, with screenshots:

- Home: quiet-beat gone; §01 CTA present and navigates to the updates view.
- Updates: 28 honest rows; old→new expands; READ SOURCE opens real md.
- Exam: Paper dropdown filters by exam, seeds the question count, and the clock shows the
  template's minutes.

**Full `pytest` before and after** — no regression from the current pass count. Known flakes to
respect: never run concurrent load beside the wall-clock perf test, and watch for leaked sqlite
breaking `temp_db` teardown.

**Final gate, in the user's stated order:** all of the above green *and* browser-walked → only
then write `start.bat` → then launch **through** `start.bat` itself and confirm `/health` reports
9 keys and the app loads at the printed URL.

---

## Section 7 — Deliberate deviations from generic guidance

Recorded so a future reader knows these were decisions, not oversights.

- **No `/api/v1/` versioning.** Generic REST guidance says version from day one. This API is
  entirely unversioned (`/api/updates`, `/api/exams/start`, `/api/health`). Introducing a version
  prefix for two new endpoints would split one coherent surface into two conventions. New
  endpoints follow the existing unversioned style.
- **No pagination on `/api/exam-templates`.** Generic guidance says always paginate collections.
  This one returns 9 rows, bounded by a static JSON file. Pagination would be noise. The document
  route returns a single resource, not a collection.
- **No rate limit on `/api/documents/{name}`.** It spends no Gemini tokens, so the existing
  `gemini_spend_guard` does not apply, and after the Section 5 rewrite the server binds to
  `127.0.0.1` only. Revisit immediately if this endpoint is ever exposed beyond loopback.
- **Flat project layout retained.** The FastAPI template guidance recommends
  `app/api/v1/endpoints/`, `schemas/`, `services/`, `repositories/`. This codebase is flat:
  `main.py`, `models.py`, `database.py`. Restructuring a 3168-line controller is out of scope and
  directly opposed to the zero-regression priority. New schemas go in the existing `models.py`;
  the one new module is `document_store.py`, which is the smallest layering step that gets
  filesystem logic out of the controller without a rewrite.
- **`TestClient`, not `httpx.AsyncClient`.** The template guidance's async test fixtures do not
  apply: the new handlers are sync `def`, and the existing suite already uses the sync `client`
  fixture at `conftest.py:86`. Introducing `pytest-asyncio` clients here would add a second test
  idiom for no benefit.
- **No in-memory repository adapters.** Clean Architecture's testability ideal wants use cases
  injectable with in-memory adapters. The existing `test_db` fixture already provides real
  isolation via a temp sqlite file and `db.DB_PATH` reassignment (`conftest.py:23-80`), and the
  suite passes with it. Retrofitting ports-and-adapters onto this codebase is a far larger change
  than this spec covers.

## Section 8 — Architecture Decision Records

Three decisions in this spec are significant enough to warrant ADRs, created alongside it in
`docs/adr/` (directory did not previously exist):

- **ADR-0001** — Serve corpus documents through a basename-allowlisted read-only route with a
  uniform 404. Security architecture.
- **ADR-0002** — Filter `LOCAL_FALLBACK` rows at read time and never delete them. Data integrity
  and auditability.
- **ADR-0003** — Resolve Gemini keys from user-level environment variables rather than per-tree
  `.env` files. Configuration and secret handling.
