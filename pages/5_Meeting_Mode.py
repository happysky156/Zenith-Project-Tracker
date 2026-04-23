from __future__ import annotations

from datetime import date

import streamlit as st

from core.dictionaries import PEOPLE
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
    get_meeting_summary_metrics,
    get_team_view_rows,
    save_meeting_followup,
)
from ui.theme import apply_theme, render_badges, render_page_header


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


apply_theme()
render_page_header("Meeting Mode", "Weekly meeting workspace with Team View, Boss View and merged Sales + Operation focus items.")

acting_user = st.selectbox("Acting User", options=PEOPLE, index=0)
view = st.radio("View", options=["Team View", "Boss View"], horizontal=True)
rows = get_team_view_rows() if view == "Team View" else get_boss_view_rows()
metrics = get_meeting_summary_metrics(rows)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Meeting Pool", metrics["total"])
m2.metric("Need Decision", metrics["need_decision"])
m3.metric("Blocked", metrics["blocked"])
m4.metric("Delayed / Due Soon", metrics["delayed_due"])
m5.metric("Repeated Issue", metrics["pattern"])

left, mid, right = st.columns([2, 2, 2])
with left:
    if st.button("Save Weekly Snapshot", type="primary", use_container_width=True, disabled=not rows):
        created = generate_weekly_snapshot(rows)
        st.success(f"Generated {created} meeting snapshot rows for {view}.")
with mid:
    if st.button("Generate Summary", use_container_width=True, disabled=not rows):
        st.session_state["meeting_summary_output"] = generate_post_meeting_summary(rows, view)
with right:
    if st.button("Hide Summary", use_container_width=True):
        st.session_state.pop("meeting_summary_output", None)

if view == "Boss View":
    st.markdown(
        "<div class='zt-soft-note'><b>Boss View logic:</b> the list is auto-sorted to put decision-needed items, blocked items, delayed / due-soon risks, and repeated issues first.</div>",
        unsafe_allow_html=True,
    )

export_rows = _build_export_rows(view, rows)
summary_output = st.session_state.get("meeting_summary_output")
if summary_output:
    st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='zt-panel-title'>Post-Meeting Summary Output</div>", unsafe_allow_html=True)
    sum_col1, sum_col2 = st.columns(2)
    with sum_col1:
        st.text_area("Boss Summary", value=summary_output.get("boss_summary", ""), height=260)
    with sum_col2:
        st.text_area("Team Summary", value=summary_output.get("team_summary", ""), height=260)
    st.markdown("</div>", unsafe_allow_html=True)

minutes_text = generate_meeting_minutes_text(export_rows, view)
followup_df = build_followup_export_dataframe(export_rows)
export_col1, export_col2 = st.columns(2)
with export_col1:
    st.download_button(
        "Download Minutes (.txt)",
        data=minutes_text,
        file_name=f"meeting_minutes_{view.lower().replace(' ', '_')}.txt",
        mime="text/plain",
        use_container_width=True,
        disabled=not rows,
    )
with export_col2:
    st.download_button(
        "Download Follow-up (.csv)",
        data=followup_df.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"meeting_followup_{view.lower().replace(' ', '_')}.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=followup_df.empty,
    )

if not rows:
    st.info("No items in the meeting pool.")
    st.stop()

