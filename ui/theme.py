from __future__ import annotations

from pathlib import Path
import base64

import streamlit as st

_RED = "#C5161D"
_RED_DARK = "#980F15"
_DARK = "#111111"
_MID = "#2C2C2C"
_TEXT_SOFT = "#A9ACB3"
_BG = "#F7F7F8"
_BORDER = "#E6E6E8"
_CARD = "#FFFFFF"
_SOFT_RED = "#FFF2F2"
_SIDEBAR_BG = "#0F1013"
_SIDEBAR_CARD = "rgba(255,255,255,0.05)"
_SIDEBAR_BORDER = "rgba(255,255,255,0.08)"

ICON_MAP = {
    "action": "⚡",
    "blocked": "⛔",
    "calendar": "📅",
    "check": "✓",
    "collapse": "▴",
    "decision": "●",
    "download": "⬇",
    "edit": "✎",
    "focus": "⌖",
    "folder": "▦",
    "hide": "◌",
    "note": "✦",
    "remove": "×",
    "repeat": "↻",
    "save": "⌘",
    "summary": "☰",
    "table": "▤",
    "user": "👤",
    "view": "◈",
    "warning": "!",
}


def icon_label(icon_key: str, text: str) -> str:
    """Return a short text label for Streamlit widgets.

    Icons are intentionally not rendered in the current UI. Use Streamlit's
    help= argument or HTML title attributes for tooltip-style explanations.
    """
    return text


def _assets_root() -> Path:
    return Path(__file__).resolve().parents[1] / "assets"


def get_sidebar_logo_path() -> Path | None:
    path = _assets_root() / "Zenith2.png"
    return path if path.exists() else None


def get_header_logo_path() -> Path | None:
    preferred = _assets_root() / "Zenith.png"
    fallback = _assets_root() / "Zenith2.png"
    if preferred.exists():
        return preferred
    return fallback if fallback.exists() else None


def _logo_base64(path: Path | None) -> str:
    if not path or not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("ascii")


