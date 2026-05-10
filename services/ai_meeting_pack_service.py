from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from services.ai_business_review_common import (
    clean_text,
    compact_record,
    default_review,
    limit_records,
    review_to_dataframe,
    review_to_markdown,
    run_ai_review_or_fallback,
)

MEETING_SOURCE_FIELDS = [
    "entity_type", "entity_id", "display_id", "project_id", "order_no", "display_title", "project_name",
    "client_code", "next_step_owner", "current_owner", "health_status", "followup_status", "request_type",
    "need_from_meeting", "need_decision_from", "main_issue", "block_point", "blocked_at", "next_step_summary",
    "target_date", "repeated_issue", "review_this_week", "result_status", "last_event",
]


def _is_due_or_overdue(value: Any) -> bool:
    text = clean_text(value)
    if not text:
        return False
    try:
        return date.fromisoformat(text[:10]) <= date.today()
    except Exception:
        return False


def _label(row: dict[str, Any]) -> str:
    return clean_text(row.get("project_id")) or clean_text(row.get("display_id")) or clean_text(row.get("entity_id")) or "Unknown record"


def _need_decision(row: dict[str, Any]) -> bool:
    health = clean_text(row.get("health_status"))
    request_type = clean_text(row.get("request_type"))
    return (
        health in {"Need Decision", "Need Alignment"}
        or request_type in {"Decision", "Approval", "Alignment"}
        or bool(clean_text(row.get("need_from_meeting")))
        or bool(clean_text(row.get("need_decision_from")))
    )


def _blocked(row: dict[str, Any]) -> bool:
    return clean_text(row.get("health_status")) == "Blocked" or bool(clean_text(row.get("block_point"))) or bool(clean_text(row.get("blocked_at")))


def _row_reason(row: dict[str, Any]) -> str:
    reasons = []
    if _need_decision(row):
        reasons.append("decision needed")
    if _blocked(row):
        reasons.append("blocked")
    if _is_due_or_overdue(row.get("target_date")) and clean_text(row.get("followup_status")).lower() != "done":
        reasons.append("due or overdue")
    if clean_text(row.get("repeated_issue")).lower() in {"yes", "true", "1", "y"} or row.get("pattern_flag"):
        reasons.append("repeated issue")
    if clean_text(row.get("health_status")) in {"High Risk", "Need Alignment"}:
        reasons.append(clean_text(row.get("health_status")))
    return ", ".join(reasons) or "open follow-up"


