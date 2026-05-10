from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from core.auth import require_login
from services.upgrade_service import field_display_map, list_module_records, upsert_module_record, MODULES
from ui.project_table import render_project_table
from ui.theme import apply_theme, render_page_header
from ui.upgrade_ui import render_metric_grid, render_upgrade_css, render_upgrade_intro, render_simple_filter_bar

apply_theme()
render_upgrade_css()
current_user = require_login()
operator = current_user["display_name"]

render_page_header("Supplier Details", "Shared supplier master data for Sales projects and Operation orders.")
render_upgrade_intro(
    "Supplier Details",
    "Supplier ID is the system key. Supplier Code is optional and can stay blank for expo or uncontacted suppliers. Active status, recent order, recent project, quotation count and risk summary are automatically calculated.",
)

DISPLAY = field_display_map("Supplier Details")

OVERVIEW_FIELDS = [
    "supplier_id", "supplier_code", "supplier_name", "supplier_short_name",
    "active_status", "active_reason", "last_order_no", "last_project_id",
    "price_comparison_count", "order_count", "quality_risk", "commercial_risk",
    "risk_summary", "last_contact_date", "last_updated_at", "last_updated_by",
]
BASIC_FIELDS = ["supplier_code", "supplier_name", "supplier_short_name", "company_type", "remark_internal"]
CONTACT_FIELDS = [
    "country", "province", "city", "location_raw", "address_standardised",
    "website_primary", "website_others", "primary_contact_name", "primary_contact_mobile",
    "primary_contact_email", "primary_contact_landline", "wechat", "other_contacts",
]
SOURCE_FIELDS = ["source_channel", "source_ref", "last_contact_date"]
COMPLIANCE_FIELDS = [
    "certificate", "certificate_remarks", "export_license", "nda_status", "nda_file",
    "audit_status", "audit_file", "catalogue_status", "catalogue_file",
]
CAPABILITY_FIELDS = [
    "main_products", "main_process", "material_capability", "surface_treatment",
    "testing_capability", "capability_tags",
]
COMMERCIAL_FIELDS = ["payment_terms", "lead_time", "quality_risk", "commercial_risk"]
SYSTEM_FIELDS = [
    "supplier_id", "active_status", "active_reason", "last_order_no", "last_project_id",
    "price_comparison_count", "order_count", "risk_summary", "created_at", "created_by",
    "last_updated_at", "last_updated_by",
]

LONG_TEXT_FIELDS = {
    "location_raw", "address_standardised", "website_others", "other_contacts", "source_ref",
    "certificate", "certificate_remarks", "main_products", "main_process", "material_capability",
    "surface_treatment", "testing_capability", "capability_tags", "remark_internal",
    "risk_summary", "active_reason",
}
URL_FIELDS = {"website_primary", "nda_file", "audit_file", "catalogue_file"}
RISK_OPTIONS = ["", "Low", "Medium", "High"]
COMPANY_TYPE_OPTIONS = ["", "Factory", "Trading Company", "Service Provider", "Factory + Trading", "Other"]


def _label(field: str) -> str:
    return DISPLAY.get(field, field.replace("_", " ").title())


def _value(record: dict[str, Any], field: str) -> Any:
    value = record.get(field)
    if value is None:
        return ""
    return value


def _clean(value: Any) -> str:
    text = str(value or "-").strip() or "-"
    return escape(text).replace("\n", "<br>")


def _field_input(field: str, record: dict[str, Any], *, key_prefix: str) -> Any:
    label = _label(field)
    value = _value(record, field)
    key = f"{key_prefix}_{field}"
    if field == "company_type":
        options = COMPANY_TYPE_OPTIONS
        current = str(value or "")
        return st.selectbox(label, options, index=options.index(current) if current in options else 0, key=key)
    if field in {"quality_risk", "commercial_risk"}:
        current = str(value or "")
        return st.selectbox(label, RISK_OPTIONS, index=RISK_OPTIONS.index(current) if current in RISK_OPTIONS else 0, key=key)
    if field in LONG_TEXT_FIELDS:
        return st.text_area(label, value=str(value or ""), height=90, key=key)
    return st.text_input(label, value=str(value or ""), key=key)


