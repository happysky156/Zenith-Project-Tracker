from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

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

try:
    from psycopg_pool import ConnectionPool
except Exception:  # pragma: no cover - optional performance dependency
    ConnectionPool = None  # type: ignore

_POSTGRES_POOL_FALLBACK = None


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


def get_database_url() -> str | None:
    """Read DATABASE_URL at runtime instead of freezing an old value on import."""
    return _read_database_url()


# Backward compatibility for older imports. New logic calls get_database_url().
DATABASE_URL = get_database_url()


def using_postgres() -> bool:
    url = get_database_url()
    return bool(url) and str(url).startswith(("postgres://", "postgresql://"))


def using_sqlite() -> bool:
    return not using_postgres()


def get_db_path() -> Path:
    return DB_PATH


def get_database_backend() -> str:
    return "PostgreSQL" if using_postgres() else "SQLite"


def get_database_display_name() -> str:
    if using_sqlite():
        return str(DB_PATH)

    parsed = urlparse(str(get_database_url()))
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


class _PooledPostgresConnection:
    """Wrapper so existing conn.close() returns a pooled connection to the pool."""

    def __init__(self, pool, conn):
        self._pool = pool
        self._conn = conn
        self._returned = False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        if self._returned:
            return
        self._returned = True
        try:
            self._pool.putconn(self._conn)
        except Exception:
            try:
                self._conn.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            try:
                self.rollback()
            except Exception:
                pass
        self.close()
        return False


def _create_pool(conninfo: str):
    if ConnectionPool is None:
        return None
    return ConnectionPool(
        conninfo=conninfo,
        min_size=0,
        max_size=5,
        open=True,
        kwargs={"row_factory": dict_row},
        timeout=20,
    )


if st is not None:
    @st.cache_resource(show_spinner=False)
    def _get_postgres_pool_cached(conninfo: str):
        return _create_pool(conninfo)
else:  # pragma: no cover
    def _get_postgres_pool_cached(conninfo: str):
        global _POSTGRES_POOL_FALLBACK
        if _POSTGRES_POOL_FALLBACK is None:
            _POSTGRES_POOL_FALLBACK = _create_pool(conninfo)
        return _POSTGRES_POOL_FALLBACK


def get_connection():
    if using_postgres():
        if psycopg is None:
            raise RuntimeError(
                "PostgreSQL is configured, but psycopg is not installed. "
                "Please add 'psycopg[binary]' to your environment before running the app."
            )
        conninfo = str(get_database_url())
        pool = _get_postgres_pool_cached(conninfo)
        if pool is not None:
            return _PooledPostgresConnection(pool, pool.getconn())
        return psycopg.connect(conninfo, row_factory=dict_row)

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
