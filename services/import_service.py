from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any
import hashlib
import uuid

import pandas as pd

from core.dictionaries import (
    DEFAULT_HEALTH,
    DEFAULT_OPERATION_PHASE,
    DEFAULT_OPERATION_RESULT,
    DEFAULT_SALES_PHASE,
    DEFAULT_SALES_RESULT,
)
from database.repositories import (
    get_import_file_archive,
    list_import_file_archive,
    sales_project_exists,
    operation_order_exists,
    upsert_operation_base_fields,
    upsert_sales_base_fields,
    write_import_batch,
    write_import_file_archive,
)
from utils.dates import now_iso
from utils.ids import new_batch_id
from utils.logger import get_logger


logger = get_logger("import_service")


IMPORT_FIELDS = {
    "Sales": ["project_id", "project_name", "client_code"],
    "Operation": ["project_id", "client_code", "order_no"],
}

OPTIONAL_FIELDS = {
    "Sales": ["category", "priority", "reference_link"],
    "Operation": ["reference_link"],
}

ALL_IMPORT_FIELDS = {
    key: required + OPTIONAL_FIELDS.get(key, []) for key, required in IMPORT_FIELDS.items()
}


@dataclass
class ImportPreview:
    dataframe: pd.DataFrame
    ignored_blank_rows: int
    missing_required_rows: int
    duplicate_key_rows: int
    new_count: int
    update_count: int
    warning_unlinked_project_rows: int
    ready: bool
    errors: list[str]
    warnings: list[str]



def read_uploaded_excel(uploaded_file) -> dict[str, pd.DataFrame]:
    # Read from bytes so the same UploadedFile can later be archived.
    file_bytes = uploaded_file.getvalue()
    xls = pd.ExcelFile(BytesIO(file_bytes))
    return {sheet: pd.read_excel(BytesIO(file_bytes), sheet_name=sheet) for sheet in xls.sheet_names}


def archive_uploaded_import_file(uploaded_file, import_type: str, uploaded_by: str | None = None) -> dict[str, Any]:
    file_bytes = uploaded_file.getvalue()
    file_id = f"if_{uuid.uuid4().hex}"
    record = {
        "file_id": file_id,
        "source_file": str(getattr(uploaded_file, "name", "uploaded_file.xlsx")),
        "import_time": now_iso(),
        "uploaded_by": uploaded_by,
        "import_type": import_type,
        "file_size": len(file_bytes),
        "file_sha256": hashlib.sha256(file_bytes).hexdigest(),
        "content_type": str(getattr(uploaded_file, "type", "application/octet-stream") or "application/octet-stream"),
        "file_bytes": file_bytes,
    }
    write_import_file_archive(record)
    return {key: value for key, value in record.items() if key != "file_bytes"}


def list_archived_import_files(limit: int = 20) -> list[dict[str, Any]]:
    return list_import_file_archive(limit=limit)


def get_archived_import_file(file_id: str) -> dict[str, Any] | None:
    return get_import_file_archive(file_id)



