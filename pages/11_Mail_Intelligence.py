from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
import streamlit as st

from core.auth import require_login
from database.mail_tracker_repository import list_mail_tracker_batches, save_mail_tracker_workbook
from services.ai_mail_summary_service import generate_ai_mail_summary
from services.ai_meeting_service import search_project_candidates
from ui.ai_review_ui import render_ai_review
from ui.theme import apply_theme, render_page_header

apply_theme()
current_user = require_login()
render_page_header(
    "Mail Intelligence",
    "Mail Tracker workbook import, isolated database storage, keyword search and AI follow-up summary.",
)

st.info(
    "Mail Tracker boundary: uploaded mail tracker data may be saved into isolated Mail Tracker database tables for later reference. "
    "It does not automatically update Sales, Operation, Meeting, RFQ or Supplier records unless a future workflow explicitly links records after review."
)


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def _split_keywords(value: str) -> list[str]:
    raw = (value or "").replace("\n", ",").replace(";", ",")
    terms = []
    for part in raw.split(","):
        text = part.strip()
        if text:
            terms.append(text)
    return terms


def _row_text(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series([], dtype=str)
    return df.fillna("").astype(str).agg(" ".join, axis=1).str.lower()


def _find_date_columns(df: pd.DataFrame) -> list[str]:
    candidates = []
    for col in df.columns:
        name = str(col).strip().lower()
        if any(token in name for token in ["date", "time", "sent", "received", "mail_time", "created"]):
            candidates.append(str(col))
    return candidates


def _apply_date_mask(df: pd.DataFrame, start_date: date | None, end_date: date | None) -> tuple[pd.Series, str]:
    if start_date is None and end_date is None:
        return pd.Series([True] * len(df), index=df.index), "All dates"
    date_cols = _find_date_columns(df)
    if not date_cols:
        # Keep rows rather than hiding possible relevant mails when the workbook has no detectable date column.
        return pd.Series([True] * len(df), index=df.index), "No detectable date column; date filter not applied to this sheet"
    combined = pd.Series([False] * len(df), index=df.index)
    for col in date_cols:
        parsed = pd.to_datetime(df[col], errors="coerce").dt.date
        mask = pd.Series([True] * len(df), index=df.index)
        if start_date is not None:
            mask &= parsed >= start_date
        if end_date is not None:
            mask &= parsed <= end_date
        combined |= mask.fillna(False)
    label = f"{start_date or '-'} to {end_date or '-'} via {', '.join(date_cols[:3])}"
    return combined, label


def _project_terms(candidate: dict[str, Any] | None, manual_query: str) -> list[str]:
    terms = []
    if manual_query.strip():
        terms.append(manual_query.strip())
    if candidate:
        for key in ["project_id", "project_name", "order_no", "client_code"]:
            value = _clean(candidate.get(key))
            if value:
                terms.append(value)
    # De-duplicate but preserve order.
    seen = set()
    final = []
    for term in terms:
        key = term.casefold()
        if key not in seen:
            final.append(term)
            seen.add(key)
    return final


def _project_context(candidate: dict[str, Any] | None, manual_query: str) -> dict[str, Any]:
    if not candidate:
        return {"manual_project_query": manual_query.strip()} if manual_query.strip() else {}
    return {
        "record_type": candidate.get("record_type"),
        "project_id": candidate.get("project_id"),
        "project_name": candidate.get("project_name"),
        "order_no": candidate.get("order_no"),
        "client_code": candidate.get("client_code"),
        "current_owner": candidate.get("current_owner"),
        "phase": candidate.get("phase"),
        "manual_project_query": manual_query.strip(),
    }


def _filter_workbook(
    workbook: dict[str, pd.DataFrame],
    *,
    keywords: list[str],
    project_terms: list[str],
    start_date: date | None,
    end_date: date | None,
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]], str]:
    filtered: dict[str, pd.DataFrame] = {}
    preview_rows: list[dict[str, Any]] = []
    date_notes: list[str] = []
    all_terms = [*keywords, *project_terms]
    lowered_terms = [t.casefold() for t in all_terms if t]

    for sheet_name, df in (workbook or {}).items():
        if not isinstance(df, pd.DataFrame) or df.empty:
            continue
        mask = pd.Series([True] * len(df), index=df.index)
        date_mask, date_note = _apply_date_mask(df, start_date, end_date)
        mask &= date_mask
        if date_note and date_note not in date_notes:
            date_notes.append(date_note)

        if lowered_terms:
            text = _row_text(df)
            term_mask = pd.Series([False] * len(df), index=df.index)
            for term in lowered_terms:
                term_mask |= text.str.contains(term, case=False, regex=False, na=False)
            mask &= term_mask

        matched = df[mask].copy()
        if not matched.empty:
            matched.insert(0, "_source_sheet", sheet_name)
            matched.insert(1, "_source_row", matched.index.astype(int) + 2)
            filtered[sheet_name] = matched
            for _, row in matched.head(40).iterrows():
                row_dict = {k: _clean(v) for k, v in row.to_dict().items()}
                preview_rows.append(row_dict)

    date_label = "; ".join(date_notes[:5]) if date_notes else "All dates"
    return filtered, preview_rows[:120], date_label


