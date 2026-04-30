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

MULTI_VALUE_FIELDS = {
    "support_from",
    "next_step_support",
    "need_alignment_with",
    "waiting_for_person",
}

STATUS_RELATED_FIELDS = {
    "phase",
    "health_status",
    "result_status",
    "quote_round",
    "sample_round",
    "doc_round",
    "test_round",
}


logger = get_logger("detail_service")


class DetailUpdateError(Exception):
    pass



def _record_as_dict(entity_type: str, entity_id: str) -> dict[str, Any]:
    row = get_sales_project(entity_id) if entity_type == "Sales" else get_operation_order(entity_id)
    if row is None:
        raise DetailUpdateError(f"{entity_type} record not found: {entity_id}")
    return dict(row)



def parse_multi_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(part).strip() for part in value if str(part).strip()]
    return []



def _normalize_value(field: str, value: Any) -> Any:
    if field in MULTI_VALUE_FIELDS:
        return ", ".join(parse_multi_value(value))
    if isinstance(value, bool):
        return int(value)
    return value



def _same_value(field: str, old: Any, new: Any) -> bool:
    old_n = _normalize_value(field, old)
    new_n = _normalize_value(field, new)
    return old_n == new_n



def _apply_update(
    entity_type: str,
    entity_id: str,
    updates: dict[str, Any],
    operator: str,
    source_page: str,
    event_type: str,
) -> dict[str, Any]:
    record = _record_as_dict(entity_type, entity_id)
    filtered_updates: dict[str, Any] = {}
    changed_fields: list[str] = []

    for field, value in updates.items():
        normalized = _normalize_value(field, value)
        if not _same_value(field, record.get(field), normalized):
            filtered_updates[field] = normalized
            changed_fields.append(field)

    if not filtered_updates:
        return {"updated": False, "message": "No new changes compared with the saved values."}

    now = now_iso()
    filtered_updates["last_event"] = event_type
    filtered_updates["last_updated_by"] = operator
    if any(field in STATUS_RELATED_FIELDS for field in changed_fields):
        filtered_updates["last_status_update_at"] = now

    if entity_type == "Sales":
        update_sales_project_fields(entity_id, filtered_updates)
    else:
        update_operation_order_fields(entity_id, filtered_updates)

    updated_record = _record_as_dict(entity_type, entity_id)
    logger.info("Detail update: %s | entity_type=%s | entity_id=%s | operator=%s | fields=%s", event_type, entity_type, entity_id, operator, ", ".join(changed_fields))

    insert_event_log(
        {
            "event_id": new_event_id(),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": updated_record.get("project_id") if entity_type == "Operation" else entity_id,
            "order_no": entity_id if entity_type == "Operation" else None,
            "event_time": now,
            "event_type": event_type,
            "event_group": "Edit",
            "old_phase": record.get("phase"),
            "new_phase": updated_record.get("phase"),
            "old_health": record.get("health_status"),
            "new_health": updated_record.get("health_status"),
            "old_result": record.get("result_status"),
            "new_result": updated_record.get("result_status"),
            "round_change": None,
            "operator": operator,
            "event_note": f"Changed fields: {', '.join(changed_fields)}",
            "source_page": source_page,
        }
    )

    return {
        "updated": True,
        "message": f"Updated {len(changed_fields)} field(s).",
        "changed_fields": changed_fields,
        "record": updated_record,
    }



def update_detail_fields(entity_type: str, entity_id: str, updates: dict[str, Any], operator: str) -> dict[str, Any]:
    return _apply_update(
        entity_type=entity_type,
        entity_id=entity_id,
        updates=updates,
        operator=operator,
        source_page="Project Detail",
        event_type="Detail Updated",
    )



def update_request_layer_fields(entity_type: str, entity_id: str, updates: dict[str, Any], operator: str) -> dict[str, Any]:
    return _apply_update(
        entity_type=entity_type,
        entity_id=entity_id,
        updates=updates,
        operator=operator,
        source_page="Project Detail",
        event_type="Request Layer Updated",
    )



def update_meeting_fields(
    entity_type: str,
    entity_id: str,
    updates: dict[str, Any],
    operator: str,
    source_page: str = "Project Detail",
    event_type: str = "Meeting Fields Updated",
) -> dict[str, Any]:
    return _apply_update(
        entity_type=entity_type,
        entity_id=entity_id,
        updates=updates,
        operator=operator,
        source_page=source_page,
        event_type=event_type,
    )


def set_record_archive_status(entity_type: str, entity_id: str, archived: bool, operator: str) -> dict[str, Any]:
    """Archive or restore a record without physically deleting it."""
    return _apply_update(
        entity_type=entity_type,
        entity_id=entity_id,
        updates={"is_archived": int(bool(archived))},
        operator=operator,
        source_page="Project Detail",
        event_type="Record Archived" if archived else "Record Restored",
    )
