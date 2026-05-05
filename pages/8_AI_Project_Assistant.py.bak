from __future__ import annotations

from html import escape
from textwrap import dedent
import re
from typing import Any

import pandas as pd
import streamlit as st

from core.auth import require_login
from core.state import init_session_state
from services.ai_project_service import (
    SUPPORTED_OUTPUT_LANGUAGES,
    SUPPORTED_RECORD_TYPES,
    SUPPORTED_SCOPES,
    AIProjectAssistantError,
    ask_ai_project_assistant,
    build_text_export,
    dashboard_to_dataframe,
    dataframe_to_csv_bytes,
    records_to_dataframe,
)
from ui.theme import apply_theme, render_page_header


st.set_page_config(
    page_title="AI Project Assistant - Zenith Project Tracker",
    page_icon="🔎",
    layout="wide",
)

init_session_state()
apply_theme()
require_login()


def _html(markup: str) -> str:
    return dedent(markup).strip()


def _safe(value: Any) -> str:
    return escape(str(value or "-"))


def _compact_answer_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n[ \t]*\n+", "\n", text)
    text = re.sub(r"(?m)^\s*(\d+)\.\s*\n\s*", r"\1. ", text)
    text = re.sub(r"(?m)^\s*[-•]\s*\n\s*", "- ", text)
    text = re.sub(r"(?m)^\s*(Sales Board|Operation Board|Dashboard|Project Details|Meeting Mode):\s*", r"\1:", text)
    return text.strip()


def _safe_compact(value: Any) -> str:
    return escape(_compact_answer_text(value))


def _render_css() -> None:
    st.markdown(
        _html(
            """
            <style>
            .block-container { padding-top: 1.05rem !important; }
            .zpa-card {
                background: #ffffff;
                border: 1px solid #e8e8eb;
                border-radius: 20px;
                padding: 1rem 1.05rem;
                box-shadow: 0 8px 24px rgba(17,17,17,0.045);
                margin-bottom: 0.8rem;
            }
            .zpa-answer {
                border-left: 5px solid #c5161d;
                background: #fffafa;
            }
            .zpa-kicker {
                color: #c5161d;
                font-size: 0.74rem;
                font-weight: 850;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                margin-bottom: 0.28rem;
            }
            .zpa-title {
                color: #111111;
                font-size: 1.08rem;
                font-weight: 850;
                margin-bottom: 0.35rem;
            }
            .zpa-meta {
                color: #444850;
                font-size: 0.9rem;
                line-height: 1.42;
                white-space: pre-wrap;
            }
            .zpa-chip {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 0.24rem 0.6rem;
                font-size: 0.76rem;
                font-weight: 760;
                border: 1px solid #e5e5e7;
                background: #fafafa;
                color: #333333;
                margin-right: 0.36rem;
                margin-top: 0.35rem;
            }
            .zpa-note {
                border: 1px solid #dfe3e8;
                background: #fafafa;
                color: #333333;
                border-radius: 16px;
                padding: 0.85rem 1rem;
                font-size: 0.9rem;
                margin-bottom: 0.8rem;
            }
            .zpa-warning {
                border: 1px solid #f2d4a7;
                background: #fff8ee;
                color: #6a4200;
                border-radius: 16px;
                padding: 0.85rem 1rem;
                font-size: 0.9rem;
                margin-bottom: 0.8rem;
            }
            .zpa-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.65rem;
                margin: 0.3rem 0 0.2rem 0;
            }
            .zpa-mini {
                border: 1px solid #eeeeef;
                border-radius: 16px;
                background: #fafafa;
                padding: 0.75rem 0.8rem;
                min-height: 76px;
            }
            .zpa-mini-label {
                color: #6f737a;
                font-size: 0.72rem;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0.04em;
                margin-bottom: 0.25rem;
            }
            .zpa-mini-value {
                color: #111111;
                font-size: 1.45rem;
                font-weight: 850;
                letter-spacing: -0.04em;
                line-height: 1.05;
            }
            </style>
            """
        ),
        unsafe_allow_html=True,
    )


