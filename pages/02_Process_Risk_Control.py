from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

from core.auth import require_login
from database.repositories import list_operation_orders, list_sales_projects
from services.process_management_service import (
    PROCESS_ORDER,
    available_quality_process_template_names,
    build_history_document_excel,
    build_process_document_excel,
    build_quality_process_template,
    get_control_points,
    get_process_definition,
    list_process_definitions,
    process_document_file_name,
    quality_process_template_name,
    quality_template_file_name,
)
from services.upgrade_service import list_module_records, list_order_module_records_by_archive_view
from ui.theme import apply_theme, render_page_header

apply_theme()
current_user = require_login()
operator = current_user.get("display_name", "")

render_page_header(
    "Business Process & Risk Control Center",
    "A control tower for business processes, risk points, owners, records and version history.",
)



def _excel_bytes_from_rows(rows: list[dict[str, Any]], sheet_name: str = "Records") -> BytesIO:
    output = BytesIO()
    df = pd.DataFrame(rows)
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    output.seek(0)
    return output


def _safe_records(process_code: str, limit: int = 300) -> tuple[list[dict[str, Any]], str]:
    try:
        if process_code == "QP-01":
            rows = list_module_records("RFQ Requirement Control", limit=limit)
            if not rows:
                rows = list_sales_projects(include_archived=False)[:limit]
                return rows, "No imported RFQ Control records yet. Showing active Sales Board projects as RFQ-stage reference data."
            return rows, "RFQ Requirement Control extension records imported from RFQ templates."
        if process_code == "QP-02":
            rows = list_module_records("Sample Tracking", limit=limit)
            return rows, "Sample Tracking records."
        if process_code == "QP-03":
            rows = list_order_module_records_by_archive_view("Order Details", limit=limit, archive_view="Active only")
            if not rows:
                rows = list_operation_orders(include_archived=False)[:limit]
                return rows, "Operation Board active order records used because Order Details has no rows."
            return rows, "Order Details active rows mapped for order setup control."
        if process_code == "QP-04":
            rows = list_order_module_records_by_archive_view("Order Details", limit=limit, archive_view="Active only")
            return rows, "Order Details active rows mapped for inspection and shipment release control."
        if process_code == "QP-05":
            return [], "No dedicated Complaint / CAPA extension exists yet. The current view shows process structure only."
        if process_code == "SV-01":
            rows = list_module_records("Supplier Details", limit=limit)
            return rows, "Supplier Details records mapped as Supplier Management source data."
    except Exception as exc:
        return [], f"Could not load mapped source records: {exc}"
    return [], "No mapped records."


def _select_preview_columns(process_code: str, rows: list[dict[str, Any]]) -> list[str]:
    preferred = {
        "QP-01": ["rfq_id", "project_id", "customer", "product_description", "rfq_gate_status", "risk_level", "current_owner", "next_step", "due_date"],
        "QP-02": ["sample_id", "project_id", "rfq_item_ref", "supplier_name", "sample_type", "sample_status", "target_sample_date", "test_status", "next_step_owner"],
        "QP-03": ["order_no", "project_id", "order_item_code", "supplier_name", "order_qty", "target_delivery_date", "shipment_status", "archive_status"],
        "QP-04": ["order_no", "project_id", "supplier_name", "target_delivery_date", "inspection_status", "packing_status", "shipment_status", "shipment_date", "archive_status"],
        "SV-01": ["supplier_code", "supplier_name", "company_type", "main_products", "quality_risk", "commercial_risk", "active_status", "order_count", "risk_summary"],
    }
    existing = set(rows[0].keys()) if rows else set()
    cols = [c for c in preferred.get(process_code, []) if c in existing]
    if cols:
        return cols
    return list(rows[0].keys())[:10] if rows else []


def _render_version_card(definition: dict[str, Any]) -> None:
    st.markdown("### Process Version")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Version", definition["version"])
    c2.metric("Status", definition["status"])
    c3.metric("Owner", definition["owner"])
    c4.metric("Effective", definition["effective_date"])
    st.caption(
        f"Quality / Compliance: {definition.get('quality_owner', '-')} · "
        f"Business: {definition.get('business_owner', '-')} · "
        f"Final approval: {definition.get('final_approver', '-')}"
    )


