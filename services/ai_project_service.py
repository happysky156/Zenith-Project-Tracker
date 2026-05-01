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
from services.project_service import get_dashboard_metrics, get_meeting_pool


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
    "with_orders": ["with orders", "have orders", "linked order", "projects with orders", "有订单", "已有订单", "关联订单"],
    "without_orders": ["without orders", "no order", "projects without orders", "没有订单", "无订单", "未下单"],
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
    # Default repository behaviour excludes archived records. This is intentional.
    return [_normalise_sales_row(row, source_id=f"S{idx + 1}") for idx, row in enumerate(list_sales_projects())]


def _load_operation_records() -> list[dict[str, Any]]:
    # Default repository behaviour excludes archived records. This is intentional.
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


def _search_records(query: str, *, scope: str, record_type: str, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query = clean_text(query)
    tokens = _tokenize(query)
    records = _load_records_for_scope(scope, record_type)
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
        "total_searchable_records": len(records),
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
                "last_event": row.get("Last Event"),
                "reference_link": row.get("Reference Link"),
                "match_reason": row.get("Match Reason"),
            }
        )

    return {
        "dashboard_metrics": dashboard_rows[:80],
        "matched_records": evidence_records,
    }


def _source_summary(records: list[dict[str, Any]], dashboard_rows: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    module_counts = Counter(clean_text(row.get("Source Module")) or "Unknown" for row in records)
    type_counts = Counter(clean_text(row.get("Record Type")) or "Unknown" for row in records)
    return {
        "matched_records": len(records),
        "dashboard_metrics": len(dashboard_rows),
        "sales_records": int(type_counts.get("Sales", 0)),
        "operation_records": int(type_counts.get("Operation", 0)),
        "sales_board_records": int(module_counts.get("Sales Board", 0)),
        "operation_board_records": int(module_counts.get("Operation Board", 0)),
        "meeting_mode_records": int(module_counts.get("Meeting Mode", 0)),
        "archived_records": "Excluded by default",
        "total_searchable_records": metadata.get("total_searchable_records", 0),
        "total_matched_records_before_limit": metadata.get("total_matched_records", 0),
        "returned_records": metadata.get("returned_records", len(records)),
    }


def _safe_language(output_language: str) -> str:
    return output_language if output_language in SUPPORTED_OUTPUT_LANGUAGES else "English"


def _fallback_answer(*, question: str, output_language: str, records: list[dict[str, Any]], dashboard_rows: list[dict[str, Any]]) -> dict[str, Any]:
    lang = _safe_language(output_language)
    count = len(records)
    metric_count = len(dashboard_rows)

    if lang == "Chinese":
        direct = f"已根据当前系统记录找到 {count} 条匹配记录。" if count else f"已根据 Dashboard 找到 {metric_count} 条统计信息。"
        detailed = "AI 总结暂时不可用。下面的表格是本次查询使用的真实系统记录。"
        limitation = "默认不包含 archived records；未在系统记录中出现的信息不会显示。"
    elif lang == "Bilingual Chinese and English":
        direct = (
            f"已根据当前系统记录找到 {count} 条匹配记录。 / Found {count} matching record(s) from current system records."
            if count
            else f"已根据 Dashboard 找到 {metric_count} 条统计信息。 / Found {metric_count} dashboard metric row(s)."
        )
        detailed = "AI summary is not available now. / AI 总结暂时不可用。Please review the evidence tables below. / 请查看下面的证据表格。"
        limitation = "Archived records are excluded by default. / 默认不包含 archived records。"
    else:
        direct = f"Found {count} matching record(s) from current system records." if count else f"Found {metric_count} dashboard metric row(s)."
        detailed = "AI summary is not available now. The tables below show the real system records used for this query."
        limitation = "Archived records are excluded by default. Information not found in system records is not shown."

    return {
        "direct_answer": direct,
        "evidence_summary": f"Matched records: {count}; Dashboard metrics: {metric_count}; Question: {question}",
        "detailed_answer": detailed,
        "not_found_or_limitations": limitation,
    }


def _not_found_answer(output_language: str) -> dict[str, Any]:
    lang = _safe_language(output_language)
    if lang == "Chinese":
        return {
            "direct_answer": "搜索不到相关记录。",
            "evidence_summary": "当前系统数据中没有找到匹配记录。Archived records 默认不包含在查询范围内。",
            "detailed_answer": "请尝试使用 Project ID、Order No、Client Code、Project Name、Owner、状态或会议关键词重新搜索。",
            "not_found_or_limitations": "没有系统记录作为证据，因此未调用 AI 生成业务结论。",
        }
    if lang == "Bilingual Chinese and English":
        return {
            "direct_answer": "搜索不到相关记录。 / No matching record was found.",
            "evidence_summary": "当前系统数据中没有找到匹配记录。 / No matched record exists in the current system data. Archived records are excluded by default.",
            "detailed_answer": "Please try Project ID, Order No, Client Code, Project Name, Owner, status, or meeting keywords. / 请尝试使用项目编号、订单号、客户代码、项目名称、负责人、状态或会议关键词。",
            "not_found_or_limitations": "No system evidence was found, so no AI business conclusion was generated. / 没有系统记录作为证据，因此未生成业务结论。",
        }
    return {
        "direct_answer": "No matching record was found.",
        "evidence_summary": "No matched record exists in the current system data. Archived records are excluded by default.",
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
    - Repositories are called with their default behaviour, which excludes archived records.
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

    if dashboard_question:
        dashboard_rows = _build_dashboard_rows()

    search_scope = "Meeting Mode" if meeting_question and scope == "All" else scope
    if scope != "Dashboard":
        records, metadata = _search_records(question, scope=search_scope, record_type=record_type, limit=result_limit)

    # Dashboard-only questions are valid even when they do not return project rows.
    if not records and not dashboard_rows:
        answer = _not_found_answer(output_language)
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
        }

    evidence_payload = _prepare_ai_evidence(records, dashboard_rows, max_rows=result_limit)
    source_summary = _source_summary(records, dashboard_rows, metadata)

    system_prompt = """
You are the AI Project Assistant for Zenith Project Tracker System.

Role:
- You are a read-only intelligent query layer.
- You answer user questions only from the provided system evidence.
- You must not create, update, delete, assume, or invent any business data.

Hard rules:
- Only use the provided dashboard_metrics and matched_records.
- Do not invent project names, order numbers, clients, owners, dates, statuses, issues, next steps, decisions, suppliers, testing results, or links.
- If the evidence does not contain the answer, say it is not found in current system records.
- Do not recommend changing system records.
- Archived records are excluded by default.
- Give the direct answer first, then evidence-based details.
- Keep the reply clear, concise, and complete.

Return JSON only with exactly these keys:
{
  "direct_answer": "...",
  "evidence_summary": "...",
  "detailed_answer": "...",
  "not_found_or_limitations": "..."
}
"""

    user_prompt = json.dumps(
        {
            "user_question": question,
            "requested_output_language": output_language,
            "search_scope": scope,
            "record_type_filter": record_type,
            "source_summary": source_summary,
            "evidence": evidence_payload,
            "required_answer_style": "Direct answer first. Then summarize by Sales Board, Operation Board, Dashboard, Project Details, and Meeting Mode when applicable.",
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

    return {
        "found": True,
        "question": question,
        "answer": answer,
        "source_summary": source_summary,
        "records": records,
        "dashboard_rows": dashboard_rows,
        "scope": scope,
        "record_type": record_type,
        "output_language": output_language,
        "ai_error": ai_error,
    }


def records_to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=EVIDENCE_COLUMNS)
    frame = pd.DataFrame(records)
    ordered = [col for col in EVIDENCE_COLUMNS if col in frame.columns]
    extra = [col for col in frame.columns if col not in ordered and col not in {"Match Score"}]
    if "Match Score" in frame.columns:
        ordered = ["Match Score"] + ordered
    if "Match Reason" in frame.columns:
        ordered = ordered + ["Match Reason"]
    return frame[ordered + extra]


def dashboard_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=DASHBOARD_COLUMNS)
    return pd.DataFrame(rows)[DASHBOARD_COLUMNS]


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
        "Archived Records: Excluded by default",
        "",
        "Question:",
        clean_text(result.get("question")),
        "",
        "Direct Answer:",
        clean_text(answer.get("direct_answer")),
        "",
        "Evidence Summary:",
        clean_text(answer.get("evidence_summary")),
        "",
        "Detailed Answer:",
        clean_text(answer.get("detailed_answer")),
        "",
        "Not Found / Limitations:",
        clean_text(answer.get("not_found_or_limitations")),
        "",
        "Source Summary:",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")

    records = result.get("records") or []
    if records:
        lines.extend(["", "Evidence Records:"])
        for index, record in enumerate(records, start=1):
            lines.append(
                f"{index}. [{record.get('Source Module')}] {record.get('Record Type')} | "
                f"Entity ID: {record.get('Entity ID') or '-'} | Project ID: {record.get('Project ID') or '-'} | "
                f"Order No: {record.get('Order No') or '-'} | Client: {record.get('Client Code') or '-'} | "
                f"Health: {record.get('Health Status') or '-'} | Result: {record.get('Result Status') or '-'} | "
                f"Main Issue: {record.get('Main Issue') or '-'} | Next Step: {record.get('Next Step') or '-'} | "
                f"Target Date: {record.get('Target Date') or '-'}"
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
