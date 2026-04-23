from __future__ import annotations

import streamlit as st

from core.dictionaries import PEOPLE
from services.project_service import apply_board_filters, list_board_projects
from ui.filters import render_common_filters
from ui.project_table import render_board_cards, render_project_table
from ui.theme import apply_theme, render_page_header

apply_theme()
render_page_header("Operation Board", "Execution-focused order header view for payment, production, shipment and risk follow-up.")

st.markdown("<div class='zt-toolbar-panel'>", unsafe_allow_html=True)
st.markdown("<div class='zt-section-kicker'>Execution control panel</div>", unsafe_allow_html=True)
st.markdown("<div class='zt-subtle-text'>Monitor payment, production, shipment and delivery risk from one place. Each row is an <b>Order No.</b>, while the linked project is pulled automatically from Sales through <b>Project ID</b>.</div>", unsafe_allow_html=True)
toolbar_col1, toolbar_col2 = st.columns([1, 2])
operator = toolbar_col1.selectbox("Acting User", options=PEOPLE, index=PEOPLE.index("Harley"), key="operation_operator")
show_table = toolbar_col2.toggle("Also show compact table view", value=False, key="operation_show_table")
st.markdown("</div>", unsafe_allow_html=True)

filters = render_common_filters("operation", "Operation")
rows = apply_board_filters(list_board_projects("Operation"), filters, "Operation")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Visible Orders", len(rows))
m2.metric("Delayed / Blocked", sum(1 for r in rows if (r.get("health_status") or "") in {"Delayed", "Blocked"}))
m3.metric("Review This Week", sum(1 for r in rows if bool(r.get("review_this_week"))))
m4.metric("Unlinked Project", sum(1 for r in rows if not r.get("linked_project_name")))

if show_table:
    st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='zt-panel-title'>Compact table view</div>", unsafe_allow_html=True)
    render_project_table(
        rows,
        [
            "order_no",
            "project_id",
            "linked_project_name",
            "client_code",
            "current_owner",
            "phase",
            "health_status",
            "result_status",
            "waiting_for_text",
            "need_from_meeting",
            "next_step_owner",
            "target_date",
            "last_event",
            "days_since_status_update",
            "days_since_review",
        ],
        empty_message="No Operation orders found.",
    )
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
st.markdown("<div class='zt-panel-title'>Operation order cards</div>", unsafe_allow_html=True)
render_board_cards(
    rows,
    entity_type="Operation",
    operator=operator,
    source_page="Operation Board",
    empty_message="No Operation orders found.",
)
st.markdown("</div>", unsafe_allow_html=True)
