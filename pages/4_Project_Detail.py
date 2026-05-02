from __future__ import annotations

from datetime import date
from html import escape
from textwrap import dedent
from typing import Any

import streamlit as st

from core.auth import require_login
from core.dictionaries import (
    HEALTH_STATUSES,
    MEETING_POOL_HEALTH,
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
    set_record_archive_status,
    update_detail_fields,
    update_meeting_fields,
    update_request_layer_fields,
)
from services.upgrade_service import (
    get_operation_extension_rows,
    get_project_extension_rows,
    get_related_suppliers,
)
from services.project_service import (
    get_record_detail,
    get_record_snapshots,
    get_record_timeline,
    list_board_projects,
    list_detail_ids,
)
from ui.project_table import render_project_table
from ui.theme import apply_theme, render_badges_html, render_page_header
from ui.upgrade_ui import render_layered_records, render_upgrade_css


current_user = require_login()
acting_user = current_user["display_name"]

DISPLAY_TO_REQUEST_TYPE = {v: k for k, v in REQUEST_TYPE_DISPLAY.items()}
HIGH_ATTENTION_HEALTH = {"Need Decision", "Need Alignment", "Blocked", "Delayed", "Due Soon"}
SEARCH_FIELDS = [
    "project_id",
    "project_name",
    "order_no",
    "linked_project_name",
    "client_code",
    "current_owner",
    "next_step_owner",
    "client_waiting_for",
    "progress_summary",
    "main_issue",
    "block_point",
    "waiting_for_text",
    "likely_reason",
    "need_from_meeting",
    "next_step_summary",
    "meeting_note",
    "last_event",
    "display_title",
    "display_id",
    "linked_orders",
    "request_note",
    "pattern_note",
]


def _html(markup: str) -> str:
    return dedent(markup).strip()


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


def _clean(value: object, default: str = "-") -> str:
    return escape(_show_value(value, default)).replace("\n", "<br>")


def _show_multi(value: object) -> str:
    items = parse_multi_value(value)
    return ", ".join(items) if items else "-"


def _bool_to_yes_no(value: object) -> str:
    return "Yes" if bool(value) else "No"


def _select_index(options: list[str], value: object, default_index: int = 0) -> int:
    text = str(value or "")
    return options.index(text) if text in options else default_index


def _toggle_editor(key: str) -> None:
    st.session_state[key] = not st.session_state.get(key, False)


def _open_record(record_type: str, record_id: str) -> None:
    st.session_state["selected_detail_type"] = record_type
    st.session_state["selected_detail_id"] = record_id
    st.rerun()


def _row_id(row: dict[str, Any]) -> str:
    return str(row.get("entity_id") or row.get("display_id") or row.get("order_no") or row.get("project_id") or "")


def _row_title(row: dict[str, Any]) -> str:
    return str(row.get("display_title") or row.get("project_name") or row.get("linked_project_name") or "-")


def _row_matches_keyword(row: dict[str, Any], keyword: str) -> bool:
    keyword = keyword.strip().lower()
    if not keyword:
        return True
    return any(keyword in str(row.get(field) or "").lower() for field in SEARCH_FIELDS)


def _filter_focus_rows(rows: list[dict[str, Any]], filters: dict[str, object]) -> list[dict[str, Any]]:
    search = str(filters.get("search") or "").strip()
    owner = str(filters.get("owner") or "").strip().lower()
    phase = str(filters.get("phase") or "").strip().lower()
    health = str(filters.get("health") or "").strip().lower()
    priority_filter = str(filters.get("priority") or "").strip().lower()
    review_only = bool(filters.get("review_only"))
    meeting_pool_only = bool(filters.get("meeting_pool_only"))
    high_attention_only = bool(filters.get("high_attention_only"))

    filtered = [row for row in rows if _row_matches_keyword(row, search)]
    if owner:
        filtered = [row for row in filtered if str(row.get("current_owner") or "").lower() == owner]
    if phase:
        filtered = [row for row in filtered if str(row.get("phase") or "").lower() == phase]
    if health:
        filtered = [row for row in filtered if str(row.get("health_status") or "").lower() == health]
    if priority_filter:
        filtered = [row for row in filtered if str(row.get("priority") or "").lower() == priority_filter]
    if review_only:
        filtered = [row for row in filtered if bool(row.get("review_this_week"))]
    if meeting_pool_only:
        filtered = [row for row in filtered if (row.get("health_status") in MEETING_POOL_HEALTH) or bool(row.get("review_this_week"))]
    if high_attention_only:
        filtered = [
            row
            for row in filtered
            if (row.get("health_status") in HIGH_ATTENTION_HEALTH) or bool(row.get("pattern_flag"))
        ]

    priority = {
        "Need Decision": 1,
        "Blocked": 2,
        "Delayed": 3,
        "Due Soon": 4,
        "Need Alignment": 5,
        "Waiting Client": 6,
        "Waiting Supplier": 7,
        "Waiting Internal": 8,
    }
    return sorted(
        filtered,
        key=lambda row: (
            priority.get(row.get("health_status") or "", 99),
            str(row.get("target_date") or "9999-12-31"),
            str(row.get("entity_type") or ""),
            _row_id(row),
        ),
    )


