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
    REQUEST_TYPE_DISPLAY,
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


DISPLAY_TO_REQUEST_TYPE = {v: k for k, v in REQUEST_TYPE_DISPLAY.items()}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def _show_value(value: object, default: str = "-") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _show_multi(value: object) -> str:
    items = parse_multi_value(value)
    return ", ".join(items) if items else "-"


def _bool_to_yes_no(value: object) -> str:
    return "Yes" if bool(value) else "No"


def _toggle_editor(key: str) -> None:
    st.session_state[key] = not st.session_state.get(key, False)


apply_theme()
render_page_header(
    "Project / Order Detail",
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

record_key = f"{selected_type}_{selected_record_id}"
basic_open_key = f"detail_basic_open_{record_key}"
request_open_key = f"detail_request_open_{record_key}"
meeting_open_key = f"detail_meeting_open_{record_key}"
for key in [basic_open_key, request_open_key, meeting_open_key]:
    st.session_state.setdefault(key, False)

header_title = detail.get("project_name") if selected_type == "Sales" else detail.get("linked_project_name") or detail.get("project_id") or "(Unlinked)"
header_subtitle = (
    f"Client Code: {_show_value(detail.get('client_code'))} | Linked Orders: {detail.get('linked_order_count') or 0} | Priority: {_show_value(detail.get('priority'))}"
    if selected_type == "Sales"
    else f"Project ID: {_show_value(detail.get('project_id'))} | Linked Project: {_show_value(detail.get('linked_project_name'))}"
)

st.markdown("<div class='zt-card'>", unsafe_allow_html=True)
st.markdown(
    f"<div class='zt-card-title'>{selected_record_id} — {header_title}</div>"
    f"<div class='zt-card-subtitle'>{header_subtitle}</div>",
    unsafe_allow_html=True,
)
render_badges(detail.get("phase"), detail.get("health_status"), detail.get("result_status"), bool(detail.get("pattern_flag")))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Current Owner", _show_value(detail.get("current_owner")))
c2.metric("Next Step Owner", _show_value(detail.get("next_step_owner")))
c3.metric("Last Event", _show_value(detail.get("last_event")))
c4.metric("Target Date", _show_value(detail.get("target_date")))

left, right = st.columns(2)
with left:
    st.write(f"**Client Waiting For:** {_show_value(detail.get('client_waiting_for'))}")
    st.write(f"**Main Issue:** {_show_value(detail.get('main_issue'))}")
    st.write(f"**Blocked At:** {_show_value(detail.get('block_point'))}")
    st.write(f"**Current Progress:** {_show_value(detail.get('progress_summary'))}")
with right:
    st.write(f"**Possible Reason:** {_show_value(detail.get('likely_reason'))}")
    st.write(f"**Need From Meeting:** {_show_value(detail.get('need_from_meeting'))}")
    st.write(f"**Next Step:** {_show_value(detail.get('next_step_summary'))}")
    st.write(f"**Meeting Note:** {_show_value(detail.get('meeting_note'))}")
    st.write(f"**What is needed:** {REQUEST_TYPE_DISPLAY.get(detail.get('request_type') or 'None', detail.get('request_type') or '-')}")
    st.write(f"**Request Summary:** {_show_value(detail.get('request_note'))}")
    st.write(f"**Decision By:** {_show_value(detail.get('need_decision_from'))}")
    st.write(f"**Align With:** {_show_multi(detail.get('need_alignment_with'))}")

st.markdown("</div>", unsafe_allow_html=True)

overview_tab, detail_tab, request_tab, meeting_tab, timeline_tab = st.tabs(
    [
        "Overview",
        "Basic Info",
        "Support / Decision",
        "Meeting Prep",
        "History",
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
    st.markdown("<div class='zt-panel-title'>Basic Info</div>", unsafe_allow_html=True)
    summary_left, summary_right = st.columns(2)
    with summary_left:
        if selected_type == "Sales":
            st.write(f"**Project Name:** {_show_value(detail.get('project_name'))}")
            st.write(f"**Client Code:** {_show_value(detail.get('client_code'))}")
            st.write(f"**Category:** {_show_value(detail.get('category'))}")
            st.write(f"**Priority:** {_show_value(detail.get('priority'))}")
        else:
            st.write(f"**Order No:** {_show_value(detail.get('order_no'))}")
            st.write(f"**Project ID:** {_show_value(detail.get('project_id'))}")
            st.write(f"**Client Code:** {_show_value(detail.get('client_code'))}")
        st.write(f"**Need Support From:** {_show_multi(detail.get('support_from'))}")
        st.write(f"**Next Step Support From:** {_show_multi(detail.get('next_step_support'))}")
        st.write(f"**Reference Link:** {_show_value(detail.get('reference_link'))}")
    with summary_right:
        result_label = "Sales Result" if selected_type == "Sales" else "Order Result"
        st.write(f"**Current Owner:** {_show_value(detail.get('current_owner'))}")
        st.write(f"**Next Step Owner:** {_show_value(detail.get('next_step_owner'))}")
        st.write(f"**Phase:** {_show_value(detail.get('phase'))}")
        st.write(f"**Health Status:** {_show_value(detail.get('health_status'))}")
        st.write(f"**{result_label}:** {_show_value(detail.get('result_status'))}")
        st.write(f"**Target Date:** {_show_value(detail.get('target_date'))}")
        st.write(f"**Doc Round:** {_show_value(detail.get('doc_round') or 0, default='0')}")
        st.write(f"**Test Round:** {_show_value(detail.get('test_round') or 0, default='0')}")
        if selected_type == "Sales":
            st.write(f"**Quote Round:** {_show_value(detail.get('quote_round') or 0, default='0')}")
            st.write(f"**Sample Round:** {_show_value(detail.get('sample_round') or 0, default='0')}")

    toggle_label = "Hide Basic Info Editor" if st.session_state[basic_open_key] else "Edit Basic Info"
    st.button(toggle_label, key=f"toggle_{basic_open_key}", on_click=_toggle_editor, args=(basic_open_key,))

    if st.session_state[basic_open_key]:
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
                support_from = st.multiselect("Need Support From", options=PEOPLE, default=parse_multi_value(detail.get("support_from")))
                next_step_owner = st.selectbox("Next Step Owner", options=[""] + PEOPLE, index=([""] + PEOPLE).index(detail.get("next_step_owner") or ""))
                next_step_support = st.multiselect("Next Step Support From", options=PEOPLE, default=parse_multi_value(detail.get("next_step_support")))

            with col2:
                phase_options = SALES_PHASES if selected_type == "Sales" else OPERATION_PHASES
                result_options = SALES_RESULTS if selected_type == "Sales" else OPERATION_RESULTS
                phase = st.selectbox("Phase", options=phase_options, index=phase_options.index(detail.get("phase") or phase_options[0]))
                health_status = st.selectbox("Health Status", options=HEALTH_STATUSES, index=HEALTH_STATUSES.index(detail.get("health_status") or HEALTH_STATUSES[0]))
                result_label = "Sales Result" if selected_type == "Sales" else "Order Result"
                result_status = st.selectbox(result_label, options=result_options, index=result_options.index(detail.get("result_status") or result_options[0]))
                target_date = st.date_input("Target Date", value=_parse_date(detail.get("target_date")))
                doc_round = st.number_input("Doc Round", min_value=0, step=1, value=int(detail.get("doc_round") or 0))
                test_round = st.number_input("Test Round", min_value=0, step=1, value=int(detail.get("test_round") or 0))
                if selected_type == "Sales":
                    quote_round = st.number_input("Quote Round", min_value=0, step=1, value=int(detail.get("quote_round") or 0))
                    sample_round = st.number_input("Sample Round", min_value=0, step=1, value=int(detail.get("sample_round") or 0))

            submitted = st.form_submit_button("Save Basic Info", type="primary")
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
                    st.session_state[basic_open_key] = False
                    st.success(result["message"])
                    st.rerun()
                else:
                    st.info(result["message"])
    st.markdown("</div>", unsafe_allow_html=True)

with request_tab:
    st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='zt-panel-title'>Support / Decision</div>", unsafe_allow_html=True)
    summary_left, summary_right = st.columns(2)
    with summary_left:
        st.write(f"**What is needed:** {REQUEST_TYPE_DISPLAY.get(detail.get('request_type') or 'None', detail.get('request_type') or '-')}")
        st.write(f"**Request Summary:** {_show_value(detail.get('request_note'))}")
        st.write(f"**Decision By:** {_show_value(detail.get('need_decision_from'))}")
        st.write(f"**Align With:** {_show_multi(detail.get('need_alignment_with'))}")
    with summary_right:
        st.write(f"**Waiting For:** {_show_multi(detail.get('waiting_for_person'))}")
        st.write(f"**Repeated Issue:** {_bool_to_yes_no(detail.get('pattern_flag'))}")
        st.write(f"**Repeated Issue Note:** {_show_value(detail.get('pattern_note'))}")

    toggle_label = "Hide Support / Decision Editor" if st.session_state[request_open_key] else "Edit Support / Decision"
    st.button(toggle_label, key=f"toggle_{request_open_key}", on_click=_toggle_editor, args=(request_open_key,))

    if st.session_state[request_open_key]:
        with st.form(f"request_edit_form_{selected_type}_{selected_record_id}"):
            col1, col2 = st.columns(2)
            request_display_options = [REQUEST_TYPE_DISPLAY[item] for item in REQUEST_TYPES]
            current_request_display = REQUEST_TYPE_DISPLAY.get(detail.get("request_type") or "None", "None")
            with col1:
                request_type_display = st.selectbox("What is needed", options=request_display_options, index=request_display_options.index(current_request_display))
                request_note = st.text_area("Request Summary", value=detail.get("request_note") or "", height=90)
                need_decision_from = st.selectbox("Decision By", options=[""] + PEOPLE, index=([""] + PEOPLE).index(detail.get("need_decision_from") or ""))
            with col2:
                need_alignment_with = st.multiselect("Align With", options=PEOPLE, default=parse_multi_value(detail.get("need_alignment_with")))
                waiting_for_person = st.multiselect("Waiting For", options=PEOPLE, default=parse_multi_value(detail.get("waiting_for_person")))
                pattern_flag = st.checkbox("Repeated Issue", value=bool(detail.get("pattern_flag")))
                pattern_note = st.text_area("Repeated Issue Note", value=detail.get("pattern_note") or "", height=90)

            submitted = st.form_submit_button("Save Support / Decision", type="primary")
            if submitted:
                result = update_request_layer_fields(
                    selected_type,
                    selected_record_id,
                    {
                        "request_type": DISPLAY_TO_REQUEST_TYPE.get(request_type_display, "None"),
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
                    st.session_state[request_open_key] = False
                    st.success(result["message"])
                    st.rerun()
                else:
                    st.info(result["message"])
    st.markdown("</div>", unsafe_allow_html=True)

with meeting_tab:
    st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='zt-panel-title'>Meeting Prep</div>", unsafe_allow_html=True)
    summary_left, summary_right = st.columns(2)
    with summary_left:
        st.write(f"**Client Waiting For:** {_show_value(detail.get('client_waiting_for'))}")
        st.write(f"**Current Progress:** {_show_value(detail.get('progress_summary'))}")
        st.write(f"**Main Issue:** {_show_value(detail.get('main_issue'))}")
        st.write(f"**Blocked At:** {_show_value(detail.get('block_point'))}")
    with summary_right:
        st.write(f"**Need From Meeting:** {_show_value(detail.get('need_from_meeting'))}")
        st.write(f"**Next Step:** {_show_value(detail.get('next_step_summary'))}")
        with st.expander("More meeting details", expanded=False):
            st.write(f"**Waiting For What:** {_show_value(detail.get('waiting_for_text'))}")
            st.write(f"**Possible Reason:** {_show_value(detail.get('likely_reason'))}")
            st.write(f"**Review This Week:** {_bool_to_yes_no(detail.get('review_this_week'))}")
            st.write(f"**Discussed in Meeting:** {_bool_to_yes_no(detail.get('discussed_this_week'))}")
            st.write(f"**Meeting Note:** {_show_value(detail.get('meeting_note'))}")

    toggle_label = "Hide Meeting Prep Editor" if st.session_state[meeting_open_key] else "Edit Meeting Prep"
    st.button(toggle_label, key=f"toggle_{meeting_open_key}", on_click=_toggle_editor, args=(meeting_open_key,))

    if st.session_state[meeting_open_key]:
        with st.form(f"meeting_edit_form_{selected_type}_{selected_record_id}"):
            client_waiting_for = st.text_input("Client Waiting For", value=detail.get("client_waiting_for") or "")
            progress_summary = st.text_area("Current Progress", value=detail.get("progress_summary") or "", height=90)
            main_issue = st.text_area("Main Issue", value=detail.get("main_issue") or "", height=90)
            block_point = st.text_area("Blocked At", value=detail.get("block_point") or "", height=90)
            need_from_meeting = st.text_input("Need From Meeting", value=detail.get("need_from_meeting") or "")
            next_step_summary = st.text_area("Next Step", value=detail.get("next_step_summary") or "", height=100)
            with st.expander("Optional details", expanded=False):
                waiting_for_text = st.text_input("Waiting For What", value=detail.get("waiting_for_text") or "")
                likely_reason = st.text_input("Possible Reason", value=detail.get("likely_reason") or "")
                review_this_week = st.checkbox("Review This Week", value=bool(detail.get("review_this_week")))
                discussed_this_week = st.checkbox("Discussed in Meeting", value=bool(detail.get("discussed_this_week")))
                meeting_note = st.text_area("Meeting Note", value=detail.get("meeting_note") or "", height=80)
            submitted = st.form_submit_button("Save Meeting Prep", type="primary")
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
                    st.session_state[meeting_open_key] = False
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
