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
render_page_header(
    "Order Board",
    "Execution-focused order control for payment, production, shipment and delivery risk follow-up.",
)


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
            <div class='zt-section-kicker'>Operation control panel</div>
            <div class='zt-subtle-text'>Use this page for fast order follow-up: payment, production, shipment, supplier waiting, delivery risk and weekly meeting preparation. Each card is an <b>Order No.</b>; the linked Sales project is pulled automatically through <b>Project ID</b>.</div>
        </div>
        """
    ),
    unsafe_allow_html=True,
)

operator_col, archive_col, view_col = st.columns([1, 1.4, 1.6])
operator_col.text_input("Acting User", value=operator, disabled=True)
archive_view = archive_col.radio(
    "Archive view",
    options=["Active only", "Archived only", "All"],
    index=0,
    horizontal=True,
    help="Archived orders are hidden by default but kept for history and audit.",
)
show_table = view_col.toggle("Also show compact table view", value=False, key="operation_show_table")

filters = render_common_filters("operation", "Operation")
base_rows = list_board_projects("Operation", include_archived=(archive_view != "Active only"))
if archive_view == "Archived only":
    base_rows = [r for r in base_rows if bool(r.get("is_archived"))]
rows = apply_board_filters(base_rows, filters, "Operation")

blocked_delayed = sum(1 for r in rows if (r.get("health_status") or "") in {"Delayed", "Blocked"})
review_this_week = sum(1 for r in rows if bool(r.get("review_this_week")))
unlinked_project = sum(1 for r in rows if not r.get("linked_project_name"))
shipment_progress = sum(1 for r in rows if (r.get("result_status") or "") in {"Partial Shipped", "Complete Shipped", "Paid Closed"})

st.markdown(
    _html(
        f"""
        <div class='zt-board-metric-grid'>
            {_metric_card('Visible Orders', len(rows), f'Filtered Orders currently shown ({archive_view})', '#111111')}
            {_metric_card('Delayed / Blocked', blocked_delayed, 'Orders needing execution attention', '#c5161d' if blocked_delayed else '#111111')}
            {_metric_card('Review This Week', review_this_week, 'Orders selected for weekly review', '#c5161d' if review_this_week else '#111111')}
            {_metric_card('Shipment Progress', shipment_progress, 'Partial shipped, complete shipped or paid closed', '#2c2c2c')}
        </div>
        """
    ),
    unsafe_allow_html=True,
)

if unlinked_project:
    st.markdown(
        _html(
            f"""
            <div class='zt-attention-strip zt-operation-link-warning'>
                <b>Link check:</b> {unlinked_project} visible order(s) do not have a linked Sales project name yet. Please check Project ID mapping when reviewing these cards.
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

if show_table:
    _section_head("Compact view", "Compact table view", "Use this only when you need a dense Excel-like list before opening an order card.")
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
            "is_archived",
            "last_event",
            "days_since_status_update",
            "days_since_review",
        ],
        empty_message="No Orders found.",
    )

_section_head(
    "Order cards",
    "Operation order cards",
    f"Red buttons show the current recorded status only. White buttons are available actions. Archive view: {archive_view}.",
)
render_board_cards(
    rows,
    entity_type="Operation",
    operator=operator,
    source_page="Order Board",
    empty_message="No Orders found.",
)
