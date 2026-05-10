from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

from core.auth import require_login
from services.ai_quotation_review_service import generate_ai_quotation_review
from services.ai_rfq_review_service import generate_ai_rfq_review
from services.upgrade_service import list_module_records
from ui.ai_review_ui import render_ai_review
from ui.index_center_view import render_market_index_reference
from ui.theme import apply_theme, render_page_header

apply_theme()
current_user = require_login()

render_page_header("RFQ Board", "RFQ working file, requirement control, supplier quotes, price comparison, market index and client quotation.")


def _df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows or [])


def _export_button(rows: list[dict[str, Any]], file_name: str, label: str) -> None:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        _df(rows).to_excel(writer, sheet_name="Records", index=False)
    st.download_button(label, output.getvalue(), file_name=file_name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)


rfq_records = list_module_records("RFQ Requirement Control", limit=1000)
supplier_quotes = list_module_records("Supplier Price Comparison", limit=2000)
client_headers = list_module_records("Client Quotation Header", limit=1000)
client_lines = list_module_records("Client Quotation Lines", limit=2000)

m1, m2, m3, m4 = st.columns(4)
m1.metric("RFQ Records", len(rfq_records))
m2.metric("Supplier Quotes", len(supplier_quotes))
m3.metric("Client Quote Versions", len(client_headers))
m4.metric("Open RFQ", sum(1 for r in rfq_records if str(r.get("rfq_gate_status") or "").lower() not in {"closed", "lost"}))

tabs = st.tabs([
    "RFQ Overview",
    "RFQ Working File",
    "Requirement Checklist",
    "Supplier Sourcing",
    "Supplier Quotes",
    "Price Comparison",
    "Market Index",
    "Client Quotation",
    "Risk Review",
    "Action Log",
    "RFQ History",
])

with tabs[0]:
    st.markdown("### RFQ Overview")
    if not rfq_records:
        st.info("No RFQ Requirement Control records yet. Download the RFQ template, complete it, and import it through Import Center.")
    else:
        df = _df(rfq_records)
        cols = [c for c in ["rfq_id", "project_id", "customer", "product_description", "rfq_gate_status", "risk_level", "current_owner", "next_step", "due_date", "last_updated_at"] if c in df.columns]
        st.dataframe(df[cols], width="stretch", hide_index=True)
        _export_button(rfq_records, "rfq_requirement_control_records.xlsx", "Export RFQ records")

with tabs[1]:
    st.markdown("### RFQ Working File")
    st.caption("The existing RFQ working file remains the free-form project summary and file-link interface. The system stores key links for traceability.")
    df = _df(rfq_records)
    if df.empty:
        st.info("No RFQ working file links imported yet.")
    else:
        cols = [c for c in ["rfq_id", "project_id", "rfq_working_file_link", "customer_original_request_link", "sourcing_link", "sampling_link", "design_file_link", "quotation_to_client_link", "original_requirement_notes"] if c in df.columns]
        st.dataframe(df[cols], width="stretch", hide_index=True)

with tabs[2]:
    st.markdown("### Requirement Checklist")
    df = _df(rfq_records)
    if df.empty:
        st.info("No requirement checklist records imported yet.")
    else:
        cols = [c for c in ["rfq_id", "drawing_received", "specification_received", "quantity_confirmed", "packaging_requirement", "testing_requirement", "compliance_requirement", "sample_required", "inspection_required", "missing_information"] if c in df.columns]
        st.dataframe(df[cols], width="stretch", hide_index=True)

        with st.expander("AI RFQ Completeness Check", expanded=False):
            st.caption("Read-only RFQ requirement review. AI does not change RFQ status, risk level, or final decision fields.")
            rfq_options = ["All RFQ records"] + sorted([str(x) for x in df.get("rfq_id", pd.Series(dtype=str)).dropna().astype(str).unique() if str(x).strip()])
            selected_rfq_for_ai = st.selectbox("RFQ scope", rfq_options, key="ai_rfq_review_scope")
            if st.button("AI RFQ Completeness Check", use_container_width=True, disabled=not rfq_records):
                with st.spinner("Reviewing RFQ completeness from current system records..."):
                    st.session_state["ai_rfq_review"] = generate_ai_rfq_review(
                        rfq_records,
                        supplier_quotes,
                        rfq_id=None if selected_rfq_for_ai == "All RFQ records" else selected_rfq_for_ai,
                    )
            if st.session_state.get("ai_rfq_review"):
                render_ai_review(st.session_state["ai_rfq_review"], title="AI RFQ Completeness Check", export_file_prefix="ai_rfq_completeness_check")

with tabs[3]:
    st.markdown("### Supplier Sourcing")
    st.caption("Supplier sourcing uses Supplier Board data and supplier quotation records linked by Project ID / RFQ Item Ref.")
    if not supplier_quotes:
        st.info("No supplier quote records found yet.")
    else:
        df = _df(supplier_quotes)
        cols = [c for c in ["project_id", "rfq_item_ref", "supplier_code", "supplier_name", "quote_date", "lead_time", "quotation_risk", "comparison_status", "remarks"] if c in df.columns]
        st.dataframe(df[cols], width="stretch", hide_index=True)

