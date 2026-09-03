# ADR-0001: Serve corpus documents via a basename-allowlisted read-only route

**Status**: Accepted
**Date**: 2026-09-03
**Deciders**: Kartik Tomar

## Context

The Amendment Intelligence tab lists statute and regulation changes sourced from 211 Markdown
files under `source_documents/md/**`, across 10 bucket directories. Users asked to read the actual
source document behind each amendment row rather than trusting a summary.

Nothing in the application serves that corpus today. `ingest_extracted_pdfs` (`database.py:1802`)
reads `extracted_pdfs/*.txt` only, and no static mount exposes `source_documents/`. The stored
`source_url` values are bare `.md` basenames such as `IFSCA_TAS_Final_Regulations_2025.md`.

Any route that turns a client-supplied string into a filesystem path is a traversal risk. The
backend also writes to a live sqlite database and calls a paid Gemini API, so it is not a
zero-consequence process.

## Decision

Add `GET /api/documents/{name}` with these properties:

- The path parameter is a **basename only** and must end in `.md`.
- Resolution happens against an index built by walking the allowlisted `source_documents/md/**`
  tree. A name is servable only if that walk found it. No client input ever joins a path.
- Any separator, `..`, absolute path, or non-`.md` extension returns **404** — the same status as
  a well-formed name that simply does not exist.
- Read-only. No write, list, or delete surface over the corpus.
- Resolution and reading live in a new `backend/document_store.py`, not in the 3168-line
  `main.py` controller, so the security boundary is unit-testable in isolation.

## Considered options

- **Mount `source_documents/` with `StaticFiles`.** Rejected: exposes all 211 files plus any
  future addition to unauthenticated enumeration, with no way to return the `bucket`/`lines`
  metadata the reader UI wants, and no control over extension.
- **Accept a relative path and normalise it.** Rejected: normalisation is exactly where traversal
  bugs live. An allowlist of names discovered by our own walk has no such surface.
- **Return 400 for malformed input and 404 only for unknown names.** Rejected: the split is an
  existence oracle. It tells a prober which input shapes reached the resolver, enabling
  enumeration of the allowlist. Uniform 404 leaks nothing.

## Consequences

**Good**: no traversal surface, because client input never constructs a path. No corpus
enumeration endpoint. The boundary is a small module with table-driven tests. Response shape is
fixed by a declared `CorpusDocumentModel`, so FastAPI cannot silently strip a field the frontend
reads.

**Bad**: the design depends on basenames being unique within the corpus. That holds today —
verified, zero duplicates among the 211 files — but it is a property of the data, not something
the route enforces, so it could break if the corpus grows. The index is built lazily and cached,
so a newly added `.md` file requires a server restart to become visible. Serving a whole file
means up to ~330KB per response.

The allowlist also spans all ten buckets, including `10_Unrelated_RRB_Documents`, whose contents
are not relevant to these exams. Those files are therefore technically servable. No amendment row
points at them, so nothing surfaces them in the UI, and narrowing the allowlist risked 404ing a
legitimate source for no real benefit. Disclosed rather than silently accepted.

**Mitigations**: duplicate basenames are detected when the index is built and the collision is
logged rather than silently shadowed, so a future corpus change surfaces instead of picking an
arbitrary file. The cache trade-off is acceptable for a local single-user tool. Response size is
bounded by the corpus itself and is fine over loopback.

## Related

- Design spec: `docs/superpowers/specs/2026-09-03-home-amendment-relocation-phase-mocks-design.md`, Section 3b.
- ADR-0003 also assumes loopback-only binding, which is what makes the absent rate limit acceptable.
