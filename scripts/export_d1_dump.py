"""Export the local SQLite database as a Cloudflare D1 compatible SQL dump.

D1 (via `wrangler d1 execute --file`) rejects transaction control and
SQLite-internal statements that `sqlite3 .dump` emits, so this script filters
them out of `iterdump()` output.

Usage:
    python scripts/export_d1_dump.py [--db data/agent.db] [--out data/d1_dump.sql]

Then import into D1:
    npx wrangler d1 execute <DB_NAME> --remote --file=data/d1_dump.sql
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SKIP_PREFIXES = (
    "BEGIN TRANSACTION",
    "COMMIT",
    "PRAGMA ",
    "DELETE FROM sqlite_sequence",
    "INSERT INTO sqlite_sequence",
    'INSERT INTO "sqlite_sequence"',
    "CREATE TABLE sqlite_sequence",
)


def export(db_path: Path, out_path: Path) -> int:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    conn = sqlite3.connect(db_path)
    count = 0
    try:
        with out_path.open("w", encoding="utf-8") as handle:
            for line in conn.iterdump():
                if line.upper().startswith(tuple(p.upper() for p in SKIP_PREFIXES)):
                    continue
                handle.write(line)
                handle.write("\n")
                count += 1
    finally:
        conn.close()
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(BASE_DIR / "data" / "agent.db"))
    parser.add_argument("--out", default=str(BASE_DIR / "data" / "d1_dump.sql"))
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = export(Path(args.db), out_path)
    print(f"Wrote {count} statements to {out_path}")
    print(f"Import with: npx wrangler d1 execute <DB_NAME> --remote --file={out_path}")


if __name__ == "__main__":
    main()