with tabs[4]:
    st.markdown("### Supplier Quotes")
    if not supplier_quotes:
        st.info("No supplier quotes imported yet.")
    else:
        df = _df(supplier_quotes)
        cols = [c for c in ["supplier_quote_id", "project_id", "rfq_item_ref", "item_option", "supplier_code", "supplier_name", "supplier_unit_cost", "currency", "moq", "lead_time", "quote_date", "selected_supplier", "recommended_supplier"] if c in df.columns]
        st.dataframe(df[cols], width="stretch", hide_index=True)
        _export_button(supplier_quotes, "supplier_quotes_for_rfq.xlsx", "Export supplier quotes")

with tabs[5]:
    st.markdown("### Price Comparison")
    st.caption("This tab shows supplier-side quotation data in the RFQ flow. It uses the same Supplier Price Comparison records as the old module.")
    if not supplier_quotes:
        st.info("No price comparison records found yet.")
    else:
        df = _df(supplier_quotes)
        cols = [c for c in ["project_id", "rfq_item_ref", "item_option", "supplier_code", "supplier_name", "supplier_unit_cost", "currency", "sample_cost", "tooling_cost", "packing_cost", "lead_time", "selected_supplier", "recommended_supplier", "quotation_risk"] if c in df.columns]
        st.dataframe(df[cols], width="stretch", hide_index=True)

        with st.expander("AI Quotation Review", expanded=False):
            st.caption("Read-only decision support. AI does not select suppliers or generate final customer quotation.")
            project_options = ["All projects"] + sorted([str(x) for x in df.get("project_id", pd.Series(dtype=str)).dropna().astype(str).unique() if str(x).strip()])
            selected_project_for_quote_ai = st.selectbox("Project scope", project_options, key="ai_quote_project_scope")
            scoped_df = df if selected_project_for_quote_ai == "All projects" or "project_id" not in df.columns else df[df["project_id"].astype(str) == selected_project_for_quote_ai]
            rfq_item_options = ["All items"] + sorted([str(x) for x in scoped_df.get("rfq_item_ref", pd.Series(dtype=str)).dropna().astype(str).unique() if str(x).strip()])
            selected_item_for_quote_ai = st.selectbox("RFQ item scope", rfq_item_options, key="ai_quote_item_scope")
            if st.button("AI Quotation Review", use_container_width=True, disabled=not supplier_quotes):
                with st.spinner("Reviewing quotation completeness and commercial risks..."):
                    st.session_state["ai_quotation_review"] = generate_ai_quotation_review(
                        supplier_quotes,
                        client_headers,
                        client_lines,
                        project_id=None if selected_project_for_quote_ai == "All projects" else selected_project_for_quote_ai,
                        rfq_item_ref=None if selected_item_for_quote_ai == "All items" else selected_item_for_quote_ai,
                    )
            if st.session_state.get("ai_quotation_review"):
                render_ai_review(st.session_state["ai_quotation_review"], title="AI Quotation Review", export_file_prefix="ai_quotation_review")

with tabs[6]:
    render_market_index_reference()

with tabs[7]:
    st.markdown("### Client Quotation")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Quotation Headers")
        if client_headers:
            df = _df(client_headers)
            cols = [c for c in ["client_quote_id", "project_id", "quote_version", "quote_date", "client_code", "quote_status", "quote_currency", "price_term"] if c in df.columns]
            st.dataframe(df[cols], width="stretch", hide_index=True)
        else:
            st.info("No client quotation headers yet.")
    with c2:
        st.markdown("#### Quotation Lines")
        if client_lines:
            df = _df(client_lines)
            cols = [c for c in ["client_quote_id", "project_id", "rfq_item_ref", "client_unit_price", "supplier_unit_cost", "quantity_basis", "estimated_gp", "estimated_gp_percent"] if c in df.columns]
            st.dataframe(df[cols], width="stretch", hide_index=True)
        else:
            st.info("No client quotation lines yet.")

with tabs[8]:
    st.markdown("### Risk Review")
    df = _df(rfq_records)
    if df.empty:
        st.info("No RFQ risk review records imported yet.")
    else:
        cols = [c for c in ["rfq_id", "quality_compliance_risk", "commercial_business_risk", "harley_review_status", "maria_review_status", "ehab_final_decision", "risk_level", "rfq_gate_status"] if c in df.columns]
        st.dataframe(df[cols], width="stretch", hide_index=True)

with tabs[9]:
    st.markdown("### Action Log")
    df = _df(rfq_records)
    if df.empty:
        st.info("No RFQ actions imported yet.")
    else:
        cols = [c for c in ["rfq_id", "current_owner", "next_step", "due_date", "missing_information", "rfq_gate_status", "last_updated_by", "last_updated_at"] if c in df.columns]
        st.dataframe(df[cols], width="stretch", hide_index=True)

with tabs[10]:
    st.markdown("### RFQ History")
    df = _df(rfq_records)
    if df.empty:
        st.info("No RFQ history yet.")
    else:
        cols = [c for c in ["rfq_id", "process_code", "process_version", "source_file", "created_at", "created_by", "last_updated_at", "last_updated_by"] if c in df.columns]
        st.dataframe(df[cols], width="stretch", hide_index=True)
