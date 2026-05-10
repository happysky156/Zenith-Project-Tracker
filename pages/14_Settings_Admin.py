from __future__ import annotations

import streamlit as st

from core.auth import require_login
from ui.index_center_view import render_index_admin_center
from ui.theme import apply_theme, render_page_header

apply_theme()
current_user = require_login()
operator = current_user.get("display_name") or current_user.get("email") or "User"
render_page_header("Settings / Admin", "System settings, reference data, index center and administrative tools.")

tab_index, tab_permissions, tab_templates = st.tabs(["Index Center", "Permissions", "Template Versions"])
with tab_index:
    render_index_admin_center(operator=operator)
with tab_permissions:
    st.markdown("### Permissions")
    st.info("Login and Import Center permission logic are retained from the existing system. Import remains restricted to authorised emails.")
with tab_templates:
    st.markdown("### Template Versions")
    st.info("Template definitions are generated from shared services so Import Center and process pages use one template source.")
