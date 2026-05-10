from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from core.auth import require_login
from services.upgrade_service import list_module_records
from services.export_service import render_standard_export_panel
from ui.index_center_view import render_market_index_reference
from ui.theme import apply_theme, render_page_header

apply_theme()
current_user = require_login()

render_page_header("RFQ Board", "RFQ working file, requirement control, supplier quotes, price comparison, market index and client quotation.")


def _df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows or [])



rfq_records = list_module_records("RFQ Requirement Control", limit=1000)
supplier_quotes = list_module_records("Supplier Price Comparison", limit=2000)
client_headers = list_module_records("Client Quotation Header", limit=1000)
client_lines = list_module_records("Client Quotation Lines", limit=2000)

m1, m2, m3, m4 = st.columns(4)
m1.metric("RFQ Records", len(rfq_records))
m2.metric("Supplier Quotes", len(supplier_quotes))
m3.metric("Client Quote Versions", len(client_headers))
m4.metric("Open RFQ", sum(1 for r in rfq_records if str(r.get("rfq_gate_status") or "").lower() not in {"closed", "lost"}))

render_standard_export_panel(
    board_name="RFQ Board",
    current_rows=rfq_records,
    filtered_rows=rfq_records,
    template_names=["QP-01 RFQ Requirement Control Template", "Price Comparison Template"],
    key_prefix="rfq_board",
)

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

with tabs[5]:
    st.markdown("### Price Comparison")
    st.caption("This tab shows supplier-side quotation data in the RFQ flow. It uses the same Supplier Price Comparison records as the old module.")
    if not supplier_quotes:
        st.info("No price comparison records found yet.")
    else:
        df = _df(supplier_quotes)
        cols = [c for c in ["project_id", "rfq_item_ref", "item_option", "supplier_code", "supplier_name", "supplier_unit_cost", "currency", "sample_cost", "tooling_cost", "packing_cost", "lead_time", "selected_supplier", "recommended_supplier", "quotation_risk"] if c in df.columns]
        st.dataframe(df[cols], width="stretch", hide_index=True)

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
