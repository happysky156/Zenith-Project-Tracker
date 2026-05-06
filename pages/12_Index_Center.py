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
    run_daily_index_fetch,
    save_manual_index,
    today_local,
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
                f"Skipped Manual: {summary.get('skipped_manual', 0)}"
            )
            st.rerun()
        except Exception as exc:
            st.error(f"Daily index fetch failed: {type(exc).__name__}: {exc}")

st.markdown("### Latest Index Summary")
latest_df = _build_dataframe(latest_rows)
if latest_df.empty:
    st.info("No index records found yet. Run the daily fetch job or add manual values below.")
else:
    categories = ["All"] + sorted([str(x) for x in latest_df["index_category"].dropna().unique()]) if "index_category" in latest_df else ["All"]
    selected_category = st.radio("Category", categories, horizontal=True)
    show_df = latest_df.copy()
    if selected_category != "All" and "index_category" in show_df:
        show_df = show_df[show_df["index_category"] == selected_category]
    st.dataframe(show_df, width="stretch", hide_index=True, column_config=_index_column_config())

with st.expander("Manual Override / Confirm", expanded=False):
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
                    st.success("Manual index saved and protected from automatic overwrite for the same date.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Manual save failed: {type(exc).__name__}: {exc}")

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

with st.expander("Index Config Records", expanded=False):
    cfg_df = pd.DataFrame(configs)
    if cfg_df.empty:
        st.info("No active configuration records found.")
    else:
        cfg_cols = ["index_category", "index_code", "index_name", "display_name", "unit", "source_name", "fetch_method", "fallback_method", "active"]
        cfg_cols = [c for c in cfg_cols if c in cfg_df.columns]
        st.dataframe(cfg_df[cfg_cols], width="stretch", hide_index=True)
