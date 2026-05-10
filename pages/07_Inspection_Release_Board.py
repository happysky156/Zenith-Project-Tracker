from __future__ import annotations

import pandas as pd
import streamlit as st

from core.auth import require_login
from services.upgrade_service import list_module_records
from services.export_service import render_standard_export_panel
from ui.theme import apply_theme, render_page_header

apply_theme()
require_login()
render_page_header("Inspection & Release Board", "Inspection requirements, COA/COC document status, inspection result and shipment release control.")

order_details = list_module_records("Order Details", limit=2000)

def _df(rows):
    return pd.DataFrame(rows or [])

m1, m2, m3 = st.columns(3)
m1.metric("Order Detail Lines", len(order_details))
m2.metric("With Shipment Date", sum(1 for r in order_details if r.get("shipment_date")))
m3.metric("With Target Delivery", sum(1 for r in order_details if r.get("target_delivery_date")))

render_standard_export_panel(
    board_name="Inspection & Release Board",
    current_rows=order_details,
    filtered_rows=order_details,
    template_names=["Order Details Template", "QP-04 Inspection & Shipment Release Template"],
    key_prefix="inspection_release_board",
)

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Inspection Required", "Shipment Release", "History"])
with tab1:
    st.markdown("### Inspection Overview")
    if not order_details:
        st.info("No order detail records found yet.")
    else:
        df = _df(order_details)
        cols = [c for c in ["project_id", "order_no", "client_code", "supplier_code", "item_code", "item_description", "target_delivery_date", "actual_delivery_date", "shipment_date", "remarks"] if c in df.columns]
        st.dataframe(df[cols], width="stretch", hide_index=True)
with tab2:
    st.markdown("### Inspection Required")
    st.info("Dedicated inspection extension records will be added in the Inspection & Shipment Release phase. Current view maps existing Order Details only.")
with tab3:
    st.markdown("### Shipment Release")
    if order_details:
        df = _df(order_details)
        cols = [c for c in ["project_id", "order_no", "target_delivery_date", "actual_delivery_date", "shipment_date", "shipping_status", "remarks"] if c in df.columns]
        st.dataframe(df[cols], width="stretch", hide_index=True)
with tab4:
    st.markdown("### Inspection History")
    st.info("History will be built from inspection records, order details, meeting records and mail intelligence.")
