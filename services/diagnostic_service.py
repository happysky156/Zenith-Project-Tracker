from __future__ import annotations

import hashlib
import os
from html import escape
from typing import Any
from urllib.parse import urlparse

import streamlit as st

from database.connection import execute, get_connection, get_database_backend, get_database_url


BUSINESS_TABLES = [
    "sales_projects",
    "operation_orders",
    "event_logs_v2",
    "import_batches",
    "meeting_snapshots_v2",
    "app_users",
    "app_user_sessions",
]


def _as_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    try:
        return dict(row)
    except Exception:
        return {}


def _database_url_source() -> str:
    if os.getenv("DATABASE_URL") or os.getenv("database_url"):
        return "environment variable"
    try:
        if "DATABASE_URL" in st.secrets or "database_url" in st.secrets:
            return "Streamlit secrets"
        if "database" in st.secrets and "url" in st.secrets["database"]:
            return "Streamlit secrets [database].url"
    except Exception:
        pass
    return "not configured"


def _safe_db_identity() -> dict[str, str]:
    url = get_database_url() or ""
    if not url:
        return {
            "backend": get_database_backend(),
            "source": _database_url_source(),
            "host": "-",
            "port": "-",
            "database": "-",
            "username": "-",
            "url_fingerprint": "-",
        }

    parsed = urlparse(str(url))
    fingerprint = hashlib.sha256(str(url).encode("utf-8")).hexdigest()[:12]
    return {
        "backend": get_database_backend(),
        "source": _database_url_source(),
        "host": parsed.hostname or "-",
        "port": str(parsed.port or "-"),
        "database": parsed.path.lstrip("/") or "-",
        "username": parsed.username or "-",
        "url_fingerprint": fingerprint,
    }


def _count_table(table_name: str) -> dict[str, Any]:
    conn = get_connection()
    cur = conn.cursor()
    try:
        execute(cur, f"SELECT COUNT(*) AS total FROM {table_name}")
        total_row = _as_dict(cur.fetchone())
        total = int(total_row.get("total") or 0)

        active = None
        archived = None
        if table_name in {"sales_projects", "operation_orders"}:
            execute(cur, f"SELECT COUNT(*) AS active FROM {table_name} WHERE COALESCE(is_archived, 0) = 0")
            active = int((_as_dict(cur.fetchone()).get("active") or 0))
            execute(cur, f"SELECT COUNT(*) AS archived FROM {table_name} WHERE COALESCE(is_archived, 0) = 1")
            archived = int((_as_dict(cur.fetchone()).get("archived") or 0))
        return {"table_name": table_name, "total": total, "active": active, "archived": archived, "error": ""}
    except Exception as exc:
        return {"table_name": table_name, "total": None, "active": None, "archived": None, "error": str(exc)}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _server_info() -> dict[str, Any]:
    conn = get_connection()
    cur = conn.cursor()
    try:
        execute(
            cur,
            """
            SELECT
                current_database() AS current_database,
                current_schema() AS current_schema,
                current_user AS current_user
            """,
        )
        return _as_dict(cur.fetchone())
    except Exception as exc:
        return {"error": str(exc)}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def render_database_diagnostics(metrics: dict[str, Any] | None = None) -> None:
    """Collapsed dashboard-only diagnostic panel for deployment troubleshooting.

    It intentionally does not expose passwords or full connection strings.
    """
    metrics = metrics or {}
    with st.expander("Database diagnostics / 数据库连接检查", expanded=False):
        if st.button("Force refresh cached data / 强制刷新缓存", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()

        identity = _safe_db_identity()
        server = _server_info()
        st.markdown(
            "\n".join(
                [
                    f"**Backend:** `{escape(identity.get('backend', '-'))}`",
                    f"**Source:** `{escape(identity.get('source', '-'))}`",
                    f"**Host:** `{escape(identity.get('host', '-'))}`",
                    f"**Port:** `{escape(identity.get('port', '-'))}`",
                    f"**Database:** `{escape(identity.get('database', '-'))}`",
                    f"**User:** `{escape(identity.get('username', '-'))}`",
                    f"**URL fingerprint:** `{escape(identity.get('url_fingerprint', '-'))}`",
                    f"**Server database/schema/user:** `{escape(str(server))}`",
                ]
            )
        )

        count_rows = [_count_table(table) for table in BUSINESS_TABLES]
        st.dataframe(count_rows, use_container_width=True, hide_index=True)

        dashboard_sales = int(metrics.get("total_sales") or metrics.get("sales_projects") or 0)
        dashboard_ops = int(metrics.get("total_operations") or metrics.get("operation_orders") or 0)
        raw_sales = next((r for r in count_rows if r["table_name"] == "sales_projects"), {})
        raw_ops = next((r for r in count_rows if r["table_name"] == "operation_orders"), {})
        st.markdown(
            f"**Dashboard metrics currently loaded:** Sales `{dashboard_sales}`, Operation `{dashboard_ops}`"
        )

        raw_sales_total = int(raw_sales.get("total") or 0)
        raw_ops_total = int(raw_ops.get("total") or 0)
        if (raw_sales_total or raw_ops_total) and dashboard_sales == 0 and dashboard_ops == 0:
            st.warning(
                "Supabase has business rows, but dashboard metrics are 0. Click 'Force refresh cached data'. "
                "If it remains 0 after refresh, the app is running a stale code path or reading a different deployed app/branch."
            )
