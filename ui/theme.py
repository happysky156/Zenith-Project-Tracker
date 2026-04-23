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
        st.markdown("<div class='zt-sidebar-brand-wrap'>", unsafe_allow_html=True)
        if logo_path:
            st.image(str(logo_path), width=118)
        else:
            st.markdown("<div class='zt-sidebar-fallback-logo'>ZENITH</div>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class='zt-sidebar-brand-text'>
                <div class='zt-sidebar-brand-title'>Zenith Tracker</div>
                <div class='zt-sidebar-brand-subtitle'>Project progress · meeting control · action follow-up</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<div class='zt-sidebar-nav-label'>Workspace</div>", unsafe_allow_html=True)


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
    [data-testid="stSidebarNav"] a svg {{
        fill: currentColor;
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
        padding-top: 1.6rem;
        padding-bottom: 2rem;
    }}
    h1, h2, h3 {{
        color: {_DARK};
        letter-spacing: -0.02em;
    }}
    .zt-header-grid {{
        display: grid;
        grid-template-columns: 152px 1fr;
        gap: 1rem;
        align-items: stretch;
        margin: 0.4rem 0 1.1rem 0;
        position: relative;
        z-index: 2;
    }}
    .zt-header-logo-panel {{
        background: transparent;
        border: none;
        border-radius: 0;
        min-height: 126px;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 6px 10px 6px 0;
        box-shadow: none;
        overflow: visible;
    }}
    .zt-header-logo-panel img {{
        max-height: 96px;
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
        padding: 18px 22px;
        min-height: 118px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-shadow: 0 8px 24px rgba(17,17,17,0.04);
    }}
    .zt-page-title {{
        font-size: 1.7rem;
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
    [data-testid="stMetricValue"] {{
        color: {_DARK};
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
    @media (max-width: 900px) {{
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


def render_badges(phase: str | None = None, health: str | None = None, result: str | None = None, pattern: bool = False) -> None:
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
    st.markdown("".join(html), unsafe_allow_html=True)
