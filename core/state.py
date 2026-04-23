from __future__ import annotations

import streamlit as st


DEFAULTS = {
    "selected_detail_type": "Sales",
    "selected_detail_id": None,
    "selected_project_id": None,  # backward compatibility for older jump logic
    "sales_filters": {},
    "operation_filters": {},
    "meeting_view": "Team View",
}


def init_session_state() -> None:
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value



def set_selected_detail(record_type: str, record_id: str) -> None:
    st.session_state["selected_detail_type"] = record_type
    st.session_state["selected_detail_id"] = record_id
    if record_type == "Sales":
        st.session_state["selected_project_id"] = record_id
