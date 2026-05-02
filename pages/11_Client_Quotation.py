from __future__ import annotations

import streamlit as st

from core.auth import require_login
from services.upgrade_service import list_module_records, upsert_module_record
from ui.theme import apply_theme, render_page_header
from ui.upgrade_ui import render_upgrade_css, render_upgrade_intro, render_metric_grid, render_layered_records, render_simple_filter_bar

apply_theme()
render_upgrade_css()
current_user = require_login()
operator = current_user["display_name"]
render_page_header("Client Quotation", "Client quotation versions, quotation lines and locked index snapshots.")
render_upgrade_intro(
    "Client Quotation",
    "Each Project ID gets automatic V1 / V2 / V3 quotation versions when Quote Version is blank. Sent quotes should be treated as locked; create a new version for revision.",
)

headers = list_module_records("Client Quotation Header", limit=1000)
lines = list_module_records("Client Quotation Lines", limit=1000)
snapshots = list_module_records("Index Snapshot", limit=1000)
render_metric_grid({"Quotation Versions": len(headers), "Quotation Lines": len(lines), "Locked Snapshots": len(snapshots), "Accepted": sum(1 for r in headers if str(r.get('quote_status') or '').lower() == 'accepted')})

with st.expander("Create client quotation header", expanded=False):
    with st.form("client_quote_header_form"):
        c1, c2, c3 = st.columns(3)
        project_id = c1.text_input("Project ID")
        quote_date = c2.date_input("Quote Date", value=None)
        quote_version = c3.text_input("Quote Version", placeholder="Leave blank for auto V1/V2/V3")
        c1, c2, c3 = st.columns(3)
        client_code = c1.text_input("Client Code")
        client_name = c2.text_input("Client Name")
        quote_status = c3.selectbox("Quote Status", ["Draft", "Sent", "Revised", "Accepted", "Lost"])
        c1, c2 = st.columns(2)
        price_term = c1.text_input("Price Term")
        quote_currency = c2.text_input("Quote Currency", value="USD")
        remarks = st.text_area("Remarks", height=80)
        submitted = st.form_submit_button("Save Client Quotation Header", type="primary")
        if submitted:
            if not project_id.strip():
                st.error("Project ID is required.")
            else:
                upsert_module_record(
                    "Client Quotation Header",
                    {
                        "project_id": project_id,
                        "quote_version": quote_version,
                        "quote_date": quote_date.isoformat() if quote_date else None,
                        "client_code": client_code,
                        "client_name": client_name,
                        "quote_status": quote_status,
                        "price_term": price_term,
                        "quote_currency": quote_currency,
                        "remarks": remarks,
                    },
                    operator=operator,
                )
                st.success("Client quotation header saved.")
                st.rerun()

view = st.radio("View", ["Headers", "Lines", "Index Snapshots"], horizontal=True)
if view == "Headers":
    filtered = render_simple_filter_bar("Client Quotation Header", headers)
    render_layered_records("Client Quotation Header", filtered, key_prefix="client_header_page", summary_field="quote_status", preview_columns=["client_quote_id", "project_id", "quote_version", "quote_date", "client_code", "quote_status", "price_term", "quote_currency"])
elif view == "Lines":
    filtered = render_simple_filter_bar("Client Quotation Lines", lines)
    render_layered_records("Client Quotation Lines", filtered, key_prefix="client_line_page", preview_columns=["client_quote_id", "project_id", "item_code", "client_unit_price", "supplier_unit_cost", "quantity_basis", "estimated_gp", "estimated_gp_percent"])
else:
    filtered = render_simple_filter_bar("Index Snapshot", snapshots)
    render_layered_records("Index Snapshot", filtered, key_prefix="snapshot_page", preview_columns=["project_id", "item_code", "quote_version", "snapshot_date", "material_index_name", "material_index_value", "freight_route", "exchange_rate_pair", "exchange_rate_value"])
