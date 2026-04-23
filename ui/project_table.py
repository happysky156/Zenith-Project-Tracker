from __future__ import annotations

import pandas as pd
import streamlit as st

from core.state import set_selected_detail
from ui.action_buttons import render_board_action_buttons
from ui.theme import render_badges


SALES_DETAIL_FIELDS = [
    ("Client Waiting For", "client_waiting_for"),
    ("Main Issue", "main_issue"),
    ("Need From Meeting", "need_from_meeting"),
    ("Next Step", "next_step_summary"),
    ("Next Step Owner", "next_step_owner"),
    ("Linked Orders", "linked_orders"),
    ("Days Since Status", "days_since_status_update"),
    ("Days Since Review", "days_since_review"),
]



COLUMN_LABELS_COMMON = {
    "project_id": "Project ID",
    "project_name": "Project Name",
    "client_code": "Client Code",
    "linked_order_count": "Linked Orders",
    "linked_orders": "Linked Orders",
    "current_owner": "Current Owner",
    "phase": "Phase",
    "health_status": "Health Status",
    "quote_round": "Quote Round",
    "sample_round": "Sample Round",
    "main_issue": "Main Issue",
    "next_step_owner": "Next Step Owner",
    "target_date": "Target Date",
    "last_event": "Last Event",
    "days_since_status_update": "Days Since Status",
    "days_since_review": "Days Since Review",
    "review_this_week": "Review This Week",
    "order_no": "Order No",
    "linked_project_name": "Linked Project",
    "result_status": "Result",
    "waiting_for_text": "Waiting For What",
    "need_from_meeting": "Need From Meeting",
}

SALES_TABLE_LABELS = dict(COLUMN_LABELS_COMMON)
SALES_TABLE_LABELS["result_status"] = "Sales Result"
OPERATION_TABLE_LABELS = dict(COLUMN_LABELS_COMMON)
OPERATION_TABLE_LABELS["result_status"] = "Order Result"


def _display_frame(frame: pd.DataFrame, present_columns: list[str], rows: list[dict]) -> pd.DataFrame:
    display = frame[present_columns].copy()
    if "review_this_week" in display.columns:
        display["review_this_week"] = display["review_this_week"].map(lambda v: "Yes" if bool(v) else "No")
    is_operation = any((r.get("entity_type") == "Operation" or r.get("order_no")) for r in rows)
    label_map = OPERATION_TABLE_LABELS if is_operation else SALES_TABLE_LABELS
    display = display.rename(columns={c: label_map.get(c, c.replace("_", " ").title()) for c in display.columns})
    return display

OPERATION_DETAIL_FIELDS = [
    ("Project ID", "project_id"),
    ("Linked Project", "linked_project_name"),
    ("Main Issue", "main_issue"),
    ("Need From Meeting", "need_from_meeting"),
    ("Next Step", "next_step_summary"),
    ("Next Step Owner", "next_step_owner"),
    ("Days Since Status", "days_since_status_update"),
    ("Days Since Review", "days_since_review"),
]



def open_detail_page(record_type: str, record_id: str) -> None:
    set_selected_detail(record_type, record_id)
    try:
        st.switch_page("pages/4_Project_Detail.py")
    except Exception:
        st.session_state["selected_detail_type"] = record_type
        st.session_state["selected_detail_id"] = record_id
        st.info("Selected record stored. Open Project / Order Detail from the sidebar.")



def _jump_records(rows: list[dict]) -> list[tuple[str, str, str]]:
    options: list[tuple[str, str, str]] = []
    for row in rows:
        entity_type = row.get("entity_type") or ("Operation" if row.get("order_no") and not row.get("project_name") else "Sales")
        entity_id = row.get("entity_id") or row.get("order_no") or row.get("project_id")
        if not entity_id:
            continue
        label_title = row.get("display_title") or row.get("project_name") or row.get("linked_project_name") or "-"
        options.append((f"{entity_type} | {entity_id} — {label_title}", entity_type, entity_id))
    return options