def _answer_card(answer: dict[str, Any]) -> None:
    st.markdown(
        _html(
            f"""
            <div class="zpa-card zpa-answer">
                <div class="zpa-kicker">Direct Answer</div>
                <div class="zpa-title">{_safe_compact(answer.get("direct_answer"))}</div>
                <div class="zpa-meta">{_safe_compact(answer.get("detailed_answer"))}</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def _summary_grid(summary: dict[str, Any]) -> None:
    st.markdown(
        _html(
            f"""
            <div class="zpa-grid">
                <div class="zpa-mini"><div class="zpa-mini-label">Final Answer Records</div><div class="zpa-mini-value">{_safe(summary.get("final_answer_records"))}</div></div>
                <div class="zpa-mini"><div class="zpa-mini-label">Sales</div><div class="zpa-mini-value">{_safe(summary.get("sales_records"))}</div></div>
                <div class="zpa-mini"><div class="zpa-mini-label">Operation</div><div class="zpa-mini-value">{_safe(summary.get("operation_records"))}</div></div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def _clean_frame_for_streamlit(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    cleaned = frame.loc[:, ~frame.columns.duplicated()].copy()
    return cleaned.fillna("").astype(str)


def _render_records_by_module(frame: pd.DataFrame, module: str) -> None:
    if frame.empty:
        st.info(f"No final answer records in {module}.")
        return

    if module == "Sales Board" and "Record Type" in frame.columns:
        module_frame = frame[frame["Record Type"] == "Sales"]
    elif module == "Operation Board" and "Record Type" in frame.columns:
        module_frame = frame[frame["Record Type"] == "Operation"]
    elif "Source Module" in frame.columns:
        module_frame = frame[frame["Source Module"] == module]
    else:
        st.info(f"No final answer records in {module}.")
        return

    if module_frame.empty:
        st.info(f"No final answer records in {module}.")
        return
    st.dataframe(_clean_frame_for_streamlit(module_frame), use_container_width=True, hide_index=True)


def _combined_export_frame(records_frame: pd.DataFrame, dashboard_frame: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if not records_frame.empty:
        tmp = records_frame.copy()
        tmp.insert(0, "Export Section", "Final Answer Records")
        frames.append(tmp.astype(str))
    if not dashboard_frame.empty:
        tmp = dashboard_frame.copy()
        tmp.insert(0, "Export Section", "Dashboard Metrics")
        frames.append(tmp.astype(str))
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True, sort=False).fillna("")
    combined = combined.loc[:, ~combined.columns.duplicated()]
    return combined


_render_css()

render_page_header(
    "AI Project Assistant",
    "Read-only natural-language search over Sales, Operation, Dashboard, Project Details, Meeting Mode, and project history records.",
)

st.markdown(
    _html(
        """
        <div class="zpa-note">
        This assistant only searches current system records. It does not change database records, does not update Meeting Prep, and uses the existing Sales Board / Dashboard order-link rule for order association questions.
        </div>
        """
    ),
    unsafe_allow_html=True,
)

left_col, right_col = st.columns([1.0, 1.55], gap="large")

with left_col:
    st.subheader("Step 1 · Ask a Project Question")

    output_language = st.selectbox(
        "AI output language",
        SUPPORTED_OUTPUT_LANGUAGES,
        index=0,
        key="ai_project_output_language",
    )

    question = st.text_area(
        "Question / 查询问题",
        height=220,
        placeholder=(
            "Examples:\n"
            "- Which projects are blocked this week?\n"
            "- Show delayed operation orders owned by Sandy\n"
            "- What should Ehab focus on this week?\n"
            "- What are all open issues for client Keter?\n"
            "- Summarize the project history for SDG-26-013\n"
            "- 哪些项目还没有订单？"
        ),
        key="ai_project_question",
    )

    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        scope = st.selectbox(
            "Search Scope",
            SUPPORTED_SCOPES,
            index=0,
            key="ai_project_scope",
            help="Choose All for normal use. Use a specific module if you want to limit the search area.",
        )
    with filter_col2:
        record_type = st.selectbox(
            "Record Type",
            SUPPORTED_RECORD_TYPES,
            index=0,
            key="ai_project_record_type",
        )

    result_limit = st.selectbox(
        "Result Limit",
        [10, 20, 50],
        index=1,
        key="ai_project_result_limit",
    )

    run_disabled = not bool(question.strip())
    if st.button(
        "Search Current System Records",
        type="primary",
        disabled=run_disabled,
        use_container_width=True,
    ):
        try:
            with st.spinner("Searching current system records and preparing answer..."):
                result = ask_ai_project_assistant(
                    question=question,
                    output_language=output_language,
                    scope=scope,
                    record_type=record_type,
                    result_limit=int(result_limit),
                )
            st.session_state["ai_project_result"] = result
        except AIProjectAssistantError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"AI Project Assistant failed: {exc}")

    if st.button("Clear AI Project Assistant Result", use_container_width=True):
        st.session_state.pop("ai_project_result", None)
        st.rerun()

with right_col:
    st.subheader("Step 2 · Answer and Evidence")
    result = st.session_state.get("ai_project_result")

    if not result:
        st.info("Enter a question on the left, choose the output language, then search current system records.")
        st.stop()

    answer = result.get("answer") or {}
    summary = result.get("source_summary") or {}
    records_frame = records_to_dataframe(result.get("records") or [])
    dashboard_frame = dashboard_to_dataframe(result.get("dashboard_rows") or [])
    combined_frame = _combined_export_frame(records_frame, dashboard_frame)

    _answer_card(answer)
    _summary_grid(summary)

    st.markdown(
        _html(
            f"""
            <div class="zpa-card">
                <div class="zpa-kicker">Based on System Records</div>
                <div class="zpa-meta">{_safe(answer.get("evidence_summary"))}</div>
                <span class="zpa-chip">Scope: {_safe(result.get("scope"))}</span>
                <span class="zpa-chip">Record Type: {_safe(result.get("record_type"))}</span>
                <span class="zpa-chip">Output: {_safe(result.get("output_language"))}</span>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    if result.get("ai_error"):
        st.warning(
            "AI API summary was not available, so the page is showing a safe system-record fallback answer. "
            f"API message: {result.get('ai_error')}"
        )

    limitation_text = answer.get("not_found_or_limitations") or "All records shown are from the current active system records."
    limitation_class = "zpa-warning" if (not result.get("found") or result.get("is_truncated") or result.get("has_scope_limitations")) else "zpa-card"
    st.markdown(
        _html(
            f"""
            <div class="{limitation_class}">
                <div class="zpa-kicker">Search Scope and Limitations</div>
                <div class="zpa-meta">{_safe(limitation_text)}</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    tab_answer, tab_sales, tab_operation, tab_dashboard, tab_detail, tab_meeting, tab_export = st.tabs(
        ["Answer", "Sales Board", "Operation Board", "Dashboard", "Project Details", "Meeting Mode", "Export"]
    )

    with tab_answer:
        st.markdown("#### Direct Answer")
        st.markdown(_compact_answer_text(answer.get("direct_answer") or "-"))
        st.markdown("#### Detailed Answer")
        st.markdown(_compact_answer_text(answer.get("detailed_answer") or "-"))
        st.markdown("#### Based on System Records")
        st.markdown(_compact_answer_text(answer.get("evidence_summary") or "The answer is based on the final records found in the current system data."))
        st.markdown("#### Search Scope and Limitations")
        st.markdown(_compact_answer_text(limitation_text))

    with tab_sales:
        _render_records_by_module(records_frame, "Sales Board")

    with tab_operation:
        _render_records_by_module(records_frame, "Operation Board")

    with tab_dashboard:
        if dashboard_frame.empty:
            st.info("No dashboard metrics were needed for this question.")
        else:
            st.dataframe(_clean_frame_for_streamlit(dashboard_frame), use_container_width=True, hide_index=True)

    with tab_detail:
        if records_frame.empty:
            st.info("No final answer records in Project Details or Project History.")
        else:
            detail_frame = records_frame[records_frame["Source Module"].isin(["Sales Board", "Operation Board", "Project History"])] if "Source Module" in records_frame.columns else records_frame
            if detail_frame.empty:
                st.info("No final answer records in Project Details or Project History.")
            else:
                st.dataframe(_clean_frame_for_streamlit(detail_frame), use_container_width=True, hide_index=True)

    with tab_meeting:
        _render_records_by_module(records_frame, "Meeting Mode")

    with tab_export:
        st.markdown("#### Export Answer and Final Answer Records")
        st.caption("Text export contains the AI answer and summary. CSV export contains only the final answer records shown on this page.")

        text_export = build_text_export(result)
        st.download_button(
            "Download Answer (.txt)",
            data=text_export.encode("utf-8-sig"),
            file_name="ai_project_assistant_answer.txt",
            mime="text/plain",
            use_container_width=True,
        )

        if combined_frame.empty:
            st.info("No CSV final answer records are available for this search result.")
        else:
            st.download_button(
                "Download Final Answer Records (.csv)",
                data=dataframe_to_csv_bytes(combined_frame),
                file_name="ai_project_assistant_final_records.csv",
                mime="text/csv",
                use_container_width=True,
            )

        if not records_frame.empty:
            st.markdown("##### Final Answer Records Preview")
            st.dataframe(_clean_frame_for_streamlit(records_frame), use_container_width=True, hide_index=True)
        if not dashboard_frame.empty:
            st.markdown("##### Dashboard Metrics Preview")
            st.dataframe(_clean_frame_for_streamlit(dashboard_frame), use_container_width=True, hide_index=True)
