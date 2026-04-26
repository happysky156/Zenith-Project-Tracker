from __future__ import annotations

from html import escape
from textwrap import dedent

import streamlit as st

from core.auth import require_login
from services.import_service import (
    ALL_IMPORT_FIELDS,
    archive_uploaded_import_file,
    get_archived_import_file,
    IMPORT_FIELDS,
    apply_mapping,
    build_preview,
    import_preview_rows,
    list_archived_import_files,
    read_uploaded_excel,
)
from services.validation_service import require_required_columns
from ui.project_table import render_project_table
from ui.theme import apply_theme, render_page_header
from utils.excel import guess_default_mapping

apply_theme()
current_user = require_login()
operator = current_user["display_name"]
render_page_header("Import Center", "Import Sales projects or Operation orders with clean validation and automatic linking.")


def _html(markup: str) -> str:
    return dedent(markup).strip()


def _render_import_css() -> None:
    st.markdown(
        _html(
            """
            <style>
            [data-testid="stWidgetLabel"] p {
                color: #111111 !important;
                font-size: 0.92rem !important;
                font-weight: 820 !important;
            }
            [data-testid="stWidgetLabel"] label {
                color: #111111 !important;
                font-weight: 820 !important;
            }
            div[role="radiogroup"] label p {
                font-weight: 520 !important;
            }

            [data-testid="stToast"] {
                border-radius: 18px !important;
                border: 1px solid #e8e8eb !important;
                box-shadow: 0 10px 28px rgba(17,17,17,0.10) !important;
                padding: 0.85rem 0.95rem !important;
            }
            [data-testid="stToast"] p {
                white-space: pre-line !important;
                font-size: 0.88rem !important;
                line-height: 1.48 !important;
                color: #2c2c2c !important;
                font-weight: 620 !important;
            }

            .zi-workflow-card {
                background: #ffffff;
                border: 1px solid #e8e8eb;
                border-radius: 22px;
                padding: 18px 20px 16px 20px;
                box-shadow: 0 10px 28px rgba(17,17,17,0.045);
                margin: 0.55rem 0 1rem 0;
            }
            .zi-section-kicker {
                color: #c5161d;
                font-size: 0.74rem;
                font-weight: 850;
                letter-spacing: 0.1em;
                text-transform: uppercase;
                margin-bottom: 0.35rem;
            }
            .zi-workflow-title {
                color: #111111;
                font-size: 1.08rem;
                font-weight: 820;
                letter-spacing: -0.02em;
                margin-bottom: 0.35rem;
            }
            .zi-workflow-text {
                color: #2c2c2c;
                font-size: 0.92rem;
                line-height: 1.5;
                margin-bottom: 0.8rem;
            }
            .zi-required-line {
                display: flex;
                flex-wrap: wrap;
                align-items: center;
                gap: 0.45rem;
                padding-top: 0.78rem;
                border-top: 1px solid #f0f0f2;
            }
            .zi-required-label {
                color: #111111;
                font-size: 0.84rem;
                font-weight: 820;
                margin-right: 0.1rem;
            }
            .zi-field-chip {
                display: inline-flex;
                align-items: center;
                border-radius: 999px;
                border: 1px solid #e5e5e7;
                background: #fafafa;
                color: #333333;
                padding: 0.3rem 0.62rem;
                font-size: 0.8rem;
                font-weight: 720;
            }

            .zi-section-head {
                margin: 1.05rem 0 0.5rem 0;
            }
            .zi-section-title {
                color: #111111;
                font-size: 1rem;
                font-weight: 820;
                margin-bottom: 0.18rem;
            }
            .zi-section-subtitle {
                color: #74777e;
                font-size: 0.84rem;
                line-height: 1.4;
            }

            .zi-validation-panel {
                background: #ffffff;
                border: 1px solid #e8e8eb;
                border-radius: 22px;
                padding: 18px 18px 16px 18px;
                box-shadow: 0 10px 28px rgba(17,17,17,0.045);
                margin: 1rem 0 1rem 0;
            }
            .zi-validation-grid {
                display: grid;
                grid-template-columns: repeat(6, minmax(0, 1fr));
                gap: 0.7rem;
                margin-top: 0.85rem;
            }
            .zi-validation-card {
                background: #fafafa;
                border: 1px solid #eeeeef;
                border-radius: 16px;
                padding: 0.78rem 0.82rem;
                min-height: 86px;
                position: relative;
                overflow: hidden;
            }
            .zi-validation-card:before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                width: 4px;
                height: 100%;
                background: var(--bar, #111111);
            }
            .zi-validation-label {
                color: #646870;
                font-size: 0.76rem;
                font-weight: 800;
                line-height: 1.2;
                margin-bottom: 0.42rem;
            }
            .zi-validation-value {
                color: #111111;
                font-size: 1.55rem;
                line-height: 1;
                font-weight: 850;
                letter-spacing: -0.04em;
            }

            .zi-empty {
                background: #ffffff;
                border: 1px dashed #d9d9dd;
                border-radius: 18px;
                padding: 1.2rem;
                color: #777b82;
                font-size: 0.9rem;
                margin-top: 0.8rem;
            }
            @media (max-width: 1300px) {
                .zi-validation-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
            }
            @media (max-width: 800px) {
                .zi-validation-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            }
            @media (max-width: 560px) {
                .zi-validation-grid { grid-template-columns: 1fr; }
            }
            </style>
            """
        ),
        unsafe_allow_html=True,
    )


