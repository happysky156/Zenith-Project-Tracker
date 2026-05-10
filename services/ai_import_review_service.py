from __future__ import annotations

from typing import Any

import pandas as pd

from services.ai_business_review_common import (
    clean_text,
    default_review,
    limit_records,
    run_ai_review_or_fallback,
    review_to_dataframe,
    review_to_markdown,
)


def _similar_columns(columns: list[str], target: str) -> list[str]:
    target_norm = target.lower().replace("_", " ").replace("-", " ")
    parts = [p for p in target_norm.split() if len(p) >= 3]
    matches = []
    for col in columns:
        col_norm = str(col).lower().replace("_", " ").replace("-", " ")
        if col_norm == target_norm or any(p in col_norm for p in parts):
            matches.append(str(col))
    return matches[:5]


def generate_ai_import_review(
    *,
    raw_df: pd.DataFrame,
    mapped_df: pd.DataFrame,
    module_name: str,
    mapping: dict[str, Any],
    required_fields: list[str] | tuple[str, ...],
    validation_errors: list[str] | None = None,
    validation_info: dict[str, Any] | None = None,
    output_language: str = "English",
    use_ai: bool = True,
) -> dict[str, Any]:
    raw_df = raw_df if isinstance(raw_df, pd.DataFrame) else pd.DataFrame()
    mapped_df = mapped_df if isinstance(mapped_df, pd.DataFrame) else pd.DataFrame()
    validation_errors = list(validation_errors or [])
    validation_info = validation_info or {}

    missing_required_rows: list[str] = []
    for field in required_fields:
        if field not in mapped_df.columns:
            missing_required_rows.append(f"Required field not mapped: {field}")
            continue
        missing_count = int(mapped_df[field].isna().sum() + (mapped_df[field].astype(str).str.strip() == "").sum())
        if missing_count:
            missing_required_rows.append(f"{field}: {missing_count} blank row(s)")

    unmapped_targets = [field for field, col in (mapping or {}).items() if not clean_text(col) or clean_text(col) == "-- Not mapped --"]
    mapped_columns = {str(col) for col in (mapping or {}).values() if clean_text(col) and clean_text(col) != "-- Not mapped --"}
    unmapped_source_columns = [str(c) for c in raw_df.columns if str(c) not in mapped_columns]

    duplicate_warnings = []
    key_candidates = [field for field in ["project_id", "order_no", "supplier_code", "rfq_id", "supplier_quote_id", "client_quote_id"] if field in mapped_df.columns]
    for key in key_candidates:
        dup_count = int(mapped_df[key].astype(str).str.strip().replace("", pd.NA).duplicated().sum()) if not mapped_df.empty else 0
        if dup_count:
            duplicate_warnings.append(f"{key}: {dup_count} possible duplicate row(s) inside uploaded file")
    if "_exists" in mapped_df.columns:
        exists_count = int(mapped_df["_exists"].astype(str).str.lower().isin(["true", "1", "yes"]).sum())
        if exists_count:
            duplicate_warnings.append(f"{exists_count} row(s) appear to already exist in the current database preview")

    format_warnings = []
    for col in mapped_df.columns:
        col_l = col.lower()
        if "date" in col_l:
            sample = mapped_df[col].dropna().astype(str).head(30)
            bad = 0
            for value in sample:
                text = value.strip()
                if not text:
                    continue
                try:
                    pd.to_datetime(text)
                except Exception:
                    bad += 1
            if bad:
                format_warnings.append(f"{col}: {bad} suspicious date value(s) in first 30 non-empty rows")
        if any(token in col_l for token in ["qty", "cost", "price", "amount", "rate", "moq"]):
            sample = mapped_df[col].dropna().astype(str).head(30)
            bad = 0
            for value in sample:
                text = value.replace(",", "").strip()
                if not text:
                    continue
                try:
                    float(text)
                except Exception:
                    bad += 1
            if bad:
                format_warnings.append(f"{col}: {bad} suspicious numeric value(s) in first 30 non-empty rows")

    mapping_suggestions = []
    for target in unmapped_targets[:20]:
        candidates = _similar_columns([str(c) for c in raw_df.columns], target)
        if candidates:
            mapping_suggestions.append(f"{target}: possible source column(s): {', '.join(candidates)}")

    risk_count = len(missing_required_rows) + len(validation_errors) + len(duplicate_warnings)
    readiness = "High Risk" if validation_errors or missing_required_rows else ("Need Review" if duplicate_warnings or format_warnings else "Ready")
    fallback = default_review(
        readiness=readiness,
        direct_summary=f"Import review for {module_name}: {len(mapped_df)} mapped row(s), {len(raw_df.columns)} source column(s). Readiness: {readiness}.",
        key_findings=[
            f"Mapped rows: {len(mapped_df)}",
            f"Required fields checked: {', '.join(required_fields) if required_fields else 'Not defined'}",
            f"Unmapped source columns: {len(unmapped_source_columns)}",
        ],
        risks=validation_errors + duplicate_warnings + format_warnings,
        missing_information=missing_required_rows + mapping_suggestions,
        suggested_actions=[
            "Review missing required fields before confirming import.",
            "Check duplicate warnings before writing records.",
            "Use the existing Confirm Import button only after validation is ready.",
        ],
        source_records=limit_records(mapped_df.head(20).fillna("").astype(str).to_dict(orient="records"), limit=20),
        confidence="High" if risk_count else "Medium",
        needs_human_attention="Yes" if readiness != "Ready" else "No",
        extra={
            "unmapped_columns": unmapped_source_columns[:50],
            "mapping_suggestions": mapping_suggestions,
            "validation_info": validation_info,
        },
    )
    if not use_ai:
        return fallback
    context = {
        "module_name": module_name,
        "mapping": mapping,
        "required_fields": list(required_fields or []),
        "validation_errors": validation_errors,
        "validation_info": validation_info,
        "rule_review": fallback,
        "sample_mapped_rows": limit_records(mapped_df.head(20).fillna("").astype(str).to_dict(orient="records"), limit=20),
    }
    result = run_ai_review_or_fallback(review_name="AI Import Assistant", context=context, fallback=fallback, output_language=output_language)
    for key in ["unmapped_columns", "mapping_suggestions", "validation_info"]:
        result.setdefault(key, fallback.get(key))
    return result


def import_review_to_markdown(review: dict[str, Any]) -> str:
    return review_to_markdown(review, title="AI Import Review")


def import_review_to_dataframe(review: dict[str, Any]) -> pd.DataFrame:
    return review_to_dataframe(review)