def _save_tab_form(title: str, fields: list[str], record: dict[str, Any], *, key_prefix: str) -> None:
    with st.form(f"supplier_edit_{key_prefix}"):
        st.caption("Only this tab will be saved. System-calculated fields are not manually maintained here.")
        payload: dict[str, Any] = {
            "supplier_id": record.get("supplier_id"),
            "supplier_name": record.get("supplier_name"),
        }
        if len(fields) <= 4:
            cols = st.columns(2)
            for idx, field in enumerate(fields):
                with cols[idx % 2]:
                    payload[field] = _field_input(field, record, key_prefix=key_prefix)
        else:
            for group_start in range(0, len(fields), 3):
                cols = st.columns(3)
                for idx, field in enumerate(fields[group_start:group_start + 3]):
                    with cols[idx]:
                        payload[field] = _field_input(field, record, key_prefix=key_prefix)
        if st.form_submit_button(f"Save {title}", type="primary"):
            if not str(payload.get("supplier_name") or "").strip():
                st.error("Supplier Name is required.")
            else:
                upsert_module_record("Supplier Details", payload, operator=operator)
                st.success(f"{title} saved.")
                st.rerun()


def _render_readonly_fields(record: dict[str, Any], fields: list[str]) -> None:
    rows = [{"Field": _label(field), "Value": record.get(field) or "-"} for field in fields]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_overview(record: dict[str, Any]) -> None:
    active = record.get("active_status") or "Inactive"
    metrics = {
        "Active Status": active,
        "Orders": record.get("order_count") or 0,
        "Price Quotes": record.get("price_comparison_count") or 0,
        "Quality Risk": record.get("quality_risk") or "-",
    }
    render_metric_grid(metrics)
    status_cols = st.columns(2)
    with status_cols[0]:
        st.markdown("#### Supplier Snapshot")
        _render_readonly_fields(record, [
            "supplier_id", "supplier_code", "supplier_name", "supplier_short_name",
            "company_type", "last_contact_date",
        ])
    with status_cols[1]:
        st.markdown("#### Auto Status")
        _render_readonly_fields(record, [
            "active_status", "active_reason", "last_order_no", "last_project_id",
            "price_comparison_count", "order_count", "risk_summary",
        ])


def _render_link_buttons(record: dict[str, Any], fields: list[str]) -> None:
    links = [(field, record.get(field)) for field in fields if record.get(field)]
    if not links:
        return
    st.caption("Quick document links")
    cols = st.columns(min(len(links), 3))
    for idx, (field, url) in enumerate(links):
        with cols[idx % len(cols)]:
            st.link_button(_label(field), str(url))


rows = list_module_records("Supplier Details", limit=2000)
active_count = sum(1 for r in rows if str(r.get("active_status") or "").lower() == "active")
missing_code = sum(1 for r in rows if not r.get("supplier_code"))
high_risk = sum(
    1 for r in rows
    if str(r.get("quality_risk") or "").lower() == "high"
    or str(r.get("commercial_risk") or "").lower() == "high"
)
render_metric_grid({
    "Total Suppliers": len(rows),
    "Active Suppliers": active_count,
    "No Supplier Code": missing_code,
    "High Risk": high_risk,
})

with st.expander("Add new supplier", expanded=False):
    with st.form("supplier_create_form"):
        st.caption("Only Supplier Name is required. Supplier ID, active status and system records are generated automatically.")
        c1, c2, c3 = st.columns(3)
        supplier_code = c1.text_input("Supplier Code", key="new_supplier_code")
        supplier_name = c2.text_input("Supplier Name", key="new_supplier_name")
        supplier_short_name = c3.text_input("Supplier Short Name", key="new_supplier_short")
        c1, c2, c3 = st.columns(3)
        company_type = c1.selectbox("Company Type", COMPANY_TYPE_OPTIONS, key="new_company_type")
        country = c2.text_input("Country", key="new_country")
        city = c3.text_input("City", key="new_city")
        c1, c2, c3 = st.columns(3)
        primary_contact_name = c1.text_input("Primary Contact Name", key="new_contact_name")
        primary_contact_mobile = c2.text_input("Primary Contact Mobile", key="new_contact_mobile")
        primary_contact_email = c3.text_input("Primary Contact Email", key="new_contact_email")
        c1, c2, c3 = st.columns(3)
        source_channel = c1.text_input("Source Channel", key="new_source_channel")
        quality_risk = c2.selectbox("Quality Risk", RISK_OPTIONS, key="new_quality_risk")
        commercial_risk = c3.selectbox("Commercial Risk", RISK_OPTIONS, key="new_commercial_risk")
        main_products = st.text_area("Main Products", height=70, key="new_main_products")
        remark_internal = st.text_area("Internal Remark", height=70, key="new_remark_internal")
        if st.form_submit_button("Create Supplier", type="primary"):
            if not supplier_name.strip():
                st.error("Supplier Name is required.")
            else:
                upsert_module_record(
                    "Supplier Details",
                    {
                        "supplier_code": supplier_code,
                        "supplier_name": supplier_name,
                        "supplier_short_name": supplier_short_name,
                        "company_type": company_type,
                        "country": country,
                        "city": city,
                        "primary_contact_name": primary_contact_name,
                        "primary_contact_mobile": primary_contact_mobile,
                        "primary_contact_email": primary_contact_email,
                        "source_channel": source_channel,
                        "quality_risk": quality_risk,
                        "commercial_risk": commercial_risk,
                        "main_products": main_products,
                        "remark_internal": remark_internal,
                    },
                    operator=operator,
                )
                st.success("Supplier created.")
                st.rerun()