def render_sidebar_branding() -> None:
    logo_path = get_sidebar_logo_path()
    with st.sidebar:
        st.markdown("<div class='zt-sidebar-top-space'></div>", unsafe_allow_html=True)
        if logo_path:
            st.image(str(logo_path), width=118)
        else:
            st.markdown("<div class='zt-sidebar-fallback-logo'>ZENITH</div>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class='zt-sidebar-brand-text'>
                <div class='zt-sidebar-brand-title'>Zenith Tracker</div>
                <div class='zt-sidebar-brand-subtitle'>Client first · Risk control · Overdeliver</div>
            </div>
            <div class='zt-sidebar-nav-label'>Workspace</div>
            """,
            unsafe_allow_html=True,
        )


def apply_theme() -> None:
    render_sidebar_branding()
    css = f"""
    <style>
    .stApp {{
        background: {_BG};
    }}
    [data-testid="stHeader"] {{
        background: transparent !important;
        border-bottom: none !important;
        box-shadow: none !important;
    }}
    [data-testid="stToolbar"] {{
        right: 0.75rem;
        top: 0.5rem;
    }}
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {_SIDEBAR_BG} 0%, #15171c 100%);
        border-right: none !important;
    }}
    [data-testid="stSidebar"] > div:first-child {{
        background: transparent;
    }}
    [data-testid="stSidebarNav"] {{
        padding-top: 0.25rem;
    }}
    [data-testid="stSidebarNav"] ul {{
        gap: 0.28rem;
    }}
    [data-testid="stSidebarNav"] li {{
        margin-bottom: 0.18rem;
    }}
    [data-testid="stSidebarNav"] a {{
        min-height: 2.7rem;
        padding: 0.62rem 0.85rem;
        border-radius: 14px;
        background: transparent;
        border: 1px solid transparent;
        color: #F6F7F9;
        font-weight: 600;
        transition: all 0.18s ease;
    }}
    [data-testid="stSidebarNav"] a:hover {{
        background: {_SIDEBAR_CARD};
        border-color: {_SIDEBAR_BORDER};
        color: #FFFFFF;
    }}
    [data-testid="stSidebarNav"] a[aria-current="page"] {{
        background: linear-gradient(90deg, rgba(197,22,29,0.22) 0%, rgba(197,22,29,0.10) 100%);
        border-color: rgba(197,22,29,0.35);
        color: #FFFFFF;
        box-shadow: inset 3px 0 0 {_RED};
    }}
    [data-testid="stSidebarNav"] a span {{
        color: inherit !important;
    }}
    /* When the app is launched with app.py, Streamlit may show the main page as "app".
       This replaces only the root page label visually, so the sidebar reads Dashboard. */
    [data-testid="stSidebarNav"] a[href="/"] span {{
        font-size: 0 !important;
    }}
    [data-testid="stSidebarNav"] a[href="/"] span::after {{
        content: "Dashboard";
        font-size: 0.95rem !important;
        color: inherit !important;
    }}
    [data-testid="stSidebarNav"] a svg {{
        fill: currentColor;
    }}
    /* Streamlit collapses long multipage menus behind a "View more" button.
       Style that native button so additional extension pages are easy to find. */
    [data-testid="stSidebarNav"] button {{
        width: 100% !important;
        min-height: 2.45rem !important;
        padding: 0.55rem 0.85rem !important;
        margin-top: 0.18rem !important;
        border-radius: 14px !important;
        background: rgba(255,255,255,0.06) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        color: #F6F7F9 !important;
        font-weight: 700 !important;
        text-align: left !important;
    }}
    [data-testid="stSidebarNav"] button:hover {{
        background: rgba(197,22,29,0.18) !important;
        border-color: rgba(197,22,29,0.35) !important;
        color: #FFFFFF !important;
    }}
    [data-testid="stSidebarNav"] button *,
    [data-testid="stSidebarNav"] button span,
    [data-testid="stSidebarNav"] button p {{
        color: #F6F7F9 !important;
        font-weight: 700 !important;
    }}
    .zt-sidebar-top-space {{
        height: 0.35rem;
    }}
    .zt-sidebar-brand-wrap {{
        padding: 0.45rem 0.35rem 0.75rem 0.35rem;
        margin-bottom: 0.95rem;
        text-align: center;
        position: relative;
    }}
    .zt-sidebar-brand-wrap::after {{
        content: '';
        display: block;
        width: 72%;
        height: 1px;
        margin: 0.8rem auto 0 auto;
        background: linear-gradient(90deg, rgba(255,255,255,0.0) 0%, rgba(197,22,29,0.85) 50%, rgba(255,255,255,0.0) 100%);
    }}
    .zt-sidebar-brand-wrap img {{
        display: block;
        margin: 0 auto 0.55rem auto;
        background: transparent !important;
        box-shadow: none !important;
        border: none !important;
    }}
    .zt-sidebar-brand-title {{
        color: #FFFFFF;
        font-size: 1.05rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        margin-bottom: 0.22rem;
    }}
    .zt-sidebar-brand-subtitle {{
        color: {_TEXT_SOFT};
        font-size: 0.78rem;
        line-height: 1.4;
    }}
    .zt-sidebar-nav-label {{
        color: rgba(255,255,255,0.52);
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin: 0.15rem 0 0.55rem 0.2rem;
    }}
    .zt-sidebar-fallback-logo {{
        display: inline-block;
        padding: 0.42rem 0.75rem;
        border-radius: 999px;
        background: linear-gradient(135deg, {_RED} 0%, {_RED_DARK} 100%);
        color: white;
        font-weight: 800;
        letter-spacing: 0.08em;
        margin-bottom: 0.55rem;
    }}
    .block-container {{
        padding-top: 1.25rem;
        padding-bottom: 2rem;
        padding-left: 1.4rem;
        padding-right: 1.6rem;
        max-width: none !important;
    }}
    [data-testid="stAppViewContainer"] .main .block-container {{
        max-width: none !important;
        width: 100%;
    }}
    h1, h2, h3 {{
        color: {_DARK};
        letter-spacing: -0.02em;
    }}
    .zt-header-grid {{
        display: grid;
        grid-template-columns: 112px minmax(0, 1fr);
        gap: 0.65rem;
        align-items: stretch;
        margin: 0.4rem 0 1.1rem 0;
        position: relative;
        z-index: 2;
    }}
    .zt-header-logo-panel {{
        background: transparent;
        border: none;
        border-radius: 0;
        min-height: 108px;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 4px 6px 4px 0;
        box-shadow: none;
        overflow: visible;
    }}
    .zt-header-logo-panel img {{
        max-height: 82px;
        width: auto;
        display: block;
        background: transparent !important;
        box-shadow: none !important;
        border: none !important;
    }}
    .zt-page-header {{
        background: linear-gradient(135deg, #ffffff 0%, #fbfbfb 100%);
        border: 1px solid {_BORDER};
        border-left: 6px solid {_RED};
        border-radius: 18px;
        padding: 16px 20px;
        min-height: 100px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-shadow: 0 8px 24px rgba(17,17,17,0.04);
    }}
    .zt-page-title {{
        font-size: 1.55rem;
        font-weight: 700;
        color: {_DARK};
        margin: 0;
    }}
    .zt-page-subtitle {{
        margin-top: 0.3rem;
        color: {_MID};
        font-size: 0.95rem;
    }}
    .zt-panel {{
        background: {_CARD};
        border: 1px solid {_BORDER};
        border-radius: 16px;
        padding: 14px 16px;
        margin-bottom: 1rem;
        box-shadow: 0 6px 18px rgba(17,17,17,0.03);
    }}
    .zt-panel-title {{
        font-size: 0.95rem;
        font-weight: 700;
        color: {_DARK};
        margin-bottom: 0.6rem;
    }}
    .zt-card {{
        background: {_CARD};
        border: 1px solid {_BORDER};
        border-radius: 18px;
        padding: 16px 18px 12px 18px;
        margin-bottom: 1rem;
        box-shadow: 0 8px 22px rgba(17,17,17,0.04);
    }}
    .zt-card-title {{
        font-size: 1.1rem;
        font-weight: 700;
        color: {_DARK};
        margin-bottom: 0.1rem;
    }}
    .zt-card-subtitle {{
        color: {_MID};
        font-size: 0.92rem;
        margin-bottom: 0.8rem;
    }}
    .zt-keyline {{
        color: {_MID};
        font-size: 0.92rem;
        margin: 0.2rem 0;
    }}
    .zt-label {{
        color: {_MID};
        font-weight: 600;
    }}
    .zt-soft-note {{
        padding: 0.6rem 0.8rem;
        border-radius: 12px;
        background: {_SOFT_RED};
        border: 1px solid #ffd6d6;
        color: {_DARK};
        font-size: 0.9rem;
        margin-top: 0.5rem;
    }}
    .zt-toolbar-panel {{
        background: linear-gradient(180deg, #ffffff 0%, #fcfcfc 100%);
        border: 1px solid {_BORDER};
        border-radius: 18px;
        padding: 14px 16px;
        margin-bottom: 1rem;
        box-shadow: 0 8px 22px rgba(17,17,17,0.04);
    }}
    .zt-section-kicker {{
        color: {_RED};
        font-size: 0.76rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.3rem;
    }}
    .zt-subtle-text {{
        color: {_MID};
        font-size: 0.9rem;
        line-height: 1.45;
    }}
    .zt-upload-tip {{
        padding: 0.72rem 0.82rem;
        border-radius: 14px;
        background: #fff9f9;
        border: 1px solid #f1d7d7;
        color: {_MID};
        font-size: 0.9rem;
    }}
    .zt-action-zone {{
        margin-top: 0.75rem;
        padding-top: 0.85rem;
        border-top: 1px dashed #dfdfe3;
    }}
    .zt-inline-stats {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.75rem;
        margin-bottom: 0.95rem;
    }}
    .zt-stat-chip {{
        background: linear-gradient(180deg, #ffffff 0%, #fbfbfb 100%);
        border: 1px solid {_BORDER};
        border-radius: 16px;
        padding: 0.85rem 0.95rem;
    }}
    .zt-stat-chip-label {{
        color: {_MID};
        font-size: 0.8rem;
        font-weight: 700;
        margin-bottom: 0.18rem;
    }}
    .zt-stat-chip-value {{
        color: {_DARK};
        font-size: 1.45rem;
        font-weight: 800;
        letter-spacing: -0.02em;
    }}
    .zt-badges {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        margin: 0.55rem 0 0.85rem 0;
    }}
    .zt-badge {{
        display: inline-block;
        padding: 0.28rem 0.62rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 700;
        border: 1px solid transparent;
        line-height: 1.2;
    }}
    .zt-badge-phase {{
        background: #ffffff;
        border-color: {_DARK};
        color: {_DARK};
    }}
    .zt-badge-health-neutral {{
        background: #f4f4f5;
        color: {_DARK};
        border-color: #dbdbde;
    }}
    .zt-badge-health-waiting {{
        background: #fff7f7;
        color: {_RED};
        border-color: #f1bcbc;
    }}
    .zt-badge-health-alert {{
        background: {_RED};
        color: #ffffff;
        border-color: {_RED};
    }}
    .zt-badge-result-positive {{
        background: #111111;
        color: #ffffff;
        border-color: #111111;
    }}
    .zt-badge-result-negative {{
        background: #fbe7e7;
        color: {_RED};
        border-color: #f2b6b6;
    }}
    .zt-badge-result-neutral {{
        background: #f4f4f5;
        color: {_DARK};
        border-color: #dbdbde;
    }}
    div.stButton > button {{
        border-radius: 12px;
        border: 1px solid {_DARK};
        background: white;
        color: {_DARK};
        font-weight: 600;
        min-height: 2.5rem;
    }}
    div.stButton > button:hover {{
        border-color: {_RED};
        color: {_RED};
    }}
    div.stButton > button[kind="primary"] {{
        background: {_RED};
        color: white;
        border-color: {_RED};
    }}
    div.stButton > button[kind="primary"]:hover {{
        background: #a60f15;
        border-color: #a60f15;
        color: white;
    }}
    div.stButton > button p,
    div.stDownloadButton > button p {{
        font-weight: 720;
        white-space: nowrap;
    }}
    [data-testid="stMetricValue"] {{
        color: {_DARK};
    }}

    div.stDownloadButton > button {{
        border-radius: 12px;
        border: 1px solid #111111;
        background: white;
        color: #111111;
        font-weight: 600;
        min-height: 2.5rem;
    }}
    div.stDownloadButton > button:hover {{
        border-color: #c5161d;
        color: #c5161d;
    }}

    /* Meeting Mode compact export toolbar.
       Scoped by a marker inserted immediately before the toolbar row. */
    div[data-testid="stMarkdown"]:has(.zt-meeting-tools-marker) + div[data-testid="stHorizontalBlock"] div.stButton > button,
    div[data-testid="stMarkdown"]:has(.zt-meeting-tools-marker) + div[data-testid="stHorizontalBlock"] div.stDownloadButton > button {{
        min-height: 1.75rem !important;
        height: 1.75rem !important;
        padding: 0.08rem 0.46rem !important;
        border-radius: 10px !important;
        white-space: nowrap !important;
        overflow: hidden !important;
    }}
    div[data-testid="stMarkdown"]:has(.zt-meeting-tools-marker) + div[data-testid="stHorizontalBlock"] div.stButton > button p,
    div[data-testid="stMarkdown"]:has(.zt-meeting-tools-marker) + div[data-testid="stHorizontalBlock"] div.stDownloadButton > button p {{
        font-size: 0.55rem !important;
        line-height: 1 !important;
        font-weight: 720 !important;
        white-space: nowrap !important;
        word-break: keep-all !important;
        overflow-wrap: normal !important;
        text-wrap: nowrap !important;
    }}
    .zt-compact-field-label {{
        color: #111111;
        font-size: 0.84rem;
        font-weight: 850;
        line-height: 1.15;
        margin: 0.08rem 0 0.28rem 0;
        letter-spacing: -0.01em;
    }}
    .zt-compact-field-label:hover {{
        color: #c5161d;
        cursor: help;
    }}
    /* Keep compact radio choices, such as Meeting View, on one line. */
    div[data-testid="stRadio"] div[role="radiogroup"] {{
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 1.05rem !important;
        align-items: center !important;
    }}
    div[data-testid="stRadio"] label {{
        white-space: nowrap !important;
    }}
    .zt-meeting-filter-grid {{
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 0.7rem;
        margin: 0.68rem 0 0.42rem 0;
    }}
    .zt-meeting-filter-card {{
        display: block;
        text-decoration: none !important;
        background: #ffffff;
        border: 1px solid #e8e8eb;
        border-radius: 20px;
        padding: 0.86rem 0.94rem;
        min-height: 104px;
        box-shadow: 0 10px 28px rgba(17,17,17,0.04);
        position: relative;
        overflow: hidden;
        cursor: pointer;
        transition: all 0.18s ease;
    }}
    .zt-meeting-filter-card:hover {{
        transform: translateY(-2px);
        border-color: rgba(197,22,29,0.34);
        box-shadow: 0 14px 34px rgba(17,17,17,0.08);
    }}
    .zt-meeting-filter-card:before {{
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        width: 4px;
        height: 100%;
        background: #111111;
    }}
    .zt-meeting-filter-card-active {{
        border-color: rgba(197,22,29,0.38);
        background: linear-gradient(180deg, #ffffff 0%, #fff7f7 100%);
        box-shadow: 0 14px 32px rgba(197,22,29,0.10);
    }}
    .zt-meeting-filter-card-active:before {{
        background: #c5161d;
    }}
    .zt-meeting-filter-count {{
        color: #111111;
        font-size: 1.75rem;
        line-height: 1;
        font-weight: 850;
        letter-spacing: -0.04em;
        margin-bottom: 0.58rem;
    }}
    .zt-meeting-filter-card-active .zt-meeting-filter-count {{
        color: #c5161d;
    }}
    .zt-meeting-filter-title {{
        color: #111111;
        font-size: 0.84rem;
        font-weight: 850;
        letter-spacing: -0.01em;
        margin-bottom: 0.2rem;
    }}
    .zt-meeting-active-filter {{
        margin: 0.78rem 0 0.9rem 0;
        padding: 0.72rem 0.82rem;
        border-radius: 15px;
        background: #fff7f7;
        border: 1px solid #ffd6d6;
        color: #2c2c2c;
        font-size: 0.88rem;
        line-height: 1.4;
    }}
    .zt-meeting-active-filter b {{
        color: #c5161d;
        font-weight: 880;
    }}
    .zt-meeting-card-head {{
        padding: 0.16rem 0.04rem 0.1rem 0.04rem;
    }}
    .zt-meeting-card-topline {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 1rem;
        padding-bottom: 0.72rem;
        border-bottom: 1px solid #f0f0f2;
    }}
    .zt-meeting-card-title {{
        color: #111111;
        font-size: 1.16rem;
        line-height: 1.3;
        font-weight: 780;
        letter-spacing: -0.02em;
        word-break: break-word;
    }}
    .zt-meeting-card-title span {{
        font-weight: 880;
    }}
    .zt-meeting-card-subtitle {{
        color: #646870;
        font-size: 0.88rem;
        line-height: 1.42;
        margin-top: 0.26rem;
    }}
    .zt-meeting-focus-strip {{
        margin-top: 0.62rem;
        margin-bottom: 0.72rem;
    }}
    .zt-meeting-field-grid {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.58rem;
        margin-top: 0.68rem;
    }}
    .zt-meeting-field {{
        border: 1px solid #eeeeef;
        background: #ffffff;
        border-radius: 16px;
        padding: 0.68rem 0.75rem;
        min-height: 78px;
    }}
    .zt-meeting-field-empty {{
        background: #fafafa;
    }}
    .zt-meeting-field-label {{
        color: #74777e;
        font-size: 0.7rem;
        font-weight: 850;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 0.26rem;
    }}
    .zt-meeting-field-value {{
        color: #111111;
        font-size: 0.9rem;
        line-height: 1.38;
        font-weight: 720;
        word-break: break-word;
    }}
    .zt-meeting-field-empty .zt-meeting-field-value {{
        color: #74777e;
        font-weight: 620;
    }}
    .zt-meeting-status-strip {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem 1rem;
        margin: 0.78rem 0 0.7rem 0;
        padding: 0.68rem 0.78rem;
        border-radius: 16px;
        background: #fff7f7;
        border: 1px solid #ffd6d6;
        color: #2c2c2c;
        font-size: 0.86rem;
        line-height: 1.38;
    }}
    .zt-meeting-status-strip b {{
        color: #111111;
        font-weight: 850;
    }}

    [data-testid="stMetric"] {{
        background: white;
        border: 1px solid {_BORDER};
        border-radius: 14px;
        padding: 0.35rem 0.75rem;
    }}
    .stDataFrame, [data-testid="stDataFrame"] {{
        border: 1px solid {_BORDER};
        border-radius: 14px;
        overflow: hidden;
        background: white;
    }}

    .zt-filter-intro-card {{
        background: linear-gradient(180deg, #ffffff 0%, #fcfcfd 100%);
        border: 1px solid #e8e8eb;
        border-radius: 20px;
        padding: 14px 16px;
        margin: 0.55rem 0 0.85rem 0;
        box-shadow: 0 10px 28px rgba(17,17,17,0.04);
    }}
    .zt-board-section-head {{
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        gap: 1rem;
        margin: 1rem 0 0.55rem 0;
    }}
    .zt-board-section-title {{
        color: #111111;
        font-size: 1.08rem;
        font-weight: 820;
        letter-spacing: -0.02em;
    }}
    .zt-board-section-note {{
        color: #74777e;
        font-size: 0.84rem;
        line-height: 1.4;
        max-width: 720px;
    }}
    .zt-board-metric-grid {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.78rem;
        margin: 0.7rem 0 1rem 0;
    }}
    .zt-board-metric-card {{
        background: #ffffff;
        border: 1px solid #e8e8eb;
        border-radius: 20px;
        padding: 0.92rem 1rem;
        box-shadow: 0 10px 28px rgba(17,17,17,0.04);
        position: relative;
        overflow: hidden;
        min-height: 104px;
    }}
    .zt-board-metric-card:before {{
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        width: 4px;
        height: 100%;
        background: var(--bar, #111111);
    }}
    .zt-board-metric-label {{
        color: #646870;
        font-size: 0.76rem;
        font-weight: 850;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-bottom: 0.36rem;
    }}
    .zt-board-metric-value {{
        color: #111111;
        font-size: 1.75rem;
        line-height: 1;
        font-weight: 850;
        letter-spacing: -0.04em;
        margin-bottom: 0.35rem;
    }}
    .zt-board-metric-sub {{
        color: #72767d;
        font-size: 0.8rem;
        line-height: 1.35;
    }}
    .zt-table-shell {{
        background: #ffffff;
        border: 1px solid #e8e8eb;
        border-radius: 22px;
        padding: 16px 18px;
        box-shadow: 0 10px 28px rgba(17,17,17,0.045);
        margin-bottom: 1rem;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        border: 1px solid #e8e8eb !important;
        border-radius: 26px !important;
        background: linear-gradient(180deg, #ffffff 0%, #fcfcfd 100%) !important;
        box-shadow: 0 16px 36px rgba(17,17,17,0.07) !important;
        margin: 0.85rem 0 1.2rem 0 !important;
        transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
        overflow: hidden;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
        transform: translateY(-2px);
        border-color: rgba(197,22,29,0.28) !important;
        box-shadow: 0 20px 46px rgba(17,17,17,0.105) !important;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"] > div {{
        border-radius: 26px !important;
        border: none !important;
        background: transparent !important;
    }}
    .zt-project-card-head {{
        padding: 0.2rem 0.05rem 0.15rem 0.05rem;
    }}
    .zt-project-card-topline {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 1rem;
        padding-bottom: 0.8rem;
        border-bottom: 1px solid #f0f0f2;
    }}
    .zt-project-eyebrow {{
        color: #c5161d;
        font-size: 0.72rem;
        font-weight: 850;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        margin-bottom: 0.26rem;
    }}
    .zt-project-title {{
        color: #111111;
        font-size: 1.18rem;
        line-height: 1.3;
        font-weight: 780;
        letter-spacing: -0.02em;
    }}
    .zt-project-title span {{
        font-weight: 880;
    }}
    .zt-project-focus-pill {{
        flex: 0 0 auto;
        border: 1px solid rgba(197,22,29,0.22);
        background: #fff7f7;
        color: #c5161d;
        border-radius: 999px;
        padding: 0.34rem 0.72rem;
        font-size: 0.78rem;
        font-weight: 820;
        white-space: nowrap;
    }}
    .zt-card-meta-grid {{
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 0.55rem;
        margin-top: 0.78rem;
    }}
    .zt-card-meta-item {{
        background: #fafafa;
        border: 1px solid #eeeeef;
        border-radius: 15px;
        padding: 0.58rem 0.68rem;
        min-height: 68px;
    }}
    .zt-card-meta-item span {{
        display: block;
        color: #74777e;
        font-size: 0.72rem;
        font-weight: 820;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 0.24rem;
    }}
    .zt-card-meta-item strong {{
        color: #111111;
        display: block;
        font-size: 0.88rem;
        line-height: 1.28;
        font-weight: 800;
        word-break: break-word;
    }}
    .zt-snapshot-grid {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.58rem;
        margin-top: 0.72rem;
    }}
    .zt-snapshot-card {{
        background: linear-gradient(180deg, #ffffff 0%, #f7f7f8 100%);
        border: 1px solid #eeeeef;
        border-radius: 16px;
        padding: 0.72rem 0.78rem;
    }}
    .zt-snapshot-label {{
        color: #6f737a;
        font-size: 0.74rem;
        font-weight: 820;
        margin-bottom: 0.24rem;
    }}
    .zt-snapshot-value {{
        color: #111111;
        font-size: 0.95rem;
        line-height: 1.32;
        font-weight: 820;
        word-break: break-word;
    }}
    .zt-detail-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.58rem 0.78rem;
        margin-top: 0.78rem;
    }}
    .zt-detail-item {{
        border: 1px solid #eeeeef;
        background: #ffffff;
        border-radius: 16px;
        padding: 0.72rem 0.8rem;
        min-height: 82px;
    }}
    .zt-detail-label {{
        color: #c5161d;
        font-size: 0.74rem;
        font-weight: 850;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 0.28rem;
    }}
    .zt-detail-value {{
        color: #2c2c2c;
        font-size: 0.9rem;
        line-height: 1.42;
        font-weight: 650;
        word-break: break-word;
    }}
    .zt-attention-strip {{
        margin-top: 0.76rem;
        padding: 0.72rem 0.82rem;
        border-radius: 16px;
        background: #fff2f2;
        border: 1px solid #ffd6d6;
        color: #111111;
        font-size: 0.88rem;
        line-height: 1.42;
    }}
    .zt-attention-strip b {{
        color: #c5161d;
        font-weight: 850;
    }}
    .zt-action-header {{
        margin: 0.85rem 0 0.45rem 0;
        padding-top: 0.78rem;
        border-top: 1px solid #f0f0f2;
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        gap: 1rem;
    }}
    .zt-action-header-title {{
        color: #111111;
        font-size: 0.95rem;
        font-weight: 850;
    }}
    .zt-action-header-note {{
        color: #74777e;
        font-size: 0.8rem;
        line-height: 1.35;
        max-width: 620px;
    }}
    .zt-action-group-head {{
        margin: 0.8rem 0 0.36rem 0;
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        gap: 0.75rem;
    }}
    .zt-action-group-title {{
        color: #111111;
        font-size: 0.84rem;
        font-weight: 850;
    }}
    .zt-action-group-note {{
        color: #7a7e85;
        font-size: 0.78rem;
        line-height: 1.35;
        text-align: right;
    }}

    .zt-selected-detail-card {{
        background: linear-gradient(180deg, #ffffff 0%, #fbfbfc 100%);
        border: 1px solid #e8e8eb;
        border-radius: 24px;
        padding: 1rem 1.1rem;
        margin: 0.9rem 0 0.45rem 0;
        box-shadow: 0 12px 32px rgba(17,17,17,0.055);
    }}
    .zt-selected-detail-title {{
        color: #111111;
        font-size: 1.22rem;
        line-height: 1.32;
        font-weight: 760;
        letter-spacing: -0.02em;
        word-break: break-word;
    }}
    .zt-selected-detail-title span {{
        font-weight: 880;
    }}
    .zt-selected-detail-subtitle {{
        color: #74777e;
        font-size: 0.88rem;
        line-height: 1.42;
        margin-top: 0.28rem;
    }}
    .zt-detail-mini-grid {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.72rem;
        margin: 0.55rem 0 1rem 0;
    }}
    .zt-detail-mini-card {{
        background: #ffffff;
        border: 1px solid #e8e8eb;
        border-radius: 18px;
        padding: 0.78rem 0.85rem;
        min-height: 86px;
        box-shadow: 0 8px 22px rgba(17,17,17,0.035);
    }}
    .zt-detail-mini-label {{
        color: #6f737a;
        font-size: 0.72rem;
        font-weight: 850;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-bottom: 0.32rem;
    }}
    .zt-detail-mini-value {{
        color: #111111;
        font-size: 0.98rem;
        line-height: 1.38;
        font-weight: 780;
        word-break: break-word;
    }}
    .zt-overview-section {{
        background: #ffffff;
        border: 1px solid #e8e8eb;
        border-radius: 22px;
        padding: 0.92rem 1rem;
        margin: 0.75rem 0 0.95rem 0;
        box-shadow: 0 10px 28px rgba(17,17,17,0.04);
    }}
    .zt-overview-section-title {{
        color: #111111;
        font-size: 0.98rem;
        font-weight: 860;
        letter-spacing: -0.01em;
        margin-bottom: 0.65rem;
    }}
    .zt-overview-grid {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.58rem;
    }}
    .zt-overview-field {{
        background: #fafafa;
        border: 1px solid #eeeeef;
        border-radius: 15px;
        padding: 0.62rem 0.7rem;
        min-height: 76px;
    }}
    .zt-overview-label {{
        color: #74777e;
        font-size: 0.72rem;
        font-weight: 850;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 0.26rem;
    }}
    .zt-overview-value {{
        color: #2c2c2c;
        font-size: 0.9rem;
        line-height: 1.38;
        font-weight: 680;
        word-break: break-word;
    }}

    .zt-sticky-summary {{
        position: sticky;
        top: 0.72rem;
        z-index: 50;
        background: rgba(255, 255, 255, 0.94);
        border: 1px solid #e8e8eb;
        border-radius: 18px;
        padding: 0.62rem 0.75rem;
        margin: 0.2rem 0 0.8rem 0;
        box-shadow: 0 12px 30px rgba(17,17,17,0.08);
        backdrop-filter: blur(12px);
    }}
    .zt-sticky-summary-kicker {{
        color: #c5161d;
        font-size: 0.66rem;
        font-weight: 880;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 0.42rem;
    }}
    .zt-sticky-summary-grid {{
        display: grid;
        grid-template-columns: 0.65fr 2.2fr 0.85fr 0.85fr 1fr 1fr 1fr;
        gap: 0.45rem;
        align-items: stretch;
    }}
    .zt-sticky-summary-item {{
        background: #fafafa;
        border: 1px solid #eeeeef;
        border-radius: 13px;
        padding: 0.42rem 0.52rem;
        min-height: 52px;
    }}
    .zt-sticky-summary-item span {{
        display: block;
        color: #74777e;
        font-size: 0.64rem;
        font-weight: 850;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 0.14rem;
    }}
    .zt-sticky-summary-item strong {{
        display: block;
        color: #111111;
        font-size: 0.82rem;
        line-height: 1.24;
        font-weight: 820;
        word-break: break-word;
    }}
    .zt-reference-link {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.28rem 0.56rem;
        border-radius: 999px;
        background: #c5161d;
        color: #ffffff !important;
        text-decoration: none !important;
        font-size: 0.78rem;
        font-weight: 850;
        margin-bottom: 0.3rem;
    }}
    .zt-reference-link:hover {{
        background: #a60f15;
        color: #ffffff !important;
        text-decoration: none !important;
    }}
    .zt-reference-url {{
        color: #6f737a;
        font-size: 0.78rem;
        line-height: 1.3;
        word-break: break-all;
    }}

    .zt-search-count-strip {{
        margin: 0.7rem 0 0.4rem 0;
        padding: 0.72rem 0.82rem;
        border-radius: 15px;
        background: #fff7f7;
        border: 1px solid #ffd6d6;
        color: #2c2c2c;
        font-size: 0.88rem;
        line-height: 1.4;
    }}
    .zt-search-count-strip b {{
        color: #c5161d;
        font-weight: 880;
    }}
    .zt-search-result-card {{
        background: linear-gradient(180deg, #ffffff 0%, #fcfcfd 100%);
        border: 1px solid #e8e8eb;
        border-radius: 22px;
        padding: 0.88rem 0.95rem;
        margin: 0.64rem 0 0.42rem 0;
        box-shadow: 0 10px 26px rgba(17,17,17,0.045);
        transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
    }}
    .zt-search-result-card:hover {{
        transform: translateY(-1px);
        border-color: rgba(197,22,29,0.28);
        box-shadow: 0 16px 34px rgba(17,17,17,0.08);
    }}
    .zt-search-result-top {{
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
        padding-bottom: 0.62rem;
        border-bottom: 1px solid #f0f0f2;
    }}
    .zt-search-result-title {{
        color: #111111;
        font-size: 1.02rem;
        line-height: 1.32;
        font-weight: 760;
        word-break: break-word;
    }}
    .zt-search-result-title span {{
        font-weight: 880;
    }}
    .zt-search-meta-grid {{
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 0.48rem;
        margin-top: 0.62rem;
    }}
    .zt-search-meta {{
        background: #fafafa;
        border: 1px solid #eeeeef;
        border-radius: 14px;
        padding: 0.48rem 0.58rem;
        min-height: 58px;
    }}
    .zt-search-meta span {{
        display: block;
        color: #74777e;
        font-size: 0.68rem;
        font-weight: 850;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 0.18rem;
    }}
    .zt-search-meta strong {{
        display: block;
        color: #111111;
        font-size: 0.82rem;
        line-height: 1.28;
        font-weight: 800;
        word-break: break-word;
    }}
    .zt-search-next {{
        margin-top: 0.62rem;
        color: #2c2c2c;
        font-size: 0.88rem;
        line-height: 1.42;
        word-break: break-word;
    }}
    .zt-search-next b {{
        color: #c5161d;
        font-weight: 850;
    }}

    [data-testid="stWidgetLabel"] p {{
        color: #111111 !important;
        font-size: 0.92rem !important;
        font-weight: 820 !important;
    }}
    [data-testid="stWidgetLabel"] label {{
        color: #111111 !important;
        font-weight: 820 !important;
    }}

    @media (max-width: 900px) {{
        .zt-board-metric-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        .zt-card-meta-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        .zt-snapshot-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        .zt-detail-grid {{ grid-template-columns: 1fr; }}
        .zt-detail-mini-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        .zt-overview-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        .zt-search-meta-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        .zt-meeting-filter-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        .zt-meeting-field-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        .zt-meeting-card-topline {{ flex-direction: column; }}
        .zt-search-result-top {{ flex-direction: column; }}
        .zt-project-card-topline {{ flex-direction: column; }}
        .zt-action-header, .zt-action-group-head {{ align-items: flex-start; flex-direction: column; }}
        .zt-action-group-note {{ text-align: left; }}
        .zt-header-grid {{
            grid-template-columns: 1fr;
        }}
        .zt-header-logo-panel {{
            min-height: 92px;
            padding-right: 0;
        }}
        .zt-page-header {{
            min-height: auto;
        }}
    }}
    
            .zt-followup-save-spacer {{ height: 1.65rem; }}
            div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button {{ font-weight: 800 !important; }}
</style>
    """
    st.markdown(css, unsafe_allow_html=True)


def render_page_header(title: str, subtitle: str | None = None) -> None:
    logo_path = get_header_logo_path()
    subtitle_html = f"<div class='zt-page-subtitle'>{subtitle}</div>" if subtitle else ""
    logo_html = (
        f"<img src='data:image/png;base64,{_logo_base64(logo_path)}' alt='Zenith logo'>"
        if logo_path and _logo_base64(logo_path)
        else "<div class='zt-sidebar-fallback-logo'>ZENITH</div>"
    )
    st.markdown(
        f"""
        <div class='zt-header-grid'>
            <div class='zt-header-logo-panel'>{logo_html}</div>
            <div class='zt-page-header'>
                <div class='zt-page-title'>{title}</div>
                {subtitle_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_panel_title(title: str) -> None:
    st.markdown(f"<div class='zt-panel-title'>{title}</div>", unsafe_allow_html=True)


def _health_class(value: str | None) -> str:
    value = (value or "").lower()
    if value in {"need decision", "need alignment", "blocked", "delayed", "due soon"}:
        return "zt-badge-health-alert"
    if value in {"waiting client", "waiting supplier", "waiting internal", "reopened"}:
        return "zt-badge-health-waiting"
    return "zt-badge-health-neutral"


def _result_class(value: str | None) -> str:
    value = (value or "").lower()
    if value in {"won", "paid closed", "complete shipped"}:
        return "zt-badge-result-positive"
    if value in {"lost", "cancelled"}:
        return "zt-badge-result-negative"
    return "zt-badge-result-neutral"


def render_badges_html(phase: str | None = None, health: str | None = None, result: str | None = None, pattern: bool = False) -> str:
    html = ["<div class='zt-badges'>"]
    if phase:
        html.append(f"<span class='zt-badge zt-badge-phase'>{phase}</span>")
    if health:
        html.append(f"<span class='zt-badge {_health_class(health)}'>{health}</span>")
    if result:
        html.append(f"<span class='zt-badge {_result_class(result)}'>{result}</span>")
    if pattern:
        html.append("<span class='zt-badge zt-badge-health-alert'>Repeated Issue</span>")
    html.append("</div>")
    return "".join(html)


def render_badges(phase: str | None = None, health: str | None = None, result: str | None = None, pattern: bool = False) -> None:
    badges_html = render_badges_html(phase, health, result, pattern)
    if badges_html:
        st.markdown(badges_html, unsafe_allow_html=True)
