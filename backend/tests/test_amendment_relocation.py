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
