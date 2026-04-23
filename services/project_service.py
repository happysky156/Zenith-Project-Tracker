from __future__ import annotations

from typing import Any

from core.dictionaries import MEETING_POOL_HEALTH
from database.repositories import (
    get_linked_orders_for_project,
    get_operation_order,
    get_sales_project,
    list_event_logs,
    list_meeting_snapshots,
    list_operation_order_ids,
    list_operation_orders,
    list_sales_project_ids,
    list_sales_projects,
)
from utils.dates import days_since_text

HIGH_ATTENTION_HEALTH = {"Need Decision", "Need Alignment", "Blocked", "Delayed", "Due Soon"}
SALES_CLOSED_RESULTS = {"Won", "Lost"}
OPERATION_CLOSED_RESULTS = {"Paid Closed", "Cancelled"}



def _decorate_common(row: dict[str, Any], entity_type: str) -> dict[str, Any]:
    item = dict(row)
    item["entity_type"] = entity_type
    item["entity_id"] = row.get("project_id") if entity_type == "Sales" else row.get("order_no")
    item["display_id"] = item["entity_id"]
    item["client_label"] = item.get("client_code") or "-"
    item["days_since_status_update"] = days_since_text(item.get("last_status_update_at"))
    item["days_since_review"] = days_since_text(item.get("last_reviewed_at"))
    if entity_type == "Sales":
        item["display_title"] = item.get("project_name") or item.get("project_id")
        linked_orders = item.get("linked_orders") or ""
        item["linked_orders_list"] = [part.strip() for part in linked_orders.split(",") if part.strip()]
    else:
        item["display_title"] = item.get("linked_project_name") or item.get("project_id") or "(Unlinked)"
    return item



def _is_active_sales(row: dict[str, Any]) -> bool:
    return not (
        (row.get("phase") == "Closed")
        or (row.get("health_status") == "Done")
        or (row.get("result_status") in SALES_CLOSED_RESULTS)
    )



def _is_active_operation(row: dict[str, Any]) -> bool:
    return not (
        (row.get("phase") == "Closure")
        or (row.get("health_status") == "Done")
        or (row.get("result_status") in OPERATION_CLOSED_RESULTS)
    )



def get_dashboard_metrics() -> dict[str, int]:
    sales = [_decorate_common(r, "Sales") for r in list_sales_projects()]
    operations = [_decorate_common(r, "Operation") for r in list_operation_orders()]
    meeting = [
        r
        for r in (sales + operations)
        if r.get("health_status") in MEETING_POOL_HEALTH or bool(r.get("review_this_week"))
    ]
    need_decision = sum(
        1 for r in (sales + operations) if r.get("health_status") == "Need Decision" or r.get("request_type") == "Decision"
    )
    return {
        "sales_projects": len(sales),
        "operation_orders": len(operations),
        "all_items": len(sales) + len(operations),
        "meeting_pool": len(meeting),
        "active_sales": sum(1 for r in sales if _is_active_sales(r)),
        "active_operations": sum(1 for r in operations if _is_active_operation(r)),
        "need_decision": need_decision,
    }



def list_board_projects(record_type: str) -> list[dict[str, Any]]:
    if record_type == "Sales":
        return [_decorate_common(r, "Sales") for r in list_sales_projects()]
    return [_decorate_common(r, "Operation") for r in list_operation_orders()]



def apply_board_filters(rows: list[dict[str, Any]], filters: dict[str, object], record_type: str) -> list[dict[str, Any]]:
    filtered = rows
    owner = (filters.get("owner") or "").strip().lower()
    phase = (filters.get("phase") or "").strip().lower()
    health = (filters.get("health") or "").strip().lower()
    priority = (filters.get("priority") or "").strip().lower()
    search = (filters.get("search") or "").strip().lower()
    review_only = bool(filters.get("review_only"))
    meeting_pool_only = bool(filters.get("meeting_pool_only"))
    high_attention_only = bool(filters.get("high_attention_only"))

    if owner:
        filtered = [r for r in filtered if (r.get("current_owner") or "").lower() == owner]
    if phase:
        filtered = [r for r in filtered if (r.get("phase") or "").lower() == phase]
    if health:
        filtered = [r for r in filtered if (r.get("health_status") or "").lower() == health]
    if priority:
        filtered = [r for r in filtered if (r.get("priority") or "").lower() == priority]
    if review_only:
        filtered = [r for r in filtered if bool(r.get("review_this_week"))]
    if meeting_pool_only:
        filtered = [r for r in filtered if (r.get("health_status") in MEETING_POOL_HEALTH) or bool(r.get("review_this_week"))]
    if high_attention_only:
        filtered = [r for r in filtered if (r.get("health_status") in HIGH_ATTENTION_HEALTH) or bool(r.get("pattern_flag"))]
    if search:
        search_fields = [
            "project_id",
            "project_name",
            "order_no",
            "linked_project_name",
            "client_code",
            "current_owner",
            "next_step_owner",
            "client_waiting_for",
            "main_issue",
            "block_point",
            "next_step_summary",
            "meeting_note",
            "last_event",
            "display_title",
            "display_id",
            "linked_orders",
        ]
        filtered = [
            r for r in filtered
            if any(search in str(r.get(field) or "").lower() for field in search_fields)
        ]
    return filtered



def list_detail_ids(record_type: str) -> list[str]:
    return list_sales_project_ids() if record_type == "Sales" else list_operation_order_ids()



def get_record_detail(record_type: str, record_id: str) -> dict[str, Any] | None:
    row = get_sales_project(record_id) if record_type == "Sales" else get_operation_order(record_id)
    if row is None:
        return None
    detail = _decorate_common(row, record_type)
    if record_type == "Sales":
        detail["linked_orders_rows"] = get_linked_orders_for_project(record_id)
    return detail



def get_record_timeline(record_type: str, record_id: str) -> list[dict[str, Any]]:
    return list_event_logs(record_type, record_id)



def get_record_snapshots(record_type: str, record_id: str) -> list[dict[str, Any]]:
    return list_meeting_snapshots(record_type, record_id)



def get_meeting_pool() -> list[dict[str, Any]]:
    rows = list_board_projects("Sales") + list_board_projects("Operation")
    meeting_rows = [
        dict(r)
        for r in rows
        if (r.get("health_status") in MEETING_POOL_HEALTH) or bool(r.get("review_this_week"))
    ]
    priority_order = {
        "Need Decision": 1,
        "Blocked": 2,
        "Delayed": 3,
        "Due Soon": 4,
        "Need Alignment": 5,
    }
    meeting_rows.sort(
        key=lambda r: (
            priority_order.get(r.get("health_status"), 99),
            str(r.get("target_date") or "9999-12-31"),
            str(r.get("display_id") or ""),
        )
    )
    return meeting_rows
