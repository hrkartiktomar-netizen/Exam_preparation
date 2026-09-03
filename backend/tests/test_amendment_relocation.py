"""Amendment relocation: the read-time ledger filter and corpus document serving.

The test_db fixture (conftest.py:23-80) points db.DB_PATH at a temp file but does
not run migration 005 or bootstrap_from_knowledge(), so the amendments table is
created empty by whichever handler calls init_db() first (F10). Rows are inserted
explicitly here rather than assumed to exist.
"""

from __future__ import annotations

import sqlite3

import pytest

import database as db
import document_store

# Built with chr() rather than written as literals: the backslash form has to
# survive unchanged through the source file, and a NUL byte is not representable
# as a literal at all.
BACKSLASH = chr(92)
NUL = chr(0)


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
