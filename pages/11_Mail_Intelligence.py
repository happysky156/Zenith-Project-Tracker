from __future__ import annotations

import pandas as pd
import streamlit as st

from core.auth import require_login
from ui.theme import apply_theme, render_page_header

apply_theme()
require_login()
render_page_header("Mail Intelligence", "Mail overview, action tracker and attachment intelligence from the mail tracker Excel output.")

uploaded = st.file_uploader("Upload mail_tracker_clean.xlsx", type=["xlsx", "xls"], help="This first version previews mail intelligence only. It does not write to the project database.")
if not uploaded:
    st.info("Upload the mail tracker clean workbook to preview Mail Overview, Action Tracker and Attachment Summary.")
    st.stop()

try:
    workbook = pd.read_excel(uploaded, sheet_name=None)
except Exception as exc:
    st.error(f"Could not read workbook: {type(exc).__name__}: {exc}")
    st.stop()

sheet_names = list(workbook.keys())
tabs = st.tabs(sheet_names)
for tab, sheet_name in zip(tabs, sheet_names):
    with tab:
        df = workbook[sheet_name]
        st.markdown(f"### {sheet_name}")
        st.metric("Rows", len(df))
        if df.empty:
            st.info("This sheet is empty.")
        else:
            st.dataframe(df, width="stretch", hide_index=True)
            st.download_button(
                f"Export {sheet_name}",
                data=df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"{sheet_name.lower().replace(' ', '_')}.csv",
                mime="text/csv",
            )
