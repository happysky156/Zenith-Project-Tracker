from __future__ import annotations

import streamlit as st

from core.auth import require_login
from services.upgrade_service import list_module_records, upsert_module_record
from services.market_index_service import latest_daily_indices, lock_client_quotation_index_snapshots, list_index_alert_events
from ui.theme import apply_theme, render_page_header
from ui.upgrade_ui import render_upgrade_css, render_upgrade_intro, render_metric_grid, render_layered_records, render_simple_filter_bar

apply_theme()
render_upgrade_css()
current_user = require_login()
operator = current_user["display_name"]
render_page_header("Client Quotation", "Client quotation versions, quotation lines and locked index snapshots.")
render_upgrade_intro(
    "Client Quotation",
    "Each Project ID gets automatic V1 / V2 / V3 quotation versions when Quote Version is blank. Sent quotes should be treated as locked; create a new version for revision.",
)

headers = list_module_records("Client Quotation Header", limit=1000)
lines = list_module_records("Client Quotation Lines", limit=1000)
snapshots = list_module_records("Index Snapshot", limit=1000)
render_metric_grid({"Quotation Versions": len(headers), "Quotation Lines": len(lines), "Locked Snapshots": len(snapshots), "Accepted": sum(1 for r in headers if str(r.get('quote_status') or '').lower() == 'accepted')})

with st.expander("Create client quotation header", expanded=False):
    with st.form("client_quote_header_form"):
        c1, c2, c3 = st.columns(3)
        project_id = c1.text_input("Project ID")
        quote_date = c2.date_input("Quote Date", value=None)
        quote_version = c3.text_input("Quote Version", placeholder="Leave blank for auto V1/V2/V3")
        c1, c2, c3 = st.columns(3)
        client_code = c1.text_input("Client Code")
        client_name = c2.text_input("Client Name")
        quote_status = c3.selectbox("Quote Status", ["Draft", "Sent", "Revised", "Accepted", "Lost"])
        c1, c2 = st.columns(2)
        price_term = c1.text_input("Price Term")
        quote_currency = c2.text_input("Quote Currency", value="USD")
        remarks = st.text_area("Remarks", height=80)
        submitted = st.form_submit_button("Save Client Quotation Header", type="primary")
        if submitted:
            if not project_id.strip():
                st.error("Project ID is required.")
            else:
                upsert_module_record(
                    "Client Quotation Header",
                    {
                        "project_id": project_id,
                        "quote_version": quote_version,
                        "quote_date": quote_date.isoformat() if quote_date else None,
                        "client_code": client_code,
                        "client_name": client_name,
                        "quote_status": quote_status,
                        "price_term": price_term,
                        "quote_currency": quote_currency,
                        "remarks": remarks,
                    },
                    operator=operator,
                )
                st.success("Client quotation header saved.")
                st.rerun()

with st.expander("Lock quotation index snapshot", expanded=False):
    st.caption("Lock current index values for a client quotation. Locked snapshots are historical quotation evidence and will not change when Daily Market Indices update later.")
    if not headers:
        st.info("Create a client quotation header before locking index snapshots.")
    else:
        header_labels = []
        for h in headers:
            header_labels.append(f"{h.get('client_quote_id')} | {h.get('project_id')} | {h.get('quote_version') or '-'} | {h.get('quote_date') or '-'}")
        header_lookup = dict(zip(header_labels, headers))
        latest_indices = latest_daily_indices()
        if not latest_indices:
            st.info("No latest index values found. Please run Index Center daily fetch or add manual index values first.")
        else:
            with st.form("lock_index_snapshot_form"):
                selected_header_label = st.selectbox("Client Quotation", header_labels)
                selected_header = header_lookup[selected_header_label]
                line_refs = sorted({str(r.get('rfq_item_ref') or '').strip() for r in lines if str(r.get('client_quote_id') or '') == str(selected_header.get('client_quote_id') or '') and str(r.get('rfq_item_ref') or '').strip()})
                rfq_item_ref = st.selectbox("RFQ Item Ref (optional)", [""] + line_refs)
                idx_labels = [f"{r.get('display_name') or r.get('index_code')} [{r.get('index_code')}] = {r.get('value')} {r.get('unit') or ''} ({r.get('fetch_status') or '-'})" for r in latest_indices]
                idx_lookup = dict(zip(idx_labels, latest_indices))
                default_labels = [label for label in idx_labels if any(code in label for code in ["USD_CNY", "FREIGHT_ISRAEL", "FREIGHT_MOROCCO"])]
                selected_indices = st.multiselect("Index values to lock", idx_labels, default=default_labels[:1], help="Select FX / material / freight indices used as quotation basis.")
                submitted_snapshot = st.form_submit_button("Lock Index Snapshot", type="primary")
                if submitted_snapshot:
                    try:
                        selected_codes = [idx_lookup[label].get('index_code') for label in selected_indices]
                        summary = lock_client_quotation_index_snapshots(
                            selected_header,
                            selected_codes,
                            operator=operator,
                            rfq_item_ref=rfq_item_ref or None,
                        )
                        st.success(
                            "Index snapshot lock completed. "
                            f"Created: {summary.get('created', 0)} | "
                            f"Skipped Existing: {summary.get('skipped_existing', 0)} | "
                            f"Missing Latest: {summary.get('missing_latest', 0)}"
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Lock snapshot failed: {type(exc).__name__}: {exc}")

with st.expander("Quotation index alerts", expanded=False):
    try:
        quotation_alerts = [r for r in list_index_alert_events(limit=1000) if r.get('related_client_quote_id')]
    except Exception as exc:
        quotation_alerts = []
        st.warning(f"Quotation alerts are temporarily unavailable: {type(exc).__name__}: {exc}")
    if not quotation_alerts:
        st.info("No quotation snapshot alert events found.")
    else:
        import pandas as pd
        alert_df = pd.DataFrame(quotation_alerts)
        alert_cols = ["alert_date", "alert_type", "index_code", "index_name", "alert_level", "reference_value", "latest_value", "change_percent", "related_project_id", "related_client_quote_id", "related_quote_version", "alert_status", "source_note"]
        alert_cols = [c for c in alert_cols if c in alert_df.columns]
        st.dataframe(alert_df[alert_cols], width="stretch", hide_index=True)

view = st.radio("View", ["Headers", "Lines", "Index Snapshots"], horizontal=True)
if view == "Headers":
    filtered = render_simple_filter_bar("Client Quotation Header", headers)
    render_layered_records("Client Quotation Header", filtered, key_prefix="client_header_page", summary_field="quote_status", preview_columns=["client_quote_id", "project_id", "quote_version", "quote_date", "client_code", "quote_status", "price_term", "quote_currency"])
elif view == "Lines":
    filtered = render_simple_filter_bar("Client Quotation Lines", lines)
    render_layered_records("Client Quotation Lines", filtered, key_prefix="client_line_page", preview_columns=["client_quote_id", "project_id", "rfq_item_ref", "client_unit_price", "supplier_unit_cost", "quantity_basis", "estimated_gp", "estimated_gp_percent"])
else:
    filtered = render_simple_filter_bar("Index Snapshot", snapshots)
    render_layered_records("Index Snapshot", filtered, key_prefix="snapshot_page", preview_columns=["project_id", "rfq_item_ref", "quote_version", "snapshot_date", "index_code", "index_display_name", "snapshot_value", "snapshot_unit", "snapshot_source_status", "material_index_name", "material_index_value", "freight_route", "exchange_rate_pair", "exchange_rate_value"])
