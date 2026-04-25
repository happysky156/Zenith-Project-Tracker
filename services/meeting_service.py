from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from database.repositories import (
    get_operation_order,
    get_sales_project,
    insert_event_log,
    insert_meeting_snapshot,
    update_operation_order_fields,
    update_sales_project_fields,
)
from services.button_service import ButtonActionError
from services.project_service import get_meeting_pool
from utils.dates import current_meeting_week, now_iso
from utils.ids import new_event_id, new_snapshot_id
from utils.logger import get_logger


logger = get_logger("meeting_service")

MEETING_ACTIONS = [
    "Reviewed No Change",
    "Discussed / Follow up",
    "Mark Follow-up Done",
    "Review Next Meeting",
    "Decision Made / Close",
    "High-Risk Follow-up",
    "Remove from Meeting",
]


class MeetingActionError(Exception):
    pass



def _normalize_multi_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, (list, tuple, set)):
        parts = [str(part).strip() for part in value if str(part).strip()]
    else:
        parts = [str(value).strip()] if str(value).strip() else []
    return ", ".join(parts) or None


def _record_as_dict(entity_type: str, entity_id: str) -> dict[str, Any]:
    row = get_sales_project(entity_id) if entity_type == "Sales" else get_operation_order(entity_id)
    if row is None:
        raise ButtonActionError(f"{entity_type} record not found: {entity_id}")
    return dict(row)



def get_team_view_rows() -> list[dict[str, Any]]:
    rows = get_meeting_pool()
    for row in rows:
        row["meeting_focus_reason"] = _focus_reason(row)
    return rows



def _boss_priority_tuple(row: dict[str, Any]) -> tuple[Any, ...]:
    health = row.get("health_status")
    request_type = row.get("request_type")
    priority = row.get("priority")
    pattern = bool(row.get("pattern_flag"))
    target_date = str(row.get("target_date") or "9999-12-31")
    review = 0 if bool(row.get("review_this_week")) else 1
    waiting_gap = 0 if (row.get("client_waiting_for") and not row.get("next_step_summary")) else 1

    health_rank = {
        "Need Decision": 0,
        "Blocked": 1,
        "Delayed": 2,
        "Due Soon": 3,
        "Need Alignment": 4,
        "Waiting Client": 5,
        "Waiting Supplier": 6,
    }.get(health, 99)

    request_rank = {"Decision": 0, "Approval": 1, "Alignment": 2, "Support": 3}.get(request_type, 9)
    priority_rank = {"High": 0, "Medium": 1, "Low": 2}.get(priority, 9)
    pattern_rank = 0 if pattern else 1

    return (health_rank, request_rank, priority_rank, pattern_rank, waiting_gap, review, target_date, str(row.get("display_id") or ""))



def _focus_reason(row: dict[str, Any]) -> str:
    reason_tags = row.get("meeting_reason_tags") or []
    if "Due / Follow-up" in reason_tags:
        return "Follow-up is due and needs checking."
    if "Manual" in reason_tags and len(reason_tags) == 1:
        return "Marked for this week's meeting review."
    health = row.get("health_status")
    request_type = row.get("request_type")
    if health == "Need Decision" or request_type == "Decision":
        who = row.get("need_decision_from") or "Ehab"
        return f"Needs a decision from {who}."
    if health == "Blocked":
        return "Blocked and needs management attention."
    if health == "Delayed":
        return "Delayed against the current plan."
    if health == "Due Soon":
        return "Target date is close and needs follow-up."
    if health == "Need Alignment":
        return "Needs internal alignment before the next step."
    if row.get("pattern_flag"):
        return "Flagged as a repeated issue."
    if row.get("client_waiting_for") and not row.get("next_step_summary"):
        return "Client is waiting, but the next step is not yet clear."
    if bool(row.get("review_this_week")):
        return "Marked for this week's meeting review."
    return "Included in the meeting pool for follow-up."


def _decorate_meeting_record(record: dict[str, Any], entity_type: str, entity_id: str) -> dict[str, Any]:
    item = dict(record)
    item["entity_type"] = entity_type
    item["entity_id"] = entity_id
    item["display_id"] = entity_id
    if entity_type == "Sales":
        item["display_title"] = item.get("project_name") or entity_id
    else:
        item["display_title"] = item.get("linked_project_name") or item.get("project_id") or "(Unlinked)"
    item["meeting_focus_reason"] = _focus_reason(item)
    return item


