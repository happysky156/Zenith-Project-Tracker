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
render_page_header("Order Details", "Order item details, extra costs and gross profit calculation.")
render_upgrade_intro(
    "Order Details and Costs",
    "Order Details supplements Operation Board without changing original operation status logic. Gross Profit is calculated from client price, supplier cost and Order Costs.",
)

order_rows = list_module_records("Order Details", limit=1000)
cost_rows = list_module_records("Order Costs", limit=1000)
revenue = sum(float(r.get("sales_revenue") or 0) for r in order_rows)
gp = sum(float(r.get("gross_profit") or 0) for r in order_rows)
render_metric_grid({"Order Detail Rows": len(order_rows), "Cost Rows": len(cost_rows), "Revenue": f"{revenue:,.2f}", "Gross Profit": f"{gp:,.2f}"})

with st.expander("Add order cost", expanded=False):
    with st.form("order_cost_form"):
        c1, c2, c3 = st.columns(3)
        order_no = c1.text_input("Order No")
        project_id = c2.text_input("Project ID")
        item_code = c3.text_input("Item Code")
        c1, c2, c3 = st.columns(3)
        cost_type = c1.selectbox("Cost Type", ["Testing Fee", "Courier Fee", "Internal Inspection Fee", "Third-party Inspection Fee", "Freight Fee", "Bank Charge", "Packaging Extra Cost", "Tooling Cost", "Sample Cost", "Other Cost"])
        cost_amount = c2.number_input("Cost Amount", min_value=0.0, step=0.01)
        currency = c3.text_input("Currency", value="USD")
        remarks = st.text_area("Remarks", height=80)
        submitted = st.form_submit_button("Save Order Cost", type="primary")
        if submitted:
            if not order_no.strip() or not cost_type.strip():
                st.error("Order No and Cost Type are required.")
            else:
                upsert_module_record("Order Costs", {"order_no": order_no, "project_id": project_id, "item_code": item_code, "cost_type": cost_type, "cost_amount": cost_amount, "currency": currency, "remarks": remarks}, operator=operator)
                st.success("Order cost saved and GP recalculated.")
                st.rerun()

view = st.radio("View", ["Order Details", "Order Costs"], horizontal=True)
if view == "Order Details":
    filtered = render_simple_filter_bar("Order Details", order_rows)
    render_layered_records("Order Details", filtered, key_prefix="order_detail_page", summary_field="shipment_status", preview_columns=["order_no", "project_id", "item_code", "supplier_name", "order_qty", "client_unit_price", "supplier_unit_cost", "extra_cost", "gross_profit", "gross_profit_percent", "shipment_status"])
else:
    filtered = render_simple_filter_bar("Order Costs", cost_rows)
    render_layered_records("Order Costs", filtered, key_prefix="order_cost_page", summary_field="cost_type", preview_columns=["order_no", "project_id", "item_code", "cost_type", "cost_amount", "currency", "paid_by", "charge_to_client", "cost_date"])
