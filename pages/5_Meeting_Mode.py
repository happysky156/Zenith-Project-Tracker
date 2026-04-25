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


def _clean(value: object) -> str:
    text = str(value or "-").strip() or "-"
    return escape(text).replace("\n", "<br>")


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
            "help": "Show all unique items in this week's meeting pool after the current owner/status filters.",
        },
        {
            "name": "Need Decision",
            "count": metrics["need_decision"],
            "help": "Show decision, approval or internal-alignment items." + overlap_note,
        },
        {
            "name": "Blocked",
            "count": metrics["blocked"],
            "help": "Show blocked/risk items or items with a clear blocked-at point." + overlap_note,
        },
        {
            "name": "Due / Follow-up",
            "count": metrics["delayed_due"],
            "help": "Show overdue follow-up items with a next step, owner and overdue target date." + overlap_note,
        },
        {
            "name": "Repeated Issue",
            "count": metrics["pattern"],
            "help": "Show items flagged as repeated or recurring issues." + overlap_note,
        },
    ]


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


def _render_summary_filter_bar(metrics: dict[str, int]) -> None:
    specs = _summary_specs(metrics)
    active_filter = st.session_state.get("meeting_active_filter", "Meeting Pool")
    cols = st.columns(len(specs))
    for col, spec in zip(cols, specs):
        name = str(spec["name"])
        count = str(spec["count"])
        label = f"**{count} {name}**"
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
                <div>                    <div class='zt-meeting-card-title'><span>{_clean(entity_id)}</span> — {_clean(title)}</div>
                    <div class='zt-meeting-card-subtitle'>{escape(subtitle)}</div>
                </div>
                <div class='zt-project-focus-pill'>{_clean(attention)}</div>
            </div>
        </div>
        """
    )


def _focus_note_html(row: dict) -> str:
    return _html(
        f"""
        <div class='zt-attention-strip zt-meeting-focus-strip'>
            <b>Why this item is in focus:</b> {_clean(row.get('meeting_focus_reason'))}
        </div>
        """
    )


def _detail_grid_html(row: dict) -> str:
    fields = [
        ("Client Waiting For", row.get("client_waiting_for")),
        ("Possible Reason", row.get("likely_reason")),
        ("Current Progress", row.get("progress_summary")),
        ("Need From Meeting", row.get("need_from_meeting")),
        ("Main Issue", row.get("main_issue")),
        ("Next Step", row.get("next_step_summary")),
        ("Blocked At", row.get("block_point")),
        ("Decision By", row.get("need_decision_from")),
    ]
    html = []
    for label, value in fields:
        muted = " zt-meeting-field-empty" if not str(value or "").strip() else ""
        html.append(
            f"<div class='zt-meeting-field{muted}'>"
            f"<div class='zt-meeting-field-label'>{escape(label)}</div>"
            f"<div class='zt-meeting-field-value'>{_clean(value)}</div>"
            "</div>"
        )
    return "<div class='zt-meeting-field-grid'>" + "".join(html) + "</div>"


def _status_strip_html(row: dict) -> str:
    return _html(
        f"""
        <div class='zt-meeting-status-strip'>
            <span><b>Next Step Owner:</b> {_clean(row.get('next_step_owner'))}</span>
            <span><b>Next Step Support From:</b> {_clean(row.get('next_step_support'))}</span>
            <span><b>Follow-up Status:</b> {_clean(row.get('followup_status') or 'Open')}</span>
            <span><b>Meeting Reason:</b> {_clean(row.get('meeting_pool_reason_text'))}</span>
            <span><b>Review This Week:</b> {'Yes' if row.get('review_this_week') else 'No'}</span>
            <span><b>Days Since Review:</b> {_clean(row.get('days_since_review'))}</span>
            <span><b>Days Since Status:</b> {_clean(row.get('days_since_status_update'))}</span>
        </div>
        """
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


current_user = require_login()
acting_user = current_user["display_name"]
apply_theme()
render_page_header(
    "Meeting Mode",
    "Weekly meeting workspace for team review, boss summary, follow-up recording and post-meeting export.",
)

control_col1, control_col2, control_col3, control_col4, control_col5 = st.columns([0.95, 1.65, 0.9, 1.1, 1.1])
with control_col1:
    _tooltip_label("Update As", "Current logged-in user. Updates are recorded under this name automatically.")
    st.text_input("Update As", value=acting_user, disabled=True, label_visibility="collapsed")
with control_col2:
    _tooltip_label("Meeting View", "Team Detail shows the full working list. Boss Summary keeps the priority order for decision-focused review.")
    meeting_view = st.radio(
        "Meeting View",
        options=["Team Detail", "Boss Summary"],
        horizontal=True,
        key="meeting_view_mode",
        label_visibility="collapsed",
    )
with control_col3:
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
with control_col4:
    _tooltip_label("Next Step Owner", "Filter the meeting list by the person responsible for the next step.")
    owner_filter = st.selectbox(
        "Next Step Owner",
        options=owner_options,
        key="meeting_next_step_owner_filter",
        label_visibility="collapsed",
    )
with control_col5:
    _tooltip_label("Follow-up Status", "Filter follow-up items by current completion status.")
    status_filter = st.selectbox(
        "Follow-up Status",
        options=status_options,
        key="meeting_followup_status_filter",
        label_visibility="collapsed",
    )

base_rows = _apply_owner_status_filters(all_rows, owner_filter, status_filter)
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
    f"<div class='zt-meeting-active-filter'><b>Showing:</b> {_clean(active_filter)} &nbsp; | &nbsp; "
    f"<b>{len(display_rows)}</b> visible item(s)"
    f" &nbsp; | &nbsp; <b>Type:</b> {_clean(meeting_type_filter)}"
    f" &nbsp; | &nbsp; <b>Owner:</b> {_clean(owner_filter)}"
    f" &nbsp; | &nbsp; <b>Follow-up:</b> {_clean(status_filter)}</div>",
    unsafe_allow_html=True,
)

# Keep the meeting workspace clean after saving follow-up updates.
# Follow-up save actions auto-close the editor without showing a large success banner.
st.session_state.pop("meeting_flash_message", None)

st.markdown("<span class='zt-meeting-tools-marker'></span>", unsafe_allow_html=True)
tool_cols = st.columns(5)
with tool_cols[0]:
    if st.button("Save", use_container_width=True, disabled=not all_rows, help="Save a weekly snapshot for the current meeting view."):
        created = generate_weekly_snapshot(all_rows)
        st.success(f"Generated {created} meeting snapshot rows for {meeting_view}.")
with tool_cols[1]:
    if st.button("Summary", use_container_width=True, disabled=not display_rows, help="Generate a post-meeting summary from the currently visible items."):
        st.session_state["meeting_summary_output"] = generate_post_meeting_summary(display_rows, meeting_view)
with tool_cols[2]:
    if st.button("Hide", use_container_width=True, help="Hide the generated summary panel."):
        st.session_state.pop("meeting_summary_output", None)
with tool_cols[3]:
    st.download_button(
        "Minutes",
        data=minutes_text,
        file_name=f"meeting_minutes_{meeting_view.lower().replace(' ', '_')}.txt",
        mime="text/plain",
        use_container_width=True,
        disabled=not display_rows,
        help="Download meeting minutes for the currently visible items.",
    )
with tool_cols[4]:
    st.download_button(
        "Follow-up",
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

_section_head("Meeting list", "Project meeting cards")

for row in display_rows:
    entity_id = row.get("entity_id") or row.get("display_id")
    if not entity_id:
        continue

    with st.container(border=True):
        st.markdown(_card_header_html(row), unsafe_allow_html=True)
        render_badges(
            phase=row.get("phase"),
            health=row.get("health_status"),
            result=row.get("result_status"),
            pattern=bool(row.get("pattern_flag")),
        )
        st.markdown(_focus_note_html(row), unsafe_allow_html=True)
        st.markdown(_detail_grid_html(row), unsafe_allow_html=True)
        st.markdown(_status_strip_html(row), unsafe_allow_html=True)

        followup_open_key = f"meeting_followup_open_{row['entity_type']}_{entity_id}"
        is_followup_open = bool(st.session_state.get(followup_open_key, False))
        toggle_label = "Hide Meeting Follow-up" if is_followup_open else "Open Meeting Follow-up"
        if st.button(
            toggle_label,
            key=f"toggle_followup_{row['entity_type']}_{entity_id}",
            use_container_width=False,
            help="Open or hide the meeting follow-up editor for this item.",
        ):
            _toggle_followup(row["entity_type"], str(entity_id))
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
                        owner_options = [""] + PEOPLE
                        current_owner = row.get("next_step_owner") or ""
                        owner_index = owner_options.index(current_owner) if current_owner in owner_options else 0
                        next_step_owner_value = st.selectbox(
                            "Next Step Owner",
                            options=owner_options,
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
                        submitted = st.form_submit_button("**Save**", use_container_width=True, type="secondary")

                if submitted:
                    result = save_meeting_followup(
                        entity_type=row["entity_type"],
                        entity_id=str(entity_id),
                        meeting_note=meeting_note_value,
                        next_step_summary=next_step_value,
                        next_step_owner=next_step_owner_value,
                        next_step_support=next_step_support_value,
                        target_date=target_date_value.isoformat() if target_date_value else None,
                        operator=acting_user,
                        source_page="Meeting Mode",
                    )
                    if result.get("updated"):
                        _upsert_session_row(meeting_view, result.get("row") or get_meeting_record(row["entity_type"], str(entity_id)))
                        pass
                    else:
                        pass
                    st.session_state[followup_open_key] = False
                    st.rerun()

        st.markdown(
            "<div class='zt-action-header'><div class='zt-action-header-title'>Meeting actions</div>"
            "<div class='zt-action-header-note'>These buttons keep the existing update logic. Bold buttons are high-impact actions.</div></div>",
            unsafe_allow_html=True,
        )
        first_row = MEETING_ACTIONS[:3]
        second_row = MEETING_ACTIONS[3:]
        for action_row in (first_row, second_row):
            cols = st.columns(len(action_row))
            for col, action_name in zip(cols, action_row):
                with col:
                    is_high_impact = action_name in {"Decision Made / Close", "High-Risk Follow-up", "Mark Follow-up Done"}
                    label = f"**{action_name}**" if is_high_impact else action_name
                    if st.button(
                        label,
                        key=f"meeting_{row['entity_type']}_{entity_id}_{action_name}",
                        use_container_width=True,
                        type="secondary",
                        help=ACTION_HELP.get(action_name),
                    ):
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
