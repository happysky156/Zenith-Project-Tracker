from __future__ import annotations

from typing import Any

from database.repositories import get_operation_order, get_sales_project
from services.detail_service import update_meeting_fields
from services.ai_meeting_service import clean_text


AI_DRAFT_TO_DB_FIELD_MAP = {
    "current_progress": "progress_summary",
    "main_issue": "main_issue",
    "blocked_at": "block_point",
    "waiting_for_what": "waiting_for_text",
    "need_from_meeting": "need_from_meeting",
    "next_step": "next_step_summary",
    "next_step_owner": "next_step_owner",
    "target_date": "target_date",
    "meeting_note": "meeting_note",
}

EMPTY_MARKERS = {"", "-", "n/a", "na", "none", "null"}


class AIMeetingApplyError(Exception):
    pass


def _normalise_entity(selected_project: dict[str, Any]) -> tuple[str, str]:
    entity_type = clean_text(selected_project.get("record_type"))
    entity_id = clean_text(selected_project.get("entity_id"))

    if entity_type not in {"Sales", "Operation"}:
        raise AIMeetingApplyError(f"Unsupported record type: {entity_type or '-'}")

    if not entity_id:
        if entity_type == "Sales":
            entity_id = clean_text(selected_project.get("project_id"))
        else:
            entity_id = clean_text(selected_project.get("order_no"))

    if not entity_id:
        raise AIMeetingApplyError("Missing entity_id. Please re-select the project/order before confirming.")

    return entity_type, entity_id


def _record_exists(entity_type: str, entity_id: str) -> bool:
    if entity_type == "Sales":
        return get_sales_project(entity_id) is not None
    return get_operation_order(entity_id) is not None


def _has_update_value(value: Any) -> bool:
    text = clean_text(value)
    return text.lower() not in EMPTY_MARKERS


def _review_yes(value: Any) -> bool:
    text = clean_text(value).lower()
    return text in {"yes", "y", "true", "1"}


def build_ai_meeting_updates(draft: dict[str, Any]) -> dict[str, Any]:
    """Convert the AI draft JSON fields into the existing database column names.

    Safety rule for version 1:
    - Empty AI fields do NOT clear existing database values.
    - review_this_week is only set when AI says Yes. AI "No" does not remove an item from review.
    """
    updates: dict[str, Any] = {}

    for ai_field, db_field in AI_DRAFT_TO_DB_FIELD_MAP.items():
        value = draft.get(ai_field)
        if _has_update_value(value):
            updates[db_field] = clean_text(value)

    if _review_yes(draft.get("review_this_week")):
        updates["review_this_week"] = 1

    if _has_update_value(draft.get("next_step")):
        # Keep meeting follow-up visible in Meeting Mode / Dashboard follow-up logic.
        updates["followup_status"] = "Open"

    return updates


def apply_ai_meeting_draft(
    *,
    selected_project: dict[str, Any],
    draft: dict[str, Any],
    operator: str,
) -> dict[str, Any]:
    """Apply a confirmed AI draft to Sales/Operation Meeting Prep fields.

    This reuses the existing Project / Order Detail update pathway, so the normal
    data cache clearing and event timeline writing are kept consistent.
    """
    entity_type, entity_id = _normalise_entity(selected_project)

    if not _record_exists(entity_type, entity_id):
        raise AIMeetingApplyError(f"{entity_type} record not found: {entity_id}")

    updates = build_ai_meeting_updates(draft)
    if not updates:
        return {
            "updated": False,
            "message": "AI draft saved, but no non-empty field was available to apply.",
            "changed_fields": [],
            "entity_type": entity_type,
            "entity_id": entity_id,
            "updates": {},
        }

    result = update_meeting_fields(
        entity_type,
        entity_id,
        updates,
        operator=operator,
        source_page="AI Meeting Assistant",
        event_type="AI Meeting Draft Applied",
    )
    result["entity_type"] = entity_type
    result["entity_id"] = entity_id
    result["updates"] = updates
    return result
