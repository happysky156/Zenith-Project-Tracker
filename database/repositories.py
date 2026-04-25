from __future__ import annotations

from collections import defaultdict
from typing import Any

from database.connection import execute, get_connection


_SCHEMA_READY = False


def _ensure_schema_ready() -> None:
    """Run additive database migrations before repository queries.

    This keeps older local SQLite databases compatible when new optional
    columns such as is_archived or followup_status are added.
    """
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    from database.schema import init_db

    init_db()
    _SCHEMA_READY = True


SALES_SNAPSHOT_FIELDS = [
    "snapshot_id",
    "meeting_week",
    "entity_type",
    "entity_id",
    "project_id",
    "order_no",
    "phase",
    "health_status",
    "result_status",
    "client_waiting_for",
    "progress_summary",
    "main_issue",
    "block_point",
    "need_from_meeting",
    "next_step_summary",
    "next_step_owner",
    "request_type",
    "need_decision_from",
    "meeting_note",
    "discussed_flag",
    "carry_forward_flag",
    "snapshot_time",
]

SALES_INSERT_FIELDS = [
    "project_id",
    "project_name",
    "client_code",
    "category",
    "priority",
    "reference_link",
    "source_file",
    "created_at",
    "phase",
    "health_status",
    "result_status",
    "current_owner",
    "next_step_owner",
]

OPERATION_INSERT_FIELDS = [
    "order_no",
    "project_id",
    "client_code",
    "reference_link",
    "source_file",
    "created_at",
    "phase",
    "health_status",
    "result_status",
    "current_owner",
    "next_step_owner",
]

SALES_IMPORT_UPDATE_FIELDS = [
    "project_name",
    "client_code",
    "category",
    "priority",
    "reference_link",
    "source_file",
]

OPERATION_IMPORT_UPDATE_FIELDS = [
    "project_id",
    "client_code",
    "reference_link",
    "source_file",
]



def _normalize_db_value(value: Any) -> Any:
    try:
        import pandas as pd

        if pd.isna(value):
            return None
    except Exception:
        pass

    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value if v)
    return value



def _rows_to_dicts(rows) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]



def _fetchall_dicts(cur) -> list[dict[str, Any]]:
    return _rows_to_dicts(cur.fetchall())



def _fetchone_dict(cur) -> dict[str, Any] | None:
    row = cur.fetchone()
    return dict(row) if row else None


def _clear_data_cache() -> None:
    """Clear cached read models after writes."""
    try:
        import streamlit as st
        st.cache_data.clear()
    except Exception:
        pass


def _active_where(include_archived: bool) -> str:
    return "" if include_archived else "WHERE COALESCE(is_archived, 0) = 0"


def _sales_name_map(include_archived: bool = False) -> dict[str, str]:
    _ensure_schema_ready()
    conn = get_connection()
    cur = conn.cursor()
    execute(cur, f"SELECT project_id, project_name FROM sales_projects {_active_where(include_archived)}")
    mapping = {row["project_id"]: row["project_name"] for row in cur.fetchall()}
    conn.close()
    return mapping



def _linked_orders_map(include_archived: bool = False) -> dict[str, list[str]]:
    _ensure_schema_ready()
    conn = get_connection()
    cur = conn.cursor()
    execute(cur, f"SELECT project_id, order_no FROM operation_orders {_active_where(include_archived)} ORDER BY order_no")
    mapping: dict[str, list[str]] = defaultdict(list)
    for row in cur.fetchall():
        if row["project_id"]:
            mapping[row["project_id"]].append(row["order_no"])
    conn.close()
    return dict(mapping)


