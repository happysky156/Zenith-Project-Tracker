from __future__ import annotations

from datetime import date, datetime, time
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

from core.auth import require_login
from services.market_index_service import (
    BOC_EXCHANGE_RATE_URL,
    latest_daily_indices,
    list_daily_indices,
    list_index_configs,
    list_index_alert_events,
    list_index_alert_rules,
    run_daily_index_fetch,
    run_index_alert_evaluation,
    save_index_alert_rule,
    save_manual_index,
    today_local,
    update_index_alert_event_status,
)
from ui.theme import apply_theme, render_page_header
from ui.upgrade_ui import render_upgrade_css, render_upgrade_intro

apply_theme()
render_upgrade_css()
current_user = require_login()
operator = current_user.get("display_name") or current_user.get("email") or "User"

render_page_header("Index Center", "Daily FX, material index and freight tracking for quotation traceability.")
render_upgrade_intro(
    "Index Center",
    "Daily Market Indices can change every day. Index Snapshots should be locked when a client quotation is created so historical quotations never change.",
)


def _to_number(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _status_label(value: Any) -> str:
    return str(value or "-").strip() or "-"


def _build_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)

    # Streamlit can render Decimal/object numeric columns inconsistently,
    # especially small negative values such as -0.0066.  Convert numeric
    # index columns to real floats before display/export so negative signs
    # stay in the correct position. This is a UI/export normalisation only;
    # it does not change stored database values or calculation logic.
    numeric_cols = ["value", "previous_value", "change_value", "change_percent"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    preferred = [
        "index_date",
        "index_category",
        "index_code",
        "display_name",
        "value",
        "unit",
        "source_name",
        "source_pub_time",
        "fetch_method",
        "fetch_status",
        "previous_value",
        "change_value",
        "change_percent",
        "confirmed",
        "error_message",
        "last_updated_at",
    ]
    cols = [c for c in preferred if c in df.columns]
    return df[cols]


def _index_column_config() -> dict[str, Any]:
    """Consistent display formatting for index numeric columns.

    Keeps small FX changes readable and prevents object/Decimal rendering
    glitches such as showing -0.0066 as 0.0-66.
    """
    return {
        "value": st.column_config.NumberColumn("value", format="%.6f"),
        "previous_value": st.column_config.NumberColumn("previous_value", format="%.6f"),
        "change_value": st.column_config.NumberColumn("change_value", format="%.6f"),
        "change_percent": st.column_config.NumberColumn("change_percent", format="%.4f"),
    }


def _excel_safe_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy that is safe for pandas/openpyxl Excel export.

    PostgreSQL/Supabase rows can contain timezone-aware datetimes, Decimal
    values, dictionaries, lists, or mixed object columns. Pandas Excel export
    raises ValueError for timezone-aware datetimes. This helper only affects the
    downloadable workbook; it does not change any database data or page logic.
    """
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
        if pd.api.types.is_datetime64_any_dtype(safe[col]):
            safe[col] = safe[col].astype("string").fillna("")
        else:
            safe[col] = safe[col].map(clean_value)

    return safe

def _build_index_history_export(
    all_rows: list[dict[str, Any]],
    latest_rows: list[dict[str, Any]],
    configs: list[dict[str, Any]],
) -> bytes:
    """Build a downloadable Excel workbook for index history only.

    This is a read-only export helper. It does not write to the database or
    change any index calculation/fetch logic.
    """
    output = BytesIO()
    history_df = _build_dataframe(all_rows)
    latest_df = _build_dataframe(latest_rows)
    config_df = pd.DataFrame(configs)

    if not config_df.empty:
        config_cols = [
            "index_category",
            "index_code",
            "index_name",
            "display_name",
            "unit",
            "source_name",
            "source_url",
            "fetch_method",
            "fallback_method",
            "fetch_enabled",
            "active",
            "remarks",
        ]
        config_cols = [c for c in config_cols if c in config_df.columns]
        config_df = config_df[config_cols]

    readme_df = pd.DataFrame([
        {"Field": "Export Purpose", "Value": "All Daily Market Indices history for Excel search, review and sharing."},
        {"Field": "Generated At", "Value": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")},
        {"Field": "History Rows", "Value": len(history_df)},
        {"Field": "Latest Index Rows", "Value": len(latest_df)},
        {"Field": "Config Rows", "Value": len(config_df)},
        {"Field": "Note", "Value": "Daily Market Indices can change every day. Locked Index Snapshots for quotations are managed separately."},
    ])

    # Excel export only: normalise values that pandas/openpyxl cannot write,
    # especially timezone-aware datetime values from PostgreSQL.
    readme_df = _excel_safe_dataframe(readme_df)
    history_df = _excel_safe_dataframe(history_df)
    latest_df = _excel_safe_dataframe(latest_df)
    config_df = _excel_safe_dataframe(config_df)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        readme_df.to_excel(writer, sheet_name="Read Me", index=False)
        history_df.to_excel(writer, sheet_name="Daily Index History", index=False)
        latest_df.to_excel(writer, sheet_name="Latest Index Summary", index=False)
        config_df.to_excel(writer, sheet_name="Index Config", index=False)

        for sheet_name, df in {
            "Read Me": readme_df,
            "Daily Index History": history_df,
            "Latest Index Summary": latest_df,
            "Index Config": config_df,
        }.items():
            ws = writer.sheets[sheet_name]
            ws.freeze_panes = "A2"
            for idx, col in enumerate(df.columns, start=1):
                values = [str(col)] + ["" if pd.isna(v) else str(v) for v in df[col].head(500)]
                width = min(max(len(v) for v in values) + 2, 48)
                ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = width

    return output.getvalue()


configs = list_index_configs()
latest_rows = latest_daily_indices()
all_daily_raw = list_daily_indices(limit=100000)
all_daily_rows = []
if all_daily_raw:
    from services.market_index_service import normalise_daily_row

    all_daily_rows = [normalise_daily_row(row) for row in all_daily_raw]

today = today_local()
today_rows = [r for r in all_daily_rows if str(r.get("index_date")) == today]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Config Items", len(configs))
c2.metric("Today's Records", len(today_rows))
c3.metric("Success", sum(1 for r in today_rows if _status_label(r.get("fetch_status")) == "Success"))
c4.metric("Carry Forward", sum(1 for r in today_rows if _status_label(r.get("fetch_status")) == "Carry Forward"))
c5.metric("Need Check", sum(1 for r in today_rows if _status_label(r.get("fetch_status")) in {"Failed", "No Parser", "Manual Required", "Need Confirm", "-"}))

st.caption(f"FX automatic source: Bank of China exchange-rate page. The script stores BOC middle rate / 100 as 1 foreign currency = CNY. Source URL: {BOC_EXCHANGE_RATE_URL}")

if all_daily_rows:
    try:
        export_bytes = _build_index_history_export(all_daily_rows, latest_rows, configs)
        st.download_button(
            "Export All Index History to Excel",
            data=export_bytes,
            file_name=f"zenith_index_history_{today}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Download all Daily Market Indices history, latest summary and index configuration. This export is read-only and does not change system data.",
        )
    except Exception as exc:
        st.warning(f"Index history export is temporarily unavailable: {type(exc).__name__}: {exc}")
else:
    st.caption("Export will be available after at least one Daily Market Indices record exists.")

# Alert data is intentionally generated and stored in dedicated event rows.
# This makes review traceable and avoids relying only on temporary page logic.
try:
    alert_events = list_index_alert_events(limit=2000)
except Exception as exc:
    alert_events = []
    st.warning(f"Index alerts are temporarily unavailable: {type(exc).__name__}: {exc}")
try:
    alert_rules = list_index_alert_rules(include_inactive=True)
except Exception as exc:
    alert_rules = []
    st.warning(f"Index alert rules are temporarily unavailable: {type(exc).__name__}: {exc}")

new_alerts = [r for r in alert_events if str(r.get("alert_status") or "New").lower() == "new"]
high_alerts = [r for r in new_alerts if str(r.get("alert_level") or "").lower() == "high"]
quotation_alerts = [r for r in new_alerts if str(r.get("alert_type") or "") == "Snapshot Deviation"]

st.markdown("### Internal Index Alert Summary")
a1, a2, a3, a4 = st.columns(4)
a1.metric("New Alerts", len(new_alerts))
a2.metric("High Alerts", len(high_alerts))
a3.metric("Quotation Snapshot Alerts", len(quotation_alerts))
a4.metric("Active Rules", sum(1 for r in alert_rules if str(r.get("active") or "0").lower() in {"1", "true", "yes"}))

if high_alerts:
    st.error("High index alerts exist. Review Index Alerts before using affected quotation snapshots.")
elif new_alerts:
    st.warning("New index alerts exist. Please review affected indices or quotation snapshots.")
else:
    st.success("No new index alerts based on current active rules.")

tab_overview, tab_alerts, tab_manual, tab_daily, tab_config = st.tabs([
    "Overview",
    "Alert Rules & Events",
    "Manual Override / Confirm",
    "All Daily Records",
    "Index Config Records",
])

with tab_overview:
    with st.expander("Manual run / refresh today's index records", expanded=False):
        st.warning("This writes today's Daily Market Indices rows. Existing Manual rows are protected and will not be overwritten.")
        if st.button("Run Daily Index Fetch Now", type="primary"):
            try:
                summary = run_daily_index_fetch(operator=operator)
                st.success(
                    "Daily index fetch completed. "
                    f"Success: {summary.get('success', 0)} | "
                    f"Carry Forward: {summary.get('carry_forward', 0)} | "
                    f"Failed: {summary.get('failed', 0)} | "
                    f"Manual Required: {summary.get('manual_required', 0)} | "
                    f"Skipped Manual: {summary.get('skipped_manual', 0)} | "
                    f"Alert Events: {summary.get('alert_events', 0)}"
                )
                if summary.get("alert_error"):
                    st.warning(f"Index fetch completed, but alert evaluation needs review: {summary.get('alert_error')}")
                st.rerun()
            except Exception as exc:
                st.error(f"Daily index fetch failed: {type(exc).__name__}: {exc}")

    st.markdown("### Latest Index Summary")
    latest_df = _build_dataframe(latest_rows)
    if latest_df.empty:
        st.info("No index records found yet. Run the daily fetch job or add manual values below.")
    else:
        categories = ["All"] + sorted([str(x) for x in latest_df["index_category"].dropna().unique()]) if "index_category" in latest_df else ["All"]
        selected_category = st.radio("Category", categories, horizontal=True, key="idx_overview_category")
        show_df = latest_df.copy()
        if selected_category != "All" and "index_category" in show_df:
            show_df = show_df[show_df["index_category"] == selected_category]
        st.dataframe(show_df, width="stretch", hide_index=True, column_config=_index_column_config())

    st.markdown("### New Alerts")
    if not new_alerts:
        st.info("No new alert events.")
    else:
        alert_preview_cols = [
            "alert_date", "alert_type", "index_code", "index_name", "alert_level",
            "reference_value", "latest_value", "change_percent", "related_project_id",
            "related_client_quote_id", "related_quote_version", "alert_status", "source_note",
        ]
        alert_df = pd.DataFrame(new_alerts)
        alert_preview_cols = [c for c in alert_preview_cols if c in alert_df.columns]
        st.dataframe(alert_df[alert_preview_cols], width="stretch", hide_index=True, column_config={
            "reference_value": st.column_config.NumberColumn("reference_value", format="%.6f"),
            "latest_value": st.column_config.NumberColumn("latest_value", format="%.6f"),
            "change_percent": st.column_config.NumberColumn("change_percent", format="%.4f"),
        })

with tab_alerts:
    st.markdown("### Alert Rules and Alert Events")
    st.caption("Rules are user-maintained thresholds. Events are generated system records for traceable review. Daily Change is already visible in Daily Market Indices; Fixed Baseline and Snapshot Deviation are designed for quotation risk control.")

    left, right = st.columns([1, 1.45])
    with left:
        st.markdown("#### Index Alert Rules")
        if not configs:
            st.info("No index config records available for rule setup.")
        else:
            cfg_labels = [f"{cfg.get('display_name') or cfg.get('index_name')} [{cfg.get('index_code')}]" for cfg in configs]
            cfg_lookup = dict(zip(cfg_labels, configs))
            with st.form("index_alert_rule_form"):
                selected_cfg_label = st.selectbox("Index", cfg_labels)
                selected_cfg = cfg_lookup[selected_cfg_label]
                rule_type = st.selectbox("Alert Type", ["Fixed Baseline", "Snapshot Deviation"], help="Daily Change is already shown in Daily Market Indices. Fixed Baseline compares latest value with a manual baseline. Snapshot Deviation compares latest value with locked quotation snapshot.")
                direction = st.selectbox("Direction", ["Both", "Up", "Down"])
                r1, r2 = st.columns(2)
                medium_threshold = r1.number_input("Medium Threshold %", min_value=0.0, value=0.5 if str(selected_cfg.get('index_category')).lower() == 'fx' else 3.0, step=0.1, format="%.3f")
                high_threshold = r2.number_input("High Threshold %", min_value=0.0, value=1.0 if str(selected_cfg.get('index_category')).lower() == 'fx' else 5.0, step=0.1, format="%.3f")
                baseline_value = st.number_input("Baseline Value (Fixed Baseline only)", min_value=0.0, value=0.0, step=0.0001, format="%.6f")
                active = st.checkbox("Active", value=(rule_type == "Snapshot Deviation"))
                remarks = st.text_area("Remarks", height=80)
                submitted = st.form_submit_button("Save Alert Rule", type="primary")
                if submitted:
                    try:
                        save_index_alert_rule(
                            {
                                "index_code": selected_cfg.get("index_code"),
                                "index_name": selected_cfg.get("display_name") or selected_cfg.get("index_name"),
                                "index_category": selected_cfg.get("index_category"),
                                "alert_type": rule_type,
                                "direction": direction,
                                "medium_threshold_percent": medium_threshold,
                                "high_threshold_percent": high_threshold,
                                "baseline_value": baseline_value if rule_type == "Fixed Baseline" and baseline_value > 0 else None,
                                "active": active,
                                "remarks": remarks,
                            },
                            operator=operator,
                        )
                        st.success("Alert rule saved.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Save alert rule failed: {type(exc).__name__}: {exc}")

        if alert_rules:
            rule_df = pd.DataFrame(alert_rules)
            rule_cols = ["index_category", "index_code", "index_name", "alert_type", "direction", "medium_threshold_percent", "high_threshold_percent", "baseline_value", "active", "remarks"]
            rule_cols = [c for c in rule_cols if c in rule_df.columns]
            st.dataframe(rule_df[rule_cols], width="stretch", hide_index=True, column_config={
                "medium_threshold_percent": st.column_config.NumberColumn("medium_threshold_percent", format="%.3f"),
                "high_threshold_percent": st.column_config.NumberColumn("high_threshold_percent", format="%.3f"),
                "baseline_value": st.column_config.NumberColumn("baseline_value", format="%.6f"),
            })
        else:
            st.info("No alert rules found yet.")

    with right:
        st.markdown("#### Index Alert Events")
        c_eval, c_status = st.columns([1, 1])
        if c_eval.button("Refresh Index Alerts Now", type="primary"):
            try:
                summary = run_index_alert_evaluation(operator=operator)
                st.success(f"Alert evaluation completed. Events generated/updated: {summary.get('events', 0)}")
                st.rerun()
            except Exception as exc:
                st.error(f"Alert evaluation failed: {type(exc).__name__}: {exc}")
        event_status_filter = c_status.selectbox("Status", ["All", "New", "Reviewed", "Closed"])
        event_rows = alert_events
        if event_status_filter != "All":
            event_rows = [r for r in event_rows if str(r.get("alert_status") or "New") == event_status_filter]
        if not event_rows:
            st.info("No alert events found for this filter.")
        else:
            event_df = pd.DataFrame(event_rows)
            event_cols = ["alert_date", "alert_type", "index_code", "index_name", "alert_level", "direction", "reference_value", "latest_value", "change_percent", "related_project_id", "related_client_quote_id", "related_quote_version", "alert_status", "review_note", "source_note"]
            event_cols = [c for c in event_cols if c in event_df.columns]
            st.dataframe(event_df[event_cols], width="stretch", hide_index=True, column_config={
                "reference_value": st.column_config.NumberColumn("reference_value", format="%.6f"),
                "latest_value": st.column_config.NumberColumn("latest_value", format="%.6f"),
                "change_percent": st.column_config.NumberColumn("change_percent", format="%.4f"),
            })
            with st.expander("Mark Alert Reviewed / Closed", expanded=False):
                labels = [f"{r.get('alert_event_id')} | {r.get('alert_type')} | {r.get('index_code')} | {r.get('alert_level')} | {r.get('related_project_id') or '-'}" for r in event_rows if r.get("alert_event_id")]
                event_lookup = dict(zip(labels, [r for r in event_rows if r.get("alert_event_id")]))
                if labels:
                    selected_event = st.selectbox("Alert Event", labels)
                    new_status = st.selectbox("New Status", ["Reviewed", "Closed", "New"])
                    review_note = st.text_area("Review Note", height=80)
                    if st.button("Save Alert Review Status"):
                        try:
                            update_index_alert_event_status(event_lookup[selected_event]["alert_event_id"], new_status, review_note, operator)
                            st.success("Alert status updated.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Alert status update failed: {type(exc).__name__}: {exc}")

with tab_manual:
    st.markdown("### Manual Override / Confirm")
    if not configs:
        st.info("No active index_config records found.")
    else:
        labels = [f"{cfg.get('display_name') or cfg.get('index_name')} [{cfg.get('index_code')}]" for cfg in configs]
        lookup = dict(zip(labels, configs))
        with st.form("manual_index_form"):
            m1, m2, m3 = st.columns([1.1, 2.2, 1.2])
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
                    try:
                        run_index_alert_evaluation(target_date=index_date.isoformat(), operator=operator)
                    except Exception:
                        pass
                    st.success("Manual index saved and protected from automatic overwrite for the same date.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Manual save failed: {type(exc).__name__}: {exc}")

with tab_daily:
    st.markdown("### All Daily Records")
    all_df = _build_dataframe(all_daily_rows)
    if all_df.empty:
        st.info("No daily index records found.")
    else:
        search = st.text_input("Search", placeholder="Search index name, category, source, status...")
        show_all = all_df.copy()
        if search:
            text = search.lower().strip()
            mask = show_all.astype(str).apply(lambda col: col.str.lower().str.contains(text, na=False)).any(axis=1)
            show_all = show_all[mask]
        st.dataframe(show_all, width="stretch", hide_index=True, column_config=_index_column_config())

with tab_config:
    st.markdown("### Index Config Records")
    cfg_df = pd.DataFrame(configs)
    if cfg_df.empty:
        st.info("No active configuration records found.")
    else:
        cfg_cols = ["index_category", "index_code", "index_name", "display_name", "unit", "source_name", "fetch_method", "fallback_method", "active"]
        cfg_cols = [c for c in cfg_cols if c in cfg_df.columns]
        st.dataframe(cfg_df[cfg_cols], width="stretch", hide_index=True)
