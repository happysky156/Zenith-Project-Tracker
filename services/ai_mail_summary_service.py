from __future__ import annotations

from typing import Any

import pandas as pd

from services.ai_business_review_common import clean_text, default_review, flatten_workbook, review_to_dataframe, review_to_markdown, run_ai_review_or_fallback


def _find_mentions(workbook: dict[str, pd.DataFrame]) -> list[str]:
    mentions = []
    keywords = ["project", "project id", "sdg", "order", "po", "client", "attachment", "drawing", "quote", "sample", "inspection", "packing", "delay"]
    for sheet, df in (workbook or {}).items():
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue
        text = " ".join(df.head(120).fillna("").astype(str).to_numpy().flatten().tolist()).lower()
        found = [kw for kw in keywords if kw in text]
        if found:
            mentions.append(f"{sheet}: possible mention(s) of {', '.join(found[:10])}")
    return mentions[:30]


def generate_ai_mail_summary(
    workbook: dict[str, pd.DataFrame],
    *,
    output_language: str = "English",
    use_ai: bool = True,
    keywords: list[str] | None = None,
    date_filter: str | None = None,
    project_context: dict[str, Any] | None = None,
    matched_record_count: int | None = None,
) -> dict[str, Any]:
    """Summarise uploaded Mail Tracker workbook data without writing to the project database."""
    workbook = workbook or {}
    keywords = [clean_text(k) for k in (keywords or []) if clean_text(k)]
    project_context = project_context or {}

    if not workbook:
        return default_review(
            readiness="Not Ready",
            direct_summary="No workbook data available for AI Mail Summary.",
            missing_information=["No uploaded mail tracker workbook."],
            confidence="High",
        )

    sheet_rows = {name: len(df) for name, df in workbook.items() if isinstance(df, pd.DataFrame)}
    total_rows = sum(sheet_rows.values())
    mentions = _find_mentions(workbook)
    findings = [f"{name}: {count} matched row(s)" for name, count in sheet_rows.items()]

    if keywords:
        findings.append(f"Keyword filter: {', '.join(keywords)}")
    if date_filter:
        findings.append(f"Date filter: {date_filter}")
    if project_context:
        project_bits = []
        for key in ["project_id", "project_name", "order_no", "client_code"]:
            value = clean_text(project_context.get(key))
            if value:
                project_bits.append(f"{key}: {value}")
        if project_bits:
            findings.append("Project matching context: " + "; ".join(project_bits))

    no_match = total_rows == 0
    direct_summary = (
        "No mail rows matched the current keyword / date / project filters. No project database records were changed."
        if no_match
        else f"AI Mail Summary generated from {total_rows} matched mail row(s) across {len(sheet_rows)} sheet(s). This is read-only and does not write to the project database."
    )

    fallback = default_review(
        readiness="Not Ready" if no_match else "Need Review",
        direct_summary=direct_summary,
        key_findings=findings,
        risks=[
            "Mail Tracker is import-and-view only in this system. This AI summary must not create Project IDs or update Sales / Operation / Meeting records.",
            "Matched emails should be checked against formal system records before any manual project update.",
        ],
        missing_information=[] if mentions else ["No obvious Project ID / Order No / attachment mentions detected in sampled matched rows."],
        suggested_actions=(
            ["Adjust keywords, date range, or project search context if no relevant mails are shown."]
            if no_match
            else mentions
            + [
                "Review matched mail rows before manually updating project records.",
                "Check whether customer requests in mail are already reflected in Meeting Board / Project Board.",
                "If mail mentions a project issue not found in system records, add it manually through the relevant business page after review.",
            ]
        ),
        source_records=[{"sheet": name, "matched_rows": count} for name, count in sheet_rows.items()],
        confidence="Medium",
        needs_human_attention="Yes",
        extra={
            "possible_mentions": mentions,
            "keywords": keywords,
            "date_filter": date_filter or "All uploaded mails",
            "project_context": project_context,
            "matched_record_count": matched_record_count if matched_record_count is not None else total_rows,
            "read_only_boundary": "Mail Tracker can only import and view uploaded workbook data. It cannot write into the project database.",
        },
    )
    if not use_ai or no_match:
        return fallback

    context = {
        "workbook_sample": flatten_workbook(workbook),
        "filters": {
            "keywords": keywords,
            "date_filter": date_filter or "All uploaded mails",
            "project_context": project_context,
            "matched_record_count": matched_record_count if matched_record_count is not None else total_rows,
        },
        "required_output_focus": [
            "Key Client Requests",
            "Open Actions",
            "Possible Project ID / Order No Mentions",
            "Inconsistency with System Records if project_context is provided",
            "Suggested Follow-up",
        ],
        "hard_boundary": "Do not write to the project database. Do not create Project ID. Do not update Sales, Operation, or Meeting fields.",
        "deterministic_review": fallback,
    }
    result = run_ai_review_or_fallback(review_name="AI Mail Search & Summary", context=context, fallback=fallback, output_language=output_language)
    result.setdefault("possible_mentions", mentions)
    result.setdefault("keywords", keywords)
    result.setdefault("date_filter", date_filter or "All uploaded mails")
    result.setdefault("project_context", project_context)
    result.setdefault("read_only_boundary", "Mail Tracker can only import and view uploaded workbook data. It cannot write into the project database.")
    return result


def mail_summary_to_markdown(review: dict[str, Any]) -> str:
    return review_to_markdown(review, title="AI Mail Summary")


def mail_summary_to_dataframe(review: dict[str, Any]) -> pd.DataFrame:
    return review_to_dataframe(review)
