from __future__ import annotations

import streamlit as st

from core.auth import require_login
from services.upgrade_service import list_module_records, upsert_module_record, field_display_map
from ui.theme import apply_theme, render_page_header
from ui.upgrade_ui import render_upgrade_css, render_upgrade_intro, render_metric_grid, render_layered_records, render_simple_filter_bar

apply_theme()
render_upgrade_css()
current_user = require_login()
operator = current_user["display_name"]
render_page_header("Supplier Details", "Shared supplier master data for Sales projects and Operation orders.")
render_upgrade_intro(
    "Supplier Details",
    "Supplier ID is the system key. Supplier Code is your internal code and can stay blank for expo or uncontacted suppliers. Active status is calculated from open order details.",
)

rows = list_module_records("Supplier Details", limit=1000)
active_count = sum(1 for r in rows if str(r.get("active_status") or "").lower() == "active")
render_metric_grid({"Total Suppliers": len(rows), "Active Suppliers": active_count, "No Supplier Code": sum(1 for r in rows if not r.get("supplier_code")), "High Risk": sum(1 for r in rows if str(r.get("quality_risk") or "").lower() == "high" or str(r.get("commercial_risk") or "").lower() == "high")})

with st.expander("Add / update supplier", expanded=False):
    with st.form("supplier_form"):
        c1, c2, c3 = st.columns(3)
        supplier_code = c1.text_input("Supplier Code")
        supplier_name = c2.text_input("Supplier Name")
        supplier_source = c3.selectbox("Supplier Source", ["", "Existing", "Expo", "Online", "Referral", "Other", "Imported"])
        c1, c2, c3 = st.columns(3)
        contact_status = c1.selectbox("Contact Status", ["", "Not Contacted", "Contacted", "Quoted", "Ordered"])
        contact_person = c2.text_input("Contact Person")
        phone = c3.text_input("Phone")
        email = st.text_input("Email")
        with st.expander("Capability and risk", expanded=False):
            c1, c2 = st.columns(2)
            main_products = c1.text_area("Main Products", height=80)
            main_process = c2.text_area("Main Process", height=80)
            c1, c2, c3 = st.columns(3)
            quality_risk = c1.selectbox("Quality Risk", ["", "Low", "Medium", "High"])
            commercial_risk = c2.selectbox("Commercial Risk", ["", "Low", "Medium", "High"])
            supplier_level = c3.selectbox("Supplier Level", ["", "A", "B", "C", "Pending"])
        remarks = st.text_area("Remarks", height=80)
        submitted = st.form_submit_button("Save Supplier", type="primary")
        if submitted:
            if not supplier_name.strip():
                st.error("Supplier Name is required.")
            else:
                upsert_module_record(
                    "Supplier Details",
                    {
                        "supplier_code": supplier_code,
                        "supplier_name": supplier_name,
                        "supplier_source": supplier_source,
                        "contact_status": contact_status,
                        "contact_person": contact_person,
                        "phone": phone,
                        "email": email,
                        "main_products": main_products,
                        "main_process": main_process,
                        "quality_risk": quality_risk,
                        "commercial_risk": commercial_risk,
                        "supplier_level": supplier_level,
                        "remarks": remarks,
                    },
                    operator=operator,
                )
                st.success("Supplier saved.")
                st.rerun()

filtered = render_simple_filter_bar("Supplier Details", rows)
render_layered_records(
    "Supplier Details",
    filtered,
    key_prefix="supplier_page",
    summary_field="active_status",
    preview_columns=["supplier_id", "supplier_code", "supplier_name", "supplier_source", "contact_status", "active_status", "active_reason", "quality_risk", "commercial_risk"],
)
