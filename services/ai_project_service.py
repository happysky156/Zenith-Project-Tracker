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
SUPPORTED_SCOPES = [
    "All",
    "Sales Board",
    "Operation Board",
    "Dashboard",
    "Project Details",
    "Meeting Mode",
    "Supplier Details",
    "Price Comparison",
    "Index Center",
    "Order Details",
]
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
    "Supplier Code",
    "Supplier ID",
    "Supplier Name",
    "RFQ Item Ref",
    "Item Option",
    "Item Spec",
    "Supplier Unit Cost",
    "Currency",
    "MOQ",
    "Lead Time",
    "Quote Date",
    "Index Name",
    "Index Value",
    "Index Date",
    "Fetch Status",
    "Order Qty",
    "Gross Profit",
    "Extension Summary",
    "Extension Details",
    "Relevance Tier",
    "Related By",
    "Suggested Answer Use",
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
    "supplier_details": ["supplier details", "supplier detail", "supplier master", "supplier code", "supplier name", "supplier", "vendor", "供应商资料", "供应商详情", "供应商代码", "供应商名称", "供应商"],
    "price_comparison": ["price comparison", "supplier quote", "supplier quotation", "rfq item", "rfq item ref", "comparison item", "quote history", "报价对比", "供应商报价", "报价比较", "RFQ", "价格对比"],
    "index_center": ["index center", "daily index", "market index", "fx", "exchange rate", "usd/cny", "hkd/cny", "gbp/cny", "freight index", "material index", "指数", "汇率", "材料价格", "运费", "每日指数"],
    "order_details": ["order details", "order detail", "order item", "gross profit", "gp", "production status", "shipment status", "inspection status", "订单明细", "订单详情", "毛利", "出货状态", "生产状态", "查货状态"],
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "at", "by", "with",
    "show", "me", "what", "which", "who", "when", "where", "why", "how", "many", "all",
    "please", "project", "projects", "order", "orders", "current", "system", "records", "record",
}

