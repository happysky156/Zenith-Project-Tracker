from __future__ import annotations

from datetime import date
from html import escape
from textwrap import dedent

import streamlit as st

from core.auth import require_login
from core.dictionaries import PEOPLE
from services.detail_service import parse_multi_value
from services.meeting_service import (
    MEETING_ACTIONS,
    MeetingActionError,
    apply_meeting_action,
    build_followup_export_dataframe,
    generate_meeting_minutes_text,
    generate_post_meeting_summary,
    generate_weekly_snapshot,
    get_meeting_record,
    get_boss_view_rows,
    get_team_view_rows,
    save_meeting_followup,
)
from ui.theme import apply_theme, render_badges, render_page_header


def _html(markup: str) -> str:
    return dedent(markup).strip()


def _clean(value: object, empty: str = "Not set") -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"-", "nan", "none", "null"}:
        text = empty
    return escape(text).replace("\n", "<br>")


def _plain(value: object, empty: str = "") -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"-", "nan", "none", "null"}:
        return empty
    return text


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def _toggle_followup(entity_type: str, entity_id: str) -> None:
    key = f"meeting_followup_open_{entity_type}_{entity_id}"
    st.session_state[key] = not bool(st.session_state.get(key))


def _meeting_session_key(view_name: str) -> str:
    return f"meeting_session_rows_{view_name.replace(' ', '_').lower()}"


def _set_meeting_active_filter(name: str) -> None:
    st.session_state["meeting_active_filter"] = name


def _reset_meeting_filters() -> None:
    st.session_state["meeting_type_filter_v2"] = "All"
    st.session_state["meeting_next_step_owner_filter"] = "All"
    st.session_state["meeting_followup_status_filter"] = "All"
    st.session_state["meeting_search_query"] = ""
    st.session_state["meeting_active_filter"] = "Meeting Pool"


def _tooltip_label(label: str, help_text: str) -> None:
    st.markdown(
        f"<div class='zt-compact-field-label' title='{escape(help_text)}'>{escape(label)}</div>",
        unsafe_allow_html=True,
    )


def _upsert_session_row(view_name: str, row: dict) -> None:
    key = _meeting_session_key(view_name)
    stored = list(st.session_state.get(key, []))
    row_key = (row.get("entity_type"), row.get("entity_id"))
    filtered = [r for r in stored if (r.get("entity_type"), r.get("entity_id")) != row_key]
    filtered.append(row)
    st.session_state[key] = filtered


def _build_export_rows(view_name: str, current_rows: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}
    for row in st.session_state.get(_meeting_session_key(view_name), []):
        merged[(row.get("entity_type"), row.get("entity_id"))] = row
    for row in current_rows:
        merged[(row.get("entity_type"), row.get("entity_id"))] = row
    return list(merged.values())


def _has_value(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text) and text.lower() not in {"-", "nan", "none", "null"}


def _is_need_decision(row: dict) -> bool:
    """Decision/alignment items shown by the Need Decision focus card.

    The same predicate is used for both the summary number and the project-list
    filter, so clicking a card can no longer show a different count.
    """
    health = str(row.get("health_status") or "").strip()
    request_type = str(row.get("request_type") or "").strip()
    return (
        health in {"Need Decision", "Need Alignment"}
        or request_type in {"Decision", "Approval", "Alignment"}
        or _has_value(row.get("need_decision_from"))
        or _has_value(row.get("need_from_meeting"))
    )


def _is_blocked(row: dict) -> bool:
    return row.get("health_status") == "Blocked" or _has_value(row.get("block_point"))


def _is_delayed_due(row: dict) -> bool:
    """Due / Follow-up: next step + owner + target date already due."""
    if str(row.get("followup_status") or "").strip().lower() == "done":
        return False
    if not _has_value(row.get("next_step_summary")):
        return False
    if not _has_value(row.get("next_step_owner")):
        return False

    target = _parse_date(row.get("target_date"))
    if not target:
        return False

    result = str(row.get("result_status") or "").strip().lower()
    closed_results = {"won", "lost", "paid closed", "closed", "completed", "cancelled", "canceled", "decision made"}
    if result in closed_results:
        return False

    return target <= date.today()


def _is_repeated(row: dict) -> bool:
    repeated = str(row.get("repeated_issue") or "").strip().lower()
    return bool(row.get("pattern_flag")) or repeated in {"yes", "true", "1", "y"}


def _meeting_metrics(rows: list[dict]) -> dict[str, int]:
    return {
        "total": len(rows),
        "need_decision": sum(1 for r in rows if _is_need_decision(r)),
        "blocked": sum(1 for r in rows if _is_blocked(r)),
        "delayed_due": sum(1 for r in rows if _is_delayed_due(r)),
        "pattern": sum(1 for r in rows if _is_repeated(r)),
        "review": sum(1 for r in rows if bool(r.get("review_this_week"))),
    }


def _normalize_followup_status(row: dict) -> str:
    status = str(row.get("followup_status") or "").strip()
    return status or "Open"


def _apply_owner_status_filters(rows: list[dict], owner_filter: str, status_filter: str) -> list[dict]:
    filtered = rows
    if owner_filter and owner_filter != "All":
        filtered = [r for r in filtered if str(r.get("next_step_owner") or "").strip() == owner_filter]
    if status_filter and status_filter != "All":
        filtered = [r for r in filtered if _normalize_followup_status(r) == status_filter]
    return filtered


def _apply_search_filter(rows: list[dict], query: str) -> list[dict]:
    keyword = (query or "").strip().lower()
    if not keyword:
        return rows
    search_keys = [
        "entity_id",
        "display_id",
        "display_title",
        "project_name",
        "linked_project_name",
        "client_code",
        "order_no",
    ]
    return [
        row
        for row in rows
        if any(keyword in str(row.get(key) or "").lower() for key in search_keys)
    ]


