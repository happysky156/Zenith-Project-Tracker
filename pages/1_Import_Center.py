from __future__ import annotations

import streamlit as st

from core.dictionaries import PEOPLE
from services.import_service import (
    ALL_IMPORT_FIELDS,
    IMPORT_FIELDS,
    apply_mapping,
    build_preview,
    import_preview_rows,
    read_uploaded_excel,
)
from services.validation_service import require_required_columns
from ui.project_table import render_project_table
from ui.theme import apply_theme, render_page_header
from utils.excel import guess_default_mapping

apply_theme()
render_page_header("Import Center", "Import Sales projects or Operation orders with clean validation and automatic linking.")

st.markdown("<div class='zt-toolbar-panel'>", unsafe_allow_html=True)
st.markdown("<div class='zt-section-kicker'>Import workflow</div>", unsafe_allow_html=True)
st.markdown("<div class='zt-subtle-text'>Upload one Excel file, choose <b>Sales</b> or <b>Operation</b>, map only the minimal key fields, then let the system keep all later status updates inside Streamlit.</div>", unsafe_allow_html=True)
st.markdown("<div class='zt-upload-tip'><b>Recommended use:</b> one admin imports files, while the team updates status, notes and meeting flags inside the system.</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

meta_col1, meta_col2, meta_col3 = st.columns([1, 1, 1])
import_type = meta_col1.radio("Import Type", options=["Sales", "Operation"], horizontal=True)
imported_by = meta_col2.selectbox(
    "Imported by",
    options=[None] + PEOPLE,
    format_func=lambda x: x or "Select name (optional)",
)
uploaded_file = meta_col3.file_uploader("Upload Excel file", type=["xlsx", "xls"])

st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
st.markdown("<div class='zt-panel-title'>Required fields</div>", unsafe_allow_html=True)
required_lines = "\n".join(f"- {field}" for field in IMPORT_FIELDS[import_type])
st.markdown(required_lines)
st.markdown("</div>", unsafe_allow_html=True)

if not uploaded_file:
    st.info("Upload an Excel file to start.")
    st.stop()

sheets = read_uploaded_excel(uploaded_file)
sheet_name = st.selectbox("Select sheet", list(sheets.keys()))
raw_df = sheets[sheet_name]

preview_col, mapping_col = st.columns([1.1, 1])
with preview_col:
    st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='zt-panel-title'>Sheet preview</div>", unsafe_allow_html=True)
    st.dataframe(raw_df.head(10), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

with mapping_col:
    st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='zt-panel-title'>Field mapping</div>", unsafe_allow_html=True)
    columns = list(raw_df.columns)
    defaults = guess_default_mapping(columns, import_type)
    options = [None] + columns
    mapping: dict[str, str | None] = {}
    cols = st.columns(2)
    for idx, target in enumerate(ALL_IMPORT_FIELDS[import_type]):
        mapping[target] = cols[idx % 2].selectbox(
            f"Map to {target}",
            options=options,
            index=options.index(defaults.get(target)) if defaults.get(target) in options else 0,
            key=f"map_{import_type}_{target}",
        )
    st.markdown("</div>", unsafe_allow_html=True)

if not require_required_columns(mapping, IMPORT_FIELDS[import_type]):
    st.error("Please map all required fields before building the import preview.")
    st.stop()

mapped_df, ignored_blank_rows = apply_mapping(raw_df, mapping, uploaded_file.name, import_type)
preview = build_preview(mapped_df, import_type, ignored_blank_rows=ignored_blank_rows)

st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
st.markdown("<div class='zt-panel-title'>Import validation</div>", unsafe_allow_html=True)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Ignored Blank Rows", preview.ignored_blank_rows)
c2.metric("Missing Required", preview.missing_required_rows)
c3.metric("Duplicate Keys", preview.duplicate_key_rows)
c4.metric("New Records", preview.new_count)
c5.metric("Updates", preview.update_count)
if import_type == "Operation":
    st.caption(f"Unlinked Project ID warnings: {preview.warning_unlinked_project_rows}")
st.markdown("</div>", unsafe_allow_html=True)

if preview.errors:
    st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='zt-panel-title'>Error list</div>", unsafe_allow_html=True)
    for msg in preview.errors[:80]:
        st.error(msg)
    st.markdown("</div>", unsafe_allow_html=True)

if preview.warnings:
    st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
    st.markdown("<div class='zt-panel-title'>Warnings</div>", unsafe_allow_html=True)
    for msg in preview.warnings[:80]:
        st.warning(msg)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='zt-panel'>", unsafe_allow_html=True)
st.markdown("<div class='zt-panel-title'>Import preview</div>", unsafe_allow_html=True)
preview_columns = IMPORT_FIELDS[import_type] + ["source_file", "_source_row_number", "_exists"]
render_project_table(
    preview.dataframe.to_dict(orient="records"),
    preview_columns,
    empty_message="Nothing to preview.",
    enable_jump=False,
)
st.markdown("</div>", unsafe_allow_html=True)

if not preview.ready:
    st.warning("Please fix the listed errors before importing.")
    st.stop()

st.markdown("<div class='zt-toolbar-panel'>", unsafe_allow_html=True)
st.markdown("<div class='zt-panel-title'>Confirm import</div>", unsafe_allow_html=True)
if st.button("Confirm Import", type="primary"):
    result = import_preview_rows(preview.dataframe, import_type=import_type, imported_by=imported_by)
    st.success(f"{import_type} import finished. New: {result['new_count']} | Updated: {result['update_count']}")
st.markdown("</div>", unsafe_allow_html=True)
