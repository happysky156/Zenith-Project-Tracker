from __future__ import annotations

from database.connection import execute, get_connection, using_postgres
from core.dictionaries import PEOPLE_EMAIL_MAP


_INIT_DONE = False


SALES_CORE_COLUMNS_SQL = """
    project_id TEXT PRIMARY KEY,
    project_name TEXT NOT NULL,
    client_code TEXT NOT NULL,
    category TEXT,
    priority TEXT,
    reference_link TEXT,
    source_file TEXT,
    created_at TEXT NOT NULL,

    current_owner TEXT,
    support_from TEXT,
    next_step_owner TEXT,
    next_step_support TEXT,
    need_decision_from TEXT,
    need_alignment_with TEXT,
    waiting_for_person TEXT,

    phase TEXT NOT NULL,
    health_status TEXT NOT NULL,
    result_status TEXT NOT NULL,
    last_event TEXT,
    last_status_update_at TEXT,
    last_reviewed_at TEXT,
    last_updated_by TEXT,

    quote_round INTEGER NOT NULL DEFAULT 0,
    sample_round INTEGER NOT NULL DEFAULT 0,
    doc_round INTEGER NOT NULL DEFAULT 0,
    test_round INTEGER NOT NULL DEFAULT 0,

    client_waiting_for TEXT,
    progress_summary TEXT,
    main_issue TEXT,
    block_point TEXT,
    waiting_for_text TEXT,
    likely_reason TEXT,
    need_from_meeting TEXT,
    next_step_summary TEXT,
    meeting_note TEXT,
    target_date TEXT,
    followup_status TEXT,
    is_archived INTEGER NOT NULL DEFAULT 0,
    review_this_week INTEGER NOT NULL DEFAULT 0,
    discussed_this_week INTEGER NOT NULL DEFAULT 0,

    request_type TEXT,
    request_note TEXT,
    pattern_flag INTEGER NOT NULL DEFAULT 0,
    pattern_note TEXT
"""


OPERATION_CORE_COLUMNS_SQL = """
    order_no TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    client_code TEXT NOT NULL,
    reference_link TEXT,
    source_file TEXT,
    created_at TEXT NOT NULL,

    current_owner TEXT,
    support_from TEXT,
    next_step_owner TEXT,
    next_step_support TEXT,
    need_decision_from TEXT,
    need_alignment_with TEXT,
    waiting_for_person TEXT,

    phase TEXT NOT NULL,
    health_status TEXT NOT NULL,
    result_status TEXT NOT NULL,
    last_event TEXT,
    last_status_update_at TEXT,
    last_reviewed_at TEXT,
    last_updated_by TEXT,

    doc_round INTEGER NOT NULL DEFAULT 0,
    test_round INTEGER NOT NULL DEFAULT 0,

    client_waiting_for TEXT,
    progress_summary TEXT,
    main_issue TEXT,
    block_point TEXT,
    waiting_for_text TEXT,
    likely_reason TEXT,
    need_from_meeting TEXT,
    next_step_summary TEXT,
    meeting_note TEXT,
    target_date TEXT,
    followup_status TEXT,
    is_archived INTEGER NOT NULL DEFAULT 0,
    review_this_week INTEGER NOT NULL DEFAULT 0,
    discussed_this_week INTEGER NOT NULL DEFAULT 0,

    request_type TEXT,
    request_note TEXT,
    pattern_flag INTEGER NOT NULL DEFAULT 0,
    pattern_note TEXT
"""


EVENT_LOGS_SQL = """
    CREATE TABLE IF NOT EXISTS event_logs_v2 (
        event_id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        project_id TEXT,
        order_no TEXT,
        event_time TEXT NOT NULL,
        event_type TEXT NOT NULL,
        event_group TEXT,
        old_phase TEXT,
        new_phase TEXT,
        old_health TEXT,
        new_health TEXT,
        old_result TEXT,
        new_result TEXT,
        round_change TEXT,
        operator TEXT,
        event_note TEXT,
        source_page TEXT
    )
"""


MEETING_SNAPSHOTS_SQL = """
    CREATE TABLE IF NOT EXISTS meeting_snapshots_v2 (
        snapshot_id TEXT PRIMARY KEY,
        meeting_week TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        project_id TEXT,
        order_no TEXT,
        phase TEXT,
        health_status TEXT,
        result_status TEXT,
        client_waiting_for TEXT,
        progress_summary TEXT,
        main_issue TEXT,
        block_point TEXT,
        need_from_meeting TEXT,
        next_step_summary TEXT,
        next_step_owner TEXT,
        request_type TEXT,
        need_decision_from TEXT,
        meeting_note TEXT,
        discussed_flag INTEGER NOT NULL DEFAULT 0,
        carry_forward_flag INTEGER NOT NULL DEFAULT 0,
        snapshot_time TEXT NOT NULL
    )
"""


IMPORT_BATCHES_SQL = """
    CREATE TABLE IF NOT EXISTS import_batches (
        batch_id TEXT PRIMARY KEY,
        source_file TEXT NOT NULL,
        import_time TEXT NOT NULL,
        imported_by TEXT,
        import_type TEXT,
        new_count INTEGER NOT NULL DEFAULT 0,
        update_count INTEGER NOT NULL DEFAULT 0,
        failed_count INTEGER NOT NULL DEFAULT 0,
        notes TEXT
    )
"""


