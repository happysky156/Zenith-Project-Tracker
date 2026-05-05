from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from datetime import datetime
from typing import Any

import pandas as pd

from database.repositories import list_operation_orders, list_sales_projects
from services.ai_client import call_deepseek_json
from services.project_service import get_dashboard_metrics, get_meeting_pool, get_record_snapshots, get_record_timeline


SUPPORTED_OUTPUT_LANGUAGES = ["English", "Chinese", "Bilingual Chinese and English"]
SUPPORTED_SCOPES = ["All", "Sales Board", "Operation Board", "Dashboard", "Project Details", "Meeting Mode"]
SUPPORTED_RECORD_TYPES = ["All", "Sales", "Operation"]

EVIDENCE_COLUMNS = [
    "Source Module",
    "Record Type",
    "Source ID",
    "Entity ID",
    "Project ID",
    "Project Name",
    "Order No",
    "Linked Orders",
    "Linked Order Count",
    "Order Link Status",
    "Client Code",
    "Current Owner",
    "Phase",
    "Health Status",
    "Result Status",
    "Current Progress",
    "Main Issue",
    "Blocked At",
    "Waiting For What",
    "Need From Meeting",
    "Next Step",
    "Next Step Owner",
    "Target Date",
    "Review This Week",
    "Meeting Focus Reason",
    "History Type",
    "History Time",
    "History Note",
    "Old Phase",
    "New Phase",
    "Old Health",
    "New Health",
    "Old Result",
    "New Result",
    "Last Event",
    "Reference Link",
]

DASHBOARD_COLUMNS = ["Metric", "Value", "Source Module"]

STATUS_KEYWORDS: dict[str, list[str]] = {
    "Blocked": ["blocked", "block", "blocking", "stuck", "卡住", "阻塞", "卡点", "卡", "停住"],
    "Delayed": ["delayed", "delay", "late", "overdue", "延期", "延迟", "逾期", "拖延", "delay了"],
    "Due Soon": ["due soon", "due", "target date", "deadline", "到期", "目标日期", "截止", "跟进到期"],
    "Need Decision": ["decision", "decide", "approval", "approve", "ehab", "boss", "老板", "决定", "决策", "批准", "审批"],
    "Need Alignment": ["alignment", "align", "coordinate", "对齐", "协调", "确认方向", "统一"],
    "Waiting Client": ["waiting client", "client waiting", "customer", "客户", "客人", "客户等待", "等客户"],
    "Waiting Supplier": ["waiting supplier", "supplier", "factory", "vendor", "供应商", "工厂", "等供应商"],
    "Waiting Internal": ["waiting internal", "internal", "team", "内部", "团队", "等内部"],
    "On Hold": ["hold", "on hold", "暂停", "搁置"],
    "On Track": ["on track", "normal", "正常", "顺利"],
}

INTENT_KEYWORDS: dict[str, list[str]] = {
    "dashboard": ["dashboard", "summary", "count", "how many", "统计", "汇总", "多少", "数量", "概览"],
    "meeting": ["meeting", "discuss", "review", "this week", "next meeting", "会议", "讨论", "本周", "下次会议", "复盘"],
    "sales": ["sales", "quotation", "quote", "sample", "project", "报价", "打样", "销售", "项目"],
    "operation": ["operation", "order", "shipment", "payment", "delivery", "订单", "出货", "付款", "收款", "交付"],
    "detail": ["detail", "details", "status of", "current status", "reference link", "project details", "详情", "状态", "链接"],
    "with_orders": ["with orders", "have orders", "linked order", "linked orders", "projects with orders", "already have orders", "已有关联订单", "有订单", "已有订单", "关联订单"],
    "without_orders": ["without orders", "no order", "no orders", "without order", "no linked order", "projects without orders", "没有订单", "无订单", "未下单", "没有关联订单", "未关联订单"],
    "unlinked_operation": ["unlinked operation", "unlinked order", "operation not linked", "operation orders without sales", "订单没有关联项目", "没有关联项目的订单", "未关联项目的订单"],
    "boss_summary": ["ehab focus", "boss focus", "what should ehab focus", "management focus", "老板关注", "老板重点", "ehab关注", "ehab重点", "管理层关注"],
    "client_open_issues": ["open issues", "client issues", "customer issues", "all open issues", "客户问题", "客户未关闭问题", "客户open issue", "open issue"],
    "history": ["history", "timeline", "change history", "project history", "order history", "变化", "历史", "时间线", "项目历史", "订单历史", "变更记录"],
    "next_step": ["next step", "follow up", "follow-up", "action", "下一步", "跟进", "行动"],
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "at", "by", "with",
    "show", "me", "what", "which", "who", "when", "where", "why", "how", "many", "all",
    "please", "project", "projects", "order", "orders", "current", "system", "records", "record",
}


class AIProjectAssistantError(RuntimeError):
    """Raised when the AI Project Assistant cannot safely complete a request."""


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _lower(value: Any) -> str:
    return clean_text(value).lower()


def _has_any(text: str, phrases: list[str]) -> bool:
    lower = _lower(text)
    return any(_lower(phrase) and _lower(phrase) in lower for phrase in phrases)


def _tokenize(query: str) -> list[str]:
    lower = _lower(query)
    tokens = re.findall(r"[a-zA-Z0-9_\-/.#]+|[\u4e00-\u9fff]{2,}", lower)
    cleaned = []
    for token in tokens:
        token = token.strip().lower()
        if not token or token in STOPWORDS or len(token) <= 1:
            continue
        cleaned.append(token)
    return cleaned


def _bool_label(value: Any) -> str:
    if isinstance(value, str):
        return "Yes" if value.strip().lower() in {"1", "true", "yes", "y"} else "No"
    return "Yes" if bool(value) else "No"


def _meeting_reference_links(row: dict[str, Any]) -> str:
    links: list[str] = []
    for idx in range(1, 4):
        label = clean_text(row.get(f"meeting_reference_link_{idx}_label")) or f"Meeting Ref {idx}"
        url = clean_text(row.get(f"meeting_reference_link_{idx}_url"))
        if url:
            links.append(f"{label}: {url}")
    return " | ".join(links)


def _normalise_sales_row(row: dict[str, Any], *, source_module: str = "Sales Board", source_id: str = "") -> dict[str, Any]:
    source_id = source_id or f"S{clean_text(row.get('project_id'))}"
    return {
        "Source Module": source_module,
        "Record Type": "Sales",
        "Source ID": source_id,
        "Entity ID": clean_text(row.get("project_id")),
        "Project ID": clean_text(row.get("project_id")),
        "Project Name": clean_text(row.get("project_name")),
        "Order No": clean_text(row.get("linked_orders")),
        "Linked Orders": clean_text(row.get("linked_orders")),
        "Linked Order Count": clean_text(row.get("linked_order_count")),
        "Order Link Status": "Linked" if int(row.get("linked_order_count") or 0) > 0 else "No linked Operation Order",
        "Client Code": clean_text(row.get("client_code")),
        "Category": clean_text(row.get("category")),
        "Priority": clean_text(row.get("priority")),
        "Current Owner": clean_text(row.get("current_owner")),
        "Support From": clean_text(row.get("support_from")),
        "Phase": clean_text(row.get("phase")),
        "Health Status": clean_text(row.get("health_status")),
        "Result Status": clean_text(row.get("result_status")),
        "Client Waiting For": clean_text(row.get("client_waiting_for")),
        "Current Progress": clean_text(row.get("progress_summary")),
        "Main Issue": clean_text(row.get("main_issue")),
        "Blocked At": clean_text(row.get("block_point")),
        "Waiting For What": clean_text(row.get("waiting_for_text")),
        "Likely Reason": clean_text(row.get("likely_reason")),
        "Need From Meeting": clean_text(row.get("need_from_meeting")),
        "Next Step": clean_text(row.get("next_step_summary")),
        "Next Step Owner": clean_text(row.get("next_step_owner")),
        "Next Step Support": clean_text(row.get("next_step_support")),
        "Target Date": clean_text(row.get("target_date")),
        "Follow-up Status": clean_text(row.get("followup_status")),
        "Review This Week": _bool_label(row.get("review_this_week")),
        "Discussed This Week": _bool_label(row.get("discussed_this_week")),
        "Request Type": clean_text(row.get("request_type")),
        "Request Note": clean_text(row.get("request_note")),
        "Need Decision From": clean_text(row.get("need_decision_from")),
        "Need Alignment With": clean_text(row.get("need_alignment_with")),
        "Waiting For Person": clean_text(row.get("waiting_for_person")),
        "Pattern Flag": _bool_label(row.get("pattern_flag")),
        "Pattern Note": clean_text(row.get("pattern_note")),
        "Meeting Note": clean_text(row.get("meeting_note")),
        "Meeting Focus Reason": clean_text(row.get("meeting_focus_reason") or row.get("meeting_pool_reason_text")),
        "Last Event": clean_text(row.get("last_event")),
        "Last Status Update At": clean_text(row.get("last_status_update_at")),
        "Last Reviewed At": clean_text(row.get("last_reviewed_at")),
        "Last Updated By": clean_text(row.get("last_updated_by")),
        "Reference Link": clean_text(row.get("reference_link")),
        "Meeting Reference Links": _meeting_reference_links(row),
        "Created At": clean_text(row.get("created_at")),
    }