uploaded = st.file_uploader(
    "Upload mail_tracker_clean.xlsx",
    type=["xlsx", "xls"],
    help="Upload the Mail Tracker workbook. You can preview it, run AI summary, and optionally save it into isolated Mail Tracker tables.",
)
if not uploaded:
    st.info("Upload the mail tracker clean workbook to preview Mail Overview, Action Tracker and Attachment Summary.")
    st.stop()

try:
    workbook = pd.read_excel(uploaded, sheet_name=None)
except Exception as exc:
    st.error(f"Could not read workbook: {type(exc).__name__}: {exc}")
    st.stop()

st.markdown("### Mail Tracker Database Storage")
st.caption("Optional: save this uploaded workbook into isolated Mail Tracker tables. This does not update Sales, Operation, Meeting, RFQ or Supplier records.")
store_cols = st.columns([1.2, 1.0, 1.0])
with store_cols[0]:
    if st.button("Save Uploaded Mail Tracker to Database", use_container_width=True):
        try:
            result = save_mail_tracker_workbook(
                workbook,
                source_file=getattr(uploaded, "name", "mail_tracker_clean.xlsx"),
                imported_by=str(current_user.get("display_name") or current_user.get("email") or ""),
                file_bytes=uploaded.getvalue(),
                notes="Saved from Mail Intelligence page. Isolated Mail Tracker storage only.",
            )
            st.success(f"Saved Mail Tracker batch {result.get('batch_id')} with {result.get('inserted_rows')} row(s).")
        except Exception as exc:
            st.error(f"Could not save Mail Tracker workbook: {type(exc).__name__}: {exc}")
with store_cols[1]:
    if st.button("Show Recent Mail Tracker Imports", use_container_width=True):
        st.session_state["show_mail_tracker_imports"] = not st.session_state.get("show_mail_tracker_imports", False)
with store_cols[2]:
    st.metric("Uploaded workbook rows", sum(len(df) for df in workbook.values() if isinstance(df, pd.DataFrame)))

if st.session_state.get("show_mail_tracker_imports"):
    try:
        batches = list_mail_tracker_batches(limit=10)
        if batches:
            st.dataframe(pd.DataFrame(batches), use_container_width=True, hide_index=True)
        else:
            st.caption("No saved Mail Tracker import batches found.")
    except Exception as exc:
        st.warning(f"Could not load saved Mail Tracker imports: {type(exc).__name__}: {exc}")

st.markdown("### AI Mail Search & Summary")
st.caption(
    "Search can use keywords, date range, and optional Project Name / Project ID context. "
    "If no keywords or project context are provided, AI summarises all uploaded mail rows. "
    "Saving Mail Tracker data is isolated and does not update formal project/order fields."
)