def _section_head(title: str, subtitle: str | None = None) -> None:
    subtitle_html = f"<div class='zi-section-subtitle'>{escape(subtitle)}</div>" if subtitle else ""
    st.markdown(
        _html(
            f"""
            <div class='zi-section-head'>
                <div class='zi-section-title'>{escape(title)}</div>
                {subtitle_html}
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def _required_field_line(import_type: str) -> str:
    chips = "".join(
        f"<span class='zi-field-chip'>{escape(field)}</span>"
        for field in IMPORT_FIELDS[import_type]
    )
    return (
        "<div class='zi-required-line'>"
        "<span class='zi-required-label'>Required fields:</span>"
        f"{chips}"
        "</div>"
    )


def _validation_card(label: str, value: int, accent: str = "#111111") -> str:
    return _html(
        f"""
        <div class='zi-validation-card' style='--bar:{accent}'>
            <div class='zi-validation-label'>{escape(label)}</div>
            <div class='zi-validation-value'>{value}</div>
        </div>
        """
    )


def _validation_grid(preview) -> str:
    total_input_records = int(len(preview.dataframe))
    duplicate_skipped = int(preview.update_count)
    return _html(
        f"""
        <div class='zi-validation-panel'>
            <div class='zi-section-title'>Import validation</div>
            <div class='zi-section-subtitle'>Validation result uses the same wording as the completion notice.</div>
            <div class='zi-validation-grid'>
                {_validation_card('Total Input Records', total_input_records, '#111111')}
                {_validation_card('Added', preview.new_count, '#111111')}
                {_validation_card('Duplicates (Skipped)', duplicate_skipped, '#2c2c2c')}
                {_validation_card('Missing Required', preview.missing_required_rows, '#c5161d' if preview.missing_required_rows else '#111111')}
                {_validation_card('Duplicate Keys', preview.duplicate_key_rows, '#c5161d' if preview.duplicate_key_rows else '#111111')}
                {_validation_card('Ignored Blank Rows', preview.ignored_blank_rows, '#a1a1aa')}
            </div>
        </div>
        """
    )



def _render_import_file_archive() -> None:
    """Show previously uploaded source Excel files stored in the database."""
    with st.expander("Uploaded source file archive", expanded=False):
        st.caption(
            "Source Excel files uploaded through Import Center are saved in the database, "
            "so they remain available after Streamlit Cloud restarts."
        )
        try:
            archived_files = list_archived_import_files(limit=20)
        except Exception as exc:
            st.warning(f"Could not load file archive yet: {exc}")
            return

        if not archived_files:
            st.info("No archived source files yet.")
            return

        for idx, item in enumerate(archived_files, start=1):
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            with col1:
                st.markdown(f"**{escape(str(item.get('source_file') or 'uploaded file'))}**")
                st.caption(
                    f"{item.get('import_time') or ''} · {item.get('uploaded_by') or 'Unknown'} · "
                    f"{item.get('import_type') or ''} · {int(item.get('file_size') or 0):,} bytes"
                )
            with col2:
                st.caption("SHA-256")
                st.code(str(item.get("file_sha256") or "")[:12], language=None)
            with col3:
                file_id = str(item.get("file_id") or "")
                if st.button("Load", key=f"load_archived_import_file_{file_id}_{idx}"):
                    st.session_state["selected_import_archive_file_id"] = file_id
            with col4:
                if st.session_state.get("selected_import_archive_file_id") == str(item.get("file_id") or ""):
                    try:
                        full_file = get_archived_import_file(str(item.get("file_id")))
                        if full_file:
                            file_bytes = full_file.get("file_bytes") or b""
                            if isinstance(file_bytes, memoryview):
                                file_bytes = file_bytes.tobytes()
                            st.download_button(
                                "Download",
                                data=bytes(file_bytes),
                                file_name=str(full_file.get("source_file") or "import_source.xlsx"),
                                mime=str(full_file.get("content_type") or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                                key=f"download_archived_import_file_{item.get('file_id')}_{idx}",
                            )
                    except Exception as exc:
                        st.warning(f"Could not prepare download: {exc}")
_render_import_css()
_render_import_file_archive()

meta_col1, meta_col2, meta_col3 = st.columns([1, 1, 1])
with meta_col1:
    import_type = st.radio("Import Type", options=["Sales", "Operation"], horizontal=True)
with meta_col2:
    imported_by = operator
    st.text_input("Imported by", value=imported_by, disabled=True)
with meta_col3:
    uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx", "xls"])

st.markdown(
    _html(
        f"""
        <div class='zi-workflow-card'>
            <div class='zi-section-kicker'>Import Workflow</div>
            <div class='zi-workflow-title'>Upload, map and validate the source file</div>
            <div class='zi-workflow-text'>
                Upload one Excel file, choose <b>Sales</b> or <b>Operation</b>, map only the key fields, then confirm the import after validation.
            </div>
            {_required_field_line(import_type)}
        </div>
        """
    ),
    unsafe_allow_html=True,
)

if not uploaded_file:
    st.markdown(
        "<div class='zi-empty'>Upload an Excel file to start.</div>",
        unsafe_allow_html=True,
    )
    st.stop()

try:
    sheets = read_uploaded_excel(uploaded_file)
except Exception as exc:
    st.error(f"Failed to read the Excel file: {exc}")
    st.stop()

sheet_name = st.selectbox("Select sheet", list(sheets.keys()))
raw_df = sheets[sheet_name]

preview_col, mapping_col = st.columns([1.1, 1])
with preview_col:
    _section_head("Sheet preview", "First 10 rows from the selected sheet.")
    st.dataframe(raw_df.head(10), use_container_width=True, hide_index=True)

with mapping_col:
    _section_head("Field mapping", "Only required key fields must be mapped. Optional fields can be left blank.")
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

if not require_required_columns(mapping, IMPORT_FIELDS[import_type]):
    st.error("Please map all required fields before building the import preview.")
    st.stop()

mapped_df, ignored_blank_rows = apply_mapping(raw_df, mapping, uploaded_file.name, import_type)
preview = build_preview(mapped_df, import_type, ignored_blank_rows=ignored_blank_rows)

st.markdown(_validation_grid(preview), unsafe_allow_html=True)

if preview.errors:
    _section_head("Error list", "Please fix these errors before importing.")
    for msg in preview.errors[:80]:
        st.error(msg)

_section_head("Import preview", "Preview records before confirming the import.")
preview_columns = IMPORT_FIELDS[import_type] + ["source_file", "_source_row_number", "_exists"]
render_project_table(
    preview.dataframe.to_dict(orient="records"),
    preview_columns,
    empty_message="Nothing to preview.",
    enable_jump=False,
)

if not preview.ready:
    st.error("Please fix the listed errors before importing.")
    st.stop()

_section_head("Confirm import", "Click once after validation is ready.")
if st.button("Confirm Import", type="primary"):
    result = import_preview_rows(preview.dataframe, import_type=import_type, imported_by=imported_by)
    try:
        archive_info = archive_uploaded_import_file(uploaded_file, import_type=import_type, uploaded_by=imported_by)
        result["archived_file_id"] = archive_info.get("file_id")
    except Exception as exc:
        st.warning(f"Import data saved, but the source file could not be archived: {exc}")
    added = int(result.get("new_count", 0))
    skipped = int(result.get("duplicate_skipped_count", result.get("update_count", 0)))
    total_input = int(result.get("total_input_records", len(preview.dataframe)))
    message = (
        f"{import_type} import completed.\n"
        f"Added: {added}\n"
        f"Duplicates (skipped): {skipped}\n"
        f"Total input records: {total_input}"
    )
    try:
        st.toast(message, icon="✅")
    except Exception:
        st.success(message)
