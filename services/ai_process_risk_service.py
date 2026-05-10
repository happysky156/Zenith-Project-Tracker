from __future__ import annotations

from typing import Any

import pandas as pd

from services.ai_business_review_common import clean_text, default_review, limit_records, review_to_dataframe, review_to_markdown, run_ai_review_or_fallback


def generate_ai_process_risk_summary(
    *,
    process_code: str,
    definition: dict[str, Any],
    control_points: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    output_language: str = "English",
    use_ai: bool = True,
) -> dict[str, Any]:
    definition = definition or {}
    control_points = list(control_points or [])
    rows = list(rows or [])

    missing = []
    risks = []
    if not rows:
        missing.append("No mapped business records found for this process in current system records.")
    if not control_points:
        missing.append("No control points found for this process definition.")

    for row in rows[:120]:
        label = clean_text(row.get("project_id")) or clean_text(row.get("order_no")) or clean_text(row.get("rfq_id")) or clean_text(row.get("supplier_code")) or "record"
        for field in ["risk_level", "quality_risk", "commercial_risk", "quotation_risk"]:
            value = clean_text(row.get(field))
            if value and value.lower() in {"high", "medium"}:
                risks.append(f"{label}: {field} = {value}")
        for field in ["missing_information", "block_point", "main_issue"]:
            value = clean_text(row.get(field))
            if value:
                risks.append(f"{label}: {field} - {value}")

    findings = [
        f"Process: {process_code} · {definition.get('short_name') or definition.get('process_name') or '-'}",
        f"Process status: {definition.get('status') or '-'}; owner: {definition.get('owner') or '-'}",
        f"Mapped records: {len(rows)}; control points: {len(control_points)}",
    ]
    readiness = "Need Review" if risks or missing else "Ready"
    fallback = default_review(
        readiness=readiness,
        direct_summary=f"Process risk summary generated for {process_code}. Mapped records: {len(rows)}. Control points: {len(control_points)}. Readiness: {readiness}.",
        key_findings=findings,
        risks=risks[:35],
        missing_information=missing,
        suggested_actions=[
            "Review key risk points against the formal control points.",
            "Add missing evidence or records before changing process status.",
            "Save any process impact assessment only after human confirmation.",
        ],
        source_records=limit_records(rows, limit=30),
        confidence="Medium" if missing else "High",
        needs_human_attention="Yes" if readiness != "Ready" else "No",
        extra={"process_code": process_code, "process_name": definition.get("process_name") or definition.get("short_name")},
    )
    if not use_ai:
        return fallback
    context = {
        "process_definition": definition,
        "control_points": control_points,
        "mapped_records": limit_records(rows, limit=35),
        "deterministic_review": fallback,
    }
    result = run_ai_review_or_fallback(review_name="AI Process & Risk Control Summary", context=context, fallback=fallback, output_language=output_language)
    result.setdefault("process_code", process_code)
    result.setdefault("process_name", definition.get("process_name") or definition.get("short_name"))
    return result


def process_review_to_markdown(review: dict[str, Any]) -> str:
    return review_to_markdown(review, title="AI Process Risk Summary")


def process_review_to_dataframe(review: dict[str, Any]) -> pd.DataFrame:
    return review_to_dataframe(review)
