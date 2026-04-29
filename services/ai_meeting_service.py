from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from database.repositories import list_operation_orders, list_sales_projects
from services.ai_client import call_deepseek_json


MEETING_FIELDS = [
    "current_progress",
    "main_issue",
    "blocked_at",
    "waiting_for_what",
    "need_from_meeting",
    "next_step",
    "next_step_owner",
    "target_date",
    "review_this_week",
    "meeting_note",
]

FIELD_LABELS = {
    "current_progress": "Current Progress",
    "main_issue": "Main Issue",
    "blocked_at": "Blocked At",
    "waiting_for_what": "Waiting For What",
    "need_from_meeting": "Need From Meeting",
    "next_step": "Next Step",
    "next_step_owner": "Next Step Owner",
    "target_date": "Target Date",
    "review_this_week": "Review This Week",
    "meeting_note": "Meeting Note",
}

# Mapping for the existing database field names.  The AI draft uses clear UI names;
# the production tables currently use the historical field names below.
UI_TO_DB_FIELD_MAP = {
    "current_progress": "progress_summary",
    "blocked_at": "block_point",
    "waiting_for_what": "waiting_for_text",
    "next_step": "next_step_summary",
}


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def _lower(value: Any) -> str:
    return clean_text(value).lower()


def _similarity(a: str, b: str) -> float:
    a = _lower(a)
    b = _lower(b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _contains_score(query: str, text: str) -> float:
    query = _lower(query)
    text = _lower(text)
    if not query or not text:
        return 0.0
    if query == text:
        return 1.0
    if query in text:
        return 0.84
    return _similarity(query, text)


def _bool_to_yes_no(value: Any) -> str:
    if isinstance(value, str):
        return "Yes" if value.strip().lower() in {"1", "true", "yes", "y"} else "No"
    return "Yes" if bool(value) else "No"


def _normalise_sales_row(row: dict[str, Any]) -> dict[str, Any]:
    linked_orders = clean_text(row.get("linked_orders"))
    return {
        "record_type": "Sales",
        "entity_id": clean_text(row.get("project_id")),
        "project_id": clean_text(row.get("project_id")),
        "project_name": clean_text(row.get("project_name")),
        "client_code": clean_text(row.get("client_code")),
        "order_no": linked_orders,
        "current_owner": clean_text(row.get("current_owner")),
        "phase": clean_text(row.get("phase")),
        "health_status": clean_text(row.get("health_status")),
        "result_status": clean_text(row.get("result_status")),
        "review_this_week": bool(row.get("review_this_week")),
        "current_progress": clean_text(row.get("progress_summary")),
        "main_issue": clean_text(row.get("main_issue")),
        "blocked_at": clean_text(row.get("block_point")),
        "waiting_for_what": clean_text(row.get("waiting_for_text")),
        "need_from_meeting": clean_text(row.get("need_from_meeting")),
        "next_step": clean_text(row.get("next_step_summary")),
        "next_step_owner": clean_text(row.get("next_step_owner")),
        "target_date": clean_text(row.get("target_date")),
        "meeting_note": clean_text(row.get("meeting_note")),
        "last_event": clean_text(row.get("last_event")),
        "raw": row,
    }


def _normalise_operation_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "Operation",
        "entity_id": clean_text(row.get("order_no")),
        "project_id": clean_text(row.get("project_id")),
        "project_name": clean_text(row.get("linked_project_name") or row.get("project_name")),
        "client_code": clean_text(row.get("client_code")),
        "order_no": clean_text(row.get("order_no")),
        "current_owner": clean_text(row.get("current_owner")),
        "phase": clean_text(row.get("phase")),
        "health_status": clean_text(row.get("health_status")),
        "result_status": clean_text(row.get("result_status")),
        "review_this_week": bool(row.get("review_this_week")),
        "current_progress": clean_text(row.get("progress_summary")),
        "main_issue": clean_text(row.get("main_issue")),
        "blocked_at": clean_text(row.get("block_point")),
        "waiting_for_what": clean_text(row.get("waiting_for_text")),
        "need_from_meeting": clean_text(row.get("need_from_meeting")),
        "next_step": clean_text(row.get("next_step_summary")),
        "next_step_owner": clean_text(row.get("next_step_owner")),
        "target_date": clean_text(row.get("target_date")),
        "meeting_note": clean_text(row.get("meeting_note")),
        "last_event": clean_text(row.get("last_event")),
        "raw": row,
    }


def list_searchable_projects() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for row in list_sales_projects():
        normalised = _normalise_sales_row(row)
        if normalised["project_id"] or normalised["project_name"]:
            rows.append(normalised)

    for row in list_operation_orders():
        normalised = _normalise_operation_row(row)
        if normalised["project_id"] or normalised["order_no"]:
            rows.append(normalised)

    return rows