APP_USERS_SQL = """
    CREATE TABLE IF NOT EXISTS app_users (
        email TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'editor',
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        last_login_at TEXT
    )
"""


APP_USER_SESSIONS_SQL = """
    CREATE TABLE IF NOT EXISTS app_user_sessions (
        session_token_hash TEXT PRIMARY KEY,
        email TEXT NOT NULL,
        display_name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'editor',
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        last_seen_at TEXT,
        revoked INTEGER NOT NULL DEFAULT 0
    )
"""


INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_sales_phase ON sales_projects(phase)",
    "CREATE INDEX IF NOT EXISTS idx_sales_health ON sales_projects(health_status)",
    "CREATE INDEX IF NOT EXISTS idx_sales_owner ON sales_projects(current_owner)",
    "CREATE INDEX IF NOT EXISTS idx_sales_target_date ON sales_projects(target_date)",
    "CREATE INDEX IF NOT EXISTS idx_orders_project_id ON operation_orders(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_orders_phase ON operation_orders(phase)",
    "CREATE INDEX IF NOT EXISTS idx_orders_health ON operation_orders(health_status)",
    "CREATE INDEX IF NOT EXISTS idx_orders_owner ON operation_orders(current_owner)",
    "CREATE INDEX IF NOT EXISTS idx_event_logs_entity ON event_logs_v2(entity_type, entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_event_logs_project ON event_logs_v2(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_event_logs_order ON event_logs_v2(order_no)",
    "CREATE INDEX IF NOT EXISTS idx_event_logs_time ON event_logs_v2(event_time)",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_week ON meeting_snapshots_v2(meeting_week)",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_entity ON meeting_snapshots_v2(entity_type, entity_id)",
    "CREATE INDEX IF NOT EXISTS idx_app_users_email ON app_users(email)",
    "CREATE INDEX IF NOT EXISTS idx_app_user_sessions_email ON app_user_sessions(email)",
    "CREATE INDEX IF NOT EXISTS idx_app_user_sessions_expires ON app_user_sessions(expires_at)",
]



def _table_exists(cur, table_name: str) -> bool:
    if using_postgres():
        execute(
            cur,
            "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = ?",
            (table_name,),
        )
        return cur.fetchone() is not None
    execute(cur, "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table_name,))
    return cur.fetchone() is not None



def _column_exists(cur, table_name: str, column_name: str) -> bool:
    if using_postgres():
        execute(
            cur,
            "SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = ? AND column_name = ?",
            (table_name, column_name),
        )
        return cur.fetchone() is not None

    execute(cur, f"PRAGMA table_info({table_name})")
    return any(row[1] == column_name for row in cur.fetchall())



def _ensure_column(cur, table_name: str, column_name: str, column_sql: str) -> None:
    if not _table_exists(cur, table_name):
        return
    if _column_exists(cur, table_name, column_name):
        return
    execute(cur, f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")




def _seed_default_app_users(cur) -> None:
    """Create phase-1 user records from the PEOPLE list without overwriting manual edits."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for display_name, email in PEOPLE_EMAIL_MAP.items():
        execute(cur, "SELECT 1 FROM app_users WHERE lower(email) = lower(?)", (email,))
        if cur.fetchone() is not None:
            continue
        execute(
            cur,
            """
            INSERT INTO app_users (email, display_name, role, active, created_at)
            VALUES (?, ?, ?, 1, ?)
            """,
            (email.lower(), display_name, "editor", now),
        )

def init_db(force: bool = False) -> None:
    """Initialise or migrate the database schema once per Streamlit process.

    This avoids remote Supabase schema checks on every Streamlit rerun/page
    switch while keeping a force option for future manual maintenance.
    """
    global _INIT_DONE
    if _INIT_DONE and not force:
        return

    conn = get_connection()
    cur = conn.cursor()

    execute(cur, f"CREATE TABLE IF NOT EXISTS sales_projects ({SALES_CORE_COLUMNS_SQL})")
    execute(cur, f"CREATE TABLE IF NOT EXISTS operation_orders ({OPERATION_CORE_COLUMNS_SQL})")
    execute(cur, EVENT_LOGS_SQL)
    execute(cur, MEETING_SNAPSHOTS_SQL)
    execute(cur, IMPORT_BATCHES_SQL)
    execute(cur, APP_USERS_SQL)
    execute(cur, APP_USER_SESSIONS_SQL)

    # Safe additive migrations for already-created databases.
    _ensure_column(cur, "sales_projects", "support_from", "TEXT")
    _ensure_column(cur, "operation_orders", "support_from", "TEXT")
    _ensure_column(cur, "sales_projects", "next_step_support", "TEXT")
    _ensure_column(cur, "operation_orders", "next_step_support", "TEXT")
    _ensure_column(cur, "sales_projects", "meeting_note", "TEXT")
    _ensure_column(cur, "operation_orders", "meeting_note", "TEXT")
    _ensure_column(cur, "sales_projects", "followup_status", "TEXT")
    _ensure_column(cur, "operation_orders", "followup_status", "TEXT")
    _ensure_column(cur, "sales_projects", "is_archived", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(cur, "operation_orders", "is_archived", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(cur, "meeting_snapshots_v2", "meeting_note", "TEXT")
    _ensure_column(cur, "import_batches", "import_type", "TEXT")

    _seed_default_app_users(cur)

    for sql in INDEX_SQL:
        execute(cur, sql)

    conn.commit()
    conn.close()
    _INIT_DONE = True
