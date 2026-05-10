from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import streamlit as st

from services.ai_business_review_common import STANDARD_AI_REVIEW_NOTICE, dataframe_to_csv_bytes, review_to_dataframe, review_to_markdown


def render_ai_review_notice() -> None:
    st.caption(STANDARD_AI_REVIEW_NOTICE)


def render_ai_review(review: dict[str, Any], *, title: str = "AI Review", export_file_prefix: str = "ai_review") -> None:
    render_ai_review_notice()
    if not review:
        st.info("No AI review has been generated yet.")
        return

    ai_used = bool(review.get("ai_used"))
    if review.get("ai_error"):
        st.warning(
            "AI API summary was not available, so this section shows a safe rule-based review. "
            f"API message: {review.get('ai_error')}"
        )
    elif ai_used:
        st.success("AI review generated from current system records.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Readiness", str(review.get("readiness") or "Need Review"))
    c2.metric("Confidence", str(review.get("confidence") or "Medium"))
    c3.metric("Human Attention", str(review.get("needs_human_attention") or "Yes"))

    st.markdown("#### Direct Summary")
    st.write(review.get("direct_summary") or "-")

    for key, label in [
        ("key_findings", "Key Findings"),
        ("risks", "Risks"),
        ("missing_information", "Missing Information"),
        ("suggested_actions", "Suggested Actions"),
    ]:
        with st.expander(label, expanded=(key in {"risks", "missing_information"} and bool(review.get(key)))):
            items = review.get(key) or []
            if not items:
                st.caption("No item found in current system records.")
            else:
                for item in items:
                    st.write(f"- {item}")

    with st.expander("Source Records", expanded=False):
        source_records = review.get("source_records") or []
        if not source_records:
            st.caption("No source records attached.")
        else:
            st.dataframe(pd.DataFrame(source_records), use_container_width=True, hide_index=True)

    export_df = review_to_dataframe(review)
    export_text = review_to_markdown(review, title=title)
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            f"Download {title} (.txt)",
            data=export_text.encode("utf-8-sig"),
            file_name=f"{export_file_prefix}.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with d2:
        st.download_button(
            f"Download {title} (.csv)",
            data=dataframe_to_csv_bytes(export_df),
            file_name=f"{export_file_prefix}.csv",
            mime="text/csv",
            use_container_width=True,
        )
