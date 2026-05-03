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




def _read_setting(name: str, default: str | None = None) -> str | None:
    """Read a runtime setting from env or Streamlit secrets."""
    env_value = os.getenv(name) or os.getenv(name.lower())
    if env_value is not None:
        return str(env_value).strip()
    if st is not None:
        try:
            if name in st.secrets:
                return str(st.secrets[name]).strip()
            lower_name = name.lower()
            if lower_name in st.secrets:
                return str(st.secrets[lower_name]).strip()
        except Exception:
            pass
    return default


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def postgres_pool_enabled() -> bool:
    """Client-side psycopg pool is optional.

    Streamlit Cloud is already connecting to Supabase's own pooler in production.
    Keeping another small app-side pool can exhaust available connections when
    multiple pages rerun or schema checks happen at the same time.  Therefore the
    safer default is direct short-lived psycopg connections.  Set
    ENABLE_POSTGRES_POOL=true only if you intentionally want app-side pooling.
    """
    return _truthy(_read_setting("ENABLE_POSTGRES_POOL", "false"))


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
        # Always leave pooled connections in a clean IDLE state.
        # Many read-only SELECT calls still open a transaction in psycopg;
        # returning an INTRANS connection can flood Streamlit logs and delay reuse.
        try:
            self._conn.rollback()
        except Exception:
            pass
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
    if ConnectionPool is None or not postgres_pool_enabled():
        return None
    return ConnectionPool(
        conninfo=conninfo,
        min_size=0,
        max_size=int(_read_setting("POSTGRES_POOL_MAX_SIZE", "4") or "4"),
        open=True,
        kwargs={"row_factory": dict_row},
        timeout=int(_read_setting("POSTGRES_POOL_TIMEOUT_SECONDS", "30") or "30"),
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
            try:
                return _PooledPostgresConnection(pool, pool.getconn())
            except Exception:
                # Do not bring down the app because the optional client-side pool
                # is temporarily exhausted. Fall back to a direct short-lived
                # connection. The caller's conn.close() will close it normally.
                pass
        return psycopg.connect(conninfo, row_factory=dict_row)

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