def generate_ai_meeting_control_pack(rows: list[dict[str, Any]], *, output_language: str = "English", use_ai: bool = True) -> dict[str, Any]:
    rows = list(rows or [])
    if not rows:
        return default_review(
            direct_summary="No current visible Meeting Board rows are available for an AI Meeting Control Pack.",
            readiness="Not Ready",
            missing_information=["No visible rows from Meeting Board."],
            suggested_actions=["Adjust filters or add Meeting Prep records before generating the pack."],
            confidence="High",
        )

    decision_rows = [r for r in rows if _need_decision(r)]
    blocked_rows = [r for r in rows if _blocked(r)]
    due_rows = [r for r in rows if _is_due_or_overdue(r.get("target_date")) and clean_text(r.get("followup_status")).lower() != "done"]
    review_rows = [r for r in rows if bool(r.get("review_this_week"))]

    priority_rows = []
    seen = set()
    for group in [decision_rows, blocked_rows, due_rows, review_rows, rows]:
        for row in group:
            key = (row.get("entity_type"), row.get("entity_id"), row.get("project_id"), row.get("order_no"))
            if key in seen:
                continue
            seen.add(key)
            priority_rows.append(row)
            if len(priority_rows) >= 12:
                break
        if len(priority_rows) >= 12:
            break

    owner_actions = []
    for row in rows:
        if clean_text(row.get("next_step_summary")) or clean_text(row.get("next_step_owner")):
            owner_actions.append(
                {
                    "Owner": clean_text(row.get("next_step_owner")) or clean_text(row.get("current_owner")) or "Not assigned",
                    "Project ID": clean_text(row.get("project_id")) or clean_text(row.get("display_id")),
                    "Order No": clean_text(row.get("order_no")),
                    "Next Step": clean_text(row.get("next_step_summary")) or clean_text(row.get("next_step")),
                    "Target Date": clean_text(row.get("target_date")),
                    "Risk": _row_reason(row),
                }
            )
    owner_actions = owner_actions[:40]

    data_gaps = []
    for row in priority_rows[:20]:
        missing = []
        for field, label in [("next_step_owner", "Owner"), ("next_step_summary", "Next Step"), ("target_date", "Target Date")]:
            if not clean_text(row.get(field)):
                missing.append(label)
        if missing:
            data_gaps.append(f"{_label(row)} missing: {', '.join(missing)}")

    boss_focus = [f"{_label(row)}: {_row_reason(row)}" for row in priority_rows[:8]]
    need_decision = [compact_record(r, ["project_id", "order_no", "display_title", "next_step_owner", "need_from_meeting", "need_decision_from", "main_issue"]) for r in decision_rows[:12]]
    blocked = [compact_record(r, ["project_id", "order_no", "blocked_at", "block_point", "main_issue", "next_step_summary", "target_date"]) for r in (blocked_rows + due_rows)[:16]]
    client_follow = [
        compact_record(r, ["project_id", "order_no", "client_code", "display_title", "need_from_meeting", "next_step_summary", "target_date"])
        for r in rows
        if clean_text(r.get("client_code")) and (clean_text(r.get("need_from_meeting")) or clean_text(r.get("next_step_summary")))
    ][:16]

    fallback = default_review(
        readiness="Need Review" if (decision_rows or blocked_rows or due_rows) else "Ready",
        direct_summary=(
            f"Meeting Control Pack generated from {len(rows)} visible Meeting Board row(s). "
            f"Decision items: {len(decision_rows)}, blocked items: {len(blocked_rows)}, due/overdue follow-ups: {len(due_rows)}."
        ),
        key_findings=boss_focus,
        risks=[f"{_label(row)}: {_row_reason(row)}" for row in (decision_rows + blocked_rows + due_rows)[:12]],
        missing_information=data_gaps,
        suggested_actions=[
            "Review Boss Focus and Need Decision items first.",
            "Confirm owners and target dates for rows with data gaps.",
            "Export this pack for weekly meeting preparation if needed.",
        ],
        source_records=limit_records(priority_rows, MEETING_SOURCE_FIELDS, limit=20),
        confidence="Medium" if data_gaps else "High",
        needs_human_attention="Yes" if (decision_rows or blocked_rows or due_rows) else "No",
        extra={
            "boss_focus": boss_focus,
            "need_decision": need_decision,
            "blocked_or_delayed": blocked,
            "owner_action_list": owner_actions,
            "client_follow_up": client_follow,
            "data_gaps": data_gaps,
        },
    )

    if not use_ai:
        return fallback

    context = {
        "visible_row_count": len(rows),
        "boss_focus": boss_focus,
        "need_decision": need_decision,
        "blocked_or_delayed": blocked,
        "owner_action_list": owner_actions[:30],
        "client_follow_up": client_follow,
        "data_gaps": data_gaps,
        "source_records": limit_records(priority_rows, MEETING_SOURCE_FIELDS, limit=20),
    }
    result = run_ai_review_or_fallback(
        review_name="AI Weekly Meeting Control Pack",
        context=context,
        fallback=fallback,
        output_language=output_language,
    )
    # Preserve structured deterministic sections for exports/tables.
    for key in ["boss_focus", "need_decision", "blocked_or_delayed", "owner_action_list", "client_follow_up", "data_gaps"]:
        result.setdefault(key, fallback.get(key, []))
    return result


def meeting_pack_to_markdown(review: dict[str, Any]) -> str:
    return review_to_markdown(review, title="AI Weekly Meeting Control Pack")


def meeting_pack_to_dataframe(review: dict[str, Any]) -> pd.DataFrame:
    rows = review_to_dataframe(review)
    structured = []
    for key, label in [
        ("boss_focus", "Boss Focus"),
        ("need_decision", "Need Decision"),
        ("blocked_or_delayed", "Blocked or Delayed"),
        ("owner_action_list", "Owner Action List"),
        ("client_follow_up", "Client Follow-up"),
        ("data_gaps", "Data Gaps"),
    ]:
        for item in review.get(key) or []:
            structured.append({"Section": label, "Item": label, "Value": item})
    if structured:
        rows = pd.concat([rows, pd.DataFrame(structured)], ignore_index=True, sort=False)
    return rows
