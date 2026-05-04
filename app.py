from __future__ import annotations

from html import escape
from io import BytesIO
from textwrap import dedent
from typing import Any
from datetime import datetime

import pandas as pd
import streamlit as st

from core.state import init_session_state
from core.auth import require_login
from services.project_service import get_dashboard_metrics
from database.repositories import list_operation_orders, list_sales_projects
from ui.theme import apply_theme, render_page_header
from utils.logger import get_logger

from pathlib import Path


def _remove_legacy_settings_page() -> None:
    """Remove the old Settings page after the page was renamed to Field Setup."""
    pages_dir = Path(__file__).resolve().parent / "pages"
    legacy_page = pages_dir / "6_Settings.py"
    replacement_page = pages_dir / "6_Field_Setup.py"
    if legacy_page.exists() and replacement_page.exists():
        try:
            legacy_page.unlink()
        except OSError:
            pass


_remove_legacy_settings_page()

st.set_page_config(
    page_title="Dashboard - Zenith Project Tracker",
    page_icon="📊",
    layout="wide",
)

init_session_state()
apply_theme()
current_user = require_login()

logger = get_logger("dashboard")
logger.info("Zenith Project Tracker dashboard started.")


def _n(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _pct(part: int, total: int) -> int:
    if total <= 0:
        return 0
    return int(round((part / total) * 100))


def _safe(value: Any) -> str:
    return escape(str(value or "-"))


def _html(markup: str) -> str:
    return dedent(markup).strip()


def _render_dashboard_css() -> None:
    st.markdown(
        _html(
            """
            <style>
            .block-container { padding-top: 1.05rem !important; }

            .zd-grid-4 {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.85rem;
                margin: 0.6rem 0 1.05rem 0;
            }
            .zd-grid-3 {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.85rem;
                margin: 0.6rem 0 1.05rem 0;
            }
            .zd-grid-2 {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.9rem;
                margin: 0.65rem 0 1.05rem 0;
            }

            .zd-card {
                background: #ffffff;
                border: 1px solid #e8e8eb;
                border-radius: 22px;
                padding: 18px 18px 16px 18px;
                box-shadow: 0 10px 28px rgba(17,17,17,0.045);
                min-height: 120px;
                position: relative;
                overflow: hidden;
            }
            .zd-card:before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 4px;
                background: var(--accent, #c5161d);
            }
            .zd-kpi-label {
                color: #6f737a;
                font-size: 0.78rem;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0.06em;
                margin-bottom: 0.42rem;
            }
            .zd-kpi-value {
                color: #111111;
                font-size: 2.25rem;
                line-height: 1;
                font-weight: 850;
                letter-spacing: -0.045em;
                margin-bottom: 0.48rem;
            }
            .zd-kpi-sub {
                color: #61646b;
                font-size: 0.86rem;
                line-height: 1.4;
            }

            .zd-section-title-wrap {
                display: flex;
                justify-content: space-between;
                align-items: flex-end;
                gap: 1rem;
                margin: 1.05rem 0 0.35rem 0;
            }
            .zd-section-kicker {
                color: #c5161d;
                font-size: 0.74rem;
                font-weight: 850;
                letter-spacing: 0.1em;
                text-transform: uppercase;
                margin-bottom: 0.16rem;
            }
            .zd-section-title {
                color: #111111;
                font-size: 1.2rem;
                font-weight: 820;
                letter-spacing: -0.02em;
            }
            .zd-section-note {
                color: #72767d;
                font-size: 0.86rem;
                line-height: 1.4;
                max-width: 760px;
            }

            .zd-panel {
                background: #ffffff;
                border: 1px solid #e8e8eb;
                border-radius: 22px;
                padding: 18px 18px 16px 18px;
                box-shadow: 0 10px 28px rgba(17,17,17,0.045);
            }
            .zd-panel-title {
                font-size: 1.02rem;
                font-weight: 820;
                color: #111111;
                margin-bottom: 0.2rem;
            }
            .zd-panel-subtitle {
                font-size: 0.84rem;
                color: #74777e;
                margin-bottom: 0.85rem;
            }

            .zd-exec-line {
                display: grid;
                grid-template-columns: 88px minmax(0, 1fr) 44px;
                align-items: center;
                gap: 0.65rem;
                margin: 0.2rem 0 0.95rem 0;
            }
            .zd-exec-label {
                color: #555961;
                font-size: 0.78rem;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0.04em;
            }
            .zd-exec-track {
                height: 12px;
                border-radius: 999px;
                background: #f0f0f2;
                overflow: hidden;
            }
            .zd-exec-fill {
                height: 100%;
                width: var(--w, 0%);
                background: linear-gradient(90deg, #111111 0%, #c5161d 100%);
                border-radius: 999px;
            }
            .zd-exec-pct {
                color: #111111;
                font-size: 0.88rem;
                font-weight: 820;
                text-align: right;
            }

            .zd-status-tile-grid {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.55rem;
            }
            .zd-status-tile-grid.operation {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }
            .zd-status-tile {
                border: 1px solid #eeeeef;
                border-radius: 16px;
                background: #fafafa;
                padding: 0.78rem 0.82rem;
                min-height: 86px;
                position: relative;
                overflow: hidden;
            }
            .zd-status-tile:before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                width: 4px;
                height: 100%;
                background: var(--bar, #c5161d);
            }
            .zd-status-name {
                color: #646870;
                font-size: 0.76rem;
                font-weight: 800;
                line-height: 1.2;
                margin-bottom: 0.4rem;
            }
            .zd-status-value {
                color: #111111;
                font-size: 1.55rem;
                font-weight: 850;
                letter-spacing: -0.04em;
                line-height: 1;
            }
            .zd-status-pct-small {
                color: #8a8d93;
                font-size: 0.75rem;
                font-weight: 700;
                margin-top: 0.35rem;
            }

            .zd-phase-panel {
                background: #ffffff;
                border: 1px solid #e8e8eb;
                border-radius: 22px;
                padding: 16px 18px;
                box-shadow: 0 10px 28px rgba(17,17,17,0.045);
            }
            .zd-phase-row {
                display: flex;
                align-items: flex-start;
                gap: 0.75rem;
                padding: 0.55rem 0;
                border-bottom: 1px solid #f0f0f2;
            }
            .zd-phase-row:last-child { border-bottom: none; }
            .zd-phase-title {
                width: 128px;
                flex: 0 0 128px;
                color: #111111;
                font-size: 0.88rem;
                font-weight: 820;
                padding-top: 0.15rem;
            }
            .zd-chip-wrap {
                display: flex;
                flex-wrap: wrap;
                gap: 0.45rem;
            }
            .zd-phase-chip {
                display: inline-flex;
                align-items: center;
                gap: 0.42rem;
                border: 1px solid #e5e5e7;
                background: #fafafa;
                color: #333333;
                border-radius: 999px;
                padding: 0.34rem 0.62rem;
                font-size: 0.8rem;
                font-weight: 720;
            }
            .zd-phase-count {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 1.35rem;
                height: 1.35rem;
                border-radius: 999px;
                background: #111111;
                color: #ffffff;
                font-size: 0.72rem;
                font-weight: 850;
                padding: 0 0.28rem;
            }

            .zd-attention-grid {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 0.75rem;
                margin-top: 0.7rem;
            }
            .zd-attention-card {
                background: #fff;
                border: 1px solid #e8e8eb;
                border-radius: 18px;
                padding: 0.85rem 0.9rem;
                box-shadow: 0 8px 22px rgba(17,17,17,0.035);
            }
            .zd-attention-label {
                color: #6f737a;
                font-size: 0.76rem;
                font-weight: 760;
                margin-bottom: 0.22rem;
            }
            .zd-attention-value {
                color: #111111;
                font-size: 1.45rem;
                font-weight: 840;
                letter-spacing: -0.035em;
            }

            .zd-table-toolbar {
                background: #ffffff;
                border: 1px solid #e8e8eb;
                border-radius: 20px;
                padding: 0.9rem 1rem;
                box-shadow: 0 8px 22px rgba(17,17,17,0.035);
                margin: 0.65rem 0 0.85rem 0;
            }
            .zd-toolbar-title {
                color: #111111;
                font-size: 0.96rem;
                font-weight: 820;
                margin-bottom: 0.2rem;
            }
            .zd-toolbar-sub {
                color: #686c73;
                font-size: 0.84rem;
                line-height: 1.4;
            }
            .zd-empty {
                background: #ffffff;
                border: 1px dashed #d9d9dd;
                border-radius: 18px;
                padding: 1.2rem;
                color: #777b82;
                font-size: 0.9rem;
            }

            @media (max-width: 1100px) {
                .zd-grid-4, .zd-grid-3, .zd-grid-2 { grid-template-columns: 1fr; }
                .zd-attention-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                .zd-status-tile-grid, .zd-status-tile-grid.operation { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            }
            @media (max-width: 700px) {
                .zd-attention-grid, .zd-status-tile-grid, .zd-status-tile-grid.operation { grid-template-columns: 1fr; }
                .zd-exec-line { grid-template-columns: 72px minmax(0, 1fr) 40px; }
                .zd-phase-row { flex-direction: column; }
                .zd-phase-title { width: auto; flex: auto; }
            }
            </style>
            """
        ),
        unsafe_allow_html=True,
    )


def _kpi_card(label: str, value: int, sub: str, accent: str = "#c5161d") -> str:
    return _html(
        f"""
        <div class='zd-card' style='--accent:{accent}'>
            <div class='zd-kpi-label'>{escape(label)}</div>
            <div class='zd-kpi-value'>{_n(value)}</div>
            <div class='zd-kpi-sub'>{escape(sub)}</div>
        </div>
        """
    )


def _section_title(kicker: str, title: str, note: str | None = None) -> None:
    note_html = f"<div class='zd-section-note'>{escape(note)}</div>" if note else ""
    st.markdown(
        _html(
            f"""
            <div class='zd-section-title-wrap'>
                <div>
                    <div class='zd-section-kicker'>{escape(kicker)}</div>
                    <div class='zd-section-title'>{escape(title)}</div>
                </div>
                {note_html}
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def _status_tiles(counts: dict[str, int], total: int, colours: dict[str, str], operation: bool = False) -> str:
    if not counts:
        return "<div class='zd-empty'>No data available yet.</div>"

    tiles = []
    for label, raw_value in counts.items():
        value = _n(raw_value)
        percent = _pct(value, total)
        colour = colours.get(label, "#c5161d")
        tiles.append(
            _html(
                f"""
                <div class='zd-status-tile' style='--bar:{colour}'>
                    <div class='zd-status-name'>{escape(label)}</div>
                    <div class='zd-status-value'>{value}</div>
                    <div class='zd-status-pct-small'>{percent}% of total</div>
                </div>
                """
            )
        )

    css_class = "zd-status-tile-grid operation" if operation else "zd-status-tile-grid"
    return f"<div class='{css_class}'>{''.join(tiles)}</div>"


def _progress_dashboard_panel(
    title: str,
    subtitle: str,
    counts: dict[str, int],
    total: int,
    active: int,
    colours: dict[str, str],
    operation: bool = False,
) -> str:
    active_pct = _pct(active, total)
    return _html(
        f"""
        <div class='zd-panel'>
            <div class='zd-panel-title'>{escape(title)}</div>
            <div class='zd-panel-subtitle'>{escape(subtitle)}</div>
            <div class='zd-exec-line'>
                <div class='zd-exec-label'>Active</div>
                <div class='zd-exec-track'><div class='zd-exec-fill' style='--w:{active_pct}%'></div></div>
                <div class='zd-exec-pct'>{active_pct}%</div>
            </div>
            {_status_tiles(counts, max(total, 1), colours, operation)}
        </div>
        """
    )


def _phase_chips(title: str, counts: dict[str, int]) -> str:
    chips = []
    for label, raw_value in counts.items():
        value = _n(raw_value)
        if value <= 0:
            continue
        chips.append(
            _html(
                f"""
                <span class='zd-phase-chip'>
                    <span>{escape(label)}</span>
                    <span class='zd-phase-count'>{value}</span>
                </span>
                """
            )
        )

    chip_html = "".join(chips) if chips else "<span class='zd-phase-chip'><span>No active item</span><span class='zd-phase-count'>0</span></span>"
    return _html(
        f"""
        <div class='zd-phase-row'>
            <div class='zd-phase-title'>{escape(title)}</div>
            <div class='zd-chip-wrap'>{chip_html}</div>
        </div>
        """
    )


def _phase_panel(sales_counts: dict[str, int], operation_counts: dict[str, int]) -> str:
    return _html(
        f"""
        <div class='zd-phase-panel'>
            {_phase_chips('Sales', sales_counts)}
            {_phase_chips('Operation', operation_counts)}
        </div>
        """
    )


def _attention_grid(attention: dict[str, int]) -> str:
    if not attention:
        return "<div class='zd-empty'>No attention data available yet.</div>"
    cards = []
    for label, raw_value in attention.items():
        value = _n(raw_value)
        cards.append(
            _html(
                f"""
                <div class='zd-attention-card'>
                    <div class='zd-attention-label'>{escape(label)}</div>
                    <div class='zd-attention-value'>{value}</div>
                </div>
                """
            )
        )
    return f"<div class='zd-attention-grid'>{''.join(cards)}</div>"


def _render_attention_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        st.info("No attention items found.")
        return

    display_columns = [
        "Type",
        "Project ID",
        "Project Name",
        "Client Code",
        "Order No",
        "Current Owner",
        "Phase",
        "Health Status",
        "Result Status",
        "Main Issue",
        "Next Step",
        "Next Step Owner",
        "Target Date",
        "Last Event",
    ]
    frame = pd.DataFrame(rows)
    present_columns = [col for col in display_columns if col in frame.columns]
    st.dataframe(frame[present_columns], use_container_width=True, hide_index=True)


EXPORT_COLUMNS = {
    "Sales Project Status": [
        "project_id",
        "project_name",
        "client_code",
        "current_owner",
        "phase",
        "health_status",
        "result_status",
        "review_this_week",
        "linked_order_count",
        "linked_orders",
        "next_step_summary",
        "next_step_owner",
        "target_date",
        "last_event",
    ],
    "Operation Order Status": [
        "order_no",
        "project_id",
        "linked_project_name",
        "client_code",
        "current_owner",
        "phase",
        "health_status",
        "result_status",
        "review_this_week",
        "waiting_for_text",
        "next_step_summary",
        "next_step_owner",
        "target_date",
        "last_event",
    ],
    "Projects with Orders": [
        "project_id",
        "project_name",
        "client_code",
        "current_owner",
        "result_status",
        "linked_order_count",
        "linked_orders",
    ],
    "Projects without Orders": [
        "project_id",
        "project_name",
        "client_code",
        "current_owner",
        "phase",
        "health_status",
        "result_status",
        "next_step_summary",
        "next_step_owner",
        "target_date",
    ],
    "Unlinked Operation Orders": [
        "order_no",
        "project_id",
        "linked_project_name",
        "client_code",
        "current_owner",
        "phase",
        "health_status",
        "result_status",
        "waiting_for_text",
        "next_step_summary",
        "next_step_owner",
        "target_date",
    ],
}

EXPORT_LABELS = {
    "project_id": "Project ID",
    "project_name": "Project Name",
    "linked_project_name": "Project Name",
    "client_code": "Client Code",
    "current_owner": "Owner",
    "phase": "Phase",
    "health_status": "Health Status",
    "result_status": "Result Status",
    "review_this_week": "Review This Week",
    "linked_order_count": "Linked Order Count",
    "linked_orders": "Linked Orders",
    "next_step_summary": "Next Step",
    "next_step_owner": "Next Step Owner",
    "target_date": "Target Date",
    "last_event": "Last Event",
    "order_no": "Order No",
    "waiting_for_text": "Waiting For What",
}


def _export_frame(rows: list[dict[str, Any]], columns: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        frame = pd.DataFrame(columns=columns)
    present_columns = [col for col in columns if col in frame.columns]
    missing_columns = [col for col in columns if col not in frame.columns]
    display = frame[present_columns].copy()
    for col in missing_columns:
        display[col] = ""
    display = display[columns]
    if "review_this_week" in display.columns:
        display["review_this_week"] = display["review_this_week"].map(lambda v: "Yes" if bool(v) else "No")
    display = display.rename(columns={col: EXPORT_LABELS.get(col, col.replace("_", " ").title()) for col in display.columns})
    return display


def _dashboard_summary_frame(metrics: dict[str, Any]) -> pd.DataFrame:
    sales_progress = metrics.get("sales_progress", {}) or {}
    operation_progress = metrics.get("operation_progress", {}) or {}
    rows = [
        ("Summary", "Total Sales", _n(metrics.get("total_sales")), "All Sales projects in the system"),
        ("Summary", "Active Sales", _n(metrics.get("active_sales")), "Not Won / Lost; Hold included"),
        ("Summary", "Total Operation", _n(metrics.get("total_operations")), "All Operation orders in the system"),
        ("Summary", "Active Operation", _n(metrics.get("active_operations")), "Not Paid Closed / Cancelled; Hold included"),
        ("Summary", "All Items", _n(metrics.get("all_items")), "Sales projects + Operation orders"),
        ("Summary", "High Attention", _n(metrics.get("high_attention_total")), "Blocked, Delayed, Due Soon, Decision or Alignment"),
        ("Summary", "Waiting Items", _n(metrics.get("waiting_total")), "Waiting Client / Supplier / Internal"),
        ("Sales Progress", "On Progress", _n(sales_progress.get("On Progress")), "Sales projects still being followed up"),
        ("Sales Progress", "Hold", _n(sales_progress.get("Hold")), "Sales projects currently on hold"),
        ("Sales Progress", "Won", _n(sales_progress.get("Won")), "Sales projects won"),
        ("Sales Progress", "Lost", _n(sales_progress.get("Lost")), "Sales projects lost"),
        ("Sales Progress", "Projects with Orders", _n(sales_progress.get("Projects with Orders")), "Sales projects linked to at least one Operation order"),
        ("Sales Progress", "Projects without Orders", _n(sales_progress.get("Projects without Orders")), "Sales projects without linked Operation orders"),
        ("Operation Progress", "On Progress", _n(operation_progress.get("On Progress")), "Operation orders still in progress"),
        ("Operation Progress", "Hold", _n(operation_progress.get("Hold")), "Operation orders currently on hold"),
        ("Operation Progress", "Partial Shipped", _n(operation_progress.get("Partial Shipped")), "Operation orders partially shipped"),
        ("Operation Progress", "Complete Shipped", _n(operation_progress.get("Complete Shipped")), "Operation orders completely shipped"),
        ("Operation Progress", "Paid Closed", _n(operation_progress.get("Paid Closed")), "Operation orders paid and closed"),
        ("Operation Progress", "Cancelled", _n(operation_progress.get("Cancelled")), "Operation orders cancelled"),
    ]
    return pd.DataFrame(rows, columns=["Section", "Metric", "Count", "Notes"])


def _build_dashboard_export_bytes(metrics: dict[str, Any]) -> bytes:
    sales_rows = list_sales_projects()
    operation_rows = list_operation_orders()

    sales_project_ids = {str(row.get("project_id") or "").strip() for row in sales_rows if str(row.get("project_id") or "").strip()}
    operation_project_ids = {
        str(row.get("project_id") or "").strip()
        for row in operation_rows
        if str(row.get("project_id") or "").strip()
    }
    with_order_ids = sales_project_ids & operation_project_ids
    without_order_ids = sales_project_ids - operation_project_ids

    projects_with_orders = [
        row for row in sales_rows
        if str(row.get("project_id") or "").strip() in with_order_ids
    ]
    projects_without_orders = [
        row for row in sales_rows
        if str(row.get("project_id") or "").strip() in without_order_ids
    ]
    unlinked_operation_orders = [
        row for row in operation_rows
        if str(row.get("project_id") or "").strip() and str(row.get("project_id") or "").strip() not in sales_project_ids
    ]

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sheets = {
            "Dashboard Summary": _dashboard_summary_frame(metrics),
            "Sales Project Status": _export_frame(sales_rows, EXPORT_COLUMNS["Sales Project Status"]),
            "Operation Order Status": _export_frame(operation_rows, EXPORT_COLUMNS["Operation Order Status"]),
            "Projects with Orders": _export_frame(projects_with_orders, EXPORT_COLUMNS["Projects with Orders"]),
            "Projects without Orders": _export_frame(projects_without_orders, EXPORT_COLUMNS["Projects without Orders"]),
            "Unlinked Operation Orders": _export_frame(unlinked_operation_orders, EXPORT_COLUMNS["Unlinked Operation Orders"]),
        }
        for sheet_name, frame in sheets.items():
            frame.to_excel(writer, index=False, sheet_name=sheet_name)
            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes = "A2"
            for column_cells in worksheet.columns:
                max_length = 0
                column_letter = column_cells[0].column_letter
                for cell in column_cells:
                    value = "" if cell.value is None else str(cell.value)
                    max_length = max(max_length, min(len(value), 60))
                worksheet.column_dimensions[column_letter].width = max(12, min(max_length + 2, 42))
    output.seek(0)
    return output.getvalue()


def _render_dashboard_header(metrics: dict[str, Any]) -> None:
    header_col, export_col = st.columns([5.5, 1.2], vertical_alignment="center")
    with header_col:
        render_page_header(
            "Zenith Project Tracker",
            "A commercial operation workspace for customer opportunities, supplier quotations, order execution and risk visibility.",
        )
    with export_col:
        st.markdown("<div style='height: 4.2rem'></div>", unsafe_allow_html=True)
        st.download_button(
            "Export Meeting Pack",
            data=_build_dashboard_export_bytes(metrics),
            file_name=f"dashboard_meeting_pack_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            help="Download the 6-sheet dashboard export pack for weekly meeting review.",
        )


_render_dashboard_css()

metrics = get_dashboard_metrics()
_render_dashboard_header(metrics)
total_sales = _n(metrics.get("total_sales"))
active_sales = _n(metrics.get("active_sales"))
total_operations = _n(metrics.get("total_operations"))
active_operations = _n(metrics.get("active_operations"))
all_items = _n(metrics.get("all_items"))
high_attention = _n(metrics.get("high_attention_total"))
waiting_total = _n(metrics.get("waiting_total"))

st.markdown(
    _html(
        f"""
        <div class='zd-grid-4'>
            {_kpi_card('Total Sales', total_sales, 'All Sales projects in the system', '#111111')}
            {_kpi_card('Active Sales', active_sales, 'Not Won / Lost; Hold included', '#c5161d')}
            {_kpi_card('Total Operation', total_operations, 'All Operation orders in the system', '#111111')}
            {_kpi_card('Active Operation', active_operations, 'Not Paid Closed / Cancelled; Hold included', '#c5161d')}
        </div>
        """
    ),
    unsafe_allow_html=True,
)

st.markdown(
    _html(
        f"""
        <div class='zd-grid-3'>
            {_kpi_card('All Items', all_items, 'Sales projects + Operation orders', '#2c2c2c')}
            {_kpi_card('High Attention', high_attention, 'Blocked, Delayed, Due Soon, Decision or Alignment', '#c5161d')}
            {_kpi_card('Waiting Items', waiting_total, 'Waiting Client / Supplier / Internal', '#8a1d1d')}
        </div>
        """
    ),
    unsafe_allow_html=True,
)

sales_colours = {
    "On Progress": "#111111",
    "Hold": "#a1a1aa",
    "Won": "#2c2c2c",
    "Lost": "#c5161d",
}
operation_colours = {
    "On Progress": "#111111",
    "Hold": "#a1a1aa",
    "Partial Shipped": "#575757",
    "Complete Shipped": "#2c2c2c",
    "Paid Closed": "#111111",
    "Cancelled": "#c5161d",
}

_section_title(
    "Progress",
    "Sales and Operation status overview",
    "Hold is counted as active, but separated in the status cards for management review.",
)

st.markdown(
    _html(
        f"""
        <div class='zd-grid-2'>
            {_progress_dashboard_panel(
                'Sales Progress',
                'Pipeline view from open follow-up to final result.',
                metrics.get('sales_progress', {}),
                max(total_sales, 1),
                active_sales,
                sales_colours,
                False,
            )}
            {_progress_dashboard_panel(
                'Operation Progress',
                'Order execution view from open order to paid closure.',
                metrics.get('operation_progress', {}),
                max(total_operations, 1),
                active_operations,
                operation_colours,
                True,
            )}
        </div>
        """
    ),
    unsafe_allow_html=True,
)

_section_title(
    "Phase",
    "Active item phase breakdown",
    "Only active phases with data are shown. Zero-value phases are hidden to keep the dashboard compact.",
)

st.markdown(
    _phase_panel(metrics.get("sales_phase_active", {}), metrics.get("operation_phase_active", {})),
    unsafe_allow_html=True,
)

_section_title(
    "Risk",
    "Attention summary",
    "These are the records that need management visibility or follow-up focus.",
)

st.markdown(_attention_grid(metrics.get("attention_summary", {})), unsafe_allow_html=True)

_section_title(
    "Review",
    "Compact attention review table",
    "Table rows come from the Attention Summary statuses. It is designed for weekly review and quick owner follow-up.",
)


show_review_table = st.toggle(
    "Show compact table review",
    value=True,
    key="dashboard_show_compact_attention_table",
)

if show_review_table:
    _render_attention_table(metrics.get("attention_review_rows", []))