def _normalise_operation_row(row: dict[str, Any], *, source_module: str = "Operation Board", source_id: str = "") -> dict[str, Any]:
    source_id = source_id or f"O{clean_text(row.get('order_no'))}"
    return {
        "Source Module": source_module,
        "Record Type": "Operation",
        "Source ID": source_id,
        "Entity ID": clean_text(row.get("order_no")),
        "Project ID": clean_text(row.get("project_id")),
        "Project Name": clean_text(row.get("linked_project_name") or row.get("project_name")),
        "Order No": clean_text(row.get("order_no")),
        "Linked Orders": clean_text(row.get("order_no")),
        "Linked Order Count": "1" if clean_text(row.get("order_no")) else "0",
        "Order Link Status": "Linked to Sales Project" if clean_text(row.get("linked_project_name")) else "No linked Sales Project",
        "Linked Project Name": clean_text(row.get("linked_project_name")),
        "Client Code": clean_text(row.get("client_code")),
        "Category": "",
        "Priority": clean_text(row.get("priority")),
        "Current Owner": clean_text(row.get("current_owner")),
        "Support From": clean_text(row.get("support_from")),
        "Phase": clean_text(row.get("phase")),
        "Health Status": clean_text(row.get("health_status")),
        "Result Status": clean_text(row.get("result_status")),
        "Client Waiting For": clean_text(row.get("client_waiting_for")),
        "Current Progress": clean_text(row.get("progress_summary")),
        "Main Issue": clean_text(row.get("main_issue")),
        "Blocked At": clean_text(row.get("block_point")),
        "Waiting For What": clean_text(row.get("waiting_for_text")),
        "Likely Reason": clean_text(row.get("likely_reason")),
        "Need From Meeting": clean_text(row.get("need_from_meeting")),
        "Next Step": clean_text(row.get("next_step_summary")),
        "Next Step Owner": clean_text(row.get("next_step_owner")),
        "Next Step Support": clean_text(row.get("next_step_support")),
        "Target Date": clean_text(row.get("target_date")),
        "Follow-up Status": clean_text(row.get("followup_status")),
        "Review This Week": _bool_label(row.get("review_this_week")),
        "Discussed This Week": _bool_label(row.get("discussed_this_week")),
        "Request Type": clean_text(row.get("request_type")),
        "Request Note": clean_text(row.get("request_note")),
        "Need Decision From": clean_text(row.get("need_decision_from")),
        "Need Alignment With": clean_text(row.get("need_alignment_with")),
        "Waiting For Person": clean_text(row.get("waiting_for_person")),
        "Pattern Flag": _bool_label(row.get("pattern_flag")),
        "Pattern Note": clean_text(row.get("pattern_note")),
        "Meeting Note": clean_text(row.get("meeting_note")),
        "Meeting Focus Reason": clean_text(row.get("meeting_focus_reason") or row.get("meeting_pool_reason_text")),
        "Last Event": clean_text(row.get("last_event")),
        "Last Status Update At": clean_text(row.get("last_status_update_at")),
        "Last Reviewed At": clean_text(row.get("last_reviewed_at")),
        "Last Updated By": clean_text(row.get("last_updated_by")),
        "Reference Link": clean_text(row.get("reference_link")),
        "Meeting Reference Links": _meeting_reference_links(row),
        "Created At": clean_text(row.get("created_at")),
    }


def _load_sales_records() -> list[dict[str, Any]]:
    return [_normalise_sales_row(row, source_id=f"S{idx + 1}") for idx, row in enumerate(list_sales_projects())]


def _load_operation_records() -> list[dict[str, Any]]:
    return [_normalise_operation_row(row, source_id=f"O{idx + 1}") for idx, row in enumerate(list_operation_orders())]


def _load_meeting_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(get_meeting_pool()):
        if row.get("entity_type") == "Sales":
            rows.append(_normalise_sales_row(row, source_module="Meeting Mode", source_id=f"M{idx + 1}"))
        else:
            rows.append(_normalise_operation_row(row, source_module="Meeting Mode", source_id=f"M{idx + 1}"))
    return rows


def _build_dashboard_rows() -> list[dict[str, Any]]:
    metrics = get_dashboard_metrics()
    rows: list[dict[str, Any]] = [
        {"Metric": "Total Sales", "Value": metrics.get("total_sales", 0), "Source Module": "Dashboard"},
        {"Metric": "Total Operation", "Value": metrics.get("total_operations", 0), "Source Module": "Dashboard"},
        {"Metric": "Active Sales", "Value": metrics.get("active_sales", 0), "Source Module": "Dashboard"},
        {"Metric": "Active Operation", "Value": metrics.get("active_operations", 0), "Source Module": "Dashboard"},
        {"Metric": "Meeting Pool", "Value": metrics.get("meeting_pool", 0), "Source Module": "Dashboard"},
        {"Metric": "Need Decision", "Value": metrics.get("need_decision", 0), "Source Module": "Dashboard"},
        {"Metric": "High Attention Total", "Value": metrics.get("high_attention_total", 0), "Source Module": "Dashboard"},
        {"Metric": "Waiting Total", "Value": metrics.get("waiting_total", 0), "Source Module": "Dashboard"},
        {"Metric": "Blocked / Delayed Total", "Value": metrics.get("blocked_delayed_total", 0), "Source Module": "Dashboard"},
    ]
    for label, value in (metrics.get("sales_progress") or {}).items():
        rows.append({"Metric": f"Sales Progress - {label}", "Value": value, "Source Module": "Dashboard"})
    for label, value in (metrics.get("operation_progress") or {}).items():
        rows.append({"Metric": f"Operation Progress - {label}", "Value": value, "Source Module": "Dashboard"})
    for label, value in (metrics.get("attention_summary") or {}).items():
        rows.append({"Metric": f"Attention - {label}", "Value": value, "Source Module": "Dashboard"})
    return rows


def _combined_text(record: dict[str, Any]) -> str:
    fields = [
        "Source Module",
        "Record Type",
        "Entity ID",
        "Project ID",
        "Project Name",
        "Order No",
        "Client Code",
        "Category",
        "Priority",
        "Current Owner",
        "Support From",
        "Phase",
        "Health Status",
        "Result Status",
        "Client Waiting For",
        "Current Progress",
        "Main Issue",
        "Blocked At",
        "Waiting For What",
        "Likely Reason",
        "Need From Meeting",
        "Next Step",
        "Next Step Owner",
        "Next Step Support",
        "Target Date",
        "Follow-up Status",
        "Request Type",
        "Request Note",
        "Need Decision From",
        "Need Alignment With",
        "Waiting For Person",
        "Pattern Note",
        "Meeting Note",
        "Meeting Focus Reason",
        "Last Event",
        "Reference Link",
        "Meeting Reference Links",
    ]
    return " ".join(clean_text(record.get(field)) for field in fields if clean_text(record.get(field))).lower()


def _source_scope_match(record: dict[str, Any], scope: str) -> bool:
    if scope == "All":
        return True
    if scope == "Sales Board":
        return record.get("Record Type") == "Sales" and record.get("Source Module") == "Sales Board"
    if scope == "Operation Board":
        return record.get("Record Type") == "Operation" and record.get("Source Module") == "Operation Board"
    if scope == "Project Details":
        return record.get("Source Module") in {"Sales Board", "Operation Board"}
    if scope == "Meeting Mode":
        return record.get("Source Module") == "Meeting Mode"
    return True


def _record_type_match(record: dict[str, Any], record_type: str) -> bool:
    return record_type == "All" or record.get("Record Type") == record_type


def _status_filter_matches(query: str, record: dict[str, Any]) -> tuple[bool, float]:
    matched_any_status = False
    score = 0.0
    for status, phrases in STATUS_KEYWORDS.items():
        if not _has_any(query, phrases):
            continue
        matched_any_status = True
        record_text = _combined_text(record)
        health = _lower(record.get("Health Status"))
        fields_to_check = [
            _lower(record.get("Health Status")),
            _lower(record.get("Result Status")),
            _lower(record.get("Phase")),
            _lower(record.get("Main Issue")),
            _lower(record.get("Blocked At")),
            _lower(record.get("Waiting For What")),
            _lower(record.get("Need From Meeting")),
            _lower(record.get("Meeting Focus Reason")),
            _lower(record.get("Last Event")),
        ]
        status_lower = status.lower()
        if status_lower in health or any(status_lower in field for field in fields_to_check):
            score += 4.5
        elif any(_lower(phrase) in record_text for phrase in phrases):
            score += 3.5
    return matched_any_status, score


