from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from core.state import set_selected_detail
from ui.action_buttons import render_board_action_buttons
from ui.theme import render_badges
from utils.options import sorted_dropdown_options


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
    "sales_revenue": "Sales Revenue (USD)",
    "estimated_revenue": "Estimated Sales Revenue (USD)",
    "supplier_cost": "Supplier Cost (USD)",
    "estimated_supplier_cost": "Estimated Supplier Cost (USD)",
    "extra_cost": "Extra Cost (USD)",
    "estimated_extra_cost": "Estimated Extra Cost (USD)",
    "gross_profit": "Gross Profit (USD)",
    "estimated_gp": "Estimated Gross Profit (USD)",
    "gross_profit_percent": "Gross Profit %",
    "estimated_gp_percent": "Estimated GP %",
    "client_unit_price": "Client Unit Price (USD)",
    "supplier_unit_cost": "Supplier Unit Cost (USD)",
    "cost_amount": "Cost Amount (USD)",
    "project_id": "Project ID",
    "project_name": "Project Name",
    "client_code": "Client Code",
    "linked_order_count": "Linked Order Count",
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
    "is_archived": "Archived",
    "archive_status": "Archive Status",
    "inherited_order_archived": "Order Archived",
    "order_no": "Order No",
    "linked_project_name": "Project Name",
    "result_status": "Result",
    "waiting_for_text": "Waiting For What",
    "need_from_meeting": "Need From Meeting",
}

SALES_TABLE_LABELS = dict(COLUMN_LABELS_COMMON)
SALES_TABLE_LABELS["result_status"] = "Sales Result"

OPERATION_TABLE_LABELS = dict(COLUMN_LABELS_COMMON)
OPERATION_TABLE_LABELS["result_status"] = "Order Result"


OPERATION_DETAIL_FIELDS = [
    ("Waiting For What", "waiting_for_text"),
    ("Main Issue", "main_issue"),
    ("Need From Meeting", "need_from_meeting"),
    ("Next Step", "next_step_summary"),
    ("Next Step Owner", "next_step_owner"),
    ("Target Date", "target_date"),
    ("Days Since Status", "days_since_status_update"),
    ("Days Since Review", "days_since_review"),
]


def _display_frame(frame: pd.DataFrame, present_columns: list[str], rows: list[dict]) -> pd.DataFrame:
    display = frame[present_columns].copy()
    if "review_this_week" in display.columns:
        display["review_this_week"] = display["review_this_week"].map(lambda v: "Yes" if bool(v) else "No")
    if "is_archived" in display.columns:
        display["is_archived"] = display["is_archived"].map(lambda v: "Yes" if bool(v) else "No")
    if "inherited_order_archived" in display.columns:
        display["inherited_order_archived"] = display["inherited_order_archived"].map(lambda v: "Yes" if bool(v) else "No")

    is_operation = any((r.get("entity_type") == "Operation" or r.get("order_no")) for r in rows)
    label_map = OPERATION_TABLE_LABELS if is_operation else SALES_TABLE_LABELS
    display = display.rename(columns={c: label_map.get(c, c.replace("_", " ").title()) for c in display.columns})
    return display


def _clean(value: object) -> str:
    text = str(value or "-").strip() or "-"
    return escape(text).replace("\n", "<br>")