def search_project_candidates(
    query: str,
    *,
    max_results: int = 12,
    record_type_filter: str = "All",
    review_only: bool = False,
) -> list[dict[str, Any]]:
    query = clean_text(query)
    if not query:
        return []

    candidates = list_searchable_projects()
    results: list[dict[str, Any]] = []

    for item in candidates:
        if record_type_filter != "All" and item.get("record_type") != record_type_filter:
            continue
        if review_only and not item.get("review_this_week"):
            continue

        project_id = clean_text(item.get("project_id"))
        project_name = clean_text(item.get("project_name"))
        client_code = clean_text(item.get("client_code"))
        order_no = clean_text(item.get("order_no"))

        score = 0.0
        # Highest confidence: Project ID and Order No.
        score = max(score, _contains_score(query, project_id) * 1.22)
        score = max(score, _contains_score(query, order_no) * 1.18)
        # High confidence: Client Code.
        score = max(score, _contains_score(query, client_code) * 1.08)
        # Medium confidence: Project Name.
        score = max(score, _contains_score(query, project_name) * 0.96)

        combined_text = " ".join(
            [
                project_id,
                project_name,
                client_code,
                order_no,
                clean_text(item.get("current_owner")),
                clean_text(item.get("phase")),
                clean_text(item.get("main_issue")),
                clean_text(item.get("next_step")),
                clean_text(item.get("last_event")),
            ]
        )
        score = max(score, _contains_score(query, combined_text) * 0.82)

        # Meeting-friendly ranking: current meeting/recent active items first.
        if item.get("review_this_week"):
            score += 0.08
        if _lower(item.get("result_status")) not in {"lost", "cancelled", "paid closed"}:
            score += 0.05

        if score >= 0.25:
            item_with_score = dict(item)
            item_with_score["match_score"] = round(score, 3)
            results.append(item_with_score)

    results.sort(
        key=lambda x: (
            float(x.get("match_score", 0)),
            bool(x.get("review_this_week")),
            clean_text(x.get("project_id")),
        ),
        reverse=True,
    )
    return results[:max_results]


def build_existing_field_snapshot(project: dict[str, Any]) -> dict[str, str]:
    return {
        "current_progress": clean_text(project.get("current_progress")),
        "main_issue": clean_text(project.get("main_issue")),
        "blocked_at": clean_text(project.get("blocked_at")),
        "waiting_for_what": clean_text(project.get("waiting_for_what")),
        "need_from_meeting": clean_text(project.get("need_from_meeting")),
        "next_step": clean_text(project.get("next_step")),
        "next_step_owner": clean_text(project.get("next_step_owner")),
        "target_date": clean_text(project.get("target_date")),
        "review_this_week": _bool_to_yes_no(project.get("review_this_week")),
        "meeting_note": clean_text(project.get("meeting_note")),
    }


def extract_meeting_fields_with_ai(
    *,
    selected_project: dict[str, Any],
    meeting_notes: str,
    output_language: str = "English",
) -> dict[str, Any]:
    existing_snapshot = build_existing_field_snapshot(selected_project)

    system_prompt = """
You are an internal project meeting assistant for Zenith E.C.S.

Your job:
- Convert messy weekly meeting notes into structured project follow-up fields.
- Do not invent facts.
- Do not convert uncertain information into confirmed information.
- If information is unclear, use "Not confirmed".
- If no information is provided for a field, use an empty string.
- Keep the output concise and business-friendly.
- Output JSON only.

Important rules:
- The user has already selected and confirmed the project.
- Never change the Project ID.
- Never create a new project.
- Never say the database has been updated.
- Do not update the database directly.
"""

    user_prompt = f"""
Please extract the following meeting fields as JSON.

Output language: {output_language}

Confirmed project:
- Record Type: {selected_project.get("record_type")}
- Entity ID: {selected_project.get("entity_id")}
- Project ID: {selected_project.get("project_id")}
- Project Name: {selected_project.get("project_name")}
- Client Code: {selected_project.get("client_code")}
- Order No: {selected_project.get("order_no")}
- Current Owner: {selected_project.get("current_owner")}
- Phase: {selected_project.get("phase")}

Existing system fields:
{existing_snapshot}

New meeting notes:
{meeting_notes}

Required JSON schema:
{{
  "current_progress": "",
  "main_issue": "",
  "blocked_at": "",
  "waiting_for_what": "",
  "need_from_meeting": "",
  "next_step": "",
  "next_step_owner": "",
  "target_date": "",
  "review_this_week": "Yes or No",
  "meeting_note": "",
  "difference_summary": "",
  "confidence": "High / Medium / Low",
  "needs_human_attention": "Yes or No"
}}
"""

    result = call_deepseek_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.1,
    )

    cleaned: dict[str, Any] = {}
    for field in MEETING_FIELDS:
        cleaned[field] = clean_text(result.get(field))

    cleaned["difference_summary"] = clean_text(result.get("difference_summary"))
    cleaned["confidence"] = clean_text(result.get("confidence") or "Medium")
    cleaned["needs_human_attention"] = clean_text(result.get("needs_human_attention") or "No")

    if cleaned["review_this_week"].strip().lower() not in {"yes", "no"}:
        cleaned["review_this_week"] = "Yes" if cleaned["review_this_week"] else "No"

    return cleaned
