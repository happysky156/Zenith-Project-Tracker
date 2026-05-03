from __future__ import annotations

from database.connection import execute, get_connection, using_postgres
from core.dictionaries import PEOPLE_EMAIL_MAP


_INIT_DONE = False
_EXT_INIT_DONE = False
_EXTENSION_LOCK_KEY = 90218001


SALES_CORE_COLUMNS_SQL = """
    project_id TEXT PRIMARY KEY,
    project_name TEXT NOT NULL,
    client_code TEXT NOT NULL,
    category TEXT,
    priority TEXT,
    reference_link TEXT,
    meeting_reference_link_1_label TEXT,
    meeting_reference_link_1_url TEXT,
    meeting_reference_link_2_label TEXT,
    meeting_reference_link_2_url TEXT,
    meeting_reference_link_3_label TEXT,
    meeting_reference_link_3_url TEXT,
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
    meeting_reference_link_1_label TEXT,
    meeting_reference_link_1_url TEXT,
    meeting_reference_link_2_label TEXT,
    meeting_reference_link_2_url TEXT,
    meeting_reference_link_3_label TEXT,
    meeting_reference_link_3_url TEXT,
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


IMPORT_FILE_ARCHIVE_SQL = """
    CREATE TABLE IF NOT EXISTS import_file_archive (
        file_id TEXT PRIMARY KEY,
        source_file TEXT NOT NULL,
        import_time TEXT NOT NULL,
        uploaded_by TEXT,
        import_type TEXT,
        file_size INTEGER NOT NULL DEFAULT 0,
        file_sha256 TEXT,
        content_type TEXT,
        file_bytes BYTEA NOT NULL
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


EXTENSION_TABLE_SQL = [
    """
    CREATE TABLE IF NOT EXISTS supplier_details (
        supplier_id TEXT PRIMARY KEY,
        supplier_code TEXT,
        supplier_name TEXT NOT NULL,
        supplier_short_name TEXT,
        company_type TEXT,
        country TEXT,
        province TEXT,
        city TEXT,
        location_raw TEXT,
        address_standardised TEXT,
        website_primary TEXT,
        website_others TEXT,
        primary_contact_name TEXT,
        primary_contact_mobile TEXT,
        primary_contact_email TEXT,
        primary_contact_landline TEXT,
        wechat TEXT,
        other_contacts TEXT,
        source_channel TEXT,
        source_ref TEXT,
        certificate TEXT,
        certificate_remarks TEXT,
        export_license TEXT,
        nda_status TEXT,
        nda_file TEXT,
        audit_status TEXT,
        audit_file TEXT,
        catalogue_status TEXT,
        catalogue_file TEXT,
        main_products TEXT,
        main_process TEXT,
        material_capability TEXT,
        surface_treatment TEXT,
        testing_capability TEXT,
        capability_tags TEXT,
        payment_terms TEXT,
        lead_time TEXT,
        quality_risk TEXT,
        commercial_risk TEXT,
        last_contact_date TEXT,
        remark_internal TEXT,
        active_status TEXT,
        active_reason TEXT,
        last_order_no TEXT,
        last_project_id TEXT,
        price_comparison_count INTEGER,
        order_count INTEGER,
        risk_summary TEXT,
        created_at TEXT,
        created_by TEXT,
        last_updated_at TEXT,
        last_updated_by TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project_items (
        project_id TEXT NOT NULL,
        item_code TEXT NOT NULL,
        item_name TEXT,
        item_description TEXT,
        client_item_no TEXT,
        drawing_no TEXT,
        drawing_revision TEXT,
        material TEXT,
        surface_treatment TEXT,
        estimated_qty REAL,
        unit TEXT,
        item_status TEXT,
        remarks TEXT,
        created_at TEXT,
        created_by TEXT,
        last_updated_at TEXT,
        last_updated_by TEXT,
        PRIMARY KEY (project_id, item_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS supplier_price_comparisons (
        supplier_quote_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        item_code TEXT NOT NULL,
        supplier_id TEXT,
        supplier_code TEXT,
        supplier_name TEXT NOT NULL,
        quote_round TEXT,
        quote_date TEXT,
        supplier_unit_cost REAL,
        currency TEXT,
        moq TEXT,
        lead_time TEXT,
        sample_lead_time TEXT,
        price_term TEXT,
        tooling_cost REAL,
        sample_cost REAL,
        packing_cost REAL,
        supplier_material_basis TEXT,
        supplier_quote_validity TEXT,
        price_adjustment_note TEXT,
        missing_info TEXT,
        quotation_quality TEXT,
        quotation_risk TEXT,
        recommended_supplier INTEGER,
        selected_supplier INTEGER,
        selection_reason TEXT,
        comparison_status TEXT,
        remarks TEXT,
        imported_at TEXT,
        imported_by TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS client_quotation_headers (
        client_quote_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        quote_version TEXT,
        quote_date TEXT,
        client_code TEXT,
        client_name TEXT,
        quote_status TEXT,
        price_term TEXT,
        quote_currency TEXT,
        index_snapshot_date TEXT,
        material_snapshot_status TEXT,
        fx_snapshot_status TEXT,
        freight_snapshot_status TEXT,
        quote_valid_until TEXT,
        remarks TEXT,
        created_at TEXT,
        created_by TEXT,
        last_updated_at TEXT,
        last_updated_by TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS client_quotation_lines (
        client_quote_line_id TEXT PRIMARY KEY,
        client_quote_id TEXT NOT NULL,
        project_id TEXT NOT NULL,
        item_code TEXT NOT NULL,
        item_name TEXT,
        selected_supplier_id TEXT,
        supplier_quote_id TEXT,
        supplier_unit_cost REAL,
        client_unit_price REAL,
        quantity_basis REAL,
        currency TEXT,
        price_term TEXT,
        material_index_used TEXT,
        freight_used TEXT,
        estimated_revenue REAL,
        estimated_supplier_cost REAL,
        estimated_extra_cost REAL,
        estimated_gp REAL,
        estimated_gp_percent REAL,
        remarks TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS index_config (
        index_config_id TEXT PRIMARY KEY,
        index_category TEXT NOT NULL,
        index_name TEXT NOT NULL,
        display_name TEXT,
        unit TEXT,
        source_name TEXT,
        source_url TEXT,
        fetch_enabled INTEGER,
        fetch_method TEXT,
        fallback_method TEXT,
        active INTEGER,
        remarks TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_market_indices (
        daily_index_id TEXT PRIMARY KEY,
        index_date TEXT NOT NULL,
        index_category TEXT,
        index_name TEXT NOT NULL,
        index_value REAL,
        unit TEXT,
        source_name TEXT,
        source_url TEXT,
        fetch_method TEXT,
        fetch_status TEXT,
        previous_value REAL,
        change_value REAL,
        change_percent REAL,
        error_message TEXT,
        confirmed_by_user INTEGER,
        confirmed_at TEXT,
        last_updated_at TEXT,
        updated_by TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS index_snapshots (
        index_snapshot_id TEXT PRIMARY KEY,
        client_quote_id TEXT,
        project_id TEXT NOT NULL,
        item_code TEXT,
        quote_version TEXT,
        snapshot_date TEXT,
        material_index_name TEXT,
        material_index_value REAL,
        material_index_unit TEXT,
        freight_index_name TEXT,
        freight_index_value REAL,
        freight_route TEXT,
        freight_unit TEXT,
        exchange_rate_pair TEXT,
        exchange_rate_value REAL,
        exchange_rate_source TEXT,
        source_name TEXT,
        source_url TEXT,
        locked_at TEXT,
        locked_by TEXT,
        remarks TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS freight_indices (
        freight_index_id TEXT PRIMARY KEY,
        index_date TEXT NOT NULL,
        destination_country TEXT NOT NULL,
        destination_port TEXT,
        origin_port TEXT,
        container_type TEXT,
        freight_value REAL,
        currency TEXT,
        source_type TEXT,
        source_note TEXT,
        last_actual_update_date TEXT,
        carry_forward INTEGER,
        remarks TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS order_details (
        order_detail_id TEXT PRIMARY KEY,
        order_no TEXT NOT NULL,
        project_id TEXT NOT NULL,
        item_code TEXT NOT NULL,
        client_quote_id TEXT,
        client_quote_line_id TEXT,
        supplier_quote_id TEXT,
        supplier_id TEXT,
        supplier_code TEXT,
        supplier_name TEXT,
        client_code TEXT,
        po_no TEXT,
        customer_item_no TEXT,
        supplier_item_no TEXT,
        order_qty REAL,
        unit TEXT,
        client_unit_price REAL,
        supplier_unit_cost REAL,
        currency TEXT,
        sales_revenue REAL,
        supplier_cost REAL,
        extra_cost REAL,
        gross_profit REAL,
        gross_profit_percent REAL,
        payment_status TEXT,
        production_status TEXT,
        inspection_status TEXT,
        packing_status TEXT,
        shipment_status TEXT,
        order_date TEXT,
        deposit_date TEXT,
        target_delivery_date TEXT,
        actual_delivery_date TEXT,
        inspection_date TEXT,
        shipment_date TEXT,
        container_no TEXT,
        bl_no TEXT,
        main_issue TEXT,
        next_step TEXT,
        next_step_owner TEXT,
        remarks TEXT,
        imported_at TEXT,
        imported_by TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS order_costs (
        cost_id TEXT PRIMARY KEY,
        order_no TEXT NOT NULL,
        project_id TEXT,
        item_code TEXT,
        cost_type TEXT NOT NULL,
        cost_description TEXT,
        cost_amount REAL,
        currency TEXT,
        paid_by TEXT,
        charge_to_client INTEGER,
        cost_date TEXT,
        invoice_no TEXT,
        remarks TEXT,
        created_at TEXT,
        created_by TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sample_tracking (
        sample_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        item_code TEXT,
        supplier_id TEXT,
        supplier_code TEXT,
        supplier_name TEXT,
        sample_type TEXT,
        sample_round TEXT,
        sample_status TEXT,
        sample_purpose TEXT,
        sample_request_date TEXT,
        target_sample_date TEXT,
        sample_sent_date TEXT,
        sample_received_date TEXT,
        sample_sent_to_client_date TEXT,
        client_feedback_date TEXT,
        client_feedback TEXT,
        sample_issue TEXT,
        revision_required INTEGER,
        next_sample_round_needed INTEGER,
        testing_required INTEGER,
        test_type TEXT,
        test_standard TEXT,
        test_lab TEXT,
        test_sent_date TEXT,
        test_status TEXT,
        test_result TEXT,
        test_report_link TEXT,
        test_fee REAL,
        test_issue TEXT,
        sample_folder_link TEXT,
        sample_photo_link_1 TEXT,
        sample_photo_link_2 TEXT,
        sample_photo_link_3 TEXT,
        courier_company TEXT,
        tracking_no TEXT,
        next_step TEXT,
        next_step_owner TEXT,
        target_date TEXT,
        remarks TEXT,
        last_updated_at TEXT,
        last_updated_by TEXT
    )
    """,
]


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
    "CREATE INDEX IF NOT EXISTS idx_import_file_archive_time ON import_file_archive(import_time)",
    "CREATE INDEX IF NOT EXISTS idx_import_file_archive_uploaded_by ON import_file_archive(uploaded_by)",
    "CREATE INDEX IF NOT EXISTS idx_app_users_email ON app_users(email)",
    "CREATE INDEX IF NOT EXISTS idx_app_user_sessions_email ON app_user_sessions(email)",
    "CREATE INDEX IF NOT EXISTS idx_app_user_sessions_expires ON app_user_sessions(expires_at)",
]