# ---------- existence ----------
def sales_project_exists(project_id: str) -> bool:
    _ensure_schema_ready()
    conn = get_connection()
    cur = conn.cursor()
    execute(cur, "SELECT 1 FROM sales_projects WHERE project_id = ?", (project_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None



def operation_order_exists(order_no: str) -> bool:
    _ensure_schema_ready()
    conn = get_connection()
    cur = conn.cursor()
    execute(cur, "SELECT 1 FROM operation_orders WHERE order_no = ?", (order_no,))
    row = cur.fetchone()
    conn.close()
    return row is not None


# ---------- list / get ----------
def list_sales_projects(include_archived: bool = False) -> list[dict[str, Any]]:
    _ensure_schema_ready()
    conn = get_connection()
    cur = conn.cursor()
    execute(cur, f"SELECT * FROM sales_projects {_active_where(include_archived)} ORDER BY created_at DESC, project_id ASC")
    rows = _fetchall_dicts(cur)
    conn.close()

    linked_map = _linked_orders_map(include_archived=include_archived)
    for row in rows:
        linked_orders = linked_map.get(row["project_id"], [])
        row["linked_order_count"] = len(linked_orders)
        row["linked_orders"] = ", ".join(linked_orders)
    return rows



def list_operation_orders(include_archived: bool = False) -> list[dict[str, Any]]:
    _ensure_schema_ready()
    conn = get_connection()
    cur = conn.cursor()
    execute(cur, f"SELECT * FROM operation_orders {_active_where(include_archived)} ORDER BY created_at DESC, order_no ASC")
    rows = _fetchall_dicts(cur)
    conn.close()

    name_map = _sales_name_map(include_archived=True)
    for row in rows:
        row["linked_project_name"] = name_map.get(row.get("project_id") or "")
    return rows



def list_sales_project_ids(include_archived: bool = False) -> list[str]:
    _ensure_schema_ready()
    conn = get_connection()
    cur = conn.cursor()
    execute(cur, f"SELECT project_id FROM sales_projects {_active_where(include_archived)} ORDER BY project_id")
    rows = [row["project_id"] for row in cur.fetchall()]
    conn.close()
    return rows



def list_operation_order_ids(include_archived: bool = False) -> list[str]:
    _ensure_schema_ready()
    conn = get_connection()
    cur = conn.cursor()
    execute(cur, f"SELECT order_no FROM operation_orders {_active_where(include_archived)} ORDER BY order_no")
    rows = [row["order_no"] for row in cur.fetchall()]
    conn.close()
    return rows



def get_sales_project(project_id: str) -> dict[str, Any] | None:
    _ensure_schema_ready()
    conn = get_connection()
    cur = conn.cursor()
    execute(cur, "SELECT * FROM sales_projects WHERE project_id = ?", (project_id,))
    row = _fetchone_dict(cur)
    conn.close()
    if row is None:
        return None

    linked_rows = get_linked_orders_for_project(project_id)
    row["linked_order_count"] = len(linked_rows)
    row["linked_orders"] = ", ".join(r["order_no"] for r in linked_rows)
    return row



def get_operation_order(order_no: str) -> dict[str, Any] | None:
    _ensure_schema_ready()
    conn = get_connection()
    cur = conn.cursor()
    execute(cur, "SELECT * FROM operation_orders WHERE order_no = ?", (order_no,))
    row = _fetchone_dict(cur)
    conn.close()
    if row is None:
        return None

    if row.get("project_id"):
        name_map = _sales_name_map()
        row["linked_project_name"] = name_map.get(row["project_id"])
    else:
        row["linked_project_name"] = None
    return row



def get_linked_orders_for_project(project_id: str, include_archived: bool = False) -> list[dict[str, Any]]:
    _ensure_schema_ready()
    conn = get_connection()
    cur = conn.cursor()
    archived_filter = "" if include_archived else "AND COALESCE(is_archived, 0) = 0"
    execute(
        cur,
        f"""
        SELECT order_no, project_id, client_code, phase, health_status, result_status, last_event, target_date, review_this_week
        FROM operation_orders
        WHERE project_id = ?
          {archived_filter}
        ORDER BY created_at DESC, order_no ASC
        """,
        (project_id,),
    )
    rows = _fetchall_dicts(cur)
    conn.close()
    return rows


# ---------- upsert import ----------
def upsert_sales_base_fields(record: dict[str, Any]) -> str:
    existing = sales_project_exists(record["project_id"])
    conn = get_connection()
    cur = conn.cursor()
    if existing:
        assignments = ", ".join(f"{field} = ?" for field in SALES_IMPORT_UPDATE_FIELDS)
        values = [_normalize_db_value(record.get(field)) for field in SALES_IMPORT_UPDATE_FIELDS]
        values.append(record["project_id"])
        execute(cur, f"UPDATE sales_projects SET {assignments} WHERE project_id = ?", values)
        action = "updated"
    else:
        placeholders = ", ".join(["?"] * len(SALES_INSERT_FIELDS))
        execute(
            cur,
            f"INSERT INTO sales_projects ({', '.join(SALES_INSERT_FIELDS)}) VALUES ({placeholders})",
            [_normalize_db_value(record.get(field)) for field in SALES_INSERT_FIELDS],
        )
        action = "inserted"
    conn.commit()
    conn.close()
    _clear_data_cache()
    return action



def upsert_operation_base_fields(record: dict[str, Any]) -> str:
    existing = operation_order_exists(record["order_no"])
    conn = get_connection()
    cur = conn.cursor()
    if existing:
        assignments = ", ".join(f"{field} = ?" for field in OPERATION_IMPORT_UPDATE_FIELDS)
        values = [_normalize_db_value(record.get(field)) for field in OPERATION_IMPORT_UPDATE_FIELDS]
        values.append(record["order_no"])
        execute(cur, f"UPDATE operation_orders SET {assignments} WHERE order_no = ?", values)
        action = "updated"
    else:
        placeholders = ", ".join(["?"] * len(OPERATION_INSERT_FIELDS))
        execute(
            cur,
            f"INSERT INTO operation_orders ({', '.join(OPERATION_INSERT_FIELDS)}) VALUES ({placeholders})",
            [_normalize_db_value(record.get(field)) for field in OPERATION_INSERT_FIELDS],
        )
        action = "inserted"
    conn.commit()
    conn.close()
    _clear_data_cache()
    return action


# ---------- generic update ----------
def update_sales_project_fields(project_id: str, updates: dict[str, Any]) -> None:
    _ensure_schema_ready()
    if not updates:
        return
    conn = get_connection()
    cur = conn.cursor()
    assignments = ", ".join(f"{field} = ?" for field in updates.keys())
    values = [_normalize_db_value(value) for value in updates.values()]
    values.append(project_id)
    execute(cur, f"UPDATE sales_projects SET {assignments} WHERE project_id = ?", values)
    conn.commit()
    conn.close()
    _clear_data_cache()



def update_operation_order_fields(order_no: str, updates: dict[str, Any]) -> None:
    _ensure_schema_ready()
    if not updates:
        return
    conn = get_connection()
    cur = conn.cursor()
    assignments = ", ".join(f"{field} = ?" for field in updates.keys())
    values = [_normalize_db_value(value) for value in updates.values()]
    values.append(order_no)
    execute(cur, f"UPDATE operation_orders SET {assignments} WHERE order_no = ?", values)
    conn.commit()
    conn.close()
    _clear_data_cache()


# ---------- event logs ----------
def insert_event_log(event: dict[str, Any]) -> None:
    conn = get_connection()
    cur = conn.cursor()
    fields = [
        "event_id",
        "entity_type",
        "entity_id",
        "project_id",
        "order_no",
        "event_time",
        "event_type",
        "event_group",
        "old_phase",
        "new_phase",
        "old_health",
        "new_health",
        "old_result",
        "new_result",
        "round_change",
        "operator",
        "event_note",
        "source_page",
    ]
    placeholders = ", ".join(["?"] * len(fields))
    execute(
        cur,
        f"INSERT INTO event_logs_v2 ({', '.join(fields)}) VALUES ({placeholders})",
        [_normalize_db_value(event.get(field)) for field in fields],
    )
    conn.commit()
    conn.close()
    _clear_data_cache()



def list_event_logs(entity_type: str, entity_id: str) -> list[dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    execute(
        cur,
        "SELECT * FROM event_logs_v2 WHERE entity_type = ? AND entity_id = ? ORDER BY event_time DESC",
        (entity_type, entity_id),
    )
    rows = _fetchall_dicts(cur)
    conn.close()
    return rows


# ---------- meeting snapshots ----------
def insert_meeting_snapshot(snapshot: dict[str, Any]) -> None:
    conn = get_connection()
    cur = conn.cursor()
    placeholders = ", ".join(["?"] * len(SALES_SNAPSHOT_FIELDS))
    execute(
        cur,
        f"INSERT INTO meeting_snapshots_v2 ({', '.join(SALES_SNAPSHOT_FIELDS)}) VALUES ({placeholders})",
        [_normalize_db_value(snapshot.get(field)) for field in SALES_SNAPSHOT_FIELDS],
    )
    conn.commit()
    conn.close()
    _clear_data_cache()



def list_meeting_snapshots(entity_type: str, entity_id: str) -> list[dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    execute(
        cur,
        "SELECT * FROM meeting_snapshots_v2 WHERE entity_type = ? AND entity_id = ? ORDER BY snapshot_time DESC",
        (entity_type, entity_id),
    )
    rows = _fetchall_dicts(cur)
    conn.close()
    return rows


# ---------- import batch ----------
def write_import_batch(record: dict[str, Any]) -> None:
    conn = get_connection()
    cur = conn.cursor()
    fields = [
        "batch_id",
        "source_file",
        "import_time",
        "imported_by",
        "import_type",
        "new_count",
        "update_count",
        "failed_count",
        "notes",
    ]
    placeholders = ", ".join(["?"] * len(fields))
    execute(
        cur,
        f"INSERT INTO import_batches ({', '.join(fields)}) VALUES ({placeholders})",
        [_normalize_db_value(record.get(field)) for field in fields],
    )
    conn.commit()
    conn.close()
    _clear_data_cache()
