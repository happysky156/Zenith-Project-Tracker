from __future__ import annotations

import streamlit as st

from core.auth import require_login
from services.upgrade_service import list_module_records, upsert_module_record
from services.export_service import render_standard_export_panel
from ui.theme import apply_theme, render_page_header
from ui.upgrade_ui import render_upgrade_css, render_upgrade_intro, render_metric_grid, render_layered_records, render_simple_filter_bar

apply_theme()
render_upgrade_css()
current_user = require_login()
operator = current_user["display_name"]
MODULE_NAME = "Sample Tracking"
render_page_header("Sample Board", "Customer samples, testing samples, retained samples and sample follow-up.")
render_upgrade_intro(
    "Sample Board",
    "Sample images are stored as links in Phase 1 to keep the system fast. Testing follow-up is kept inside sample tracking for the first version.",
)

rows = list_module_records(MODULE_NAME, limit=1000)
render_metric_grid({"Sample Records": len(rows), "In Progress": sum(1 for r in rows if str(r.get('sample_status') or '').lower() == 'in progress'), "Testing": sum(1 for r in rows if str(r.get('test_status') or '').lower() in {'testing', 'sent to lab'}), "Need Revision": sum(1 for r in rows if str(r.get('sample_status') or '').lower() == 'need revision')})

with st.expander("Add sample tracking record", expanded=False):
    with st.form("sample_form"):
        c1, c2, c3 = st.columns(3)
        project_id = c1.text_input("Project ID")
        rfq_item_ref = c2.text_input("RFQ Item Ref")
        supplier_name = c3.text_input("Supplier Name")
        c1, c2, c3 = st.columns(3)
        sample_type = c1.selectbox("Sample Type", ["", "Initial Sample", "Revised Sample", "Approved Sample", "Testing Sample", "Pre-production Sample", "Mass Production Sample", "Reference Sample"])
        sample_round = c2.text_input("Sample Round", value="1")
        sample_status = c3.selectbox("Sample Status", ["Not Started", "In Progress", "Sent", "Approved", "Rejected", "Need Revision"])
        c1, c2 = st.columns(2)
        target_sample_date = c1.date_input("Target Sample Date", value=None)
        test_status = c2.selectbox("Test Status", ["Not Required", "Pending", "Sent to Lab", "Testing", "Passed", "Failed", "Need Retest"])
        client_feedback = st.text_area("Client Feedback", height=80)
        next_step = st.text_area("Next Step", height=80)
        c1, c2 = st.columns(2)
        next_step_owner = c1.text_input("Next Step Owner")
        sample_folder_link = c2.text_input("Sample Folder Link")
        remarks = st.text_area("Remarks", height=80)
        submitted = st.form_submit_button("Save Sample Record", type="primary")
        if submitted:
            if not project_id.strip():
                st.error("Project ID is required.")
            else:
                upsert_module_record(
                    MODULE_NAME,
                    {
                        "project_id": project_id,
                        "rfq_item_ref": rfq_item_ref,
                        "supplier_name": supplier_name,
                        "sample_type": sample_type,
                        "sample_round": sample_round,
                        "sample_status": sample_status,
                        "target_sample_date": target_sample_date.isoformat() if target_sample_date else None,
                        "test_status": test_status,
                        "client_feedback": client_feedback,
                        "next_step": next_step,
                        "next_step_owner": next_step_owner,
                        "sample_folder_link": sample_folder_link,
                        "remarks": remarks,
                    },
                    operator=operator,
                )
                st.success("Sample tracking record saved.")
                st.rerun()

filtered = render_simple_filter_bar(MODULE_NAME, rows)
render_standard_export_panel(
    board_name="Sample Board",
    current_rows=rows,
    filtered_rows=filtered,
    template_names=["Sample Tracking Template", "QP-02 Sample Control Template"],
    key_prefix="sample_board",
)
render_layered_records(MODULE_NAME, filtered, key_prefix="sample_page", summary_field="sample_status", preview_columns=["project_id", "rfq_item_ref", "supplier_name", "sample_type", "sample_round", "sample_status", "target_sample_date", "test_status", "next_step_owner", "sample_folder_link"])
