# Home Amendment Relocation + Phase Mocks + Tree-Aware start.bat — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the amendment/law content off the home page into a readable Amendment Intelligence tab, make the mock section generate real per-phase exams, and finish with a `start.bat` that actually works in the worktree.

**Architecture:** No new services, tables, or migrations. Two new read-only `GET` endpoints (`/api/exam-templates`, `/api/documents/{name}`), one behavioural fix to `/api/exams/start`, one read-time filter inside `get_updates`, one new filesystem module `backend/document_store.py`, and frontend edits confined to five existing files. Gemini keys move to Windows user-level environment variables so every tree resolves them identically.

**Tech Stack:** FastAPI 0.115.0, Pydantic 2.13.4, Starlette 0.38.6, uvicorn 0.32.0, sqlite3, pytest 9.1.1, httpx 0.28.1 `TestClient`. Frontend is hand-rolled ES5-style vanilla JS in IIFEs plus GSAP/ScrollTrigger — no build step and no JS test harness.

**Working tree:** every path below is relative to `D:\Exam_preparation\.worktrees\ledger-award-pass`. Branch `feature/ledger-award-pass`, PR #5. The main tree at `D:\Exam_preparation` stays dirty by design. **No local merges. Never `--amend`. Stage by explicit path. Never print the git origin URL unredacted. Do not touch the leaked PAT.**

**Commit identity:** the repo has no git identity configured, so every commit in this plan uses the inline form:

```bash
git -c user.name="Kartik Tomar" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "..."
```

**Source spec:** `docs/superpowers/specs/2026-09-03-home-amendment-relocation-phase-mocks-design.md` (approved). ADRs: `docs/adr/0001-corpus-document-route-basename-allowlist.md`, `0002-filter-local-fallback-at-read-time.md`, `0003-gemini-keys-as-user-environment-variables.md`.

---

## Verified facts this plan depends on

Every one of these was established empirically against the installed stack during the max-depth check, not assumed. Several contradict the approved spec. Do not re-derive them; do not design around them either.

| # | Fact | How it was verified |
|---|---|---|
| **F1** | `response_model` **silently strips** keys the model does not declare, returning HTTP 200. | `TestClient` against `response_model=list[Loose]` returned `[{'template_id': 'SUBJECT_DRILL'}]`; the `undeclared` key vanished with no error. |
| **F2** | `response_model` **raises HTTP 500** when a non-nullable field receives `None`. | `response_model=list[Strict]` with `phase: int` and `phase=None` in the payload → `500 Internal Server Error`. |
| **F3** | A Starlette `{name}` convertor matches `[^/]+`. Percent-encoded `%2F` and `%2e%2e%2f` probes **404 at the router** and never reach the handler. | Probe run: `..%2F..%2Fbackend%2Fifsca_exam.db` → 404 with the handler not entered. Starlette docs: "By default, parameters capture characters until the end of the path or the next slash." |
| **F4** | **Backslash and drive-absolute values reach the handler intact.** `..\..\secret.md` → 200 with `name='..\\..\\secret.md'`; `C:%5CWindows%5Cwin.ini` → 200 with `name='C:\\Windows\\win.ini'`. | Probe run against a live route declaring only `/api/documents/{name}`. |
| **F5** | On Windows, `CORPUS_ROOT / name` **escapes the corpus** for those values. `root / '..\..\backend\ifsca_exam.db'` resolves to the real database (`exists=True`, `inside_corpus=False`). `root / 'C:\Windows\win.ini'` → `C:\Windows\win.ini`, because **pathlib discards the left operand entirely when the right side carries a drive**. | `pathlib` resolution run printing joined path, resolved path, `exists()`, and an `inside_corpus` prefix test. |
| **F6** | A NUL byte reaches the handler and `read_text()` raises `ValueError: embedded null character` → **HTTP 500, not 404**. | `Path('x\x00.md').read_text()` raised `ValueError`. |
| **F7** | **`TestClient`/httpx normalizes `../` away before the request is sent.** `client.get("/api/documents/../secret.md")` returns 404 *because the URL became `/api/secret.md`*, not because any handler rejected it. A traversal test written that way is **vacuous**. | Probe run against an app whose only routes were `/api/documents` and `/api/documents/{name}`: both `/api/documents/../secret.md` and `/api/documents/a/../../b.md` returned 404. |
| **F8** | Corpus `.md` files live in **bucket subdirectories**, not at `source_documents/md/`. `root / 'IFSCA_Compliance_Handbook.md'` → `exists=False`; the real path is `03_IFSCA_Act_Regulations_Handbooks_Circulars/IFSCA_Compliance_Handbook.md`. So the walking allowlist is required for the **happy path**, not only for security. | `pathlib` resolution run plus `find`. |
| **F9** | `source_documents/md/**` holds **211 `.md` files across 10 buckets** with **zero basename collisions**. | `find . -name "*.md" | wc -l` → 211; `sort | uniq -d` → empty. Buckets: `01_Previous_Year_Papers`, `02_Recruitment_Notifications_Handouts_Results`, `03_IFSCA_Act_Regulations_Handbooks_Circulars`, `04_IFSCA_Annual_Reports`, `05_IFSCA_Bulletins`, `06_IFSCA_Reports_Consultations_Brochures`, `07_ICSI_Study_Material`, `08_Consulting_Firm_Reports`, `09_Exam_Study_Material_Current_Affairs`, `10_Unrelated_RRB_Documents`. |
| **F10** | `exam_templates` **does not exist** in the `test_db` fixture's database, and is **empty** even after `db.init_db()`. The table is created by `migrations/005_knowledge_layer.sql:88` and seeded only by `db.bootstrap_from_knowledge()` (`database.py:1473`, template insert loop at `1529-1533`), which the fixture never calls. | Reproduced the fixture's setup steps verbatim: `sqlite3.OperationalError: no such table: exam_templates`, then `exam_templates: 0` after `init_db()`. |
| **F11** | `SmartMockRequestModel.mode` is `Literal["balanced", "weakness-heavy", "amendment-heavy", "pyq-like"]` (`models.py:239`). **`"targeting_weighted"` is not a valid value and would 422.** The spec's §4c is wrong. | `models.py:237-241` read. |
| **F12** | `SmartMockRequestModel.total_questions` is `Field(default=50, ge=5, le=100)` (`models.py:238`) but `#exam-count` is `min="10" max="200"` (`index.html:204`). **Any value above 100 would 422.** | Both files read. |
| **F13** | `router.js:102-107` installs a **delegated click activator for any `[data-view]` element**, calling `navigate(el.dataset.view)`. `updates` is a valid route (`router.js:7`: `["today","exam","pyq","descriptive","tracker","updates","review","results"]`). A CTA therefore needs **no new JS click handler**. | `router.js` read. |
| **F14** | **No route shadowing** for either new endpoint. `/api/documents` (`main.py:734`, exact match, GET) is disjoint from `/api/documents/{name}`; `/api/exam-templates` is a distinct prefix from `/api/exams/...`. The `{exam_id}` routes all carry a suffix segment. | Full grep of the `/api/document*`, `/api/exam*`, `/api/updates*` route table. |
| **F15** | `gemini_spend_guard` (`main.py:549-570`) is an **idempotency** guard only. It does not require Gemini keys, so it will not make the `/api/exams/start` tests fail for an environmental reason. | Read of the guard body: it calls `_begin_spend_guard`/`_end_spend_guard` and raises 409 on a duplicate in-flight key. Nothing else. |
| **F16** | Live `backend/ifsca_exam.db`: `amendments` = 39 rows = **11 `LOCAL_FALLBACK`** + 13 `PACK_SEEDED` + 15 `SEEDED`. `amendment_updates` = 0 rows. `source_url` holds either a bare `.md` basename (14 distinct) or an `https://` URL (the rest are `rbi.org.in`). All 11 junk rows are titled `Manual review required`; their `new_value` is raw RBI HTML nav or `%PDF-1.6%` binary. Filtering gives an honest **28**. | Grouped SQL against the live DB, plus a `GROUP BY source_url` listing. |
| **F17** | `PROJECT_ROOT = PathLib(__file__).resolve().parents[1]` already exists at `main.py:103`. **`main.py:19` imports `Path` from fastapi**, and `pathlib.Path` as `PathLib`. So `Path(...)` in a handler signature is the FastAPI parameter decorator, not a filesystem path. | Read. |
| **F18** | `views.js` defines **only `qs` (line 10) and `qsa` (line 11)** — there is **no `el()` helper**, unlike `today.js`. Any new element in `views.js` must use `document.createElement`. `exam.js` **does** define `esc()` at line 16; `views.js` defines `esc()` at line 16. | Grep of both files. |
| **F19** | **Not freshly verified:** the claim that uvicorn `--reload` re-runs `lifespan` (and so restarts the four APScheduler jobs and re-seeds the banks on every file edit) is carried from project memory `ledger-deployment-hazard`. context7's uvicorn entry redirected (`/encode/uvicorn` → `/kludex/uvicorn`) and returned no content. Task 16 does not depend on this being true — it keeps `--reload` behind an explicit dev flag either way. | context7 query returned only a redirect notice. |

### Spec corrections this plan applies

The approved spec is authoritative on **intent**. Five of its details are wrong against the code and are corrected here. Each correction is flagged again at the task that implements it.