def _apply_meeting_filter(rows: list[dict], active_filter: str) -> list[dict]:
    if active_filter == "Need Decision":
        return [r for r in rows if _is_need_decision(r)]
    if active_filter == "Blocked":
        return [r for r in rows if _is_blocked(r)]
    if active_filter == "Due / Follow-up":
        return [r for r in rows if _is_delayed_due(r)]
    if active_filter == "Repeated Issue":
        return [r for r in rows if _is_repeated(r)]
    return rows


def _summary_specs(metrics: dict[str, int]) -> list[dict[str, object]]:
    overlap_note = " Focus groups may overlap, so these numbers do not need to add up to Meeting Pool."
    return [
        {
            "name": "Meeting Pool",
            "count": metrics["total"],
            "class": "pool",
            "help": "Show all unique items in this week's meeting pool after the current owner/status/search filters.",
        },
        {
            "name": "Need Decision",
            "count": metrics["need_decision"],
            "class": "decision",
            "help": "Show decision, approval or internal-alignment items." + overlap_note,
        },
        {
            "name": "Blocked",
            "count": metrics["blocked"],
            "class": "blocked",
            "help": "Show blocked/risk items or items with a clear blocked-at point." + overlap_note,
        },
        {
            "name": "Due / Follow-up",
            "count": metrics["delayed_due"],
            "class": "due",
            "help": "Show overdue follow-up items with a next step, owner and overdue target date." + overlap_note,
        },
        {
            "name": "Repeated Issue",
            "count": metrics["pattern"],
            "class": "repeat",
            "help": "Show items flagged as repeated or recurring issues." + overlap_note,
        },
    ]


