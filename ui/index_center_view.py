from __future__ import annotations

from datetime import date, datetime, time
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

from services.market_index_service import (
    BOC_EXCHANGE_RATE_URL,
    latest_daily_indices,
    list_daily_indices,
    list_index_configs,
    list_index_alert_events,
    run_daily_index_fetch,
    save_manual_index,
    today_local,
)


def _status_label(value: Any) -> str:
    return str(value or "-").strip() or "-"


def _build_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    numeric_cols = ["value", "previous_value", "change_value", "change_percent"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    preferred = [
        "index_date", "index_category", "index_code", "display_name", "value", "unit",
        "source_name", "fetch_status", "previous_value", "change_value", "change_percent",
        "confirmed", "last_updated_at",
    ]
    cols = [c for c in preferred if c in df.columns]
    return df[cols]


def _index_column_config() -> dict[str, Any]:
    return {
        "value": st.column_config.NumberColumn("value", format="%.6f"),
        "previous_value": st.column_config.NumberColumn("previous_value", format="%.6f"),
        "change_value": st.column_config.NumberColumn("change_value", format="%.6f"),
        "change_percent": st.column_config.NumberColumn("change_percent", format="%.4f"),
    }


def _excel_safe_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    safe = df.copy()

    def clean_value(value: Any) -> Any:
        if value is None:
            return ""
        try:
            if pd.isna(value):
                return ""
        except Exception:
            pass
        if isinstance(value, pd.Timestamp):
            if value.tzinfo is not None:
                value = value.tz_convert(None)
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                value = value.replace(tzinfo=None)
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, date) and not isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, time):
            return value.strftime("%H:%M:%S")
        if isinstance(value, (dict, list, tuple, set)):
            return str(value)
        return value

    for col in safe.columns:
        safe[col] = safe[col].map(clean_value) if not pd.api.types.is_datetime64_any_dtype(safe[col]) else safe[col].astype("string").fillna("")
    return safe