def _result_options(board_type: str) -> list[str]:
    if board_type == "Sales":
        return SALES_RESULTS
    if board_type == "Operation":
        return OPERATION_RESULTS
    return list(dict.fromkeys(SALES_RESULTS + OPERATION_RESULTS))


def _result_label(row: dict[str, Any]) -> str:
    record_id = _row_id(row)
    title = _row_title(row)
    client = row.get("client_code") or "-"
    owner = row.get("current_owner") or "-"
    health = row.get("health_status") or "-"
    return f"{record_id} — {title} | {client} | {owner} | {health}"


def _mini_item(label: str, value: object) -> str:
    return (
        f"<div class='zt-detail-mini-card'>"
        f"<div class='zt-detail-mini-label'>{escape(label)}</div>"
        f"<div class='zt-detail-mini-value'>{_clean(value)}</div>"
        f"</div>"
    )


def _is_url(value: object) -> bool:
    text = str(value or "").strip()
    return text.startswith("http://") or text.startswith("https://")


def _has_meaningful_value(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text and text != "-")


def _overview_value_html(label: str, value: object) -> str:
    text = _show_value(value)
    if "link" in label.lower() and _is_url(text):
        safe_url = escape(text, quote=True)
        safe_text = escape(text)
        return (
            f"<a class='zt-reference-link' href='{safe_url}' target='_blank' rel='noopener noreferrer'>"
            "Open Reference</a>"
            f"<div class='zt-reference-url'>{safe_text}</div>"
        )
    return _clean(value)


def _field_item(label: str, value: object) -> str:
    return f"""
    <div class='zt-overview-field'>
        <div class='zt-overview-label'>{escape(label)}</div>
        <div class='zt-overview-value'>{_overview_value_html(label, value)}</div>
    </div>
    """


def _overview_section(title: str, items: list[tuple[str, object]]) -> str:
    fields = "".join(_field_item(label, value) for label, value in items)
    return _html(
        f"""
        <div class='zt-overview-section'>
            <div class='zt-overview-section-title'>{escape(title)}</div>
            <div class='zt-overview-grid'>{fields}</div>
        </div>
        """
    )



def _render_optional_overview_section(title: str, items: list[tuple[str, object]]) -> None:
    if any(_has_meaningful_value(value) for _, value in items):
        st.markdown(_overview_section(title, items), unsafe_allow_html=True)

def _search_result_card(row: dict[str, Any]) -> str:
    record_type = str(row.get("entity_type") or "-")
    record_id = _row_id(row)
    title = _row_title(row)
    focus = row.get("health_status") or "Normal Follow-up"
    order_text = row.get("order_no") if record_type == "Operation" else row.get("linked_orders") or row.get("linked_order_count")
    meta_items = [
        ("Client", row.get("client_code") or "-"),
        ("Owner", row.get("current_owner") or "-"),
        ("Phase", row.get("phase") or "-"),
        ("Result", row.get("result_status") or "-"),
        ("Target", row.get("target_date") or "-"),
        ("Order", order_text or "-"),
    ]
    meta_html = "".join(
        f"<div class='zt-search-meta'><span>{escape(label)}</span><strong>{_clean(value)}</strong></div>"
        for label, value in meta_items
    )
    return _html(
        f"""
        <div class='zt-search-result-card'>
            <div class='zt-search-result-top'>
                <div>
                    <div class='zt-project-eyebrow'>{escape(record_type)} detail result</div>
                    <div class='zt-search-result-title'><span>{escape(record_id)}</span> — {_clean(title)}</div>
                </div>
                <div class='zt-project-focus-pill'>{_clean(focus)}</div>
            </div>
            <div class='zt-search-meta-grid'>{meta_html}</div>
            <div class='zt-search-next'><b>Next Step:</b> {_clean(row.get('next_step_summary'))}</div>
        </div>
        """
    )


