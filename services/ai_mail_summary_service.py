from __future__ import annotations

from typing import Any

import pandas as pd

from services.ai_business_review_common import clean_text, default_review, flatten_workbook, review_to_dataframe, review_to_markdown, run_ai_review_or_fallback


def _find_mentions(workbook: dict[str, pd.DataFrame]) -> list[str]:
    mentions = []
    keywords = ["project", "project id", "sdg", "order", "po", "client", "attachment", "drawing", "quote", "sample"]
    for sheet, df in (workbook or {}).items():
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue
        text = " ".join(df.head(80).fillna("").astype(str).to_numpy().flatten().tolist()).lower()
        found = [kw for kw in keywords if kw in text]
        if found:
            mentions.append(f"{sheet}: possible mention(s) of {', '.join(found[:8])}")
    return mentions[:20]


def generate_ai_mail_summary(workbook: dict[str, pd.DataFrame], *, output_language: str = "English", use_ai: bool = True) -> dict[str, Any]:
    workbook = workbook or {}
    if not workbook:
        return default_review(
            readiness="Not Ready",
            direct_summary="No workbook data available for AI Mail Summary.",
            missing_information=["No uploaded mail tracker workbook."],
            confidence="High",
        )
    sheet_rows = {name: len(df) for name, df in workbook.items() if isinstance(df, pd.DataFrame)}
    mentions = _find_mentions(workbook)
    findings = [f"{name}: {count} row(s)" for name, count in sheet_rows.items()]
    fallback = default_review(
        readiness="Need Review",
        direct_summary=f"Mail workbook summary generated from {len(sheet_rows)} sheet(s). This does not write to the project database.",
        key_findings=findings,
        risks=["Mail summary is based only on the uploaded workbook preview, not the full project database."],
        missing_information=[] if mentions else ["No obvious Project ID / Order No / attachment mentions detected in sampled rows."],
        suggested_actions=mentions + ["Review the workbook manually before updating any project, order or meeting fields."],
        source_records=[{"sheet": name, "rows": count} for name, count in sheet_rows.items()],
        confidence="Medium",
        needs_human_attention="Yes",
        extra={"possible_mentions": mentions},
    )
    if not use_ai:
        return fallback
    context = {"workbook_sample": flatten_workbook(workbook), "deterministic_review": fallback}
    result = run_ai_review_or_fallback(review_name="AI Mail Summary", context=context, fallback=fallback, output_language=output_language)
    result.setdefault("possible_mentions", mentions)
    return result


def mail_summary_to_markdown(review: dict[str, Any]) -> str:
    return review_to_markdown(review, title="AI Mail Summary")


def mail_summary_to_dataframe(review: dict[str, Any]) -> pd.DataFrame:
    return review_to_dataframe(review)