def render_project_table(rows: list[dict], columns: list[str], empty_message: str = "No records", enable_jump: bool = True) -> None:
    if not rows:
        st.info(empty_message)
        return
    frame = pd.DataFrame(rows)
    present_columns = [col for col in columns if col in frame.columns]
    st.dataframe(_display_frame(frame, present_columns, rows), use_container_width=True, hide_index=True)

    jump_options = _jump_records(rows) if enable_jump else []
    if jump_options:
        with st.expander("Open Project / Order Detail from this table"):
            labels = [label for label, _, _ in jump_options]
            selected_label = st.selectbox("Jump to Project / Order Detail", options=[""] + labels, key=f"table_jump_{len(rows)}_{'_'.join(present_columns[:2])}")
            if selected_label:
                record_type, record_id = next((rtype, rid) for label, rtype, rid in jump_options if label == selected_label)
                if st.button("Open Detail", key=f"open_table_detail_{record_type}_{record_id}", type="primary"):
                    open_detail_page(record_type, record_id)



def render_board_cards(
    rows: list[dict],
    entity_type: str,
    operator: str,
    source_page: str,
    empty_message: str = "No records",
) -> None:
    if not rows:
        st.info(empty_message)
        return

    detail_fields = SALES_DETAIL_FIELDS if entity_type == "Sales" else OPERATION_DETAIL_FIELDS
    for row in rows:
        entity_id = row.get("entity_id") or row.get("display_id")
        title = row.get("display_title") or row.get("project_name") or row.get("linked_project_name") or "-"
        subtitle_left = f"Client Code: {row.get('client_code') or '-'}"
        subtitle_right = f"Current Owner: {row.get('current_owner') or '-'}"

        st.markdown("<div class='zt-card'>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='zt-card-title'>{entity_id} — {title}</div>"
            f"<div class='zt-card-subtitle'>{subtitle_left} | {subtitle_right}</div>",
            unsafe_allow_html=True,
        )
        render_badges(
            phase=row.get("phase"),
            health=row.get("health_status"),
            result=row.get("result_status"),
            pattern=bool(row.get("pattern_flag")),
        )

        st.markdown("<div class='zt-section-kicker'>Current card snapshot</div>", unsafe_allow_html=True)
        top_cols = st.columns(4)
        top_cols[0].metric("Next Step Owner", row.get("next_step_owner") or "-")
        top_cols[1].metric("Last Event", row.get("last_event") or "-")
        top_cols[2].metric("Days Since Status", row.get("days_since_status_update") if row.get("days_since_status_update") is not None else "-")
        top_cols[3].metric("Days Since Review", row.get("days_since_review") if row.get("days_since_review") is not None else "-")

        detail_cols = st.columns(2)
        left_fields = detail_fields[:4]
        right_fields = detail_fields[4:]
        for label, key in left_fields:
            detail_cols[0].write(f"**{label}:** {row.get(key) or '-'}")
        for label, key in right_fields:
            detail_cols[1].write(f"**{label}:** {row.get(key) or '-'}")

        if row.get("health_status") in {"Need Decision", "Blocked", "Delayed", "Need Alignment"}:
            st.markdown(
                f"<div class='zt-soft-note'><b>Attention:</b> This item is currently marked as <b>{row.get('health_status')}</b>.</div>",
                unsafe_allow_html=True,
            )

        st.markdown("<div class='zt-action-zone'>", unsafe_allow_html=True)
        nav_col, helper_col = st.columns([1, 4])
        if nav_col.button("Open Detail", key=f"open_detail_{entity_type}_{entity_id}", type="primary"):
            open_detail_page(entity_type, entity_id)
        helper_col.caption("Open Project / Order Detail for full history, richer editing and lower-frequency actions.")

        render_board_action_buttons(
            entity_type=entity_type,
            entity_id=entity_id,
            operator=operator,
            source_page=source_page,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
