from __future__ import annotations

from html import escape
from textwrap import dedent
from typing import Any

import pandas as pd
import streamlit as st

from core.auth import require_login
from core.state import init_session_state
from database.ai_repository import save_ai_update_draft
from services.ai_client import AIConfigError, AIResponseError
from services.ai_meeting_service import (
    FIELD_LABELS,
    MEETING_FIELDS,
    build_existing_field_snapshot,
    extract_meeting_fields_with_ai,
    search_project_candidates,
)
from ui.theme import apply_theme, render_page_header


st.set_page_config(
    page_title="AI Meeting Assistant - Zenith Project Tracker",
    page_icon="🤖",
    layout="wide",
)

init_session_state()
apply_theme()
current_user = require_login()


def _html(markup: str) -> str:
    return dedent(markup).strip()


def _safe(value: Any) -> str:
    return escape(str(value or "-"))


def _render_css() -> None:
    st.markdown(
        _html(
            """
            <style>
            .block-container { padding-top: 1.05rem !important; }

            .zai-card {
                background: #ffffff;
                border: 1px solid #e8e8eb;
                border-radius: 20px;
                padding: 1rem 1.05rem;
                box-shadow: 0 8px 24px rgba(17,17,17,0.045);
                margin-bottom: 0.75rem;
            }
            .zai-selected {
                border: 1px solid #c5161d;
                background: #fffafa;
            }
            .zai-kicker {
                color: #c5161d;
                font-size: 0.74rem;
                font-weight: 850;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                margin-bottom: 0.18rem;
            }
            .zai-title {
                color: #111111;
                font-size: 1.08rem;
                font-weight: 850;
                margin-bottom: 0.28rem;
            }
            .zai-meta {
                color: #61646b;
                font-size: 0.86rem;
                line-height: 1.45;
            }
            .zai-chip {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 0.22rem 0.55rem;
                font-size: 0.76rem;
                font-weight: 760;
                border: 1px solid #e5e5e7;
                background: #fafafa;
                color: #333333;
                margin-right: 0.32rem;
                margin-top: 0.3rem;
            }
            .zai-warning {
                border: 1px solid #f2d4a7;
                background: #fff8ee;
                color: #6a4200;
                border-radius: 16px;
                padding: 0.85rem 1rem;
                font-size: 0.9rem;
                margin-bottom: 0.8rem;
            }
            .zai-success {
                border: 1px solid #b7e4c7;
                background: #f3fff6;
                color: #184d2b;
                border-radius: 16px;
                padding: 0.85rem 1rem;
                font-size: 0.9rem;
                margin-top: 0.85rem;
            }
            </style>
            """
        ),
        unsafe_allow_html=True,
    )


