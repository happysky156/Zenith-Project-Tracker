from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from urllib.parse import urlparse, urlunparse

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "project_tracker.db"

try:
    import streamlit as st
except Exception:  # pragma: no cover - streamlit runtime only
    st = None  # type: ignore

try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:  # pragma: no cover - optional dependency until postgres is used
    psycopg = None  # type: ignore
    dict_row = None  # type: ignore



def _read_database_url() -> str | None:
    env_value = os.getenv("DATABASE_URL") or os.getenv("database_url")
    if env_value:
        return env_value.strip()

    if st is None:
        return None

    try:
        if "DATABASE_URL" in st.secrets:
            return str(st.secrets["DATABASE_URL"]).strip()
        if "database_url" in st.secrets:
            return str(st.secrets["database_url"]).strip()
        if "database" in st.secrets and "url" in st.secrets["database"]:
            return str(st.secrets["database"]["url"]).strip()
    except Exception:
        return None
    return None


DATABASE_URL = _read_database_url()



def using_postgres() -> bool:
    return bool(DATABASE_URL) and str(DATABASE_URL).startswith(("postgres://", "postgresql://"))



def using_sqlite() -> bool:
    return not using_postgres()



def get_db_path() -> Path:
    return DB_PATH



def get_database_backend() -> str:
    return "PostgreSQL" if using_postgres() else "SQLite"



def get_database_display_name() -> str:
    if using_sqlite():
        return str(DB_PATH)

    parsed = urlparse(str(DATABASE_URL))
    host = parsed.hostname or "unknown-host"
    port = f":{parsed.port}" if parsed.port else ""
    db_name = parsed.path.lstrip("/") or "postgres"
    user = parsed.username or "user"
    return f"postgresql://{user}:***@{host}{port}/{db_name}"



def adapt_sql(sql: str) -> str:
    if using_postgres():
        return sql.replace("?", "%s")
    return sql



def execute(cur, sql: str, params: tuple | list | None = None):
    params = tuple(params or ())
    return cur.execute(adapt_sql(sql), params)



def get_connection():
    if using_postgres():
        if psycopg is None:
            raise RuntimeError(
                "PostgreSQL is configured, but psycopg is not installed. "
                "Please add 'psycopg[binary]' to your environment before running the app."
            )
        return psycopg.connect(str(DATABASE_URL), row_factory=dict_row)

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