filtered = render_simple_filter_bar("Supplier Details", rows)
with st.expander("Supplier summary table", expanded=True):
    render_project_table(
        filtered,
        [
            "supplier_id", "supplier_code", "supplier_name", "supplier_short_name", "company_type",
            "country", "province", "city", "active_status", "last_order_no", "last_project_id",
            "price_comparison_count", "order_count", "quality_risk", "commercial_risk",
        ],
        empty_message="No suppliers.",
        enable_jump=False,
    )

if not filtered:
    st.info("No supplier matches the current search.")
    st.stop()

labels: list[str] = []
label_to_id: dict[str, str] = {}
for row in filtered:
    supplier_id = str(row.get("supplier_id") or "")
    label = f"{row.get('supplier_code') or supplier_id} | {row.get('supplier_name') or '-'}"
    if row.get("city") or row.get("country"):
        label += f"  ·  {row.get('city') or '-'}, {row.get('country') or '-'}"
    labels.append(label)
    label_to_id[label] = supplier_id

selected_label = st.selectbox("Open Supplier Detail", labels, key="supplier_detail_select")
selected_id = label_to_id.get(selected_label)
selected = next((row for row in filtered if str(row.get("supplier_id") or "") == selected_id), filtered[0])

st.markdown(
    f"""
    <div class='zu-hero-card'>
        <div class='zu-kicker'>Supplier Detail</div>
        <div class='zu-title'>{_clean(selected.get('supplier_code') or selected.get('supplier_id'))} · {_clean(selected.get('supplier_name'))}</div>
        <div class='zu-text'>Use the tabs below to review and edit one part of the supplier record at a time. Overview and Activity/System Records keep auto-calculated fields read-only.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

tabs = st.tabs([
    "Overview",
    "Basic Info",
    "Contact & Location",
    "Source & Reference",
    "Compliance & Documents",
    "Capability",
    "Commercial & Risk",
    "Activity & System Records",
])

with tabs[0]:
    _render_overview(selected)

with tabs[1]:
    _save_tab_form("Basic Info", BASIC_FIELDS, selected, key_prefix=f"basic_{selected_id}")

with tabs[2]:
    _save_tab_form("Contact & Location", CONTACT_FIELDS, selected, key_prefix=f"contact_{selected_id}")

with tabs[3]:
    _save_tab_form("Source & Reference", SOURCE_FIELDS, selected, key_prefix=f"source_{selected_id}")

with tabs[4]:
    _render_link_buttons(selected, ["nda_file", "audit_file", "catalogue_file"])
    _save_tab_form("Compliance & Documents", COMPLIANCE_FIELDS, selected, key_prefix=f"compliance_{selected_id}")

with tabs[5]:
    _save_tab_form("Capability", CAPABILITY_FIELDS, selected, key_prefix=f"capability_{selected_id}")

with tabs[6]:
    _save_tab_form("Commercial & Risk", COMMERCIAL_FIELDS, selected, key_prefix=f"commercial_{selected_id}")

with tabs[7]:
    st.markdown("#### Activity & System Records")
    _render_readonly_fields(selected, SYSTEM_FIELDS)
    with st.expander("Field guide", expanded=False):
        guide = [
            {"field_name": f.name, "display_name": f.display, "description": f.description}
            for f in MODULES["Supplier Details"].fields
        ]
        render_project_table(guide, ["field_name", "display_name", "description"], empty_message="No fields.", enable_jump=False)
