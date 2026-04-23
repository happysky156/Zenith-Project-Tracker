from __future__ import annotations

from datetime import date

import streamlit as st

from core.dictionaries import (
    HEALTH_STATUSES,
    OPERATION_PHASES,
    OPERATION_RESULTS,
    PEOPLE,
    PRIORITIES,
    REQUEST_TYPES,
    SALES_PHASES,
    SALES_RESULTS,
)
from services.detail_service import (
    parse_multi_value,
    update_detail_fields,
    update_meeting_fields,
    update_request_layer_fields,
)
from services.project_service import get_record_detail, get_record_snapshots, get_record_timeline, list_detail_ids
from ui.project_table import render_project_table
from ui.theme import apply_theme, render_badges, render_page_header



def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


apply_theme()
render_page_header(
    "Project Detail",
    "Single detail page for both Sales projects and Operation orders. Board jumps still open this page directly.",
)

selected_type = st.session_state.get("selected_detail_type", "Sales")
selected_type = st.radio("Detail Type", options=["Sales", "Operation"], index=0 if selected_type == "Sales" else 1, horizontal=True)
st.session_state["selected_detail_type"] = selected_type

record_ids = list_detail_ids(selected_type)
if not record_ids:
    st.info(f"No {selected_type} records yet. Import first.")
    st.stop()

preselected = st.session_state.get("selected_detail_id")
if preselected not in record_ids:
    preselected = record_ids[0]
selected_index = record_ids.index(preselected)

header_col1, header_col2 = st.columns([2, 1])
with header_col1:
    select_label = "Select Project ID" if selected_type == "Sales" else "Select Order No"
    selected_record_id = st.selectbox(select_label, options=record_ids, index=selected_index)
    st.session_state["selected_detail_id"] = selected_record_id
with header_col2:
    acting_user = st.selectbox("Acting User", options=PEOPLE, index=PEOPLE.index("Harley"), key="detail_operator")

detail = get_record_detail(selected_type, selected_record_id)
if not detail:
    st.warning("Record not found.")
    st.stop()

header_title = detail.get("project_name") if selected_type == "Sales" else detail.get("linked_project_name") or detail.get("project_id") or "(Unlinked)"
header_subtitle = (
    f"Client Code: {detail.get('client_code') or '-'} | Linked Orders: {detail.get('linked_order_count') or 0} | Priority: {detail.get('priority') or '-'}"
    if selected_type == "Sales"
    else f"Project ID: {detail.get('project_id') or '-'} | Linked Project: {detail.get('linked_project_name') or '-'}"
)

st.markdown("<div class='zt-card'>", unsafe_allow_html=True)
st.markdown(
    f"<div class='zt-card-title'>{selected_record_id} — {header_title}</div>"
    f"<div class='zt-card-subtitle'>{header_subtitle}</div>",
    unsafe_allow_html=True,
)
render_badges(detail.get("phase"), detail.get("health_status"), detail.get("result_status"), bool(detail.get("pattern_flag")))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Current Owner", detail.get("current_owner") or "-")
c2.metric("Next Step Owner", detail.get("next_step_owner") or "-")
c3.metric("Last Event", detail.get("last_event") or "-")
c4.metric("Target Date", detail.get("target_date") or "-")

left, right = st.columns(2)
with left:
    st.write(f"**Client Waiting For:** {detail.get('client_waiting_for') or '-'}")
    st.write(f"**Main Issue:** {detail.get('main_issue') or '-'}")
    st.write(f"**Block Point:** {detail.get('block_point') or '-'}")
    st.write(f"**Progress Summary:** {detail.get('progress_summary') or '-'}")
with right:
    st.write(f"**Likely Reason:** {detail.get('likely_reason') or '-'}")
    st.write(f"**Need From Meeting:** {detail.get('need_from_meeting') or '-'}")
    st.write(f"**Next Step:** {detail.get('next_step_summary') or '-'}")
    st.write(f"**Meeting Quick Note:** {detail.get('meeting_note') or '-'}")
    st.write(f"**Request Type:** {detail.get('request_type') or '-'}")
    st.write(f"**Request Note:** {detail.get('request_note') or '-'}")
    st.write(f"**Need Decision From:** {detail.get('need_decision_from') or '-'}")
    st.write(f"**Need Alignment With:** {detail.get('need_alignment_with') or '-'}")

st.markdown("</div>", unsafe_allow_html=True)

overview_tab, detail_tab, request_tab, meeting_tab, timeline_tab = st.tabs(
    [
        "Overview",
        "Edit Detail",
        "Edit Request Layer",
        "Edit Meeting Fields",
        "Timeline & Snapshots",
    ]
)

