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


def _clean_status(value: object) -> str:
    return str(value or "").strip()


def _flag_true(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "on"}


def _action_matches_current_state(entity_type: str, row: dict | None, action_name: str) -> bool:
    """Return True only when this shortcut represents the current stored state.

    Management rule:
    - White button = available action.
    - Red button = current recorded state only.
    - Red is not used to mark a shortcut as generally important.
    - For closed Sales results, only the relevant Close Won / Close Lost button
      is highlighted; progress and risk shortcuts stay neutral.
    """
    if not row:
        return False

    phase = _clean_status(row.get("phase"))
    health = _clean_status(row.get("health_status"))
    result = _clean_status(row.get("result_status"))
    review_this_week = _flag_true(row.get("review_this_week"))

    if action_name == "Add to This Week Meeting":
        return review_this_week

    if entity_type == "Sales":
        # Once a sales project is closed won/lost, the result is the only status
        # that should be highlighted. Old quotation/sample/risk actions should
        # not remain visually active.
        if result == "Won":
            return action_name == "Close Won"
        if result == "Lost":
            return action_name == "Close Lost"

        quote_round = int(row.get("quote_round") or 0)
        if action_name == "Quote Sent":
            return phase == "Quotation" and quote_round <= 1
        if action_name == "Quote Revised":
            return phase == "Quotation" and quote_round > 1
        if action_name == "Sample Sent":
            return phase == "Sampling" and health != "Need Alignment"
        if action_name == "Sample Feedback NG":
            return phase == "Sampling" and health == "Need Alignment"
        if action_name == "Waiting Client":
            return health == "Waiting Client"
        if action_name == "Waiting Supplier":
            return health == "Waiting Supplier"
        if action_name == "Need Decision":
            return health == "Need Decision"
        if action_name == "Need Alignment":
            return health == "Need Alignment"
        return False

    if entity_type == "Operation":
        # Paid Closed is the final operation state. Only Shipment Paid should be
        # highlighted in that situation.
        if result == "Paid Closed":
            return action_name == "Shipment Paid"

        if action_name == "Prepayment Received":
            return phase == "Payment"
        if action_name == "Production Started":
            return phase == "Execution"
        if action_name == "Partial Shipment":
            return result == "Partial Shipped"
        if action_name == "Complete Shipment":
            return result == "Complete Shipped"
        if action_name == "Shipment Paid":
            return phase == "Closure"
        if action_name == "Waiting Supplier":
            return health == "Waiting Supplier"
        if action_name == "Waiting Internal":
            return health == "Waiting Internal"
        if action_name == "Delay Confirmed":
            return health == "Delayed"
        if action_name == "Mark Blocked":
            return health == "Blocked"
        if action_name == "Need Decision":
            return health == "Need Decision"
        return False

    return False


def _get_actions(entity_type: str) -> list[str]:
    return SALES_BOARD_ACTIONS if entity_type == "Sales" else OPERATION_BOARD_ACTIONS


def _render_action_group(
    entity_type: str,
    entity_id: str,
    operator: str,
    source_page: str,
    title: str,
    note: str,
    group_actions: list[str],
    actions: list[str],
    current_row: dict | None = None,
) -> None:
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
            is_current_status = _action_matches_current_state(entity_type, current_row, action_name)
            if st.button(
                ACTION_LABELS.get(action_name, action_name),
                key=f"{source_page}_{entity_type}_{entity_id}_{action_name}",
                use_container_width=True,
                type="primary" if is_current_status else "secondary",
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


def render_board_action_buttons(
    entity_type: str,
    entity_id: str,
    operator: str,
    source_page: str,
    current_row: dict | None = None,
) -> None:
    actions = _get_actions(entity_type)
    grouped_actions = set()
    for title, note, group_actions in ACTION_GROUPS.get(entity_type, []):
        grouped_actions.update(group_actions)
        _render_action_group(
            entity_type,
            entity_id,
            operator,
            source_page,
            title,
            note,
            group_actions,
            actions,
            current_row=current_row,
        )

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
            current_row=current_row,
        )
