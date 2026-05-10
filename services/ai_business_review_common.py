from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import pandas as pd

from services.ai_client import AIConfigError, AIResponseError, call_deepseek_json


STANDARD_AI_REVIEW_NOTICE = (
    "AI output is a draft/review based on current system records. "
    "Please review before taking action."
)


def clean_text(value: Any, empty: str = "") -> str:
    if value is None:
        return empty
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "-"}:
        return empty
    return text


def has_value(value: Any) -> bool:
    return bool(clean_text(value))


def compact_record(record: dict[str, Any], fields: list[str] | tuple[str, ...] | None = None) -> dict[str, Any]:
    if not record:
        return {}
    if fields:
        keys = [field for field in fields if field in record]
    else:
        keys = list(record.keys())[:28]
    return {key: _json_safe(record.get(key)) for key in keys if has_value(record.get(key)) or key in {"project_id", "order_no", "supplier_code", "rfq_id"}}


def limit_records(records: list[dict[str, Any]] | None, fields: list[str] | tuple[str, ...] | None = None, limit: int = 60) -> list[dict[str, Any]]:
    return [compact_record(row, fields) for row in list(records or [])[:limit]]


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


def default_review(
    *,
    direct_summary: str,
    readiness: str = "Need Review",
    key_findings: list[str] | None = None,
    risks: list[str] | None = None,
    missing_information: list[str] | None = None,
    suggested_actions: list[str] | None = None,
    source_records: list[dict[str, Any]] | None = None,
    confidence: str = "Medium",
    needs_human_attention: str = "Yes",
    ai_error: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "success",
        "readiness": readiness,
        "direct_summary": direct_summary,
        "key_findings": key_findings or [],
        "risks": risks or [],
        "missing_information": missing_information or [],
        "suggested_actions": suggested_actions or [],
        "source_records": source_records or [],
        "confidence": confidence,
        "needs_human_attention": needs_human_attention,
        "ai_error": ai_error,
    }
    if extra:
        payload.update(extra)
    return payload


def run_ai_review_or_fallback(
    *,
    review_name: str,
    context: dict[str, Any],
    fallback: dict[str, Any],
    output_language: str = "English",
    temperature: float = 0.1,
) -> dict[str, Any]:
    """Ask the configured AI to polish a deterministic review. Never raises on API/config failure."""
    system_prompt = (
        "You are an AI business-control assistant embedded inside Zenith Business Control System. "
        "Use only the provided system records and deterministic checks. Do not invent missing data. "
        "If something is not present in current records, say it is not found in current system records. "
        "Do not make final commercial decisions. Return one JSON object only with these keys: "
        "status, readiness, direct_summary, key_findings, risks, missing_information, suggested_actions, "
        "source_records, confidence, needs_human_attention. Keep content concise and business-friendly."
    )
    user_prompt = json.dumps(
        {
            "review_name": review_name,
            "output_language": output_language,
            "safety_notice": STANDARD_AI_REVIEW_NOTICE,
            "deterministic_fallback_review": fallback,
            "context": context,
        },
        ensure_ascii=False,
        default=str,
    )
    try:
        ai_result = call_deepseek_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
        )
        merged = fallback.copy()
        for key in [
            "status",
            "readiness",
            "direct_summary",
            "key_findings",
            "risks",
            "missing_information",
            "suggested_actions",
            "source_records",
            "confidence",
            "needs_human_attention",
        ]:
            if key in ai_result:
                merged[key] = ai_result[key]
        merged["ai_error"] = ""
        merged["ai_used"] = True
        return normalize_review(merged)
    except (AIConfigError, AIResponseError, Exception) as exc:
        safe = fallback.copy()
        safe["ai_error"] = str(exc)
        safe["ai_used"] = False
        return normalize_review(safe)


def normalize_review(review: dict[str, Any]) -> dict[str, Any]:
    normalized = review.copy()
    for key in ["key_findings", "risks", "missing_information", "suggested_actions", "source_records"]:
        value = normalized.get(key)
        if value is None:
            normalized[key] = []
        elif isinstance(value, str):
            normalized[key] = [value] if value.strip() else []
        elif isinstance(value, list):
            normalized[key] = value
        else:
            normalized[key] = [value]
    normalized.setdefault("status", "success")
    normalized.setdefault("readiness", "Need Review")
    normalized.setdefault("direct_summary", "AI review generated from current system records.")
    normalized.setdefault("confidence", "Medium")
    normalized.setdefault("needs_human_attention", "Yes")
    normalized.setdefault("ai_error", "")
    normalized.setdefault("ai_used", False)
    return normalized


def review_to_markdown(review: dict[str, Any], title: str = "AI Review") -> str:
    review = normalize_review(review)
    lines = [
        f"# {title}",
        "",
        f"Readiness: {review.get('readiness', '-')}",
        f"Confidence: {review.get('confidence', '-')}",
        f"Needs Human Attention: {review.get('needs_human_attention', '-')}",
        "",
        "## Direct Summary",
        str(review.get("direct_summary") or "-"),
    ]
    sections = [
        ("Key Findings", review.get("key_findings") or []),
        ("Risks", review.get("risks") or []),
        ("Missing Information", review.get("missing_information") or []),
        ("Suggested Actions", review.get("suggested_actions") or []),
        ("Source Records", review.get("source_records") or []),
    ]
    for heading, items in sections:
        lines.extend(["", f"## {heading}"])
        if not items:
            lines.append("- -")
        else:
            for item in items:
                if isinstance(item, dict):
                    lines.append("- " + "; ".join(f"{k}: {v}" for k, v in item.items()))
                else:
                    lines.append(f"- {item}")
    if review.get("ai_error"):
        lines.extend(["", "## AI API Message", str(review.get("ai_error"))])
    return "\n".join(lines)


def review_to_dataframe(review: dict[str, Any]) -> pd.DataFrame:
    review = normalize_review(review)
    rows: list[dict[str, Any]] = []
    rows.append({"Section": "Summary", "Item": "Readiness", "Value": review.get("readiness")})
    rows.append({"Section": "Summary", "Item": "Direct Summary", "Value": review.get("direct_summary")})
    rows.append({"Section": "Summary", "Item": "Confidence", "Value": review.get("confidence")})
    rows.append({"Section": "Summary", "Item": "Needs Human Attention", "Value": review.get("needs_human_attention")})
    for key, label in [
        ("key_findings", "Key Finding"),
        ("risks", "Risk"),
        ("missing_information", "Missing Information"),
        ("suggested_actions", "Suggested Action"),
        ("source_records", "Source Record"),
    ]:
        for item in review.get(key) or []:
            value = item if not isinstance(item, dict) else json.dumps(item, ensure_ascii=False, default=str)
            rows.append({"Section": label, "Item": label, "Value": value})
    if review.get("ai_error"):
        rows.append({"Section": "AI API", "Item": "Message", "Value": review.get("ai_error")})
    return pd.DataFrame(rows)


def dataframe_to_csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


def flatten_workbook(workbook: dict[str, pd.DataFrame], row_limit_per_sheet: int = 40) -> dict[str, list[dict[str, Any]]]:
    flat: dict[str, list[dict[str, Any]]] = {}
    for name, df in (workbook or {}).items():
        if not isinstance(df, pd.DataFrame):
            continue
        clean = df.head(row_limit_per_sheet).fillna("").astype(str)
        flat[str(name)] = clean.to_dict(orient="records")
    return flat