for row in rows:
    entity_id = row.get("entity_id")
    title = row.get("display_title") or row.get("project_name") or row.get("linked_project_name") or "-"
    subtitle = (
        f"Type: {row.get('entity_type')} | Owner: {row.get('current_owner') or '-'} | Client Code: {row.get('client_code') or '-'}"
    )

    st.markdown("<div class='zt-card'>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='zt-card-title'>{entity_id} — {title}</div>"
        f"<div class='zt-card-subtitle'>{subtitle}</div>",
        unsafe_allow_html=True,
    )
    render_badges(
        phase=row.get("phase"),
        health=row.get("health_status"),
        result=row.get("result_status"),
        pattern=bool(row.get("pattern_flag")),
    )

    st.markdown(
        f"<div class='zt-soft-note'><b>Why this item is in focus:</b> {row.get('meeting_focus_reason') or '-'} </div>",
        unsafe_allow_html=True,
    )

    detail_cols = st.columns(2)
    with detail_cols[0]:
        st.write(f"**Client Waiting For:** {row.get('client_waiting_for') or '-'}")
        st.write(f"**Current Progress:** {row.get('progress_summary') or '-'}")
        st.write(f"**Main Issue:** {row.get('main_issue') or '-'}")
        st.write(f"**Blocked At:** {row.get('block_point') or '-'}")
    with detail_cols[1]:
        st.write(f"**Possible Reason:** {row.get('likely_reason') or '-'}")
        st.write(f"**Need From Meeting:** {row.get('need_from_meeting') or '-'}")
        st.write(f"**Next Step:** {row.get('next_step_summary') or '-'}")
        st.write(f"**Decision By:** {row.get('need_decision_from') or '-'}")

    st.markdown(
        (
            f"<div class='zt-soft-note'><b>Next Step Owner:</b> {row.get('next_step_owner') or '-'}"
            f" &nbsp; | &nbsp; <b>Review This Week:</b> {'Yes' if row.get('review_this_week') else 'No'}"
            f" &nbsp; | &nbsp; <b>Days Since Review:</b> {row.get('days_since_review') or '-'}"
            f" &nbsp; | &nbsp; <b>Days Since Status:</b> {row.get('days_since_status_update') or '-'}"
            f"</div>"
        ),
        unsafe_allow_html=True,
    )

    followup_open_key = f"meeting_followup_open_{row['entity_type']}_{entity_id}"
    is_followup_open = bool(st.session_state.get(followup_open_key, False))
    toggle_label = "Hide Meeting Follow-up" if is_followup_open else "Open Meeting Follow-up"
    if st.button(toggle_label, key=f"toggle_followup_{row['entity_type']}_{entity_id}", use_container_width=False):
        _toggle_followup(row["entity_type"], entity_id)
        st.rerun()

    if is_followup_open:
        st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
        st.markdown("<div class='zt-panel-title'>Meeting Follow-up</div>", unsafe_allow_html=True)
        with st.form(key=f"meeting_followup_form_{row['entity_type']}_{entity_id}"):
            follow_cols = st.columns([2.2, 1.2, 1.1])
            with follow_cols[0]:
                meeting_note_value = st.text_area(
                    "Meeting Note",
                    value=row.get("meeting_note") or "",
                    key=f"meeting_note_{row['entity_type']}_{entity_id}",
                    height=90,
                    placeholder="Short note taken during the meeting...",
                )
                next_step_value = st.text_area(
                    "Next Step",
                    value=row.get("next_step_summary") or "",
                    key=f"meeting_next_step_{row['entity_type']}_{entity_id}",
                    height=90,
                    placeholder="What should happen next?",
                )
            with follow_cols[1]:
                owner_options = [""] + PEOPLE
                current_owner = row.get("next_step_owner") or ""
                owner_index = owner_options.index(current_owner) if current_owner in owner_options else 0
                next_step_owner_value = st.selectbox(
                    "Next Step Owner",
                    options=owner_options,
                    index=owner_index,
                    key=f"meeting_next_step_owner_{row['entity_type']}_{entity_id}",
                )
            with follow_cols[2]:
                parsed_target = _parse_date(row.get("target_date"))
                target_date_value = st.date_input(
                    "Target Date",
                    value=parsed_target,
                    key=f"meeting_target_date_{row['entity_type']}_{entity_id}",
                    format="YYYY-MM-DD",
                )

            submitted = st.form_submit_button("Save Meeting Follow-up", use_container_width=True, type="primary")

        if submitted:
            result = save_meeting_followup(
                entity_type=row["entity_type"],
                entity_id=entity_id,
                meeting_note=meeting_note_value,
                next_step_summary=next_step_value,
                next_step_owner=next_step_owner_value,
                target_date=target_date_value.isoformat() if target_date_value else None,
                operator=acting_user,
                source_page="Meeting Mode",
            )
            if result.get("updated"):
                _upsert_session_row(view, result.get("row") or get_meeting_record(row["entity_type"], entity_id))
                st.success(f"{entity_id}: meeting follow-up saved")
                st.session_state[followup_open_key] = False
                st.rerun()
            else:
                st.info(result["message"])
        st.markdown("</div>", unsafe_allow_html=True)

    first_row = MEETING_ACTIONS[:3]
    second_row = MEETING_ACTIONS[3:]
    for action_row in (first_row, second_row):
        cols = st.columns(len(action_row))
        for col, action_name in zip(cols, action_row):
            with col:
                if st.button(
                    action_name,
                    key=f"meeting_{row['entity_type']}_{entity_id}_{action_name}",
                    use_container_width=True,
                    type="primary" if action_name in {"Decision Made / Close", "High-Risk Follow-up"} else "secondary",
                ):
                    try:
                        action_result = apply_meeting_action(
                            entity_type=row["entity_type"],
                            entity_id=entity_id,
                            action_name=action_name,
                            operator=acting_user,
                            source_page="Meeting Mode",
                        )
                        _upsert_session_row(view, action_result.get("row") or get_meeting_record(row["entity_type"], entity_id))
                        st.success(f"{entity_id}: {action_name}")
                        st.rerun()
                    except MeetingActionError as exc:
                        st.error(str(exc))
    st.markdown("</div>", unsafe_allow_html=True)
