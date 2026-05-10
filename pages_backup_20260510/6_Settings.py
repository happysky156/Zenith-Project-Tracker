from __future__ import annotations

import streamlit as st

from core.dictionaries import (
    HEALTH_STATUSES,
    OPERATION_PHASES,
    OPERATION_RESULTS,
    PEOPLE,
    PRIORITIES,
    RECORD_TYPES,
    REQUEST_TYPES,
    REQUEST_TYPE_DISPLAY_VALUES,
    SALES_PHASES,
    SALES_RESULTS,
)
from ui.theme import apply_theme, render_page_header

apply_theme()
render_page_header("Settings / Options", "Simple fixed options used across the system.")

sections = [
    ("People", PEOPLE),
    ("Record Types", RECORD_TYPES),
    ("Sales Phases", SALES_PHASES),
    ("Operation Phases", OPERATION_PHASES),
    ("Health Status", HEALTH_STATUSES),
    ("Sales Results", SALES_RESULTS),
    ("Order Results", OPERATION_RESULTS),
    ("What is needed", REQUEST_TYPE_DISPLAY_VALUES),
    ("Priorities", PRIORITIES),
]

for title, values in sections:
    st.markdown("<div class='zt-card'>", unsafe_allow_html=True)
    st.subheader(title)
    st.write(values)
    st.markdown("</div>", unsafe_allow_html=True)