with overview_tab:
    if selected_type == "Sales":
        st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
        st.markdown("<div class='zt-panel-title'>Linked orders from Operation</div>", unsafe_allow_html=True)
        render_project_table(
            detail.get("linked_orders_rows") or [],
            ["order_no", "project_id", "client_code", "phase", "health_status", "result_status", "last_event", "target_date", "review_this_week"],
            empty_message="No linked orders yet.",
        )
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='zt-panel-title'>Current record JSON</div>", unsafe_allow_html=True)
    st.json(detail)
    st.markdown("</div>", unsafe_allow_html=True)

with detail_tab:
    st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='zt-panel-title'>Editable detail</div>", unsafe_allow_html=True)
    with st.form(f"detail_edit_form_{selected_type}_{selected_record_id}"):
        col1, col2 = st.columns(2)
        with col1:
            if selected_type == "Sales":
                project_name = st.text_input("Project Name", value=detail.get("project_name") or "")
                client_code = st.text_input("Client Code", value=detail.get("client_code") or "")
                category = st.text_input("Category", value=detail.get("category") or "")
                priority = st.selectbox("Priority", options=[""] + PRIORITIES, index=([""] + PRIORITIES).index(detail.get("priority") or ""))
                reference_link = st.text_input("Reference Link", value=detail.get("reference_link") or "")
            else:
                st.text_input("Order No", value=detail.get("order_no") or selected_record_id, disabled=True)
                project_id = st.text_input("Project ID", value=detail.get("project_id") or "")
                client_code = st.text_input("Client Code", value=detail.get("client_code") or "")
                reference_link = st.text_input("Reference Link", value=detail.get("reference_link") or "")

            current_owner = st.selectbox("Current Owner", options=[""] + PEOPLE, index=([""] + PEOPLE).index(detail.get("current_owner") or ""))
            support_from = st.multiselect("Support From", options=PEOPLE, default=parse_multi_value(detail.get("support_from")))
            next_step_owner = st.selectbox("Next Step Owner", options=[""] + PEOPLE, index=([""] + PEOPLE).index(detail.get("next_step_owner") or ""))
            next_step_support = st.multiselect("Next Step Support", options=PEOPLE, default=parse_multi_value(detail.get("next_step_support")))

        with col2:
            phase_options = SALES_PHASES if selected_type == "Sales" else OPERATION_PHASES
            result_options = SALES_RESULTS if selected_type == "Sales" else OPERATION_RESULTS
            phase = st.selectbox("Phase", options=phase_options, index=phase_options.index(detail.get("phase") or phase_options[0]))
            health_status = st.selectbox("Health Status", options=HEALTH_STATUSES, index=HEALTH_STATUSES.index(detail.get("health_status") or HEALTH_STATUSES[0]))
            result_status = st.selectbox("Result Status", options=result_options, index=result_options.index(detail.get("result_status") or result_options[0]))
            target_date = st.date_input("Target Date", value=_parse_date(detail.get("target_date")))
            doc_round = st.number_input("Doc Round", min_value=0, step=1, value=int(detail.get("doc_round") or 0))
            test_round = st.number_input("Test Round", min_value=0, step=1, value=int(detail.get("test_round") or 0))
            if selected_type == "Sales":
                quote_round = st.number_input("Quote Round", min_value=0, step=1, value=int(detail.get("quote_round") or 0))
                sample_round = st.number_input("Sample Round", min_value=0, step=1, value=int(detail.get("sample_round") or 0))

        submitted = st.form_submit_button("Save Detail", type="primary")
        if submitted:
            updates = {
                "client_code": client_code.strip(),
                "reference_link": reference_link.strip(),
                "current_owner": current_owner or None,
                "support_from": support_from,
                "next_step_owner": next_step_owner or None,
                "next_step_support": next_step_support,
                "phase": phase,
                "health_status": health_status,
                "result_status": result_status,
                "target_date": target_date.isoformat() if target_date else None,
                "doc_round": doc_round,
                "test_round": test_round,
            }
            if selected_type == "Sales":
                updates.update({
                    "project_name": project_name.strip(),
                    "category": category.strip(),
                    "priority": priority or None,
                    "quote_round": quote_round,
                    "sample_round": sample_round,
                })
            else:
                updates.update({"project_id": project_id.strip()})
            result = update_detail_fields(selected_type, selected_record_id, updates, operator=acting_user)
            if result.get("updated"):
                st.success(result["message"])
                st.rerun()
            else:
                st.info(result["message"])
    st.markdown("</div>", unsafe_allow_html=True)