def get_meeting_record(entity_type: str, entity_id: str) -> dict[str, Any]:
    return _decorate_meeting_record(_record_as_dict(entity_type, entity_id), entity_type, entity_id)


def get_boss_view_rows() -> list[dict[str, Any]]:
    rows = get_meeting_pool()
    for row in rows:
        row["meeting_focus_reason"] = _focus_reason(row)
    return sorted(rows, key=_boss_priority_tuple)



def _build_meeting_updates(record: dict[str, Any], action_name: str) -> tuple[dict[str, Any], bool, bool, str | None]:
    updates: dict[str, Any] = {}
    discussed_flag = False
    carry_forward_flag = False
    event_note: str | None = None

    if action_name == "Reviewed No Change":
        updates["discussed_this_week"] = 1
        discussed_flag = True
        event_note = "Reviewed in meeting with no business-status change."
    elif action_name == "Discussed / Follow up":
        updates["discussed_this_week"] = 1
        if record.get("next_step_summary"):
            updates["followup_status"] = record.get("followup_status") or "Open"
        discussed_flag = True
    elif action_name == "Mark Follow-up Done":
        updates["discussed_this_week"] = 1
        updates["followup_status"] = "Done"
        discussed_flag = True
        event_note = "Follow-up marked as done."
    elif action_name == "Review Next Meeting":
        updates["discussed_this_week"] = 1
        updates["review_this_week"] = 1
        discussed_flag = True
        carry_forward_flag = True
    elif action_name == "Decision Made / Close":
        updates["discussed_this_week"] = 1
        updates["review_this_week"] = 0
        updates["request_type"] = None
        updates["request_note"] = None
        if record.get("health_status") == "Need Decision":
            updates["health_status"] = "On Track"
        discussed_flag = True
        event_note = "Meeting decision recorded."
    elif action_name == "High-Risk Follow-up":
        updates["discussed_this_week"] = 1
        updates["review_this_week"] = 1
        updates["followup_status"] = "Blocked"
        updates["request_type"] = "Decision"
        updates["need_decision_from"] = record.get("need_decision_from") or "Ehab"
        updates["health_status"] = "Need Decision"
        discussed_flag = True
        event_note = "Escalated from meeting."
    elif action_name == "Remove from Meeting":
        updates["review_this_week"] = 0
        event_note = "Removed from current meeting pool."
    else:
        raise MeetingActionError(f"Unsupported meeting action: {action_name}")

    return updates, discussed_flag, carry_forward_flag, event_note



def _write_snapshot(entity_type: str, entity_id: str, record_after: dict[str, Any], discussed_flag: bool, carry_forward_flag: bool) -> None:
    insert_meeting_snapshot(
        {
            "snapshot_id": new_snapshot_id(),
            "meeting_week": current_meeting_week(),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": record_after.get("project_id") if entity_type == "Operation" else entity_id,
            "order_no": entity_id if entity_type == "Operation" else None,
            "phase": record_after.get("phase"),
            "health_status": record_after.get("health_status"),
            "result_status": record_after.get("result_status"),
            "client_waiting_for": record_after.get("client_waiting_for"),
            "progress_summary": record_after.get("progress_summary"),
            "main_issue": record_after.get("main_issue"),
            "block_point": record_after.get("block_point"),
            "need_from_meeting": record_after.get("need_from_meeting"),
            "next_step_summary": record_after.get("next_step_summary"),
            "next_step_owner": record_after.get("next_step_owner"),
            "request_type": record_after.get("request_type"),
            "need_decision_from": record_after.get("need_decision_from"),
            "meeting_note": record_after.get("meeting_note"),
            "discussed_flag": int(discussed_flag),
            "carry_forward_flag": int(carry_forward_flag),
            "snapshot_time": now_iso(),
        }
    )



