# ADR-0003: Resolve Gemini keys from user-level environment variables

**Status**: Accepted
**Date**: 2026-09-03
**Deciders**: Kartik Tomar

## Context

Gemini is mandatory for mock generation: `db.generate_smart_mock` (`database.py:4701`) raises
unless `use_gemini` is true, and `/api/exams/start` hardcodes it. With no keys loaded,
`gemini_available()` returns False and exam generation cannot work at all.

The repository now has two working trees — the main checkout and the
`feature/ledger-award-pass` worktree — and more may follow. Verified state:

- The worktree has **no** `backend/.env`. Only `.env.example`. Importing `gemini_integration`
  there resolves zero keys, and no `GEMINI`/`GOOGLE` variable exists in the OS environment either.
- The main tree has a real `backend/.env` using `GEMINI_KEY_1..9`.
- `gemini_integration.py:137-138` reads `GEMINI_KEY` and `GEMINI_KEY_1..50`.
- `backend/.env.example` documents `GEMINI_API_KEY_1..5` — names **nothing in the code reads**. It
  also calls `PORT` a "Flask server port"; this is FastAPI, and `main.py` never reads `PORT`.
  Following the template yields a silently key-less app with no startup error.
- `gemini_integration.py:131-132` loads `.env` into `os.environ` **only if the key is not already
  set**, so OS-level variables take precedence over any `.env` file.
- `.gitignore:18` covers `backend/.env` and `.gitignore:21` covers `*.db`.

Because `DB_PATH` is tree-relative (`database.py:27`), each tree keeps its own database, but keys
are the same credentials everywhere.

## Decision

Publish the nine keys plus `GEMINI_MODEL`, `GEMINI_MODEL_MOCK`, `GEMINI_MODEL_ACCURACY`,
`GEMINI_THINKING_LEVEL`, `GEMINI_MOCK_THINKING`, `GEMINI_ACCURACY_THINKING`, and
`UPDATE_TRACK_INTERVAL_HOURS` as **Windows user-level environment variables** in
`HKCU\Environment`, sourced once from the main tree's working `.env`.

- Written by a one-shot Python step using `winreg`, then broadcast via `WM_SETTINGCHANGE`.
- Only key names and value lengths are ever printed. Values are never echoed, never placed on a
  command line, and never written into the repository.
- `start.bat` stops testing for the existence of `backend/.env` and instead reads `GET /health`
  (`main.py:581-599`), which already reports `api_keys_loaded`, `gemini_available`,
  `central_ai_ready`, and `database_initialized`. Zero keys produces a loud warning naming the
  endpoints that will fail.
- `backend/.env.example` is corrected to the real `GEMINI_KEY_N` names and documented as optional.

## Considered options

- **Copy the main tree's `.env` into each worktree.** Rejected: N copies of a rotating 9-key set,
  guaranteed to drift, and every copy is another secret sitting in a directory that could be
  zipped, synced, or committed by a tool that does not respect `.gitignore`.
- **`setx GEMINI_KEY_1 <value>`.** Rejected: places live secrets on the command line, in process
  arguments, and in shell history.
- **Keep the file-existence check and require a per-tree `.env`.** Rejected: it is a false
  blocker. It tests for a file, not for working credentials, and it currently makes `start.bat`
  exit 1 immediately in the worktree.
- **Store keys in the database.** Rejected: puts credentials in a file matched by `*.db` that is
  routinely copied between trees and inspected during debugging.

## Consequences

**Good**: one source of truth for every tree, present and future. Precedence already favours OS
variables, so main-tree behaviour is unchanged (identical values). No secret file is created
anywhere in the repository, so there is nothing to accidentally commit. `start.bat`'s key check
becomes semantic — it verifies credentials actually loaded, not that a file exists.

**Bad**: user-level variables are readable by every process running as this user, which is
broader exposure than a file inside the repo directory (though not world-readable). The change is
persistent across reboots. Already-running processes — including the server currently on :8020 —
do not see it until restarted, so verification requires a fresh launch. Per-tree key sets become
awkward, since the OS value wins over any local `.env`.

**Mitigations**: reversible by deleting those registry values. Keys are rotated through a pool
already, so a leak of one is survivable. Where a tree genuinely needs different keys, set them in
that shell session before launching, which overrides the user-level value.

## Related

- Design spec: `docs/superpowers/specs/2026-09-03-home-amendment-relocation-phase-mocks-design.md`, Section 5.
- ADR-0001's absent rate limit assumes the loopback-only binding that this same `start.bat` rewrite introduces.
