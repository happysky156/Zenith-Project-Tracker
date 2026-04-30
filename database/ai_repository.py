from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from database.connection import execute, get_connection
from database.schema import init_db


AI_UPDATE_DRAFTS_SQL = """
    CREATE TABLE IF NOT EXISTS ai_update_drafts (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        record_type TEXT,
        entity_id TEXT,
        project_name TEXT,
        client_code TEXT,
        order_no TEXT,
        user_email TEXT,
        user_name TEXT,
        source_text TEXT,
        draft_json TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL,
        confirmed_at TEXT,
        confirmed_by TEXT
    )
"""


def _normalise_user(current_user: Any) -> tuple[str, str]:
    if isinstance(current_user, dict):
        return (
            str(current_user.get("email") or ""),
            str(current_user.get("display_name") or current_user.get("name") or ""),
        )
    return (
        str(getattr(current_user, "email", "") or ""),
        str(getattr(current_user, "display_name", "") or getattr(current_user, "name", "") or ""),
    )


def ensure_ai_tables() -> None:
    # Keep existing core schema initialisation behaviour, then add the AI table.
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    execute(cur, AI_UPDATE_DRAFTS_SQL)
    conn.commit()
    conn.close()


def save_ai_update_draft(
    *,
    selected_project: dict[str, Any],
    meeting_notes: str,
    draft_json: dict[str, Any],
    current_user: Any,
    status: str = "pending",
) -> str:
    ensure_ai_tables()

    draft_id = str(uuid.uuid4())
    user_email, user_name = _normalise_user(current_user)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    confirmed_at = now if status in {"confirmed", "confirmed_applied", "confirmed_no_change"} else None
    confirmed_by = user_name or user_email if confirmed_at else None

    conn = get_connection()
    cur = conn.cursor()
    execute(
        cur,
        """
        INSERT INTO ai_update_drafts (
            id,
            project_id,
            record_type,
            entity_id,
            project_name,
            client_code,
            order_no,
            user_email,
            user_name,
            source_text,
            draft_json,
            status,
            created_at,
            confirmed_at,
            confirmed_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            draft_id,
            str(selected_project.get("project_id") or ""),
            str(selected_project.get("record_type") or ""),
            str(selected_project.get("entity_id") or ""),
            str(selected_project.get("project_name") or ""),
            str(selected_project.get("client_code") or ""),
            str(selected_project.get("order_no") or ""),
            user_email,
            user_name,
            meeting_notes,
            json.dumps(draft_json, ensure_ascii=False),
            status,
            now,
            confirmed_at,
            confirmed_by,
        ),
    )
    conn.commit()
    conn.close()
    return draft_id


def mark_ai_draft_confirmed(*, draft_id: str, current_user: Any) -> None:
    mark_ai_draft_status(draft_id=draft_id, status="confirmed", current_user=current_user)


def mark_ai_draft_status(*, draft_id: str, status: str, current_user: Any) -> None:
    """Update the lifecycle status of an AI draft.

    Typical statuses:
    - pending
    - confirmed
    - confirmed_applied
    - confirmed_no_change
    - confirmed_apply_failed
    """
    ensure_ai_tables()
    user_email, user_name = _normalise_user(current_user)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    confirmed_by = user_name or user_email

    conn = get_connection()
    cur = conn.cursor()
    execute(
        cur,
        """
        UPDATE ai_update_drafts
        SET status = ?, confirmed_at = COALESCE(confirmed_at, ?), confirmed_by = COALESCE(confirmed_by, ?)
        WHERE id = ?
        """,
        (status, now, confirmed_by, draft_id),
    )
    conn.commit()
    conn.close()


def list_ai_update_drafts(limit: int = 50) -> list[dict[str, Any]]:
    ensure_ai_tables()
    conn = get_connection()
    cur = conn.cursor()
    execute(
        cur,
        """
        SELECT *
        FROM ai_update_drafts
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (int(limit),),
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows
