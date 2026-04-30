from __future__ import annotations

from html import escape
from textwrap import dedent
from typing import Any

import pandas as pd
import streamlit as st

from core.auth import require_login
from core.state import init_session_state
from database.ai_repository import mark_ai_draft_status, save_ai_update_draft
from services.ai_apply_service import AIMeetingApplyError, apply_ai_meeting_draft
from services.ai_client import AIConfigError, AIResponseError
from services.ai_meeting_service import (
    FIELD_LABELS,
    MEETING_FIELDS,
    build_existing_field_snapshot,
    clean_text,
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
acting_user = str(current_user.get("display_name") or current_user.get("email") or "AI User") if isinstance(current_user, dict) else str(current_user)


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
            .zai-note {
                border: 1px solid #dfe3e8;
                background: #fafafa;
                color: #333333;
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
        st.session_state.pop("ai_apply_result", None)
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


def _default_apply(field: str, existing_value: str, ai_value: str) -> bool:
    existing = clean_text(existing_value)
    ai = clean_text(ai_value)
    if not ai:
        return False
    if field == "review_this_week":
        return ai.lower() == "yes" and existing.lower() != "yes"
    if not existing:
        return True
    if existing == ai:
        return False
    # Existing value should not be overwritten by default. User must choose it.
    return False


def _build_review_dataframe(project: dict[str, Any], draft: dict[str, Any]) -> pd.DataFrame:
    existing = build_existing_field_snapshot(project)
    rows = []
    for field in MEETING_FIELDS:
        existing_value = existing.get(field, "")
        ai_value = clean_text(draft.get(field))
        rows.append(
            {
                "Apply": _default_apply(field, existing_value, ai_value),
                "Field Key": field,
                "Field": FIELD_LABELS.get(field, field),
                "Existing Record": existing_value,
                "AI Suggested Update": ai_value,
            }
        )
    return pd.DataFrame(rows)


def _draft_from_review_table(review_frame: pd.DataFrame, original_draft: dict[str, Any]) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    applied_fields: list[str] = []
    label_to_key = {label: key for key, label in FIELD_LABELS.items()}

    for _, row in review_frame.iterrows():
        # Field Key is intentionally hidden in the UI. Keep this fallback so the
        # apply logic remains stable even if Streamlit returns only displayed columns.
        field_key = clean_text(row.get("Field Key"))
        if field_key not in MEETING_FIELDS:
            field_key = label_to_key.get(clean_text(row.get("Field")), "")
        if field_key not in MEETING_FIELDS:
            continue
        value = clean_text(row.get("AI Suggested Update"))
        apply_flag = bool(row.get("Apply"))
        if apply_flag and value:
            selected[field_key] = value
            applied_fields.append(field_key)
        else:
            selected[field_key] = ""

    selected["ai_summary_for_review"] = clean_text(original_draft.get("ai_summary_for_review"))
    selected["difference_summary"] = clean_text(original_draft.get("difference_summary"))
    selected["confidence"] = clean_text(original_draft.get("confidence"))
    selected["needs_human_attention"] = clean_text(original_draft.get("needs_human_attention"))
    selected["applied_fields"] = applied_fields
    selected["raw_ai_draft"] = original_draft
    return selected


def _render_review_editor(project: dict[str, Any], draft: dict[str, Any]) -> pd.DataFrame:
    review_frame = _build_review_dataframe(project, draft)
    st.caption(
        "Review the AI suggestion and apply only the fields you want to update. "
        "Meeting Note is not included."
    )
    return st.data_editor(
        review_frame,
        use_container_width=True,
        hide_index=True,
        height=430,
        num_rows="fixed",
        column_order=["Apply", "Field", "Existing Record", "AI Suggested Update"],
        disabled=["Field", "Existing Record"],
        column_config={
            "Apply": st.column_config.CheckboxColumn(
                "Apply",
                help="Tick only the fields you want to write into the system.",
                width="small",
            ),
            "Field": st.column_config.TextColumn("Field", width="medium"),
            "Existing Record": st.column_config.TextColumn("Existing Record", width="large"),
            "AI Suggested Update": st.column_config.TextColumn("AI Suggested Update", width="large"),
        },
        key="ai_meeting_prep_review_editor",
    )


_render_css()

render_page_header(
    "AI Meeting Assistant",
    "Find project first, confirm Project ID, then let AI structure weekly meeting prep fields.",
)

st.divider()

selected_project = st.session_state.get("ai_selected_project")
meeting_notes = st.session_state.get("ai_meeting_notes", "")

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

    if not selected_project:
        st.info("Please search and select one project/order first.")
    else:
        _render_selected_project(selected_project)

        if st.button("Clear selected project", use_container_width=True):
            st.session_state.pop("ai_selected_project", None)
            st.session_state.pop("ai_generated_draft", None)
            st.session_state.pop("ai_saved_draft_id", None)
            st.session_state.pop("ai_apply_result", None)
            st.rerun()

        st.divider()
        st.subheader("Step 3 · Paste Meeting Prep Input")

        output_language = st.selectbox(
            "AI output language",
            ["English", "Chinese", "Bilingual Chinese and English"],
            index=0,
            key="ai_output_language",
        )

        meeting_notes = st.text_area(
            "Colleague input / pre-meeting information",
            height=180,
            placeholder=(
                "Example: 客户还在等盐雾测试结果，供应商说下周三可以给新样板。"
                "Maria 需要先问客户能不能接受延迟。"
            ),
            key="ai_meeting_notes",
        )

        generate_disabled = not bool(selected_project.get("project_id")) or not meeting_notes.strip()

        if st.button(
            "Generate AI Meeting Prep Draft",
            disabled=generate_disabled,
            type="primary",
            use_container_width=True,
            key="generate_ai_meeting_prep_draft_button",
        ):
            # Keep feedback visible on the same run. Do not immediately rerun,
            # otherwise users may think the button had no response and Step 4 may
            # appear below the fold without a clear success message.
            st.session_state.pop("ai_generation_error", None)
            st.session_state.pop("ai_generation_message", None)
            try:
                with st.spinner("AI is preparing Meeting Prep fields..."):
                    draft = extract_meeting_fields_with_ai(
                        selected_project=selected_project,
                        meeting_notes=meeting_notes,
                        output_language=output_language,
                    )
                st.session_state["ai_generated_draft"] = draft
                st.session_state.pop("ai_saved_draft_id", None)
                st.session_state.pop("ai_apply_result", None)
                st.session_state["ai_generation_message"] = (
                    "AI Meeting Prep Draft generated. Please review Step 4 below."
                )
                st.rerun()
            except (AIConfigError, AIResponseError) as exc:
                st.session_state.pop("ai_generated_draft", None)
                st.session_state["ai_generation_error"] = str(exc)
            except Exception as exc:
                st.session_state.pop("ai_generated_draft", None)
                st.session_state["ai_generation_error"] = f"AI processing failed: {exc}"

        generation_error = st.session_state.get("ai_generation_error")
        generation_message = st.session_state.get("ai_generation_message")
        if generation_error:
            st.error(generation_error)
        elif generation_message:
            st.success(generation_message)

# Keep the AI review table outside the right column so Existing / AI Suggested columns have enough width.
draft = st.session_state.get("ai_generated_draft")
selected_project = st.session_state.get("ai_selected_project")
meeting_notes = st.session_state.get("ai_meeting_notes", "")

if selected_project and isinstance(draft, dict):
    st.divider()
    st.subheader("Step 4 · Review AI Meeting Prep Draft")

    st.markdown(
        _html(
            f"""
            <div class="zai-card">
                <div class="zai-kicker">AI Review Summary</div>
                <div class="zai-meta">
                    AI Summary for Review: <b>{_safe(draft.get("ai_summary_for_review"))}</b><br>
                    Difference Summary: <b>{_safe(draft.get("difference_summary"))}</b><br>
                    Confidence: <b>{_safe(draft.get("confidence"))}</b><br>
                    Needs Human Attention: <b>{_safe(draft.get("needs_human_attention"))}</b>
                </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    edited_review_frame = _render_review_editor(selected_project, draft)

    st.warning(
        "Confirm will save the AI draft and apply only the selected fields into the core "
        "Sales / Operation Meeting Prep fields. Empty fields will not clear existing data. "
        "AI Review This Week = Yes can add the item to this week's review; AI No will not remove it. "
        "Meeting Note will not be changed by this assistant."
    )

    selected_draft = _draft_from_review_table(edited_review_frame, draft)
    selected_count = len(selected_draft.get("applied_fields") or [])
    st.caption(f"Selected fields to apply: {selected_count}")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Save as Pending AI Draft", use_container_width=True):
            draft_id = save_ai_update_draft(
                selected_project=selected_project,
                meeting_notes=meeting_notes,
                draft_json={"raw_ai_draft": draft, "review_table": edited_review_frame.to_dict("records")},
                current_user=current_user,
                status="pending",
            )
            st.session_state["ai_saved_draft_id"] = draft_id
            st.session_state["ai_apply_result"] = None
            st.success(f"AI draft saved. Draft ID: {draft_id}")

    with col_b:
        if st.button(
            "Confirm Selected Fields + Update System",
            type="primary",
            use_container_width=True,
            disabled=selected_count == 0,
        ):
            draft_id = save_ai_update_draft(
                selected_project=selected_project,
                meeting_notes=meeting_notes,
                draft_json=selected_draft,
                current_user=current_user,
                status="confirmed",
            )
            try:
                apply_result = apply_ai_meeting_draft(
                    selected_project=selected_project,
                    draft=selected_draft,
                    operator=acting_user,
                )
                final_status = "confirmed_applied" if apply_result.get("updated") else "confirmed_no_change"
                mark_ai_draft_status(
                    draft_id=draft_id,
                    status=final_status,
                    current_user=current_user,
                )
                st.session_state["ai_saved_draft_id"] = draft_id
                st.session_state["ai_apply_result"] = apply_result
                if apply_result.get("updated"):
                    st.success(
                        f"AI Meeting Prep confirmed and applied. Draft ID: {draft_id}. "
                        f"{apply_result.get('message')}"
                    )
                else:
                    st.info(
                        f"AI draft confirmed and saved. Draft ID: {draft_id}. "
                        f"{apply_result.get('message')}"
                    )
            except AIMeetingApplyError as exc:
                mark_ai_draft_status(
                    draft_id=draft_id,
                    status="confirmed_apply_failed",
                    current_user=current_user,
                )
                st.session_state["ai_saved_draft_id"] = draft_id
                st.session_state["ai_apply_result"] = None
                st.error(f"Draft saved, but applying to the system failed: {exc}")
            except Exception as exc:
                mark_ai_draft_status(
                    draft_id=draft_id,
                    status="confirmed_apply_failed",
                    current_user=current_user,
                )
                st.session_state["ai_saved_draft_id"] = draft_id
                st.session_state["ai_apply_result"] = None
                st.error(f"Draft saved, but applying to the system failed: {exc}")

    saved_draft_id = st.session_state.get("ai_saved_draft_id")
    apply_result = st.session_state.get("ai_apply_result")
    if saved_draft_id:
        changed_fields = ", ".join(apply_result.get("changed_fields") or []) if apply_result else "-"
        apply_message = apply_result.get("message") if apply_result else "Saved as pending AI draft."
        entity_label = (
            f"{apply_result.get('entity_type')} / {apply_result.get('entity_id')}"
            if apply_result else "Not applied yet"
        )
        st.markdown(
            _html(
                f"""
                <div class="zai-success">
                Saved Draft ID: <b>{_safe(saved_draft_id)}</b><br>
                Applied Record: <b>{_safe(entity_label)}</b><br>
                Result: <b>{_safe(apply_message)}</b><br>
                Changed Fields: <b>{_safe(changed_fields)}</b><br>
                Meeting Note was not changed by this AI assistant.<br>
                Dashboard / Meeting Mode should show the latest values after refresh because cached read data is cleared after writes.
                </div>
                """
            ),
            unsafe_allow_html=True,
        )