def _section_head(kicker: str, title: str, note: str | None = None) -> None:
    note_html = f"<div class='zt-board-section-note'>{escape(note)}</div>" if note else ""
    st.markdown(
        _html(
            f"""
            <div class='zt-board-section-head zt-meeting-section-head'>
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


def _render_summary_filter_bar(metrics: dict[str, int]) -> None:
    specs = _summary_specs(metrics)
    active_filter = st.session_state.get("meeting_active_filter", "Meeting Pool")
    st.markdown("<span class='zt-meeting-kpi-marker'></span>", unsafe_allow_html=True)
    cols = st.columns(len(specs))
    for col, spec in zip(cols, specs):
        name = str(spec["name"])
        count = str(spec["count"])
        # Streamlit button labels support Markdown; keeping the number and label on
        # separate lines makes the control read more like a KPI card.
        label = f"**{count}**\n\n{name}"
        is_active = active_filter == name
        with col:
            st.button(
                label,
                key=f"meeting_filter_btn_{name}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
                help=str(spec["help"]),
                on_click=_set_meeting_active_filter,
                args=(name,),
            )


def _card_header_html(row: dict) -> str:
    entity_id = row.get("entity_id") or row.get("display_id") or "-"
    title = row.get("display_title") or row.get("project_name") or row.get("linked_project_name") or "-"
    subtitle = (
        f"Type: {row.get('entity_type') or '-'} | Owner: {row.get('current_owner') or '-'} | "
        f"Client Code: {row.get('client_code') or '-'}"
    )
    attention = row.get("health_status") or "Meeting Item"
    return _html(
        f"""
        <div class='zt-meeting-card-head'>
            <div class='zt-meeting-card-topline'>
                <div>
                    <div class='zt-meeting-card-title'><span>{_clean(entity_id, empty='-')}</span> — {_clean(title, empty='-')}</div>
                    <div class='zt-meeting-card-subtitle'>{escape(subtitle)}</div>
                </div>
                <div class='zt-project-focus-pill'>{_clean(attention, empty='Meeting Item')}</div>
            </div>
        </div>
        """
    )


def _focus_reason_tags(row: dict) -> list[tuple[str, str]]:
    """Reason tags only. Keep detailed field content in the main cards below."""
    tags: list[tuple[str, str]] = []

    def add(label: str, class_name: str) -> None:
        if label not in [existing[0] for existing in tags]:
            tags.append((label, class_name))

    if _is_delayed_due(row):
        add("Due / Follow-up", "due")
    if _is_need_decision(row):
        add("Need Decision", "decision")
    if _is_blocked(row):
        add("Blocked / Risk", "blocked")
    if _is_repeated(row):
        add("Repeated Issue", "repeat")
    if bool(row.get("review_this_week")):
        add("Review This Week", "review")

    # Keep a concise fallback tag, but do not repeat Main Issue / Need From Meeting / Blocked At text here.
    if not tags:
        reason = _plain(row.get("meeting_focus_reason"))
        add(reason or "Meeting Review", "review")

    return tags[:5]


def _focus_note_html(row: dict) -> str:
    chips = "".join(
        f"<span class='zt-focus-chip zt-focus-{escape(class_name)}'>{escape(label)}</span>"
        for label, class_name in _focus_reason_tags(row)
    )
    return _html(
        f"""
        <div class='zt-attention-strip zt-meeting-focus-strip'>
            <div class='zt-meeting-focus-title'>Why this item is in focus</div>
            <div class='zt-meeting-focus-chips'>{chips}</div>
        </div>
        """
    )


def _meeting_field_html(label: str, value: object, class_name: str = "") -> str:
    muted = " zt-meeting-field-empty" if not _has_value(value) else ""
    extra = f" {class_name}" if class_name else ""
    return (
        f"<div class='zt-meeting-field{muted}{extra}'>"
        f"<div class='zt-meeting-field-label'>{escape(label)}</div>"
        f"<div class='zt-meeting-field-value'>{_clean(value)}</div>"
        "</div>"
    )


def _main_summary_html(row: dict) -> str:
    target_date = _plain(row.get("target_date"), empty="Not set")
    footer_badges = [
        ("Owner", row.get("next_step_owner")),
        ("Target Date", target_date),
        ("Support From", row.get("next_step_support")),
    ]
    footer_html = "".join(
        f"<span><b>{escape(label)}:</b> {_clean(value)}</span>" for label, value in footer_badges
    )
    return _html(
        f"""
        <div class='zt-meeting-summary-grid'>
            {_meeting_field_html('Main Issue', row.get('main_issue'), 'zt-field-main-issue')}
            {_meeting_field_html('Current Progress', row.get('progress_summary'), 'zt-field-progress')}
            {_meeting_field_html('Blocked At', row.get('block_point'), 'zt-field-blocked')}
            {_meeting_field_html('Need From Meeting', row.get('need_from_meeting'), 'zt-field-need')}
        </div>
        <div class='zt-meeting-next-step-card'>
            <div class='zt-meeting-field-label'>Next Step</div>
            <div class='zt-meeting-field-value'>{_clean(row.get('next_step_summary'))}</div>
            <div class='zt-meeting-next-step-meta'>{footer_html}</div>
        </div>
        """
    )


def _secondary_detail_grid_html(row: dict) -> str:
    fields = [
        ("Client Waiting For", row.get("client_waiting_for")),
        ("Possible Reason", row.get("likely_reason")),
        ("Decision By", row.get("need_decision_from")),
        ("Next Step Support From", row.get("next_step_support")),
        ("Days Since Review", row.get("days_since_review")),
        ("Days Since Status", row.get("days_since_status_update")),
    ]
    html = [_meeting_field_html(label, value) for label, value in fields]
    return "<div class='zt-meeting-field-grid zt-secondary-field-grid'>" + "".join(html) + "</div>"


def _status_strip_html(row: dict) -> str:
    """Status-only strip. Do not repeat Owner / Support From already shown in Next Step."""
    badges = [
        ("Status", row.get("followup_status") or "Open"),
        ("Review This Week", "Yes" if row.get("review_this_week") else "No"),
        ("Reason", row.get("meeting_pool_reason_text")),
        ("Days Since Status", row.get("days_since_status_update")),
    ]
    badge_html = "".join(
        f"<span><b>{escape(label)}:</b> {_clean(value)}</span>" for label, value in badges
    )
    return _html(
        f"""
        <div class='zt-meeting-status-strip'>
            <div class='zt-followup-summary-title'>Follow-up Summary</div>
            <div class='zt-followup-summary-badges'>{badge_html}</div>
        </div>
        """
    )


def _boss_priority_tags_html(row: dict) -> str:
    chips = "".join(
        f"<span class='zt-focus-chip zt-focus-{escape(class_name)}'>{escape(label)}</span>"
        for label, class_name in _focus_reason_tags(row)
    )
    return f"<div class='zt-boss-priority-tags'>{chips}</div>"


def _boss_decision_focus(row: dict) -> str:
    need = _plain(row.get("need_from_meeting"))
    block = _plain(row.get("block_point"))
    issue = _plain(row.get("main_issue"))
    if need:
        return f"Need meeting support / decision: {need}"
    if block:
        return f"Blocked point requires review: {block}"
    if issue:
        return f"Key issue for review: {issue}"
    return _plain(row.get("meeting_focus_reason")) or "Review this item and confirm the next action."


def _boss_summary_html(row: dict) -> str:
    meta_items = [
        ("Owner", row.get("next_step_owner") or row.get("current_owner")),
        ("Target Date", row.get("target_date")),
        ("Status", row.get("followup_status") or "Open"),
    ]
    meta_html = "".join(
        f"<span><b>{escape(label)}:</b> {_clean(value)}</span>" for label, value in meta_items
    )
    return _html(
        f"""
        {_boss_priority_tags_html(row)}
        <div class='zt-boss-focus-card'>
            <div class='zt-meeting-field-label'>Boss Focus</div>
            <div class='zt-boss-focus-value'>{_clean(_boss_decision_focus(row))}</div>
        </div>
        <div class='zt-boss-summary-grid'>
            {_meeting_field_html('Main Issue', row.get('main_issue'), 'zt-field-main-issue')}
            {_meeting_field_html('Need From Meeting', row.get('need_from_meeting'), 'zt-field-need')}
        </div>
        <div class='zt-boss-next-step-card'>
            <div class='zt-meeting-field-label'>Recommended Next Step</div>
            <div class='zt-meeting-field-value'>{_clean(row.get('next_step_summary'))}</div>
            <div class='zt-meeting-next-step-meta'>{meta_html}</div>
        </div>
        """
    )


def _active_filter_html(active_filter: str, visible_count: int, meeting_type: str, owner: str, status: str, query: str) -> str:
    badge_pairs = [
        active_filter,
        f"{visible_count} items",
        f"Type: {meeting_type}",
        f"Owner: {owner}",
        f"Follow-up: {status}",
    ]
    if query.strip():
        badge_pairs.append(f"Search: {query.strip()}")
    badges = "".join(f"<span>{escape(str(item))}</span>" for item in badge_pairs)
    return f"<div class='zt-meeting-active-filter'><b>Showing</b>{badges}</div>"


def _apply_meeting_mode_css() -> None:
    st.markdown(
        _html(
            """
            <style>
            /* Production view: hide Streamlit's default chrome so Meeting Mode feels like an internal system. */
            #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {
                visibility: hidden !important;
                height: 0 !important;
            }

            /* More compact page header for Meeting Mode. */
            .zt-header-grid {
                margin-bottom: 0.65rem !important;
            }
            .zt-page-header {
                min-height: 86px !important;
                padding: 1.0rem 1.15rem !important;
            }
            .zt-page-title {
                font-size: 1.45rem !important;
            }
            .zt-page-subtitle {
                margin-top: 0.32rem !important;
                font-size: 0.88rem !important;
            }
            .zt-header-logo-panel {
                min-height: 86px !important;
            }
            .zt-header-logo-panel img {
                max-height: 74px !important;
            }

            .zt-meeting-top-control-card,
            .zt-meeting-filter-card-wrap,
            .zt-meeting-toolbar-card {
                background: #ffffff;
                border: 1px solid #e8e8eb;
                border-radius: 18px;
                padding: 0.82rem 0.92rem;
                box-shadow: 0 10px 28px rgba(17,17,17,0.035);
                margin-bottom: 0.72rem;
            }
            .zt-meeting-inline-meta {
                display: flex;
                flex-wrap: wrap;
                gap: 0.45rem 0.7rem;
                align-items: center;
                margin-bottom: 0.3rem;
            }
            .zt-meeting-inline-meta span {
                display: inline-flex;
                align-items: center;
                border: 1px solid #eeeeef;
                background: #fafafa;
                border-radius: 999px;
                padding: 0.28rem 0.58rem;
                color: #2c2c2c;
                font-size: 0.78rem;
                font-weight: 740;
            }
            .zt-meeting-inline-meta b {
                color: #c5161d;
                margin-right: 0.25rem;
            }

            div[data-testid="stMarkdown"]:has(.zt-meeting-kpi-marker) + div[data-testid="stHorizontalBlock"] div.stButton > button {
                min-height: 4.75rem !important;
                border-radius: 18px !important;
                border-color: #e8e8eb !important;
                background: #ffffff !important;
                box-shadow: 0 10px 26px rgba(17,17,17,0.035) !important;
            }
            div[data-testid="stMarkdown"]:has(.zt-meeting-kpi-marker) + div[data-testid="stHorizontalBlock"] div.stButton > button[kind="primary"] {
                background: linear-gradient(180deg, #c5161d 0%, #a81118 100%) !important;
                border-color: #c5161d !important;
                color: white !important;
            }
            div[data-testid="stMarkdown"]:has(.zt-meeting-kpi-marker) + div[data-testid="stHorizontalBlock"] div.stButton > button p {
                white-space: pre-line !important;
                font-size: 0.86rem !important;
                line-height: 1.22 !important;
                text-align: center !important;
                font-weight: 820 !important;
            }
            div[data-testid="stMarkdown"]:has(.zt-meeting-kpi-marker) + div[data-testid="stHorizontalBlock"] div.stButton > button p strong {
                font-size: 1.7rem !important;
                line-height: 1.05 !important;
                font-weight: 900 !important;
            }

            .zt-meeting-active-filter {
                margin: 0.8rem 0 0.7rem 0 !important;
                padding: 0.62rem 0.75rem !important;
                border-radius: 16px !important;
                background: #fff7f7 !important;
                border: 1px solid #ffd6d6 !important;
                display: flex !important;
                align-items: center !important;
                flex-wrap: wrap !important;
                gap: 0.38rem !important;
            }
            .zt-meeting-active-filter b {
                color: #c5161d !important;
                font-weight: 900 !important;
                margin-right: 0.25rem !important;
            }
            .zt-meeting-active-filter span {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                border: 1px solid #ffd6d6;
                background: #ffffff;
                color: #2c2c2c;
                font-size: 0.78rem;
                font-weight: 760;
                padding: 0.22rem 0.52rem;
            }

            /* Override previous compact toolbar rule and make labels readable. */
            div[data-testid="stMarkdown"]:has(.zt-meeting-tools-marker) + div[data-testid="stHorizontalBlock"] div.stButton > button,
            div[data-testid="stMarkdown"]:has(.zt-meeting-tools-marker) + div[data-testid="stHorizontalBlock"] div.stDownloadButton > button {
                min-height: 2.45rem !important;
                height: auto !important;
                padding: 0.35rem 0.55rem !important;
                border-radius: 12px !important;
            }
            div[data-testid="stMarkdown"]:has(.zt-meeting-tools-marker) + div[data-testid="stHorizontalBlock"] div.stButton > button p,
            div[data-testid="stMarkdown"]:has(.zt-meeting-tools-marker) + div[data-testid="stHorizontalBlock"] div.stDownloadButton > button p {
                font-size: 0.74rem !important;
                line-height: 1.12 !important;
                font-weight: 820 !important;
                white-space: normal !important;
            }

            .zt-meeting-summary-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.66rem;
                margin-top: 0.72rem;
            }
            .zt-meeting-field {
                min-height: 88px !important;
                box-shadow: 0 8px 20px rgba(17,17,17,0.025);
            }
            .zt-field-main-issue,
            .zt-field-blocked {
                background: #fff5f5 !important;
                border-color: #ffd7d7 !important;
            }
            .zt-field-need {
                background: #fff9ed !important;
                border-color: #ffe5b8 !important;
            }
            .zt-field-progress {
                background: #f4f8ff !important;
                border-color: #dce9ff !important;
            }
            .zt-meeting-next-step-card {
                margin-top: 0.66rem;
                background: #f5fff8;
                border: 1px solid #d7f1df;
                border-radius: 16px;
                padding: 0.72rem 0.82rem;
                box-shadow: 0 8px 20px rgba(17,17,17,0.025);
            }
            .zt-meeting-next-step-meta,
            .zt-followup-summary-badges {
                display: flex;
                flex-wrap: wrap;
                gap: 0.42rem;
                margin-top: 0.55rem;
            }
            .zt-meeting-next-step-meta span,
            .zt-followup-summary-badges span {
                display: inline-flex;
                border-radius: 999px;
                border: 1px solid #e8e8eb;
                background: #ffffff;
                padding: 0.22rem 0.55rem;
                color: #2c2c2c;
                font-size: 0.78rem;
                font-weight: 720;
            }
            .zt-meeting-next-step-meta b,
            .zt-followup-summary-badges b {
                color: #111111;
                margin-right: 0.22rem;
            }
            .zt-secondary-field-grid {
                grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
                margin-top: 0.2rem !important;
            }
            .zt-followup-summary-title {
                font-weight: 900;
                color: #c5161d;
                margin-bottom: 0.1rem;
                font-size: 0.86rem;
            }
            .zt-meeting-status-strip {
                display: block !important;
                margin-top: 0.78rem !important;
            }
            .zt-meeting-focus-strip {
                padding: 0.72rem 0.85rem !important;
            }
            .zt-meeting-focus-title {
                color: #c5161d;
                font-size: 0.84rem;
                font-weight: 900;
                margin-bottom: 0.36rem;
            }
            .zt-meeting-focus-chips,
            .zt-boss-priority-tags {
                display: flex;
                flex-wrap: wrap;
                gap: 0.42rem;
            }
            .zt-focus-chip {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 0.24rem 0.62rem;
                font-size: 0.78rem;
                font-weight: 860;
                border: 1px solid #e8e8eb;
                background: #ffffff;
            }
            .zt-focus-due { color: #975a00; background: #fff7e8; border-color: #ffe0ad; }
            .zt-focus-decision { color: #b45309; background: #fff3e8; border-color: #ffd6b3; }
            .zt-focus-blocked { color: #c5161d; background: #fff2f2; border-color: #ffd1d1; }
            .zt-focus-repeat { color: #5a3a42; background: #f7f2f4; border-color: #ead7dd; }
            .zt-focus-review { color: #2c2c2c; background: #f8f8f8; border-color: #e7e7e7; }

            .zt-boss-priority-tags {
                margin: 0.65rem 0 0.55rem 0;
            }
            .zt-boss-focus-card,
            .zt-boss-next-step-card {
                border-radius: 16px;
                border: 1px solid #ffd6d6;
                background: #fff8f8;
                padding: 0.72rem 0.82rem;
                margin-top: 0.55rem;
                box-shadow: 0 8px 20px rgba(17,17,17,0.025);
            }
            .zt-boss-focus-value {
                color: #111111;
                font-size: 0.98rem;
                line-height: 1.45;
                font-weight: 860;
            }
            .zt-boss-summary-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.66rem;
                margin-top: 0.66rem;
            }
            .zt-boss-next-step-card {
                background: #f5fff8;
                border-color: #d7f1df;
            }
            .zt-boss-action-header {
                margin-top: 0.78rem !important;
            }

            .zt-open-followup-spacer {
                height: 0.25rem;
            }

            .zt-action-header {
                border-top: 1px solid #f0f0f2;
                margin-top: 0.78rem;
                padding-top: 0.68rem;
            }
            .zt-action-header-title {
                font-size: 0.94rem;
                color: #111111;
                font-weight: 900;
                margin-bottom: 0.12rem;
            }
            .zt-action-header-note {
                color: #74777e;
                font-size: 0.80rem;
                margin-bottom: 0.36rem;
            }
            .zt-action-group-title {
                margin: 0.42rem 0 0.18rem 0;
                color: #111111;
                font-size: 0.84rem;
                font-weight: 900;
            }
            .zt-action-group-title span {
                color: #74777e;
                font-weight: 720;
                margin-left: 0.35rem;
                font-size: 0.76rem;
            }

            div[data-testid="stMarkdown"]:has(.zt-action-buttons-marker) + div[data-testid="stHorizontalBlock"] div.stButton > button,
            div[data-testid="stMarkdown"]:has(.zt-action-risk-marker) + div[data-testid="stHorizontalBlock"] div.stButton > button {
                min-height: 2.45rem !important;
                border-radius: 12px !important;
                padding: 0.28rem 0.5rem !important;
            }
            div[data-testid="stMarkdown"]:has(.zt-action-buttons-marker) + div[data-testid="stHorizontalBlock"] div.stButton > button p,
            div[data-testid="stMarkdown"]:has(.zt-action-risk-marker) + div[data-testid="stHorizontalBlock"] div.stButton > button p {
                font-size: 0.82rem !important;
                line-height: 1.12 !important;
                font-weight: 820 !important;
            }
            div[data-testid="stMarkdown"]:has(.zt-action-risk-marker) + div[data-testid="stHorizontalBlock"] > div:nth-child(1) div.stButton > button {
                background: #fff7e8 !important;
                border-color: #f4b35d !important;
                color: #7a3d00 !important;
            }
            div[data-testid="stMarkdown"]:has(.zt-action-risk-marker) + div[data-testid="stHorizontalBlock"] > div:nth-child(2) div.stButton > button {
                background: #fff2f2 !important;
                border-color: #ffb8b8 !important;
                color: #b00020 !important;
            }

            @media (max-width: 900px) {
                .zt-meeting-summary-grid,
                .zt-boss-summary-grid,
                .zt-secondary-field-grid {
                    grid-template-columns: 1fr !important;
                }
            }
            </style>
            """
        ),
        unsafe_allow_html=True,
    )


ACTION_HELP = {
    "Reviewed No Change": "Mark the item as reviewed this week without changing the business status.",
    "Discussed / Follow up": "Mark the item as discussed and keep it for normal follow-up.",
    "Mark Follow-up Done": "Mark the current next-step follow-up as done for this item.",
    "Review Next Meeting": "Keep this item in the meeting pool for the next meeting.",
    "Decision Made / Close": "Record that the meeting decision has been made and remove the active decision request.",
    "High-Risk Follow-up": "Escalate this item as a high-risk decision follow-up.",
    "Remove from Meeting": "Remove this item from the current weekly meeting pool.",
}


def _run_meeting_action(row: dict, entity_id: str, action_name: str, acting_user: str, meeting_view: str) -> None:
    try:
        action_result = apply_meeting_action(
            entity_type=row["entity_type"],
            entity_id=str(entity_id),
            action_name=action_name,
            operator=acting_user,
            source_page="Meeting Mode",
        )
        _upsert_session_row(meeting_view, action_result.get("row") or get_meeting_record(row["entity_type"], str(entity_id)))
        st.success(f"{entity_id}: {action_name}")
        st.rerun()
    except MeetingActionError as exc:
        st.error(str(exc))


def _render_action_button(row: dict, entity_id: str, action_name: str, acting_user: str, meeting_view: str) -> None:
    pending_key = f"confirm_remove_{row['entity_type']}_{entity_id}"
    is_high_impact = action_name in {"Decision Made / Close", "High-Risk Follow-up", "Mark Follow-up Done", "Remove from Meeting"}
    label = f"**{action_name}**" if is_high_impact else action_name

    if action_name == "Remove from Meeting":
        if st.session_state.get(pending_key):
            st.warning("Confirm remove from current meeting?", icon="⚠️")
            confirm_col, cancel_col = st.columns(2)
            with confirm_col:
                if st.button(
                    "**Confirm**",
                    key=f"confirm_{row['entity_type']}_{entity_id}_{action_name}",
                    use_container_width=True,
                    help="Confirm and remove this item from the current meeting pool.",
                ):
                    st.session_state.pop(pending_key, None)
                    _run_meeting_action(row, entity_id, action_name, acting_user, meeting_view)
            with cancel_col:
                if st.button(
                    "Cancel",
                    key=f"cancel_{row['entity_type']}_{entity_id}_{action_name}",
                    use_container_width=True,
                    help="Cancel remove action.",
                ):
                    st.session_state.pop(pending_key, None)
                    st.rerun()
            return

        if st.button(
            label,
            key=f"meeting_{row['entity_type']}_{entity_id}_{action_name}",
            use_container_width=True,
            type="secondary",
            help=ACTION_HELP.get(action_name),
        ):
            st.session_state[pending_key] = True
            st.rerun()
        return

    if st.button(
        label,
        key=f"meeting_{row['entity_type']}_{entity_id}_{action_name}",
        use_container_width=True,
        type="secondary",
        help=ACTION_HELP.get(action_name),
    ):
        _run_meeting_action(row, entity_id, action_name, acting_user, meeting_view)


def _render_meeting_actions(row: dict, entity_id: str, acting_user: str, meeting_view: str, boss_mode: bool = False) -> None:
    if boss_mode:
        st.markdown(
            "<div class='zt-action-header zt-boss-action-header'><div class='zt-action-header-title'>Boss Decision Actions</div>"
            "<div class='zt-action-header-note'>Use these only to record the meeting outcome for this item.</div></div>",
            unsafe_allow_html=True,
        )
        action_groups = [
            ("Decision Actions", "Short list for boss review", ["Discussed / Follow up", "Decision Made / Close", "Review Next Meeting"]),
        ]
    else:
        st.markdown(
            "<div class='zt-action-header'><div class='zt-action-header-title'>Meeting Actions</div>"
            "<div class='zt-action-header-note'>Select the meeting result for this item. High-impact actions will update status and history.</div></div>",
            unsafe_allow_html=True,
        )
        action_groups = [
            ("Primary Actions", "Most common meeting results", ["Discussed / Follow up", "Decision Made / Close", "Review Next Meeting"]),
            ("Secondary Actions", "Review or completion updates", ["Reviewed No Change", "Mark Follow-up Done"]),
            ("Risk / Remove Actions", "Use carefully", ["High-Risk Follow-up", "Remove from Meeting"]),
        ]

    valid_actions = set(MEETING_ACTIONS)
    for group_title, group_note, action_names in action_groups:
        action_names = [a for a in action_names if a in valid_actions]
        if not action_names:
            continue

        risk_group = group_title == "Risk / Remove Actions"
        marker_class = "zt-action-risk-marker" if risk_group else "zt-action-buttons-marker"
        st.markdown(
            f"<div class='zt-action-group-title'>{escape(group_title)} <span>{escape(group_note)}</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown(f"<span class='{marker_class}'></span>", unsafe_allow_html=True)
        cols = st.columns(len(action_names))
        for col, action_name in zip(cols, action_names):
            with col:
                _render_action_button(row, entity_id, action_name, acting_user, meeting_view)




current_user = require_login()
acting_user = current_user["display_name"]
apply_theme()
_apply_meeting_mode_css()
render_page_header(
    "Meeting Mode",
    "Weekly meeting workspace for review, summary, follow-up recording and export.",
)

# -----------------------------------------------------------------------------
# Top controls: current operator + meeting mode, then business filters.
# -----------------------------------------------------------------------------
st.markdown("<div class='zt-meeting-top-control-card'>", unsafe_allow_html=True)
meta_col, view_col = st.columns([1.1, 1.5])
with meta_col:
    st.markdown(
        f"<div class='zt-meeting-inline-meta'><span><b>Update As</b>{escape(acting_user)}</span></div>",
        unsafe_allow_html=True,
    )
with view_col:
    _tooltip_label("Meeting View", "Team Detail shows the full working list. Boss Summary keeps the priority order for decision-focused review.")
    meeting_view = st.radio(
        "Meeting View",
        options=["Team Detail", "Boss Summary"],
        horizontal=True,
        key="meeting_view_mode",
        label_visibility="collapsed",
    )
st.markdown("</div>", unsafe_allow_html=True)

filter_col1, filter_col2, filter_col3, filter_col4, filter_col5 = st.columns([0.9, 1.1, 1.1, 1.4, 0.7])
with filter_col1:
    _tooltip_label("Type", "Choose All, Sales or Operation for this meeting section.")
    meeting_type_filter = st.selectbox(
        "Type",
        options=["All", "Sales", "Operation"],
        index=0,
        key="meeting_type_filter_v2",
        label_visibility="collapsed",
    )

service_view = "Team View" if meeting_view == "Team Detail" else "Boss View"
all_rows_raw = get_team_view_rows() if service_view == "Team View" else get_boss_view_rows()
if meeting_type_filter == "All":
    all_rows = list(all_rows_raw)
else:
    all_rows = [
        r for r in all_rows_raw
        if str(r.get("entity_type") or "").strip().lower() == meeting_type_filter.lower()
    ]

owner_options = [
    "All",
    *sorted({str(r.get("next_step_owner") or "").strip() for r in all_rows if str(r.get("next_step_owner") or "").strip()}),
]
status_options = ["All", "Open", "In Progress", "Done", "Blocked"]
if st.session_state.get("meeting_next_step_owner_filter") not in owner_options:
    st.session_state["meeting_next_step_owner_filter"] = "All"
if st.session_state.get("meeting_followup_status_filter") not in status_options:
    st.session_state["meeting_followup_status_filter"] = "All"

with filter_col2:
    _tooltip_label("Next Step Owner", "Filter the meeting list by the person responsible for the next step.")
    owner_filter = st.selectbox(
        "Next Step Owner",
        options=owner_options,
        key="meeting_next_step_owner_filter",
        label_visibility="collapsed",
    )
with filter_col3:
    _tooltip_label("Follow-up Status", "Filter follow-up items by current completion status.")
    status_filter = st.selectbox(
        "Follow-up Status",
        options=status_options,
        key="meeting_followup_status_filter",
        label_visibility="collapsed",
    )
with filter_col4:
    _tooltip_label("Search", "Search by Project ID, project name, order number or client code.")
    search_query = st.text_input(
        "Search",
        key="meeting_search_query",
        placeholder="Project ID / Project Name / Client Code",
        label_visibility="collapsed",
    )
with filter_col5:
    st.markdown("<div style='height:1.72rem'></div>", unsafe_allow_html=True)
    st.button("Reset", use_container_width=True, on_click=_reset_meeting_filters, help="Reset Meeting Mode filters.")

base_rows = _apply_owner_status_filters(all_rows, owner_filter, status_filter)
base_rows = _apply_search_filter(base_rows, search_query)
metrics = _meeting_metrics(base_rows)

if "meeting_active_filter" not in st.session_state:
    st.session_state["meeting_active_filter"] = "Meeting Pool"

_render_summary_filter_bar(metrics)

active_filter = st.session_state.get("meeting_active_filter", "Meeting Pool")
display_rows = _apply_meeting_filter(base_rows, active_filter)
export_rows = _build_export_rows(meeting_view, display_rows)
minutes_text = generate_meeting_minutes_text(export_rows, meeting_view)
followup_df = build_followup_export_dataframe(export_rows)

st.markdown(
    _active_filter_html(active_filter, len(display_rows), meeting_type_filter, owner_filter, status_filter, search_query),
    unsafe_allow_html=True,
)

# Keep the meeting workspace clean after saving follow-up updates.
# Follow-up save actions auto-close the editor without showing a large success banner.
st.session_state.pop("meeting_flash_message", None)

st.markdown("<span class='zt-meeting-tools-marker'></span>", unsafe_allow_html=True)
tool_cols = st.columns(5)
with tool_cols[0]:
    if st.button("Save Weekly Snapshot", use_container_width=True, disabled=not all_rows, help="Save a weekly snapshot for the current meeting view."):
        created = generate_weekly_snapshot(all_rows)
        st.success(f"Generated {created} meeting snapshot rows for {meeting_view}.")
with tool_cols[1]:
    if st.button("Generate Summary", use_container_width=True, disabled=not display_rows, help="Generate a post-meeting summary from the currently visible items."):
        st.session_state["meeting_summary_output"] = generate_post_meeting_summary(display_rows, meeting_view)
with tool_cols[2]:
    if st.button("Hide Summary", use_container_width=True, help="Hide the generated summary panel."):
        st.session_state.pop("meeting_summary_output", None)
with tool_cols[3]:
    st.download_button(
        "Download Minutes (.txt)",
        data=minutes_text,
        file_name=f"meeting_minutes_{meeting_view.lower().replace(' ', '_')}.txt",
        mime="text/plain",
        use_container_width=True,
        disabled=not display_rows,
        help="Download meeting minutes for the currently visible items.",
    )
with tool_cols[4]:
    st.download_button(
        "Download Follow-up (.csv)",
        data=followup_df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"meeting_followup_{meeting_view.lower().replace(' ', '_')}.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=followup_df.empty,
        help="Download the follow-up list as CSV for the currently visible items.",
    )

summary_output = st.session_state.get("meeting_summary_output")
if summary_output:
    with st.container(border=True):
        st.markdown("<div class='zt-panel-title'>Post-Meeting Summary Output</div>", unsafe_allow_html=True)
        sum_col1, sum_col2 = st.columns(2)
        with sum_col1:
            st.text_area("Boss Summary", value=summary_output.get("boss_summary", ""), height=220)
        with sum_col2:
            st.text_area("Team Summary", value=summary_output.get("team_summary", ""), height=220)

if not all_rows:
    st.info("No items in the meeting pool.")
    st.stop()

if not display_rows:
    st.info(f"No items found for: {active_filter}.")
    st.stop()

_section_head("Meeting list", f"Project meeting cards ({len(display_rows)} items)")

for row in display_rows:
    entity_id = row.get("entity_id") or row.get("display_id")
    if not entity_id:
        continue
    entity_id = str(entity_id)

    with st.container(border=True):
        st.markdown(_card_header_html(row), unsafe_allow_html=True)
        render_badges(
            phase=row.get("phase"),
            health=row.get("health_status"),
            result=row.get("result_status"),
            pattern=bool(row.get("pattern_flag")),
        )

        if meeting_view == "Boss Summary":
            st.markdown(_boss_summary_html(row), unsafe_allow_html=True)
            _render_meeting_actions(row, entity_id, acting_user, meeting_view, boss_mode=True)
            continue

        st.markdown(_focus_note_html(row), unsafe_allow_html=True)
        st.markdown(_main_summary_html(row), unsafe_allow_html=True)
        st.markdown(_status_strip_html(row), unsafe_allow_html=True)

        followup_open_key = f"meeting_followup_open_{row['entity_type']}_{entity_id}"
        is_followup_open = bool(st.session_state.get(followup_open_key, False))
        toggle_label = "Hide Meeting Follow-up" if is_followup_open else "Open Meeting Follow-up"

        detail_col, followup_col = st.columns([4.4, 1.25])
        with detail_col:
            with st.expander("More Details / Secondary Info", expanded=False):
                st.markdown(_secondary_detail_grid_html(row), unsafe_allow_html=True)
        with followup_col:
            st.markdown("<div class='zt-open-followup-spacer'></div>", unsafe_allow_html=True)
            if st.button(
                toggle_label,
                key=f"toggle_followup_{row['entity_type']}_{entity_id}",
                use_container_width=True,
                help="Open or hide the meeting follow-up editor for this item.",
            ):
                _toggle_followup(row["entity_type"], entity_id)
                st.rerun()

        if is_followup_open:
            with st.container(border=True):
                st.markdown("<div class='zt-panel-title'>Meeting Follow-up</div>", unsafe_allow_html=True)
                with st.form(key=f"meeting_followup_form_{row['entity_type']}_{entity_id}"):
                    note_cols = st.columns(2)
                    with note_cols[0]:
                        meeting_note_value = st.text_area(
                            "Meeting Note",
                            value=row.get("meeting_note") or "",
                            key=f"meeting_note_{row['entity_type']}_{entity_id}",
                            height=90,
                            placeholder="Short note taken during the meeting...",
                        )
                    with note_cols[1]:
                        next_step_value = st.text_area(
                            "Next Step",
                            value=row.get("next_step_summary") or "",
                            key=f"meeting_next_step_{row['entity_type']}_{entity_id}",
                            height=90,
                            placeholder="What should happen next?",
                        )

                    owner_date_cols = st.columns([1.0, 1.2, 1.0, 1.05])
                    with owner_date_cols[0]:
                        owner_options_form = [""] + PEOPLE
                        current_owner = row.get("next_step_owner") or ""
                        owner_index = owner_options_form.index(current_owner) if current_owner in owner_options_form else 0
                        next_step_owner_value = st.selectbox(
                            "Next Step Owner",
                            options=owner_options_form,
                            index=owner_index,
                            key=f"meeting_next_step_owner_{row['entity_type']}_{entity_id}",
                        )
                    with owner_date_cols[1]:
                        next_step_support_value = st.multiselect(
                            "Next Step Support From",
                            options=PEOPLE,
                            default=parse_multi_value(row.get("next_step_support")),
                            key=f"meeting_next_step_support_{row['entity_type']}_{entity_id}",
                        )
                    with owner_date_cols[2]:
                        parsed_target = _parse_date(row.get("target_date"))
                        target_date_value = st.date_input(
                            "Target Date",
                            value=parsed_target,
                            key=f"meeting_target_date_{row['entity_type']}_{entity_id}",
                            format="YYYY-MM-DD",
                        )
                    with owner_date_cols[3]:
                        st.markdown("<div class='zt-followup-save-spacer'></div>", unsafe_allow_html=True)
                        submitted = st.form_submit_button("**Save Follow-up**", use_container_width=True, type="secondary")

                if submitted:
                    result = save_meeting_followup(
                        entity_type=row["entity_type"],
                        entity_id=entity_id,
                        meeting_note=meeting_note_value,
                        next_step_summary=next_step_value,
                        next_step_owner=next_step_owner_value,
                        next_step_support=next_step_support_value,
                        target_date=target_date_value.isoformat() if target_date_value else None,
                        operator=acting_user,
                        source_page="Meeting Mode",
                    )
                    if result.get("updated"):
                        _upsert_session_row(meeting_view, result.get("row") or get_meeting_record(row["entity_type"], entity_id))
                    st.session_state[followup_open_key] = False
                    st.rerun()

        _render_meeting_actions(row, entity_id, acting_user, meeting_view, boss_mode=False)
