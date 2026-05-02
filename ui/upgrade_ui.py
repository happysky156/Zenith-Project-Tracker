from __future__ import annotations

from html import escape
from textwrap import dedent
from typing import Any

import streamlit as st

from services.upgrade_service import MODULES, build_summary_metrics, field_display_map, field_names
from ui.project_table import render_project_table


def _html(markup: str) -> str:
    return dedent(markup).strip()


def render_upgrade_css() -> None:
    st.markdown(
        _html(
            """
            <style>
            .zu-hero-card {
                background: #ffffff;
                border: 1px solid #e8e8eb;
                border-radius: 24px;
                padding: 18px 20px 16px 20px;
                box-shadow: 0 12px 30px rgba(17,17,17,0.045);
                margin: 0.5rem 0 1rem 0;
            }
            .zu-kicker {
                color: #c5161d;
                font-size: 0.72rem;
                font-weight: 860;
                letter-spacing: 0.1em;
                text-transform: uppercase;
                margin-bottom: 0.35rem;
            }
            .zu-title {
                color: #111111;
                font-size: 1.08rem;
                font-weight: 850;
                letter-spacing: -0.02em;
                margin-bottom: 0.35rem;
            }
            .zu-text {
                color: #555961;
                font-size: 0.9rem;
                line-height: 1.5;
            }
            .zu-metric-grid {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.75rem;
                margin: 0.8rem 0 1rem 0;
            }
            .zu-metric-card {
                background: #ffffff;
                border: 1px solid #eeeeef;
                border-radius: 18px;
                padding: 0.85rem 0.9rem;
                box-shadow: 0 8px 20px rgba(17,17,17,0.035);
            }
            .zu-metric-label {
                color: #646870;
                font-size: 0.75rem;
                font-weight: 820;
                line-height: 1.2;
                margin-bottom: 0.4rem;
            }
            .zu-metric-value {
                color: #111111;
                font-size: 1.45rem;
                line-height: 1;
                font-weight: 880;
                letter-spacing: -0.04em;
            }
            .zu-status-chip {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                padding: 0.24rem 0.55rem;
                border: 1px solid #e7e7ea;
                background: #fafafa;
                color: #333333;
                font-size: 0.78rem;
                font-weight: 740;
                margin: 0.12rem 0.2rem 0.12rem 0;
            }
            .zu-field-group-title {
                color: #111111;
                font-size: 0.98rem;
                font-weight: 850;
                margin: 0.4rem 0 0.2rem 0;
            }
            .zu-empty {
                background: #ffffff;
                border: 1px dashed #d9d9dd;
                border-radius: 18px;
                padding: 1rem;
                color: #74777e;
                font-size: 0.9rem;
                margin: 0.6rem 0;
            }
            @media (max-width: 1100px) {
                .zu-metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            }
            @media (max-width: 680px) {
                .zu-metric-grid { grid-template-columns: 1fr; }
            }
            </style>
            """
        ),
        unsafe_allow_html=True,
    )


def render_upgrade_intro(title: str, description: str, kicker: str = "v18 Extension") -> None:
    st.markdown(
        _html(
            f"""
            <div class='zu-hero-card'>
                <div class='zu-kicker'>{escape(kicker)}</div>
                <div class='zu-title'>{escape(title)}</div>
                <div class='zu-text'>{escape(description)}</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def render_metric_grid(metrics: dict[str, Any]) -> None:
    html = "".join(
        f"<div class='zu-metric-card'><div class='zu-metric-label'>{escape(str(k))}</div><div class='zu-metric-value'>{escape(str(v))}</div></div>"
        for k, v in metrics.items()
    )
    st.markdown(f"<div class='zu-metric-grid'>{html}</div>", unsafe_allow_html=True)


def render_status_chips(items: list[str]) -> None:
    if not items:
        return
    html = "".join(f"<span class='zu-status-chip'>{escape(str(item))}</span>" for item in items if item)
    st.markdown(html, unsafe_allow_html=True)


def render_layered_records(
    module_name: str,
    rows: list[dict[str, Any]],
    *,
    key_prefix: str,
    summary_field: str | None = None,
    preview_columns: list[str] | None = None,
    detail_columns: list[str] | None = None,
    expanded: bool = False,
) -> None:
    spec = MODULES[module_name]
    render_upgrade_intro(spec.title, spec.description, kicker="Detail Tab" if key_prefix.startswith("detail") else "Module")
    if not rows:
        st.markdown("<div class='zu-empty'>No records yet.</div>", unsafe_allow_html=True)
        return
    render_metric_grid(build_summary_metrics(rows, summary_field))
    display_map = field_display_map(module_name)
    preview_columns = preview_columns or field_names(module_name)[:8]
    detail_columns = detail_columns or field_names(module_name)

    with st.expander("Summary table", expanded=True):
        render_project_table(rows, preview_columns, empty_message="No records.", enable_jump=False)
    with st.expander("All fields / audit details", expanded=expanded):
        st.caption("Full field view is hidden by default so large tabs stay fast and readable.")
        render_project_table(rows, detail_columns, empty_message="No records.", enable_jump=False)
        with st.expander("Field guide", expanded=False):
            guide = [
                {"field_name": f.name, "display_name": f.display, "description": f.description}
                for f in spec.fields
            ]
            render_project_table(guide, ["field_name", "display_name", "description"], empty_message="No fields.", enable_jump=False)


def render_simple_filter_bar(module_name: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    search = st.text_input("Search", placeholder="Search by Project ID, supplier, item, order, status...", key=f"search_{module_name}")
    if not search:
        return rows
    keyword = search.strip().lower()
    return [row for row in rows if any(keyword in str(v or "").lower() for v in row.values())]
