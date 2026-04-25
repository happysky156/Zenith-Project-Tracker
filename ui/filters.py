from __future__ import annotations

import streamlit as st

from core.dictionaries import HEALTH_STATUSES, PEOPLE, PRIORITIES, OPERATION_PHASES, SALES_PHASES


def render_common_filters(prefix: str, record_type: str) -> dict[str, object]:
    phase_options = SALES_PHASES if record_type == "Sales" else OPERATION_PHASES
    search_placeholder = "Search Project ID, project, client, issue or next step..." if record_type == "Sales" else "Search Order No, Project ID, linked project, client, issue or next step..."

    st.markdown(
        """
        <div class='zt-filter-intro-card'>
            <div class='zt-section-kicker'>Filter & focus</div>
            <div class='zt-subtle-text'>Narrow the list by owner, phase, health and meeting relevance. Use search to quickly find the right item.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    owner = r1c1.selectbox("Current Owner", options=[""] + PEOPLE, key=f"{prefix}_owner")
    phase = r1c2.selectbox("Phase", options=[""] + phase_options, key=f"{prefix}_phase")
    health = r1c3.selectbox("Health", options=[""] + HEALTH_STATUSES, key=f"{prefix}_health")
    priority = r1c4.selectbox("Priority", options=[""] + PRIORITIES, key=f"{prefix}_priority")

    r2c1, r2c2, r2c3, r2c4 = st.columns([2.2, 1, 1, 1])
    search = r2c1.text_input(
        "Search",
        value=st.session_state.get(f"{prefix}_search", ""),
        key=f"{prefix}_search",
        placeholder=search_placeholder,
    )
    review_only = r2c2.checkbox("Review this week", value=st.session_state.get(f"{prefix}_review_only", False), key=f"{prefix}_review_only")
    meeting_pool_only = r2c3.checkbox("Meeting pool only", value=st.session_state.get(f"{prefix}_meeting_only", False), key=f"{prefix}_meeting_only")
    high_attention_only = r2c4.checkbox("High attention only", value=st.session_state.get(f"{prefix}_high_attention_only", False), key=f"{prefix}_high_attention_only")

    return {
        "owner": owner or None,
        "phase": phase or None,
        "health": health or None,
        "priority": priority or None,
        "search": (search or "").strip(),
        "review_only": bool(review_only),
        "meeting_pool_only": bool(meeting_pool_only),
        "high_attention_only": bool(high_attention_only),
    }