def _candidate_card(candidate: dict[str, Any], index: int) -> None:
    review_text = "Review This Week" if candidate.get("review_this_week") else "Normal"
    selected = (
        st.session_state.get("ai_selected_project", {}).get("record_type") == candidate.get("record_type")
        and st.session_state.get("ai_selected_project", {}).get("entity_id") == candidate.get("entity_id")
    )
    css_class = "zai-card zai-selected" if selected else "zai-card"

    st.markdown(
        _html(
            f"""
            <div class="{css_class}">
                <div class="zai-kicker">{_safe(candidate.get("record_type"))} · Match Score {_safe(candidate.get("match_score"))}</div>
                <div class="zai-title">{_safe(candidate.get("project_id"))} · {_safe(candidate.get("project_name"))}</div>
                <div class="zai-meta">
                    Client Code: <b>{_safe(candidate.get("client_code"))}</b><br>
                    Order No: <b>{_safe(candidate.get("order_no"))}</b><br>
                    Owner: <b>{_safe(candidate.get("current_owner"))}</b><br>
                    Phase: <b>{_safe(candidate.get("phase"))}</b><br>
                    Next Step: {_safe(candidate.get("next_step"))}<br>
                    Target Date: {_safe(candidate.get("target_date"))}
                </div>
                <span class="zai-chip">{_safe(review_text)}</span>
                <span class="zai-chip">{_safe(candidate.get("health_status"))}</span>
                <span class="zai-chip">{_safe(candidate.get("result_status"))}</span>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    key = f"select_project_{index}_{candidate.get('record_type')}_{candidate.get('entity_id')}"
    if st.button("Select this project", key=key, use_container_width=True):
        st.session_state["ai_selected_project"] = candidate
        st.session_state.pop("ai_generated_draft", None)
        st.session_state.pop("ai_saved_draft_id", None)
        st.rerun()


def _render_selected_project(project: dict[str, Any]) -> None:
    st.markdown(
        _html(
            f"""
            <div class="zai-card zai-selected">
                <div class="zai-kicker">Confirmed Project Before AI Processing</div>
                <div class="zai-title">{_safe(project.get("project_id"))} · {_safe(project.get("project_name"))}</div>
                <div class="zai-meta">
                    Record Type: <b>{_safe(project.get("record_type"))}</b><br>
                    Entity ID: <b>{_safe(project.get("entity_id"))}</b><br>
                    Client Code: <b>{_safe(project.get("client_code"))}</b><br>
                    Order No: <b>{_safe(project.get("order_no"))}</b><br>
                    Owner: <b>{_safe(project.get("current_owner"))}</b><br>
                    Phase: <b>{_safe(project.get("phase"))}</b>
                </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def _render_diff_table(project: dict[str, Any], draft: dict[str, Any]) -> None:
    existing = build_existing_field_snapshot(project)
    rows = []
    for field in MEETING_FIELDS:
        rows.append(
            {
                "Field": FIELD_LABELS.get(field, field),
                "Existing Record": existing.get(field, ""),
                "AI Suggested Update": draft.get(field, ""),
            }
        )

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


_render_css()

render_page_header(
    "AI Meeting Assistant",
    "Find project first, confirm Project ID, then let AI structure weekly meeting notes.",
)

st.markdown(
    _html(
        """
        <div class="zai-warning">
        Rule: colleagues can search by Project Name, Order No, Client Code, or Project ID.
        But no AI draft can be saved until one Project ID is confirmed.
        </div>
        """
    ),
    unsafe_allow_html=True,
)

st.divider()

left_col, right_col = st.columns([1.05, 1.25], gap="large")

with left_col:
    st.subheader("Step 1 · Find Project / Order")

    search_query = st.text_input(
        "Search by Project ID, Project Name, Order No, or Client Code",
        placeholder="Example: SDG, EHS, GLG inverter, GLG180326-1, friction wheel",
        key="ai_project_search_query",
    )

    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        record_type_filter = st.selectbox(
            "Record Type",
            ["All", "Sales", "Operation"],
            index=0,
            key="ai_record_type_filter",
        )
    with filter_col2:
        review_only = st.checkbox(
            "Review This Week only",
            value=False,
            key="ai_review_only_filter",
        )

    if search_query:
        candidates = search_project_candidates(
            search_query,
            record_type_filter=record_type_filter,
            review_only=review_only,
        )

        if not candidates:
            st.info("No confirmed project found. Try another keyword, Project Name, Order No, or Client Code.")
        else:
            st.caption(f"Found {len(candidates)} possible record(s). Please select one before AI processing.")
            for index, candidate in enumerate(candidates):
                _candidate_card(candidate, index)

with right_col:
    st.subheader("Step 2 · Confirm Project ID")
    selected_project = st.session_state.get("ai_selected_project")

    if not selected_project:
        st.info("Please search and select one project/order first.")
        st.stop()

    _render_selected_project(selected_project)

    if st.button("Clear selected project", use_container_width=True):
        st.session_state.pop("ai_selected_project", None)
        st.session_state.pop("ai_generated_draft", None)
        st.session_state.pop("ai_saved_draft_id", None)
        st.rerun()

    st.divider()
    st.subheader("Step 3 · Paste Meeting Notes")

    output_language = st.selectbox(
        "AI output language",
        ["English", "Chinese", "Bilingual Chinese and English"],
        index=0,
        key="ai_output_language",
    )

    meeting_notes = st.text_area(
        "Meeting notes / colleague input",
        height=180,
        placeholder=(
            "Example: 客户还在等盐雾测试结果，供应商说下周三可以给新样板。"
            "Maria 需要先问客户能不能接受延迟。"
        ),
        key="ai_meeting_notes",
    )

    generate_disabled = not bool(selected_project.get("project_id")) or not meeting_notes.strip()

    if st.button(
        "Generate AI Field Draft",
        disabled=generate_disabled,
        type="primary",
        use_container_width=True,
    ):
        try:
            with st.spinner("AI is extracting meeting fields..."):
                draft = extract_meeting_fields_with_ai(
                    selected_project=selected_project,
                    meeting_notes=meeting_notes,
                    output_language=output_language,
                )
            st.session_state["ai_generated_draft"] = draft
            st.session_state.pop("ai_saved_draft_id", None)
            st.rerun()
        except (AIConfigError, AIResponseError) as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"AI processing failed: {exc}")

    draft = st.session_state.get("ai_generated_draft")

    if draft:
        st.divider()
        st.subheader("Step 4 · Review AI Draft")

        st.markdown(
            _html(
                f"""
                <div class="zai-card">
                    <div class="zai-kicker">AI Summary</div>
                    <div class="zai-meta">
                        Difference Summary: <b>{_safe(draft.get("difference_summary"))}</b><br>
                        Confidence: <b>{_safe(draft.get("confidence"))}</b><br>
                        Needs Human Attention: <b>{_safe(draft.get("needs_human_attention"))}</b>
                    </div>
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

        _render_diff_table(selected_project, draft)

        st.warning(
            "This first version saves the AI result into ai_update_drafts only. "
            "It does not directly overwrite the core Sales / Operation table."
        )

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Save as Pending AI Draft", use_container_width=True):
                draft_id = save_ai_update_draft(
                    selected_project=selected_project,
                    meeting_notes=meeting_notes,
                    draft_json=draft,
                    current_user=current_user,
                    status="pending",
                )
                st.session_state["ai_saved_draft_id"] = draft_id
                st.success(f"AI draft saved. Draft ID: {draft_id}")

        with col_b:
            if st.button("Confirm AI Draft", type="primary", use_container_width=True):
                draft_id = save_ai_update_draft(
                    selected_project=selected_project,
                    meeting_notes=meeting_notes,
                    draft_json=draft,
                    current_user=current_user,
                    status="confirmed",
                )
                st.session_state["ai_saved_draft_id"] = draft_id
                st.success(f"AI draft confirmed and saved. Draft ID: {draft_id}")

        saved_draft_id = st.session_state.get("ai_saved_draft_id")
        if saved_draft_id:
            st.markdown(
                _html(
                    f"""
                    <div class="zai-success">
                    Saved Draft ID: <b>{_safe(saved_draft_id)}</b><br>
                    Next step: connect confirmed draft to the existing Project / Order Detail update function after review.
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )
