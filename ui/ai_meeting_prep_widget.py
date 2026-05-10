from __future__ import annotations

from html import escape
from textwrap import dedent
from typing import Any

import pandas as pd
import streamlit as st

from database.ai_repository import mark_ai_draft_status, save_ai_update_draft
from services.ai_apply_service import apply_ai_meeting_draft
from services.ai_client import AIConfigError, AIResponseError
from services.ai_meeting_service import (
    FIELD_LABELS,
    MEETING_FIELDS,
    build_existing_field_snapshot,
    clean_text,
    extract_meeting_fields_with_ai,
    search_project_candidates,
)


def _html(markup: str) -> str:
    return dedent(markup).strip()


def _safe(value: Any) -> str:
    return escape(str(value or "-"))


def _render_css() -> None:
    st.markdown(
        _html(
            """
            <style>
            .zai-card {
                background: #ffffff;
                border: 1px solid #e8e8eb;
                border-radius: 18px;
                padding: 0.85rem 0.95rem;
                box-shadow: 0 8px 22px rgba(17,17,17,0.035);
                margin-bottom: 0.65rem;
            }
            .zai-selected { border: 1px solid #c5161d; background: #fffafa; }
            .zai-kicker {
                color: #c5161d;
                font-size: 0.72rem;
                font-weight: 850;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                margin-bottom: 0.16rem;
            }
            .zai-title { color: #111111; font-size: 0.98rem; font-weight: 850; margin-bottom: 0.22rem; }
            .zai-meta { color: #61646b; font-size: 0.84rem; line-height: 1.42; }
            .zai-chip {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 0.18rem 0.5rem;
                font-size: 0.72rem;
                font-weight: 760;
                border: 1px solid #e5e5e7;
                background: #fafafa;
                color: #333333;
                margin-right: 0.28rem;
                margin-top: 0.28rem;
            }
            .zai-note {
                border: 1px solid #dfe3e8;
                background: #fafafa;
                color: #333333;
                border-radius: 14px;
                padding: 0.72rem 0.85rem;
                font-size: 0.88rem;
                margin-bottom: 0.7rem;
            }
            </style>
            """
        ),
        unsafe_allow_html=True,
    )


