from __future__ import annotations

from html import escape
from textwrap import dedent
import re

import pandas as pd
import streamlit as st

from core.auth import require_login
from core.dictionaries import (
    HEALTH_STATUSES,
    OPERATION_PHASES,
    OPERATION_RESULTS,
    PEOPLE,
    PRIORITIES,
    RECORD_TYPES,
    REQUEST_TYPE_DISPLAY_VALUES,
    SALES_PHASES,
    SALES_RESULTS,
)
from ui.theme import apply_theme, render_page_header


apply_theme()
current_user = require_login()
render_page_header(
    "Field Setup",
    "Read-only reference for the internal field lists, option values and meeting logic used by this project tracker.",
)


def _html(markup: str) -> str:
    """Return compact HTML for Streamlit markdown rendering.

    Streamlit's Markdown parser may close an HTML block when it sees blank
    lines. When subsequent HTML is indented, it can be rendered as literal
    code text such as </div>. Keep each HTML block continuous.
    """
    text = dedent(markup).strip()
    text = re.sub(r"\n\s*\n", "\n", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _safe(value: object) -> str:
    return escape(str(value or "-"))


def _chips(values: list[str]) -> str:
    if not values:
        return "<span class='zf-empty'>No values</span>"
    return "".join(f"<span class='zf-chip'>{_safe(v)}</span>" for v in values)


def _render_css() -> None:
    st.markdown(
        _html(
            """
            <style>
            .block-container { padding-top: 1.05rem !important; }

            .zf-grid-4 {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.85rem;
                margin: 0.65rem 0 1.05rem 0;
            }
            .zf-grid-3 {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.85rem;
                margin: 0.65rem 0 1.05rem 0;
            }
            .zf-grid-2 {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.85rem;
                margin: 0.65rem 0 1.05rem 0;
            }
            .zf-card {
                background: #ffffff;
                border: 1px solid #e8e8eb;
                border-radius: 22px;
                padding: 18px 18px 16px 18px;
                box-shadow: 0 10px 28px rgba(17,17,17,0.045);
                min-height: 118px;
                position: relative;
                overflow: hidden;
            }
            .zf-card:before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 4px;
                background: #c5161d;
            }
            .zf-card-title {
                color: #111111;
                font-size: 1.02rem;
                font-weight: 850;
                letter-spacing: -0.02em;
                margin-bottom: 0.25rem;
            }
            .zf-card-subtitle {
                color: #74777e;
                font-size: 0.84rem;
                line-height: 1.45;
                margin-bottom: 0.65rem;
            }
            .zf-kpi {
                color: #111111;
                font-size: 2.05rem;
                font-weight: 850;
                line-height: 1;
                letter-spacing: -0.045em;
            }
            .zf-kicker {
                color: #c5161d;
                font-size: 0.72rem;
                font-weight: 850;
                text-transform: uppercase;
                letter-spacing: 0.12em;
                margin: 1.2rem 0 0.18rem 0;
            }
            .zf-section-title {
                color: #111111;
                font-size: 1.18rem;
                font-weight: 850;
                letter-spacing: -0.025em;
                margin-bottom: 0.2rem;
            }
            .zf-section-note {
                color: #72767d;
                font-size: 0.86rem;
                line-height: 1.45;
                margin-bottom: 0.55rem;
                max-width: 980px;
            }
            .zf-chip-wrap {
                display: flex;
                flex-wrap: wrap;
                gap: 0.45rem;
                margin-top: 0.45rem;
            }
            .zf-chip {
                display: inline-flex;
                align-items: center;
                min-height: 30px;
                padding: 0.28rem 0.7rem;
                border-radius: 999px;
                background: #f7f7f8;
                border: 1px solid #e9e9ec;
                color: #111111;
                font-size: 0.82rem;
                font-weight: 760;
                margin: 0.14rem 0.18rem 0.14rem 0;
            }
            .zf-empty {
                color: #8b8f96;
                font-size: 0.84rem;
            }
            .zf-rule-card {
                background: #ffffff;
                border: 1px solid #e8e8eb;
                border-radius: 22px;
                padding: 18px;
                box-shadow: 0 10px 28px rgba(17,17,17,0.045);
            }
            .zf-rule-card strong {
                color: #111111;
                font-size: 1rem;
                font-weight: 850;
            }
            .zf-rule-card ul {
                margin: 0.65rem 0 0 1rem;
                padding: 0;
                color: #3e4248;
                font-size: 0.86rem;
                line-height: 1.5;
            }
            .zf-note-panel {
                background: #fff7f7;
                border: 1px solid #ffd1d1;
                border-radius: 20px;
                padding: 14px 16px;
                color: #2d2d2d;
                font-size: 0.88rem;
                line-height: 1.45;
                margin: 0.45rem 0 0.9rem 0;
            }
            .zf-note-panel b { color: #c5161d; }
            .zf-mini-line {
                display: flex;
                justify-content: space-between;
                gap: 1rem;
                border-top: 1px solid #eeeeef;
                padding-top: 0.6rem;
                margin-top: 0.65rem;
                color: #646870;
                font-size: 0.82rem;
            }
            @media (max-width: 1100px) {
                .zf-grid-4 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                .zf-grid-3 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            }
            @media (max-width: 720px) {
                .zf-grid-4, .zf-grid-3, .zf-grid-2 { grid-template-columns: 1fr; }
            }
            </style>
            """
        ),
        unsafe_allow_html=True,
    )


def _section(kicker: str, title: str, note: str) -> None:
    st.markdown(
        _html(
            f"""
            <div class='zf-kicker'>{_safe(kicker)}</div>
            <div class='zf-section-title'>{_safe(title)}</div>
            <div class='zf-section-note'>{_safe(note)}</div>
            """
        ),
        unsafe_allow_html=True,
    )


def _card(title: str, subtitle: str, count: int | str, footer: str) -> str:
    return (
        f"<div class='zf-card'>"
        f"<div class='zf-card-title'>{_safe(title)}</div>"
        f"<div class='zf-card-subtitle'>{_safe(subtitle)}</div>"
        f"<div class='zf-kpi'>{_safe(count)}</div>"
        f"<div class='zf-mini-line'><span>{_safe(footer)}</span><span>Read only</span></div>"
        f"</div>"
    )


def _option_card(title: str, subtitle: str, values: list[str]) -> str:
    return (
        f"<div class='zf-card'>"
        f"<div class='zf-card-title'>{_safe(title)}</div>"
        f"<div class='zf-card-subtitle'>{_safe(subtitle)}</div>"
        f"<div class='zf-chip-wrap'>{_chips(values)}</div>"
        f"</div>"
    )


def _rule_card(title: str, rules: list[str]) -> str:
    items = "".join(f"<li>{_safe(rule)}</li>" for rule in rules)
    return f"<div class='zf-rule-card'><strong>{_safe(title)}</strong><ul>{items}</ul></div>"


_render_css()

st.markdown(
    _html(
        """
        <div class='zf-note-panel'>
            <b>Read-only page.</b> This page explains the internal dropdown values and logic used by the tracker. It is not an app system setting page and it does not change database records.
        </div>
        """
    ),
    unsafe_allow_html=True,
)

_section(
    "Dropdown Lists",
    "Option lists",
    "These are the values currently used by the dropdown fields. The display is for checking and reference only.",
)
option_cards = [
    _option_card("People", "Owner / updater / next-step owner list.", PEOPLE),
    _option_card("Record Type", "High-level type used to separate Sales and Operation work.", RECORD_TYPES),
    _option_card("Sales Phase", "Sales process stage options.", SALES_PHASES),
    _option_card("Operation Phase", "Order and delivery process stage options.", OPERATION_PHASES),
    _option_card("Health Status", "Current risk or attention status.", HEALTH_STATUSES),
    _option_card("Sales Result", "Sales outcome values.", SALES_RESULTS),
    _option_card("Operation Result", "Operation execution outcome values.", OPERATION_RESULTS),
    _option_card("Request / Need Type", "What kind of support or decision is needed.", REQUEST_TYPE_DISPLAY_VALUES),
    _option_card("Priority", "Simple priority values used for sorting and focus.", PRIORITIES),
]
st.markdown(
    _html(f"<div class='zf-grid-3'>{''.join(option_cards)}</div>"),
    unsafe_allow_html=True,
)

_section(
    "Meeting Mode",
    "Meeting logic reference",
    "These rules explain why records appear in Meeting Mode focus groups. The groups may overlap, so the sub-counts do not need to add up to Meeting Pool.",
)
st.markdown(
    _html(
        f"""
        <div class='zf-grid-2'>
            {_rule_card('Meeting Pool', ['Manual: Review This Week is Yes or the item is added to the meeting pool.', 'Auto: item is included when it triggers Need Decision, Blocked / Risk, Due / Follow-up, or Repeated Issue logic.', 'Meeting Pool is the unique total list for the current meeting view and filters.'])}
            {_rule_card('Need Decision', ['Health Status is Need Decision or Need Alignment.', 'Request type is Decision, Approval or Alignment.', 'Need From Meeting / Need Decision From contains content.'])}
            {_rule_card('Blocked / Risk', ['Health Status is Blocked.', 'Blocked At contains content.', 'The item has a clear risk or blocking point that needs meeting attention.'])}
            {_rule_card('Due / Follow-up', ['Next Step contains content.', 'Next Step Owner is selected.', 'Target Date is already overdue.', 'Follow-up Status is not Done.'])}
            {_rule_card('Repeated Issue', ['Repeated Issue is Yes / True.', 'Pattern Flag is selected.', 'Used to highlight recurring or repeated project problems.'])}
            {_rule_card('Follow-up Status', ['Open: default status when a next step is created.', 'In Progress: follow-up is ongoing.', 'Done: follow-up is completed and excluded from Due / Follow-up.', 'Blocked: follow-up itself is blocked.'])}
        </div>
        """
    ),
    unsafe_allow_html=True,
)

_section(
    "Usage Map",
    "Where the fields are used",
    "A simple map showing how key field groups connect to the main pages.",
)
usage_df = pd.DataFrame(
    [
        {"Field Group": "People", "Main Fields": "Current Owner, Next Step Owner, Next Step Support From", "Used In": "Sales Board, Operation Board, Project Details, Meeting Mode"},
        {"Field Group": "Phase", "Main Fields": "Sales Phase, Operation Phase", "Used In": "Boards, Project Details, Dashboard summaries"},
        {"Field Group": "Health Status", "Main Fields": "On Track, Waiting, Blocked, Need Alignment, Need Decision", "Used In": "Boards, Project Details, Meeting Mode focus groups"},
        {"Field Group": "Result Status", "Main Fields": "Sales Result, Operation Result", "Used In": "Boards, Project Details, Dashboard outcomes"},
        {"Field Group": "Meeting Fields", "Main Fields": "Need From Meeting, Meeting Note, Next Step, Target Date", "Used In": "Meeting Mode, Project Details"},
        {"Field Group": "Follow-up", "Main Fields": "Next Step, Owner, Support From, Target Date, Follow-up Status", "Used In": "Meeting Mode, Project Details, export files"},
        {"Field Group": "Priority", "Main Fields": "High, Medium, Low", "Used In": "Project Details, filters and future sorting"},
    ]
)
st.dataframe(usage_df, use_container_width=True, hide_index=True)

with st.expander("Advanced notes for code maintenance", expanded=False):
    st.markdown(
        """
        - This page is intentionally read-only. It should not be used for changing database records during meetings.
        - Dropdown values are loaded from `core/dictionaries.py`.
        - Meeting Mode focus logic is implemented in `pages/5_Meeting_Mode.py` and related export logic is implemented in `services/meeting_service.py`.
        - If new dropdown values are added later, review related filters and meeting logic at the same time.
        """
    )
