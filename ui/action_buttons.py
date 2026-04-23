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



def _get_actions(entity_type: str) -> list[str]:
    return SALES_BOARD_ACTIONS if entity_type == "Sales" else OPERATION_BOARD_ACTIONS



def render_board_action_buttons(entity_type: str, entity_id: str, operator: str, source_page: str) -> None:
    actions = _get_actions(entity_type)
    for row_actions in [actions[:6], actions[6:]]:
        if not row_actions:
            continue
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