def normalize_value(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text if text else None



def apply_mapping(df: pd.DataFrame, mapping: dict[str, str | None], source_file: str, import_type: str) -> tuple[pd.DataFrame, int]:
    rows: list[dict[str, Any]] = []
    ignored_blank_rows = 0
    fields = ALL_IMPORT_FIELDS[import_type]
    for idx, row in df.iterrows():
        item: dict[str, Any] = {field: None for field in fields}
        for target, source_col in mapping.items():
            if source_col and source_col in df.columns:
                item[target] = normalize_value(row[source_col])
        item["source_file"] = source_file
        item["_source_row_number"] = idx + 2
        if all(item.get(field) is None for field in IMPORT_FIELDS[import_type]):
            ignored_blank_rows += 1
            continue
        rows.append(item)
    return pd.DataFrame(rows), ignored_blank_rows



def _exists(import_type: str, key: str | None) -> bool:
    if not key:
        return False
    if import_type == "Sales":
        return sales_project_exists(key)
    return operation_order_exists(key)



def _key_field(import_type: str) -> str:
    return "project_id" if import_type == "Sales" else "order_no"



def build_preview(mapped_df: pd.DataFrame, import_type: str, ignored_blank_rows: int = 0) -> ImportPreview:
    if mapped_df.empty:
        preview = pd.DataFrame(columns=ALL_IMPORT_FIELDS[import_type] + ["source_file", "_source_row_number", "_exists"])
    else:
        preview = mapped_df.copy()
        for field in ALL_IMPORT_FIELDS[import_type]:
            if field in preview.columns:
                preview[field] = preview[field].apply(normalize_value)
        key_field = _key_field(import_type)
        preview["_exists"] = preview[key_field].apply(lambda x: _exists(import_type, normalize_value(x)))

    errors: list[str] = []
    warnings: list[str] = []
    required_fields = IMPORT_FIELDS[import_type]
    key_field = _key_field(import_type)

    missing_required_rows = 0
    duplicate_key_rows = 0
    unlinked_project_rows = 0

    if not preview.empty:
        for _, row in preview.iterrows():
            missing_fields = [field for field in required_fields if normalize_value(row.get(field)) is None]
            if missing_fields:
                missing_required_rows += 1
                errors.append(f"Row {int(row['_source_row_number'])}: missing {', '.join(missing_fields)}")

        normalized_keys = preview[key_field].apply(normalize_value)
        valid_keys = normalized_keys.dropna()
        duplicate_mask = valid_keys.duplicated(keep=False)
        duplicate_values = set(valid_keys[duplicate_mask].tolist())
        if duplicate_values:
            dup_rows = preview[normalized_keys.isin(duplicate_values)]
            duplicate_key_rows = len(dup_rows)
            for _, row in dup_rows.iterrows():
                errors.append(f"Row {int(row['_source_row_number'])}: duplicate {key_field} = {normalize_value(row.get(key_field))}")

        if import_type == "Operation":
            for _, row in preview.iterrows():
                project_id = normalize_value(row.get("project_id"))
                if project_id and not sales_project_exists(project_id):
                    unlinked_project_rows += 1
                    warnings.append(f"Row {int(row['_source_row_number'])}: project_id {project_id} is not in Sales yet")

    new_count = int((preview["_exists"] == False).sum()) if not preview.empty else 0
    update_count = int((preview["_exists"] == True).sum()) if not preview.empty else 0
    ready = missing_required_rows == 0 and duplicate_key_rows == 0 and not preview.empty

    return ImportPreview(
        dataframe=preview,
        ignored_blank_rows=ignored_blank_rows,
        missing_required_rows=missing_required_rows,
        duplicate_key_rows=duplicate_key_rows,
        new_count=new_count,
        update_count=update_count,
        warning_unlinked_project_rows=unlinked_project_rows,
        ready=ready,
        errors=errors,
        warnings=warnings,
    )



def import_preview_rows(preview_df: pd.DataFrame, import_type: str, imported_by: str | None = None) -> dict[str, int]:
    new_count = 0
    duplicate_skipped_count = 0
    total_input_records = int(len(preview_df))
    if preview_df.empty:
        return {
            "new_count": 0,
            "update_count": 0,
            "duplicate_skipped_count": 0,
            "total_input_records": 0,
        }

    for _, row in preview_df.iterrows():
        # Existing database records are treated as duplicates during import.
        # They are counted and skipped here so the import does not overwrite
        # status, owner, meeting or other working fields that the team may
        # have already updated in the system.
        if bool(row.get("_exists")):
            duplicate_skipped_count += 1
            continue

        if import_type == "Sales":
            project_id = normalize_value(row.get("project_id"))
            project_name = normalize_value(row.get("project_name"))
            client_code = normalize_value(row.get("client_code"))
            if not project_id:
                continue
            record = {
                "project_id": project_id,
                "project_name": project_name or project_id,
                "client_code": client_code or "Unknown",
                "category": normalize_value(row.get("category")),
                "priority": normalize_value(row.get("priority")),
                "reference_link": normalize_value(row.get("reference_link")),
                "source_file": row["source_file"],
                "created_at": now_iso(),
                "phase": DEFAULT_SALES_PHASE,
                "health_status": DEFAULT_HEALTH,
                "result_status": DEFAULT_SALES_RESULT,
                "current_owner": imported_by,
                "next_step_owner": imported_by,
            }
            action = upsert_sales_base_fields(record)
        else:
            order_no = normalize_value(row.get("order_no"))
            project_id = normalize_value(row.get("project_id"))
            client_code = normalize_value(row.get("client_code"))
            if not order_no:
                continue
            record = {
                "order_no": order_no,
                "project_id": project_id or order_no,
                "client_code": client_code or "Unknown",
                "reference_link": normalize_value(row.get("reference_link")),
                "source_file": row["source_file"],
                "created_at": now_iso(),
                "phase": DEFAULT_OPERATION_PHASE,
                "health_status": DEFAULT_HEALTH,
                "result_status": DEFAULT_OPERATION_RESULT,
                "current_owner": imported_by,
                "next_step_owner": imported_by,
            }
            action = upsert_operation_base_fields(record)

        if action == "inserted":
            new_count += 1
        else:
            duplicate_skipped_count += 1

    logger.info(
        "Import batch: source=%s | type=%s | added=%s | duplicates_skipped=%s | total_input=%s | operator=%s",
        str(preview_df["source_file"].iloc[0]) if len(preview_df) else "unknown",
        import_type,
        new_count,
        duplicate_skipped_count,
        total_input_records,
        imported_by,
    )

    write_import_batch(
        {
            "batch_id": new_batch_id(),
            "source_file": str(preview_df["source_file"].iloc[0]) if len(preview_df) else "unknown",
            "import_time": now_iso(),
            "imported_by": imported_by,
            "import_type": import_type,
            "new_count": new_count,
            # Keep the existing database column for compatibility.
            # In the current UI this value means "duplicates skipped".
            "update_count": duplicate_skipped_count,
            "failed_count": 0,
            "notes": f"{import_type} import | duplicates skipped",
        }
    )
    return {
        "new_count": new_count,
        "update_count": duplicate_skipped_count,
        "duplicate_skipped_count": duplicate_skipped_count,
        "total_input_records": total_input_records,
    }