def _candidate_card(candidate: dict[str, Any], index: int, *, key_prefix: str) -> None:
    review_text = "Review This Week" if candidate.get("review_this_week") else "Normal"
    selected = (
        st.session_state.get(f"{key_prefix}_selected_project", {}).get("record_type") == candidate.get("record_type")
        and st.session_state.get(f"{key_prefix}_selected_project", {}).get("entity_id") == candidate.get("entity_id")
    )
    css_class = "zai-card zai-selected" if selected else "zai-card"
    st.markdown(
        _html(
            f"""
            <div class="{css_class}">
                <div class="zai-kicker">{_safe(candidate.get('record_type'))} · Match Score {_safe(candidate.get('match_score'))}</div>
                <div class="zai-title">{_safe(candidate.get('project_id'))} · {_safe(candidate.get('project_name'))}</div>
                <div class="zai-meta">
                    Client Code: <b>{_safe(candidate.get('client_code'))}</b><br>
                    Order No: <b>{_safe(candidate.get('order_no'))}</b><br>
                    Owner: <b>{_safe(candidate.get('current_owner'))}</b><br>
                    Phase: <b>{_safe(candidate.get('phase'))}</b><br>
                    Next Step: {_safe(candidate.get('next_step'))}<br>
                    Target Date: {_safe(candidate.get('target_date'))}
                </div>
                <span class="zai-chip">{_safe(review_text)}</span>
                <span class="zai-chip">{_safe(candidate.get('health_status'))}</span>
                <span class="zai-chip">{_safe(candidate.get('result_status'))}</span>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )
    key = f"{key_prefix}_select_project_{index}_{candidate.get('record_type')}_{candidate.get('entity_id')}"
    if st.button("Select this project", key=key, use_container_width=True):
        st.session_state[f"{key_prefix}_selected_project"] = candidate
        st.session_state.pop(f"{key_prefix}_generated_draft", None)
        st.session_state.pop(f"{key_prefix}_saved_draft_id", None)
        st.session_state.pop(f"{key_prefix}_apply_result", None)
        st.rerun()


def _render_selected_project(project: dict[str, Any]) -> None:
    st.markdown(
        _html(
            f"""
            <div class="zai-card zai-selected">
                <div class="zai-kicker">Confirmed Project Before AI Processing</div>
                <div class="zai-title">{_safe(project.get('project_id'))} · {_safe(project.get('project_name'))}</div>
                <div class="zai-meta">
                    Record Type: <b>{_safe(project.get('record_type'))}</b><br>
                    Entity ID: <b>{_safe(project.get('entity_id'))}</b><br>
                    Client Code: <b>{_safe(project.get('client_code'))}</b><br>
                    Order No: <b>{_safe(project.get('order_no'))}</b><br>
                    Owner: <b>{_safe(project.get('current_owner'))}</b><br>
                    Phase: <b>{_safe(project.get('phase'))}</b>
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
    reverse_field_labels = {label: field for field, label in FIELD_LABELS.items()}
    for _, row in review_frame.iterrows():
        field_key = clean_text(row.get("Field Key")) or reverse_field_labels.get(clean_text(row.get("Field")), "")
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


def _render_review_editor(project: dict[str, Any], draft: dict[str, Any], *, key_prefix: str) -> pd.DataFrame:
    review_frame = _build_review_dataframe(project, draft)
    return st.data_editor(
        review_frame,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_order=["Apply", "Field", "Existing Record", "AI Suggested Update"],
        disabled=["Field", "Existing Record"],
        column_config={
            "Apply": st.column_config.CheckboxColumn("Apply", help="Tick only the fields you want to write into the system.", width="small"),
            "Field": st.column_config.TextColumn("Field", width="medium"),
            "Existing Record": st.column_config.TextColumn("Existing Record", width="large"),
            "AI Suggested Update": st.column_config.TextColumn("AI Suggested Update", width="large"),
        },
        key=f"{key_prefix}_review_editor",
    )



def _project_key(project: dict[str, Any] | None) -> str:
    if not project:
        return ""
    return "|".join(
        [
            str(project.get("record_type") or ""),
            str(project.get("entity_id") or ""),
            str(project.get("project_id") or ""),
            str(project.get("order_no") or ""),
        ]
    )


def _project_label(project: dict[str, Any]) -> str:
    project_id = clean_text(project.get("project_id")) or clean_text(project.get("entity_id")) or "-"
    project_name = clean_text(project.get("project_name")) or "-"
    order_no = clean_text(project.get("order_no")) or "-"
    owner = clean_text(project.get("next_step_owner")) or clean_text(project.get("current_owner")) or "-"
    status = clean_text(project.get("health_status")) or "-"
    return f"{project_id} · {project_name} | Order: {order_no} | Owner: {owner} | {status}"


def _set_selected_project(project: dict[str, Any], *, key_prefix: str) -> None:
    new_key = _project_key(project)
    old_key = st.session_state.get(f"{key_prefix}_selected_project_key")
    if new_key != old_key:
        st.session_state[f"{key_prefix}_selected_project"] = project
        st.session_state[f"{key_prefix}_selected_project_key"] = new_key
        st.session_state.pop(f"{key_prefix}_generated_draft", None)
        st.session_state.pop(f"{key_prefix}_saved_draft_id", None)
        st.session_state.pop(f"{key_prefix}_apply_result", None)


def render_ai_meeting_prep_assistant(
    current_user: Any,
    *,
    key_prefix: str = "meeting_board_ai_prep",
    meeting_context_candidates: list[dict[str, Any]] | None = None,
    selected_project_context: dict[str, Any] | None = None,
    compact: bool = False,
) -> None:
    """Render the AI Meeting Prep Assistant inside Meeting Board.

    This widget keeps the previous safety workflow:
    search/select project -> AI draft -> existing vs suggested review -> optional confirmed update.
    Meeting Note is intentionally excluded from AI updates.
    """
    _render_css()
    acting_user = str(current_user.get("display_name") or current_user.get("email") or "AI User") if isinstance(current_user, dict) else str(current_user)

    st.markdown(
        _html(
            """
            <div class="zai-note">
                AI Meeting Assistant is embedded in Meeting Board. It prepares structured Meeting Prep suggestions only.
                Meeting Note is not updated by AI. Selected fields are written only after human confirmation.
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    context_candidates = list(meeting_context_candidates or [])
    if selected_project_context and not context_candidates:
        context_candidates = [selected_project_context]

    if context_candidates:
        st.subheader("AI Meeting Assistant")
        st.caption("Target is linked to the current Meeting Board search results. Select one item, then generate a Meeting Prep draft while reviewing the project card beside it.")
        candidate_keys = [_project_key(item) for item in context_candidates]
        default_key = _project_key(selected_project_context) if selected_project_context else candidate_keys[0]
        default_index = candidate_keys.index(default_key) if default_key in candidate_keys else 0
        selected_context_index = st.selectbox(
            "Target project / order from current Meeting Board results",
            options=list(range(len(context_candidates))),
            index=default_index,
            format_func=lambda idx: _project_label(context_candidates[int(idx)]),
            key=f"{key_prefix}_context_target_select",
        )
        _set_selected_project(context_candidates[int(selected_context_index)], key_prefix=key_prefix)
    else:
        left_col, right_col = st.columns([0.95, 1.55], gap="large")
        with left_col:
            st.subheader("1 · Find Project / Order")
            search_query = st.text_input(
                "Search by Project ID, Project Name, Order No, or Client Code",
                placeholder="Example: SDG-26-014, GLG180326-1, client code, product name",
                key=f"{key_prefix}_search_query",
            )
            f1, f2 = st.columns(2)
            with f1:
                record_type_filter = st.selectbox(
                    "Record Type",
                    ["All", "Sales", "Operation"],
                    index=0,
                    key=f"{key_prefix}_record_type_filter",
                )
            with f2:
                review_only = st.checkbox("Review This Week only", value=False, key=f"{key_prefix}_review_only")

            if search_query:
                candidates = search_project_candidates(search_query, record_type_filter=record_type_filter, review_only=review_only)
                if not candidates:
                    st.info("No confirmed project found. Try another keyword, Project Name, Order No, or Client Code.")
                else:
                    st.caption(f"Found {len(candidates)} possible record(s). Please select one before AI processing.")
                    for index, candidate in enumerate(candidates):
                        _candidate_card(candidate, index, key_prefix=key_prefix)

        with right_col:
            st.subheader("2 · Generate Meeting Prep Draft")
    if context_candidates:
        st.subheader("Generate Meeting Prep Draft")
    selected_project = st.session_state.get(f"{key_prefix}_selected_project")
    if not selected_project:
        st.info("Search and select one project/order first.")
        return

    _render_selected_project(selected_project)
    if not context_candidates:
        if st.button("Clear selected project", use_container_width=True, key=f"{key_prefix}_clear_selected"):
            st.session_state.pop(f"{key_prefix}_selected_project", None)
            st.session_state.pop(f"{key_prefix}_selected_project_key", None)
            st.session_state.pop(f"{key_prefix}_generated_draft", None)
            st.session_state.pop(f"{key_prefix}_saved_draft_id", None)
            st.session_state.pop(f"{key_prefix}_apply_result", None)
            st.rerun()

    output_language = st.selectbox(
        "AI output language",
        ["English", "Chinese", "Bilingual Chinese and English"],
        index=0,
        key=f"{key_prefix}_output_language",
    )
    meeting_notes = st.text_area(
        "Colleague input / pre-meeting information",
        height=160,
        placeholder="Paste meeting notes, colleague update, client request, supplier feedback, or boss decision point here.",
        key=f"{key_prefix}_meeting_notes",
    )
    generate_disabled = not bool(selected_project.get("project_id")) or not meeting_notes.strip()
    if st.button(
        "Generate AI Meeting Prep Draft",
        disabled=generate_disabled,
        type="primary",
        use_container_width=True,
        key=f"{key_prefix}_generate",
    ):
        try:
            with st.spinner("AI is preparing Meeting Prep fields..."):
                draft = extract_meeting_fields_with_ai(
                    selected_project=selected_project,
                    meeting_notes=meeting_notes,
                    output_language=output_language,
                )
            st.session_state[f"{key_prefix}_generated_draft"] = draft
            st.session_state.pop(f"{key_prefix}_saved_draft_id", None)
            st.session_state.pop(f"{key_prefix}_apply_result", None)
            st.rerun()
        except (AIConfigError, AIResponseError) as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"AI processing failed: {exc}")

    draft = st.session_state.get(f"{key_prefix}_generated_draft")
    if not draft:
        return

    st.divider()
    st.subheader("3 · Review AI Suggested Update")
    st.markdown(
        _html(
            f"""
            <div class="zai-card">
                <div class="zai-kicker">AI Review Summary</div>
                <div class="zai-meta">
                    AI Summary for Review: <b>{_safe(draft.get('ai_summary_for_review'))}</b><br>
                    Difference Summary: <b>{_safe(draft.get('difference_summary'))}</b><br>
                    Confidence: <b>{_safe(draft.get('confidence'))}</b><br>
                    Needs Human Attention: <b>{_safe(draft.get('needs_human_attention'))}</b>
                </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )
    edited_review_frame = _render_review_editor(selected_project, draft, key_prefix=key_prefix)
    st.warning(
        "Confirm will apply only the selected fields into Sales / Operation Meeting Prep fields. "
        "Empty AI fields will not clear existing data. Existing non-empty fields are not selected by default. "
        "Meeting Note will not be changed."
    )
    selected_draft = _draft_from_review_table(edited_review_frame, draft)
    selected_count = len(selected_draft.get("applied_fields") or [])
    st.caption(f"Selected fields to apply: {selected_count}")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Save as Pending AI Draft", use_container_width=True, key=f"{key_prefix}_save_pending"):
            draft_id = save_ai_update_draft(
                selected_project=selected_project,
                meeting_notes=meeting_notes,
                draft_json={"raw_ai_draft": draft, "review_table": edited_review_frame.to_dict("records")},
                current_user=current_user,
                status="pending",
            )
            st.session_state[f"{key_prefix}_saved_draft_id"] = draft_id
            st.session_state[f"{key_prefix}_apply_result"] = None
            st.success(f"AI draft saved. Draft ID: {draft_id}")
    with c2:
        if st.button(
            "Confirm Selected Fields + Update System",
            type="primary",
            use_container_width=True,
            disabled=selected_count == 0,
            key=f"{key_prefix}_confirm_apply",
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
                mark_ai_draft_status(draft_id=draft_id, status=final_status, current_user=current_user)
                st.session_state[f"{key_prefix}_saved_draft_id"] = draft_id
                st.session_state[f"{key_prefix}_apply_result"] = apply_result
                if apply_result.get("updated"):
                    st.success(f"AI Meeting Prep confirmed and applied. Draft ID: {draft_id}.")
                else:
                    st.info(f"AI draft confirmed, but no field changed. Draft ID: {draft_id}.")
            except Exception as exc:
                mark_ai_draft_status(draft_id=draft_id, status="apply_failed", current_user=current_user)
                st.error(f"Saved draft, but applying selected fields failed: {exc}")

    apply_result = st.session_state.get(f"{key_prefix}_apply_result")
    if apply_result:
        updated_fields = apply_result.get("updated_fields") or []
        skipped_fields = apply_result.get("skipped_fields") or []
        if updated_fields:
            st.write("Updated fields:", ", ".join(updated_fields))
        if skipped_fields:
            st.write("Skipped fields:", ", ".join(skipped_fields))