with request_tab:
    st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='zt-panel-title'>Request layer</div>", unsafe_allow_html=True)
    with st.form(f"request_edit_form_{selected_type}_{selected_record_id}"):
        col1, col2 = st.columns(2)
        with col1:
            request_type = st.selectbox("Request Type", options=REQUEST_TYPES, index=REQUEST_TYPES.index(detail.get("request_type") or "None"))
            request_note = st.text_area("Request Note", value=detail.get("request_note") or "", height=90)
            need_decision_from = st.selectbox("Need Decision From", options=[""] + PEOPLE, index=([""] + PEOPLE).index(detail.get("need_decision_from") or ""))
        with col2:
            need_alignment_with = st.multiselect("Need Alignment With", options=PEOPLE, default=parse_multi_value(detail.get("need_alignment_with")))
            waiting_for_person = st.multiselect("Waiting For Person", options=PEOPLE, default=parse_multi_value(detail.get("waiting_for_person")))
            pattern_flag = st.checkbox("Pattern Flag", value=bool(detail.get("pattern_flag")))
            pattern_note = st.text_area("Pattern Note", value=detail.get("pattern_note") or "", height=90)

        submitted = st.form_submit_button("Save Request Layer", type="primary")
        if submitted:
            result = update_request_layer_fields(
                selected_type,
                selected_record_id,
                {
                    "request_type": None if request_type == "None" else request_type,
                    "request_note": request_note.strip(),
                    "need_decision_from": need_decision_from or None,
                    "need_alignment_with": need_alignment_with,
                    "waiting_for_person": waiting_for_person,
                    "pattern_flag": pattern_flag,
                    "pattern_note": pattern_note.strip(),
                },
                operator=acting_user,
            )
            if result.get("updated"):
                st.success(result["message"])
                st.rerun()
            else:
                st.info(result["message"])
    st.markdown("</div>", unsafe_allow_html=True)

with meeting_tab:
    st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='zt-panel-title'>Meeting fields</div>", unsafe_allow_html=True)
    with st.form(f"meeting_edit_form_{selected_type}_{selected_record_id}"):
        client_waiting_for = st.text_input("Client Waiting For", value=detail.get("client_waiting_for") or "")
        progress_summary = st.text_area("Progress Summary", value=detail.get("progress_summary") or "", height=100)
        main_issue = st.text_area("Main Issue", value=detail.get("main_issue") or "", height=90)
        block_point = st.text_area("Block Point", value=detail.get("block_point") or "", height=90)
        waiting_for_text = st.text_input("Waiting For Text", value=detail.get("waiting_for_text") or "")
        likely_reason = st.text_input("Likely Reason", value=detail.get("likely_reason") or "")
        need_from_meeting = st.text_input("Need From Meeting", value=detail.get("need_from_meeting") or "")
        next_step_summary = st.text_area("Next Step Summary", value=detail.get("next_step_summary") or "", height=100)
        meeting_note = st.text_area("Meeting Quick Note", value=detail.get("meeting_note") or "", height=80, help="Short note you may want to capture during or right after the meeting.")
        sub1, sub2 = st.columns(2)
        review_this_week = sub1.checkbox("Review This Week", value=bool(detail.get("review_this_week")))
        discussed_this_week = sub2.checkbox("Discussed This Week", value=bool(detail.get("discussed_this_week")))
        submitted = st.form_submit_button("Save Meeting Fields", type="primary")
        if submitted:
            result = update_meeting_fields(
                selected_type,
                selected_record_id,
                {
                    "client_waiting_for": client_waiting_for.strip(),
                    "progress_summary": progress_summary.strip(),
                    "main_issue": main_issue.strip(),
                    "block_point": block_point.strip(),
                    "waiting_for_text": waiting_for_text.strip(),
                    "likely_reason": likely_reason.strip(),
                    "need_from_meeting": need_from_meeting.strip(),
                    "next_step_summary": next_step_summary.strip(),
                    "meeting_note": meeting_note.strip(),
                    "review_this_week": review_this_week,
                    "discussed_this_week": discussed_this_week,
                },
                operator=acting_user,
            )
            if result.get("updated"):
                st.success(result["message"])
                st.rerun()
            else:
                st.info(result["message"])
    st.markdown("</div>", unsafe_allow_html=True)

with timeline_tab:
    st.subheader("Event Timeline")
    render_project_table(
        get_record_timeline(selected_type, selected_record_id),
        [
            "event_time",
            "event_type",
            "old_phase",
            "new_phase",
            "old_health",
            "new_health",
            "old_result",
            "new_result",
            "operator",
            "event_note",
        ],
        empty_message="No event logs yet.",
        enable_jump=False,
    )

    st.subheader("Meeting Snapshots")
    render_project_table(
        get_record_snapshots(selected_type, selected_record_id),
        [
            "meeting_week",
            "phase",
            "health_status",
            "main_issue",
            "meeting_note",
            "next_step_summary",
            "snapshot_time",
        ],
        empty_message="No meeting snapshots yet.",
        enable_jump=False,
    )
