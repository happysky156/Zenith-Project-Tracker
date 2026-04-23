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
    SALES_PHASES,
    SALES_RESULTS,
)
from ui.theme import apply_theme, render_page_header

apply_theme()
render_page_header("Settings / Dictionaries", "Code-based dictionaries and fixed options used across the MVP.")

sections = [
    ("People", PEOPLE),
    ("Record Types", RECORD_TYPES),
    ("Sales Phases", SALES_PHASES),
    ("Operation Phases", OPERATION_PHASES),
    ("Health Statuses", HEALTH_STATUSES),
    ("Sales Results", SALES_RESULTS),
    ("Operation Results", OPERATION_RESULTS),
    ("Request Types", REQUEST_TYPES),
    ("Priorities", PRIORITIES),
]

for title, values in sections:
    st.markdown("<div class='zt-card'>", unsafe_allow_html=True)
    st.subheader(title)
    st.write(values)
    st.markdown("</div>", unsafe_allow_html=True)
