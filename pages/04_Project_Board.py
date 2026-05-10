from __future__ import annotations

from html import escape
from textwrap import dedent

import streamlit as st

from core.auth import require_login
from services.project_service import apply_board_filters, list_board_projects
from ui.filters import render_common_filters
from ui.project_table import render_board_cards, render_project_table
from ui.theme import apply_theme, render_page_header

apply_theme()
current_user = require_login()
operator = current_user["display_name"]
render_page_header("Project Board", "Project overview, linked RFQ/order visibility and project follow-up.")


def _html(markup: str) -> str:
    return dedent(markup).strip()


def _n(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _metric_card(label: str, value: object, sub: str, accent: str = "#111111") -> str:
    return _html(
        f"""
        <div class='zt-board-metric-card' style='--bar:{accent}'>
            <div class='zt-board-metric-label'>{escape(label)}</div>
            <div class='zt-board-metric-value'>{_n(value)}</div>
            <div class='zt-board-metric-sub'>{escape(sub)}</div>
        </div>
        """
    )


def _section_head(kicker: str, title: str, note: str | None = None) -> None:
    note_html = f"<div class='zt-board-section-note'>{escape(note)}</div>" if note else ""
    st.markdown(
        _html(
            f"""
            <div class='zt-board-section-head'>
                <div>
                    <div class='zt-section-kicker'>{escape(kicker)}</div>
                    <div class='zt-board-section-title'>{escape(title)}</div>
                </div>
                {note_html}
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


st.markdown(
    _html(
        """
        <div class='zt-filter-intro-card'>
            <div class='zt-section-kicker'>Sales control panel</div>
            <div class='zt-subtle-text'>Use this page for fast project follow-up: quote, sample, waiting status, decision raising and meeting preparation. Linked orders come from Operation automatically through <b>Project ID</b>.</div>
        </div>
        """
    ),
    unsafe_allow_html=True,
)

toolbar_col1, toolbar_col2 = st.columns([1, 2])
toolbar_col1.text_input("Acting User", value=operator, disabled=True)
show_table = toolbar_col2.toggle("Also show compact table view", value=False, key="sales_show_table")

filters = render_common_filters("sales", "Sales")
rows = apply_board_filters(list_board_projects("Sales"), filters, "Sales")

need_decision = sum(1 for r in rows if (r.get("health_status") or "") == "Need Decision")
review_this_week = sum(1 for r in rows if bool(r.get("review_this_week")))
linked_orders = sum(int(r.get("linked_order_count") or 0) for r in rows)

st.markdown(
    _html(
        f"""
        <div class='zt-board-metric-grid'>
            {_metric_card('Visible Sales Projects', len(rows), 'Filtered Sales projects currently shown', '#111111')}
            {_metric_card('Need Decision', need_decision, 'Items requiring management decision', '#c5161d' if need_decision else '#111111')}
            {_metric_card('Review This Week', review_this_week, 'Items selected for weekly review', '#c5161d' if review_this_week else '#111111')}
            {_metric_card('Linked Orders', linked_orders, 'Operation orders linked by Project ID', '#2c2c2c')}
        </div>
        """
    ),
    unsafe_allow_html=True,
)

if show_table:
    _section_head("Compact view", "Compact table view", "Use this only when you need a dense Excel-like list before opening a project card.")
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

_section_head(
    "Project cards",
    "Sales project cards",
    "Red buttons show the current recorded status only. White buttons are available actions.",
)
render_board_cards(
    rows,
    entity_type="Sales",
    operator=operator,
    source_page="Sales Board",
    empty_message="No Sales projects found.",
)
