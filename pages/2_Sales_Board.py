from __future__ import annotations

import streamlit as st

from core.dictionaries import PEOPLE
from services.project_service import apply_board_filters, list_board_projects
from ui.filters import render_common_filters
from ui.project_table import render_board_cards, render_project_table
from ui.theme import apply_theme, render_page_header

apply_theme()
render_page_header("Sales Board", "High-frequency sales actions with automatic linked-order visibility.")

st.markdown("<div class='zt-toolbar-panel'>", unsafe_allow_html=True)
st.markdown("<div class='zt-section-kicker'>Sales control panel</div>", unsafe_allow_html=True)
st.markdown("<div class='zt-subtle-text'>Use this page for fast project follow-up: quote, sample, waiting status, decision raising and meeting preparation. Linked orders come from Operation automatically through <b>Project ID</b>.</div>", unsafe_allow_html=True)
toolbar_col1, toolbar_col2 = st.columns([1, 2])
operator = toolbar_col1.selectbox("Acting User", options=PEOPLE, index=PEOPLE.index("Harley"), key="sales_operator")
show_table = toolbar_col2.toggle("Also show compact table view", value=False, key="sales_show_table")
st.markdown("</div>", unsafe_allow_html=True)

filters = render_common_filters("sales", "Sales")
rows = apply_board_filters(list_board_projects("Sales"), filters, "Sales")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Visible Sales Projects", len(rows))
m2.metric("Need Decision", sum(1 for r in rows if (r.get("health_status") or "") == "Need Decision"))
m3.metric("Review This Week", sum(1 for r in rows if bool(r.get("review_this_week"))))
m4.metric("Linked Orders", sum(int(r.get("linked_order_count") or 0) for r in rows))

if show_table:
    st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='zt-panel-title'>Compact table view</div>", unsafe_allow_html=True)
    render_project_table(
        rows,
        [
            "project_id",
            "project_name",
            "client_code",
            "linked_order_count",
            "linked_orders",
            "current_owner",
            "phase",
            "health_status",
            "quote_round",
            "sample_round",
            "main_issue",
            "next_step_owner",
            "target_date",
            "last_event",
            "days_since_status_update",
            "days_since_review",
            "review_this_week",
        ],
        empty_message="No Sales projects found.",
    )
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
st.markdown("<div class='zt-panel-title'>Sales project cards</div>", unsafe_allow_html=True)
render_board_cards(
    rows,
    entity_type="Sales",
    operator=operator,
    source_page="Sales Board",
    empty_message="No Sales projects found.",
)
st.markdown("</div>", unsafe_allow_html=True)