def _first_non_empty(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text and text.lower() not in {"-", "nan", "none", "null"}:
            return text
    return "-"


def _operation_project_name(row: dict) -> str:
    """Return the best available project name for an Operation order card."""
    return _first_non_empty(
        row.get("linked_project_name"),
        row.get("project_name"),
        row.get("display_title"),
    )


def _attention_class(health: str | None, pattern_flag: bool) -> str:
    health = health or ""
    if pattern_flag:
        return "Repeated Issue"
    if health in {"Need Decision", "Blocked", "Delayed", "Need Alignment", "Due Soon"}:
        return health
    if health in {"Waiting Client", "Waiting Supplier", "Waiting Internal"}:
        return health
    return "Normal Follow-up"


def _card_html(row: dict, entity_type: str, title: str, entity_id: str) -> str:
    is_sales = entity_type == "Sales"
    client = row.get("client_code") or "-"
    owner = row.get("current_owner") or "-"
    phase = row.get("phase") or "-"
    health = row.get("health_status") or "-"
    result = row.get("result_status") or "-"
    linked_orders = row.get("linked_orders") or "-"
    order_no = row.get("order_no") or entity_id or "-"
    project_name = _operation_project_name(row)

    if is_sales:
        identity_items = [
            ("Client", client),
            ("Owner", owner),
            ("Phase", phase),
            ("Health", health),
            ("Result", result),
            ("Linked Orders", linked_orders),
        ]
    else:
        identity_items = [
            ("Order No", order_no),
            ("Project Name", project_name),
            ("Project ID", row.get("project_id") or "-"),
            ("Client", client),
            ("Owner", owner),
            ("Phase", phase),
            ("Health", health),
            ("Result", result),
        ]

    identity_html = "".join(
        f"<div class='zt-card-meta-item'><span>{escape(label)}</span><strong>{_clean(value)}</strong></div>"
        for label, value in identity_items
    )

    snapshot_items = [
        ("Next Step Owner", row.get("next_step_owner") or "-"),
        ("Last Event", row.get("last_event") or "-"),
        ("Days Since Status", row.get("days_since_status_update") if row.get("days_since_status_update") is not None else "-"),
        ("Days Since Review", row.get("days_since_review") if row.get("days_since_review") is not None else "-"),
    ]
    snapshot_html = "".join(
        f"<div class='zt-snapshot-card'><div class='zt-snapshot-label'>{escape(label)}</div><div class='zt-snapshot-value'>{_clean(value)}</div></div>"
        for label, value in snapshot_items
    )

    detail_fields = SALES_DETAIL_FIELDS if is_sales else OPERATION_DETAIL_FIELDS
    detail_html = "".join(
        f"<div class='zt-detail-item'><div class='zt-detail-label'>{escape(label)}</div><div class='zt-detail-value'>{_clean(row.get(key))}</div></div>"
        for label, key in detail_fields
    )

    attention_label = _attention_class(row.get("health_status"), bool(row.get("pattern_flag")))
    attention_html = ""
    if attention_label != "Normal Follow-up":
        attention_html = (
            "<div class='zt-attention-strip'>"
            f"<b>Attention:</b> {escape(attention_label)}. Please check the next step, owner and timing before the weekly meeting."
            "</div>"
        )

    card_label = "Sales project card" if is_sales else "Operation order card"
    display_id_label = escape(entity_id or "-")
    title_sep = " — " if is_sales else " · Project: "

    return f"""
    <div class='zt-project-card-head zt-{entity_type.lower()}-card-head'>
        <div class='zt-project-card-topline'>
            <div>
                <div class='zt-project-eyebrow'>{escape(card_label)}</div>
                <div class='zt-project-title'><span>{display_id_label}</span>{title_sep}{_clean(title)}</div>
            </div>
            <div class='zt-project-focus-pill'>{escape(attention_label)}</div>
        </div>
        <div class='zt-card-meta-grid'>{identity_html}</div>
        <div class='zt-snapshot-grid'>{snapshot_html}</div>
        <div class='zt-detail-grid'>{detail_html}</div>
        {attention_html}
    </div>
    """


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

        if entity_type == "Operation":
            label_title = _operation_project_name(row)
        else:
            label_title = _first_non_empty(row.get("display_title"), row.get("project_name"), row.get("linked_project_name"))

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
            labels = sorted_dropdown_options([label for label, _, _ in jump_options], pinned=())
            selected_label = st.selectbox(
                "Jump to Project / Order Detail",
                options=[""] + labels,
                key=f"table_jump_{len(rows)}_{'_'.join(present_columns[:2])}",
            )
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

    for row in rows:
        entity_id = row.get("entity_id") or row.get("display_id")

        if entity_type == "Operation":
            title = _operation_project_name(row)
        else:
            title = _first_non_empty(
                row.get("display_title"),
                row.get("project_name"),
                row.get("linked_project_name"),
            )

        with st.container(border=True):
            st.markdown(_card_html(row, entity_type, str(title), str(entity_id or "-")), unsafe_allow_html=True)
            render_badges(
                phase=row.get("phase"),
                health=row.get("health_status"),
                result=row.get("result_status"),
                pattern=bool(row.get("pattern_flag")),
            )

            st.markdown(
                "<div class='zt-action-header'><div class='zt-action-header-title'>Quick actions</div>"
                "<div class='zt-action-header-note'>Use the buttons below to update this item without opening the full detail page.</div></div>",
                unsafe_allow_html=True,
            )
            nav_col, helper_col = st.columns([1, 4])
            if nav_col.button("Open Detail", key=f"open_detail_{entity_type}_{entity_id}", type="secondary"):
                open_detail_page(entity_type, entity_id)
            helper_col.caption("Open Project / Order Detail for full history, richer editing and lower-frequency actions.")

            render_board_action_buttons(
                entity_type=entity_type,
                entity_id=entity_id,
                operator=operator,
                source_page=source_page,
                current_row=row,
            )
