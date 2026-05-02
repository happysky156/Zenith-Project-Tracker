from __future__ import annotations

from datetime import date
import streamlit as st

from core.auth import require_login
from services.upgrade_service import carry_forward_daily_indices, list_module_records, seed_default_index_config, upsert_module_record
from ui.theme import apply_theme, render_page_header
from ui.upgrade_ui import render_upgrade_css, render_upgrade_intro, render_metric_grid, render_layered_records

apply_theme()
render_upgrade_css()
current_user = require_login()
operator = current_user["display_name"]
render_page_header("Index Center", "Daily FX, material index and freight tracking for quotation traceability.")
render_upgrade_intro(
    "Index Center",
    "Daily Market Indices can change every day. Index Snapshots are locked when a client quotation is created so historical quotations never change.",
)

if st.button("Seed default index config", help="Creates USD/CNY, Stainless Steel 304, Carbon Steel, Zinc, Aluminium, PP, ABS, PVC, Freight to Israel and Freight to Morocco if missing."):
    inserted = seed_default_index_config()
    st.success(f"Default index config ready. Inserted {inserted} new config row(s).")
    st.rerun()

if st.button("Carry forward today's missing indices"):
    result = carry_forward_daily_indices(target_date=date.today().isoformat(), operator=operator)
    st.success(f"Carry-forward completed. Created: {result.get('created', 0)} | Skipped: {result.get('skipped', 0)}")
    st.rerun()

configs = list_module_records("Index Config", limit=500)
daily = list_module_records("Daily Market Indices", limit=1000)
today = date.today().isoformat()
today_rows = [r for r in daily if r.get("index_date") == today]
render_metric_grid({"Config Items": len(configs), "Today's Records": len(today_rows), "Carry Forward": sum(1 for r in today_rows if str(r.get('fetch_status') or '') == 'Carry Forward'), "Failed": sum(1 for r in today_rows if str(r.get('fetch_status') or '') == 'Failed')})

st.markdown("### Today Index Summary")
if not today_rows:
    st.info("No index records for today yet. Use manual input or carry-forward.")
else:
    cols = st.columns(3)
    for idx, row in enumerate(today_rows):
        with cols[idx % 3]:
            st.metric(str(row.get("index_name") or "-"), f"{row.get('index_value') or '-'} {row.get('unit') or ''}", delta=row.get("change_value"))
            st.caption(f"Source: {row.get('source_name') or '-'} | Updated: {row.get('last_updated_at') or '-'} | Status: {row.get('fetch_status') or '-'}")

with st.expander("Manual Override / Confirm", expanded=False):
    with st.form("manual_index_form"):
        c1, c2, c3 = st.columns(3)
        index_date = c1.date_input("Index Date", value=date.today())
        index_name = c2.selectbox("Index Name", [r.get("index_name") for r in configs] or ["USD/CNY"])
        index_value = c3.number_input("Index Value", min_value=0.0, value=0.0, step=0.01)
        cfg = next((r for r in configs if r.get("index_name") == index_name), {})
        c1, c2 = st.columns(2)
        unit = c1.text_input("Unit", value=str(cfg.get("unit") or ""))
        source_name = c2.text_input("Source Name", value=str(cfg.get("source_name") or "Manual"))
        source_url = st.text_input("Source URL", value=str(cfg.get("source_url") or ""))
        submitted = st.form_submit_button("Save Manual Index", type="primary")
        if submitted:
            upsert_module_record(
                "Daily Market Indices",
                {
                    "index_date": index_date.isoformat(),
                    "index_category": cfg.get("index_category"),
                    "index_name": index_name,
                    "index_value": index_value,
                    "unit": unit,
                    "source_name": source_name,
                    "source_url": source_url,
                    "fetch_method": "Manual",
                    "fetch_status": "Manual",
                    "confirmed_by_user": 1,
                },
                operator=operator,
            )
            st.success("Manual index saved.")
            st.rerun()

view = st.radio("View", ["FX Rates", "Material Indices", "Freight Indices", "All Daily Records", "Index Config"], horizontal=True)
if view == "Index Config":
    render_layered_records("Index Config", configs, key_prefix="index_config_page", summary_field="index_category", preview_columns=["index_category", "index_name", "display_name", "unit", "source_name", "fetch_method", "fallback_method", "active"])
else:
    if view == "FX Rates":
        rows = [r for r in daily if r.get("index_category") == "FX"]
    elif view == "Material Indices":
        rows = [r for r in daily if r.get("index_category") in {"Metal", "Plastic"}]
    elif view == "Freight Indices":
        rows = [r for r in daily if r.get("index_category") == "Freight"]
    else:
        rows = daily
    render_layered_records("Daily Market Indices", rows, key_prefix="daily_index_page", summary_field="fetch_status", preview_columns=["index_date", "index_category", "index_name", "index_value", "unit", "source_name", "fetch_status", "change_value", "change_percent"])