1. **§4c posts `mode: "targeting_weighted"`** → replaced with `"balanced"` (**F11**). The spec's value is not in the model's `Literal`, so it would 422 on *every* exam start — the exact class of silent contract break this plan exists to remove.
2. **§4c leaves `#exam-count max="200"`** → changed to `min="5" max="100" step="5"` (**F12**), matching `Field(ge=5, le=100)`.
3. **§3b "Any separator, `..`, absolute path → 404"** → made concrete and Windows-specific: `\`, `/`, `..`, a drive letter, and NUL are each named and rejected, because on Windows only the backslash and drive forms actually reach the handler (**F4**, **F5**, **F6**).
4. **§6 test 3 "includes the 8 objective templates plus `CUSTOM`"** → the arithmetic is wrong. After excluding the two `*_DESC` rows there are **8 total *including* `CUSTOM`** (IFSCA 3 + SEBI 3 + `SUBJECT_DRILL` + `CUSTOM`). Tests assert an explicit ID set rather than a count, and **seed their own rows** because the table is empty under the fixture (**F10**).
5. **§3c implies `views.js` can reuse the `el()` helper** → it cannot (**F18**). The reader uses `document.createElement`.

### One design improvement over the spec

The spec's §2b wired the CTA through `LedgerRouter.navigate(s.cta.view)`. **F13** shows the router already delegates on `[data-view]`, so the button needs only the attribute. This adds no new event listener, no new closure over panel state, and no new failure mode if the router loads after `today.js`. The `cta.view` value still drives it, so the data shape the spec describes is preserved.

---

## File structure

**Create:**

| File | Responsibility |
|---|---|
| `backend/document_store.py` | Walk `source_documents/md/**` once into a cached `{basename: Path}` allowlist; expose `resolve(name)` and `read_document(name)`. All filesystem and path-safety logic lives here, never in the controller. |
| `backend/tests/test_amendment_relocation.py` | The `LOCAL_FALLBACK` read filter, the document store unit tests (including the real traversal defence), and the document route's endpoint tests. |
| `backend/tests/test_phase_exam_templates.py` | `list_exam_templates`, `/api/exam-templates`, and the `/api/exams/start` template + time-limit fix. |

**Modify:**

| File | Change |
|---|---|
| `backend/main.py` | Filter `LOCAL_FALLBACK` in `get_updates` (3029-3053); add `/api/documents/{name}` after line 736; add `/api/exam-templates` before line 1296; forward `template_id` and the real `time_limit_seconds` in `exam_start`; extend the `from models import (...)` block (57-100) and the local-import block (24-36). |
| `backend/database.py` | Add `list_exam_templates()` after `get_exam_template` (ends line 4617). |
| `backend/models.py` | Append `CorpusDocumentModel` and `ExamTemplateModel` after `ExamAggregateResponseModel` (file ends line 576). |
| `backend/.env.example` | Correct to the variable names the code actually reads; document global env vars as the primary path. |
| `frontend/index.html` | Delete the quiet-beat block (152-162); add `#exam-paper`; realign `#exam-count` bounds (193-207). |
| `frontend/js/today.js` | Add `cta` to `STATUTES[0]` (247-258); render it in `initStatutePath` (264-271); delete `renderQuietBeat` (405-449) and its call site (786-787). |
| `frontend/js/views.js` | Add `openDocumentReader`; expandable old→new detail, READ SOURCE, and delegated handlers inside `loadUpdates` (491-564). |
| `frontend/js/exam.js` | Load templates, populate `#exam-paper`, seed the count, post model-real field names (42-83). |
| `frontend/js/api.js` | Add `document(name)` and `examTemplates()`. |
| `frontend/css/today.css` | Add `.statute-path__cta` after line 431; delete quiet-beat rules at 475-555, 684-686, 808-822. |
| `frontend/css/views.css` | Add amendment-detail and corpus-reader rules after line 330. |
| `frontend/css/motion.css` | Delete the two quiet-beat motion rules (56, 63). |
| `start.bat` | Full rewrite — **Task 16, strictly last.** |

**Deliberately not touched:** `beginSession`, the exam palette, the submit flow, `exam_submit` scoring, `/api/generate-smart-mock` and its alias `/api/mocks/generate`, `TEMPLATE_UNIT_TOPICS`, `_template_allocation`, `backend/knowledge/exam_patterns.json`, `attachMaskReveals`, the `.mask-reveal` CSS utility, the finale stamp button, the `API.lawDaily()` fetch, `list_curated_amendments`, and the `amendments` table contents.

---

## Task 1: Record the regression baseline

Everything after this is judged against these numbers. Without them, "no regression" is an unfalsifiable claim.

**Files:** none — read-only.

- [ ] **Step 1: Confirm the tree is clean and on the right branch**

Run:
```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass" && git status --short && git rev-parse --abbrev-ref HEAD
```
Expected: no output from `git status --short`, then `feature/ledger-award-pass`.

If the tree is **not** clean, stop and investigate before editing anything. Do not `git checkout --`, `git restore`, or `git clean` to make it clean — it may be someone else's in-progress work. This repo has had concurrent automations trigger rebase operations; if you find a rebase or merge in progress, abort your own work and surface it rather than pushing through.

- [ ] **Step 2: Confirm there is no stale lock or stash you are about to collide with**

Run:
```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass" && git stash list && ls .git 2>/dev/null | head -3; git rev-parse --git-dir
```
Expected: an empty stash list. Note whatever the stash list contains — Task 2 Step 5 uses `git stash push`/`pop` and you must be able to prove afterwards that only your own entry was consumed.

- [ ] **Step 3: Run the full suite and record the pass count**

Run:
```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -m pytest tests -q 2>&1 | tail -20
```
Expected: a summary line of the form `N passed in Xs`, possibly with skips.
**The baseline measured during plan authoring was `134 passed in 71.82s`** (134
collected, 0 failed, 0 errors, on a clean `feature/ledger-award-pass` at
`ba8783b1`). Write down the `N` *you* observe. If it is not 134, the tree you are
running in differs from the one this plan was written against — reconcile that
before writing a single line of feature code, because Task 8 compares the final
total against your number, not against 134. The suite takes roughly 70-80
seconds; do not shorten it with `-x` or `-k`.

Known flakes to respect, from project memory `ledger-test-env-gotchas`:
- Never run anything else concurrently beside the wall-clock performance test.
- A leaked sqlite handle can break `temp_db` teardown on Windows. If a run fails *only* in teardown, re-run once before believing it.
- Console output is cp1252; a Unicode assertion message can itself raise.

- [ ] **Step 4: Confirm `main.py` imports cleanly**

Run:
```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -c "import main; print('import main OK')"
```
Expected: `import main OK`, no traceback.

- [ ] **Step 5: Syntax-check the five frontend JS files you are about to edit**

Run:
```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/frontend/js" && for f in api.js exam.js today.js views.js router.js; do node --check "$f" && echo "OK $f"; done
```
Expected: five `OK <file>` lines. This is the frontend's only automated gate — there is no JS test harness, so Task 15's browser-walk carries the behavioural weight.

No commit; nothing changed.

---

## Task 2: Filter `LOCAL_FALLBACK` rows out of `/api/updates`

**Spec part 3a.** The ledger currently shows 11 junk rows titled `Manual review required` whose summaries are raw RBI HTML navigation menus and `%PDF-1.6%` binary (**F16**). This is a **read filter, not a deletion** — the rows stay in the database (ADR-0002).

**Files:**
- Create: `backend/tests/test_amendment_relocation.py`
- Modify: `backend/main.py:3029-3053` (`get_updates`)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_amendment_relocation.py`:

```python
"""Amendment relocation: the read-time ledger filter and corpus document serving.

The test_db fixture (conftest.py:23-80) points db.DB_PATH at a temp file but does
not run migration 005 or bootstrap_from_knowledge(), so the amendments table is
created empty by whichever handler calls init_db() first (F10). Rows are inserted
explicitly here rather than assumed to exist.
"""

from __future__ import annotations

import sqlite3

import database as db


def _insert_amendment(
    amendment_id: str,
    rule_name: str,
    new_value: str,
    verify_status: str,
    source_url: str | None = None,
    old_value: str | None = None,
    effective_date: str = "2026-01-15",
) -> None:
    db.init_db()
    conn = sqlite3.connect(db.DB_PATH)
    try:
        conn.execute(
            """
            INSERT INTO amendments
            (amendment_id, topic, rule_name, effective_date, old_value,
             new_value, source_url, verify_status, priority, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                amendment_id, "PH2_IFSCA_ACT", rule_name, effective_date, old_value,
                new_value, source_url, verify_status, "HIGH", "2026-01-15T00:00:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()


def test_updates_drops_local_fallback_but_keeps_real_rows(client):
    _insert_amendment(
        "amd_real", "IFSCA (Capital Markets) Regulations",
        "Registration fee reduced to USD 5,000", "PACK_SEEDED",
        source_url="IFSCA_Fee_Circular_08Apr2025.md",
        old_value="USD 25,000",
    )
    _insert_amendment(
        "amd_junk", "Manual review required",
        "%PDF-1.6%\nHome | About Us | Notifications", "LOCAL_FALLBACK",
        source_url="https://www.rbi.org.in/CommonMan/English/Scripts/Notification.aspx?Id=3315",
    )

    resp = client.get("/api/updates?sort=date_desc&limit=60")
    assert resp.status_code == 200
    body = resp.json()
    titles = [u["title"] for u in body["updates"]]

    assert "IFSCA (Capital Markets) Regulations" in titles
    assert "Manual review required" not in titles


def test_local_fallback_filter_is_read_only_not_a_delete(client):
    """ADR-0002: the row stays in the database and still counts toward status.

    This test passes both before and after the filter exists -- it is the guard
    against someone 'fixing' the ledger by deleting rows instead of hiding them.
    """
    _insert_amendment(
        "amd_junk_2", "Manual review required", "%PDF-1.6%", "LOCAL_FALLBACK",
    )

    client.get("/api/updates?sort=date_desc&limit=60")

    conn = sqlite3.connect(db.DB_PATH)
    try:
        still_there = conn.execute(
            "SELECT COUNT(*) FROM amendments WHERE amendment_id = 'amd_junk_2'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert still_there == 1

    status = client.get("/api/updates/status")
    assert status.status_code == 200


def test_local_fallback_filter_also_applies_to_the_tracker_feed(client):
    """The filter must sit AFTER both sources resolve, so a tracker-written
    LOCAL_FALLBACK row is dropped too -- not just corpus-fallback ones."""
    db.init_db()
    conn = sqlite3.connect(db.DB_PATH)
    try:
        conn.execute(
            """
            INSERT INTO amendment_updates
            (update_id, title, summary, verification_status, discovered_at,
             category, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "upd_junk", "Manual review required", "%PDF-1.6%",
                "LOCAL_FALLBACK", "2026-02-01T00:00:00", "AMENDMENT", "ACTIVE",
            ),
        )
        conn.execute(
            """
            INSERT INTO amendment_updates
            (update_id, title, summary, verification_status, discovered_at,
             category, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "upd_real", "IFSCA Bullion Circular", "New storage norms",
                "VERIFIED", "2026-02-02T00:00:00", "AMENDMENT", "ACTIVE",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    resp = client.get("/api/updates?sort=date_desc&limit=60")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "tracker"
    titles = [u["title"] for u in body["updates"]]
    assert "IFSCA Bullion Circular" in titles
    assert "Manual review required" not in titles
```

- [ ] **Step 2: Run the tests and watch them FAIL**

Run:
```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -m pytest tests/test_amendment_relocation.py -q 2>&1 | tail -30
```
Expected: **1 passed, 2 failed**.
- `test_local_fallback_filter_is_read_only_not_a_delete` **passes already** — it asserts the row survives, which is true before any filter exists. That is intentional; it is the guard described in its docstring.
- The other two fail with `AssertionError: assert 'Manual review required' not in [...]`.

If instead you get a collection error such as `no such table: amendment_updates`, the third test's column list does not match the live schema. Inspect it before changing anything:
```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -c "
import re, pathlib
sql = pathlib.Path('migrations/006_update_tracker.sql').read_text(encoding='utf-8')
m = re.search(r'CREATE TABLE IF NOT EXISTS amendment_updates\s*\((.*?)\n\s*\);', sql, re.S)
print(m.group(0) if m else 'not in 006; check database.py SCHEMA')
"
```
Correct the INSERT column list to match. **Do not weaken the assertion** to make it pass.

- [ ] **Step 3: Implement the filter**

In `backend/main.py`, `get_updates` currently reads (lines 3029-3053):

```python
@app.get("/api/updates")
def get_updates(
    sort: str = Query("date_desc", pattern="^(date_desc|date_asc|priority|category)$"),
    category: str | None = Query(None),
    exam: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """List amendment updates with sorting/filtering + recent tracker runs."""
    try:
        updates = db.list_amendment_updates(
            sort=sort, category=category, exam=exam, status=status, limit=limit,
        )
        source = "tracker"
        # amendment_updates is written only by the tracker. When it has discovered
        # nothing the curated corpus still holds real verified amendments, but that
        # ledger has no exam/category/status columns to narrow by, so a filtered
        # request must not silently widen into unfiltered corpus rows.
        if not updates and not (category or exam or status):
            updates = db.list_curated_amendments(sort=sort, limit=limit)
            source = "corpus"
        runs = db.get_tracker_runs(limit=5)
        return {"updates": updates, "runs": runs, "source": source}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
```

Insert the filter **between the corpus fallback and the `runs = ...` line**. The tail of the `try` block becomes:

```python
        if not updates and not (category or exam or status):
            updates = db.list_curated_amendments(sort=sort, limit=limit)
            source = "corpus"
        # LOCAL_FALLBACK is what extract_amendment_structured returns when Gemini
        # cannot parse a page (gemini_integration.py:1372-1382): rule_name is the
        # literal string "Manual review required" and new_value is the first 500
        # characters of raw HTML or PDF binary. The rows stay in the table for
        # audit (ADR-0002) but are never shown. Applied after both sources
        # resolve, so the tracker feed is filtered too, not just the corpus.
        updates = [
            u for u in updates
            if (u.get("verification_status") or "").upper() != "LOCAL_FALLBACK"
        ]
        runs = db.get_tracker_runs(limit=5)
        return {"updates": updates, "runs": runs, "source": source}
```

Change nothing else in the handler. In particular:

- **Do not** reassign `source` when the filter empties the list. An empty *filtered* tracker feed must not fall through to the corpus, because that would resurrect the junk rows through the other door.
- **Do not** move the filter above the corpus fallback. Placing it before both sources resolve means it only ever sees the tracker feed, and the corpus rows — which are where all 11 junk rows actually live (**F16**) — would sail straight through.
- `u.get(...)` rather than `u[...]` because both sources return plain dicts, and a tracker row missing the column must not turn a listing endpoint into a 500.

- [ ] **Step 4: Run the tests and watch them PASS**

Run:
```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -m pytest tests/test_amendment_relocation.py -q 2>&1 | tail -20
```
Expected: `3 passed`.

- [ ] **Step 5: Prove the RED was real**

Revert the filter, confirm the two tests fail again, then restore it. Skipping this means the test may never have exercised the new code — the classic regression test that does not test the regression.

First, record the current stash state so you can prove afterwards that only your own entry was touched:
```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass" && git stash list
```

Then stash **only** `main.py`:
```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass" && git stash push -- backend/main.py && cd backend && python -m pytest tests/test_amendment_relocation.py -q 2>&1 | tail -5
```
Expected: `1 passed, 2 failed`.

Restore:
```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass" && git stash pop && git stash list
```
Expected: the pop succeeds, and `git stash list` shows exactly what Step 5's first command showed (empty, if it started empty).

Then re-run Step 4 and confirm `3 passed`.

**Stash safety:** this repo has had concurrent automations trigger rebase operations. Use `git stash push -- <path>` (scoped) and `git stash pop` — never a bare `git stash` that sweeps unrelated work, and never `git checkout --` as a shortcut. If `pop` reports a conflict, stop and resolve it properly; do not discard either side.

- [ ] **Step 6: Verify against the live database, not just the fixture**

The fixture proves the logic; this proves it works on the real 39 rows (**F16**). It spends no Gemini tokens.

Run:
```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -c "
from fastapi.testclient import TestClient
import main
c = TestClient(main.app)
r = c.get('/api/updates?sort=date_desc&limit=60')
body = r.json()
rows = body['updates']
print('status      :', r.status_code)
print('source      :', body['source'])
print('rows        :', len(rows))
print('junk visible:', sum(1 for x in rows if x['title'] == 'Manual review required'))
print('pdf visible :', sum(1 for x in rows if '%PDF' in (x.get('summary') or '')))
"
```
Expected:
```
status      : 200
source      : corpus
rows        : 28
junk visible: 0
pdf visible : 0
```

If `rows` is 39 or `junk visible` is non-zero, you edited the **main tree's** `main.py` rather than the worktree's. Check `git rev-parse --show-toplevel` before continuing.

- [ ] **Step 7: Commit**

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass" && git add backend/main.py backend/tests/test_amendment_relocation.py && git -c user.name="Kartik Tomar" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "$(cat <<'EOF'
fix(updates): hide LOCAL_FALLBACK extraction stubs from the amendment ledger

Read-time filter only; the rows stay in the table for audit (ADR-0002). Applied
after both the tracker feed and the corpus fallback resolve, so neither door can
resurface rows whose title is the literal "Manual review required" and whose
summary is raw HTML or PDF binary. Live ledger goes from 39 rows to an honest 28.
EOF
)"
```

---

## Task 3: `backend/document_store.py` — the corpus allowlist

**Spec part 3b, first half.** All path-safety logic lives here, not in the controller. `main.py` is already 3168 lines, and walking a corpus is a filesystem concern, not an HTTP one (ADR-0001).

**Files:**
- Create: `backend/document_store.py`
- Modify: `backend/tests/test_amendment_relocation.py` (append)

- [ ] **Step 1: Write the failing unit tests**

These test the module **directly**, not through HTTP. That is deliberate and load-bearing: **F7** proved `TestClient`/httpx normalizes `../` away before the request is sent, so an HTTP-only traversal test passes vacuously and proves nothing about the defence. **F4** proved the backslash and drive-absolute forms *do* reach the handler — those are the ones that matter, and they are only honestly testable at module level.

Append to `backend/tests/test_amendment_relocation.py`:

```python
import document_store

BACKSLASH = chr(92)
NUL = chr(0)


def test_resolve_finds_a_corpus_file_by_basename_across_buckets():
    """F8: corpus files live in bucket subdirectories, not at the md root, so a
    flat-root join would not find them. The walk is required for the happy path,
    not only for security."""
    hits = list(document_store.CORPUS_ROOT.rglob("IFSCA_Compliance_Handbook.md"))
    assert hits, "corpus fixture missing; cannot test resolve()"

    found = document_store.resolve("IFSCA_Compliance_Handbook.md")
    assert found is not None
    assert found.name == "IFSCA_Compliance_Handbook.md"
    assert found.parent != document_store.CORPUS_ROOT, "expected a bucket subdir, not the md root"


def test_index_covers_the_whole_corpus_with_no_collisions():
    """F9: 211 files across 10 buckets, zero basename collisions. If a collision
    is ever introduced this asserts on it rather than silently serving one of the
    two files depending on walk order."""
    index = document_store.index()
    assert len(index) > 100, f"only {len(index)} documents indexed"
    names = [p.name for p in index.values()]
    assert len(names) == len(set(names)), "basename collision in the corpus index"


def test_resolve_returns_none_for_every_traversal_form():
    """F4/F5: on Windows, backslash and drive-absolute names reach the handler
    intact, and pathlib would resolve them outside the corpus. root/'..\\..\\
    backend\\ifsca_exam.db' -> the real database; root/'C:\\Windows\\win.ini' ->
    C:\\Windows\\win.ini, because pathlib discards the left operand for a drive."""
    malicious = [
        ".." + BACKSLASH + ".." + BACKSLASH + "backend" + BACKSLASH + "ifsca_exam.db",
        "C:" + BACKSLASH + "Windows" + BACKSLASH + "win.ini",
        "c:" + BACKSLASH + "windows" + BACKSLASH + "system.ini",
        BACKSLASH + BACKSLASH + "localhost" + BACKSLASH + "share" + BACKSLASH + "x.md",
        "../backend/ifsca_exam.db",
        "..",
        ".",
        "",
        "05_IFSCA_Bulletins" + BACKSLASH + "IFSCA_Compliance_Handbook.md",
        "05_IFSCA_Bulletins/IFSCA_Compliance_Handbook.md",
        "no_such_file.md",
        "IFSCA_Compliance_Handbook.txt",
        "IFSCA_Compliance_Handbook",
        "IFSCA_Compliance_Handbook.md.",
        "IFSCA_Compliance_Handbook.md" + BACKSLASH,
    ]
    for name in malicious:
        assert document_store.resolve(name) is None, f"resolve() accepted {name!r}"


def test_resolve_rejects_a_nul_byte_instead_of_letting_open_raise():
    """F6: read_text() on a NUL-containing path raises ValueError, which would
    surface as a 500 and break ADR-0001's uniform-404 promise."""
    assert document_store.resolve("IFSCA_Compliance_Handbook.md" + NUL) is None
    assert document_store.read_document("IFSCA_Compliance_Handbook.md" + NUL) is None


def test_read_document_returns_name_bucket_lines_bytes_text():
    doc = document_store.read_document("IFSCA_Compliance_Handbook.md")
    assert doc is not None
    assert doc["name"] == "IFSCA_Compliance_Handbook.md"
    assert doc["bucket"]
    assert doc["bucket"] != "md", "bucket should be the numbered subdirectory"
    assert doc["lines"] > 0
    assert doc["bytes"] > 0
    assert doc["text"]
    assert doc["bytes"] == len(doc["text"].encode("utf-8"))
    assert doc["lines"] == doc["text"].count("\n") + (0 if doc["text"].endswith("\n") else 1)


def test_read_document_returns_none_for_unknown_names():
    assert document_store.read_document("definitely_not_in_the_corpus.md") is None
    assert document_store.read_document("") is None


def test_read_document_never_returns_a_path_outside_the_corpus():
    """Belt and braces over F5: whatever resolve() hands back must still sit under
    CORPUS_ROOT after resolution, so a symlink or a future refactor that starts
    joining user input cannot silently become an arbitrary file read."""
    for name in [
        ".." + BACKSLASH + ".." + BACKSLASH + "backend" + BACKSLASH + ".env.example",
        "C:" + BACKSLASH + "Windows" + BACKSLASH + "win.ini",
        ".." + BACKSLASH + ".." + BACKSLASH + "start.bat",
    ]:
        assert document_store.read_document(name) is None, f"read_document() served {name!r}"


def test_is_safe_basename_is_the_explicit_gate():
    """The allowlist alone already defeats every probe above, because none of them
    is a key in it. This test pins the explicit gate so it cannot be removed as
    'redundant' by a future reader who has not re-derived F4/F5/F6."""
    assert document_store._is_safe_basename("IFSCA_Compliance_Handbook.md") is True
    assert document_store._is_safe_basename("x.txt") is False
    assert document_store._is_safe_basename("a" + BACKSLASH + "b.md") is False
    assert document_store._is_safe_basename("a/b.md") is False
    assert document_store._is_safe_basename("..") is False
    assert document_store._is_safe_basename("") is False
    assert document_store._is_safe_basename("C:x.md") is False
    assert document_store._is_safe_basename("x" + NUL + ".md") is False
```

- [ ] **Step 2: Run them and watch them FAIL**

Run:
```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -m pytest tests/test_amendment_relocation.py -q 2>&1 | tail -15
```
Expected: a **collection error** — `ModuleNotFoundError: No module named 'document_store'`. That is the correct RED for a module that does not exist yet; no test can run at all.

- [ ] **Step 3: Create `backend/document_store.py`**

```python
"""Read-only access to the markdown corpus under source_documents/md.

Serves the READ SOURCE action in the Amendment Intelligence view, so a row in the
amendment ledger can be checked against the document it was extracted from.

Security model (ADR-0001): a request supplies a *basename only*, and that
basename is looked up in an allowlist built by walking the corpus. A path is
never constructed from user input, so there is no traversal surface to get wrong.

On Windows this matters considerably more than it looks. Starlette's {name}
convertor matches [^/]+, so a forward-slash traversal 404s at the router and
never arrives here -- but a backslash value and a drive-absolute value both reach
the handler completely intact, and pathlib then resolves them outside the corpus:

    CORPUS_ROOT / '..\\..\\backend\\ifsca_exam.db'  -> the real database, exists
    CORPUS_ROOT / 'C:\\Windows\\win.ini'            -> C:\\Windows\\win.ini, exists

The second is not a partial escape. pathlib discards the left operand entirely
when the right side carries a drive, so the corpus root stops being involved at
all. A NUL byte is a third, separate hazard: read_text() on one raises
ValueError, which would surface as a 500 rather than the uniform 404 this module
promises, and the 400/500 split would itself become an existence oracle.

Note also that the corpus files are not at the md root -- they sit in ten
numbered bucket subdirectories -- so the walk is required to find a legitimate
document at all, not merely to reject a malicious one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
CORPUS_ROOT = PROJECT_ROOT / "source_documents" / "md"

# basename -> absolute Path. Built once on first use, following the
# _INITIALIZED_DB_PATHS lazy-cache precedent at database.py:986.
# Trade-off, disclosed: a newly added .md file needs a server restart to appear.
_INDEX: dict[str, Path] | None = None


def _is_safe_basename(name: str) -> bool:
    """Reject anything that is not a plain filename before it is ever looked up.

    Defence in depth. The allowlist alone already defeats every form below,
    because none of them is a key in it. This explicit gate exists so the intent
    stays legible at the boundary and so a future refactor that starts joining
    user input to CORPUS_ROOT cannot silently become an arbitrary file read.
    """
    if not name or "\x00" in name:
        return False
    if not name.endswith(".md"):
        return False
    if "/" in name or "\\" in name:
        return False
    if name in (".", ".."):
        return False
    # A drive letter ("C:x.md") or a UNC prefix makes pathlib discard the left
    # operand of a join. Path.is_absolute() is unreliable for a bare drive on
    # some inputs, so check the shape directly.
    if len(name) >= 2 and name[1] == ":":
        return False
    return True


def _build_index() -> dict[str, Path]:
    if not CORPUS_ROOT.is_dir():
        return {}
    index: dict[str, Path] = {}
    for path in CORPUS_ROOT.rglob("*.md"):
        if not path.is_file():
            continue
        # 211 files across 10 buckets with zero basename collisions, so a
        # basename is a safe unique key. First match wins if that ever changes,
        # which keeps behaviour deterministic rather than walk-order dependent.
        index.setdefault(path.name, path)
    return index


def index() -> dict[str, Path]:
    """The cached basename -> absolute-path allowlist."""
    global _INDEX
    if _INDEX is None:
        _INDEX = _build_index()
    return _INDEX


def resolve(name: str) -> Path | None:
    """Absolute path for an allowlisted corpus basename, else None."""
    if not _is_safe_basename(name):
        return None
    path = index().get(name)
    if path is None:
        return None
    # Belt and braces: whatever the walk produced must still sit under the corpus
    # once symlinks are resolved. relative_to raises ValueError when it does not.
    try:
        resolved = path.resolve()
        resolved.relative_to(CORPUS_ROOT.resolve())
    except (OSError, ValueError):
        return None
    return resolved


def read_document(name: str) -> dict[str, Any] | None:
    """Corpus document content, or None for anything not allowlisted.

    errors="replace" because these are OCR transcriptions of scanned PDFs; a
    stray undecodable byte must not turn a readable document into a 500.
    """
    path = resolve(name)
    if path is None:
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return {
        "name": path.name,
        "bucket": path.parent.name,
        "lines": text.count("\n") + (0 if text.endswith("\n") else 1),
        "bytes": len(text.encode("utf-8")),
        "text": text,
    }
```

- [ ] **Step 4: Run the tests and watch them PASS**

Run:
```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -m pytest tests/test_amendment_relocation.py -q 2>&1 | tail -15
```
Expected: `12 passed` (3 from Task 2 + 9 new).

If `test_resolve_finds_a_corpus_file_by_basename_across_buckets` fails on its `corpus fixture missing` assertion, `CORPUS_ROOT` does not point where the corpus is. Locate it before changing anything:
```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass" && find source_documents/md -name "IFSCA_Compliance_Handbook.md" && find . -maxdepth 3 -type d -name md
```
Fix `CORPUS_ROOT`, **not the test**.

If `test_index_covers_the_whole_corpus_with_no_collisions` reports a collision, that is a real finding about the corpus, not a test bug. Stop and surface it — a collision means two different documents share a basename and the route would serve whichever the walk found first.

- [ ] **Step 5: Sanity-check the module standalone, outside pytest**

Confirms the cache, the walk, and the rejection all work in a plain process:

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -c "
import document_store as ds
print('CORPUS_ROOT :', ds.CORPUS_ROOT, ds.CORPUS_ROOT.is_dir())
print('indexed     :', len(ds.index()))
print('buckets     :', len({p.parent.name for p in ds.index().values()}))
d = ds.read_document('IFSCA_Compliance_Handbook.md')
print('happy path  :', d['name'], d['bucket'], d['lines'], 'lines', d['bytes'], 'bytes')
bs = chr(92)
for probe in ['..' + bs + '..' + bs + 'backend' + bs + 'ifsca_exam.db', 'C:' + bs + 'Windows' + bs + 'win.ini', 'x.txt', '']:
    print('rejected', repr(probe)[:50], '->', ds.read_document(probe))
"
```
Expected: `indexed: 211`, `buckets: 10`, a real document with non-zero lines/bytes, and `None` for all four rejected probes.

- [ ] **Step 6: Commit**

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass" && git add backend/document_store.py backend/tests/test_amendment_relocation.py && git -c user.name="Kartik Tomar" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "$(cat <<'EOF'
feat(corpus): add a basename-allowlisted document store

Walks source_documents/md once into a cached {basename: Path} index and never
constructs a path from user input. Rejects backslash, drive-absolute and NUL
forms explicitly: on Windows those reach the handler intact, and pathlib
discards the left operand of a join when the right side carries a drive, so
root/'C:\Windows\win.ini' resolves to the real file.

Tested at module level rather than only over HTTP, because TestClient normalizes
'../' away before sending and an HTTP-only traversal test passes vacuously.
EOF
)"
```

---

## Task 4: `GET /api/documents/{name}` + `CorpusDocumentModel`

**Spec part 3b, second half.** The handler does only three things: parse, call, map.

**Files:**
- Modify: `backend/models.py` (append after line 576)
- Modify: `backend/main.py` (local imports at 24-36; model imports at 57-100; new route after line 736)
- Modify: `backend/tests/test_amendment_relocation.py` (append)

- [ ] **Step 1: Write the failing endpoint tests**

Append to `backend/tests/test_amendment_relocation.py`:

```python
import pytest


def test_document_route_serves_a_real_corpus_file(client):
    resp = client.get("/api/documents/IFSCA_Compliance_Handbook.md")
    if resp.status_code == 404 and document_store.resolve("IFSCA_Compliance_Handbook.md") is None:
        pytest.skip("IFSCA_Compliance_Handbook.md absent from this corpus")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "IFSCA_Compliance_Handbook.md"
    assert body["bucket"]
    assert body["lines"] > 0
    assert body["bytes"] > 0
    assert body["text"]


def test_document_route_response_model_declares_every_key(client):
    """F1: response_model silently strips undeclared keys with a 200. This pins
    the exact contract the frontend reader depends on, so a field added to
    read_document() without being added to the model cannot vanish unnoticed --
    the defect class that already caused four frontend bugs in this project."""
    resp = client.get("/api/documents/IFSCA_Compliance_Handbook.md")
    if resp.status_code == 404 and document_store.resolve("IFSCA_Compliance_Handbook.md") is None:
        pytest.skip("corpus file absent")
    assert set(resp.json().keys()) == {"name", "bucket", "lines", "bytes", "text"}


@pytest.mark.parametrize("probe", [
    "..%2F..%2Fbackend%2Fifsca_exam.db",
    "%2e%2e%2f%2e%2e%2fbackend%2f.env.example",
    "..%5C..%5Cbackend%5Cifsca_exam.db",
    "C:%5CWindows%5Cwin.ini",
    "%5C%5Clocalhost%5Cshare%5Cx.md",
    "IFSCA_Compliance_Handbook.txt",
    "IFSCA_Compliance_Handbook",
    "no_such_document_at_all.md",
    "%00.md",
    "IFSCA_Compliance_Handbook.md%00.txt",
])
def test_document_route_returns_404_for_every_malformed_probe(client, probe):
    """ADR-0001: uniform 404 for both malformed and unknown names. No 400/404
    split, because the split is itself an existence oracle that lets a prober
    enumerate which input shapes the allowlist accepts.

    F7: httpx normalizes a literal '../' away before sending, so every probe here
    is percent-encoded and arrives un-normalized. F3: the %2F forms 404 at the
    router, which is the correct end-to-end behaviour but does not exercise this
    handler. The backslash and drive forms are the ones that reach it (F4), and
    they are additionally unit-tested against document_store in Task 3, which is
    where the real security weight sits.
    """
    resp = client.get("/api/documents/" + probe)
    assert resp.status_code == 404, f"{probe!r} returned {resp.status_code}: {resp.text[:200]}"


def test_document_route_does_not_shadow_the_existing_list_endpoint(client):
    """F14: /api/documents (main.py:734) is an exact match and must still work
    after the parameterized sibling is registered."""
    resp = client.get("/api/documents")
    assert resp.status_code == 200
    assert "documents" in resp.json()


def test_document_route_is_not_reachable_for_a_non_md_extension(client):
    """Guards the .md-only rule specifically: a sibling corpus artefact with
    another extension must not become readable through this route."""
    resp = client.get("/api/documents/IFSCA_Compliance_Handbook.pdf")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run them and watch them FAIL**

Run:
```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -m pytest tests/test_amendment_relocation.py -q 2>&1 | tail -25
```
Expected: the 12 Task-2/3 tests still pass. Of the new ones:
- `test_document_route_serves_a_real_corpus_file` → **fails**, 404.
- `test_document_route_response_model_declares_every_key` → **fails**, 404.
- `test_document_route_does_not_shadow_the_existing_list_endpoint` → **passes already** (the list endpoint exists).
- The 10 parametrized probes and the `.pdf` test → **pass already**, because 404 is what an unregistered route returns. **This is expected and is precisely why Task 3's direct unit tests carry the security weight.** Do not mistake these passes for evidence the defence works.

Record which failed. If any parametrized probe returns 200 or 500 *here*, a route already exists and this plan's premise is wrong — stop and investigate before adding a second one.

- [ ] **Step 3: Add `CorpusDocumentModel` to `backend/models.py`**

The file currently ends at line 576 with `ExamAggregateResponseModel`. Append after it:

```python
class CorpusDocumentModel(BaseModel):
    """A markdown corpus document, served for manual reading.

    Deliberately not named DocumentModel: that already exists (models.py:96-111)
    and models ingestion *metadata* for the documents table -- document_id,
    sha256, pages, line_count, status. This models file *content*. Reusing the
    name would either shadow that model or force a rename across its callers.

    Every field is declared because response_model silently strips anything it
    does not (F1), and the frontend reader depends on all five.
    """

    name: str
    bucket: str
    lines: int
    bytes: int
    text: str
```

- [ ] **Step 4: Import it in `backend/main.py`**

The `from models import (` block runs from line 57 to line 100. Insert `CorpusDocumentModel,` after `AnalyticsTimelineModel,` (line 61) so the leading alphabetical run stays intact:

```python
    AmendmentResponseModel,
    AnalyticsTimelineModel,
    CorpusDocumentModel,
    DashboardStatsModel,
```

- [ ] **Step 5: Import the module**

In the local-import block (`main.py:24-36`), insert `import document_store` after `import amendment_poller` (line 25):

```python
import database as db
import amendment_poller
import document_store
import job_queue
import essay_grader
```

- [ ] **Step 6: Add the route**

In `backend/main.py`, the existing list endpoint is at lines 734-736:

```python
@app.get("/api/documents")
def list_documents(limit: int = Query(default=200, ge=1, le=500)):
    return {"documents": db.list_documents(limit=limit)}
```

Insert the new route **immediately after it**, before `@app.get("/api/topics", response_model=list[TopicModel])`:

```python
@app.get("/api/documents/{name}", response_model=CorpusDocumentModel)
def get_corpus_document(name: str):
    """Serve one markdown corpus document for manual reading.

    Sync def on purpose: reading up to ~330KB from disk is blocking I/O, and
    FastAPI runs sync handlers in a threadpool. async def here would block the
    event loop for the duration of the read. This also matches the codebase,
    which is 121 sync handlers to 8 async.

    Uniform 404 for both malformed and unknown names (ADR-0001). Deliberately
    NOT Path(pattern=...): that would answer 422 for a malformed name and 404 for
    an unknown one, and the split tells a prober which input shapes the allowlist
    accepts. Note also that Path in this module is fastapi.Path (main.py:19),
    with pathlib.Path imported as PathLib (F17).

    No rate limit: this spends no Gemini tokens, so gemini_spend_guard does not
    apply, and the server binds to loopback only. Revisit immediately if this
    endpoint is ever exposed beyond 127.0.0.1.
    """
    document = document_store.read_document(name)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return CorpusDocumentModel(**document)
```

- [ ] **Step 7: Run the tests and watch them PASS**

Run:
```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -m pytest tests/test_amendment_relocation.py -q 2>&1 | tail -20
```
Expected: `25 passed` (12 previous + 3 plain + 10 parametrized).

- [ ] **Step 8: Confirm the app still imports and both routes are registered in the right order**

Run:
```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -c "
import main
paths = [r.path for r in main.app.routes if hasattr(r, 'path')]
assert '/api/documents' in paths, 'list endpoint lost'
assert '/api/documents/{name}' in paths, 'new route not registered'
print('both document routes registered')
print('  /api/documents       at index', paths.index('/api/documents'))
print('  /api/documents/{name} at index', paths.index('/api/documents/{name}'))
print('  total routes         :', len(paths))
"
```
Expected: both registered, and the **exact-match route's index is lower** than the parameterized one. Starlette matches in registration order, so if the parameterized route came first it would swallow `/api/documents` and Task 4's shadow test would have caught it — this confirms the ordering directly.

- [ ] **Step 9: Smoke the endpoint against the live corpus over a real HTTP path**

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -c "
from fastapi.testclient import TestClient
import main
c = TestClient(main.app)
ok = c.get('/api/documents/IFSCA_Compliance_Handbook.md')
print('happy   :', ok.status_code, ok.json()['bucket'], ok.json()['lines'], 'lines', ok.json()['bytes'], 'bytes')
print('traversal:', c.get('/api/documents/C:%5CWindows%5Cwin.ini').status_code,
                c.get('/api/documents/..%5C..%5Cbackend%5Cifsca_exam.db').status_code,
                c.get('/api/documents/x.txt').status_code,
                c.get('/api/documents/%00.md').status_code)
print('list    :', c.get('/api/documents').status_code)
"
```
Expected: `happy : 200 03_IFSCA_Act_Regulations_Handbooks_Circulars <n> lines <n> bytes`, then `traversal: 404 404 404 404`, then `list : 200`.

- [ ] **Step 10: Commit**

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass" && git add backend/main.py backend/models.py backend/tests/test_amendment_relocation.py && git -c user.name="Kartik Tomar" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "$(cat <<'EOF'
feat(api): serve corpus markdown through GET /api/documents/{name}

Basename-allowlisted via document_store, sync def for the blocking read, and a
uniform 404 for both malformed and unknown names so the endpoint is not an
existence oracle. CorpusDocumentModel declares all five keys because
response_model silently strips anything undeclared.

Named CorpusDocumentModel rather than DocumentModel, which already exists and
models ingestion metadata for the documents table.
EOF
)"
```

---

## Newly verified facts (F20-F24) — established while writing Tasks 5-6

These were verified against the live database and the installed libraries during
plan authoring. They correct the spec.

| # | Fact |
|---|---|
| F20 | The live `backend/ifsca_exam.db` has **10** `exam_templates` rows, but only **7** can actually drive `generate_smart_mock`. Verified by running the readiness predicate over all 10 live rows: READY = `CUSTOM`, `IFSCA_PH1_P1`, `IFSCA_PH1_P2_GENERAL`, `IFSCA_PH2_P2_GENERAL`, `SEBI_PH1_P1`, `SEBI_PH1_P2_GENERAL`, `SEBI_PH2_P2_GENERAL`. EXCLUDED = `IFSCA_PH2_P1_DESC`, `SEBI_PH2_P1_DESC`, `SUBJECT_DRILL`. |
| F21 | `_template_allocation` (`database.py:4640-4698`) returns `{}` for any template that declares **neither** a non-empty `sections_json` **nor** a non-empty `syllabus_units_json` **and** is not a key of `TEMPLATE_UNIT_TOPICS`. `generate_smart_mock` then raises `RuntimeError("Mock allocation is empty; ingest the knowledge pack first.")` (`database.py:4744-4745`), and `exam_start`'s blanket `except Exception` (`main.py:1352-1353`) converts that into **HTTP 500 with a misleading message** that tells the user to ingest the knowledge pack. This is the live fate of `SUBJECT_DRILL` and both `*_DESC` rows. |
| F22 | `TEMPLATE_UNIT_TOPICS` (`database.py:4620`) has exactly **4** keys: `IFSCA_PH1_P2_GENERAL`, `IFSCA_PH2_P2_GENERAL`, `SEBI_PH1_P2_GENERAL`, `SEBI_PH2_P2_GENERAL`. The two Phase I Paper 1 templates are covered instead by their non-empty `sections_json`. |
| F23 | `TestClient(app)` in `conftest.py:91` is constructed **without** a context manager, so **`lifespan` never runs in tests** and `db.init_db()` (`main.py:152`) is never called. That is why `exam_templates` does not exist in the fixture DB (F10) even though it always exists in production. |
| F24 | `db._run_migration_005(conn)` (`database.py:1300-1317`) creates `exam_templates` from `migrations/005_knowledge_layer.sql:88-104`. When passed an existing connection it executes the script but **does not commit** (`if owns_conn: conn.commit()` at 1310-1311) — the caller must commit. This is the same house pattern conftest already uses for `_run_migration_002`. |
| F25 | `response_model=dict[str, list[ExamTemplateModel]]` was probed empirically on the installed FastAPI 0.115.0 / Pydantic 2.13.4 with a throwaway app. Confirmed: the inner model **is** registered in `components.schemas`; `phase: int \| None` serializes to `{'anyOf': [{'type': 'integer'}, {'type': 'null'}], 'title': 'Phase'}`; `ExamTemplateModel(**row)` accepts the full 15-column row without error (`extra="ignore"` is the Pydantic v2 default); and the wire object carries **exactly the 8 declared keys** — `marks_per_question`, `total_marks`, `aggregate_cutoff_pct`, `sections_json`, `syllabus_units_json`, `descriptive_components_json` and `notes` are all stripped silently with HTTP 200. |

**Refinement of F10.** The earlier note said the fix was to make
`list_exam_templates()` call `init_db()`. That is **wrong** and is withdrawn:
`init_db()` publishes the path into the module-level `_INITIALIZED_DB_PATHS`
cache (`database.py:1583`) which conftest never clears, so calling it from tests
leaks cache entries for temp paths that are then unlinked. Instead
`list_exam_templates()` follows `get_exam_template`'s existing pattern (**no**
`init_db()` — `lifespan` guarantees the table in production), and the **test**
creates the table itself via `db._run_migration_005(conn)` + `conn.commit()`,
exactly as conftest already does for migration 002.

**Additional spec corrections (continuing the numbering from chunk 1):**

6. **Spec lines 438-439** say `db.list_exam_templates()` "excludes both `*_DESC`
   rows (NULL `total_questions`), includes the 8 objective templates plus
   `CUSTOM`". Both halves are wrong. The real exclusion rule is not
   `total_questions IS NULL` — `SUBJECT_DRILL` has `total_questions = 20` and
   still 500s (F21). And the real count is **7 rows including `CUSTOM`**, not 9.
   The tests therefore assert an explicit ID list, not a count.
7. **Spec line 445** uses `template="SUBJECT_DRILL"` as the forwarding probe for
   `/api/exams/start`. `SUBJECT_DRILL` is excluded from the catalogue, so using
   it as the probe would test a value the UI can never send. Task 7 probes with
   `IFSCA_PH2_P2_GENERAL` instead. The substance of the assertion is unchanged:
   a spy records the `template_id` kwarg verbatim.
8. **Spec §4 does not mention that `/api/exams/start` cannot be exercised
   end-to-end in this worktree at all.** `generate_smart_mock` raises
   `RuntimeError` when `not gemini_available()` (`database.py:4707-4708`), and
   per memory `ledger-worktree-no-gemini-keys` this worktree has **zero** Gemini
   keys. Every Task 7 test must therefore monkeypatch `db.generate_smart_mock`
   with a spy. A test that does not will fail for an environmental reason and
   prove nothing about the fix.

---

### Task 5: `db.list_exam_templates()` — the generatable-exam catalogue

**Files:**
- Modify: `backend/database.py` — insert two new functions between line 4698
  (the last line of `_template_allocation`,
  `return {unit: count for unit, count in allocation.items() if count > 0}`) and
  line 4701 (`def generate_smart_mock(`). Lines 4699-4700 are blank.
- Create: `backend/tests/test_phase_exam_templates.py`

**Why the predicate lives here, not in the frontend.** The frontend cannot tell a
generatable template from a broken one: `SUBJECT_DRILL` looks perfectly normal
(20 questions, 20 minutes, `exam = "ANY"`). Only the allocation logic knows it
produces nothing. Putting the rule next to `_template_allocation` — the function
whose behaviour it mirrors — means the two cannot drift apart unnoticed.

**Why excluded rows are dropped rather than returned with a flag.** A returned
`objective_ready: false` field would have to be rendered as a disabled option
with an explanatory tooltip, which is new CSS, new JS and new copy for three rows
the user cannot use anyway. Spec line 318 already decides the descriptive papers
"stay out of the picker; descriptive practice has its own view". Dropping them at
the query boundary is the smaller surface. The reason is preserved where it
cannot rot: in `_template_is_objective_ready`'s docstring and in
`test_list_exam_templates_excludes_rows_whose_allocation_is_empty`.

- [ ] **Step 1: Write the failing test file**

Create `backend/tests/test_phase_exam_templates.py` with exactly this content.
`LIVE_TEMPLATES` mirrors the 10 rows currently in `backend/ifsca_exam.db`
(dumped and transcribed during plan authoring) so the exclusion and ordering
tests run against production-shaped data rather than a convenient fiction.

```python
"""Tests for the phase/paper exam-template catalogue behind GET /api/exam-templates.

The conftest `test_db` fixture runs SCHEMA plus migrations 002 only, and
TestClient is built without a context manager so `lifespan` (and therefore
db.init_db) never runs. exam_templates is created by migration 005, so every
test here creates and seeds the table itself via db._run_migration_005 -- the
same house pattern conftest uses for migration 002.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

import pytest

import database as db


# Mirrors the 10 rows in backend/ifsca_exam.db at plan-authoring time.
# Column order matches _COLUMNS below.
LIVE_TEMPLATES: list[dict[str, Any]] = [
    {
        "template_id": "CUSTOM", "exam": "ANY", "name": "Custom mock",
        "phase": None, "paper": None, "total_questions": 50,
        "marks_per_question": 1.0, "total_marks": None, "time_limit_minutes": 60,
        "cutoff_pct": None, "aggregate_cutoff_pct": None,
        "sections_json": "[]", "syllabus_units_json": "[]",
        "descriptive_components_json": "[]", "notes": None,
    },
    {
        "template_id": "IFSCA_PH1_P1", "exam": "IFSCA",
        "name": "IFSCA Phase I Paper 1 (all streams)",
        "phase": 1, "paper": 1, "total_questions": 100,
        "marks_per_question": 1.0, "total_marks": 100, "time_limit_minutes": 60,
        "cutoff_pct": 30.0, "aggregate_cutoff_pct": None,
        "sections_json": json.dumps([
            {"name": "General Awareness (Financial Sector)", "questions": 25},
            {"name": "English Language", "questions": 25},
            {"name": "Quantitative Aptitude", "questions": 25},
            {"name": "Reasoning", "questions": 25},
        ]),
        "syllabus_units_json": "[]", "descriptive_components_json": "[]",
        "notes": "Screening only; marks not counted for final selection.",
    },
    {
        "template_id": "IFSCA_PH1_P2_GENERAL", "exam": "IFSCA",
        "name": "IFSCA Phase I Paper 2 (General stream)",
        "phase": 1, "paper": 2, "total_questions": 50,
        "marks_per_question": 2.0, "total_marks": 100, "time_limit_minutes": 60,
        "cutoff_pct": 40.0, "aggregate_cutoff_pct": None,
        "sections_json": "[]",
        "syllabus_units_json": json.dumps([
            "General knowledge & current events",
            "Economic & social development",
            "Commerce & accountancy",
            "Management", "Finance", "Costing",
            "Indian & global economy",
            "GoI financial-sector schemes",
        ]),
        "descriptive_components_json": "[]",
        "notes": "Aggregate cut-off across both Phase I papers: 40%.",
    },
    {
        "template_id": "IFSCA_PH2_P1_DESC", "exam": "IFSCA",
        "name": "IFSCA Phase II Paper 1 (Descriptive English)",
        "phase": 2, "paper": 1, "total_questions": None,
        "marks_per_question": None, "total_marks": 100, "time_limit_minutes": 60,
        "cutoff_pct": 30.0, "aggregate_cutoff_pct": None,
        "sections_json": "[]", "syllabus_units_json": "[]",
        "descriptive_components_json": json.dumps([
            {"type": "ESSAY", "marks": 30, "word_limit_min": 200, "word_limit_max": 400},
            {"type": "PRECIS", "marks": 35, "word_limit_min": 120, "word_limit_max": 130, "title_required": True},
            {"type": "RC", "marks": 35, "answers_in_own_words": True},
        ]),
        "notes": "Typed on computer; one question displayed at a time.",
    },
    {
        "template_id": "IFSCA_PH2_P2_GENERAL", "exam": "IFSCA",
        "name": "IFSCA Phase II Paper 2 (General stream)",
        "phase": 2, "paper": 2, "total_questions": 50,
        "marks_per_question": 2.0, "total_marks": 100, "time_limit_minutes": 60,
        "cutoff_pct": 40.0, "aggregate_cutoff_pct": None,
        "sections_json": "[]",
        "syllabus_units_json": json.dumps([
            "IFSCA Act/IFSCA/IFSC/GIFT IFSC/GIFT City/Global Financial Centres",
            "Union Budget & Economic Survey", "Banking", "Capital Market",
            "Insurance", "Pension Sector",
        ]),
        "descriptive_components_json": "[]", "notes": None,
    },
    {
        "template_id": "SEBI_PH1_P1", "exam": "SEBI", "name": "SEBI Phase 1 Paper 1",
        "phase": 1, "paper": 1, "total_questions": 80,
        "marks_per_question": 1.25, "total_marks": 100, "time_limit_minutes": 60,
        "cutoff_pct": 30.0, "aggregate_cutoff_pct": None,
        "sections_json": json.dumps([
            {"name": "General Awareness", "questions": 20, "marks": 25},
            {"name": "English Language", "questions": 20, "marks": 25},
            {"name": "Quantitative Aptitude", "questions": 20, "marks": 25},
            {"name": "Reasoning", "questions": 20, "marks": 25},
        ]),
        "syllabus_units_json": "[]", "descriptive_components_json": "[]",
        "notes": None,
    },
    {
        "template_id": "SEBI_PH1_P2_GENERAL", "exam": "SEBI",
        "name": "SEBI Phase 1 Paper 2 (General stream)",
        "phase": 1, "paper": 2, "total_questions": 50,
        "marks_per_question": 2.0, "total_marks": 100, "time_limit_minutes": 40,
        "cutoff_pct": 40.0, "aggregate_cutoff_pct": None,
        "sections_json": "[]",
        "syllabus_units_json": json.dumps([
            "Commerce & Accountancy", "Management", "Finance", "Costing",
            "Companies Act", "Economics",
        ]),
        "descriptive_components_json": "[]", "notes": None,
    },
    {
        "template_id": "SEBI_PH2_P1_DESC", "exam": "SEBI",
        "name": "SEBI Phase 2 Paper 1 (Descriptive)",
        "phase": 2, "paper": 1, "total_questions": None,
        "marks_per_question": None, "total_marks": 100, "time_limit_minutes": 60,
        "cutoff_pct": 30.0, "aggregate_cutoff_pct": None,
        "sections_json": "[]", "syllabus_units_json": "[]",
        "descriptive_components_json": json.dumps([
            {"type": "ESSAY", "marks": 30, "word_limit_min": 250, "word_limit_max": 270, "topics_offered": 4},
            {"type": "PRECIS", "marks": 30, "word_limit_min": 140, "word_limit_max": 160, "title_required": True},
            {"type": "RC", "marks": 40, "questions": 5},
        ]),
        "notes": "Letter Writing appears in the 2025 TOC.",
    },
    {
        "template_id": "SEBI_PH2_P2_GENERAL", "exam": "SEBI",
        "name": "SEBI Phase 2 Paper 2 (General stream)",
        "phase": 2, "paper": 2, "total_questions": 100,
        "marks_per_question": 1.0, "total_marks": 100, "time_limit_minutes": 90,
        "cutoff_pct": 40.0, "aggregate_cutoff_pct": 50.0,
        "sections_json": "[]",
        "syllabus_units_json": json.dumps([
            "Commerce & Accountancy", "Management", "Finance", "Costing",
            "Companies Act", "Economics",
        ]),
        "descriptive_components_json": "[]",
        "notes": "Post-2024 pattern: 100 x 1 mark (2022 was 50 x 2 marks).",
    },
    {
        "template_id": "SUBJECT_DRILL", "exam": "ANY",
        "name": "Subject drill (cross-exam)",
        "phase": None, "paper": None, "total_questions": 20,
        "marks_per_question": 1.0, "total_marks": None, "time_limit_minutes": 20,
        "cutoff_pct": None, "aggregate_cutoff_pct": None,
        "sections_json": "[]", "syllabus_units_json": "[]",
        "descriptive_components_json": "[]",
        "notes": "Mixed IFSCA/SEBI bank questions filtered by subject_id.",
    },
]

_COLUMNS = (
    "template_id, exam, name, phase, paper, total_questions, marks_per_question, "
    "total_marks, time_limit_minutes, cutoff_pct, aggregate_cutoff_pct, "
    "sections_json, syllabus_units_json, descriptive_components_json, notes"
)

# The 7 rows a user can actually start an exam from, in catalogue order.
EXPECTED_ORDER = [
    "CUSTOM",
    "IFSCA_PH1_P1",
    "IFSCA_PH1_P2_GENERAL",
    "IFSCA_PH2_P2_GENERAL",
    "SEBI_PH1_P1",
    "SEBI_PH1_P2_GENERAL",
    "SEBI_PH2_P2_GENERAL",
]


def _seed_templates(db_path: str, rows: list[dict[str, Any]] | None = None) -> None:
    """Create exam_templates via migration 005 and insert `rows` (default: all 10 live rows)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        db._run_migration_005(conn)
        conn.commit()
        for row in rows if rows is not None else LIVE_TEMPLATES:
            conn.execute(
                f"INSERT INTO exam_templates ({_COLUMNS}) VALUES ({','.join('?' * 15)})",
                tuple(row[column] for column in _COLUMNS.split(", ")),
            )
        conn.commit()
    finally:
        conn.close()


def test_list_exam_templates_returns_the_seven_generatable_rows(test_db: str) -> None:
    _seed_templates(test_db)
    templates = db.list_exam_templates()
    assert [t["template_id"] for t in templates] == EXPECTED_ORDER


def test_list_exam_templates_excludes_rows_whose_allocation_is_empty(test_db: str) -> None:
    """SUBJECT_DRILL declares 20 questions but no sections and no syllabus units,
    and is not a TEMPLATE_UNIT_TOPICS key, so _template_allocation returns {} and
    generate_smart_mock raises "Mock allocation is empty" -> HTTP 500. The two
    descriptive papers are the same shape. Offering any of the three in the picker
    would hand the user a guaranteed error, so they are not catalogue rows."""
    _seed_templates(test_db)
    ids = {t["template_id"] for t in db.list_exam_templates()}
    assert "SUBJECT_DRILL" not in ids
    assert "IFSCA_PH2_P1_DESC" not in ids
    assert "SEBI_PH2_P1_DESC" not in ids


def test_list_exam_templates_orders_by_exam_then_phase_then_paper(test_db: str) -> None:
    """CUSTOM (exam='ANY', phase NULL) sorts first so the picker's default option
    is the current behaviour; then IFSCA before SEBI, phase 1 before phase 2,
    paper 1 before paper 2. COALESCE(phase, 0) keeps NULL out of the sort."""
    _seed_templates(test_db)
    templates = db.list_exam_templates()
    ifsca_rows = [t for t in templates if t["exam"] == "IFSCA"]
    sebi_rows = [t for t in templates if t["exam"] == "SEBI"]
    assert [t["template_id"] for t in ifsca_rows] == [
        "IFSCA_PH1_P1", "IFSCA_PH1_P2_GENERAL", "IFSCA_PH2_P2_GENERAL"
    ]
    assert [t["template_id"] for t in sebi_rows] == [
        "SEBI_PH1_P1", "SEBI_PH1_P2_GENERAL", "SEBI_PH2_P2_GENERAL"
    ]
    assert templates[0]["template_id"] == "CUSTOM"


def test_list_exam_templates_carries_the_fields_the_picker_renders(test_db: str) -> None:
    _seed_templates(test_db)
    sebi_p2 = next(
        t for t in db.list_exam_templates() if t["template_id"] == "SEBI_PH1_P2_GENERAL"
    )
    assert sebi_p2["name"] == "SEBI Phase 1 Paper 2 (General stream)"
    assert sebi_p2["phase"] == 1
    assert sebi_p2["paper"] == 2
    assert sebi_p2["total_questions"] == 50
    assert sebi_p2["time_limit_minutes"] == 40
    assert sebi_p2["cutoff_pct"] == 40.0


def test_list_exam_templates_on_an_empty_table_returns_an_empty_list(test_db: str) -> None:
    """Migration 005 creates the table but seeds nothing -- seeding only happens in
    bootstrap_from_knowledge (database.py:1473). An unseeded install must yield an
    empty catalogue, not an OperationalError."""
    _seed_templates(test_db, rows=[])
    assert db.list_exam_templates() == []


@pytest.mark.parametrize(
    "template, expected",
    [
        ({"template_id": "CUSTOM", "sections_json": "[]", "syllabus_units_json": "[]"}, True),
        ({"template_id": "IFSCA_PH1_P1",
          "sections_json": '[{"name": "Reasoning", "questions": 25}]',
          "syllabus_units_json": "[]"}, True),
        ({"template_id": "IFSCA_PH2_P2_GENERAL",
          "sections_json": "[]", "syllabus_units_json": "[]"}, True),
        ({"template_id": "SEBI_PH1_P2_GENERAL", "sections_json": "[]",
          "syllabus_units_json": '["Finance"]'}, True),
        ({"template_id": "SUBJECT_DRILL",
          "sections_json": "[]", "syllabus_units_json": "[]"}, False),
        ({"template_id": "IFSCA_PH2_P1_DESC",
          "sections_json": "[]", "syllabus_units_json": "[]"}, False),
        ({"template_id": "X", "sections_json": None, "syllabus_units_json": None}, False),
    ],
)
def test_template_is_objective_ready_predicate(
    template: dict[str, Any], expected: bool
) -> None:
    """The third case passes on the TEMPLATE_UNIT_TOPICS key alone: no sections,
    no units in the row. The last case proves the `or "[]"` guards against NULL
    columns, which migration 005 permits."""
    assert db._template_is_objective_ready(template) is expected
```

Note on the two `AttributeError` shapes: the five catalogue tests fail on
`db.list_exam_templates`, the seven predicate cases fail on
`db._template_is_objective_ready`. Both are expected in the same run.

- [ ] **Step 2: Run the tests and watch them fail**

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -m pytest tests/test_phase_exam_templates.py -v
```

Expected: **12 collected, 12 failed** — five catalogue tests with
`AttributeError: module 'database' has no attribute 'list_exam_templates'`, and
the seven parametrized cases of `test_template_is_objective_ready_predicate` with
`AttributeError: module 'database' has no attribute
'_template_is_objective_ready'`. **Read the actual count and write it down.** If
you see anything other than 12 collected, your transcription of Step 1 differs
from this plan — reconcile before continuing. If you see `PASSED`, something
already implements this; stop and investigate.

- [ ] **Step 3: Implement the predicate and the catalogue query**

Insert into `backend/database.py` immediately after line 4698
(`    return {unit: count for unit, count in allocation.items() if count > 0}`,
the last line of `_template_allocation`) and before the two blank lines preceding
`def generate_smart_mock(` at line 4701. `json` is already imported at module
level in `database.py`; do not add an import.

```python
def _template_is_objective_ready(template: dict[str, Any]) -> bool:
    """True when this template can actually drive generate_smart_mock.

    Mirrors _template_allocation above: that function returns {} unless the
    template declares sections, is a TEMPLATE_UNIT_TOPICS key, or declares
    syllabus units. An empty allocation makes generate_smart_mock raise
    "Mock allocation is empty; ingest the knowledge pack first.", which
    exam_start's blanket except turns into an HTTP 500 whose message blames a
    knowledge pack that is already ingested. SUBJECT_DRILL and the two
    descriptive papers are all three shapes of that dead end, so they are
    catalogue rows but not generatable exams. CUSTOM bypasses the template path
    entirely (generate_smart_mock only looks the template up when
    template_id != "CUSTOM") and is always ready.
    """
    template_id = template["template_id"]
    if template_id == "CUSTOM":
        return True
    if template_id in TEMPLATE_UNIT_TOPICS:
        return True
    if json.loads(template.get("sections_json") or "[]"):
        return True
    return bool(json.loads(template.get("syllabus_units_json") or "[]"))


def list_exam_templates() -> list[dict[str, Any]]:
    """Every exam template a user can actually start, ordered for a picker.

    No init_db() here: get_exam_template does not call it either, and lifespan
    (main.py:152) has already run it by the time any request is served. Tests
    create the table themselves with _run_migration_005, which is the same
    pattern conftest uses for migration 002.

    COALESCE(phase, 0) / COALESCE(paper, 0) sort CUSTOM's NULLs first rather
    than last, so the picker's top option is the current default behaviour and
    the IFSCA/SEBI papers follow in exam -> phase -> paper order.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM exam_templates
            ORDER BY exam,
                     COALESCE(phase, 0),
                     COALESCE(paper, 0),
                     template_id
            """
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows if _template_is_objective_ready(dict(row))]
```

**Do not** add `init_db()` to `list_exam_templates()`. See the F10 refinement
above: it pollutes `_INITIALIZED_DB_PATHS` with temp paths the fixture then
unlinks.

**Do not** call `dict(row)` once and reuse the variable — `_template_is_objective_ready`
does not mutate, but reading the comprehension as "filter a materialised list of
dicts" is the point. If you prefer, this is equivalent and slightly cheaper:

```python
    templates = [dict(row) for row in rows]
    return [template for template in templates if _template_is_objective_ready(template)]
```

Either form is acceptable; pick the second if the linter complains about the
double conversion.

- [ ] **Step 4: Run the tests and watch them pass**

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -m pytest tests/test_phase_exam_templates.py -v
```

Expected: **12 passed**, 0 failed, 0 errors. If
`test_list_exam_templates_on_an_empty_table_returns_an_empty_list` fails with
`sqlite3.OperationalError: no such table: exam_templates`, the
`db._run_migration_005(conn)` call in `_seed_templates` did not run or the
`conn.commit()` after it was omitted (F24: `_run_migration_005` does not commit
when handed an existing connection).

- [ ] **Step 5: Prove the tests are not vacuous (red-green on the predicate)**

Temporarily break the predicate so `SUBJECT_DRILL` slips through, and confirm a
test catches it. In `_template_is_objective_ready`, change the final line from

```python
    return bool(json.loads(template.get("syllabus_units_json") or "[]"))
```

to

```python
    return True
```

Run:

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -m pytest tests/test_phase_exam_templates.py -q
```

Expected: **exactly 6 failures** —
`test_list_exam_templates_returns_the_seven_generatable_rows` (10 rows instead of
7), `test_list_exam_templates_excludes_rows_whose_allocation_is_empty`
(`SUBJECT_DRILL` present), `test_list_exam_templates_orders_by_exam_then_phase_then_paper`
(`IFSCA_PH2_P1_DESC` intrudes between phase 1 paper 2 and phase 2 paper 2), and
the three parametrized predicate cases whose expectation is `False`
(`SUBJECT_DRILL`, `IFSCA_PH2_P1_DESC`, and the NULL-columns case `X`). The four
`True` predicate cases and the two remaining catalogue tests still pass, which is
the point: the break is selective, so a green suite here would mean the exclusion
tests are vacuous and must be fixed before going on.

Then restore the line exactly:

```python
    return bool(json.loads(template.get("syllabus_units_json") or "[]"))
```

and re-run to confirm **12 passed** again.

- [ ] **Step 6: Smoke the catalogue against the live database**

This reads `backend/ifsca_exam.db` with SELECTs only — no writes.

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -c "
import database as db
rows = db.list_exam_templates()
print('count:', len(rows))
for r in rows:
    print('  %-24s %-6s ph=%-4s pp=%-4s q=%-4s min=%-3s cut=%s' % (
        r['template_id'], r['exam'], r['phase'], r['paper'],
        r['total_questions'], r['time_limit_minutes'], r['cutoff_pct']))
ids = {r['template_id'] for r in rows}
print('excluded present?', sorted(ids & {'SUBJECT_DRILL','IFSCA_PH2_P1_DESC','SEBI_PH2_P1_DESC'}))
"
```

Expected: `count: 7`, then the seven IDs in the order `CUSTOM`, `IFSCA_PH1_P1`,
`IFSCA_PH1_P2_GENERAL`, `IFSCA_PH2_P2_GENERAL`, `SEBI_PH1_P1`,
`SEBI_PH1_P2_GENERAL`, `SEBI_PH2_P2_GENERAL`, then `excluded present? []`.

- [ ] **Step 7: Commit**

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass" && git add backend/database.py backend/tests/test_phase_exam_templates.py && git -c user.name="Kartik Tomar" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "$(cat <<'EOF'
feat(db): add list_exam_templates returning only generatable exams

_template_allocation returns {} for a template with no sections, no syllabus
units and no TEMPLATE_UNIT_TOPICS entry, and generate_smart_mock turns that into
"Mock allocation is empty" -- which exam_start reports as a 500 blaming an
already-ingested knowledge pack. SUBJECT_DRILL and both descriptive papers are
that shape, so offering them would hand the user a guaranteed error.

_template_is_objective_ready mirrors the allocation logic beside it so the two
cannot drift. Tests seed all 10 live rows through _run_migration_005 because
TestClient never runs lifespan, so init_db (and migration 005) never happens
under pytest.
EOF
)"
```

---

### Task 6: `GET /api/exam-templates` and `ExamTemplateModel`

**Files:**
- Modify: `backend/models.py` — append `ExamTemplateModel` after the
  `CorpusDocumentModel` class that Task 3/4 created at the end of the file.
  Anchor on the literal text of `CorpusDocumentModel`, not on a line number:
  Task 4 has already shifted everything below the old line 576.
- Modify: `backend/main.py` — add `ExamTemplateModel,` to the
  `from models import (...)` block (the block spans lines 57-100 before Task 4's
  edit); add the route between `submit_mock` (ends line 1293) and
  `@app.post("/api/exams/start", ...)` (line 1296). Lines 1294-1295 are blank.
- Test: `backend/tests/test_phase_exam_templates.py` (append to the Task 5 file —
  the endpoint and the query it exposes belong in one place)

**Why `response_model` here is load-bearing, not decoration.** F1: it silently
strips undeclared keys. `list_exam_templates()` returns full 15-column rows
including `sections_json`, `syllabus_units_json`, `descriptive_components_json`
and `notes` — raw JSON strings the picker would have to re-parse. Declaring only
the rendered fields means the wire format is the contract, and the three JSON
blobs never leave the backend. **Every field the picker reads must be declared,
or it will vanish with HTTP 200 and the UI will show `undefined`.** That is the
exact defect class recorded in memory `ledger-response-model-strips-keys`, which
caused four frontend bugs.

**Why every numeric field is nullable.** F2: `response_model` raises HTTP 500
when a non-nullable field receives `None`. In the live rows `phase` and `paper`
are NULL for `CUSTOM`; `total_questions`, `marks_per_question` and `cutoff_pct`
are NULL for several rows. A `phase: int` declaration would 500 on `CUSTOM` — the
picker's first and default option.

- [ ] **Step 1: Append the endpoint tests**

Add to the **end** of `backend/tests/test_phase_exam_templates.py`. These need
the `client` fixture from conftest, which depends on `test_db`, so the seeding
must happen before the client is used — the fixture order in the signature
(`test_db` first, then `client`) guarantees that.

```python
def test_get_exam_templates_returns_the_catalogue(test_db: str, client) -> None:
    _seed_templates(test_db)
    response = client.get("/api/exam-templates")
    assert response.status_code == 200
    body = response.json()
    assert [t["template_id"] for t in body["templates"]] == EXPECTED_ORDER


def test_get_exam_templates_declares_every_field_the_picker_renders(test_db: str, client) -> None:
    """response_model strips undeclared keys silently (HTTP 200, key absent), so a
    field missing from ExamTemplateModel shows up in the UI as undefined rather
    than as an error. This asserts the wire contract explicitly."""
    _seed_templates(test_db)
    body = client.get("/api/exam-templates").json()
    ifsca_p1 = next(t for t in body["templates"] if t["template_id"] == "IFSCA_PH1_P1")
    for field in (
        "template_id", "exam", "name", "phase", "paper",
        "total_questions", "time_limit_minutes", "cutoff_pct",
    ):
        assert field in ifsca_p1, f"{field} was stripped by response_model"
    assert ifsca_p1["exam"] == "IFSCA"
    assert ifsca_p1["phase"] == 1
    assert ifsca_p1["paper"] == 1
    assert ifsca_p1["total_questions"] == 100
    assert ifsca_p1["time_limit_minutes"] == 60
    assert ifsca_p1["cutoff_pct"] == 30.0


def test_get_exam_templates_survives_null_phase_and_paper(test_db: str, client) -> None:
    """CUSTOM has phase=NULL, paper=NULL and cutoff_pct=NULL. A non-nullable
    declaration on any of those makes FastAPI raise a 500 during response
    validation, so this is the regression test for the nullable annotations."""
    _seed_templates(test_db)
    body = client.get("/api/exam-templates").json()
    custom = next(t for t in body["templates"] if t["template_id"] == "CUSTOM")
    assert custom["phase"] is None
    assert custom["paper"] is None
    assert custom["cutoff_pct"] is None
    assert custom["total_questions"] == 50


def test_get_exam_templates_does_not_leak_the_json_blobs(test_db: str, client) -> None:
    """sections_json / syllabus_units_json / descriptive_components_json are raw
    JSON strings meant for _template_allocation, not for the browser."""
    _seed_templates(test_db)
    body = client.get("/api/exam-templates").json()
    for template in body["templates"]:
        assert "sections_json" not in template
        assert "syllabus_units_json" not in template
        assert "descriptive_components_json" not in template


def test_get_exam_templates_on_an_unseeded_install_returns_an_empty_list(test_db: str, client) -> None:
    _seed_templates(test_db, rows=[])
    response = client.get("/api/exam-templates")
    assert response.status_code == 200
    assert response.json() == {"templates": []}


def test_exam_templates_route_does_not_shadow_or_get_shadowed(test_db: str, client) -> None:
    """/api/exam-templates must stay distinct from /api/exams/start and from
    /api/documents. FastAPI matches in declaration order, so a later
    /api/{something} catch-all would swallow it -- this pins the observable
    behaviour rather than the registration order."""
    _seed_templates(test_db)
    assert client.get("/api/exam-templates").status_code == 200
    assert client.get("/api/documents").status_code == 200
    assert client.get("/api/exams/start").status_code in (404, 405)
```

- [ ] **Step 2: Run them and watch them fail**

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -m pytest tests/test_phase_exam_templates.py -q
```

Expected: **18 collected, 12 passed, 6 failed.** The 12 passing are Task 5's. Of
the 6 new failures, three fail on the status assertion
(`assert 404 == 200` — `test_get_exam_templates_returns_the_catalogue`,
`test_get_exam_templates_on_an_unseeded_install_returns_an_empty_list`,
`test_exam_templates_route_does_not_shadow_or_get_shadowed`) and three fail with
`KeyError: 'templates'` because FastAPI's 404 body is `{"detail": "Not Found"}`
(`test_get_exam_templates_declares_every_field_the_picker_renders`,
`test_get_exam_templates_survives_null_phase_and_paper`,
`test_get_exam_templates_does_not_leak_the_json_blobs`). Both shapes mean the
same thing: the route does not exist yet. Write the observed counts down.

- [ ] **Step 3: Add `ExamTemplateModel` to `backend/models.py`**

Append after the `CorpusDocumentModel` class added in Task 4 (which is at the end
of `models.py`). `BaseModel` is already imported; no new imports are needed.

```python
class ExamTemplateModel(BaseModel):
    """One row of the phase/paper picker.

    Every numeric field is nullable because the live rows genuinely carry NULLs
    (CUSTOM has no phase, paper or cutoff) and response_model raises a 500 when a
    non-nullable field receives None. The three *_json columns and `notes` are
    deliberately undeclared: response_model strips them, which is how the raw JSON
    blobs stay inside the backend.
    """

    template_id: str
    exam: str
    name: str
    phase: int | None = None
    paper: int | None = None
    total_questions: int | None = None
    time_limit_minutes: int | None = None
    cutoff_pct: float | None = None
```

- [ ] **Step 4: Import the model in `backend/main.py`**

In the `from models import (...)` block, insert one line immediately after
`    ExamAnalyticsResponseModel,`:

```python
    ExamTemplateModel,
```

The block is alphabetical through `WeakTopicsResponseModel` and then becomes an
appended tail; `ExamTemplateModel` belongs between `ExamAnalyticsResponseModel`
and `HealthResponseModel` to keep the alphabetical run intact. Task 4 already
inserted `CorpusDocumentModel,` after `AnalyticsTimelineModel,` — do not disturb
it.

- [ ] **Step 5: Add the route**

Insert into `backend/main.py` between the end of `submit_mock` (line 1293,
`        raise HTTPException(status_code=400, detail=str(exc)) from exc`) and the
`@app.post("/api/exams/start", ...)` decorator at line 1296. Lines 1294-1295 are
blank; keep exactly two blank lines between the two functions.

```python
@app.get("/api/exam-templates", response_model=dict[str, list[ExamTemplateModel]])
def list_exam_templates_endpoint():
    """Phase/paper catalogue for the mock picker.

    Only templates that can actually generate an objective exam are returned --
    db.list_exam_templates filters out SUBJECT_DRILL and the two descriptive
    papers, whose allocation resolves to empty and would surface as a 500 from
    /api/exams/start. Sync def: the handler does blocking sqlite access, matching
    get_exam_template and the rest of this module's read endpoints.

    No pagination: the collection is bounded by the exam-pattern knowledge file
    (10 rows today, 7 after filtering). See the spec's API-design deviations.
    """
    return {"templates": [ExamTemplateModel(**row) for row in db.list_exam_templates()]}
```

`ExamTemplateModel(**row)` works with the full 15-key row because Pydantic v2's
default is `extra="ignore"` — the undeclared columns are dropped at construction,
and `response_model` would drop them again at serialization. Both layers agree,
so there is no silent-surprise gap.

Naming: the function is `list_exam_templates_endpoint`, **not**
`list_exam_templates`. `main.py` does `import database as db` and calls
`db.list_exam_templates()`, so there is no shadowing bug — but a bare
`list_exam_templates` in `main.py` would read as if it were the db function and
would collide the moment anyone writes `from database import *`. Operation IDs in
the generated OpenAPI schema are derived from the function name, and
`list_exam_templates_endpoint` keeps them unambiguous against
`/api/documents`'s `list_documents`.

- [ ] **Step 6: Run the tests and watch them pass**

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -m pytest tests/test_phase_exam_templates.py -v
```

Expected: **18 passed** (12 from Task 5 + 6 from Task 6), 0 failed.

If `test_get_exam_templates_declares_every_field_the_picker_renders` fails with a
`KeyError` or an `assert field in ifsca_p1` failure naming a field you *did*
declare, the route is returning the raw dicts rather than the models — check that
`response_model=` is spelled on the decorator and that the handler returns the
`{"templates": [...]}` envelope, not a bare list.

If it fails with **500**, read the server-side traceback: F2 means a `None` hit a
non-nullable annotation. Compare your `ExamTemplateModel` field-by-field against
the Step 3 listing.

- [ ] **Step 7: Verify the route is registered and the OpenAPI schema is honest**

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -c "
import main
paths = [r.path for r in main.app.routes]
print('/api/exam-templates registered:', '/api/exam-templates' in paths)
print('neighbours:', [p for p in paths if p.startswith('/api/exam') or p.startswith('/api/documents')])
schema = main.app.openapi()
props = schema['components']['schemas']['ExamTemplateModel']['properties']
print('declared fields:', sorted(props))
print('phase nullable:', props['phase'])
"
```

Expected, verified against the installed FastAPI 0.115.0 / Pydantic 2.13.4 with a
throwaway app of the same shape:

```
/api/exam-templates registered: True
neighbours: ['/api/documents', '/api/documents/{name}', '/api/exam-templates', '/api/exams/start', '/api/exams/{exam_id}/time-remaining', '/api/exams/{exam_id}/submit', '/api/exams/{exam_id}/aggregate', '/api/exams/{exam_id}/analytics']
declared fields: ['cutoff_pct', 'exam', 'name', 'paper', 'phase', 'template_id', 'time_limit_minutes', 'total_questions']
phase nullable: {'anyOf': [{'type': 'integer'}, {'type': 'null'}], 'title': 'Phase'}
```

Ordering within `neighbours` follows declaration order in `main.py`, so
`/api/exam-templates` appears before `/api/exams/start` only if you inserted the
route above it as Step 5 directs; either position is correct here. The `anyOf`
shape on `phase` is the proof that the nullable annotation survived into the
schema rather than being coerced to a bare `integer`.

Shadowing is structurally impossible for this route: every dynamic exam route
lives under the `/api/exams/` prefix, and `/api/exam-templates` does not start
with `/api/exams`. There is no `/api/{param}` catch-all anywhere in `main.py`.

- [ ] **Step 8: Live HTTP smoke against the real database**

Serves the real `backend/ifsca_exam.db`. Read-only.

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -c "
from fastapi.testclient import TestClient
import main, database as db
with TestClient(main.app) as c:
    r = c.get('/api/exam-templates')
    print('status:', r.status_code)
    body = r.json()
    print('count:', len(body['templates']))
    for t in body['templates']:
        print('  %-24s %-6s ph=%-5s pp=%-5s q=%-5s min=%-4s cut=%-5s keys=%d' % (
            t['template_id'], t['exam'], t['phase'], t['paper'],
            t['total_questions'], t['time_limit_minutes'], t['cutoff_pct'], len(t)))
"
```

Expected: `status: 200`, `count: 7`, seven lines in catalogue order, `CUSTOM`
showing `ph=None pp=None ... cut=None`, and **`keys=8` on every line** — proof
that the seven undeclared columns were stripped and the eight declared ones all
survived.

Using `with TestClient(...)` here (unlike conftest) **does** run `lifespan`, so
`db.init_db()` executes against the live DB. That is a no-op on an already
initialised path (`_INITIALIZED_DB_PATHS` guard plus the `DB_PATH.exists()`
check) and performs no writes beyond the idempotent migration scripts the app
runs on every normal startup. If you would rather not touch the live file at all,
skip this step — Steps 6 and 7 already prove the contract; this one only proves
it against production data.

- [ ] **Step 9: Commit**

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass" && git add backend/models.py backend/main.py backend/tests/test_phase_exam_templates.py && git -c user.name="Kartik Tomar" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "$(cat <<'EOF'
feat(api): expose GET /api/exam-templates for the phase/paper picker

ExamTemplateModel declares only the eight fields the picker renders. That is
load-bearing twice over: response_model silently strips the three raw *_json
columns so they never reach the browser, and every numeric field is nullable
because CUSTOM genuinely has NULL phase/paper/cutoff -- a non-nullable
declaration there would 500 on the picker's default option.

Sync def for the blocking sqlite read, no pagination because the collection is
bounded by the exam-pattern knowledge file.
EOF
)"
```

---

### Task 7: thread `template_id` through `/api/exams/start`

**Files:**
- Modify: `backend/main.py` — the `exam_start` handler (line 1296 before Task 6's
  insertion; Task 6 added ~20 lines above it, so locate it by the decorator
  `@app.post("/api/exams/start", dependencies=[Depends(gemini_spend_guard("exams:start"))])`
  rather than by number). Two edits: the `db.generate_smart_mock(...)` call and
  the `"time_limit_seconds": 3600,` entry in the returned dict.
- Modify: `backend/tests/test_phase_exam_templates.py` — append the spy helpers
  and 9 test items, and widen the module docstring.

**This is the fix for the silent-drop defect.** `exam.js:61-65` posts
`{exam_type, question_count, allocation_mode}`. `SmartMockRequestModel` declares
`{total_questions, mode, use_gemini, template}` with `extra="ignore"`. **Zero
field overlap** — so every value the user sets in the exam form is discarded
without an error, and `generate_smart_mock` is called with its own defaults. The
machinery to honour a template already exists (`database.py:4701` accepts
`template_id`, `_template_allocation` at 4640 resolves it); it is simply never
reached. Task 11 fixes the frontend's field names; this task makes the backend
actually consume the one field that matters.

**Why the time limit reads from the generator's result instead of a second
lookup.** `generate_smart_mock` already resolves it: `database.py:4866-4869` sets
`result["time_limit_minutes"] = template.get("time_limit_minutes") or 60` — and
sets it **only** when a template was used, because the `if template:` guard fails
for `CUSTOM` (the function looks the template up only when
`template_id != "CUSTOM"`, line 4710). So `result.get("time_limit_minutes") or 60`
reproduces today's hardcoded 3600 for `CUSTOM` exactly, and gives the real paper
length otherwise. Adding a `db.get_exam_template()` call in `exam_start` would
duplicate a query the generator has already made and create two places to keep in
sync.

**Why every test here monkeypatches `generate_smart_mock`.** Spec correction 8:
this worktree has **zero** Gemini keys (memory `ledger-worktree-no-gemini-keys`),
and `generate_smart_mock` raises `RuntimeError("Gemini is not available, so a
serious smart mock cannot be generated.")` at `database.py:4707-4708` before it
ever looks at `template_id`. An un-spied test fails with HTTP 500 for an
environmental reason and proves nothing about the forwarding fix. The spy is also
what makes these tests fast and deterministic — no thread pool, no network, no
question rows written.

**Deliberately not changed, with reasons:**

- **`"expected_time_sec": 180` and `"negative_marking": -1` stay hardcoded.**
  `generate_smart_mock` returns per-template `marks_per_question` and
  `negative_marking_per_wrong` (`database.py:4868-4869`) and it would be two more
  lines to forward them. But the submit path (`exam_submit`) applies **neither**
  per-template marks nor negative marking — spec line 316 records this as a known
  deviation. Advertising a template-specific penalty in the payload while the
  grader ignores it would make the UI promise something the score does not
  honour. Forwarding those two fields belongs with the scoring fix, not here.
- **No validation that `request.template` is in the catalogue.** A direct API
  caller can still post `template="SUBJECT_DRILL"` and get the misleading
  `"Mock allocation is empty; ingest the knowledge pack first."` 500. The picker
  built in Task 11 cannot produce that value, and adding a boundary check here
  would mean a second `get_exam_template` read per exam start to guard a path the
  UI never takes. The misleading message is a real defect and is recorded in the
  disclosed-deviations list at the end of this plan; it is not fixed here.

- [ ] **Step 1: Widen the module docstring**

At the top of `backend/tests/test_phase_exam_templates.py`, replace the Task 5
docstring with this one. The seeding note stays because it is still the reason
`_run_migration_005` appears in the helpers.

```python
"""Tests for the phase/paper exam feature: catalogue, endpoint, and exam start.

Covers three things that one feature depends on:
  1. db.list_exam_templates -- which templates can actually generate an exam.
  2. GET /api/exam-templates -- the wire contract the picker renders.
  3. POST /api/exams/start -- that the chosen template reaches generate_smart_mock
     and that the paper's own time limit replaces the hardcoded hour.

The conftest `test_db` fixture runs SCHEMA plus migration 002 only, and
TestClient is built without a context manager so `lifespan` (and therefore
db.init_db) never runs. exam_templates is created by migration 005, so tests
that need the table create and seed it via db._run_migration_005 -- the same
house pattern conftest uses for migration 002.

The exam-start tests monkeypatch db.generate_smart_mock. This worktree has no
Gemini keys, so the real function raises before it reads template_id; without
the spy these tests would fail environmentally and prove nothing.
"""
```

- [ ] **Step 2: Append the spy helpers and the 9 test items**

Add to the **end** of `backend/tests/test_phase_exam_templates.py`.

```python
# --- /api/exams/start: the chosen template must reach the generator ----------


def _install_generate_spy(
    monkeypatch, result: dict[str, Any]
) -> list[dict[str, Any]]:
    """Swap db.generate_smart_mock for a recorder and return the call log.

    main.py does `import database as db` and calls `db.generate_smart_mock(...)`,
    so patching the attribute on the database module is enough. monkeypatch undoes
    it at teardown, so nothing else in the 186-test suite sees the fake.
    """
    calls: list[dict[str, Any]] = []

    def spy(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return result

    monkeypatch.setattr(db, "generate_smart_mock", spy)
    return calls


def _answer_key_question(sample_question: dict[str, Any]) -> dict[str, Any]:
    """conftest's sample_question plus every field exam_start must strip.

    sample_question already carries correct_option, explanation and
    source_chunk_id; the seven added here complete the ten-field answer key so
    the strip test asserts on all of them rather than on a convenient subset.
    Every added key is a declared QuestionModel field, so model_validate accepts
    it and _coerce_question does not blow up before the strip loop runs.
    """
    question = dict(sample_question)
    question.update(
        {
            "source": "IFSCA Act 2019, Section 10",
            "source_document_id": "doc_001",
            "page_start": 5,
            "page_end": 6,
            "citation_note": "As amended by the 2023 notification.",
            "tested_fact": "fact_001",
            "trap_logic": "Confuses Section 10 with Section 15.",
        }
    )
    return question


def _fake_mock_result(
    question: dict[str, Any], time_limit_minutes: int | None = None
) -> dict[str, Any]:
    """Shaped like generate_smart_mock's return (database.py:4850-4870).

    `time_limit_minutes` is present only when a template was used, which mirrors
    the real `if template:` guard. Omitting it is therefore how the CUSTOM
    fallback gets exercised -- not by passing a sentinel value.
    """
    result: dict[str, Any] = {
        "mock_id": "SM_20260903_120000_abcd",
        "template_id": "CUSTOM",
        "allocation": {"PH2_IFSCA_ACT": 1},
        "allocation_summary": {
            "weak_topics_focused": 1,
            "medium_topics": 0,
            "strong_topics": 0,
            "weak_pct": "100.0%",
            "medium_pct": "0.0%",
            "strong_pct": "0.0%",
        },
        "weakness_analysis": [],
        "questions": [question],
    }
    if time_limit_minutes is not None:
        result["time_limit_minutes"] = time_limit_minutes
    return result


def test_exams_start_forwards_the_chosen_template_id(
    test_db: str, client, monkeypatch, sample_question
) -> None:
    """The regression test for the silent-drop defect: exam.js posts fields the
    model does not declare, they are ignored, and generate_smart_mock is called
    with its own defaults. Asserting on the spy's kwargs is the only way to see
    the value actually arrive."""
    _seed_templates(test_db)
    calls = _install_generate_spy(monkeypatch, _fake_mock_result(sample_question))
    response = client.post("/api/exams/start", json={"template": "IFSCA_PH2_P2_GENERAL"})
    assert response.status_code == 200
    assert calls[0]["template_id"] == "IFSCA_PH2_P2_GENERAL"


def test_exams_start_defaults_to_custom_when_no_template_is_chosen(
    test_db: str, client, monkeypatch, sample_question
) -> None:
    """Both an empty JSON body and no body at all must land on CUSTOM, which is
    what the endpoint does today. Verified on the installed FastAPI: an
    `X | None = None` body parameter yields None for a bodiless POST rather than
    a 422, and `request = request or SmartMockRequestModel()` supplies defaults."""
    _seed_templates(test_db)
    calls = _install_generate_spy(monkeypatch, _fake_mock_result(sample_question))
    assert client.post("/api/exams/start", json={}).status_code == 200
    assert calls[0]["template_id"] == "CUSTOM"
    assert client.post("/api/exams/start").status_code == 200
    assert calls[1]["template_id"] == "CUSTOM"


def test_exams_start_still_forwards_count_and_mode(
    test_db: str, client, monkeypatch, sample_question
) -> None:
    """Collateral-damage guard, not a red-green test: this passes before and after
    the fix. total_questions and mode were already forwarded correctly; adding
    template_id must not disturb them."""
    _seed_templates(test_db)
    calls = _install_generate_spy(monkeypatch, _fake_mock_result(sample_question))
    response = client.post(
        "/api/exams/start",
        json={"total_questions": 40, "mode": "amendment-heavy", "template": "SEBI_PH1_P1"},
    )
    assert response.status_code == 200
    assert calls[0]["total_questions"] == 40
    assert calls[0]["mode"] == "amendment-heavy"
    assert calls[0]["use_gemini"] is True


def test_exams_start_time_limit_comes_from_the_chosen_paper(
    test_db: str, client, monkeypatch, sample_question
) -> None:
    """SEBI Phase 1 Paper 2 is a 40-minute paper. The hardcoded 3600 gave every
    exam an hour, so the clock lied for every paper except one."""
    _seed_templates(test_db)
    _install_generate_spy(
        monkeypatch, _fake_mock_result(sample_question, time_limit_minutes=40)
    )
    response = client.post("/api/exams/start", json={"template": "SEBI_PH1_P2_GENERAL"})
    assert response.status_code == 200
    assert response.json()["time_limit_seconds"] == 2400


def test_exams_start_time_limit_falls_back_to_an_hour_for_custom(
    test_db: str, client, monkeypatch, sample_question
) -> None:
    """CUSTOM never resolves a template row inside generate_smart_mock, so the
    result carries no time_limit_minutes and the previous 3600 must survive
    unchanged. This is the no-behaviour-change half of the fix."""
    _seed_templates(test_db)
    _install_generate_spy(monkeypatch, _fake_mock_result(sample_question))
    response = client.post("/api/exams/start", json={"template": "CUSTOM"})
    assert response.status_code == 200
    assert response.json()["time_limit_seconds"] == 3600


def test_exams_start_still_strips_every_answer_key_field(
    test_db: str, client, monkeypatch, sample_question
) -> None:
    """The response is deliberately blind: an exam that ships its own answer key
    can be passed by reading the payload. Ten fields are popped and two Phase 3
    fields are added. Editing the return dict for the time limit must not disturb
    either half."""
    _seed_templates(test_db)
    _install_generate_spy(
        monkeypatch, _fake_mock_result(_answer_key_question(sample_question))
    )
    body = client.post("/api/exams/start", json={"template": "IFSCA_PH1_P1"}).json()
    question = body["questions"][0]
    for answer_key_field in (
        "correct_option",
        "explanation",
        "source",
        "source_document_id",
        "source_chunk_id",
        "page_start",
        "page_end",
        "citation_note",
        "tested_fact",
        "trap_logic",
    ):
        assert answer_key_field not in question, f"{answer_key_field} leaked"
    assert question["expected_time_sec"] == 180
    assert question["negative_marking"] == -1
    assert question["question_text"] == sample_question["question_text"]
    assert body["question_count"] == 1
    assert body["exam_id"] == "EXAM_" + body["mock_id"]


@pytest.mark.parametrize(
    "payload",
    [
        {"total_questions": 200},
        {"total_questions": 4},
        {"mode": "targeting_weighted"},
    ],
)
def test_exams_start_rejects_values_the_model_does_not_accept(
    test_db: str, client, monkeypatch, sample_question, payload: dict[str, Any]
) -> None:
    """Pins the two constraints that forced spec corrections 1 and 2, so the
    frontend cannot drift back into them. Verified on the installed FastAPI:
    total_questions is ge=5 le=100 (200 and 4 both 422, 100 is accepted) and mode
    is a four-value Literal that does not include "targeting_weighted".

    The index.html number input still says max="200" at this point in the plan;
    Task 11 corrects it to max="100". If that task is skipped, a user who drags
    the slider to the top gets a 422 and the exam never starts.
    """
    _seed_templates(test_db)
    _install_generate_spy(monkeypatch, _fake_mock_result(sample_question))
    assert client.post("/api/exams/start", json=payload).status_code == 422
```

- [ ] **Step 3: Run the new tests and watch exactly three fail**

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -m pytest tests/test_phase_exam_templates.py -q
```

Expected: **27 collected, 24 passed, 3 failed.** The three failures are the red
half of the red-green cycle:

| Test | Pre-fix failure |
|---|---|
| `test_exams_start_forwards_the_chosen_template_id` | `KeyError: 'template_id'` — the kwarg is never passed |
| `test_exams_start_defaults_to_custom_when_no_template_is_chosen` | `KeyError: 'template_id'` — same cause |
| `test_exams_start_time_limit_comes_from_the_chosen_paper` | `assert 3600 == 2400` — the hardcoded hour |

The other six items added in Step 2 **pass before the fix as well as after**, and
that is deliberate: `test_exams_start_still_forwards_count_and_mode`,
`test_exams_start_time_limit_falls_back_to_an_hour_for_custom`,
`test_exams_start_still_strips_every_answer_key_field` and the three parametrized
rejection cases are guards against collateral damage, not evidence of the defect.
Six new passes plus eighteen existing ones is where the 24 comes from.

If **more** than three fail, a guard has caught something you broke while writing
the tests — read it before continuing. If **fewer** than three fail, the defect
this task exists to fix is not the defect in your tree; stop and reconcile against
`main.py`'s `exam_start` before editing it.

- [ ] **Step 4: Forward `template_id` in `backend/main.py`**

In `exam_start`, change the generator call from

```python
        result = db.generate_smart_mock(
            total_questions=request.total_questions,
            mode=request.mode,
            use_gemini=True,
        )
```

to

```python
        result = db.generate_smart_mock(
            total_questions=request.total_questions,
            mode=request.mode,
            use_gemini=True,
            template_id=request.template,
        )
```

One added line. `generate_smart_mock`'s signature already accepts
`template_id: str = "CUSTOM"` (`database.py:4705`), so nothing else in the
backend needs to change for this edit to be valid.

- [ ] **Step 5: Derive the time limit from the chosen paper**

In the same handler's return dict, change

```python
            "time_limit_seconds": 3600,
```

to

```python
            # generate_smart_mock resolves the chosen paper's own limit
            # (database.py:4867) and omits the key for CUSTOM, so `or 60`
            # reproduces the previous hardcoded hour exactly.
            "time_limit_seconds": int(result.get("time_limit_minutes") or 60) * 60,
```

Do **not** introduce a `db.get_exam_template(request.template)` call here — see
the rationale at the top of this task. Do **not** touch `"expected_time_sec": 180`
or `"negative_marking": -1` two lines above; the reasons are in the
"Deliberately not changed" list.

- [ ] **Step 6: Update the handler docstring**

`exam_start`'s docstring currently reads:

```python
    """Start a new exam session with adaptive mock generation.

    Per PROJECT_REFACTOR_PLAN.xml Phase 3: Return 50 questions with:
    - Standard fields (question_text, options, difficulty)
    - expected_time_sec: Time user should spend (~3 min default)
    - negative_marking: Penalty for wrong answer (-1 points)
    """
```

Replace it with:

```python
    """Start a new exam session with adaptive mock generation.

    `template` selects the paper: CUSTOM keeps the adaptive allocation, while a
    phase/paper template id routes the question split through
    _template_allocation and sets the clock from that paper's own time limit.

    Per PROJECT_REFACTOR_PLAN.xml Phase 3: Return the questions with:
    - Standard fields (question_text, options, difficulty)
    - expected_time_sec: Time user should spend (~3 min default)
    - negative_marking: Penalty for wrong answer (-1 points)

    The response is blind: the ten answer-key fields are stripped so the exam
    cannot be passed by reading the payload.
    """
```

"Return 50 questions" becomes "Return the questions" because the count is now
`request.total_questions`, which the picker sets from the chosen paper (100 for
IFSCA Phase I Paper 1, 80 for SEBI Phase 1 Paper 1, 50 for the Paper 2s).

- [ ] **Step 7: Run the tests and watch them pass**

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -m pytest tests/test_phase_exam_templates.py -v
```

Expected: **27 passed**, 0 failed.

If `test_exams_start_time_limit_comes_from_the_chosen_paper` still reports 3600,
the `or 60` fallback is swallowing a real value — check that you wrote
`result.get("time_limit_minutes")` and not `result.get("time_limit_seconds")`, and
that `int(...)` wraps only the minutes.

- [ ] **Step 8: Prove the forwarding test is not vacuous**

Revert Step 4 only (delete the `template_id=request.template,` line) and re-run:

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -m pytest tests/test_phase_exam_templates.py -q
```

Expected: **2 failures** — the two `KeyError: 'template_id'` tests. Note that
`test_exams_start_time_limit_comes_from_the_chosen_paper` still **passes** here,
because the spy supplies `time_limit_minutes` regardless of what the handler sent.
That is the honest limit of this suite: the spy proves the value travels from
handler to generator, and Task 15's browser-walk is what proves the real
generator honours it. Restore the line and confirm **27 passed** again.

- [ ] **Step 9: Commit**

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass" && git add backend/main.py backend/tests/test_phase_exam_templates.py && git -c user.name="Kartik Tomar" -c user.email="hrkartiktomar-netizen@users.noreply.github.com" commit -m "$(cat <<'EOF'
fix(api): forward the chosen paper to generate_smart_mock from /api/exams/start

SmartMockRequestModel declares {total_questions, mode, use_gemini, template} with
extra=ignore, and the handler passed only the first three -- so the template
machinery in generate_smart_mock/_template_allocation was never reached and every
exam got an adaptive CUSTOM allocation plus a hardcoded hour, whatever the user
picked. SEBI Phase 1 Paper 2 is a 40-minute paper; the clock lied for it.

The limit now reads result["time_limit_minutes"], which generate_smart_mock
already resolves from the template row and omits for CUSTOM, so `or 60` keeps
today's 3600 for the default path instead of adding a second lookup.

Tests monkeypatch the generator: this worktree has no Gemini keys, so the real
one raises before reading template_id and an un-spied test would prove nothing.
EOF
)"
```

---

### Task 8: backend regression gate

**Files:** none — this task changes nothing. It is a gate. **Do not proceed to
Task 9 with a red gate.**

Everything the browser can see in Tasks 9-13 depends on the six commits from
Tasks 2-7 being sound. Frontend work on top of a broken backend produces
symptoms that look like frontend bugs, and debugging them costs far more than
this gate does. The gate is also the only place in the plan where the
`verification-before-completion` rule gets applied to the backend as a whole
rather than to one file at a time.

`$BASE` below means the commit SHA Task 1 recorded — `ba8783b1` at
plan-authoring time. Substitute your own; a stale SHA makes every diff in this
task meaningless.

- [ ] **Step 1: Run the whole suite and compare against the baseline**

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -m pytest -q 2>&1 | tail -20
```

Expected: **186 passed, 0 failed, 0 errors.** The arithmetic, so a different
number can be diagnosed rather than shrugged at:

| Source | Items |
|---|---|
| Baseline (Task 1, measured: `134 passed in 71.82s`) | 134 |
| `tests/test_amendment_relocation.py` — new, Tasks 2 (3) + 3 (9) + 4 (13) | 25 |
| `tests/test_phase_exam_templates.py` — new, Tasks 5 (12) + 6 (6) + 7 (9) | 27 |
| **Total** | **186** |

**Zero pre-existing tests may change state.** If the total is 186 but the split
is wrong — say 187 passed with one pre-existing test now failing and two new ones
missing — the arithmetic above is how you tell. If a *pre-existing* test fails,
that is a regression: stop, run
`python -m pytest <that test> -v` on its own, and use
`superpowers:systematic-debugging` before touching anything else. Do not "fix" it
by editing the pre-existing test.

Respect the known flakes from memory `ledger-test-env-gotchas`: never run
anything concurrently with the wall-clock performance test, and if a run fails
*only* in teardown, re-run once before believing it.

- [ ] **Step 2: Prove no pre-existing test file was edited**

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass" && git diff --stat $BASE..HEAD -- backend/tests/conftest.py backend/tests/test_e2e_correctness.py backend/tests/test_e2e_workflows.py backend/tests/test_phase6_intelligence.py backend/tests/test_regressions.py backend/tests/test_update_tracker.py && echo "(empty above = clean)"
```

Expected: **no output** before the `(empty above = clean)` line. Any diffstat
here means a pre-existing test or the shared fixture was modified to make the
suite pass — which is how a real regression gets hidden. Revert it and fix the
code instead.

This also guards a specific hazard: `conftest.py`'s `test_db` fixture is shared by
all 186 tests. Editing it to create `exam_templates` globally would have been the
lazy fix for F10, and would have changed the fixture every other test file sees.
Task 5 seeds through a local helper instead, precisely so this diff stays empty.

- [ ] **Step 3: Prove the production diff is exactly six files**

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass" && git diff --name-status $BASE..HEAD
```

Expected — exactly these six, and nothing else:

```
M       backend/database.py
A       backend/document_store.py
M       backend/main.py
M       backend/models.py
A       backend/tests/test_amendment_relocation.py
A       backend/tests/test_phase_exam_templates.py
```

`M` = modified, `A` = added. Anything beyond this list is unplanned surface.
In particular: **no frontend file may appear yet** (Tasks 9-13 own those), **no
`start.bat`** (Task 16 owns it, strictly last), **no `backend/.env` or
`.env.example`** (Task 14 owns those), and **no migration file** — this plan adds
no schema.

- [ ] **Step 4: Prove the Task 5 red-green break was restored**

Task 5 Step 5 deliberately changed `_template_is_objective_ready`'s last line to
`return True` to prove the exclusion tests bite. If that edit was left in place
the suite would still show failures — but this check catches the case where it was
only partly restored, or restored in the wrong copy of the tree.

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass" && git diff $BASE..HEAD -- backend/database.py | grep -n "return True" && echo "^^ inspect each hit" ; grep -n -A2 'return bool(json.loads(template.get("syllabus_units_json")' backend/database.py
```

Expected: the `grep -n -A2` at the end prints exactly one hit, showing

```
    return bool(json.loads(template.get("syllabus_units_json") or "[]"))
```

as the final line of `_template_is_objective_ready`. Any `return True` in the diff
must be inside an unrelated hunk — read each one and confirm it is not the
predicate's last line.

- [ ] **Step 5: Prove the app still imports and both new routes are registered**

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/backend" && python -c "import main; print('import main: OK')" && python -c "
import main
paths = [r.path for r in main.app.routes]
for expected in ('/api/documents/{name}', '/api/exam-templates'):
    print(expected, '->', expected in paths)
print('total routes:', len(paths))
print('response_model count:', sum(1 for r in main.app.routes if getattr(r, 'response_model', None) is not None))
"
```

Expected: `import main: OK` with no traceback and no warning output;
`/api/documents/{name} -> True`; `/api/exam-templates -> True`;
`total routes: 108`; `response_model count: 37`.

Both baseline figures were measured during plan authoring on a clean tree at
`ba8783b1`: **106 routes** and **35 `response_model` declarations**, the latter
confirmed two ways — `grep -c "response_model=" backend/main.py` and the runtime
count of routes whose `response_model` attribute is not `None` both returned 35.
Task 4 adds one route and one model; Task 6 adds one route and one model; Task 7
adds neither, because `exam_start` stays blind and deliberately unmodelled. So
each count rises by exactly two, and a rise of one or three means a task was
skipped or an extra endpoint appeared.

If your own Task 1 baseline differs from 106/35, compare against **your**
baseline plus two rather than against 108/37.

To re-read the baseline without moving the branch:

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass" && git show $BASE:backend/main.py | grep -c "response_model="
```

Expected: `35`. Do **not** check out `$BASE` in this worktree — six commits of
work sit on top of it, and memory `ledger-award-execution-hazards` records that
concurrent automations in this repo have triggered rebase operations. Read the
baseline with `git show`; never move the branch to get it.

- [ ] **Step 6: Prove the JS files are still syntactically valid**

Tasks 2-7 touch no frontend file, so this is a tripwire, not a test: if it fails,
something outside the plan edited the frontend.

```bash
cd "D:/Exam_preparation/.worktrees/ledger-award-pass/frontend" && for f in js/api.js js/views.js js/exam.js js/today.js js/router.js; do node --check "$f" && echo "OK $f"; done
```

Expected: five `OK js/...` lines, no `SyntaxError`.

- [ ] **Step 7: Record the gate result**

Write down, in your working notes for this execution:

- the exact final line of the suite (`186 passed in Xs`),
- the six-file `--name-status` list,
- the route and `response_model` counts,
- the SHA of the Task 7 commit (Task 18's PR description needs the range
  `$BASE..<that SHA>`).

There is nothing to commit. If every step above is green, the backend is done and
Tasks 9-13 can build on it. If any step is red, fix it inside the relevant task
and re-run this whole gate — a partially green gate is a red gate.

---
