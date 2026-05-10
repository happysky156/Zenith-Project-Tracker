from __future__ import annotations

from typing import Any

import pandas as pd

from services.ai_business_review_common import clean_text, default_review, limit_records, review_to_dataframe, review_to_markdown, run_ai_review_or_fallback

QUOTE_FIELDS = [
    "supplier_quote_id", "project_id", "rfq_item_ref", "item_option", "supplier_code", "supplier_name",
    "supplier_unit_cost", "currency", "moq", "lead_time", "sample_cost", "tooling_cost", "packing_cost",
    "quote_validity", "selected_supplier", "recommended_supplier", "quotation_risk", "comparison_status", "remarks",
]


def _num(value: Any) -> float | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return float(text.replace(",", ""))
    except Exception:
        return None


def generate_ai_quotation_review(
    supplier_quotes: list[dict[str, Any]],
    client_headers: list[dict[str, Any]] | None = None,
    client_lines: list[dict[str, Any]] | None = None,
    *,
    project_id: str | None = None,
    rfq_item_ref: str | None = None,
    output_language: str = "English",
    use_ai: bool = True,
) -> dict[str, Any]:
    quotes = list(supplier_quotes or [])
    if project_id:
        quotes = [q for q in quotes if clean_text(q.get("project_id")) == clean_text(project_id)]
    if rfq_item_ref:
        quotes = [q for q in quotes if clean_text(q.get("rfq_item_ref")) == clean_text(rfq_item_ref)]
    headers = list(client_headers or [])
    lines = list(client_lines or [])

    if not quotes:
        return default_review(
            readiness="Not Ready",
            direct_summary="No supplier quotation records found in current system records for this review.",
            missing_information=["No Supplier Price Comparison records available."],
            suggested_actions=["Import supplier quotation records before running quotation review."],
            confidence="High",
        )

    costs = [(q, _num(q.get("supplier_unit_cost"))) for q in quotes]
    valid_costs = [(q, cost) for q, cost in costs if cost is not None]
    lowest = min(valid_costs, key=lambda x: x[1]) if valid_costs else None
    highest = max(valid_costs, key=lambda x: x[1]) if valid_costs else None
    selected = [q for q in quotes if clean_text(q.get("selected_supplier")).lower() in {"yes", "true", "1", "y", "selected"}]
    recommended = [q for q in quotes if clean_text(q.get("recommended_supplier")).lower() in {"yes", "true", "1", "y", "recommended"}]

    missing = []
    risks = []
    for q in quotes[:80]:
        label = f"{clean_text(q.get('project_id')) or '-'} / {clean_text(q.get('rfq_item_ref')) or '-'} / {clean_text(q.get('supplier_name')) or clean_text(q.get('supplier_code')) or 'supplier'}"
        row_missing = []
        for field, name in [
            ("supplier_unit_cost", "supplier unit cost"),
            ("currency", "currency"),
            ("moq", "MOQ"),
            ("lead_time", "lead time"),
            ("quote_validity", "quote validity"),
        ]:
            if field in q and not clean_text(q.get(field)):
                row_missing.append(name)
        if row_missing:
            missing.append(f"{label}: missing {', '.join(row_missing)}")
        if clean_text(q.get("quotation_risk")):
            risks.append(f"{label}: {clean_text(q.get('quotation_risk'))}")
        if not clean_text(q.get("supplier_code")):
            risks.append(f"{label}: supplier code not found")

    if not selected and not recommended:
        risks.append("No selected or recommended supplier is marked in current quotation records.")
    if not any(clean_text(q.get("packing_cost")) for q in quotes):
        risks.append("Packing cost not found in supplier quote records.")
    if not headers and not lines:
        risks.append("No client quotation header/line records found in current system records.")

    findings = [
        f"Supplier quote records reviewed: {len(quotes)}",
        f"Lowest unit cost: {clean_text(lowest[0].get('supplier_name')) if lowest else 'not found'} {lowest[1] if lowest else ''}",
        f"Highest unit cost: {clean_text(highest[0].get('supplier_name')) if highest else 'not found'} {highest[1] if highest else ''}",
        f"Selected supplier rows: {len(selected)}; recommended supplier rows: {len(recommended)}",
    ]
    readiness = "Not Ready" if not valid_costs else ("Need Review" if missing or risks else "Ready")
    fallback = default_review(
        readiness=readiness,
        direct_summary=f"Quotation review covered {len(quotes)} supplier quote record(s). Readiness: {readiness}. AI does not select supplier or generate final client price.",
        key_findings=findings,
        risks=risks[:30],
        missing_information=missing[:30],
        suggested_actions=[
            "Confirm missing cost, currency, MOQ, lead time and quote validity before sending client quotation.",
            "Review selected/recommended supplier manually; AI must not make the final supplier choice.",
            "Check market index/exchange-rate snapshot if linked to this quotation.",
        ],
        source_records=limit_records(quotes, QUOTE_FIELDS, limit=30),
        confidence="Medium" if missing or risks else "High",
        needs_human_attention="Yes" if readiness != "Ready" else "No",
        extra={"lowest_price": findings[1], "highest_price": findings[2], "selected_count": len(selected), "recommended_count": len(recommended)},
    )
    if not use_ai:
        return fallback
    context = {
        "supplier_quotes": limit_records(quotes, QUOTE_FIELDS, limit=35),
        "client_headers": limit_records(headers, limit=10),
        "client_lines": limit_records(lines, limit=20),
        "deterministic_review": fallback,
    }
    result = run_ai_review_or_fallback(review_name="AI Quotation Review", context=context, fallback=fallback, output_language=output_language)
    for key in ["lowest_price", "highest_price", "selected_count", "recommended_count"]:
        result.setdefault(key, fallback.get(key))
    return result


def quotation_review_to_markdown(review: dict[str, Any]) -> str:
    return review_to_markdown(review, title="AI Quotation Review")


def quotation_review_to_dataframe(review: dict[str, Any]) -> pd.DataFrame:
    return review_to_dataframe(review)