# Read-only AI configuration. These rules help the assistant connect existing records
# without changing business logic or writing data.
AI_MODULE_SOURCE_PRIORITY = [
    "Sales Board",
    "Operation Board",
    "Meeting Mode",
    "Project History",
    "Supplier Details",
    "Price Comparison",
    "Order Details",
    "Index Center",
    "Dashboard",
]
AI_JOIN_KEYS = [
    "project_id",
    "supplier_code",
    "supplier_id",
    "order_no",
    "rfq_item_ref",
    "item_option",
    "index_name",
    "index_code",
]
AI_REVIEW_RULES = {
    "price_comparison": [
        "missing price",
        "missing currency",
        "missing MOQ",
        "missing lead time",
        "missing quote date",
        "missing supplier code",
        "supplier not matched or supplier name missing",
        "price is zero or negative",
    ],
    "index_center": [
        "fetch_status is Failed",
        "fetch_status is Carry Forward",
        "confirmed is false where manual confirmation is expected",
    ],
    "order_details": [
        "missing gross profit",
        "missing supplier code",
        "open production / inspection / shipment issue",
    ],
}
AI_ANSWER_TEMPLATES = {
    "project": "Project Summary → Current Records → Quotations / Suppliers → Orders → Review Points → Evidence",
    "supplier": "Supplier Master Data → Related Quotations → Related Orders → Review Points → Evidence",
    "price_comparison": "Supplier Quotes → Lowest / Highest → Completeness / Review Points → Selection Status → Evidence",
    "index": "Latest Index Value → Source / Status / Confirmed → Limitations → Evidence",
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



# -----------------------------------------------------------------------------
# Read-only extension module evidence for AI Project Assistant
# -----------------------------------------------------------------------------

AI_EXTENSION_SCOPES = {"Supplier Details", "Price Comparison", "Index Center", "Order Details"}

AI_SCOPE_TO_EXTENSION_MODULES: dict[str, tuple[str, ...]] = {
    "Supplier Details": ("Supplier Details",),
    "Price Comparison": ("Supplier Price Comparison",),
    "Index Center": ("Daily Market Indices", "Index Config", "Index Snapshot", "Index Alert Rules", "Index Alert Events", "Freight Index"),
    "Order Details": ("Order Details",),
}

AI_EXTENSION_SOURCE_NAMES: dict[str, str] = {
    "Supplier Details": "Supplier Details",
    "Supplier Price Comparison": "Price Comparison",
    "Daily Market Indices": "Index Center",
    "Index Config": "Index Center",
    "Index Snapshot": "Index Center",
    "Index Alert Rules": "Index Center",
    "Index Alert Events": "Index Center",
    "Freight Index": "Index Center",
    "Order Details": "Order Details",
}


def _detail_pairs(row: dict[str, Any], fields: list[tuple[str, str]]) -> str:
    parts: list[str] = []
    for key, label in fields:
        value = clean_text(row.get(key))
        if value:
            parts.append(f"{label}: {value}")
    return " | ".join(parts)


def _normalise_extension_row(module_name: str, row: dict[str, Any], index: int) -> dict[str, Any]:
    """Convert extension rows into the same read-only evidence shape used by the AI assistant.

    This does not update or infer business data. It only exposes existing module records
    as searchable evidence for the read-only AI Project Assistant.
    """
    source_module = AI_EXTENSION_SOURCE_NAMES.get(module_name, module_name)
    source_prefix = {
        "Supplier Details": "SUP",
        "Supplier Price Comparison": "PC",
        "Daily Market Indices": "IDX",
        "Index Config": "ICFG",
        "Index Snapshot": "ISNP",
        "Index Alert Rules": "IAR",
        "Index Alert Events": "IAE",
        "Freight Index": "FRT",
        "Order Details": "OD",
    }.get(module_name, "EXT")

    source_id = clean_text(
        row.get("supplier_id")
        or row.get("supplier_quote_id")
        or row.get("daily_index_id")
        or row.get("index_config_id")
        or row.get("index_snapshot_id")
        or row.get("freight_index_id")
        or row.get("order_detail_id")
        or f"{source_prefix}-{index + 1}"
    )
    entity_id = source_id
    project_id = clean_text(row.get("project_id") or row.get("last_project_id"))
    order_no = clean_text(row.get("order_no") or row.get("last_order_no"))

    if module_name == "Supplier Details":
        summary = _detail_pairs(row, [
            ("supplier_code", "Supplier Code"),
            ("supplier_name", "Supplier Name"),
            ("active_status", "Active"),
            ("quality_risk", "Quality Risk"),
            ("commercial_risk", "Commercial Risk"),
            ("main_products", "Main Products"),
            ("main_process", "Main Process"),
            ("capability_tags", "Capability Tags"),
            ("risk_summary", "Risk Summary"),
        ])
        details = _detail_pairs(row, [
            ("supplier_short_name", "Short Name"),
            ("company_type", "Company Type"),
            ("country", "Country"),
            ("province", "Province"),
            ("city", "City"),
            ("website_primary", "Website"),
            ("primary_contact_name", "Contact"),
            ("primary_contact_mobile", "Mobile"),
            ("primary_contact_email", "Email"),
            ("certificate", "Certificate"),
            ("nda_status", "NDA"),
            ("audit_status", "Audit"),
            ("catalogue_status", "Catalogue"),
            ("payment_terms", "Payment Terms"),
            ("lead_time", "Lead Time"),
            ("last_order_no", "Last Order"),
            ("last_project_id", "Last Project"),
            ("price_comparison_count", "Price Comparison Count"),
            ("order_count", "Order Count"),
            ("remark_internal", "Internal Remark"),
        ])
        return {
            "Source Module": source_module,
            "Record Type": "Extension",
            "Source ID": f"{source_prefix}-{source_id}",
            "Entity ID": source_id,
            "Project ID": project_id,
            "Project Name": "",
            "Order No": order_no,
            "Client Code": "",
            "Current Owner": "",
            "Phase": clean_text(row.get("active_status")),
            "Health Status": clean_text(row.get("risk_summary") or row.get("quality_risk") or row.get("commercial_risk")),
            "Result Status": clean_text(row.get("active_status")),
            "Current Progress": summary,
            "Main Issue": clean_text(row.get("risk_summary")),
            "Next Step": "",
            "Reference Link": clean_text(row.get("website_primary")),
            "Supplier Code": clean_text(row.get("supplier_code")),
            "Supplier ID": clean_text(row.get("supplier_id") or source_id),
            "Supplier Name": clean_text(row.get("supplier_name")),
            "Extension Summary": summary,
            "Extension Details": details,
        }

    if module_name == "Supplier Price Comparison":
        summary = _detail_pairs(row, [
            ("project_id", "Project ID"),
            ("rfq_item_ref", "RFQ Item Ref"),
            ("item_option", "Item Option"),
            ("supplier_code", "Supplier Code"),
            ("supplier_name", "Supplier Name"),
            ("supplier_unit_cost", "Supplier Unit Cost USD"),
            ("currency", "Currency"),
            ("moq", "MOQ"),
            ("lead_time", "Lead Time"),
            ("quote_date", "Quote Date"),
            ("comparison_status", "Comparison Status"),
            ("selected_supplier", "Selected"),
            ("recommended_supplier", "Recommended"),
        ])
        details = _detail_pairs(row, [
            ("item_spec", "Item Spec"),
            ("quote_round", "Quote Round"),
            ("quote_file_ref", "Source Ref"),
            ("price_term", "Price Term"),
            ("tooling_cost", "Tooling Cost"),
            ("sample_cost", "Sample Cost"),
            ("packing_cost", "Packing Cost"),
            ("supplier_material_basis", "Material Basis"),
            ("supplier_quote_validity", "Quote Validity"),
            ("missing_info", "Missing Info"),
            ("quotation_quality", "Quotation Quality"),
            ("quotation_risk", "Quotation Risk"),
            ("selection_reason", "Selection Reason"),
            ("remarks", "Remarks"),
        ])
        return {
            "Source Module": source_module,
            "Record Type": "Extension",
            "Source ID": f"{source_prefix}-{source_id}",
            "Entity ID": source_id,
            "Project ID": project_id,
            "Project Name": "",
            "Order No": "",
            "Client Code": "",
            "Current Owner": "",
            "Phase": clean_text(row.get("comparison_status")),
            "Health Status": clean_text(row.get("quotation_risk")),
            "Result Status": clean_text(row.get("comparison_status")),
            "Current Progress": summary,
            "Main Issue": clean_text(row.get("missing_info") or row.get("quotation_risk")),
            "Next Step": clean_text(row.get("price_adjustment_note")),
            "Reference Link": clean_text(row.get("quote_file_ref")),
            "Supplier Code": clean_text(row.get("supplier_code")),
            "Supplier ID": clean_text(row.get("supplier_id")),
            "Supplier Name": clean_text(row.get("supplier_name")),
            "RFQ Item Ref": clean_text(row.get("rfq_item_ref")),
            "Item Option": clean_text(row.get("item_option")),
            "Item Spec": clean_text(row.get("item_spec")),
            "Supplier Unit Cost": clean_text(row.get("supplier_unit_cost")),
            "Currency": clean_text(row.get("currency")),
            "MOQ": clean_text(row.get("moq")),
            "Lead Time": clean_text(row.get("lead_time")),
            "Quote Date": clean_text(row.get("quote_date")),
            "Extension Summary": summary,
            "Extension Details": details,
        }

    if module_name in {"Daily Market Indices", "Index Config", "Index Snapshot", "Freight Index"}:
        summary = _detail_pairs(row, [
            ("index_date", "Index Date"),
            ("index_category", "Category"),
            ("index_name", "Index Name"),
            ("index_value", "Index Value"),
            ("unit", "Unit"),
            ("fetch_status", "Fetch Status"),
            ("source_name", "Source"),
            ("display_name", "Display Name"),
            ("fetch_method", "Fetch Method"),
            ("fallback_method", "Fallback"),
            ("destination_country", "Destination"),
            ("freight_value", "Freight Value"),
            ("snapshot_date", "Snapshot Date"),
            ("material_index_name", "Material Index"),
            ("material_index_value", "Material Value"),
            ("exchange_rate_pair", "FX Pair"),
            ("exchange_rate_value", "FX Value"),
        ])
        details = _detail_pairs(row, [
            ("source_url", "Source URL"),
            ("previous_value", "Previous Value"),
            ("change_value", "Change Value"),
            ("change_percent", "Change Percent"),
            ("error_message", "Error Message"),
            ("confirmed_by_user", "Confirmed"),
            ("confirmed_at", "Confirmed At"),
            ("last_updated_at", "Last Updated"),
            ("updated_by", "Updated By"),
            ("freight_route", "Freight Route"),
            ("freight_index_value", "Freight Index Value"),
            ("locked_at", "Locked At"),
            ("locked_by", "Locked By"),
            ("remarks", "Remarks"),
        ])
        index_name = clean_text(row.get("index_name") or row.get("display_name") or row.get("material_index_name") or row.get("freight_index_name") or row.get("destination_country"))
        return {
            "Source Module": source_module,
            "Record Type": "Extension",
            "Source ID": f"{source_prefix}-{source_id}",
            "Entity ID": source_id,
            "Project ID": project_id,
            "Project Name": "",
            "Order No": "",
            "Client Code": "",
            "Current Owner": "",
            "Phase": clean_text(row.get("index_category") or row.get("fetch_method")),
            "Health Status": clean_text(row.get("fetch_status") or row.get("error_message")),
            "Result Status": clean_text(row.get("fetch_status") or row.get("active")),
            "Current Progress": summary,
            "Main Issue": clean_text(row.get("error_message")),
            "Next Step": "",
            "Reference Link": clean_text(row.get("source_url")),
            "Index Name": index_name,
            "Index Value": clean_text(row.get("index_value") or row.get("freight_value") or row.get("material_index_value") or row.get("exchange_rate_value")),
            "Index Date": clean_text(row.get("index_date") or row.get("snapshot_date")),
            "Fetch Status": clean_text(row.get("fetch_status")),
            "Extension Summary": summary,
            "Extension Details": details,
        }

    if module_name == "Order Details":
        summary = _detail_pairs(row, [
            ("project_id", "Project ID"),
            ("order_no", "Order No"),
            ("order_item_code", "Order Item Code"),
            ("supplier_code", "Supplier Code"),
            ("supplier_name", "Supplier Name"),
            ("order_qty", "Order Qty"),
            ("client_unit_price", "Client Unit Price USD"),
            ("supplier_unit_cost", "Supplier Unit Cost USD"),
            ("gross_profit", "Gross Profit USD"),
            ("gross_profit_percent", "Gross Profit %"),
            ("production_status", "Production Status"),
            ("inspection_status", "Inspection Status"),
            ("shipment_status", "Shipment Status"),
        ])
        details = _detail_pairs(row, [
            ("client_code", "Client Code"),
            ("po_no", "PO No"),
            ("customer_item_no", "Customer Item No"),
            ("supplier_item_no", "Supplier Item No"),
            ("sales_revenue", "Sales Revenue"),
            ("supplier_cost", "Supplier Cost"),
            ("extra_cost", "Extra Cost"),
            ("payment_status", "Payment Status"),
            ("packing_status", "Packing Status"),
            ("order_date", "Order Date"),
            ("target_delivery_date", "Target Delivery Date"),
            ("actual_delivery_date", "Actual Delivery Date"),
            ("inspection_date", "Inspection Date"),
            ("shipment_date", "Shipment Date"),
            ("container_no", "Container No"),
            ("bl_no", "B/L No"),
            ("main_issue", "Main Issue"),
            ("next_step", "Next Step"),
            ("next_step_owner", "Next Step Owner"),
            ("remarks", "Remarks"),
        ])
        return {
            "Source Module": source_module,
            "Record Type": "Extension",
            "Source ID": f"{source_prefix}-{source_id}",
            "Entity ID": source_id,
            "Project ID": project_id,
            "Project Name": "",
            "Order No": order_no,
            "Client Code": clean_text(row.get("client_code")),
            "Current Owner": clean_text(row.get("next_step_owner")),
            "Phase": clean_text(row.get("production_status")),
            "Health Status": clean_text(row.get("main_issue")),
            "Result Status": clean_text(row.get("shipment_status") or row.get("payment_status")),
            "Current Progress": summary,
            "Main Issue": clean_text(row.get("main_issue")),
            "Next Step": clean_text(row.get("next_step")),
            "Next Step Owner": clean_text(row.get("next_step_owner")),
            "Target Date": clean_text(row.get("target_delivery_date")),
            "Reference Link": "",
            "Supplier Code": clean_text(row.get("supplier_code")),
            "Supplier ID": clean_text(row.get("supplier_id")),
            "Supplier Name": clean_text(row.get("supplier_name")),
            "Order Qty": clean_text(row.get("order_qty")),
            "Currency": clean_text(row.get("currency")),
            "Gross Profit": clean_text(row.get("gross_profit")),
            "Extension Summary": summary,
            "Extension Details": details,
        }

    return {
        "Source Module": source_module,
        "Record Type": "Extension",
        "Source ID": f"{source_prefix}-{source_id}",
        "Entity ID": source_id,
        "Project ID": project_id,
        "Project Name": "",
        "Order No": order_no,
        "Client Code": "",
        "Current Progress": _detail_pairs(row, [(key, key) for key in sorted(row.keys())[:12]]),
        "Extension Details": _detail_pairs(row, [(key, key) for key in sorted(row.keys())]),
    }


def _load_extension_records_for_scope(scope: str) -> list[dict[str, Any]]:
    if scope == "Dashboard" or scope == "Meeting Mode":
        return []
    module_names: list[str] = []
    if scope == "All":
        for names in AI_SCOPE_TO_EXTENSION_MODULES.values():
            module_names.extend(names)
    elif scope in AI_SCOPE_TO_EXTENSION_MODULES:
        module_names.extend(AI_SCOPE_TO_EXTENSION_MODULES[scope])
    else:
        return []

    try:
        from services.upgrade_service import list_module_records
    except Exception:
        return []

    records: list[dict[str, Any]] = []
    # Keep limits practical so the assistant remains responsive and read-only.
    limits = {
        "Supplier Details": 2000,
        "Supplier Price Comparison": 3000,
        "Daily Market Indices": 1200,
        "Index Config": 300,
        "Index Snapshot": 1200,
        "Index Alert Rules": 600,
        "Index Alert Events": 1200,
        "Freight Index": 500,
        "Order Details": 3000,
    }
    for module_name in module_names:
        try:
            rows = list_module_records(module_name, limit=limits.get(module_name, 1000))
        except Exception:
            continue
        for idx, row in enumerate(rows):
            records.append(_normalise_extension_row(module_name, row, idx))
    return records


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
        "Supplier Code",
        "Supplier ID",
        "Supplier Name",
        "RFQ Item Ref",
        "Item Option",
        "Item Spec",
        "Supplier Unit Cost",
        "Currency",
        "MOQ",
        "Lead Time",
        "Quote Date",
        "Index Name",
        "Index Value",
        "Index Date",
        "Fetch Status",
        "Order Qty",
        "Gross Profit",
        "Extension Summary",
        "Extension Details",
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
    if scope in AI_EXTENSION_SCOPES:
        return record.get("Source Module") == scope
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
    if "supplier_details" in intents and record.get("Source Module") == "Supplier Details":
        score += 2.8
    if "price_comparison" in intents and record.get("Source Module") == "Price Comparison":
        score += 2.8
    if "index_center" in intents and record.get("Source Module") == "Index Center":
        score += 2.8
    if "order_details" in intents and record.get("Source Module") == "Order Details":
        score += 2.8

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
    records.extend(_load_extension_records_for_scope(scope))

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
    extension_terms = []
    for key in ["supplier_details", "price_comparison", "index_center", "order_details"]:
        extension_terms.extend(INTENT_KEYWORDS.get(key, []))
    extension_specific = _has_any(lower, extension_terms)
    asks_operation = _has_any(lower, operation_terms)
    asks_sales = _has_any(lower, sales_terms)
    if extension_specific:
        pass
    elif asks_operation and not asks_sales:
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


def _is_broad_integrated_question(query: str) -> bool:
    """Return True when the user is asking for a broad cross-module overview."""
    return _has_any(
        query,
        [
            "all information",
            "all info",
            "everything about",
            "current situation",
            "current status",
            "overall status",
            "overview",
            "full picture",
            "integrated summary",
            "show all",
            "所有信息",
            "全部信息",
            "完整信息",
            "整体情况",
            "当前情况",
            "综合信息",
            "整合",
            "总览",
        ],
    )



def _extract_explicit_keys(query: str) -> dict[str, set[str]]:
    """Extract exact business identifiers from a user question.

    This is a retrieval guardrail: exact keys narrow the evidence before the AI
    sees it, so broad project questions do not pull in same-client or loosely
    similar records.
    """
    text = clean_text(query)
    upper = text.upper()
    keys: dict[str, set[str]] = {
        "project_id": set(),
        "order_no": set(),
        "supplier_code": set(),
        "supplier_id": set(),
        "rfq_item_ref": set(),
        "item_option": set(),
        "index_name": set(),
    }

    for value in re.findall(r"\bSDG-\d{2}-\d{3}\b", upper):
        keys["project_id"].add(value)
    # Supplier codes used in this system are SD + digits; avoid matching SDG project IDs.
    for value in re.findall(r"\bSD(?!G\b)\d{1,6}\b", upper):
        keys["supplier_code"].add(value)
    for value in re.findall(r"\bSUP-\d{3,}\b", upper):
        keys["supplier_id"].add(value)
    for value in re.findall(r"\bITM[-_ ]?\d{1,4}\b", upper):
        keys["rfq_item_ref"].add(value.replace(" ", "-").replace("_", "-"))

    # Order numbers are company/client prefixes followed by date-like digits and suffix.
    # This intentionally excludes project IDs and supplier IDs.
    for value in re.findall(r"\b(?!SDG\b)(?!SUP\b)[A-Z]{2,6}\d{5,8}-\d{1,4}\b", upper):
        keys["order_no"].add(value)

    index_patterns = [
        r"\bUSD[/_\-]?CNY\b", r"\bHKD[/_\-]?CNY\b", r"\bGBP[/_\-]?CNY\b",
        r"\bPP\b", r"\bPVC\b", r"\bABS\b",
        r"\bZINC\b", r"\bALUMINIUM\b", r"\bALUMINUM\b",
        r"\bCARBON\s+STEEL\b", r"\bSTAINLESS\s+STEEL\s*304\b",
        r"\bFREIGHT\s+TO\s+ISRAEL\b", r"\bFREIGHT\s+TO\s+MOROCCO\b",
    ]
    for pattern in index_patterns:
        for match in re.findall(pattern, upper):
            value = clean_text(match).upper().replace("-", "/").replace("_", "/")
            value = re.sub(r"\s+", " ", value)
            if value:
                keys["index_name"].add(value)
    return keys


def _explicit_key_present(keys: dict[str, set[str]], *names: str) -> bool:
    return any(bool(keys.get(name)) for name in names)


def _record_has_project(record: dict[str, Any], project_ids: set[str]) -> bool:
    project_id = clean_text(record.get("Project ID")).upper()
    return bool(project_id and project_id in project_ids)


def _record_has_order(record: dict[str, Any], order_nos: set[str]) -> bool:
    if not order_nos:
        return False
    own_order = clean_text(record.get("Order No")).upper()
    if own_order and own_order in order_nos:
        return True
    for linked_order in _split_join_list(record.get("Linked Orders")):
        if linked_order.upper() in order_nos:
            return True
    return False


def _record_has_supplier(record: dict[str, Any], supplier_codes: set[str], supplier_ids: set[str] | None = None) -> bool:
    supplier_ids = supplier_ids or set()
    code = clean_text(record.get("Supplier Code")).upper()
    sid = clean_text(record.get("Supplier ID") or record.get("Entity ID")).upper()
    return bool((code and code in supplier_codes) or (sid and sid in supplier_ids))


def _record_has_index(record: dict[str, Any], index_names: set[str]) -> bool:
    if clean_text(record.get("Source Module")) != "Index Center" or not index_names:
        return False
    candidates = {
        clean_text(record.get("Index Name")).upper(),
        clean_text(record.get("Entity ID")).upper(),
        clean_text(record.get("Extension Summary")).upper(),
    }
    compact_candidates = {c.replace("_", "/").replace("-", "/") for c in candidates if c}
    for idx in index_names:
        compact = idx.upper().replace("_", "/").replace("-", "/")
        if compact in compact_candidates or any(compact in candidate for candidate in compact_candidates):
            return True
    return False


def _question_intent(query: str, scope: str) -> str:
    """Lightweight intent router for answer style and retrieval narrowing."""
    lower = _lower(query)
    keys = _extract_explicit_keys(query)
    if _explicit_key_present(keys, "index_name") or scope == "Index Center" or _has_any(lower, INTENT_KEYWORDS["index_center"]):
        return "index"
    if scope == "Supplier Details" or (_explicit_key_present(keys, "supplier_code", "supplier_id") and not _explicit_key_present(keys, "project_id", "order_no")):
        return "supplier"
    if scope == "Price Comparison" or _has_any(lower, INTENT_KEYWORDS["price_comparison"]):
        return "price_comparison"
    if _explicit_key_present(keys, "order_no") or scope == "Order Details" or (_has_any(lower, INTENT_KEYWORDS["order_details"]) and not _explicit_key_present(keys, "project_id")):
        return "order"
    if _explicit_key_present(keys, "project_id") or scope in {"Project Details", "Sales Board", "Operation Board"}:
        return "project"
    if _has_any(lower, INTENT_KEYWORDS["meeting"]):
        return "meeting"
    return "general"


def _mark_relevance(row: dict[str, Any], tier: str, related_by: str, suggested_use: str) -> dict[str, Any]:
    marked = dict(row)
    marked["Relevance Tier"] = tier
    marked["Related By"] = related_by
    marked["Suggested Answer Use"] = suggested_use
    existing_reason = clean_text(marked.get("Match Reason"))
    if related_by and related_by not in existing_reason:
        marked["Match Reason"] = f"{existing_reason}; {related_by}" if existing_reason else related_by
    return marked


def _dedupe_by_identity(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in records:
        identity = _record_source_identity(row)
        if not identity or identity in seen:
            continue
        seen.add(identity)
        out.append(row)
    return out


def _strong_relevance_records_for_query(
    *,
    query: str,
    records: list[dict[str, Any]],
    scope: str,
    limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    """Return exact-key, strong-relevance evidence for focused questions.

    The goal is management usefulness: for a project question, include only the
    project records and directly linked supplier/order/quotation records. Do not
    pull in same-client records, same-category suppliers, or supplier history
    unless the user explicitly asks for those.
    """
    keys = _extract_explicit_keys(query)
    intent = _question_intent(query, scope)
    project_ids = keys.get("project_id", set())
    order_nos = keys.get("order_no", set())
    supplier_codes = keys.get("supplier_code", set())
    supplier_ids = keys.get("supplier_id", set())
    index_names = keys.get("index_name", set())

    if not any([project_ids, order_nos, supplier_codes, supplier_ids, index_names]):
        return None

    priority = {module: idx for idx, module in enumerate(AI_MODULE_SOURCE_PRIORITY)}
    strong: list[dict[str, Any]] = []
    related_but_not_expanded = 0

    if intent == "project" and project_ids:
        # 1) Direct project evidence.
        direct_project = [r for r in records if _record_has_project(r, project_ids)]
        for row in direct_project:
            strong.append(_mark_relevance(row, "Strong", "Exact Project ID match", "Use in project management answer"))

        # 2) Orders explicitly linked by exact project records.
        linked_orders = set(order_nos)
        for row in direct_project:
            for order_no in _split_join_list(row.get("Linked Orders")):
                linked_orders.add(order_no.upper())
            own_order = clean_text(row.get("Order No")).upper()
            if own_order:
                linked_orders.add(own_order)

        direct_orders = [r for r in records if _record_has_order(r, linked_orders)] if linked_orders else []
        for row in direct_orders:
            strong.append(_mark_relevance(row, "Strong", "Order No linked to exact Project ID", "Use only for this project/order situation"))

        # 3) Suppliers only if they appear in the exact project/order/price evidence.
        direct_bundle = _dedupe_by_identity(direct_project + direct_orders)
        supplier_codes_from_direct = {
            clean_text(r.get("Supplier Code")).upper()
            for r in direct_bundle
            if clean_text(r.get("Supplier Code"))
        }
        supplier_ids_from_direct = {
            clean_text(r.get("Supplier ID")).upper()
            for r in direct_bundle
            if clean_text(r.get("Supplier ID"))
        }
        # Price comparison records for the exact project may introduce additional suppliers.
        price_rows = [r for r in direct_project if clean_text(r.get("Source Module")) == "Price Comparison"]
        supplier_codes_from_direct.update(
            clean_text(r.get("Supplier Code")).upper() for r in price_rows if clean_text(r.get("Supplier Code"))
        )
        supplier_rows = [
            r for r in records
            if clean_text(r.get("Source Module")) == "Supplier Details"
            and _record_has_supplier(r, supplier_codes_from_direct, supplier_ids_from_direct)
        ]
        for row in supplier_rows:
            strong.append(_mark_relevance(row, "Strong", "Supplier Code found in exact project/order records", "Use only as linked supplier master data"))

        # 4) Do not include unrelated index rows unless the project itself has index snapshot rows.
        # Daily market indices are not project evidence unless the question asks about index.

        # Count weak records that matched by supplier but are outside this project; keep them out of final tabs.
        for r in records:
            if clean_text(r.get("Source Module")) in {"Price Comparison", "Order Details"} and _record_has_supplier(r, supplier_codes_from_direct):
                if not _record_has_project(r, project_ids) and not _record_has_order(r, linked_orders):
                    related_but_not_expanded += 1

    elif intent == "supplier" and (supplier_codes or supplier_ids):
        for row in records:
            if _record_has_supplier(row, supplier_codes, supplier_ids):
                strong.append(_mark_relevance(row, "Strong", "Exact Supplier Code / Supplier ID match", "Use in supplier answer"))

    elif intent == "order" and order_nos:
        direct_orders = [r for r in records if _record_has_order(r, order_nos)]
        for row in direct_orders:
            strong.append(_mark_relevance(row, "Strong", "Exact Order No match", "Use in order answer"))
        supplier_codes_from_order = {
            clean_text(r.get("Supplier Code")).upper()
            for r in direct_orders
            if clean_text(r.get("Supplier Code"))
        }
        supplier_rows = [
            r for r in records
            if clean_text(r.get("Source Module")) == "Supplier Details"
            and _record_has_supplier(r, supplier_codes_from_order)
        ]
        for row in supplier_rows:
            strong.append(_mark_relevance(row, "Strong", "Supplier Code found in exact order records", "Use as linked supplier master data"))

    elif intent == "index" and index_names:
        for row in records:
            if _record_has_index(row, index_names):
                strong.append(_mark_relevance(row, "Strong", "Exact Index Name / Index Code match", "Use in index answer"))

    elif intent == "price_comparison" and project_ids:
        for row in records:
            if clean_text(row.get("Source Module")) == "Price Comparison" and _record_has_project(row, project_ids):
                strong.append(_mark_relevance(row, "Strong", "Exact Project ID in Price Comparison", "Use in quotation comparison answer"))

    strong = _dedupe_by_identity(strong)
    if not strong:
        return None

    strong.sort(
        key=lambda row: (
            priority.get(clean_text(row.get("Source Module")), 99),
            clean_text(row.get("Project ID")),
            clean_text(row.get("Order No")),
            clean_text(row.get("Supplier Code")),
            clean_text(row.get("RFQ Item Ref")),
            clean_text(row.get("Source ID")),
        )
    )
    capped = strong[: max(limit, min(len(strong), 50))]
    return capped, {
        "query_mode": "Strong Relevance Exact-Key Search + Read-only Join",
        "answer_intent": intent,
        "strong_relevance_filter": True,
        "explicit_project_ids": sorted(project_ids),
        "explicit_order_nos": sorted(order_nos),
        "explicit_supplier_codes": sorted(supplier_codes),
        "explicit_supplier_ids": sorted(supplier_ids),
        "explicit_index_names": sorted(index_names),
        "total_searchable_records": len(records),
        "total_records_after_deterministic_filters": len(strong),
        "total_matched_records": len(strong),
        "returned_records": len(capped),
        "initial_matched_records": len(capped),
        "join_expanded_records": 0,
        "join_keys_used": sorted(k for k, v in keys.items() if v),
        "related_but_not_expanded": related_but_not_expanded,
    }


def _split_join_list(value: Any) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [part.strip() for part in re.split(r"[,;，；|]+", text) if part.strip()]


def _record_source_identity(record: dict[str, Any]) -> str:
    return clean_text(record.get("Source ID")) or "|".join(
        clean_text(record.get(field))
        for field in ["Source Module", "Record Type", "Project ID", "Order No", "Entity ID", "Supplier Code", "RFQ Item Ref", "Item Option"]
    )


def _extract_join_values(records: list[dict[str, Any]]) -> dict[str, set[str]]:
    values: dict[str, set[str]] = {
        "project_id": set(),
        "supplier_code": set(),
        "supplier_id": set(),
        "order_no": set(),
        "rfq_item_ref": set(),
        "item_option": set(),
        "index_name": set(),
    }
    for row in records:
        for field, key in [
            ("Project ID", "project_id"),
            ("Supplier Code", "supplier_code"),
            ("Supplier ID", "supplier_id"),
            ("Order No", "order_no"),
            ("RFQ Item Ref", "rfq_item_ref"),
            ("Item Option", "item_option"),
            ("Index Name", "index_name"),
        ]:
            value = clean_text(row.get(field))
            if value:
                values[key].add(value)
        if clean_text(row.get("Source Module")) == "Supplier Details":
            supplier_entity = clean_text(row.get("Entity ID"))
            if supplier_entity:
                values["supplier_id"].add(supplier_entity)
        for order_no in _split_join_list(row.get("Linked Orders")):
            values["order_no"].add(order_no)
    return values


def _record_join_match_reason(record: dict[str, Any], join_values: dict[str, set[str]]) -> str:
    """Return a deterministic read-only join reason, or empty string if not linked."""
    module = clean_text(record.get("Source Module"))
    project_id = clean_text(record.get("Project ID"))
    supplier_code = clean_text(record.get("Supplier Code"))
    supplier_id = clean_text(record.get("Supplier ID"))
    order_no = clean_text(record.get("Order No"))
    index_name = clean_text(record.get("Index Name"))

    # Project ID is the first-level commercial join key. It can connect core and extension records.
    if project_id and project_id in join_values.get("project_id", set()):
        return f"Deterministic cross-module join: Project ID = {project_id}"

    # Supplier joins are especially important for project questions: Order Details / Price Comparison
    # may reveal a supplier_code that must be joined back to Supplier Details.
    if supplier_code and supplier_code in join_values.get("supplier_code", set()):
        return f"Deterministic cross-module join: Supplier Code = {supplier_code}"
    if supplier_id and supplier_id in join_values.get("supplier_id", set()):
        return f"Deterministic cross-module join: Supplier ID = {supplier_id}"
    if module == "Supplier Details" and clean_text(record.get("Entity ID")) in join_values.get("supplier_id", set()):
        return f"Deterministic cross-module join: Supplier ID = {clean_text(record.get('Entity ID'))}"

    if order_no and order_no in join_values.get("order_no", set()):
        return f"Deterministic cross-module join: Order No = {order_no}"
    if order_no:
        for linked_order in join_values.get("order_no", set()):
            if linked_order and linked_order in _split_join_list(record.get("Linked Orders")):
                return f"Deterministic cross-module join: Linked Order No = {linked_order}"

    # Only use index-name expansion for index-specific records, not for unrelated project questions.
    if module == "Index Center" and index_name and index_name in join_values.get("index_name", set()):
        return f"Deterministic cross-module join: Index Name = {index_name}"

    return ""


def _expand_records_by_join_keys(
    *,
    question: str,
    seed_records: list[dict[str, Any]],
    available_records: list[dict[str, Any]],
    scope: str,
    max_total: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Add deterministic read-only cross-module records using approved join keys.

    This function never writes data and never invents records. It only adds records already
    loaded from the current system when they are connected by project_id, supplier_code,
    supplier_id, order_no, rfq_item_ref/item_option, or index_name/index_code.
    """
    if not seed_records or scope not in {"All", "Project Details"}:
        return seed_records, {"join_expanded_records": 0, "join_keys_used": []}

    expanded: list[dict[str, Any]] = [dict(row) for row in seed_records]
    seen = {_record_source_identity(row) for row in expanded}
    keys_used: set[str] = set()

    # Broad project questions should include a wider evidence bundle; narrower queries still get
    # direct supplier/order/project support records so statements such as supplier master data are grounded.
    broad = _is_broad_integrated_question(question)
    passes = 3 if broad else 2

    for _ in range(passes):
        join_values = _extract_join_values(expanded)
        added_this_pass = 0
        for record in available_records:
            if len(expanded) >= max_total:
                break
            identity = _record_source_identity(record)
            if not identity or identity in seen:
                continue
            reason = _record_join_match_reason(record, join_values)
            if not reason:
                continue
            row = dict(record)
            existing_reason = clean_text(row.get("Match Reason"))
            row["Match Reason"] = f"{existing_reason}; {reason}" if existing_reason else reason
            expanded.append(row)
            seen.add(identity)
            added_this_pass += 1
            if "Project ID" in reason:
                keys_used.add("project_id")
            elif "Supplier Code" in reason:
                keys_used.add("supplier_code")
            elif "Supplier ID" in reason:
                keys_used.add("supplier_id")
            elif "Order No" in reason:
                keys_used.add("order_no")
            elif "Index Name" in reason:
                keys_used.add("index_name")
        if added_this_pass == 0:
            break

    # Keep module priority stable while retaining joined evidence.
    priority = {module: idx for idx, module in enumerate(AI_MODULE_SOURCE_PRIORITY)}
    expanded.sort(
        key=lambda row: (
            priority.get(clean_text(row.get("Source Module")), 99),
            clean_text(row.get("Project ID")),
            clean_text(row.get("Order No")),
            clean_text(row.get("Supplier Code")),
            clean_text(row.get("RFQ Item Ref")),
            clean_text(row.get("Source ID")),
        )
    )
    return expanded, {
        "join_expanded_records": max(0, len(expanded) - len(seed_records)),
        "join_keys_used": sorted(keys_used),
        "join_expansion_mode": "broad_integrated_overview" if broad else "direct_related_records",
    }

def _search_records(query: str, *, scope: str, record_type: str, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query = clean_text(query)
    tokens = _tokenize(query)
    loaded_records = _load_records_for_scope(scope, record_type)

    strong_result = _strong_relevance_records_for_query(
        query=query,
        records=loaded_records,
        scope=scope,
        limit=limit,
    )
    if strong_result is not None:
        return strong_result

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
    expanded, expansion_metadata = _expand_records_by_join_keys(
        question=query,
        seed_records=matched,
        available_records=loaded_records,
        scope=scope,
        max_total=min(max(limit * 2, limit + 10), 50),
    )
    metadata = {
        "query_mode": "Natural Language Search + Deterministic Cross-Module Join",
        "total_searchable_records": len(loaded_records),
        "total_records_after_deterministic_filters": len(records),
        "total_matched_records": len(scored),
        "returned_records": len(expanded),
        "initial_matched_records": len(matched),
        "tokens": tokens,
    }
    metadata.update(expansion_metadata)
    return expanded, metadata


def _looks_like_dashboard_question(query: str, scope: str) -> bool:
    if scope == "Dashboard":
        return True
    return _has_any(query, INTENT_KEYWORDS["dashboard"])


def _looks_like_meeting_question(query: str, scope: str) -> bool:
    if scope == "Meeting Mode":
        return True
    return _has_any(query, INTENT_KEYWORDS["meeting"])


def _safe_float(value: Any) -> float | None:
    text = clean_text(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _review_points_for_record(record: dict[str, Any]) -> list[str]:
    """Return read-only review hints based only on fields in the evidence row."""
    module = clean_text(record.get("Source Module"))
    points: list[str] = []

    if module == "Price Comparison":
        if _safe_float(record.get("Supplier Unit Cost")) is None:
            points.append("missing price")
        elif (_safe_float(record.get("Supplier Unit Cost")) or 0) <= 0:
            points.append("price is zero or negative")
        if not clean_text(record.get("Currency")):
            points.append("missing currency")
        if not clean_text(record.get("MOQ")):
            points.append("missing MOQ")
        if not clean_text(record.get("Lead Time")):
            points.append("missing lead time")
        if not clean_text(record.get("Quote Date")):
            points.append("missing quote date")
        if not clean_text(record.get("Supplier Code")):
            points.append("missing supplier code")
        if not clean_text(record.get("Supplier Name")):
            points.append("supplier name missing")
        if _has_any(record.get("Extension Details"), ["not matched", "supplier not matched", "unmatched"]):
            points.append("supplier not matched")

    elif module == "Index Center":
        status = clean_text(record.get("Fetch Status") or record.get("Result Status"))
        if status.lower() in {"failed", "fail"}:
            points.append("index fetch failed")
        elif status.lower() == "carry forward":
            points.append("index value is carried forward")
        if _has_any(record.get("Extension Details"), ["Confirmed: False", "confirmed: false", "Confirmed: No"]):
            points.append("index value not manually confirmed")

    elif module == "Order Details":
        if not clean_text(record.get("Supplier Code")):
            points.append("missing supplier code")
        if not clean_text(record.get("Gross Profit")):
            points.append("gross profit not recorded")
        if clean_text(record.get("Main Issue")):
            points.append("open order issue recorded")

    return points


def _build_readonly_analysis_context(records: list[dict[str, Any]], dashboard_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build compact cross-module context from current evidence only.

    This does not infer external facts and does not modify records. It gives the model
    deterministic joins, review rules, and evidence counts so answers stay grounded.
    """
    module_counts = Counter(clean_text(row.get("Source Module")) or "Unknown" for row in records)
    project_ids = sorted({clean_text(row.get("Project ID")) for row in records if clean_text(row.get("Project ID"))})
    supplier_codes = sorted({clean_text(row.get("Supplier Code")) for row in records if clean_text(row.get("Supplier Code"))})
    order_nos = sorted({clean_text(row.get("Order No")) for row in records if clean_text(row.get("Order No"))})
    rfq_keys = sorted({
        " / ".join(part for part in [clean_text(row.get("Project ID")), clean_text(row.get("RFQ Item Ref")), clean_text(row.get("Item Option"))] if part)
        for row in records
        if clean_text(row.get("RFQ Item Ref"))
    })
    index_names = sorted({clean_text(row.get("Index Name")) for row in records if clean_text(row.get("Index Name"))})

    review_rows: list[dict[str, Any]] = []
    for row in records:
        points = _review_points_for_record(row)
        if points:
            review_rows.append({
                "source_id": clean_text(row.get("Source ID")),
                "source_module": clean_text(row.get("Source Module")),
                "project_id": clean_text(row.get("Project ID")),
                "supplier_code": clean_text(row.get("Supplier Code")),
                "rfq_item_ref": clean_text(row.get("RFQ Item Ref")),
                "item_option": clean_text(row.get("Item Option")),
                "review_points": points,
            })

    return {
        "definition": "Read-only business record assistant. Cross-module answers must use only the provided system records.",
        "module_source_priority": AI_MODULE_SOURCE_PRIORITY,
        "join_keys": AI_JOIN_KEYS,
        "allowed_join_examples": [
            "Project ID -> Price Comparison",
            "Project ID -> Order Details",
            "Supplier Code -> Supplier Details",
            "Supplier Code -> Price Comparison",
            "Supplier Code -> Order Details",
            "Index Name / Index Code -> Daily Market Indices",
        ],
        "review_rules": AI_REVIEW_RULES,
        "answer_templates": AI_ANSWER_TEMPLATES,
        "not_found_handling": "If a field or module record is not present in evidence, state that it was not found in current system records. Do not convert not-found into a real-world fact.",
        "evidence_requirement": "Every business statement must be supported by provided evidence rows. Use final_source_ids for the rows that directly answer the question.",
        "evidence_counts_by_module": dict(module_counts),
        "join_key_values_found": {
            "project_id": project_ids[:30],
            "supplier_code": supplier_codes[:30],
            "order_no": order_nos[:30],
            "project_rfq_item_option": rfq_keys[:30],
            "index_name": index_names[:30],
        },
        "deterministic_review_points": review_rows[:40],
        "dashboard_metric_rows": len(dashboard_rows),
    }


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
                "supplier_code": row.get("Supplier Code"),
                "supplier_id": row.get("Supplier ID"),
                "supplier_name": row.get("Supplier Name"),
                "rfq_item_ref": row.get("RFQ Item Ref"),
                "item_option": row.get("Item Option"),
                "item_spec": row.get("Item Spec"),
                "supplier_unit_cost": row.get("Supplier Unit Cost"),
                "currency": row.get("Currency"),
                "moq": row.get("MOQ"),
                "lead_time": row.get("Lead Time"),
                "quote_date": row.get("Quote Date"),
                "index_name": row.get("Index Name"),
                "index_value": row.get("Index Value"),
                "index_date": row.get("Index Date"),
                "fetch_status": row.get("Fetch Status"),
                "order_qty": row.get("Order Qty"),
                "gross_profit": row.get("Gross Profit"),
                "extension_summary": row.get("Extension Summary"),
                "extension_details": row.get("Extension Details"),
                "match_reason": row.get("Match Reason"),
            }
        )

    return {
        "dashboard_metrics": dashboard_rows[:80],
        "system_records": evidence_records,
        "readonly_analysis_context": _build_readonly_analysis_context(records[:max_rows], dashboard_rows[:80]),
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
        "supplier_details_records": int(module_counts.get("Supplier Details", 0)),
        "price_comparison_records": int(module_counts.get("Price Comparison", 0)),
        "index_center_records": int(module_counts.get("Index Center", 0)),
        "order_details_records": int(module_counts.get("Order Details", 0)),
        "extension_records": int(type_counts.get("Extension", 0)),
    }
    if metadata.get("full_result_count") is not None:
        summary["total_final_answer_records"] = metadata.get("full_result_count")
        summary["records_shown"] = len(records)
    if metadata.get("client_terms"):
        summary["client_terms"] = metadata.get("client_terms")
    if metadata.get("answer_intent"):
        summary["answer_intent"] = metadata.get("answer_intent")
    if metadata.get("strong_relevance_filter"):
        summary["strong_relevance_filter"] = "On"
    if metadata.get("related_but_not_expanded"):
        summary["related_but_not_expanded"] = metadata.get("related_but_not_expanded")
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
        record_type = clean_text(row.get("Record Type"))

        # Extension rows can represent multiple business lines under the same
        # Project ID / Order No, especially Order Details item lines and Price
        # Comparison supplier quotes. Do not collapse them into one row; otherwise
        # the AI answer may incorrectly describe only the first item.
        if record_type == "Extension" or module in {"Supplier Details", "Price Comparison", "Index Center", "Order Details"}:
            key = (
                module,
                clean_text(row.get("Source ID")) or clean_text(row.get("Entity ID")),
                clean_text(row.get("Project ID")),
                "|".join([
                    clean_text(row.get("Order No")),
                    clean_text(row.get("Supplier Code")),
                    clean_text(row.get("RFQ Item Ref")),
                    clean_text(row.get("Item Option")),
                    clean_text(row.get("Item Spec"))[:80],
                ]),
            )
        elif module == "Project History":
            key = (
                record_type,
                clean_text(row.get("Project ID")),
                clean_text(row.get("Order No")),
                clean_text(row.get("Source ID")),
            )
        else:
            key = (
                record_type,
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

    if _is_broad_integrated_question(question):
        return _dedupe_final_records(records, scope=scope)

    selected_ids = _source_ids_mentioned_in_answer(answer, records)
    if selected_ids:
        selected = [row for row in records if clean_text(row.get("Source ID")) in selected_ids]
        # Keep deterministic support records in the final evidence if they were added by approved join keys.
        # This prevents a project answer from saying a supplier exists while the Supplier Details tab shows no row.
        support = [
            row for row in records
            if "Deterministic cross-module join" in clean_text(row.get("Match Reason"))
            and clean_text(row.get("Source ID")) not in selected_ids
        ]
        if support:
            selected.extend(support)
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
    issue = clean_text(record.get("Main Issue") or record.get("Need From Meeting") or record.get("Meeting Focus Reason") or record.get("Next Step") or record.get("Extension Summary"))

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
    extension_groups: dict[str, list[dict[str, Any]]] = {}
    for row in final_records:
        if clean_text(row.get("Record Type")) == "Extension":
            extension_groups.setdefault(clean_text(row.get("Source Module")) or "Extension", []).append(row)

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
        for module_name, module_rows in extension_groups.items():
            details.append(f"{module_name}:\n" + "\n".join(f"{idx}. {_format_record_line(row, lang=lang)}" for idx, row in enumerate(module_rows, start=1)))
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
        for module_name, module_rows in extension_groups.items():
            details.append(f"{module_name}:\n" + "\n".join(f"{idx}. {_format_record_line(row, lang='English')}" for idx, row in enumerate(module_rows, start=1)))
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
        for module_name, module_rows in extension_groups.items():
            details.append(f"{module_name}:\n" + "\n".join(f"{idx}. {_format_record_line(row, lang='English')}" for idx, row in enumerate(module_rows, start=1)))
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


def _polish_management_answer_text(answer: dict[str, Any], *, answer_intent: str = "") -> dict[str, Any]:
    """Small deterministic wording polish for management answers.

    This does not add business facts. It only standardises headings and makes
    project-index/order-detail wording safer when the model uses generic phrases.
    """
    polished = dict(answer or {})
    text_keys = ["direct_answer", "evidence_summary", "detailed_answer", "not_found_or_limitations"]
    for key in text_keys:
        value = clean_text(polished.get(key))
        if not value:
            polished[key] = value
            continue
        replacements = [
            ("Missing or Not Found in Current System Records", "Information Gaps in Current System Records"),
            ("Missing or not found in current system records", "Information gaps in current system records"),
            ("Missing/not found", "Information gaps"),
            ("Missing / not found", "Information gaps"),
        ]
        if answer_intent == "project":
            replacements.extend([
                ("No Index Center records found for this project", "No project-linked Index Snapshot or Index Center records were found for this project"),
                ("No Index Center records found", "No project-linked Index Snapshot or Index Center records were found"),
                ("No Index Center records were found", "No project-linked Index Snapshot or Index Center records were found"),
                ("No price comparison or index records found", "No Price Comparison records or project-linked Index records were found"),
                ("No Price Comparison or Index records were found", "No Price Comparison records or project-linked Index records were found"),
                ("No Price Comparison or Index records found", "No Price Comparison records or project-linked Index records were found"),
            ])
        for old, new in replacements:
            value = value.replace(old, new)
        polished[key] = value
    return polished


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

    evidence_payload = _prepare_ai_evidence(records, dashboard_rows, max_rows=min(max(len(records), result_limit), 100))

    system_prompt = """
You are the AI Project Assistant for Zenith Project Tracker System.

Definition:
- You are a read-only business record analysis assistant.
- You may search, join, compare, and explain only the system evidence provided in the payload.
- You must never invent facts, assume missing information, or modify system data.

Hard data rules:
- Use only dashboard_metrics, system_records, and readonly_analysis_context from the user payload.
- Some system_records may be included by deterministic cross-module joins. Treat them as valid evidence only when their Match Reason or join keys support the answer.
- If a module, field, supplier, quote, order, index, or project is not found in the evidence, say it was not found in current system records.
- Do not turn "not found in system records" into "does not exist in real life".
- Distinguish facts from record-based review notes. Use wording such as "System records show" and "This may need review because".
- Do not make final business decisions for the user. You may identify lowest price, missing information, selected status, or review points from records.

Allowed join keys:
- project_id
- supplier_code
- supplier_id
- order_no
- rfq_item_ref
- item_option
- index_name / index_code
Only connect modules using these keys when the evidence contains them.

Module source priority:
- Sales Board and Operation Board for current project/order status.
- Meeting Mode and Project History for meeting/follow-up evidence.
- Supplier Details for supplier master data and risk fields.
- Price Comparison for supplier quotes, RFQ Item Ref, Item Option, Item Spec, price, MOQ, lead time, and selected/comparison status.
- Order Details for order items, quantities, supplier cost, gross profit, production/inspection/shipment status. If multiple order item rows share the same order_no, summarize the item count and key financial/status facts; do not imply there is only one item unless the evidence has only one order item row.
- Index Center for latest index values, source, fetch status, and confirmed status. For project questions, mention Index Center only when there is a project-linked Index Snapshot or project-linked index basis; otherwise say no project-linked Index Snapshot / Index Center record was found.

Review rules:
- Price Comparison may need review when price, currency, MOQ, lead time, quote date, supplier code, or supplier name is missing; supplier is not matched; or price is zero/negative.
- Index Center may need review when fetch_status is Failed, value is Carry Forward, or confirmed status is false where confirmation is expected.
- Order Details may need review when gross profit is missing, supplier code is missing, or an open order issue is recorded.

Answer format and management style:
- Return JSON only.
- Answer like a management meeting assistant, not a raw data export.
- Use this structure unless the user asks for a different format: Direct Answer → Current situation → Confirmed facts → Main risk / impact → Information gaps in current system records → Suggested next step → Evidence used.
- Keep the answer concise. Do not dump every field from every evidence row. In the Direct Answer, emphasize the blocked point, main risk/impact, and next step before secondary details.
- Include a module only if it is strongly related to the user question. If no strongly related records exist for a module, state that briefly and do not expand it.
- final_source_ids must include only Source ID values that directly support the answer.
- Do not mention candidate records, internal search counts, checked-record counts, or weak related records.
- If the user asks for "all information", still summarize by management value; do not list every raw field unless the user explicitly asks for raw records/export-style details.

Language rule:
- requested_output_language is mandatory.
- English: English narrative only. Keep raw project names, codes, links, and statuses unchanged.
- Chinese: Simplified Chinese narrative. Keep project IDs, order numbers, supplier codes, and raw system values unchanged.
- Bilingual Chinese and English: clearly bilingual, not random mixed-language text.

Required JSON keys exactly:
{
  "direct_answer": "...",
  "evidence_summary": "...",
  "detailed_answer": "...",
  "not_found_or_limitations": "...",
  "final_source_ids": ["..."]
}
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
                "Direct answer first. Then give a boss-style management answer using only strongly related system records. "
                "Structure the answer as: current situation, confirmed facts, main risk/impact, information gaps in current system records, suggested next step, evidence used. "
                "When useful, connect modules only with project_id, supplier_code, supplier_id, order_no, rfq_item_ref, item_option, and index_name/index_code. Treat deterministic joined records as supporting evidence, not AI-created facts. "
                "Use the readonly_analysis_context review rules to identify missing information or review points, but do not invent facts or make final decisions. "
                "If data is not found, state that it was not found in current system records. For project index data, use 'No project-linked Index Snapshot or Index Center records were found' rather than implying the whole Index Center is empty. For Order Details, handle multiple order item rows safely and summarize item count when applicable. "
                "Do not list raw records one by one unless the user explicitly asks for raw records. Do not mention candidate records or internal checked records. Follow requested_output_language strictly; do not mix languages unless bilingual output is selected."
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
    answer = _polish_management_answer_text(answer, answer_intent=clean_text(metadata.get("answer_intent")))

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

    if ai_error:
        # If the model API is unavailable or returns invalid JSON, keep the page useful by
        # rendering a deterministic read-only system-record answer. This preserves the
        # safety rule: no system evidence means no business conclusion.
        safe_answer = _build_language_safe_final_answer(
            question=question,
            output_language=output_language,
            final_records=final_records,
            dashboard_rows=dashboard_rows,
        )
        answer.update(safe_answer)
    elif _language_mismatch_for_output(answer, output_language):
        safe_answer = _build_language_safe_final_answer(
            question=question,
            output_language=output_language,
            final_records=final_records,
            dashboard_rows=dashboard_rows,
        )
        answer.update(safe_answer)

    answer = _polish_management_answer_text(answer, answer_intent=clean_text(metadata.get("answer_intent")))
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
                f"Extension: {record.get('Extension Summary') or '-'} | "
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