def _build_index_export(all_rows: list[dict[str, Any]], latest_rows: list[dict[str, Any]], configs: list[dict[str, Any]]) -> bytes:
    output = BytesIO()
    history_df = _excel_safe_dataframe(_build_dataframe(all_rows))
    latest_df = _excel_safe_dataframe(_build_dataframe(latest_rows))
    config_df = _excel_safe_dataframe(pd.DataFrame(configs))
    readme_df = pd.DataFrame([
        {"Field": "Export Purpose", "Value": "Daily Market Indices history for quotation review and traceability."},
        {"Field": "Generated At", "Value": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")},
        {"Field": "History Rows", "Value": len(history_df)},
        {"Field": "Latest Rows", "Value": len(latest_df)},
    ])
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        readme_df.to_excel(writer, sheet_name="Read Me", index=False)
        history_df.to_excel(writer, sheet_name="Daily Index History", index=False)
        latest_df.to_excel(writer, sheet_name="Latest Index Summary", index=False)
        config_df.to_excel(writer, sheet_name="Index Config", index=False)
    return output.getvalue()


def _load_index_data() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    configs = list_index_configs()
    latest_rows = latest_daily_indices()
    raw = list_daily_indices(limit=100000)
    all_rows = []
    if raw:
        from services.market_index_service import normalise_daily_row
        all_rows = [normalise_daily_row(row) for row in raw]
    try:
        alerts = list_index_alert_events(limit=1000)
    except Exception:
        alerts = []
    return configs, latest_rows, all_rows, alerts


def render_market_index_reference() -> None:
    """RFQ-facing index view. Read-only; uses the same index data as Admin."""
    st.markdown("### Market Index Reference")
    st.caption("Quotation-facing view of FX, material and freight indices. Admin maintenance stays in Settings / Admin → Index Center.")
    configs, latest_rows, all_rows, alerts = _load_index_data()
    today = today_local()
    today_rows = [r for r in all_rows if str(r.get("index_date")) == today]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Latest Items", len(latest_rows))
    c2.metric("Today's Records", len(today_rows))
    c3.metric("New Alerts", sum(1 for r in alerts if str(r.get("alert_status") or "New").lower() == "new"))
    c4.metric("Configs", len(configs))

    latest_df = _build_dataframe(latest_rows)
    if latest_df.empty:
        st.info("No latest index records found yet.")
    else:
        categories = ["All"] + sorted([str(x) for x in latest_df.get("index_category", pd.Series(dtype=str)).dropna().unique()])
        selected_category = st.radio("Category", categories, horizontal=True, key="rfq_market_index_category")
        show_df = latest_df.copy()
        if selected_category != "All" and "index_category" in show_df.columns:
            show_df = show_df[show_df["index_category"] == selected_category]
        st.dataframe(show_df, width="stretch", hide_index=True, column_config=_index_column_config())

    if all_rows:
        st.download_button(
            "Export index history",
            data=_build_index_export(all_rows, latest_rows, configs),
            file_name=f"zenith_index_history_{today}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def render_index_admin_center(operator: str) -> None:
    """Admin-facing index center. Keeps existing market_index_service business logic."""
    st.markdown("### Index Center")
    st.caption(f"FX source: Bank of China. Source URL: {BOC_EXCHANGE_RATE_URL}")
    configs, latest_rows, all_rows, alerts = _load_index_data()
    today = today_local()
    today_rows = [r for r in all_rows if str(r.get("index_date")) == today]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Config Items", len(configs))
    c2.metric("Today's Records", len(today_rows))
    c3.metric("Success", sum(1 for r in today_rows if _status_label(r.get("fetch_status")) == "Success"))
    c4.metric("Carry Forward", sum(1 for r in today_rows if _status_label(r.get("fetch_status")) == "Carry Forward"))
    c5.metric("New Alerts", sum(1 for r in alerts if str(r.get("alert_status") or "New").lower() == "new"))

    tab_overview, tab_manual, tab_daily, tab_config, tab_alerts = st.tabs([
        "Overview", "Manual Override / Confirm", "All Daily Records", "Index Config", "Alerts"
    ])

    with tab_overview:
        with st.expander("Run daily index fetch", expanded=False):
            st.warning("This writes today's Daily Market Indices rows. Existing Manual rows are protected from automatic overwrite.")
            if st.button("Run Daily Index Fetch Now", type="primary"):
                try:
                    summary = run_daily_index_fetch(operator=operator)
                    st.success(
                        f"Daily index fetch completed. Success: {summary.get('success', 0)} | "
                        f"Carry Forward: {summary.get('carry_forward', 0)} | Failed: {summary.get('failed', 0)} | "
                        f"Manual Required: {summary.get('manual_required', 0)}"
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Daily index fetch failed: {type(exc).__name__}: {exc}")
        st.markdown("#### Latest Index Summary")
        latest_df = _build_dataframe(latest_rows)
        if latest_df.empty:
            st.info("No index records found yet.")
        else:
            st.dataframe(latest_df, width="stretch", hide_index=True, column_config=_index_column_config())
        if all_rows:
            st.download_button(
                "Export all index history",
                data=_build_index_export(all_rows, latest_rows, configs),
                file_name=f"zenith_index_history_{today}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    with tab_manual:
        if not configs:
            st.info("No index config records found.")
        else:
            labels = [f"{cfg.get('display_name') or cfg.get('index_name')} [{cfg.get('index_code')}]" for cfg in configs]
            lookup = dict(zip(labels, configs))
            with st.form("manual_index_form_admin"):
                m1, m2, m3 = st.columns([1, 2.2, 1.2])
                index_date = m1.date_input("Index Date", value=date.fromisoformat(today_local()))
                selected_label = m2.selectbox("Index", labels)
                index_value = m3.number_input("Index Value", min_value=0.0, value=0.0, step=0.0001, format="%.6f")
                cfg = lookup[selected_label]
                s1, s2 = st.columns(2)
                source_name = s1.text_input("Source Name", value=str(cfg.get("source_name") or "Manual"))
                source_url = s2.text_input("Source URL", value=str(cfg.get("source_url") or ""))
                submitted = st.form_submit_button("Save Manual Index", type="primary")
                if submitted:
                    try:
                        save_manual_index(cfg, index_date.isoformat(), index_value, source_name, source_url, operator)
                        st.success("Manual index saved and protected from automatic overwrite for the same date.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Manual save failed: {type(exc).__name__}: {exc}")

    with tab_daily:
        df = _build_dataframe(all_rows)
        if df.empty:
            st.info("No daily index records found.")
        else:
            search = st.text_input("Search daily records", placeholder="Search index, category, source, status...")
            show_df = df.copy()
            if search:
                text = search.lower().strip()
                mask = show_df.astype(str).apply(lambda col: col.str.lower().str.contains(text, na=False)).any(axis=1)
                show_df = show_df[mask]
            st.dataframe(show_df, width="stretch", hide_index=True, column_config=_index_column_config())

    with tab_config:
        cfg_df = pd.DataFrame(configs)
        if cfg_df.empty:
            st.info("No index configuration records found.")
        else:
            cols = [c for c in ["index_category", "index_code", "index_name", "display_name", "unit", "source_name", "fetch_method", "fallback_method", "active", "remarks"] if c in cfg_df.columns]
            st.dataframe(cfg_df[cols], width="stretch", hide_index=True)

    with tab_alerts:
        if not alerts:
            st.info("No index alert events found.")
        else:
            alert_df = pd.DataFrame(alerts)
            cols = [c for c in ["alert_date", "alert_type", "index_code", "index_name", "alert_level", "reference_value", "latest_value", "change_percent", "related_project_id", "related_client_quote_id", "alert_status", "source_note"] if c in alert_df.columns]
            st.dataframe(alert_df[cols], width="stretch", hide_index=True)
