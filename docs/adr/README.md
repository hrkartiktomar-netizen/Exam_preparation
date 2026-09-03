# Architecture Decision Records

Lightweight ADRs for the IFSCA/SEBI exam-preparation engine. Format follows the "Lightweight ADR"
template: Status, Context, Decision, Consequences. Kept to roughly one page each.

## Index

| ADR | Title | Status | Date |
| --- | ----- | ------ | ---- |
| [0001](0001-corpus-document-route-basename-allowlist.md) | Serve corpus documents via a basename-allowlisted read-only route | Accepted | 2026-09-03 |
| [0002](0002-filter-local-fallback-at-read-time.md) | Filter LOCAL_FALLBACK amendment rows at read time, never delete | Accepted | 2026-09-03 |
| [0003](0003-gemini-keys-as-user-environment-variables.md) | Resolve Gemini keys from user-level environment variables | Accepted | 2026-09-03 |

## Creating a new ADR

1. Copy an existing file to `NNNN-title-with-dashes.md`.
2. Fill in Status, Context, Decision, Consequences. Include the options you rejected and why.
3. Add a row to the index above.

## Status values

- **Proposed** — under discussion
- **Accepted** — decided, being implemented
- **Deprecated** — no longer relevant
- **Superseded** — replaced by a later ADR (link it)
- **Rejected** — considered and not adopted

Never edit an accepted ADR to change the decision. Write a new one and mark the old as superseded.
