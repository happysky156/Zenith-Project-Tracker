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
render_page_header("Price Comparison", "Supplier-side cost quotations by Project ID + Item Code + Supplier.")
render_upgrade_intro(
    "Supplier Price Comparison",
    "This page records supplier prices only. Client quotation is managed separately so margin and index snapshots can be traced clearly.",
)

rows = list_module_records("Supplier Price Comparison", limit=1000)
completed = sum(1 for r in rows if str(r.get("comparison_status") or "").lower() == "completed")
selected = sum(1 for r in rows if int(r.get("selected_supplier") or 0) == 1)
recommended = sum(1 for r in rows if int(r.get("recommended_supplier") or 0) == 1)
render_metric_grid({"Quote Records": len(rows), "Completed": completed, "Selected": selected, "Recommended": recommended})

with st.expander("Add supplier quote", expanded=False):
    with st.form("supplier_quote_form"):
        c1, c2, c3 = st.columns(3)
        project_id = c1.text_input("Project ID")
        item_code = c2.text_input("Item Code")
        quote_round = c3.text_input("Quote Round", value="1")
        c1, c2, c3 = st.columns(3)
        supplier_code = c1.text_input("Supplier Code")
        supplier_name = c2.text_input("Supplier Name")
        quote_date = c3.date_input("Quote Date", value=None)
        c1, c2, c3, c4 = st.columns(4)
        supplier_unit_cost = c1.number_input("Supplier Unit Cost", min_value=0.0, step=0.01, value=0.0)
        currency = c2.text_input("Currency", value="USD")
        price_term = c3.text_input("Price Term")
        lead_time = c4.text_input("Lead Time")
        c1, c2 = st.columns(2)
        recommended_supplier = c1.checkbox("Recommended Supplier")
        selected_supplier = c2.checkbox("Selected Supplier")
        with st.expander("Risk / missing info", expanded=False):
            quotation_quality = st.selectbox("Quotation Quality", ["", "Complete", "Partial", "Poor"])
            quotation_risk = st.selectbox("Quotation Risk", ["", "Low", "Medium", "High"])
            missing_info = st.text_area("Missing Information", height=80)
            selection_reason = st.text_area("Selection Reason", height=80)
        remarks = st.text_area("Remarks", height=80)
        submitted = st.form_submit_button("Save Supplier Quote", type="primary")
        if submitted:
            if not project_id.strip() or not item_code.strip() or not supplier_name.strip():
                st.error("Project ID, Item Code and Supplier Name are required.")
            else:
                upsert_module_record(
                    "Supplier Price Comparison",
                    {
                        "project_id": project_id,
                        "item_code": item_code,
                        "supplier_code": supplier_code,
                        "supplier_name": supplier_name,
                        "quote_round": quote_round,
                        "quote_date": quote_date.isoformat() if quote_date else None,
                        "supplier_unit_cost": supplier_unit_cost,
                        "currency": currency,
                        "price_term": price_term,
                        "lead_time": lead_time,
                        "recommended_supplier": recommended_supplier,
                        "selected_supplier": selected_supplier,
                        "quotation_quality": quotation_quality,
                        "quotation_risk": quotation_risk,
                        "missing_info": missing_info,
                        "selection_reason": selection_reason,
                        "remarks": remarks,
                    },
                    operator=operator,
                )
                st.success("Supplier quote saved.")
                st.rerun()

filtered = render_simple_filter_bar("Supplier Price Comparison", rows)
render_layered_records(
    "Supplier Price Comparison",
    filtered,
    key_prefix="price_page",
    summary_field="comparison_status",
    preview_columns=["project_id", "item_code", "supplier_code", "supplier_name", "quote_round", "supplier_unit_cost", "currency", "recommended_supplier", "selected_supplier", "comparison_status"],
)
