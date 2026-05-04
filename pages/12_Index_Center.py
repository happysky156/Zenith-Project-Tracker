from __future__ import annotations

from datetime import date
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


configs = list_index_configs()
latest_rows = latest_daily_indices()
all_daily_raw = list_daily_indices(limit=3000)
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
    st.dataframe(show_df, width="stretch", hide_index=True)

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
    st.dataframe(show_all, width="stretch", hide_index=True)

with st.expander("Index Config Records", expanded=False):
    cfg_df = pd.DataFrame(configs)
    if cfg_df.empty:
        st.info("No active configuration records found.")
    else:
        cfg_cols = ["index_category", "index_code", "index_name", "display_name", "unit", "source_name", "fetch_method", "fallback_method", "active"]
        cfg_cols = [c for c in cfg_cols if c in cfg_df.columns]
        st.dataframe(cfg_df[cfg_cols], width="stretch", hide_index=True)
