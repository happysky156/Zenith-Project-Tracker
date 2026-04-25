from __future__ import annotations

import streamlit as st

from core.dictionaries import OPERATION_BOARD_ACTIONS, SALES_BOARD_ACTIONS
from services.button_service import ButtonActionError, apply_button_action


ACTION_LABELS = {
    "Quote Sent": "Quote Sent",
    "Quote Revised": "Quote Revised",
    "Sample Sent": "Sample Sent",
    "Sample Feedback NG": "Sample NG",
    "Waiting Client": "Waiting Client",
    "Waiting Supplier": "Waiting Supplier",
    "Waiting Internal": "Waiting Internal",
    "Need Decision": "Need Decision",
    "Need Alignment": "Need Alignment",
    "Close Won": "Close Won",
    "Close Lost": "Close Lost",
    "Add to This Week Meeting": "Push To Meeting",
    "Prepayment Received": "Prepayment In",
    "Production Started": "Production Started",
    "Delay Confirmed": "Delay Confirmed",
    "Partial Shipment": "Partial Shipment",
    "Complete Shipment": "Complete Shipment",
    "Shipment Paid": "Shipment Paid",
    "Mark Blocked": "Mark Blocked",
}

PRIMARY_ACTIONS = {
    "Quote Sent",
    "Sample Sent",
    "Need Decision",
    "Close Won",
    "Prepayment Received",
    "Production Started",
    "Shipment Paid",
}

ACTION_GROUPS = {
    "Sales": [
        (
            "Progress update",
            "Normal sales movement: quotation and sample status.",
            ["Quote Sent", "Quote Revised", "Sample Sent", "Sample Feedback NG"],
        ),
        (
            "Waiting / risk signal",
            "Use these when the project needs attention before it can move forward.",
            ["Waiting Client", "Waiting Supplier", "Need Decision", "Need Alignment"],
        ),
        (
            "Result / meeting",
            "Close the sales result or push the item into this week’s meeting review.",
            ["Close Won", "Close Lost", "Add to This Week Meeting"],
        ),
    ],
    "Operation": [
        (
            "Execution progress",
            "Normal order movement: payment, production and shipment status.",
            ["Prepayment Received", "Production Started", "Partial Shipment", "Complete Shipment", "Shipment Paid"],
        ),
        (
            "Waiting / risk signal",
            "Use these when the order needs supplier action, internal support or management attention.",
            ["Waiting Supplier", "Waiting Internal", "Delay Confirmed", "Mark Blocked", "Need Decision"],
        ),
        (
            "Meeting review",
            "Push the item into this week’s meeting review.",
            ["Add to This Week Meeting"],
        ),
    ],
}


def _get_actions(entity_type: str) -> list[str]:
    return SALES_BOARD_ACTIONS if entity_type == "Sales" else OPERATION_BOARD_ACTIONS


def _render_action_group(entity_type: str, entity_id: str, operator: str, source_page: str, title: str, note: str, group_actions: list[str], actions: list[str]) -> None:
    row_actions = [action for action in group_actions if action in actions]
    if not row_actions:
        return

    st.markdown(
        f"<div class='zt-action-group-head'><div class='zt-action-group-title'>{title}</div><div class='zt-action-group-note'>{note}</div></div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(len(row_actions))
    for col, action_name in zip(cols, row_actions):
        with col:
            if st.button(
                ACTION_LABELS.get(action_name, action_name),
                key=f"{source_page}_{entity_type}_{entity_id}_{action_name}",
                use_container_width=True,
                type="primary" if action_name in PRIMARY_ACTIONS else "secondary",
            ):
                try:
                    apply_button_action(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        action_name=action_name,
                        operator=operator,
                        source_page=source_page,
                    )
                    st.success(f"{entity_id}: {action_name}")
                    st.rerun()
                except ButtonActionError as exc:
                    st.error(str(exc))


def render_board_action_buttons(entity_type: str, entity_id: str, operator: str, source_page: str) -> None:
    actions = _get_actions(entity_type)
    grouped_actions = set()
    for title, note, group_actions in ACTION_GROUPS.get(entity_type, []):
        grouped_actions.update(group_actions)
        _render_action_group(entity_type, entity_id, operator, source_page, title, note, group_actions, actions)

    remaining_actions = [action for action in actions if action not in grouped_actions]
    if remaining_actions:
        _render_action_group(
            entity_type,
            entity_id,
            operator,
            source_page,
            "Other actions",
            "Additional status shortcuts kept from the original board logic.",
            remaining_actions,
            actions,
        )