def _intent_score(query: str, record: dict[str, Any]) -> tuple[set[str], float]:
    intents: set[str] = set()
    score = 0.0
    lower = _lower(query)

    for intent, phrases in INTENT_KEYWORDS.items():
        if _has_any(lower, phrases):
            intents.add(intent)

    if "meeting" in intents and record.get("Source Module") == "Meeting Mode":
        score += 2.8
    if "sales" in intents and record.get("Record Type") == "Sales":
        score += 1.6
    if "operation" in intents and record.get("Record Type") == "Operation":
        score += 1.6
    if "with_orders" in intents:
        order_no = clean_text(record.get("Order No"))
        if record.get("Record Type") == "Sales" and order_no:
            score += 3.5
    if "without_orders" in intents:
        order_no = clean_text(record.get("Order No"))
        if record.get("Record Type") == "Sales" and not order_no:
            score += 3.5
    if "next_step" in intents and clean_text(record.get("Next Step")):
        score += 1.2
    if "detail" in intents:
        score += 0.6

    return intents, score


def _score_record(query: str, record: dict[str, Any], tokens: list[str]) -> tuple[float, list[str]]:
    reasons: list[str] = []
    text = _combined_text(record)
    score = 0.0
    query_lower = _lower(query)

    identifiers = [
        clean_text(record.get("Entity ID")),
        clean_text(record.get("Project ID")),
        clean_text(record.get("Order No")),
        clean_text(record.get("Client Code")),
    ]
    for identifier in identifiers:
        identifier_lower = _lower(identifier)
        if not identifier_lower:
            continue
        if identifier_lower and identifier_lower in query_lower:
            score += 8.0
            reasons.append(f"Exact identifier match: {identifier}")
            break

    project_name = _lower(record.get("Project Name"))
    if project_name and len(project_name) >= 4 and (project_name in query_lower or query_lower in project_name):
        score += 5.0
        reasons.append("Project name match")

    if query_lower and len(query_lower) >= 3 and query_lower in text:
        score += 4.0
        reasons.append("Direct text match")

    token_hits = [token for token in tokens if token in text]
    if token_hits:
        score += min(len(token_hits), 8) * 0.85
        reasons.append("Keyword match: " + ", ".join(token_hits[:5]))

    matched_status, status_score = _status_filter_matches(query, record)
    if status_score:
        score += status_score
        reasons.append("Status / issue match")

    intents, intent_points = _intent_score(query, record)
    if intent_points:
        score += intent_points
        reasons.append("Intent match: " + ", ".join(sorted(intents)))

    # Useful active/follow-up rows should be slightly easier to find for broad queries.
    if record.get("Review This Week") == "Yes":
        score += 0.35
    if clean_text(record.get("Next Step")):
        score += 0.15

    if not tokens and not matched_status and not intents:
        score = 0.0

    return score, reasons


