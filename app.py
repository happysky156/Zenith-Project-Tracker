from __future__ import annotations

import streamlit as st

from database.connection import get_database_backend, get_database_display_name
from database.schema import init_db
from core.state import init_session_state
from services.project_service import get_dashboard_metrics
from ui.theme import apply_theme, render_page_header
from utils.logger import get_logger, get_log_file_path

st.set_page_config(
    page_title="Zenith Project Tracker",
    page_icon="📌",
    layout="wide",
)

init_db()
init_session_state()
apply_theme()

logger = get_logger("app")
logger.info("Zenith Project Tracker started.")

render_page_header(
    "Zenith Project Tracker",
    "Internal workspace to keep Sales projects, Operation orders and Weekly Meeting control linked in one place.",
)

metrics = get_dashboard_metrics()
col1, col2, col3, col4 = st.columns(4)
col1.metric("Active Sales", metrics["active_sales"], help="Sales items that are not closed or done.")
col2.metric("Active Orders", metrics["active_operations"], help="Operation orders that are not closed or done.")
col3.metric("Meeting Pool", metrics["meeting_pool"])
col4.metric("Need Decision", metrics["need_decision"])

st.caption(
    f"Total master records — Sales: {metrics['sales_projects']} | Operation: {metrics['operation_orders']} | All items: {metrics['all_items']}"
)

st.markdown(
    "<div class='zt-panel'>Use the sidebar pages to start with Import Center. Sales is keyed by <b>Project ID</b>; Operation is keyed by <b>Order No</b>; both are linked through <b>Project ID</b>; status and history are kept inside the system instead of Excel. Active counts on top exclude already closed / done items, so they are better for daily follow-up.</div>",
    unsafe_allow_html=True,
)

with st.expander(f"Current database target ({get_database_backend()})"):
    st.code(str(get_database_display_name()))

with st.expander("Current log file"):
    st.code(str(get_log_file_path()))

st.markdown(
    """
### What is already live
- Split import flow for Sales and Operation
- Automatic Sales ↔ Operation linking by Project ID
- High-frequency action buttons on both boards
- One shared Detail page for Sales Project / Operation Order
- Weekly Meeting actions and weekly snapshots
- PostgreSQL-ready database connection for multi-location use
- Quick meeting note support during live meetings

### Current visual update
- Zenith red + black theme
- Unified page header with logo support
- Cleaner board cards and meeting layout
- Better visual emphasis for risk states
- Active counts on dashboard for daily management
"""
)
