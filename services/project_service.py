from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from core.dictionaries import (
    MEETING_POOL_HEALTH,
    OPERATION_PHASES,
    SALES_PHASES,
)
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
SALES_PROGRESS_ORDER = ["On Progress", "Hold", "Won", "Lost"]
OPERATION_PROGRESS_ORDER = [
    "On Progress",
    "Hold",
    "Partial Shipped",
    "Complete Shipped",
    "Paid Closed",
    "Cancelled",
]
ATTENTION_ORDER = [
    "Blocked",
    "Delayed",
    "Due Soon",
    "Need Decision",
    "Need Alignment",
    "Waiting Client",
    "Waiting Supplier",
    "Waiting Internal",
]


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
    """Sales active logic for dashboard: Hold is still active; only Won/Lost are closed."""
    return (row.get("result_status") or "") not in SALES_CLOSED_RESULTS


def _is_active_operation(row: dict[str, Any]) -> bool:
    """Operation active logic for dashboard: Hold is still active; only Paid Closed/Cancelled are closed."""
    return (row.get("result_status") or "") not in OPERATION_CLOSED_RESULTS


def _sales_progress_label(row: dict[str, Any]) -> str:
    result = row.get("result_status") or ""
    health = row.get("health_status") or ""
    if result == "Won":
        return "Won"
    if result == "Lost":
        return "Lost"
    if health == "On Hold":
        return "Hold"
    return "On Progress"


def _operation_progress_label(row: dict[str, Any]) -> str:
    result = row.get("result_status") or ""
    health = row.get("health_status") or ""
    if result == "Paid Closed":
        return "Paid Closed"
    if result == "Cancelled":
        return "Cancelled"
    if health == "On Hold":
        return "Hold"
    if result == "Partial Shipped":
        return "Partial Shipped"
    if result == "Complete Shipped":
        return "Complete Shipped"
    return "On Progress"


def _ordered_counts(values: list[str], order: list[str]) -> dict[str, int]:
    counter = Counter(v for v in values if v)
    return {label: int(counter.get(label, 0)) for label in order}


def _field_counts(rows: list[dict[str, Any]], field: str, order: list[str]) -> dict[str, int]:
    return _ordered_counts([str(r.get(field) or "") for r in rows], order)


