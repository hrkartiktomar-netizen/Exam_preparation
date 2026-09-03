# ADR-0002: Filter LOCAL_FALLBACK amendment rows at read time, never delete

**Status**: Accepted
**Date**: 2026-09-03
**Deciders**: Kartik Tomar

## Context

The Amendment Intelligence tab is meant to be a reading list of real statutory changes. The live
database holds 39 `amendments` rows: 15 `SEEDED` and 13 `PACK_SEEDED` rows that are genuine
(real titles, effective dates spanning 2024-06-04 to 2026-09-30, topics, and `new_value` text),
plus **11 `LOCAL_FALLBACK` rows that are junk**. Every junk row is titled "Manual review required"
and its summary is raw RBI HTML navigation markup or `%PDF-1.6%` binary prefix — the residue of a
scrape that failed to extract text.

`amendment_updates` holds 0 rows, so `/api/updates` (`main.py:3029-3053`) falls back to
`db.list_curated_amendments`. Sorted `date_desc`, the junk occupies positions 2 through 12 — the
user's reading list is mostly noise, and the row count displayed is dishonest.

The same poller that produced these rows can produce more, so any fix must not assume a one-off
cleanup.

## Decision

Drop rows whose `verification_status == "LOCAL_FALLBACK"` inside `get_updates`, **after both
sources resolve**, so the filter covers the tracker feed and the corpus fallback identically.

The rows are **not deleted** from the database. `/api/updates/status` continues to count them.

## Considered options

- **`DELETE FROM amendments WHERE verification_status='LOCAL_FALLBACK'`.** Rejected: irreversible
  destruction of evidence about a failing scraper, and the poller would simply recreate the rows,
  so it is not even a durable fix.
- **Filter only the corpus-fallback branch.** Rejected: leaves junk visible whenever the tracker
  feed has rows, so the defect reappears under normal operation.
- **Fix the poller so it never writes unextractable content.** Correct as a root-cause fix, but a
  larger change to `update_tracker.py` and `amendment_poller.py`, and it does nothing about the 11
  rows already stored. Worth doing separately; it does not replace this decision.
- **Filter in SQL.** Viable, but the two sources are assembled in Python before the response is
  built, so a single post-resolution filter is fewer moving parts and cannot diverge between
  branches.

## Consequences

**Good**: the reading list becomes honest — 28 real rows instead of 39 mixed ones. The evidence
that the scraper produced garbage is preserved for diagnosis. Reversible by removing one filter.
No migration, no data loss.

**Bad**: `/api/updates` and `/api/updates/status` now report different counts (28 shown, 39
counted). That is intentional — the status endpoint is a health signal about the pipeline, not a
display count — but it can read as an inconsistency to someone who does not know why.

**Mitigations**: the divergence is asserted in tests so it cannot drift silently, and the reason
is recorded here. The underlying poller defect stays visible in project notes as separate work.

## Related

- Design spec: `docs/superpowers/specs/2026-09-03-home-amendment-relocation-phase-mocks-design.md`, Section 3a.
- ADR-0001 makes the surviving rows actionable by serving the source document behind each one.