with st.container(border=True):
    f1, f2, f3 = st.columns([1.2, 0.9, 1.1], gap="large")
    with f1:
        keyword_text = st.text_area(
            "Keywords",
            placeholder="Example: inspection, packing, delay, sample, payment",
            height=88,
            key="mail_ai_keywords",
        )
    with f2:
        date_mode = st.selectbox(
            "Date filter",
            ["All uploaded mails", "Last 7 days", "Last 14 days", "Last 30 days", "Custom date range"],
            key="mail_ai_date_mode",
        )
        today = date.today()
        start_date: date | None = None
        end_date: date | None = None
        if date_mode == "Last 7 days":
            start_date, end_date = today - timedelta(days=7), today
        elif date_mode == "Last 14 days":
            start_date, end_date = today - timedelta(days=14), today
        elif date_mode == "Last 30 days":
            start_date, end_date = today - timedelta(days=30), today
        elif date_mode == "Custom date range":
            c1, c2 = st.columns(2)
            with c1:
                start_date = st.date_input("From", value=today - timedelta(days=30), key="mail_ai_start_date")
            with c2:
                end_date = st.date_input("To", value=today, key="mail_ai_end_date")
    with f3:
        project_query = st.text_input(
            "Project Name / Project ID / Order No",
            placeholder="Optional. Example: SDG-26-014 or project name",
            key="mail_ai_project_query",
        )
        selected_candidate: dict[str, Any] | None = None
        project_candidates = search_project_candidates(project_query, max_results=8) if project_query.strip() else []
        if project_candidates:
            candidate_options = list(range(len(project_candidates)))
            selected_candidate_index = st.selectbox(
                "Matched system project context",
                candidate_options,
                format_func=lambda idx: (
                    f"{project_candidates[idx].get('project_id') or '-'} · "
                    f"{project_candidates[idx].get('project_name') or '-'} · "
                    f"{project_candidates[idx].get('order_no') or '-'}"
                ),
                key="mail_ai_project_candidate",
            )
            selected_candidate = project_candidates[int(selected_candidate_index)]
        elif project_query.strip():
            st.caption("No system project match found. The manual project query will still be used as a mail keyword.")

    keywords = _split_keywords(keyword_text)
    project_match_terms = _project_terms(selected_candidate, project_query)
    filtered_workbook, preview_rows, date_label = _filter_workbook(
        workbook,
        keywords=keywords,
        project_terms=project_match_terms,
        start_date=start_date,
        end_date=end_date,
    )
    matched_count = sum(len(df) for df in filtered_workbook.values())

    st.metric("Matched mail rows", matched_count)
    st.caption(
        f"Applied filters: keywords={keywords or 'All'}; project terms={project_match_terms or 'None'}; date={date_label}. "
        "Mail summary does not update Sales / Operation / Meeting records."
    )

    if preview_rows:
        with st.expander("Matched mail rows preview", expanded=False):
            st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
    else:
        st.warning("No mail rows matched the current filters. AI summary will explain that no matching uploaded mail rows were found.")

    if st.button("Generate AI Mail Summary", use_container_width=True):
        with st.spinner("Summarising matched mail records from the uploaded workbook..."):
            st.session_state["ai_mail_summary"] = generate_ai_mail_summary(
                filtered_workbook,
                keywords=keywords,
                date_filter=date_label,
                project_context=_project_context(selected_candidate, project_query),
                matched_record_count=matched_count,
            )

if st.session_state.get("ai_mail_summary"):
    with st.expander("AI Mail Summary Output", expanded=True):
        render_ai_review(st.session_state["ai_mail_summary"], title="AI Mail Search & Summary", export_file_prefix="ai_mail_summary")

st.markdown("### Uploaded Workbook Preview")
sheet_names = list(workbook.keys())
tabs = st.tabs(sheet_names)
for tab, sheet_name in zip(tabs, sheet_names):
    with tab:
        df = workbook[sheet_name]
        st.markdown(f"### {sheet_name}")
        st.metric("Rows", len(df))
        if df.empty:
            st.info("This sheet is empty.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button(
                f"Export {sheet_name}",
                data=df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"{sheet_name.lower().replace(' ', '_')}.csv",
                mime="text/csv",
            )