def apply_meeting_action(entity_type: str, entity_id: str, action_name: str, operator: str, source_page: str) -> dict[str, Any]:
    record = _record_as_dict(entity_type, entity_id)
    updates, discussed_flag, carry_forward_flag, event_note = _build_meeting_updates(record, action_name)
    now = now_iso()

    updates["last_event"] = action_name
    updates["last_updated_by"] = operator
    updates["last_reviewed_at"] = now

    logger.info("Meeting action: %s | entity_type=%s | entity_id=%s | operator=%s", action_name, entity_type, entity_id, operator)
    if entity_type == "Sales":
        update_sales_project_fields(entity_id, updates)
    else:
        update_operation_order_fields(entity_id, updates)
    record_after = _record_as_dict(entity_type, entity_id)

    insert_event_log(
        {
            "event_id": new_event_id(),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": record_after.get("project_id") if entity_type == "Operation" else entity_id,
            "order_no": entity_id if entity_type == "Operation" else None,
            "event_time": now,
            "event_type": action_name,
            "event_group": "Meeting",
            "old_phase": record.get("phase"),
            "new_phase": record_after.get("phase"),
            "old_health": record.get("health_status"),
            "new_health": record_after.get("health_status"),
            "old_result": record.get("result_status"),
            "new_result": record_after.get("result_status"),
            "round_change": None,
            "operator": operator,
            "event_note": event_note,
            "source_page": source_page,
        }
    )

    _write_snapshot(entity_type=entity_type, entity_id=entity_id, record_after=record_after, discussed_flag=discussed_flag, carry_forward_flag=carry_forward_flag)

    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action_name": action_name,
        "new_health": record_after.get("health_status"),
        "review_this_week": record_after.get("review_this_week"),
        "discussed_this_week": record_after.get("discussed_this_week"),
        "row": _decorate_meeting_record(record_after, entity_type, entity_id),
    }



def save_meeting_followup(
    entity_type: str,
    entity_id: str,
    meeting_note: str | None,
    next_step_summary: str | None,
    next_step_owner: str | None,
    next_step_support: Any | None = None,
    target_date: str | None = None,
    operator: str = "",
    source_page: str = "Meeting Mode",
) -> dict[str, Any]:
    record = _record_as_dict(entity_type, entity_id)

    normalized_note = (meeting_note or "").strip() or None
    normalized_next_step = (next_step_summary or "").strip() or None
    normalized_owner = (next_step_owner or "").strip() or None
    normalized_support = _normalize_multi_value(next_step_support)
    normalized_target = (target_date or "").strip() or None

    candidate_updates = {
        "meeting_note": normalized_note,
        "next_step_summary": normalized_next_step,
        "next_step_owner": normalized_owner,
        "next_step_support": normalized_support,
        "target_date": normalized_target,
        "followup_status": "Open" if normalized_next_step else None,
    }

    changed_fields = [
        field
        for field, value in candidate_updates.items()
        if (record.get(field) or None) != value
    ]
    if not changed_fields:
        return {"updated": False, "message": "No change in meeting follow-up."}

    now = now_iso()
    updates = dict(candidate_updates)
    updates.update(
        {
            "last_event": "Meeting Follow-up Saved",
            "last_updated_by": operator,
            "last_reviewed_at": now,
        }
    )

    if entity_type == "Sales":
        update_sales_project_fields(entity_id, updates)
    else:
        update_operation_order_fields(entity_id, updates)

    record_after = _record_as_dict(entity_type, entity_id)
    note_parts: list[str] = []
    if normalized_note:
        note_parts.append(f"note: {normalized_note}")
    if normalized_next_step:
        owner_part = normalized_owner or record_after.get("current_owner") or "-"
        support_part = f" | support {normalized_support}" if normalized_support else ""
        due_part = f" | due {normalized_target}" if normalized_target else ""
        note_parts.append(f"next: {normalized_next_step} [{owner_part}]{support_part}{due_part}")

    insert_event_log(
        {
            "event_id": new_event_id(),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": record_after.get("project_id") if entity_type == "Operation" else entity_id,
            "order_no": entity_id if entity_type == "Operation" else None,
            "event_time": now,
            "event_type": "Meeting Follow-up Saved",
            "event_group": "Meeting",
            "old_phase": record.get("phase"),
            "new_phase": record_after.get("phase"),
            "old_health": record.get("health_status"),
            "new_health": record_after.get("health_status"),
            "old_result": record.get("result_status"),
            "new_result": record_after.get("result_status"),
            "round_change": None,
            "operator": operator,
            "event_note": " | ".join(note_parts) if note_parts else f"Changed fields: {', '.join(changed_fields)}",
            "source_page": source_page,
        }
    )
    return {"updated": True, "message": "Meeting follow-up saved.", "changed_fields": changed_fields, "row": _decorate_meeting_record(record_after, entity_type, entity_id)}