SUPPLIER_DETAILS_EXTENSION_COLUMNS = {
    "company_type": "TEXT",
    "location_raw": "TEXT",
    "address_standardised": "TEXT",
    "website_primary": "TEXT",
    "website_others": "TEXT",
    "primary_contact_name": "TEXT",
    "primary_contact_mobile": "TEXT",
    "primary_contact_email": "TEXT",
    "primary_contact_landline": "TEXT",
    "other_contacts": "TEXT",
    "source_channel": "TEXT",
    "source_ref": "TEXT",
    "certificate": "TEXT",
    "certificate_remarks": "TEXT",
    "export_license": "TEXT",
    "nda_status": "TEXT",
    "nda_file": "TEXT",
    "audit_status": "TEXT",
    "audit_file": "TEXT",
    "catalogue_status": "TEXT",
    "catalogue_file": "TEXT",
    "capability_tags": "TEXT",
    "last_contact_date": "TEXT",
    "remark_internal": "TEXT",
    "price_comparison_count": "INTEGER",
    "order_count": "INTEGER",
    "risk_summary": "TEXT",
    "created_at": "TEXT",
    "created_by": "TEXT",
}


EXTENSION_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_supplier_details_code ON supplier_details(supplier_code)",
    "CREATE INDEX IF NOT EXISTS idx_supplier_details_name ON supplier_details(supplier_name)",
    "CREATE INDEX IF NOT EXISTS idx_project_items_project ON project_items(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_supplier_price_project_item ON supplier_price_comparisons(project_id, item_code)",
    "CREATE INDEX IF NOT EXISTS idx_supplier_price_supplier ON supplier_price_comparisons(supplier_id)",
    "CREATE INDEX IF NOT EXISTS idx_client_quote_project ON client_quotation_headers(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_client_quote_lines_project ON client_quotation_lines(project_id, item_code)",
    "CREATE INDEX IF NOT EXISTS idx_daily_indices_date_name ON daily_market_indices(index_date, index_name)",
    "CREATE INDEX IF NOT EXISTS idx_index_snapshots_project ON index_snapshots(project_id, quote_version)",
    "CREATE INDEX IF NOT EXISTS idx_freight_indices_date_dest ON freight_indices(index_date, destination_country)",
    "CREATE INDEX IF NOT EXISTS idx_order_details_project ON order_details(project_id)",
    "CREATE INDEX IF NOT EXISTS idx_order_details_order ON order_details(order_no)",
    "CREATE INDEX IF NOT EXISTS idx_order_costs_order ON order_costs(order_no)",
    "CREATE INDEX IF NOT EXISTS idx_sample_tracking_project ON sample_tracking(project_id)",
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
    execute(cur, IMPORT_FILE_ARCHIVE_SQL)
    execute(cur, APP_USERS_SQL)
    execute(cur, APP_USER_SESSIONS_SQL)

    # Keep application startup light: extension tables are initialised lazily
    # by services.upgrade_service.ensure_ready() when an extension page/import is used.
    # This avoids blocking the main Dashboard/login page on Streamlit Cloud.

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
    _ensure_column(cur, "import_file_archive", "content_type", "TEXT")

    # Meeting Mode reference links: fixed three link slots per Sales / Operation record.
    # Safe additive migrations only; existing business/data logic is not changed.
    for table_name in ["sales_projects", "operation_orders"]:
        _ensure_column(cur, table_name, "meeting_reference_link_1_label", "TEXT")
        _ensure_column(cur, table_name, "meeting_reference_link_1_url", "TEXT")
        _ensure_column(cur, table_name, "meeting_reference_link_2_label", "TEXT")
        _ensure_column(cur, table_name, "meeting_reference_link_2_url", "TEXT")
        _ensure_column(cur, table_name, "meeting_reference_link_3_label", "TEXT")
        _ensure_column(cur, table_name, "meeting_reference_link_3_url", "TEXT")

    _seed_default_app_users(cur)

    for sql in INDEX_SQL:
        execute(cur, sql)

    conn.commit()
    conn.close()
    _INIT_DONE = True