def _load_records_for_scope(scope: str, record_type: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if scope in {"All", "Sales Board", "Project Details"}:
        records.extend(_load_sales_records())
    if scope in {"All", "Operation Board", "Project Details"}:
        records.extend(_load_operation_records())
    if scope in {"All", "Meeting Mode"}:
        records.extend(_load_meeting_records())

    # Remove duplicate exact rows that can occur when Scope=All; keep module-specific entries
    # because the user explicitly wants display by existing system architecture.
    return [
        record
        for record in records
        if _source_scope_match(record, scope) and _record_type_match(record, record_type)
    ]



def _is_closed_record(record: dict[str, Any]) -> bool:
    result = _lower(record.get("Result Status"))
    if record.get("Record Type") == "Operation":
        return result in {"paid closed", "cancelled", "canceled"}
    return result in {"won", "lost", "closed", "completed", "cancelled", "canceled"}


def _is_open_issue_record(record: dict[str, Any]) -> bool:
    if _is_closed_record(record):
        return False
    return any(
        clean_text(record.get(field))
        for field in [
            "Main Issue",
            "Blocked At",
            "Waiting For What",
            "Need From Meeting",
            "Next Step",
            "Meeting Note",
            "Meeting Focus Reason",
        ]
    ) or clean_text(record.get("Health Status")) in {
        "Blocked",
        "Delayed",
        "Due Soon",
        "Need Decision",
        "Need Alignment",
        "Waiting Client",
        "Waiting Supplier",
        "Waiting Internal",
    }


def _extract_owner_terms(query: str, records: list[dict[str, Any]]) -> list[str]:
    lower = _lower(query)
    terms: list[str] = []
    for pattern in [
        r"(?:owned by|owner|responsible by|handled by)\s+([a-zA-Z][a-zA-Z\s._-]{1,40})",
        r"(?:负责人|owner)[:：]?\s*([\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z\s._-]{0,30})",
    ]:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            raw = match.group(1).strip()
            raw = re.split(
                r"\b(?:with|and|where|that|which|for|is|are|delayed|blocked|orders?)\b|[，,。.;；]",
                raw,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip()
            if raw:
                terms.append(raw.lower())

    known_people: set[str] = set()
    for row in records:
        for field in ["Current Owner", "Next Step Owner", "Support From", "Next Step Support", "Waiting For Person", "Need Decision From"]:
            value = _lower(row.get(field))
            if len(value) >= 2:
                known_people.add(value)

    for person in known_people:
        if person and person in lower:
            terms.append(person)

    cleaned: list[str] = []
    for term in terms:
        term = term.strip().lower()
        if not term or term in STOPWORDS or term in cleaned:
            continue
        cleaned.append(term)
    return cleaned


def _record_has_owner_term(record: dict[str, Any], owner_terms: list[str]) -> bool:
    if not owner_terms:
        return True
    owner_text = " ".join(
        _lower(record.get(field))
        for field in ["Current Owner", "Next Step Owner", "Support From", "Next Step Support", "Waiting For Person", "Need Decision From"]
    )
    return any(term in owner_text for term in owner_terms)


def _record_matches_requested_status(query: str, record: dict[str, Any]) -> bool:
    requested = any(_has_any(query, phrases) for phrases in STATUS_KEYWORDS.values())
    if not requested:
        return True
    _, score = _status_filter_matches(query, record)
    return score > 0


def _apply_deterministic_filters(query: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Narrow obvious multi-condition questions without changing any business data."""
    if not records:
        return records
    original = records
    lower = _lower(query)
    filtered = records

    operation_terms = ["operation order", "operation orders", "operation", "order", "orders", "订单", "出货", "付款", "交付"]
    sales_terms = ["sales project", "sales projects", "sales", "quotation", "quote", "sample", "报价", "打样", "销售项目"]
    asks_operation = _has_any(lower, operation_terms)
    asks_sales = _has_any(lower, sales_terms)
    if asks_operation and not asks_sales:
        candidate = [r for r in filtered if r.get("Record Type") == "Operation"]
        if candidate:
            filtered = candidate
    elif asks_sales and not asks_operation:
        candidate = [r for r in filtered if r.get("Record Type") == "Sales"]
        if candidate:
            filtered = candidate

    candidate = [r for r in filtered if _record_matches_requested_status(query, r)]
    if candidate:
        filtered = candidate

    owner_terms = _extract_owner_terms(query, original)
    candidate = [r for r in filtered if _record_has_owner_term(r, owner_terms)]
    if owner_terms and candidate:
        filtered = candidate

    return filtered or original


def _detect_special_intent(query: str) -> str:
    lower = _lower(query)
    if _has_any(lower, INTENT_KEYWORDS["unlinked_operation"]):
        return "unlinked_operation_orders"
    if _has_any(lower, INTENT_KEYWORDS["without_orders"]):
        return "projects_without_orders"
    # Check with-orders after without-orders so Chinese "没有订单" does not trigger "有订单".
    if _has_any(lower, INTENT_KEYWORDS["with_orders"]):
        return "projects_with_orders"
    if _has_any(lower, INTENT_KEYWORDS["boss_summary"]) or (
        "ehab" in lower and _has_any(lower, ["focus", "summary", "this week", "review", "关注", "重点", "本周", "汇总"])
    ):
        return "boss_summary"
    if _has_any(lower, INTENT_KEYWORDS["history"]):
        return "project_history"
    if _has_any(lower, INTENT_KEYWORDS["client_open_issues"]):
        return "client_open_issues"
    return "natural_search"


def _order_association_query(intent: str, *, scope: str, record_type: str, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sales_records = _load_sales_records()
    operation_records = _load_operation_records()
    sales_project_ids = {clean_text(row.get("Project ID")) for row in sales_records if clean_text(row.get("Project ID"))}
    operation_project_ids = {clean_text(row.get("Project ID")) for row in operation_records if clean_text(row.get("Project ID"))}
    orders_by_project: dict[str, list[str]] = {}
    for op in operation_records:
        project_id = clean_text(op.get("Project ID"))
        order_no = clean_text(op.get("Order No"))
        if project_id and order_no:
            orders_by_project.setdefault(project_id, []).append(order_no)

    if intent == "projects_with_orders":
        full = [row for row in sales_records if clean_text(row.get("Project ID")) in operation_project_ids]
        for row in full:
            linked_orders = orders_by_project.get(clean_text(row.get("Project ID")), [])
            row["Linked Orders"] = ", ".join(linked_orders)
            row["Linked Order Count"] = str(len(linked_orders))
            row["Order No"] = row["Linked Orders"]
            row["Order Link Status"] = "Linked Operation Order found by Project ID"
            row["Match Reason"] = "System order-link rule: Sales Project ID exists in active Operation Project IDs"
    elif intent == "projects_without_orders":
        full = [row for row in sales_records if clean_text(row.get("Project ID")) not in operation_project_ids]
        for row in full:
            row["Linked Orders"] = ""
            row["Linked Order Count"] = "0"
            row["Order No"] = ""
            row["Order Link Status"] = "No active Operation Order matched by Project ID"
            row["Match Reason"] = "System order-link rule: Sales Project ID is not found in active Operation Project IDs"
    else:
        full = [row for row in operation_records if clean_text(row.get("Project ID")) not in sales_project_ids]
        for row in full:
            row["Order Link Status"] = "No active Sales Project matched by Project ID"
            row["Match Reason"] = "System order-link rule: Operation Project ID is not found in active Sales Project IDs"

    if record_type != "All":
        full = [row for row in full if row.get("Record Type") == record_type]
    if scope == "Sales Board":
        full = [row for row in full if row.get("Record Type") == "Sales"]
    elif scope == "Operation Board":
        full = [row for row in full if row.get("Record Type") == "Operation"]

    full.sort(key=lambda row: (clean_text(row.get("Client Code")), clean_text(row.get("Project ID")), clean_text(row.get("Order No"))))
    returned = full[:limit]
    metadata = {
        "query_mode": "System Order Association Rule",
        "total_searchable_records": len(sales_records) + len(operation_records),
        "total_matched_records": len(full),
        "returned_records": len(returned),
        "full_result_count": len(full),
    }
    return returned, metadata


def _boss_focus_query(*, scope: str, record_type: str, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records = _load_records_for_scope("All" if scope == "Dashboard" else scope, record_type)
    priority = {"Need Decision": 0, "Need Alignment": 1, "Blocked": 2, "Delayed": 3, "Due Soon": 4, "Waiting Client": 5, "Waiting Supplier": 6, "Waiting Internal": 7}
    full: list[dict[str, Any]] = []
    for row in records:
        high_attention = clean_text(row.get("Health Status")) in priority
        ehab_related = "ehab" in _combined_text(row)
        meeting_related = row.get("Review This Week") == "Yes" or clean_text(row.get("Need From Meeting")) or clean_text(row.get("Meeting Focus Reason"))
        decision_related = clean_text(row.get("Request Type")) in {"Decision", "Approval", "Alignment"} or clean_text(row.get("Need Decision From"))
        if high_attention or ehab_related or meeting_related or decision_related:
            item = dict(row)
            item["Match Reason"] = "Boss focus summary: high attention / meeting pool / decision or Ehab-related evidence"
            full.append(item)

    full.sort(key=lambda row: (priority.get(clean_text(row.get("Health Status")), 99), clean_text(row.get("Target Date")) or "9999-12-31", clean_text(row.get("Entity ID"))))
    returned = full[:limit]
    return returned, {
        "query_mode": "Boss Focus Summary",
        "total_searchable_records": len(records),
        "total_matched_records": len(full),
        "returned_records": len(returned),
    }


def _extract_client_terms(query: str) -> list[str]:
    terms: list[str] = []
    for pattern in [r"(?:client|customer)\s+([a-zA-Z0-9_\-]+)", r"客户\s*([\u4e00-\u9fffA-Za-z0-9_\-]+)"]:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            terms.append(match.group(1).strip().lower())
    tokens = _tokenize(query)
    for token in tokens:
        if token not in STOPWORDS and token not in {"open", "issues", "issue", "client", "customer", "客户", "问题"}:
            terms.append(token.lower())
    cleaned: list[str] = []
    for term in terms:
        if term and term not in cleaned:
            cleaned.append(term)
    return cleaned


def _client_open_issues_query(query: str, *, scope: str, record_type: str, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records = _load_records_for_scope("All" if scope == "Dashboard" else scope, record_type)
    terms = _extract_client_terms(query)
    full: list[dict[str, Any]] = []
    for row in records:
        text = _combined_text(row)
        if terms and not any(term in text for term in terms):
            continue
        if not _is_open_issue_record(row):
            continue
        item = dict(row)
        item["Match Reason"] = "Client open issue summary: client keyword + open issue/current follow-up evidence"
        full.append(item)

    full.sort(key=lambda row: (clean_text(row.get("Client Code")), clean_text(row.get("Health Status")), clean_text(row.get("Target Date")) or "9999-12-31", clean_text(row.get("Entity ID"))))
    returned = full[:limit]
    return returned, {
        "query_mode": "Client Open Issues Summary",
        "total_searchable_records": len(records),
        "total_matched_records": len(full),
        "returned_records": len(returned),
        "client_terms": ", ".join(terms),
    }


def _normalise_history_event(row: dict[str, Any], base: dict[str, Any], index: int) -> dict[str, Any]:
    event_type = clean_text(row.get("event_type"))
    note = clean_text(row.get("event_note"))
    old_phase = clean_text(row.get("old_phase"))
    new_phase = clean_text(row.get("new_phase"))
    old_health = clean_text(row.get("old_health"))
    new_health = clean_text(row.get("new_health"))
    old_result = clean_text(row.get("old_result"))
    new_result = clean_text(row.get("new_result"))
    return {
        "Source Module": "Project History",
        "Record Type": clean_text(row.get("entity_type")) or base.get("Record Type"),
        "Source ID": f"H-E{index}",
        "Entity ID": clean_text(row.get("entity_id")) or base.get("Entity ID"),
        "Project ID": clean_text(row.get("project_id")) or base.get("Project ID"),
        "Project Name": base.get("Project Name"),
        "Order No": clean_text(row.get("order_no")) or base.get("Order No"),
        "Client Code": base.get("Client Code"),
        "Current Owner": base.get("Current Owner"),
        "Phase": f"{old_phase} -> {new_phase}" if old_phase or new_phase else base.get("Phase"),
        "Health Status": f"{old_health} -> {new_health}" if old_health or new_health else base.get("Health Status"),
        "Result Status": f"{old_result} -> {new_result}" if old_result or new_result else base.get("Result Status"),
        "Current Progress": event_type,
        "Main Issue": note,
        "Next Step": base.get("Next Step"),
        "Next Step Owner": base.get("Next Step Owner"),
        "Target Date": base.get("Target Date"),
        "History Type": "Event Log",
        "History Time": clean_text(row.get("event_time")),
        "History Note": note or event_type,
        "Old Phase": old_phase,
        "New Phase": new_phase,
        "Old Health": old_health,
        "New Health": new_health,
        "Old Result": old_result,
        "New Result": new_result,
        "Last Event": note or event_type,
        "Match Reason": "Project history from event_logs_v2",
    }


def _normalise_history_snapshot(row: dict[str, Any], base: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "Source Module": "Project History",
        "Record Type": clean_text(row.get("entity_type")) or base.get("Record Type"),
        "Source ID": f"H-S{index}",
        "Entity ID": clean_text(row.get("entity_id")) or base.get("Entity ID"),
        "Project ID": clean_text(row.get("project_id")) or base.get("Project ID"),
        "Project Name": base.get("Project Name"),
        "Order No": clean_text(row.get("order_no")) or base.get("Order No"),
        "Client Code": base.get("Client Code"),
        "Current Owner": base.get("Current Owner"),
        "Phase": clean_text(row.get("phase")),
        "Health Status": clean_text(row.get("health_status")),
        "Result Status": clean_text(row.get("result_status")),
        "Current Progress": clean_text(row.get("progress_summary")),
        "Main Issue": clean_text(row.get("main_issue")),
        "Blocked At": clean_text(row.get("block_point")),
        "Need From Meeting": clean_text(row.get("need_from_meeting")),
        "Next Step": clean_text(row.get("next_step_summary")),
        "Next Step Owner": clean_text(row.get("next_step_owner")),
        "History Type": "Meeting Snapshot",
        "History Time": clean_text(row.get("snapshot_time")),
        "History Note": clean_text(row.get("meeting_note")) or clean_text(row.get("main_issue")),
        "Last Event": clean_text(row.get("meeting_note")) or clean_text(row.get("main_issue")),
        "Match Reason": "Project history from meeting_snapshots_v2",
    }


def _project_history_query(query: str, *, scope: str, record_type: str, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base_records = _load_records_for_scope("Project Details" if scope in {"All", "Dashboard", "Meeting Mode"} else scope, record_type)
    tokens = _tokenize(query)
    scored: list[tuple[float, dict[str, Any], list[str]]] = []
    for record in base_records:
        score, reasons = _score_record(query, record, tokens)
        if score >= 1.2:
            scored.append((score, record, reasons))
    scored.sort(key=lambda item: item[0], reverse=True)
    selected_base = [dict(item[1]) for item in scored[:3]]

    history_rows: list[dict[str, Any]] = []
    for base in selected_base:
        base["Match Reason"] = "Current Project Details record selected for history summary"
        history_rows.append(base)
        entity_type = clean_text(base.get("Record Type"))
        entity_id = clean_text(base.get("Entity ID"))
        if not entity_type or not entity_id:
            continue
        try:
            for idx, event in enumerate(get_record_timeline(entity_type, entity_id)[:20], start=1):
                history_rows.append(_normalise_history_event(event, base, idx))
            for idx, snapshot in enumerate(get_record_snapshots(entity_type, entity_id)[:20], start=1):
                history_rows.append(_normalise_history_snapshot(snapshot, base, idx))
        except Exception:
            pass

    returned = history_rows[:limit]
    return returned, {
        "query_mode": "Project History Summary",
        "total_searchable_records": len(base_records),
        "total_matched_records": len(history_rows),
        "returned_records": len(returned),
    }


def _build_order_association_answer(intent: str, *, output_language: str, records: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    lang = _safe_language(output_language)
    total = int(metadata.get("full_result_count") or metadata.get("total_matched_records") or 0)
    returned = len(records)
    if intent == "projects_without_orders":
        label_en = "Sales projects have no linked active Operation Order by Project ID"
        label_cn = "个 Sales 项目没有通过 Project ID 关联到 active Operation Order"
    elif intent == "projects_with_orders":
        label_en = "Sales projects have linked active Operation Orders by Project ID"
        label_cn = "个 Sales 项目已经通过 Project ID 关联到 active Operation Order"
    else:
        label_en = "Operation orders have no linked active Sales Project by Project ID"
        label_cn = "个 Operation 订单没有通过 Project ID 关联到 active Sales Project"

    names = []
    for row in records[:12]:
        title = clean_text(row.get("Project Name")) or clean_text(row.get("Project ID")) or clean_text(row.get("Order No"))
        pid = clean_text(row.get("Project ID"))
        oid = clean_text(row.get("Order No"))
        suffix = f" ({pid})" if pid else (f" ({oid})" if oid else "")
        names.append(f"- {title}{suffix}")
    detail = "\n".join(names) if names else "No evidence rows are displayed."

    if lang == "Chinese":
        return {
            "direct_answer": f"根据系统现有 Sales Board / Dashboard 订单关联规则，当前共有 {total}{label_cn}。",
            "evidence_summary": "答案依据：复用系统已有的订单关联逻辑，即用 active Sales Project ID 与 active Operation Project ID 进行匹配。",
            "detailed_answer": detail,
            "not_found_or_limitations": "",
        }
    if lang == "Bilingual Chinese and English":
        return {
            "direct_answer": f"根据系统现有 Sales Board / Dashboard 订单关联规则，当前共有 {total}{label_cn}。 / Based on the existing Sales Board / Dashboard order-link rule, {total} {label_en}.",
            "evidence_summary": "答案依据：active Sales Project ID 与 active Operation Project ID 匹配。 / The answer is based on the system order-link rule: active Sales Project ID is matched against active Operation Project ID.",
            "detailed_answer": detail,
            "not_found_or_limitations": "",
        }
    return {
        "direct_answer": f"Based on the existing Sales Board / Dashboard order-link rule, {total} {label_en}.",
        "evidence_summary": "The answer is based on the system order-link rule: active Sales Project ID is matched against active Operation Project ID, using the same order-link logic as the current system.",
        "detailed_answer": detail,
        "not_found_or_limitations": "",
    }

def _search_records(query: str, *, scope: str, record_type: str, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query = clean_text(query)
    tokens = _tokenize(query)
    loaded_records = _load_records_for_scope(scope, record_type)
    records = _apply_deterministic_filters(query, loaded_records)
    scored: list[tuple[float, dict[str, Any], list[str]]] = []

    for record in records:
        score, reasons = _score_record(query, record, tokens)
        if score >= 1.2:
            row = dict(record)
            row["Match Score"] = round(score, 2)
            row["Match Reason"] = "; ".join(reasons[:4])
            scored.append((score, row, reasons))

    scored.sort(
        key=lambda item: (
            item[0],
            item[1].get("Review This Week") == "Yes",
            clean_text(item[1].get("Target Date")),
            clean_text(item[1].get("Entity ID")),
        ),
        reverse=True,
    )

    matched = [item[1] for item in scored[:limit]]
    metadata = {
        "query_mode": "Natural Language Search",
        "total_searchable_records": len(loaded_records),
        "total_records_after_deterministic_filters": len(records),
        "total_matched_records": len(scored),
        "returned_records": len(matched),
        "tokens": tokens,
    }
    return matched, metadata


def _looks_like_dashboard_question(query: str, scope: str) -> bool:
    if scope == "Dashboard":
        return True
    return _has_any(query, INTENT_KEYWORDS["dashboard"])


def _looks_like_meeting_question(query: str, scope: str) -> bool:
    if scope == "Meeting Mode":
        return True
    return _has_any(query, INTENT_KEYWORDS["meeting"])


def _prepare_ai_evidence(records: list[dict[str, Any]], dashboard_rows: list[dict[str, Any]], *, max_rows: int = 50) -> dict[str, Any]:
    evidence_records = []
    for row in records[:max_rows]:
        evidence_records.append(
            {
                "source_id": row.get("Source ID"),
                "source_module": row.get("Source Module"),
                "record_type": row.get("Record Type"),
                "entity_id": row.get("Entity ID"),
                "project_id": row.get("Project ID"),
                "project_name": row.get("Project Name"),
                "order_no": row.get("Order No"),
                "linked_orders": row.get("Linked Orders"),
                "linked_order_count": row.get("Linked Order Count"),
                "order_link_status": row.get("Order Link Status"),
                "client_code": row.get("Client Code"),
                "current_owner": row.get("Current Owner"),
                "phase": row.get("Phase"),
                "health_status": row.get("Health Status"),
                "result_status": row.get("Result Status"),
                "current_progress": row.get("Current Progress"),
                "main_issue": row.get("Main Issue"),
                "blocked_at": row.get("Blocked At"),
                "waiting_for_what": row.get("Waiting For What"),
                "need_from_meeting": row.get("Need From Meeting"),
                "next_step": row.get("Next Step"),
                "next_step_owner": row.get("Next Step Owner"),
                "target_date": row.get("Target Date"),
                "review_this_week": row.get("Review This Week"),
                "meeting_focus_reason": row.get("Meeting Focus Reason"),
                "history_type": row.get("History Type"),
                "history_time": row.get("History Time"),
                "history_note": row.get("History Note"),
                "last_event": row.get("Last Event"),
                "reference_link": row.get("Reference Link"),
                "match_reason": row.get("Match Reason"),
            }
        )

    return {
        "dashboard_metrics": dashboard_rows[:80],
        "system_records": evidence_records,
    }


def _source_summary(records: list[dict[str, Any]], dashboard_rows: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    module_counts = Counter(clean_text(row.get("Source Module")) or "Unknown" for row in records)
    type_counts = Counter(clean_text(row.get("Record Type")) or "Unknown" for row in records)
    final_count = len(records) if records else len(dashboard_rows)
    summary = {
        "query_mode": metadata.get("query_mode", "Natural Language Search"),
        "final_answer_records": final_count,
        "dashboard_metrics": len(dashboard_rows),
        "sales_records": int(type_counts.get("Sales", 0)),
        "operation_records": int(type_counts.get("Operation", 0)),
        "sales_board_records": int(module_counts.get("Sales Board", 0)),
        "operation_board_records": int(module_counts.get("Operation Board", 0)),
        "meeting_mode_records": int(module_counts.get("Meeting Mode", 0)),
        "project_history_records": int(module_counts.get("Project History", 0)),
    }
    if metadata.get("full_result_count") is not None:
        summary["total_final_answer_records"] = metadata.get("full_result_count")
        summary["records_shown"] = len(records)
    if metadata.get("client_terms"):
        summary["client_terms"] = metadata.get("client_terms")
    return summary


def _coerce_source_id_set(value: Any) -> set[str]:
    ids: set[str] = set()
    if isinstance(value, list):
        for item in value:
            text = clean_text(item)
            if text:
                ids.add(text)
    elif isinstance(value, str):
        for item in re.split(r"[,;\n]+", value):
            text = clean_text(item)
            if text:
                ids.add(text)
    return ids


def _source_ids_mentioned_in_answer(answer: dict[str, Any], records: list[dict[str, Any]]) -> set[str]:
    valid_ids = {clean_text(row.get("Source ID")) for row in records if clean_text(row.get("Source ID"))}
    selected = _coerce_source_id_set(answer.get("final_source_ids"))
    selected = {sid for sid in selected if sid in valid_ids}
    if selected:
        return selected

    answer_text = " ".join(
        clean_text(answer.get(key))
        for key in ["direct_answer", "evidence_summary", "detailed_answer", "not_found_or_limitations"]
    )
    for sid in valid_ids:
        if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(sid)}(?![A-Za-z0-9_-])", answer_text):
            selected.add(sid)
    return selected


def _apply_final_condition_filters(query: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not records:
        return records

    lower = _lower(query)
    owner_terms = _extract_owner_terms(query, records)
    final_records = records

    next_step_owner_phrases = [
        "next step owner",
        "next_step_owner",
        "next-step owner",
        "下一步负责人",
        "跟进负责人",
        "next step 负责人",
    ]
    if _has_any(lower, next_step_owner_phrases) and owner_terms:
        candidate = [
            row for row in final_records
            if clean_text(row.get("Next Step"))
            and any(term in _lower(row.get("Next Step Owner")) for term in owner_terms)
        ]
        if candidate:
            final_records = candidate

    current_owner_phrases = ["current owner", "owned by", "owner is", "owner:", "负责人", "当前负责人"]
    if _has_any(lower, current_owner_phrases) and not _has_any(lower, next_step_owner_phrases) and owner_terms:
        candidate = [
            row for row in final_records
            if any(term in _lower(row.get("Current Owner")) for term in owner_terms)
        ]
        if candidate:
            final_records = candidate

    return final_records


def _dedupe_final_records(records: list[dict[str, Any]], *, scope: str) -> list[dict[str, Any]]:
    if not records or scope == "Meeting Mode":
        return records

    def priority(row: dict[str, Any]) -> int:
        module = clean_text(row.get("Source Module"))
        if module in {"Sales Board", "Operation Board"}:
            return 0
        if module == "Project History":
            return 1
        if module == "Meeting Mode":
            return 2
        return 3

    chosen: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in records:
        module = clean_text(row.get("Source Module"))
        if module == "Project History":
            key = (
                clean_text(row.get("Record Type")),
                clean_text(row.get("Project ID")),
                clean_text(row.get("Order No")),
                clean_text(row.get("Source ID")),
            )
        else:
            key = (
                clean_text(row.get("Record Type")),
                clean_text(row.get("Project ID")),
                clean_text(row.get("Order No")) or clean_text(row.get("Entity ID")),
                "",
            )
        existing = chosen.get(key)
        if existing is None or priority(row) < priority(existing):
            chosen[key] = row

    return list(chosen.values())


def _finalize_records_for_display(
    *,
    question: str,
    records: list[dict[str, Any]],
    answer: dict[str, Any],
    scope: str,
) -> list[dict[str, Any]]:
    if not records:
        return records

    selected_ids = _source_ids_mentioned_in_answer(answer, records)
    if selected_ids:
        selected = [row for row in records if clean_text(row.get("Source ID")) in selected_ids]
    else:
        selected = _apply_final_condition_filters(question, records)

    return _dedupe_final_records(selected or records, scope=scope)


def _build_scope_limitations(
    *,
    output_language: str,
    records: list[dict[str, Any]],
    dashboard_rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    scope: str,
    record_type: str,
) -> tuple[str, bool, bool]:
    lang = _safe_language(output_language)
    full_count = metadata.get("full_result_count")
    shown_count = len(records)
    is_truncated = bool(full_count is not None and int(full_count or 0) > shown_count)
    has_scope_limitations = scope != "All" or record_type != "All"

    type_counts = Counter(clean_text(row.get("Record Type")) or "Unknown" for row in records)
    sales_count = int(type_counts.get("Sales", 0))
    operation_count = int(type_counts.get("Operation", 0))

    notes_en: list[str] = []
    notes_cn: list[str] = []

    if is_truncated:
        notes_en.append(f"The system found more final answer records than the current Result Limit. Only the first {shown_count} records are shown.")
        notes_cn.append(f"系统找到的最终结果数量超过当前 Result Limit，因此当前只显示前 {shown_count} 条记录。")

    if has_scope_limitations:
        notes_en.append(f"The search was limited to Scope = {scope}, Record Type = {record_type}.")
        notes_cn.append(f"本次搜索范围限制为 Scope = {scope}, Record Type = {record_type}。")

    if records:
        if sales_count == 0 and operation_count > 0 and record_type == "All":
            notes_en.append("All final answer records are from Operation Board. No final answer records were found in Sales Board.")
            notes_cn.append("所有最终结果均来自 Operation Board；Sales Board 中没有最终结果记录。")
        elif operation_count == 0 and sales_count > 0 and record_type == "All":
            notes_en.append("All final answer records are from Sales Board. No final answer records were found in Operation Board.")
            notes_cn.append("所有最终结果均来自 Sales Board；Operation Board 中没有最终结果记录。")

    if not notes_en and (records or dashboard_rows):
        notes_en.append("All records shown are from the current active system records.")
        notes_cn.append("当前显示的记录均来自系统当前有效记录。")

    if not notes_en and not records and not dashboard_rows:
        notes_en.append("No final answer records were found in the current active system records.")
        notes_cn.append("当前系统有效记录中没有找到最终结果。")

    if lang == "Chinese":
        return " ".join(notes_cn), is_truncated, has_scope_limitations
    if lang == "Bilingual Chinese and English":
        return " ".join(notes_cn) + " / " + " ".join(notes_en), is_truncated, has_scope_limitations
    return " ".join(notes_en), is_truncated, has_scope_limitations


def _safe_language(output_language: str) -> str:
    return output_language if output_language in SUPPORTED_OUTPUT_LANGUAGES else "English"




def _contains_cjk(text: Any) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", clean_text(text)))


def _language_mismatch_for_output(answer: dict[str, Any], output_language: str) -> bool:
    """Detect obvious narrative-language mismatch in model output.

    This is a safety net for UI consistency. Project names, client codes and raw
    system field values are still preserved in tables and exports.
    """
    lang = _safe_language(output_language)
    if lang != "English":
        return False
    # English output should not have Chinese narrative in the core answer sections.
    text = " ".join(clean_text(answer.get(key)) for key in ["direct_answer", "evidence_summary", "detailed_answer"])
    return _contains_cjk(text)


def _record_display_name(record: dict[str, Any]) -> str:
    name = clean_text(record.get("Project Name")) or clean_text(record.get("Entity ID")) or clean_text(record.get("Project ID")) or clean_text(record.get("Order No")) or "Unnamed record"
    project_id = clean_text(record.get("Project ID"))
    order_no = clean_text(record.get("Order No"))
    parts = [name]
    if project_id:
        parts.append(f"Project ID: {project_id}")
    if order_no:
        parts.append(f"Order: {order_no}")
    return " (" + ", ".join(parts[1:]) + ")" if len(parts) > 1 and not name.startswith("(") else name


def _format_record_line(record: dict[str, Any], *, lang: str) -> str:
    name = clean_text(record.get("Project Name")) or clean_text(record.get("Entity ID")) or clean_text(record.get("Project ID")) or clean_text(record.get("Order No")) or "Unnamed record"
    project_id = clean_text(record.get("Project ID"))
    order_no = clean_text(record.get("Order No"))
    owner = clean_text(record.get("Current Owner"))
    phase = clean_text(record.get("Phase"))
    health = clean_text(record.get("Health Status"))
    next_step_owner = clean_text(record.get("Next Step Owner"))
    target_date = clean_text(record.get("Target Date"))
    issue = clean_text(record.get("Main Issue") or record.get("Need From Meeting") or record.get("Meeting Focus Reason") or record.get("Next Step"))

    if lang == "Chinese":
        bits = [name]
        if project_id:
            bits.append(f"Project ID: {project_id}")
        if order_no:
            bits.append(f"Order: {order_no}")
        if owner:
            bits.append(f"负责人: {owner}")
        if phase:
            bits.append(f"阶段: {phase}")
        if health:
            bits.append(f"状态: {health}")
        if next_step_owner:
            bits.append(f"下一步负责人: {next_step_owner}")
        if target_date:
            bits.append(f"目标日期: {target_date}")
        if issue:
            bits.append(f"依据: {issue}")
        return "；".join(bits) + "。"

    bits = [name]
    if project_id:
        bits.append(f"Project ID: {project_id}")
    if order_no:
        bits.append(f"Order: {order_no}")
    if owner:
        bits.append(f"Owner: {owner}")
    if phase:
        bits.append(f"Phase: {phase}")
    if health:
        bits.append(f"Health: {health}")
    if next_step_owner:
        bits.append(f"Next Step Owner: {next_step_owner}")
    if target_date:
        bits.append(f"Target Date: {target_date}")
    if issue:
        bits.append(f"Evidence: {issue}")
    return "; ".join(bits) + "."


def _build_language_safe_final_answer(
    *,
    question: str,
    output_language: str,
    final_records: list[dict[str, Any]],
    dashboard_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    lang = _safe_language(output_language)
    count = len(final_records)
    metric_count = len(dashboard_rows)

    sales = [row for row in final_records if clean_text(row.get("Record Type")) == "Sales"]
    operation = [row for row in final_records if clean_text(row.get("Record Type")) == "Operation"]

    names = [clean_text(row.get("Project Name")) or clean_text(row.get("Entity ID")) or clean_text(row.get("Project ID")) or clean_text(row.get("Order No")) for row in final_records]
    names = [name for name in names if name]
    name_text = ", ".join(names[:12])

    if lang == "Chinese":
        direct = f"根据当前系统记录，本次查询共有 {count} 条最终结果。" + (f" 包括：{name_text}。" if name_text else "")
        details: list[str] = []
        if sales:
            details.append("Sales Board:\n" + "\n".join(f"{idx}. {_format_record_line(row, lang=lang)}" for idx, row in enumerate(sales, start=1)))
        if operation:
            details.append("Operation Board:\n" + "\n".join(f"{idx}. {_format_record_line(row, lang=lang)}" for idx, row in enumerate(operation, start=1)))
        if not details and dashboard_rows:
            details.append("Dashboard:\n" + "\n".join(f"- {row.get('Metric')}: {row.get('Value')}" for row in dashboard_rows))
        detailed = "\n\n".join(details) if details else "未找到可显示的最终记录。"
        evidence = "答案基于当前系统数据中的最终结果记录。"
    elif lang == "Bilingual Chinese and English":
        direct = (
            f"根据当前系统记录，本次查询共有 {count} 条最终结果。 / "
            f"Based on current system records, this query returned {count} final answer record(s)."
            + (f" Records / 记录: {name_text}." if name_text else "")
        )
        details = []
        if sales:
            details.append("Sales Board:\n" + "\n".join(f"{idx}. {_format_record_line(row, lang='English')}" for idx, row in enumerate(sales, start=1)))
        if operation:
            details.append("Operation Board:\n" + "\n".join(f"{idx}. {_format_record_line(row, lang='English')}" for idx, row in enumerate(operation, start=1)))
        if not details and dashboard_rows:
            details.append("Dashboard:\n" + "\n".join(f"- {row.get('Metric')}: {row.get('Value')}" for row in dashboard_rows))
        detailed = "\n\n".join(details) if details else "未找到可显示的最终记录。 / No final records are available for display."
        evidence = "答案基于当前系统数据中的最终结果记录。 / The answer is based on the final records found in the current system data."
    else:
        direct = f"Based on current system records, this query returned {count} final answer record(s)." + (f" Records: {name_text}." if name_text else "")
        details = []
        if sales:
            details.append("Sales Board:\n" + "\n".join(f"{idx}. {_format_record_line(row, lang='English')}" for idx, row in enumerate(sales, start=1)))
        if operation:
            details.append("Operation Board:\n" + "\n".join(f"{idx}. {_format_record_line(row, lang='English')}" for idx, row in enumerate(operation, start=1)))
        if not details and dashboard_rows:
            details.append("Dashboard:\n" + "\n".join(f"- {row.get('Metric')}: {row.get('Value')}" for row in dashboard_rows))
        detailed = "\n\n".join(details) if details else f"Dashboard metrics returned: {metric_count}."
        evidence = "The answer is based on the final records found in the current system data."

    return {
        "direct_answer": direct,
        "evidence_summary": evidence,
        "detailed_answer": detailed,
        "not_found_or_limitations": "",
        "final_source_ids": [clean_text(row.get("Source ID")) for row in final_records if clean_text(row.get("Source ID"))],
    }


def _fallback_answer(*, question: str, output_language: str, records: list[dict[str, Any]], dashboard_rows: list[dict[str, Any]]) -> dict[str, Any]:
    lang = _safe_language(output_language)
    count = len(records)
    metric_count = len(dashboard_rows)

    if lang == "Chinese":
        direct = f"已根据当前系统记录找到 {count} 条最终结果。" if count else f"已根据 Dashboard 找到 {metric_count} 条统计信息。"
        detailed = "AI 总结暂时不可用。下面的表格是本次查询使用的真实系统记录。"
        limitation = "未在系统记录中出现的信息不会显示。"
    elif lang == "Bilingual Chinese and English":
        direct = (
            f"已根据当前系统记录找到 {count} 条最终结果。 / Found {count} final answer record(s) from current system records."
            if count
            else f"已根据 Dashboard 找到 {metric_count} 条统计信息。 / Found {metric_count} dashboard metric row(s)."
        )
        detailed = "AI summary is not available now. / AI 总结暂时不可用。Please review the evidence tables below. / 请查看下面的证据表格。"
        limitation = "当前显示的记录均来自系统当前有效记录。"
    else:
        direct = f"Found {count} final answer record(s) from current system records." if count else f"Found {metric_count} dashboard metric row(s)."
        detailed = "AI summary is not available now. The tables below show the real system records used for this query."
        limitation = "Information not found in system records is not shown."

    return {
        "direct_answer": direct,
        "evidence_summary": f"Final answer records: {count}; Dashboard metrics: {metric_count}; Question: {question}",
        "detailed_answer": detailed,
        "not_found_or_limitations": limitation,
    }


def _not_found_answer(output_language: str) -> dict[str, Any]:
    lang = _safe_language(output_language)
    if lang == "Chinese":
        return {
            "direct_answer": "搜索不到相关记录。",
            "evidence_summary": "当前系统数据中没有找到最终结果记录。",
            "detailed_answer": "请尝试使用 Project ID、Order No、Client Code、Project Name、Owner、状态或会议关键词重新搜索。",
            "not_found_or_limitations": "没有系统记录作为证据，因此未调用 AI 生成业务结论。",
        }
    if lang == "Bilingual Chinese and English":
        return {
            "direct_answer": "搜索不到相关记录。 / No final answer record was found.",
            "evidence_summary": "当前系统数据中没有找到最终结果记录。 / No final answer record exists in the current system data.",
            "detailed_answer": "Please try Project ID, Order No, Client Code, Project Name, Owner, status, or meeting keywords. / 请尝试使用项目编号、订单号、客户代码、项目名称、负责人、状态或会议关键词。",
            "not_found_or_limitations": "No system evidence was found, so no AI business conclusion was generated. / 没有系统记录作为证据，因此未生成业务结论。",
        }
    return {
        "direct_answer": "No final answer record was found.",
        "evidence_summary": "No final answer record exists in the current system data.",
        "detailed_answer": "Please try Project ID, Order No, Client Code, Project Name, Owner, status, or meeting keywords.",
        "not_found_or_limitations": "No system evidence was found, so no AI business conclusion was generated.",
    }


def ask_ai_project_assistant(
    *,
    question: str,
    output_language: str = "English",
    scope: str = "All",
    record_type: str = "All",
    result_limit: int = 20,
) -> dict[str, Any]:
    """Read-only natural-language query over current Zenith Project Tracker data.

    Important safety design:
    - Database writes are never performed here.
    - AI is called only after deterministic system-data retrieval.
    - If no system evidence is found, a not-found answer is returned without asking the model to infer.
    """
    question = clean_text(question)
    if not question:
        raise AIProjectAssistantError("Please enter a question first.")

    scope = scope if scope in SUPPORTED_SCOPES else "All"
    record_type = record_type if record_type in SUPPORTED_RECORD_TYPES else "All"
    output_language = _safe_language(output_language)
    result_limit = max(1, min(int(result_limit or 20), 50))

    dashboard_rows: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {"total_searchable_records": 0, "total_matched_records": 0, "returned_records": 0}

    dashboard_question = _looks_like_dashboard_question(question, scope)
    meeting_question = _looks_like_meeting_question(question, scope)
    special_intent = _detect_special_intent(question)

    if dashboard_question:
        dashboard_rows = _build_dashboard_rows()

    if special_intent in {"projects_with_orders", "projects_without_orders", "unlinked_operation_orders"}:
        records, metadata = _order_association_query(special_intent, scope=scope, record_type=record_type, limit=result_limit)
        if not records:
            answer = _not_found_answer(output_language)
            limitation_text, is_truncated, has_scope_limitations = _build_scope_limitations(
                output_language=output_language,
                records=[],
                dashboard_rows=[],
                metadata=metadata,
                scope=scope,
                record_type=record_type,
            )
            answer["not_found_or_limitations"] = limitation_text
            return {
                "found": False,
                "question": question,
                "answer": answer,
                "source_summary": _source_summary([], [], metadata),
                "records": [],
                "dashboard_rows": [],
                "scope": scope,
                "record_type": record_type,
                "output_language": output_language,
                "is_truncated": is_truncated,
                "has_scope_limitations": has_scope_limitations,
            }
        records = _dedupe_final_records(records, scope=scope)
        answer = _build_order_association_answer(special_intent, output_language=output_language, records=records, metadata=metadata)
        limitation_text, is_truncated, has_scope_limitations = _build_scope_limitations(
            output_language=output_language,
            records=records,
            dashboard_rows=[],
            metadata=metadata,
            scope=scope,
            record_type=record_type,
        )
        answer["not_found_or_limitations"] = limitation_text
        return {
            "found": bool(records),
            "question": question,
            "answer": answer,
            "source_summary": _source_summary(records, [], metadata),
            "records": records,
            "dashboard_rows": [],
            "scope": scope,
            "record_type": record_type,
            "output_language": output_language,
            "ai_error": "",
            "is_truncated": is_truncated,
            "has_scope_limitations": has_scope_limitations,
        }

    if special_intent == "boss_summary":
        records, metadata = _boss_focus_query(scope=scope, record_type=record_type, limit=result_limit)
    elif special_intent == "client_open_issues":
        records, metadata = _client_open_issues_query(question, scope=scope, record_type=record_type, limit=result_limit)
    elif special_intent == "project_history":
        records, metadata = _project_history_query(question, scope=scope, record_type=record_type, limit=result_limit)
    else:
        search_scope = "Meeting Mode" if meeting_question and scope == "All" else scope
        if scope != "Dashboard":
            records, metadata = _search_records(question, scope=search_scope, record_type=record_type, limit=result_limit)

    # Dashboard-only questions are valid even when they do not return project rows.
    if not records and not dashboard_rows:
        answer = _not_found_answer(output_language)
        limitation_text, is_truncated, has_scope_limitations = _build_scope_limitations(
            output_language=output_language,
            records=[],
            dashboard_rows=[],
            metadata=metadata,
            scope=scope,
            record_type=record_type,
        )
        answer["not_found_or_limitations"] = limitation_text
        return {
            "found": False,
            "question": question,
            "answer": answer,
            "source_summary": _source_summary([], [], metadata),
            "records": [],
            "dashboard_rows": [],
            "scope": scope,
            "record_type": record_type,
            "output_language": output_language,
            "is_truncated": is_truncated,
            "has_scope_limitations": has_scope_limitations,
        }

    evidence_payload = _prepare_ai_evidence(records, dashboard_rows, max_rows=result_limit)

    system_prompt = """
You are the AI Project Assistant for Zenith Project Tracker System.

Role:
- You are a read-only intelligent query layer.
- You answer user questions only from the provided system evidence.
- You must not create, update, delete, assume, or invent any business data.

Hard rules:
- Only use the provided dashboard_metrics and system_records.
- Do not invent project names, order numbers, clients, owners, dates, statuses, issues, next steps, decisions, suppliers, testing results, or links.
- If the evidence does not contain the answer, say it is not found in current system records.
- Do not recommend changing system records.
- Give the direct answer first, then evidence-based details.
- For order association answers, respect the system order-link rule evidence rather than guessing from wording.
- For boss, client and history summaries, summarise only the evidence rows provided.
- Keep the reply clear, concise, and complete.

Language rule:
- The requested_output_language value is mandatory and overrides the language of the user's question.
- If requested_output_language is "English", write all narrative text, labels, explanations and summaries in English only. Do not mix Chinese narrative into the answer. Keep project names, order numbers, client codes and raw system field values unchanged when needed.
- If requested_output_language is "Chinese", write the narrative text in Simplified Chinese. Keep project names, order numbers and client codes unchanged.
- If requested_output_language is "Bilingual Chinese and English", provide a clearly bilingual answer rather than random mixed-language text.

Return JSON only with exactly these keys:
{
  "direct_answer": "...",
  "evidence_summary": "...",
  "detailed_answer": "...",
  "not_found_or_limitations": "...",
  "final_source_ids": ["Source ID values that directly satisfy the user's question"]
}

Important display rule:
- final_source_ids must include only records that truly answer the user's question.
- Do not include records that were merely checked or used as candidates.
- Do not mention candidate record counts, checked record counts, or internal search counts in the user-facing answer.
- Use "final answer records" rather than "matched records" when describing the result count.
"""

    user_prompt = json.dumps(
        {
            "user_question": question,
            "requested_output_language": output_language,
            "search_scope": scope,
            "record_type_filter": record_type,
            "search_context": {"query_mode": metadata.get("query_mode", "Natural Language Search")},
            "special_intent": special_intent,
            "evidence": evidence_payload,
            "required_answer_style": (
                "Direct answer first. Then summarize only the final answer records by Sales Board, Operation Board, Dashboard, Project Details, and Meeting Mode when applicable. "
                "Do not mention candidate records or internal checked records. Follow requested_output_language strictly; do not mix languages unless bilingual output is selected."
            ),
        },
        ensure_ascii=False,
        indent=2,
    )

    ai_error = ""
    try:
        answer = call_deepseek_json(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.05)
    except Exception as exc:
        # Keep the assistant usable if the model API is temporarily unavailable. The evidence table
        # is still deterministic and read-only. The UI will show this message so the user knows
        # the answer is a safe fallback rather than a full model-generated summary.
        ai_error = str(exc)
        answer = _fallback_answer(question=question, output_language=output_language, records=records, dashboard_rows=dashboard_rows)

    for key in ["direct_answer", "evidence_summary", "detailed_answer", "not_found_or_limitations"]:
        answer[key] = clean_text(answer.get(key))

    if records and special_intent == "natural_search":
        final_records = _finalize_records_for_display(question=question, records=records, answer=answer, scope=scope)
    else:
        final_records = _dedupe_final_records(records, scope=scope)

    limitation_text, is_truncated, has_scope_limitations = _build_scope_limitations(
        output_language=output_language,
        records=final_records,
        dashboard_rows=dashboard_rows,
        metadata=metadata,
        scope=scope,
        record_type=record_type,
    )

    if _language_mismatch_for_output(answer, output_language):
        safe_answer = _build_language_safe_final_answer(
            question=question,
            output_language=output_language,
            final_records=final_records,
            dashboard_rows=dashboard_rows,
        )
        answer.update(safe_answer)

    answer["not_found_or_limitations"] = limitation_text
    source_summary = _source_summary(final_records, dashboard_rows, metadata)

    return {
        "found": True,
        "question": question,
        "answer": answer,
        "source_summary": source_summary,
        "records": final_records,
        "dashboard_rows": dashboard_rows,
        "scope": scope,
        "record_type": record_type,
        "output_language": output_language,
        "ai_error": ai_error,
        "is_truncated": is_truncated,
        "has_scope_limitations": has_scope_limitations,
    }


def records_to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=EVIDENCE_COLUMNS)
    frame = pd.DataFrame(records)
    # Streamlit/Arrow fails when duplicate columns are passed. Keep the first occurrence only.
    frame = frame.loc[:, ~frame.columns.duplicated()]
    ordered = [col for col in EVIDENCE_COLUMNS if col in frame.columns]
    leading = [col for col in ["Match Score"] if col in frame.columns]
    trailing = [col for col in ["Match Reason"] if col in frame.columns]
    used = set(ordered + leading + trailing)
    extra = [col for col in frame.columns if col not in used]
    final_columns = leading + ordered + trailing + extra
    return frame.loc[:, final_columns].fillna("")


def dashboard_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=DASHBOARD_COLUMNS)
    frame = pd.DataFrame(rows)
    frame = frame.loc[:, ~frame.columns.duplicated()]
    return frame[[col for col in DASHBOARD_COLUMNS if col in frame.columns]].fillna("")


def source_summary_to_dataframe(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [{"Item": key.replace("_", " ").title(), "Value": value} for key, value in summary.items()]
    return pd.DataFrame(rows)


def build_text_export(result: dict[str, Any]) -> str:
    answer = result.get("answer") or {}
    summary = result.get("source_summary") or {}
    lines = [
        "AI Project Assistant Answer",
        "=" * 32,
        f"Generated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "",
        "Question:",
        clean_text(result.get("question")),
        "",
        "Direct Answer:",
        clean_text(answer.get("direct_answer")),
        "",
        "Based on System Records:",
        clean_text(answer.get("evidence_summary")),
        "",
        "Detailed Answer:",
        clean_text(answer.get("detailed_answer")),
        "",
        "Search Scope and Limitations:",
        clean_text(answer.get("not_found_or_limitations")),
        "",
        "Source Summary:",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")

    records = result.get("records") or []
    if records:
        lines.extend(["", "Final Answer Records:"])
        for index, record in enumerate(records, start=1):
            lines.append(
                f"{index}. [{record.get('Source Module')}] {record.get('Record Type')} | "
                f"Entity ID: {record.get('Entity ID') or '-'} | Project ID: {record.get('Project ID') or '-'} | "
                f"Order No: {record.get('Order No') or '-'} | Client: {record.get('Client Code') or '-'} | "
                f"Order Link: {record.get('Order Link Status') or '-'} | "
                f"Health: {record.get('Health Status') or '-'} | Result: {record.get('Result Status') or '-'} | "
                f"Main Issue: {record.get('Main Issue') or '-'} | Next Step: {record.get('Next Step') or '-'} | "
                f"Target Date: {record.get('Target Date') or '-'} | "
                f"History: {record.get('History Type') or '-'} {record.get('History Time') or ''} {record.get('History Note') or ''}"
            )

    dashboard_rows = result.get("dashboard_rows") or []
    if dashboard_rows:
        lines.extend(["", "Dashboard Metrics:"])
        for row in dashboard_rows:
            lines.append(f"- {row.get('Metric')}: {row.get('Value')}")

    return "\n".join(lines).strip() + "\n"


def dataframe_to_csv_bytes(frame: pd.DataFrame) -> bytes:
    output = io.StringIO()
    frame.to_csv(output, index=False, quoting=csv.QUOTE_MINIMAL)
    return output.getvalue().encode("utf-8-sig")