def _render_search_focus() -> tuple[str | None, str | None]:
    st.markdown(
        _html(
            """
            <div class='zt-filter-intro-card'>
                <div class='zt-section-kicker'>Filter & Focus</div>
                <div class='zt-subtle-text'>Narrow the list by type, owner, phase, health and meeting relevance. Use key words to quickly find the right record.</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    phase_options = list(dict.fromkeys(SALES_PHASES + OPERATION_PHASES))

    r1c0, r1c1, r1c2, r1c3, r1c4 = st.columns([0.8, 1, 1, 1, 1])
    type_filter = r1c0.selectbox("Type", options=["All", "Sales", "Operation"], key="detail_focus_type")
    owner = r1c1.selectbox("Current Owner", options=[""] + PEOPLE, key="detail_focus_owner")
    phase = r1c2.selectbox("Phase", options=[""] + phase_options, key="detail_focus_phase")
    health = r1c3.selectbox("Health", options=[""] + HEALTH_STATUSES, key="detail_focus_health")
    priority_value = r1c4.selectbox("Priority", options=[""] + PRIORITIES, key="detail_focus_priority")

    r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns([2.2, 1, 1, 1, 1])
    search = r2c1.text_input(
        "Key words",
        value=st.session_state.get("detail_keyword", ""),
        key="detail_keyword",
        placeholder="Search Order No, Project ID, linked project, client, issue or next step...",
    )
    review_only = r2c2.checkbox("Review this week", value=st.session_state.get("detail_focus_review", False), key="detail_focus_review")
    meeting_pool_only = r2c3.checkbox("Meeting pool only", value=st.session_state.get("detail_focus_meeting_pool", False), key="detail_focus_meeting_pool")
    high_attention_only = r2c4.checkbox("High attention only", value=st.session_state.get("detail_focus_attention", False), key="detail_focus_attention")
    # If a record has just been archived, enable "Include archived" on the next rerun.
    # Do this before the checkbox widget is created. Streamlit does not allow
    # assigning to a widget-backed session_state key after that widget has
    # already been instantiated in the same run.
    if st.session_state.pop("detail_force_include_archived", False):
        st.session_state["detail_include_archived"] = True

    include_archived = r2c5.checkbox("Include archived", value=st.session_state.get("detail_include_archived", False), key="detail_include_archived")

    if type_filter == "Sales":
        all_rows = list_board_projects("Sales", include_archived=include_archived)
    elif type_filter == "Operation":
        all_rows = list_board_projects("Operation", include_archived=include_archived)
    else:
        all_rows = list_board_projects("Sales", include_archived=include_archived) + list_board_projects("Operation", include_archived=include_archived)

    focus_rows = _filter_focus_rows(
        all_rows,
        {
            "search": search,
            "owner": owner,
            "phase": phase,
            "health": health,
            "priority": priority_value,
            "review_only": review_only,
            "meeting_pool_only": meeting_pool_only,
            "high_attention_only": high_attention_only,
        },
    )

    st.markdown(
        _html(
            f"""
            <div class='zt-search-count-strip'>
                <b>{len(focus_rows)}</b> result(s) found. Select one result below; the detail page will open automatically.
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    if not focus_rows:
        st.session_state["selected_detail_type"] = None
        st.session_state["selected_detail_id"] = None
        st.info("No matching record found. Try fewer key words or clear some filters.")
        return None, None

    label_to_row: dict[str, dict[str, Any]] = {}
    result_labels: list[str] = []
    for row in focus_rows:
        base_label = _result_label(row)
        label = base_label
        duplicate_index = 2
        while label in label_to_row:
            label = f"{base_label} ({duplicate_index})"
            duplicate_index += 1
        label_to_row[label] = row
        result_labels.append(label)

    current_type = st.session_state.get("selected_detail_type")
    current_id = st.session_state.get("selected_detail_id")
    current_label = ""
    for label, row in label_to_row.items():
        if str(row.get("entity_type") or "Sales") == current_type and _row_id(row) == current_id:
            current_label = label
            break

    signature = "|".join(
        [
            str(type_filter),
            str(search),
            str(owner),
            str(phase),
            str(health),
            str(priority_value),
            str(review_only),
            str(meeting_pool_only),
            str(high_attention_only),
            str(include_archived),
        ]
    )
    widget_key = "detail_focus_selected_result"

    if st.session_state.get("detail_focus_signature") != signature:
        st.session_state[widget_key] = current_label or result_labels[0]
        st.session_state["detail_focus_signature"] = signature
    elif st.session_state.get(widget_key) not in result_labels:
        st.session_state[widget_key] = current_label or result_labels[0]

    selected_label = st.selectbox("Search results", options=result_labels, key=widget_key)
    selected_row = label_to_row[selected_label]
    selected_type = str(selected_row.get("entity_type") or "Sales")
    selected_id = _row_id(selected_row)
    st.session_state["selected_detail_type"] = selected_type
    st.session_state["selected_detail_id"] = selected_id
    st.caption("Selected record opens automatically below. This does not change any project data.")
    return selected_type, selected_id


def _render_sticky_summary(detail: dict[str, Any], selected_type: str, selected_record_id: str) -> None:
    project_title = detail.get("project_name") if selected_type == "Sales" else detail.get("linked_project_name") or detail.get("project_id") or "(Unlinked)"
    items = [
        ("ID", selected_record_id),
        ("Project / Item", project_title),
        ("Client", detail.get("client_code")),
        ("Owner", detail.get("current_owner")),
        ("Phase", detail.get("phase")),
        ("Health", detail.get("health_status")),
        ("Result", detail.get("result_status")),
    ]
    item_html = "".join(
        f"<div class='zt-sticky-summary-item'><span>{escape(label)}</span><strong>{_clean(value)}</strong></div>"
        for label, value in items
    )
    st.markdown(
        _html(
            f"""
            <div class='zt-sticky-summary'>
                <div class='zt-sticky-summary-kicker'>Now editing</div>
                <div class='zt-sticky-summary-grid'>{item_html}</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def _render_selected_header(detail: dict[str, Any], selected_type: str, selected_record_id: str) -> None:
    header_title = detail.get("project_name") if selected_type == "Sales" else detail.get("linked_project_name") or detail.get("project_id") or "(Unlinked)"
    header_subtitle = (
        f"Client Code: {_show_value(detail.get('client_code'))} | Linked Orders: {detail.get('linked_order_count') or 0} | Priority: {_show_value(detail.get('priority'))}"
        if selected_type == "Sales"
        else f"Project ID: {_show_value(detail.get('project_id'))} | Linked Project: {_show_value(detail.get('linked_project_name'))}"
    )

    st.markdown(
        _html(
            f"""
            <div class='zt-selected-detail-card'>
                <div class='zt-project-eyebrow'>Selected detail</div>
                <div class='zt-selected-detail-title'><span>{escape(selected_record_id)}</span> — {_clean(header_title)}</div>
                <div class='zt-selected-detail-subtitle'>{escape(header_subtitle)}</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )
    badges_html = render_badges_html(
        detail.get("phase"),
        detail.get("health_status"),
        detail.get("result_status"),
        bool(detail.get("pattern_flag")),
    )
    if badges_html:
        st.markdown(badges_html, unsafe_allow_html=True)

    mini_cards_html = (
        "<div class='zt-detail-mini-grid'>"
        + _mini_item("Current Owner", detail.get("current_owner"))
        + _mini_item("Next Step Owner", detail.get("next_step_owner"))
        + _mini_item("Last Event", detail.get("last_event"))
        + _mini_item("Target Date", detail.get("target_date"))
        + "</div>"
    )
    st.markdown(mini_cards_html, unsafe_allow_html=True)

    _render_optional_overview_section(
        "Meeting Snapshot",
        [
            ("Client Waiting For", detail.get("client_waiting_for")),
            ("Main Issue", detail.get("main_issue")),
            ("Blocked At", detail.get("block_point")),
            ("Current Progress", detail.get("progress_summary")),
            ("Possible Reason", detail.get("likely_reason")),
            ("Need From Meeting", detail.get("need_from_meeting")),
            ("Next Step", detail.get("next_step_summary")),
            ("Meeting Note", detail.get("meeting_note")),
        ],
    )


def _render_overview(detail: dict[str, Any], selected_type: str) -> None:
    if selected_type == "Sales":
        basic_items = [
            ("Project ID", detail.get("project_id")),
            ("Project Name", detail.get("project_name")),
            ("Client Code", detail.get("client_code")),
            ("Category", detail.get("category")),
            ("Priority", detail.get("priority")),
            ("Linked Orders", detail.get("linked_orders") or detail.get("linked_order_count")),
        ]
    else:
        basic_items = [
            ("Order No", detail.get("order_no")),
            ("Project ID", detail.get("project_id")),
            ("Linked Project", detail.get("linked_project_name")),
            ("Client Code", detail.get("client_code")),
            ("Reference Link", detail.get("reference_link")),
        ]

    st.markdown(
        _overview_section("Basic Info", basic_items),
        unsafe_allow_html=True,
    )
    st.markdown(
        _overview_section(
            "Status Snapshot",
            [
                ("Current Owner", detail.get("current_owner")),
                ("Support From", _show_multi(detail.get("support_from"))),
                ("Next Step Owner", detail.get("next_step_owner")),
                ("Next Step Support", _show_multi(detail.get("next_step_support"))),
                ("Phase", detail.get("phase")),
                ("Health Status", detail.get("health_status")),
                ("Result Status", detail.get("result_status")),
                ("Target Date", detail.get("target_date")),
                ("Review This Week", _bool_to_yes_no(detail.get("review_this_week"))),
                ("Discussed in Meeting", _bool_to_yes_no(detail.get("discussed_this_week"))),
            ],
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        _overview_section(
            "Meeting Focus",
            [
                ("Client Waiting For", detail.get("client_waiting_for")),
                ("Progress Summary", detail.get("progress_summary")),
                ("Main Issue", detail.get("main_issue")),
                ("Blocked At", detail.get("block_point")),
                ("Waiting For What", detail.get("waiting_for_text")),
                ("Possible Reason", detail.get("likely_reason")),
                ("Need From Meeting", detail.get("need_from_meeting")),
                ("Meeting Note", detail.get("meeting_note")),
            ],
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        _overview_section(
            "Next Action / Support",
            [
                ("Next Step", detail.get("next_step_summary")),
                ("What is needed", REQUEST_TYPE_DISPLAY.get(detail.get("request_type") or "None", detail.get("request_type") or "-")),
                ("Request Summary", detail.get("request_note")),
                ("Decision By", detail.get("need_decision_from")),
                ("Align With", _show_multi(detail.get("need_alignment_with"))),
                ("Waiting For", _show_multi(detail.get("waiting_for_person"))),
                ("Repeated Issue", _bool_to_yes_no(detail.get("pattern_flag"))),
                ("Repeated Issue Note", detail.get("pattern_note")),
            ],
        ),
        unsafe_allow_html=True,
    )


apply_theme()
render_upgrade_css()
render_page_header(
    "Project / Order Detail",
    "Search, open and update Sales projects or Operation orders from one focused editing page.",
)

selection_type, selection_id = _render_search_focus()
if not selection_type or not selection_id:
    st.stop()

selected_type = selection_type
selected_record_id = selection_id

include_archived_records = bool(st.session_state.get("detail_include_archived"))
record_ids = list_detail_ids(selected_type, include_archived=include_archived_records)
if selected_record_id not in record_ids:
    st.warning("Selected record is no longer available under the current filters.")
    st.stop()

st.text_input("Acting User", value=acting_user, disabled=True)

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

_render_selected_header(detail, selected_type, selected_record_id)
_render_sticky_summary(detail, selected_type, selected_record_id)

if selected_type == "Sales":
    tab_names = [
        "Overview",
        "Basic Info",
        "Meeting Prep",
        "Supplier Details",
        "Project Items",
        "Price Comparison",
        "Client Quotation",
        "Sample Tracking",
        "History",
    ]
else:
    tab_names = [
        "Overview",
        "Basic Info",
        "Meeting Prep",
        "Supplier Details",
        "Order Details",
        "Order Costs",
        "Client Quotation",
        "History",
    ]

tab_map = dict(zip(tab_names, st.tabs(tab_names)))
overview_tab = tab_map["Overview"]
detail_tab = tab_map["Basic Info"]
meeting_tab = tab_map["Meeting Prep"]
timeline_tab = tab_map["History"]

with overview_tab:
    _render_overview(detail, selected_type)
    if selected_type == "Sales":
        st.markdown(
            "<div class='zt-board-section-title' style='margin-top:1rem;'>Linked orders from Operation</div>",
            unsafe_allow_html=True,
        )
        render_project_table(
            detail.get("linked_orders_rows") or [],
            ["order_no", "project_id", "client_code", "phase", "health_status", "result_status", "last_event", "target_date", "review_this_week"],
            empty_message="No linked orders yet.",
        )

with detail_tab:
    with st.container(border=True):
        st.markdown(
            _overview_section(
                "Basic Info Summary",
                [
                    ("Project Name" if selected_type == "Sales" else "Order No", detail.get("project_name") if selected_type == "Sales" else detail.get("order_no")),
                    ("Project ID", detail.get("project_id")),
                    ("Client Code", detail.get("client_code")),
                    ("Current Owner", detail.get("current_owner")),
                    ("Next Step Owner", detail.get("next_step_owner")),
                    ("Phase", detail.get("phase")),
                    ("Health Status", detail.get("health_status")),
                    ("Result Status", detail.get("result_status")),
                    ("Target Date", detail.get("target_date")),
                    ("Reference Link", detail.get("reference_link")),
                ],
            ),
            unsafe_allow_html=True,
        )

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
                        priority_options = [""] + PRIORITIES
                        priority = st.selectbox("Priority", options=priority_options, index=_select_index(priority_options, detail.get("priority")))
                        reference_link = st.text_input("Reference Link", value=detail.get("reference_link") or "")
                    else:
                        st.text_input("Order No", value=detail.get("order_no") or selected_record_id, disabled=True)
                        project_id = st.text_input("Project ID", value=detail.get("project_id") or "")
                        client_code = st.text_input("Client Code", value=detail.get("client_code") or "")
                        reference_link = st.text_input("Reference Link", value=detail.get("reference_link") or "")

                    people_options = [""] + PEOPLE
                    current_owner = st.selectbox("Current Owner", options=people_options, index=_select_index(people_options, detail.get("current_owner")))
                    support_from = st.multiselect("Need Support From", options=PEOPLE, default=parse_multi_value(detail.get("support_from")))
                    next_step_owner = st.selectbox("Next Step Owner", options=people_options, index=_select_index(people_options, detail.get("next_step_owner")))
                    next_step_support = st.multiselect("Next Step Support From", options=PEOPLE, default=parse_multi_value(detail.get("next_step_support")))

                with col2:
                    phase_options = SALES_PHASES if selected_type == "Sales" else OPERATION_PHASES
                    result_options = SALES_RESULTS if selected_type == "Sales" else OPERATION_RESULTS
                    phase = st.selectbox("Phase", options=phase_options, index=_select_index(phase_options, detail.get("phase")))
                    health_status = st.selectbox("Health Status", options=HEALTH_STATUSES, index=_select_index(HEALTH_STATUSES, detail.get("health_status")))
                    result_label = "Sales Result" if selected_type == "Sales" else "Order Result"
                    result_status = st.selectbox(result_label, options=result_options, index=_select_index(result_options, detail.get("result_status")))
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

with meeting_tab:
    with st.container(border=True):
        st.markdown(
            _overview_section(
                "Meeting Prep Summary",
                [
                    ("Client Waiting For", detail.get("client_waiting_for")),
                    ("Current Progress", detail.get("progress_summary")),
                    ("Main Issue", detail.get("main_issue")),
                    ("Blocked At", detail.get("block_point")),
                    ("Need From Meeting", detail.get("need_from_meeting")),
                    ("Next Step", detail.get("next_step_summary")),
                    ("Waiting For What", detail.get("waiting_for_text")),
                    ("Possible Reason", detail.get("likely_reason")),
                    ("Review This Week", _bool_to_yes_no(detail.get("review_this_week"))),
                    ("Discussed in Meeting", _bool_to_yes_no(detail.get("discussed_this_week"))),
                    ("Meeting Note", detail.get("meeting_note")),
                ],
            ),
            unsafe_allow_html=True,
        )

        toggle_label = "Hide Meeting Prep Editor" if st.session_state[meeting_open_key] else "Edit Meeting Prep"
        st.button(toggle_label, key=f"toggle_{meeting_open_key}", on_click=_toggle_editor, args=(meeting_open_key,))

        if st.session_state[meeting_open_key]:
            with st.form(f"meeting_edit_form_{selected_type}_{selected_record_id}"):
                client_waiting_for = st.text_input("Client Waiting For", value=detail.get("client_waiting_for") or "")
                progress_summary = st.text_area("Current Progress", value=detail.get("progress_summary") or "", height=110)
                main_issue = st.text_area("Main Issue", value=detail.get("main_issue") or "", height=110)
                block_point = st.text_area("Blocked At", value=detail.get("block_point") or "", height=110)
                need_from_meeting = st.text_input("Need From Meeting", value=detail.get("need_from_meeting") or "")
                next_step_summary = st.text_area("Next Step", value=detail.get("next_step_summary") or "", height=120)
                with st.expander("Optional details", expanded=False):
                    waiting_for_text = st.text_input("Waiting For What", value=detail.get("waiting_for_text") or "")
                    likely_reason = st.text_input("Possible Reason", value=detail.get("likely_reason") or "")
                    review_this_week = st.checkbox("Review This Week", value=bool(detail.get("review_this_week")))
                    discussed_this_week = st.checkbox("Discussed in Meeting", value=bool(detail.get("discussed_this_week")))
                    meeting_note = st.text_area("Meeting Note", value=detail.get("meeting_note") or "", height=100)
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


# v18 extension tabs. These are read-only summary/detail views over new extension tables.
# They do not modify the original Sales / Operation core workflow.
ext_project_id = selected_record_id if selected_type == "Sales" else detail.get("project_id")
if selected_type == "Sales":
    ext_rows = get_project_extension_rows(str(ext_project_id or "")) if ext_project_id else {}
else:
    ext_rows = get_operation_extension_rows(selected_record_id, str(ext_project_id or "") if ext_project_id else None)

with tab_map["Supplier Details"]:
    supplier_rows = get_related_suppliers(selected_type, selected_record_id, project_id=str(ext_project_id or "") if ext_project_id else None)
    render_layered_records(
        "Supplier Details",
        supplier_rows,
        key_prefix=f"detail_supplier_{record_key}",
        summary_field="active_status",
        preview_columns=["supplier_id", "supplier_code", "supplier_name", "supplier_source", "contact_status", "active_status", "active_reason", "quality_risk", "commercial_risk"],
    )

if selected_type == "Sales":
    with tab_map["Project Items"]:
        render_layered_records(
            "Project Items",
            ext_rows.get("Project Items", []),
            key_prefix=f"detail_items_{record_key}",
            summary_field="item_status",
            preview_columns=["project_id", "item_code", "item_name", "client_item_no", "material", "surface_treatment", "estimated_qty", "unit", "item_status"],
        )

    with tab_map["Price Comparison"]:
        render_layered_records(
            "Supplier Price Comparison",
            ext_rows.get("Supplier Price Comparison", []),
            key_prefix=f"detail_price_{record_key}",
            summary_field="comparison_status",
            preview_columns=["project_id", "item_code", "supplier_code", "supplier_name", "quote_round", "supplier_unit_cost", "currency", "recommended_supplier", "selected_supplier", "comparison_status"],
        )

    with tab_map["Client Quotation"]:
        st.markdown("### Client Quotation Versions")
        render_layered_records(
            "Client Quotation Header",
            ext_rows.get("Client Quotation Header", []),
            key_prefix=f"detail_client_header_{record_key}",
            summary_field="quote_status",
            preview_columns=["client_quote_id", "project_id", "quote_version", "quote_date", "client_code", "quote_status", "price_term", "quote_currency"],
        )
        st.markdown("### Client Quotation Lines")
        render_layered_records(
            "Client Quotation Lines",
            ext_rows.get("Client Quotation Lines", []),
            key_prefix=f"detail_client_lines_{record_key}",
            preview_columns=["client_quote_id", "project_id", "item_code", "client_unit_price", "supplier_unit_cost", "quantity_basis", "estimated_gp", "estimated_gp_percent"],
        )
        st.markdown("### Locked Index Snapshots")
        render_layered_records(
            "Index Snapshot",
            ext_rows.get("Index Snapshot", []),
            key_prefix=f"detail_index_snapshots_{record_key}",
            preview_columns=["project_id", "item_code", "quote_version", "snapshot_date", "material_index_name", "material_index_value", "freight_route", "exchange_rate_pair", "exchange_rate_value"],
        )

    with tab_map["Sample Tracking"]:
        render_layered_records(
            "Sample Tracking",
            ext_rows.get("Sample Tracking", []),
            key_prefix=f"detail_sample_{record_key}",
            summary_field="sample_status",
            preview_columns=["project_id", "item_code", "supplier_name", "sample_type", "sample_round", "sample_status", "target_sample_date", "test_status", "next_step_owner", "sample_folder_link"],
        )
else:
    with tab_map["Order Details"]:
        render_layered_records(
            "Order Details",
            ext_rows.get("Order Details", []),
            key_prefix=f"detail_order_details_{record_key}",
            summary_field="shipment_status",
            preview_columns=["order_no", "project_id", "item_code", "supplier_name", "order_qty", "client_unit_price", "supplier_unit_cost", "extra_cost", "gross_profit", "gross_profit_percent", "shipment_status"],
        )

    with tab_map["Order Costs"]:
        render_layered_records(
            "Order Costs",
            ext_rows.get("Order Costs", []),
            key_prefix=f"detail_order_costs_{record_key}",
            summary_field="cost_type",
            preview_columns=["order_no", "project_id", "item_code", "cost_type", "cost_amount", "currency", "paid_by", "charge_to_client", "cost_date"],
        )

    with tab_map["Client Quotation"]:
        st.markdown("### Linked Client Quotation Versions")
        render_layered_records(
            "Client Quotation Header",
            ext_rows.get("Client Quotation Header", []),
            key_prefix=f"detail_op_client_header_{record_key}",
            summary_field="quote_status",
            preview_columns=["client_quote_id", "project_id", "quote_version", "quote_date", "client_code", "quote_status", "price_term", "quote_currency"],
        )
        st.markdown("### Locked Index Snapshots")
        render_layered_records(
            "Index Snapshot",
            ext_rows.get("Index Snapshot", []),
            key_prefix=f"detail_op_snapshots_{record_key}",
            preview_columns=["project_id", "item_code", "quote_version", "snapshot_date", "material_index_name", "material_index_value", "freight_route", "exchange_rate_pair", "exchange_rate_value"],
        )

with timeline_tab:
    st.markdown("<div class='zt-board-section-title'>Event Timeline</div>", unsafe_allow_html=True)
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

    st.markdown("<div class='zt-board-section-title' style='margin-top:1rem;'>Meeting Snapshots</div>", unsafe_allow_html=True)
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

    with st.expander("Advanced raw record", expanded=False):
        st.json(detail)


st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
with st.expander("Advanced Record Control", expanded=False):
    is_archived = bool(detail.get("is_archived"))
    st.markdown(
        _html(
            f"""
            <div class='zt-filter-intro-card'>
                <div class='zt-section-kicker'>Record Control</div>
                <div class='zt-subtle-text'>Archive hides this record from Dashboard, Boards and Meeting Mode without deleting history. Restore makes it active again.</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )
    status_text = "Archived" if is_archived else "Active"
    st.write(f"Current status: **{status_text}**")
    confirm_key = f"archive_confirm_{selected_type}_{selected_record_id}"
    confirm_text = st.text_input("Type the Project ID / Order No to confirm", key=confirm_key)

    def _confirmation_tokens(*values: Any) -> set[str]:
        tokens: set[str] = set()
        for value in values:
            raw = str(value or "").strip()
            if not raw:
                continue
            pieces = [raw]
            for separator in [",", ";", "|", "\n"]:
                next_pieces: list[str] = []
                for piece in pieces:
                    next_pieces.extend(piece.split(separator))
                pieces = next_pieces
            for piece in pieces:
                cleaned = piece.strip()
                if cleaned:
                    tokens.add(cleaned.upper())
        return tokens

    accepted_confirmation_values = _confirmation_tokens(
        selected_record_id,
        detail.get("project_id"),
        detail.get("order_no"),
        detail.get("linked_orders"),
    )
    confirmed = confirm_text.strip().upper() in accepted_confirmation_values
    accepted_display = " / ".join(sorted(accepted_confirmation_values)) if accepted_confirmation_values else selected_record_id
    st.caption(f"Accepted confirmation value: {accepted_display}")

    if is_archived:
        if st.button("Restore this record", key=f"restore_{selected_type}_{selected_record_id}", disabled=not confirmed):
            result = set_record_archive_status(selected_type, selected_record_id, archived=False, operator=acting_user)
            if result.get("updated"):
                st.rerun()
            else:
                st.info(result.get("message", "No change."))
    else:
        if st.button("Archive this record", key=f"archive_{selected_type}_{selected_record_id}", disabled=not confirmed):
            result = set_record_archive_status(selected_type, selected_record_id, archived=True, operator=acting_user)
            if result.get("updated"):
                # Set a non-widget flag now; the actual checkbox state is updated
                # at the top of the next rerun before the checkbox is created.
                st.session_state["detail_force_include_archived"] = True
                st.rerun()
            else:
                st.info(result.get("message", "No change."))