def init_extension_db(force: bool = False) -> None:
    """Initialise additive extension tables only when extension modules are used.

    The function is intentionally idempotent per Streamlit process and serialised
    with a PostgreSQL advisory lock. Streamlit Cloud can open multiple sessions
    at the same time; without this guard, two sessions may try to create the same
    extension indexes concurrently and Supabase/PostgreSQL can report a deadlock.
    """
    global _EXT_INIT_DONE
    if _EXT_INIT_DONE and not force:
        return

    # Ensure the original core schema exists first, but do not force it unless
    # explicitly requested.
    init_db(force=force)

    conn = get_connection()
    cur = conn.cursor()
    advisory_locked = False
    try:
        if using_postgres():
            # Serialise extension DDL across concurrent Streamlit sessions.
            execute(cur, f"SELECT pg_advisory_lock({_EXTENSION_LOCK_KEY})")
            advisory_locked = True

        for sql in EXTENSION_TABLE_SQL:
            execute(cur, sql)

        # Additive Supplier Details migrations. Existing databases may still have
        # the earlier short supplier table; these columns make the new tabbed
        # supplier detail page and import template available without dropping any
        # old data.
        for column_name, column_sql in SUPPLIER_DETAILS_EXTENSION_COLUMNS.items():
            _ensure_column(cur, "supplier_details", column_name, column_sql)

        # One-time safe copy from the earlier short Supplier Details fields into
        # the new structured fields. Old columns are intentionally not dropped,
        # so no existing data is destroyed. These updates only fill blank new
        # fields.
        supplier_copy_pairs = [
            ("contact_person", "primary_contact_name"),
            ("phone", "primary_contact_mobile"),
            ("email", "primary_contact_email"),
            ("address", "location_raw"),
            ("address", "address_standardised"),
            ("certification", "certificate"),
            ("supplier_source", "source_channel"),
            ("remarks", "remark_internal"),
        ]
        for old_column, new_column in supplier_copy_pairs:
            if _column_exists(cur, "supplier_details", old_column) and _column_exists(cur, "supplier_details", new_column):
                execute(
                    cur,
                    f"UPDATE supplier_details SET {new_column} = COALESCE({new_column}, {old_column}) "
                    f"WHERE {new_column} IS NULL AND {old_column} IS NOT NULL",
                )

        for sql in EXTENSION_INDEX_SQL:
            execute(cur, sql)
        conn.commit()
        _EXT_INIT_DONE = True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        if advisory_locked:
            try:
                execute(cur, f"SELECT pg_advisory_unlock({_EXTENSION_LOCK_KEY})")
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
        conn.close()

