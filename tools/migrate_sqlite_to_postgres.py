from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

try:
    import psycopg
except Exception as exc:  # pragma: no cover
    raise SystemExit("psycopg is required. Run: pip install 'psycopg[binary]'") from exc

TABLES = [
    ("sales_projects", "project_id"),
    ("operation_orders", "order_no"),
    ("event_logs_v2", "event_id"),
    ("meeting_snapshots_v2", "snapshot_id"),
    ("import_batches", "batch_id"),
]


def quote_columns(columns: list[str]) -> str:
    return ", ".join(columns)



def copy_table(sqlite_conn: sqlite3.Connection, pg_conn, table_name: str, pk_name: str) -> int:
    sqlite_cur = sqlite_conn.cursor()
    sqlite_cur.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cur.fetchall()
    if not rows:
        return 0

    columns = [description[0] for description in sqlite_cur.description]
    placeholders = ", ".join(["%s"] * len(columns))
    assignments = ", ".join(f"{col}=EXCLUDED.{col}" for col in columns if col != pk_name)
    insert_sql = (
        f"INSERT INTO {table_name} ({quote_columns(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT ({pk_name}) DO UPDATE SET {assignments}"
    )

    with pg_conn.cursor() as cur:
        for row in rows:
            cur.execute(insert_sql, tuple(row))
    pg_conn.commit()
    return len(rows)



def main() -> None:
    parser = argparse.ArgumentParser(description="Copy local SQLite tracker data into PostgreSQL.")
    parser.add_argument("--sqlite-path", default="project_tracker.db", help="Path to the local SQLite database file.")
    parser.add_argument("--database-url", required=True, help="Target PostgreSQL DATABASE_URL.")
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite_path).resolve()
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite file not found: {sqlite_path}")

    os.environ["DATABASE_URL"] = args.database_url
    from database.schema import init_db  # import after env is set

    init_db()

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = psycopg.connect(args.database_url)

    try:
        total = 0
        for table_name, pk_name in TABLES:
            copied = copy_table(sqlite_conn, pg_conn, table_name, pk_name)
            total += copied
            print(f"{table_name}: copied {copied} row(s)")
        print(f"Done. Total copied rows: {total}")
    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    main()
