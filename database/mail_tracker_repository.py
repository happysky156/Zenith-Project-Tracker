from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import uuid4

import pandas as pd

from database.connection import execute, get_connection


def ensure_mail_tracker_tables() -> None:
    """Create isolated Mail Tracker storage tables.

    These tables are intentionally separate from Sales / Operation / Meeting records.
    Other modules can link to these records later, but this import does not update
    formal project/order fields.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS mail_tracker_import_batches (
                batch_id TEXT PRIMARY KEY,
                source_file TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                imported_by TEXT,
                workbook_sha256 TEXT,
                sheet_count INTEGER NOT NULL DEFAULT 0,
                row_count INTEGER NOT NULL DEFAULT 0,
                notes TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS mail_tracker_rows (
                row_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                sheet_name TEXT NOT NULL,
                source_row INTEGER,
                row_json TEXT NOT NULL,
                detected_project_id TEXT,
                detected_order_no TEXT,
                detected_client_code TEXT,
                detected_date TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _detect_value(row: dict[str, Any], tokens: list[str]) -> str:
    for key, value in row.items():
        name = str(key).lower()
        if any(token in name for token in tokens):
            cleaned = _clean(value)
            if cleaned:
                return cleaned
    return ""


def _detect_date(row: dict[str, Any]) -> str:
    for key, value in row.items():
        name = str(key).lower()
        if any(token in name for token in ["date", "time", "sent", "received", "created"]):
            try:
                parsed = pd.to_datetime(value, errors="coerce")
                if pd.notna(parsed):
                    return parsed.isoformat()
            except Exception:
                pass
            cleaned = _clean(value)
            if cleaned:
                return cleaned
    return ""


def save_mail_tracker_workbook(
    workbook: dict[str, pd.DataFrame],
    *,
    source_file: str,
    imported_by: str = "",
    file_bytes: bytes | None = None,
    notes: str = "",
) -> dict[str, Any]:
    ensure_mail_tracker_tables()
    batch_id = f"mail-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    imported_at = datetime.utcnow().isoformat(timespec="seconds")
    workbook_sha256 = hashlib.sha256(file_bytes or b"").hexdigest() if file_bytes is not None else ""
    sheet_count = len(workbook or {})
    row_count = sum(len(df) for df in (workbook or {}).values() if isinstance(df, pd.DataFrame))

    with get_connection() as conn:
        cur = conn.cursor()
        execute(
            cur,
            """
            INSERT INTO mail_tracker_import_batches
            (batch_id, source_file, imported_at, imported_by, workbook_sha256, sheet_count, row_count, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (batch_id, source_file, imported_at, imported_by, workbook_sha256, sheet_count, row_count, notes),
        )
        inserted = 0
        for sheet_name, df in (workbook or {}).items():
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            clean_df = df.fillna("")
            for index, row in clean_df.iterrows():
                row_dict = {str(k): _clean(v) for k, v in row.to_dict().items()}
                execute(
                    cur,
                    """
                    INSERT INTO mail_tracker_rows
                    (row_id, batch_id, sheet_name, source_row, row_json, detected_project_id,
                     detected_order_no, detected_client_code, detected_date, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid4().hex,
                        batch_id,
                        str(sheet_name),
                        int(index) + 2,
                        json.dumps(row_dict, ensure_ascii=False, default=str),
                        _detect_value(row_dict, ["project id", "project_id", "project"]),
                        _detect_value(row_dict, ["order no", "order_no", "po", "order"]),
                        _detect_value(row_dict, ["client code", "client_code", "client"]),
                        _detect_date(row_dict),
                        imported_at,
                    ),
                )
                inserted += 1
        conn.commit()
    return {"batch_id": batch_id, "sheet_count": sheet_count, "row_count": row_count, "inserted_rows": inserted}


def list_mail_tracker_batches(limit: int = 10) -> list[dict[str, Any]]:
    ensure_mail_tracker_tables()
    with get_connection() as conn:
        cur = conn.cursor()
        execute(
            cur,
            """
            SELECT batch_id, source_file, imported_at, imported_by, workbook_sha256, sheet_count, row_count, notes
            FROM mail_tracker_import_batches
            ORDER BY imported_at DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        return [dict(row) for row in cur.fetchall()]
