from __future__ import annotations

from typing import Any

import pandas as pd

from services.ai_business_review_common import clean_text, compact_record, default_review, limit_records, review_to_dataframe, review_to_markdown, run_ai_review_or_fallback
from services.upgrade_service import list_module_records, list_order_module_records_by_archive_view

SUPPLIER_FIELDS = [
    "supplier_id", "supplier_code", "supplier_name", "supplier_short_name", "company_type", "country", "province", "city",
    "primary_contact_name", "primary_contact_mobile", "primary_contact_email", "certificate", "export_license",
    "nda_status", "audit_status", "catalogue_status", "main_products", "main_process", "material_capability",
    "testing_capability", "quality_risk", "commercial_risk", "active_status", "last_order_no", "last_project_id",
    "price_comparison_count", "order_count", "risk_summary",
]


def _matches_supplier(row: dict[str, Any], supplier: dict[str, Any]) -> bool:
    codes = {clean_text(supplier.get("supplier_code")), clean_text(supplier.get("supplier_id"))}
    names = {clean_text(supplier.get("supplier_name")), clean_text(supplier.get("supplier_short_name"))}
    codes.discard("")
    names.discard("")
    return (clean_text(row.get("supplier_code")) in codes) or (clean_text(row.get("supplier_id")) in codes) or (clean_text(row.get("supplier_name")) in names)


def generate_ai_supplier_risk_summary(
    supplier_record: dict[str, Any],
    *,
    output_language: str = "English",
    use_ai: bool = True,
) -> dict[str, Any]:
    supplier_record = supplier_record or {}
    if not supplier_record:
        return default_review(
            readiness="Not Ready",
            direct_summary="No supplier record selected for AI risk summary.",
            missing_information=["No selected Supplier Details record."],
            confidence="High",
        )

    try:
        quote_rows = [r for r in list_module_records("Supplier Price Comparison", limit=2000) if _matches_supplier(r, supplier_record)]
    except Exception:
        quote_rows = []
    try:
        order_rows = [r for r in list_order_module_records_by_archive_view("Order Details", limit=2000, archive_view="All") if _matches_supplier(r, supplier_record)]
    except Exception:
        order_rows = []

    missing = []
    for field, label in [
        ("supplier_code", "Supplier Code"),
        ("primary_contact_name", "Primary Contact Name"),
        ("primary_contact_email", "Primary Contact Email"),
        ("certificate", "Certificate"),
        ("audit_status", "Audit Status"),
        ("catalogue_status", "Catalogue Status"),
        ("main_products", "Main Products"),
    ]:
        if not clean_text(supplier_record.get(field)):
            missing.append(f"{label} not found in current supplier record")

    risks = []
    for field, label in [("quality_risk", "Quality risk"), ("commercial_risk", "Commercial risk")]:
        value = clean_text(supplier_record.get(field))
        if value:
            risks.append(f"{label}: {value}")
    if not quote_rows:
        risks.append("No supplier quotation records found for this supplier in current system records.")
    if not order_rows:
        risks.append("No order detail records found for this supplier in current system records.")

    findings = [
        f"Supplier: {clean_text(supplier_record.get('supplier_code')) or clean_text(supplier_record.get('supplier_id'))} · {clean_text(supplier_record.get('supplier_name'))}",
        f"Activity: {len(quote_rows)} quote record(s), {len(order_rows)} order detail record(s).",
        f"Location: {clean_text(supplier_record.get('city')) or '-'}, {clean_text(supplier_record.get('country')) or '-'}",
    ]

    readiness = "High Risk" if any("High" in r for r in risks) else ("Need Review" if missing or risks else "Ready")
    fallback = default_review(
        readiness=readiness,
        direct_summary=f"Supplier risk summary generated for {clean_text(supplier_record.get('supplier_name')) or 'selected supplier'}. Data completeness issues: {len(missing)}. Quote records: {len(quote_rows)}. Order records: {len(order_rows)}.",
        key_findings=findings,
        risks=risks,
        missing_information=missing,
        suggested_actions=[
            "Complete missing supplier master data before using this supplier for urgent orders.",
            "Review quotation and order history before supplier selection.",
            "Do not treat this AI summary as supplier approval or rejection.",
        ],
        source_records=[compact_record(supplier_record, SUPPLIER_FIELDS)] + limit_records(quote_rows, limit=10) + limit_records(order_rows, limit=10),
        confidence="Medium" if missing else "High",
        needs_human_attention="Yes" if readiness != "Ready" else "No",
        extra={"quote_count": len(quote_rows), "order_count": len(order_rows)},
    )
    if not use_ai:
        return fallback
    context = {
        "supplier_record": compact_record(supplier_record, SUPPLIER_FIELDS),
        "quote_records": limit_records(quote_rows, limit=20),
        "order_records": limit_records(order_rows, limit=20),
        "deterministic_review": fallback,
    }
    result = run_ai_review_or_fallback(review_name="AI Supplier Risk Summary", context=context, fallback=fallback, output_language=output_language)
    result.setdefault("quote_count", len(quote_rows))
    result.setdefault("order_count", len(order_rows))
    return result


def supplier_review_to_markdown(review: dict[str, Any]) -> str:
    return review_to_markdown(review, title="AI Supplier Risk Summary")


def supplier_review_to_dataframe(review: dict[str, Any]) -> pd.DataFrame:
    return review_to_dataframe(review)