def _recent_updates(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    def sort_key(row: dict[str, Any]) -> str:
        return str(row.get("last_status_update_at") or row.get("last_reviewed_at") or row.get("created_at") or "")

    sorted_rows = sorted(rows, key=sort_key, reverse=True)
    recent: list[dict[str, Any]] = []
    for row in sorted_rows[:limit]:
        recent.append(
            {
                "Type": row.get("entity_type") or "-",
                "ID": row.get("display_id") or "-",
                "Client": row.get("client_code") or "-",
                "Phase": row.get("phase") or "-",
                "Health": row.get("health_status") or "-",
                "Result": row.get("result_status") or "-",
                "Owner": row.get("current_owner") or "-",
                "Next Step Owner": row.get("next_step_owner") or "-",
                "Target Date": row.get("target_date") or "-",
                "Last Event": row.get("last_event") or "-",
            }
        )
    return recent


def _attention_review_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rows used by Dashboard compact review table.

    Only records with Health Status included in the Attention Summary are listed.
    Sales and Operation are normalized into the same display structure.
    """

    priority = {label: index for index, label in enumerate(ATTENTION_ORDER)}
    attention_rows = [r for r in rows if (r.get("health_status") or "") in priority]

    def sort_key(row: dict[str, Any]) -> tuple[int, str, str]:
        return (
            priority.get(row.get("health_status") or "", 99),
            str(row.get("target_date") or "9999-12-31"),
            str(row.get("display_id") or ""),
        )

    normalized: list[dict[str, Any]] = []
    for row in sorted(attention_rows, key=sort_key):
        is_operation = (row.get("entity_type") == "Operation")
        normalized.append(
            {
                "Type": row.get("entity_type") or "-",
                "Project ID": row.get("project_id") or "-",
                "Project Name": (
                    row.get("linked_project_name")
                    if is_operation
                    else row.get("project_name")
                ) or row.get("display_title") or "-",
                "Client Code": row.get("client_code") or "-",
                "Order No": row.get("order_no") if is_operation else "-",
                "Current Owner": row.get("current_owner") or "-",
                "Phase": row.get("phase") or "-",
                "Health Status": row.get("health_status") or "-",
                "Result Status": row.get("result_status") or "-",
                "Main Issue": row.get("main_issue") or "-",
                "Next Step": row.get("next_step_summary") or "-",
                "Next Step Owner": row.get("next_step_owner") or "-",
                "Target Date": row.get("target_date") or "-",
                "Last Event": row.get("last_event") or "-",
            }
        )
    return normalized


def get_dashboard_metrics() -> dict[str, Any]:
    sales = [_decorate_common(r, "Sales") for r in list_sales_projects()]
    operations = [_decorate_common(r, "Operation") for r in list_operation_orders()]
    all_rows = sales + operations

    meeting = [
        r
        for r in all_rows
        if r.get("health_status") in MEETING_POOL_HEALTH or bool(r.get("review_this_week"))
    ]
    need_decision = sum(
        1 for r in all_rows if r.get("health_status") == "Need Decision" or r.get("request_type") == "Decision"
    )

    active_sales = [r for r in sales if _is_active_sales(r)]
    active_operations = [r for r in operations if _is_active_operation(r)]

    attention_summary = _field_counts(all_rows, "health_status", ATTENTION_ORDER)

    return {
        # Existing keys kept for compatibility.
        "sales_projects": len(sales),
        "operation_orders": len(operations),
        "all_items": len(all_rows),
        "meeting_pool": len(meeting),
        "active_sales": len(active_sales),
        "active_operations": len(active_operations),
        "need_decision": need_decision,
        # New dashboard keys.
        "total_sales": len(sales),
        "total_operations": len(operations),
        "sales_progress": _ordered_counts([_sales_progress_label(r) for r in sales], SALES_PROGRESS_ORDER),
        "operation_progress": _ordered_counts(
            [_operation_progress_label(r) for r in operations], OPERATION_PROGRESS_ORDER
        ),
        "sales_phase_active": _field_counts(active_sales, "phase", SALES_PHASES),
        "operation_phase_active": _field_counts(active_operations, "phase", OPERATION_PHASES),
        "attention_summary": attention_summary,
        "high_attention_total": sum(attention_summary.get(label, 0) for label in HIGH_ATTENTION_HEALTH),
        "waiting_total": sum(
            attention_summary.get(label, 0)
            for label in ["Waiting Client", "Waiting Supplier", "Waiting Internal"]
        ),
        "blocked_delayed_total": attention_summary.get("Blocked", 0) + attention_summary.get("Delayed", 0),
        "attention_review_rows": _attention_review_rows(all_rows),
        "recent_updates": _recent_updates(all_rows),  # Kept for compatibility with older dashboard versions.
    }


def list_board_projects(record_type: str, include_archived: bool = False) -> list[dict[str, Any]]:
    if record_type == "Sales":
        return [_decorate_common(r, "Sales") for r in list_sales_projects(include_archived=include_archived)]
    return [_decorate_common(r, "Operation") for r in list_operation_orders(include_archived=include_archived)]


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


def list_detail_ids(record_type: str, include_archived: bool = False) -> list[str]:
    return list_sales_project_ids(include_archived=include_archived) if record_type == "Sales" else list_operation_order_ids(include_archived=include_archived)


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



def _meeting_has_value(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and text.lower() not in {"-", "nan", "none", "null"}


def _meeting_parse_date(value: Any) -> date | None:
    if not _meeting_has_value(value):
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except Exception:
        return None


def _meeting_is_closed(row: dict[str, Any]) -> bool:
    result = str(row.get("result_status") or "").strip()
    if row.get("entity_type") == "Operation":
        return result in OPERATION_CLOSED_RESULTS
    return result in SALES_CLOSED_RESULTS or result.lower() in {"closed", "completed", "cancelled", "canceled", "decision made"}


def _meeting_need_decision(row: dict[str, Any]) -> bool:
    health = str(row.get("health_status") or "").strip()
    request_type = str(row.get("request_type") or "").strip()
    return (
        health in {"Need Decision", "Need Alignment"}
        or request_type in {"Decision", "Approval", "Alignment"}
        or _meeting_has_value(row.get("need_decision_from"))
        or _meeting_has_value(row.get("need_from_meeting"))
    )


def _meeting_blocked(row: dict[str, Any]) -> bool:
    return str(row.get("health_status") or "").strip() == "Blocked" or _meeting_has_value(row.get("block_point"))


def _meeting_due_followup(row: dict[str, Any]) -> bool:
    """Meeting follow-up reminder: next step + owner + target date already due.

    The weekly meeting is reviewed once a week, so this intentionally does not
    pull in items that are merely due within the next 7 days.
    """
    if _meeting_is_closed(row):
        return False
    if str(row.get("followup_status") or "").strip().lower() == "done":
        return False
    if not _meeting_has_value(row.get("next_step_summary")):
        return False
    if not _meeting_has_value(row.get("next_step_owner")):
        return False
    target = _meeting_parse_date(row.get("target_date"))
    return bool(target and target <= date.today())


def _meeting_repeated(row: dict[str, Any]) -> bool:
    repeated = str(row.get("repeated_issue") or "").strip().lower()
    return bool(row.get("pattern_flag")) or repeated in {"yes", "true", "1", "y"}


def _meeting_reason_tags(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if bool(row.get("review_this_week")):
        reasons.append("Manual")
    if _meeting_need_decision(row):
        reasons.append("Need Decision")
    if _meeting_blocked(row):
        reasons.append("Blocked / Risk")
    if _meeting_due_followup(row):
        reasons.append("Due / Follow-up")
    if _meeting_repeated(row):
        reasons.append("Repeated Issue")

    # Keep existing attention-health behaviour for compatibility with the
    # previous meeting pool, but mark it as an automatic status reminder.
    if row.get("health_status") in MEETING_POOL_HEALTH and not any(
        tag in reasons for tag in ["Need Decision", "Blocked / Risk", "Due / Follow-up"]
    ):
        reasons.append(f"Status: {row.get('health_status')}")
    return reasons


def get_meeting_pool() -> list[dict[str, Any]]:
    rows = list_board_projects("Sales") + list_board_projects("Operation")
    meeting_rows: list[dict[str, Any]] = []

    for row in rows:
        if _meeting_is_closed(row):
            continue
        reasons = _meeting_reason_tags(row)
        if not reasons:
            continue

        item = dict(row)
        item["meeting_reason_tags"] = reasons
        item["meeting_pool_source"] = "Manual + Auto" if "Manual" in reasons and len(reasons) > 1 else ("Manual" if "Manual" in reasons else "Auto")
        item["meeting_pool_reason_text"] = ", ".join(reasons)
        meeting_rows.append(item)

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
