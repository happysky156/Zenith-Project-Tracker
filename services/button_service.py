from __future__ import annotations

from typing import Any

from database.repositories import (
    get_operation_order,
    get_sales_project,
    insert_event_log,
    update_operation_order_fields,
    update_sales_project_fields,
)
from utils.dates import now_iso
from utils.ids import new_event_id
from utils.logger import get_logger


logger = get_logger("button_service")


class ButtonActionError(Exception):
    pass


STATUS_ACTIONS = {
    "Quote Sent",
    "Quote Revised",
    "Sample Sent",
    "Sample Feedback NG",
    "Waiting Client",
    "Waiting Supplier",
    "Waiting Internal",
    "Need Decision",
    "Need Alignment",
    "Close Won",
    "Close Lost",
    "Prepayment Received",
    "Production Started",
    "Delay Confirmed",
    "Partial Shipment",
    "Complete Shipment",
    "Shipment Paid",
    "Mark Blocked",
}



def _record_as_dict(entity_type: str, entity_id: str) -> dict[str, Any]:
    row = get_sales_project(entity_id) if entity_type == "Sales" else get_operation_order(entity_id)
    if row is None:
        raise ButtonActionError(f"{entity_type} record not found: {entity_id}")
    return dict(row)



def _build_sales_updates(project: dict[str, Any], action_name: str) -> tuple[dict[str, Any], str | None, str]:
    updates: dict[str, Any] = {}
    round_change: str | None = None
    event_group = "Event"

    if action_name == "Quote Sent":
        updates["phase"] = "Quotation"
        if int(project.get("quote_round") or 0) == 0:
            updates["quote_round"] = 1
            round_change = "quote_round +1"
    elif action_name == "Quote Revised":
        updates["phase"] = "Quotation"
        updates["quote_round"] = int(project.get("quote_round") or 0) + 1
        round_change = "quote_round +1"
    elif action_name == "Sample Sent":
        updates["phase"] = "Sampling"
        if int(project.get("sample_round") or 0) == 0:
            updates["sample_round"] = 1
            round_change = "sample_round +1"
    elif action_name == "Sample Feedback NG":
        updates["phase"] = "Sampling"
        updates["health_status"] = "Need Alignment"
        updates["request_type"] = "Alignment"
        updates["review_this_week"] = 1
    elif action_name == "Waiting Client":
        updates["health_status"] = "Waiting Client"
        event_group = "Health"
    elif action_name == "Waiting Supplier":
        updates["health_status"] = "Waiting Supplier"
        event_group = "Health"
    elif action_name == "Waiting Internal":
        updates["health_status"] = "Waiting Internal"
        event_group = "Health"
    elif action_name == "Need Decision":
        updates["health_status"] = "Need Decision"
        updates["request_type"] = "Decision"
        updates["need_decision_from"] = project.get("need_decision_from") or "Ehab"
        updates["review_this_week"] = 1
        event_group = "Health"
    elif action_name == "Need Alignment":
        updates["health_status"] = "Need Alignment"
        updates["request_type"] = "Alignment"
        updates["review_this_week"] = 1
        event_group = "Health"
    elif action_name == "Close Won":
        updates["phase"] = "Closed"
        updates["result_status"] = "Won"
        updates["health_status"] = "Done"
        updates["review_this_week"] = 0
        event_group = "Result"
    elif action_name == "Close Lost":
        updates["phase"] = "Closed"
        updates["result_status"] = "Lost"
        updates["health_status"] = "Done"
        updates["review_this_week"] = 0
        event_group = "Result"
    elif action_name == "Add to This Week Meeting":
        updates["review_this_week"] = 1
        event_group = "Meeting"
    else:
        raise ButtonActionError(f"Unsupported sales action: {action_name}")

    return updates, round_change, event_group



def _build_operation_updates(order: dict[str, Any], action_name: str) -> tuple[dict[str, Any], str | None, str]:
    updates: dict[str, Any] = {}
    event_group = "Event"

    if action_name == "Prepayment Received":
        updates["phase"] = "Payment"
    elif action_name == "Production Started":
        updates["phase"] = "Execution"
        updates["health_status"] = "On Track"
    elif action_name == "Delay Confirmed":
        updates["health_status"] = "Delayed"
        updates["review_this_week"] = 1
        event_group = "Health"
    elif action_name == "Partial Shipment":
        updates["phase"] = "Shipment"
        updates["result_status"] = "Partial Shipped"
        event_group = "Result"
    elif action_name == "Complete Shipment":
        updates["phase"] = "Shipment"
        updates["result_status"] = "Complete Shipped"
        event_group = "Result"
    elif action_name == "Shipment Paid":
        updates["phase"] = "Closure"
        updates["result_status"] = "Paid Closed"
        updates["health_status"] = "Done"
        updates["review_this_week"] = 0
        event_group = "Result"
    elif action_name == "Waiting Supplier":
        updates["health_status"] = "Waiting Supplier"
        event_group = "Health"
    elif action_name == "Waiting Internal":
        updates["health_status"] = "Waiting Internal"
        event_group = "Health"
    elif action_name == "Need Decision":
        updates["health_status"] = "Need Decision"
        updates["request_type"] = "Decision"
        updates["need_decision_from"] = order.get("need_decision_from") or "Ehab"
        updates["review_this_week"] = 1
        event_group = "Health"
    elif action_name == "Mark Blocked":
        updates["health_status"] = "Blocked"
        updates["review_this_week"] = 1
        event_group = "Health"
    elif action_name == "Add to This Week Meeting":
        updates["review_this_week"] = 1
        event_group = "Meeting"
    else:
        raise ButtonActionError(f"Unsupported operation action: {action_name}")

    return updates, None, event_group



def apply_button_action(
    entity_type: str,
    entity_id: str,
    action_name: str,
    operator: str,
    source_page: str,
    event_note: str | None = None,
) -> dict[str, Any]:
    record = _record_as_dict(entity_type, entity_id)
    if entity_type == "Sales":
        updates, round_change, event_group = _build_sales_updates(record, action_name)
    else:
        updates, round_change, event_group = _build_operation_updates(record, action_name)

    now = now_iso()
    updates["last_event"] = action_name
    updates["last_updated_by"] = operator
    if action_name in STATUS_ACTIONS:
        updates["last_status_update_at"] = now

    if entity_type == "Sales":
        update_sales_project_fields(entity_id, updates)
    else:
        update_operation_order_fields(entity_id, updates)

    new_phase = updates.get("phase", record.get("phase"))
    new_health = updates.get("health_status", record.get("health_status"))
    new_result = updates.get("result_status", record.get("result_status"))

    logger.info("Button action: %s | entity_type=%s | entity_id=%s | operator=%s", action_name, entity_type, entity_id, operator)

    insert_event_log(
        {
            "event_id": new_event_id(),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": record.get("project_id") if entity_type == "Operation" else entity_id,
            "order_no": entity_id if entity_type == "Operation" else None,
            "event_time": now,
            "event_type": action_name,
            "event_group": event_group,
            "old_phase": record.get("phase"),
            "new_phase": new_phase,
            "old_health": record.get("health_status"),
            "new_health": new_health,
            "old_result": record.get("result_status"),
            "new_result": new_result,
            "round_change": round_change,
            "operator": operator,
            "event_note": event_note,
            "source_page": source_page,
        }
    )

    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action_name": action_name,
        "new_phase": new_phase,
        "new_health": new_health,
        "new_result": new_result,
        "round_change": round_change,
    }
