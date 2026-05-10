from __future__ import annotations

from typing import Any

import pandas as pd

from services.ai_business_review_common import clean_text, compact_record, default_review, limit_records, review_to_dataframe, review_to_markdown, run_ai_review_or_fallback

RFQ_FIELDS = [
    "rfq_id", "project_id", "customer", "product_description", "rfq_gate_status", "risk_level",
    "drawing_received", "specification_received", "quantity_confirmed", "packaging_requirement",
    "testing_requirement", "compliance_requirement", "sample_required", "inspection_required",
    "missing_information", "quality_compliance_risk", "commercial_business_risk", "current_owner", "next_step", "due_date",
]


def _yes(value: Any) -> bool:
    return clean_text(value).lower() in {"yes", "y", "true", "1", "received", "confirmed", "done", "ok"}


def generate_ai_rfq_review(
    rfq_records: list[dict[str, Any]],
    supplier_quotes: list[dict[str, Any]] | None = None,
    *,
    rfq_id: str | None = None,
    output_language: str = "English",
    use_ai: bool = True,
) -> dict[str, Any]:
    records = list(rfq_records or [])
    if rfq_id:
        records = [r for r in records if clean_text(r.get("rfq_id")) == clean_text(rfq_id)]
    quotes = list(supplier_quotes or [])
    if not records:
        return default_review(
            readiness="Not Ready",
            direct_summary="No RFQ Requirement Control records found in current system records.",
            missing_information=["No RFQ records available for review."],
            suggested_actions=["Import RFQ Requirement Control records before running the review."],
            confidence="High",
        )

    review_records = records[:80]
    missing = []
    risks = []
    findings = []
    questions = []
    for row in review_records:
        label = clean_text(row.get("rfq_id")) or clean_text(row.get("project_id")) or "RFQ record"
        row_missing = []
        checks = [
            ("drawing_received", "drawing"),
            ("specification_received", "specification"),
            ("quantity_confirmed", "quantity"),
            ("packaging_requirement", "packing requirement"),
            ("testing_requirement", "testing requirement"),
            ("compliance_requirement", "compliance requirement"),
        ]
        for field, name in checks:
            if field in row and not _yes(row.get(field)) and not clean_text(row.get(field)):
                row_missing.append(name)
        if clean_text(row.get("missing_information")):
            row_missing.append(f"missing info note: {clean_text(row.get('missing_information'))}")
        if row_missing:
            missing.append(f"{label}: {', '.join(row_missing)}")
        if clean_text(row.get("risk_level")).lower() in {"high", "medium"}:
            risks.append(f"{label}: risk level is {clean_text(row.get('risk_level'))}")
        if clean_text(row.get("quality_compliance_risk")):
            risks.append(f"{label}: quality/compliance risk - {clean_text(row.get('quality_compliance_risk'))}")
        if clean_text(row.get("commercial_business_risk")):
            risks.append(f"{label}: commercial/business risk - {clean_text(row.get('commercial_business_risk'))}")
        if row_missing:
            questions.append(f"For {label}, please confirm: {', '.join(row_missing[:4])}.")
        findings.append(f"{label}: status {clean_text(row.get('rfq_gate_status')) or 'not found'}, owner {clean_text(row.get('current_owner')) or 'not assigned'}")

    project_ids = {clean_text(r.get("project_id")) for r in review_records if clean_text(r.get("project_id"))}
    related_quotes = [q for q in quotes if clean_text(q.get("project_id")) in project_ids] if project_ids else []
    if not related_quotes:
        risks.append("No related supplier quote records found for reviewed RFQ project(s) in current system records.")

    readiness = "Not Ready" if missing else ("Need Review" if risks else "Ready")
    fallback = default_review(
        readiness=readiness,
        direct_summary=f"RFQ review covered {len(review_records)} RFQ record(s) and {len(related_quotes)} related supplier quote record(s). Readiness: {readiness}.",
        key_findings=findings[:20],
        risks=risks[:30],
        missing_information=missing[:30],
        suggested_actions=(questions[:12] + ["Confirm missing RFQ requirements before final quotation or production commitment."])[0:20],
        source_records=limit_records(review_records, RFQ_FIELDS, limit=25),
        confidence="Medium" if missing else "High",
        needs_human_attention="Yes" if readiness != "Ready" else "No",
        extra={"questions_to_ask_client": questions[:20], "related_quote_count": len(related_quotes)},
    )
    if not use_ai:
        return fallback
    context = {
        "rfq_records": limit_records(review_records, RFQ_FIELDS, limit=30),
        "supplier_quote_sample": limit_records(related_quotes, limit=30),
        "deterministic_review": fallback,
    }
    result = run_ai_review_or_fallback(review_name="AI RFQ Completeness Check", context=context, fallback=fallback, output_language=output_language)
    result.setdefault("questions_to_ask_client", fallback.get("questions_to_ask_client", []))
    result.setdefault("related_quote_count", fallback.get("related_quote_count", 0))
    return result


def rfq_review_to_markdown(review: dict[str, Any]) -> str:
    return review_to_markdown(review, title="AI RFQ Completeness Check")


def rfq_review_to_dataframe(review: dict[str, Any]) -> pd.DataFrame:
    rows = review_to_dataframe(review)
    if review.get("questions_to_ask_client"):
        rows = pd.concat([rows, pd.DataFrame([{"Section": "Questions to Ask Client", "Item": "Question", "Value": q} for q in review.get("questions_to_ask_client")])], ignore_index=True)
    return rows