def generate_weekly_snapshot(rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        _write_snapshot(
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            record_after=row,
            discussed_flag=bool(row.get("discussed_this_week")),
            carry_forward_flag=False,
        )
        count += 1
    return count




def _summary_has_value(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and text.lower() not in {"-", "nan", "none", "null"}


def _summary_parse_date(value: Any) -> date | None:
    if not _summary_has_value(value):
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except Exception:
        return None


def _summary_need_decision(row: dict[str, Any]) -> bool:
    health = str(row.get("health_status") or "").strip()
    request_type = str(row.get("request_type") or "").strip()
    return (
        health in {"Need Decision", "Need Alignment"}
        or request_type in {"Decision", "Approval", "Alignment"}
        or _summary_has_value(row.get("need_decision_from"))
        or _summary_has_value(row.get("need_from_meeting"))
    )


def _summary_blocked(row: dict[str, Any]) -> bool:
    return str(row.get("health_status") or "").strip() == "Blocked" or _summary_has_value(row.get("block_point"))


def _summary_due_followup(row: dict[str, Any]) -> bool:
    if str(row.get("followup_status") or "").strip().lower() == "done":
        return False
    if not _summary_has_value(row.get("next_step_summary")):
        return False
    if not _summary_has_value(row.get("next_step_owner")):
        return False
    target = _summary_parse_date(row.get("target_date"))
    return bool(target and target <= date.today())


def _summary_repeated(row: dict[str, Any]) -> bool:
    repeated = str(row.get("repeated_issue") or "").strip().lower()
    return bool(row.get("pattern_flag")) or repeated in {"yes", "true", "1", "y"}


def get_meeting_summary_metrics(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(rows),
        "need_decision": sum(1 for r in rows if _summary_need_decision(r)),
        "blocked": sum(1 for r in rows if _summary_blocked(r)),
        "delayed_due": sum(1 for r in rows if _summary_due_followup(r)),
        "pattern": sum(1 for r in rows if _summary_repeated(r)),
        "review": sum(1 for r in rows if bool(r.get("review_this_week"))),
    }
def _line_for_summary(row: dict[str, Any]) -> str:
    head = f"{row.get('display_id')} ({row.get('display_title') or '-'})"
    parts = [head]
    if row.get("main_issue"):
        parts.append(f"issue: {row.get('main_issue')}")
    if row.get("next_step_summary"):
        owner = row.get("next_step_owner") or row.get("current_owner") or "-"
        due = f" due {row.get('target_date')}" if row.get('target_date') else ""
        parts.append(f"next: {row.get('next_step_summary')} [{owner}]{due}")
    elif row.get("client_waiting_for"):
        parts.append(f"client waiting for: {row.get('client_waiting_for')}")
    elif row.get("meeting_note"):
        parts.append(f"note: {row.get('meeting_note')}")
    return " — ".join(parts)





def _meeting_minutes_block(row: dict[str, Any]) -> str:
    lines = [
        f"- {row.get('entity_type')} | {row.get('display_id')} | {row.get('display_title') or '-'}",
        f"  Client Code: {row.get('client_code') or '-'}",
        f"  Phase / Health / Result: {row.get('phase') or '-'} / {row.get('health_status') or '-'} / {row.get('result_status') or '-'}",
        f"  Focus: {row.get('meeting_focus_reason') or '-'}",
        f"  Current Progress: {row.get('progress_summary') or '-'}",
        f"  Main Issue: {row.get('main_issue') or '-'}",
        f"  Blocked At: {row.get('block_point') or '-'}",
        f"  Possible Reason: {row.get('likely_reason') or '-'}",
        f"  Need From Meeting: {row.get('need_from_meeting') or '-'}",
        f"  Meeting Note: {row.get('meeting_note') or '-'}",
        f"  Next Step: {row.get('next_step_summary') or '-'}",
        f"  Next Step Owner: {row.get('next_step_owner') or row.get('current_owner') or '-'}",
        f"  Target Date: {row.get('target_date') or '-'}",
    ]
    if row.get('need_decision_from'):
        lines.append(f"  Decision By: {row.get('need_decision_from')}")
    return "\n".join(lines)


def generate_meeting_minutes_text(rows: list[dict[str, Any]], view_name: str) -> str:
    week = current_meeting_week()
    metrics = get_meeting_summary_metrics(rows)
    lines = [
        f"Meeting Minutes ({week}) — {view_name}",
        f"Total items: {metrics['total']}",
        f"Need decision: {metrics['need_decision']} | Blocked: {metrics['blocked']} | Due / Follow-up: {metrics['delayed_due']} | Repeated issues: {metrics['pattern']}",
        "",
        "Items reviewed:",
    ]
    if rows:
        for row in rows:
            lines.append(_meeting_minutes_block(row))
            lines.append("")
    else:
        lines.append("- No items in the meeting pool.")
    return "\n".join(lines).strip() + "\n"


def build_followup_export_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    export_rows = []
    for row in rows:
        export_rows.append(
            {
                "Type": row.get("entity_type"),
                "ID": row.get("display_id"),
                "Title": row.get("display_title") or "-",
                "Client Code": row.get("client_code") or "-",
                "Phase": row.get("phase") or "-",
                "Health": row.get("health_status") or "-",
                "Result": row.get("result_status") or "-",
                "Current Progress": row.get("progress_summary") or "-",
                "Main Issue": row.get("main_issue") or "-",
                "Blocked At": row.get("block_point") or "-",
                "Possible Reason": row.get("likely_reason") or "-",
                "Need From Meeting": row.get("need_from_meeting") or "-",
                "Meeting Note": row.get("meeting_note") or "-",
                "Next Step": row.get("next_step_summary") or "-",
                "Next Step Owner": row.get("next_step_owner") or row.get("current_owner") or "-",
                "Target Date": row.get("target_date") or "-",
                "Follow-up Status": row.get("followup_status") or "Open",
                "Meeting Reason": row.get("meeting_pool_reason_text") or ", ".join(row.get("meeting_reason_tags") or []) or "-",
                "Decision By": row.get("need_decision_from") or "-",
                "Last Event": row.get("last_event") or "-",
                "Review This Week": "Yes" if row.get("review_this_week") else "No",
            }
        )
    return pd.DataFrame(export_rows)


def generate_post_meeting_summary(rows: list[dict[str, Any]], view_name: str) -> dict[str, str]:
    week = current_meeting_week()
    metrics = get_meeting_summary_metrics(rows)
    need_decision_rows = [r for r in rows if _summary_need_decision(r)]
    risk_rows = [r for r in rows if _summary_blocked(r) or _summary_due_followup(r)]
    pattern_rows = [r for r in rows if _summary_repeated(r)]
    follow_up_rows = [r for r in rows if _summary_has_value(r.get("next_step_summary")) or _summary_has_value(r.get("meeting_note"))]

    boss_lines = [
        f"Weekly Meeting Summary ({week}) — {view_name}",
        f"Total items reviewed: {metrics['total']}",
        f"Need decision: {metrics['need_decision']}; Blocked: {metrics['blocked']}; Due / Follow-up: {metrics['delayed_due']}; Repeated issues: {metrics['pattern']}",
        "",
        "Boss priorities:",
    ]
    if need_decision_rows:
        boss_lines.append("1. Decision-needed items:")
        boss_lines.extend([f"- {_line_for_summary(r)}" for r in need_decision_rows[:10]])
    if risk_rows:
        boss_lines.append("2. Execution / timing risks:")
        boss_lines.extend([f"- {_line_for_summary(r)}" for r in risk_rows[:10]])
    if pattern_rows:
        boss_lines.append("3. Repeated issues:")
        boss_lines.extend([f"- {_line_for_summary(r)}" for r in pattern_rows[:10]])
    if not (need_decision_rows or risk_rows or pattern_rows):
        boss_lines.append("- No major escalation item in the current meeting pool.")

    team_lines = [
        f"Post-Meeting Action List ({week}) — {view_name}",
        f"Total items in pool: {metrics['total']}",
        "",
        "Next-step focus:",
    ]
    if follow_up_rows:
        team_lines.extend([f"- {_line_for_summary(r)}" for r in follow_up_rows[:20]])
    else:
        team_lines.append("- No explicit next-step summary or quick meeting note recorded yet.")

    return {"boss_summary": "\n".join(boss_lines), "team_summary": "\n".join(team_lines)}
