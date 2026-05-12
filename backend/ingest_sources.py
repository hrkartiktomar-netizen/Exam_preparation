"""Command-line entry point for ingesting the local PDF text corpus."""

from __future__ import annotations

import argparse
import json

import database


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest extracted IFSCA PDF text into SQLite FTS tables.")
    parser.add_argument("--force", action="store_true", help="Rebuild document/chunk rows even if already indexed.")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for a quick test run.")
    args = parser.parse_args()

    database.init_db()
    result = database.ingest_documents(force=args.force, limit=args.limit)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