def _render_summary(definition: dict[str, Any]) -> None:
    st.markdown("### Process Summary")
    summary_df = pd.DataFrame(
        [
            {"Item": "Purpose", "Content": definition["purpose"]},
            {"Item": "Scope", "Content": definition["scope"]},
            {"Item": "Trigger", "Content": definition["trigger"]},
            {"Item": "Existing data sources", "Content": definition["existing_sources"]},
            {"Item": "Future extension", "Content": definition["extension_needed"]},
        ]
    )
    st.dataframe(summary_df, use_container_width=True, hide_index=True)


def _render_control_points(process_code: str) -> None:
    st.markdown("### Control Points")
    points = get_control_points(process_code)
    st.dataframe(pd.DataFrame(points), use_container_width=True, hide_index=True)


def _render_rfq_positioning() -> None:
    st.markdown("### RFQ Working File + RFQ Control Layer")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown(
            """
            <div style="border:1px solid #E5E7EB; border-radius:14px; padding:14px; background:#FAFAFA; min-height:155px;">
              <div style="font-weight:700; color:#111827; margin-bottom:6px;">Old flow: RFQ Working File</div>
              <div style="color:#4B5563; font-size:0.92rem;">Used for free notes, customer original requirements, pictures, and WeCom file links such as sourcing, sampling, design file and quotation to client.</div>
              <div style="margin-top:10px; color:#047857; font-weight:600;">Keep this strength. Do not force the team to abandon the familiar document.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div style="border:1px solid #E5E7EB; border-radius:14px; padding:14px; background:#F8FAFC; min-height:155px;">
              <div style="font-weight:700; color:#111827; margin-bottom:6px;">New flow: RFQ Control Layer</div>
              <div style="color:#4B5563; font-size:0.92rem;">Adds RFQ status, missing information, risk level, owner, next step, due date, requirement checklist and risk review for system tracking.</div>
              <div style="margin-top:10px; color:#B45309; font-weight:600;">Use it to control risk and create system records.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    upgrade_rows = [
        {
            "Old RFQ Working File strength": "Project file link hub",
            "How it is kept": "Template keeps sourcing / sampling / design / quotation links",
            "New control added": "Each link has mapped field, owner, last checked date and remarks",
        },
        {
            "Old RFQ Working File strength": "Free notes and customer original requirements",
            "How it is kept": "Original Requirement Notes section remains flexible",
            "New control added": "Requirement Checklist converts key items into trackable fields",
        },
        {
            "Old RFQ Working File strength": "Task area",
            "How it is kept": "Task section remains familiar",
            "New control added": "Action Log adds owner, due date, status and result link",
        },
        {
            "Old RFQ Working File strength": "Easy for team meeting",
            "How it is kept": "Excel is still the working file",
            "New control added": "System records RFQ status, risk level and next step after Harley updates/imports",
        },
    ]
    st.dataframe(pd.DataFrame(upgrade_rows), use_container_width=True, hide_index=True)


def _render_quick_actions(process_code: str, rows: list[dict[str, Any]]) -> None:
    definition = get_process_definition(process_code)
    st.markdown("### Quick Actions")
    st.caption("Download the current process document, standard Excel template, or current related records.")

    process_doc = build_process_document_excel(process_code).getvalue()
    st.download_button(
        "Export process document",
        data=process_doc,
        file_name=process_document_file_name(process_code),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key=f"{process_code}_process_doc",
    )

    template_name = quality_process_template_name(process_code)
    template_bytes = build_quality_process_template(template_name).getvalue()
    st.download_button(
        "Download process template",
        data=template_bytes,
        file_name=quality_template_file_name(template_name),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key=f"{process_code}_template",
    )

    export_rows = rows if rows else [
        {
            "process_code": process_code,
            "process_name": definition["process_name"],
            "note": "No mapped business records available for this view yet.",
        }
    ]
    record_bytes = _excel_bytes_from_rows(export_rows, sheet_name="Mapped Records").getvalue()
    st.download_button(
        "Export current view records",
        data=record_bytes,
        file_name=f"{process_code.lower()}_mapped_records.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key=f"{process_code}_records",
    )

    st.info(
        "Input and import are controlled through Import Center or each board page. This center focuses on process visibility and exports."
    )


def _render_records_view(process_code: str) -> None:
    st.markdown("### Process Records View")
    rows, source_note = _safe_records(process_code)
    st.caption(source_note)
    if not rows:
        st.warning("No mapped records are available for this process yet.")
        return rows
    cols = _select_preview_columns(process_code, rows)
    df = pd.DataFrame(rows)
    if cols:
        st.dataframe(df[cols], use_container_width=True, hide_index=True)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
    return rows


def _render_process_tab(process_code: str) -> None:
    definition = get_process_definition(process_code)
    st.subheader(f"{process_code} · {definition['short_name']}")
    left, right = st.columns([3, 1], gap="large")
    with left:
        _render_version_card(definition)
        _render_summary(definition)
        if process_code == "QP-01":
            _render_rfq_positioning()
        _render_control_points(process_code)
        rows = _render_records_view(process_code)
    with right:
        _render_quick_actions(process_code, rows)


def _render_overview() -> None:
    st.subheader("Overview")
    st.write(
        "This page creates a single process-and-risk control center for five formal control processes and one supplier management view. "
        "It is designed for a small trading company: simple controls, clear owners, RFQ import support, template downloads and mapped records from existing modules."
    )
    overview_df = pd.DataFrame(list_process_definitions())[
        ["process_code", "short_name", "process_type", "version", "status", "owner", "existing_sources", "extension_needed"]
    ]
    st.dataframe(overview_df, use_container_width=True, hide_index=True)

    st.markdown("### Current boundary")
    st.success("QP-01 RFQ Requirement Control is connected for import and display. Other processes currently show mapped records or process structure. Core Sales / Operation business logic is unchanged.")
    st.markdown(
        "- Template downloads are generated from central definitions.\n"
        "- QP-01 RFQ records can be imported by Harley through Import Center and displayed in QP-01.\n"
        "- Other process records are mapped from existing modules where possible.\n"
        "- AI-assisted summaries and impact assessments should only run after a user clicks a generation button and confirms the output."
    )

    st.markdown("### Download all quality process templates")
    names = available_quality_process_template_names()
    cols = st.columns(3)
    for idx, name in enumerate(names):
        with cols[idx % 3]:
            st.download_button(
                f"Download {name}",
                data=build_quality_process_template(name).getvalue(),
                file_name=quality_template_file_name(name),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key=f"overview_template_{idx}_{name}",
            )


def _render_history() -> None:
    st.subheader("History")
    st.write(
        "History is designed as the unified place for active versions, archived versions, change log, approvals, "
        "timestamps, rejection comments and change impact assessment."
    )
    active_df = pd.DataFrame(list_process_definitions())[
        ["process_code", "short_name", "version", "status", "owner", "quality_owner", "business_owner", "final_approver", "effective_date"]
    ]
    st.markdown("### Active Process Versions")
    st.dataframe(active_df, use_container_width=True, hide_index=True)

    st.markdown("### Recommended History Enhancements")
    enhancements = pd.DataFrame(
        [
            {
                "Area": "AI-assisted summary",
                "Recommendation": "Trigger only when Harley clicks a Generate Summary button. Do not call AI automatically on every change.",
                "Next step": "Planned",
            },
            {
                "Area": "Change impact assessment",
                "Recommendation": "Add change_impact_assessment field. AI can assist only after button click; Harley must review and confirm.",
                "Next step": "Planned",
            },
            {
                "Area": "Approval workflow",
                "Recommendation": "Add approval timestamps and rejection comments for Harley, Maria and Ehab.",
                "Next step": "Planned",
            },
            {
                "Area": "Effective date",
                "Recommendation": "Default to change date, but allow Harley to set a future effective date for announced process changes.",
                "Next step": "Planned",
            },
        ]
    )
    st.dataframe(enhancements, use_container_width=True, hide_index=True)

    st.download_button(
        "Export history design document",
        data=build_history_document_excel().getvalue(),
        file_name="quality_process_history_design.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    template_name = "Process History Template"
    st.download_button(
        "Download Process History Template",
        data=build_quality_process_template(template_name).getvalue(),
        file_name=quality_template_file_name(template_name),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


tabs = st.tabs(
    [
        "Overview",
        "QP-01 RFQ",
        "QP-02 Sample",
        "QP-03 Order Setup",
        "QP-04 Inspection & Shipment",
        "QP-05 Complaint Closure",
        "SV-01 Supplier Management",
        "History",
    ]
)

with tabs[0]:
    _render_overview()
for idx, process_code in enumerate(PROCESS_ORDER, start=1):
    with tabs[idx]:
        _render_process_tab(process_code)
with tabs[-1]:
    _render_history()
