from __future__ import annotations

import streamlit as st

from services.export_service import render_standard_export_panel

from core.auth import require_login
from ui.theme import apply_theme, render_page_header

apply_theme()
require_login()
render_page_header("Complaint / CAPA Board", "Quality complaints, Corrective Action and Preventive Action, closure evidence and supplier history update.")

render_standard_export_panel(
    board_name="Complaint / CAPA Board",
    current_rows=[],
    filtered_rows=[],
    template_names=["QP-05 Quality Complaint Closure Template"],
    key_prefix="complaint_capa_board",
)

tabs = st.tabs(["Complaint Overview", "Open Complaints", "Issue Detail", "Root Cause Analysis", "Corrective & Preventive Actions", "Closure", "Complaint History"])
with tabs[0]:
    st.info("Complaint / CAPA records will be added as a dedicated extension. Existing project, order and supplier data are not changed.")
for tab, title in zip(tabs[1:], ["Open Complaints", "Issue Detail", "Root Cause Analysis", "Corrective & Preventive Actions", "Closure", "Complaint History"]):
    with tab:
        st.markdown(f"### {title}")
        st.info("No dedicated Complaint / CAPA records yet.")
