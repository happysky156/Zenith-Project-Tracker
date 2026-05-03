from __future__ import annotations

from datetime import date, datetime
from typing import Any

from database.connection import execute, get_connection
from database.repositories import insert_event_log
from utils.dates import now_iso
from utils.ids import new_event_id


MILESTONES = [
    (1, "project_created", "Project Created"),
    (2, "supplier_added", "Supplier Added"),
    (3, "rfq_sent", "RFQ Sent"),
    (4, "supplier_quote_received", "Supplier Quote Received"),
    (5, "price_comparison_completed", "Price Comparison Completed"),
    (6, "client_quotation_created", "Client Quotation V1 Created"),
    (7, "index_snapshot_locked", "Index Snapshot Locked"),
    (8, "client_quotation_sent", "Client Quotation Sent"),
    (9, "sample_requested", "Sample Requested"),
    (10, "sample_sent_to_client", "Sample Sent to Client"),
    (11, "client_approved_sample", "Client Approved Sample"),
    (12, "order_created", "Order Created"),
    (13, "production_followup", "Production Follow-up"),
    (14, "inspection_completed", "Inspection Completed"),
    (15, "shipment_completed", "Shipment Completed"),
    (16, "final_cost_updated", "Final Cost Updated"),
    (17, "gross_profit_confirmed", "Gross Profit Confirmed"),
    (18, "project_closed", "Project Closed"),
]

CLOSED_RESULTS = {"won", "lost", "paid closed", "cancelled", "canceled", "closed", "complete", "completed"}
RISK_HEALTH = {"risk", "blocked", "delayed", "due soon", "need decision", "need alignment", "waiting client", "waiting supplier", "waiting internal"}


def _is_blank(value: Any) -> bool:
    return value is None or str(value).strip().lower() in {"", "-", "nan", "none", "null"}


def _text(value: Any) -> str | None:
    if _is_blank(value):
        return None
    return str(value).strip()


def _parse_datetime(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    raw = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:10], fmt)
        except Exception:
            continue
    return None


def _date_text(value: Any) -> str | None:
    dt = _parse_datetime(value)
    if dt:
        return dt.date().isoformat()
    return None


def _days_between(start: Any, end: Any | None = None) -> int | None:
    start_dt = _parse_datetime(start)
    if not start_dt:
        return None
    end_dt = _parse_datetime(end) or datetime.combine(date.today(), datetime.min.time())
    return max((end_dt.date() - start_dt.date()).days, 0)


def _earliest(*values: Any) -> str | None:
    dates = [_date_text(v) for v in values if _date_text(v)]
    return min(dates) if dates else None


def _latest(*values: Any) -> str | None:
    dates = [_date_text(v) for v in values if _date_text(v)]
    return max(dates) if dates else None


def _first_date(rows: list[dict[str, Any]], fields: list[str], predicate=None) -> str | None:
    dates: list[str] = []
    for row in rows:
        if predicate and not predicate(row):
            continue
        for field in fields:
            value = _date_text(row.get(field))
            if value:
                dates.append(value)
                break
    return min(dates) if dates else None


def _latest_date(rows: list[dict[str, Any]], fields: list[str], predicate=None) -> str | None:
    dates: list[str] = []
    for row in rows:
        if predicate and not predicate(row):
            continue
        for field in fields:
            value = _date_text(row.get(field))
            if value:
                dates.append(value)
                break
    return max(dates) if dates else None


def _contains_any(value: Any, words: set[str]) -> bool:
    text = str(value or "").lower()
    return any(word in text for word in words)


def fetch_project_timeline_source(record_type: str, record_id: str, project_id: str | None = None) -> dict[str, Any]:
    """Read all available lifecycle data for a Project/Order without raising UI errors.

    Missing extension tables/columns are tolerated so the timeline can show
    placeholders while the database is gradually migrated.
    """
    project_id = project_id or (record_id if record_type == "Sales" else None)
    conn = get_connection()
    cur = conn.cursor()

    def q(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        try:
            execute(cur, sql, params)
            return [dict(row) for row in cur.fetchall()]
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            return []

    sales = q("SELECT * FROM sales_projects WHERE project_id = ?", (project_id,)) if project_id else []
    operation = q("SELECT * FROM operation_orders WHERE order_no = ?", (record_id,)) if record_type == "Operation" else []
    linked_ops = q("SELECT * FROM operation_orders WHERE project_id = ?", (project_id,)) if project_id else []
    event_rows = []
    if record_type == "Sales" and project_id:
        event_rows = q("SELECT * FROM event_logs_v2 WHERE project_id = ? ORDER BY event_time DESC", (project_id,))
    else:
        event_rows = q(
            "SELECT * FROM event_logs_v2 WHERE entity_type = ? AND entity_id = ? ORDER BY event_time DESC",
            (record_type, record_id),
        )
    ext = {
        "project_items": q("SELECT * FROM project_items WHERE project_id = ?", (project_id,)) if project_id else [],
        "supplier_price_comparisons": q("SELECT * FROM supplier_price_comparisons WHERE project_id = ?", (project_id,)) if project_id else [],
        "client_quotation_headers": q("SELECT * FROM client_quotation_headers WHERE project_id = ?", (project_id,)) if project_id else [],
        "client_quotation_lines": q("SELECT * FROM client_quotation_lines WHERE project_id = ?", (project_id,)) if project_id else [],
        "index_snapshots": q("SELECT * FROM index_snapshots WHERE project_id = ?", (project_id,)) if project_id else [],
        "order_details": q("SELECT * FROM order_details WHERE project_id = ?", (project_id,)) if project_id else [],
        "order_costs": q("SELECT * FROM order_costs WHERE project_id = ?", (project_id,)) if project_id else [],
        "sample_tracking": q("SELECT * FROM sample_tracking WHERE project_id = ?", (project_id,)) if project_id else [],
    }
    conn.close()
    return {
        "project_id": project_id,
        "record_type": record_type,
        "record_id": record_id,
        "sales": sales[0] if sales else {},
        "operation": operation[0] if operation else {},
        "linked_operations": linked_ops,
        "events": event_rows,
        **ext,
    }


def build_lifecycle_view(record_type: str, record_id: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    project_id = (detail or {}).get("project_id") or (record_id if record_type == "Sales" else None)
    source = fetch_project_timeline_source(record_type, record_id, str(project_id) if project_id else None)
    base = dict(detail or {})
    if source.get("sales"):
        base = {**source["sales"], **base}
    if record_type == "Operation" and source.get("operation"):
        base = {**source["operation"], **base}

    quotes = source["supplier_price_comparisons"]
    client_headers = source["client_quotation_headers"]
    snapshots = source["index_snapshots"]
    samples = source["sample_tracking"]
    order_details = source["order_details"]
    order_costs = source["order_costs"]
    linked_ops = source["linked_operations"]
    events = source["events"]

    event_by_type = {}
    for ev in events:
        typ = str(ev.get("event_type") or "")
        if typ:
            event_by_type.setdefault(typ, []).append(ev)

    def event_date(types: list[str]) -> str | None:
        rows: list[dict[str, Any]] = []
        for typ in types:
            rows.extend(event_by_type.get(typ, []))
        return _first_date(rows, ["actual_date", "event_time", "created_at"])

    project_created = _earliest(base.get("created_at"), event_date(["Project Created"]))
    supplier_added = _earliest(
        event_date(["Supplier Added"]),
        _first_date(quotes, ["quote_date", "imported_at"], lambda r: bool(_text(r.get("supplier_name")) or _text(r.get("supplier_id")))),
        _first_date(order_details, ["order_date", "imported_at"], lambda r: bool(_text(r.get("supplier_name")) or _text(r.get("supplier_id")))),
        _first_date(samples, ["sample_request_date", "last_updated_at"], lambda r: bool(_text(r.get("supplier_name")) or _text(r.get("supplier_id")))),
    )
    rfq_sent_event = event_date(["RFQ Sent"])
    supplier_quote_received = _earliest(event_date(["Supplier Quote Received", "Supplier Quote Imported", "Supplier Price Comparison Updated"]), _first_date(quotes, ["quote_date", "imported_at"]))
    price_completed = _earliest(
        event_date(["Price Comparison Completed"]),
        _first_date(
            quotes,
            ["quote_date", "imported_at"],
            lambda r: str(r.get("comparison_status") or "").lower() == "completed" or bool(r.get("selected_supplier")) or bool(r.get("recommended_supplier")),
        ),
    )
    client_v1 = _earliest(
        event_date(["Client Quotation V1 Created", "Client Quotation Created"]),
        _first_date(client_headers, ["quote_date", "created_at", "last_updated_at"], lambda r: str(r.get("quote_version") or "").upper() in {"V1", "1", ""}),
    )
    index_locked = _earliest(event_date(["Index Snapshot Locked"]), _first_date(snapshots, ["locked_at", "snapshot_date"]))
    client_sent = _earliest(
        event_date(["Client Quotation Sent"]),
        _first_date(client_headers, ["quote_date", "last_updated_at", "created_at"], lambda r: str(r.get("quote_status") or "").lower() == "sent"),
    )
    sample_requested = _earliest(event_date(["Sample Requested"]), _first_date(samples, ["sample_request_date", "last_updated_at"]))
    sample_sent = _earliest(event_date(["Sample Sent to Client"]), _first_date(samples, ["sample_sent_to_client_date"]))
    sample_approved = _earliest(
        event_date(["Client Approved Sample", "Sample Approved"]),
        _first_date(samples, ["client_feedback_date", "last_updated_at"], lambda r: "approved" in str(r.get("sample_status") or "").lower()),
    )
    order_created = _earliest(event_date(["Order Created"]), _first_date(order_details, ["order_date", "imported_at"]), _first_date(linked_ops, ["created_at"]))
    production_followup = _earliest(
        event_date(["Production Follow-up"]),
        _first_date(order_details, ["actual_delivery_date", "target_delivery_date", "order_date", "imported_at"], lambda r: bool(_text(r.get("production_status")))),
    )
    inspection_completed = _earliest(
        event_date(["Inspection Completed"]),
        _first_date(order_details, ["inspection_date", "imported_at"], lambda r: bool(_text(r.get("inspection_date"))) or _contains_any(r.get("inspection_status"), {"passed", "complete", "completed"})),
    )
    shipment_completed = _earliest(
        event_date(["Shipment Completed"]),
        _first_date(order_details, ["shipment_date", "actual_delivery_date", "imported_at"], lambda r: bool(_text(r.get("shipment_date"))) or _contains_any(r.get("shipment_status"), {"complete", "completed", "shipped"})),
        _first_date(linked_ops, ["last_status_update_at", "created_at"], lambda r: str(r.get("result_status") or "").lower() in {"complete shipped", "paid closed"}),
    )
    final_cost = _earliest(event_date(["Final Cost Updated"]), _latest_date(order_costs, ["cost_date", "created_at"]))
    gp_confirmed = _earliest(
        event_date(["Gross Profit Confirmed"]),
        _latest_date(order_details, ["imported_at", "order_date"], lambda r: not _is_blank(r.get("gross_profit"))),
    )
    closed = _earliest(
        event_date(["Project Closed", "Record Archived"]),
        base.get("last_status_update_at") if str(base.get("result_status") or "").strip().lower() in CLOSED_RESULTS else None,
    )

    actual_by_code = {
        "project_created": project_created,
        "supplier_added": supplier_added,
        "rfq_sent": rfq_sent_event,
        "supplier_quote_received": supplier_quote_received,
        "price_comparison_completed": price_completed,
        "client_quotation_created": client_v1,
        "index_snapshot_locked": index_locked,
        "client_quotation_sent": client_sent,
        "sample_requested": sample_requested,
        "sample_sent_to_client": sample_sent,
        "client_approved_sample": sample_approved,
        "order_created": order_created,
        "production_followup": production_followup,
        "inspection_completed": inspection_completed,
        "shipment_completed": shipment_completed,
        "final_cost_updated": final_cost,
        "gross_profit_confirmed": gp_confirmed,
        "project_closed": closed,
    }

    done_sequences = [seq for seq, code, _ in MILESTONES if actual_by_code.get(code)]
    last_done_seq = max(done_sequences) if done_sequences else 0
    current_seq = min((seq for seq, _, _ in MILESTONES if seq > last_done_seq), default=None)

    milestones: list[dict[str, Any]] = []
    for seq, code, label in MILESTONES:
        actual = actual_by_code.get(code)
        status = "Done" if actual else ("Current" if current_seq == seq else "Pending")
        if not actual and last_done_seq > seq:
            status = "Missing"
        if code.startswith("sample_") or code == "client_approved_sample":
            # If an order exists and no sample record exists, many trading cases do not need sample tracking.
            if order_created and not samples and not actual:
                status = "Not Applicable"
        planned = None
        if code in {"sample_requested", "sample_sent_to_client"}:
            planned = _first_date(samples, ["target_sample_date", "target_date"])
        elif code in {"order_created", "production_followup", "inspection_completed", "shipment_completed"}:
            planned = _first_date(order_details, ["target_delivery_date"])
        else:
            planned = _date_text(base.get("target_date")) if status == "Current" else None
        delay = None
        if planned:
            if actual:
                delay = max(_days_between(planned, actual) or 0, 0)
            elif date.fromisoformat(planned) < date.today():
                delay = _days_between(planned)
                if status in {"Current", "Pending"}:
                    status = "Delayed"
        milestones.append(
            {
                "Sequence": seq,
                "Milestone": label,
                "Status": status,
                "Planned Date": planned or "-",
                "Actual Date": actual or "-",
                "Delay Days": delay if delay is not None else "-",
                "Date Source": "Auto" if actual else ("Manual Target" if planned else "Not recorded"),
            }
        )

    stage = next((m for m in milestones if m["Status"] in {"Current", "Delayed"}), None)
    current_stage = stage["Milestone"] if stage else ("Closed" if closed else "Not classified yet")
    previous_done_dates = [m["Actual Date"] for m in milestones if m["Actual Date"] != "-"]
    current_stage_start = max(previous_done_dates) if previous_done_dates else project_created
    days_in_stage = _days_between(current_stage_start) if current_stage_start and current_stage != "Closed" else None

    target_date = _date_text(base.get("target_date"))
    delay_days = None
    if target_date and date.fromisoformat(target_date) < date.today() and not closed:
        delay_days = _days_between(target_date)

    waiting_for = _text(base.get("client_waiting_for")) or _text(base.get("waiting_for_text")) or _text(base.get("block_point")) or _text(base.get("need_from_meeting")) or _text(base.get("next_step_owner"))
    waiting_since = _date_text(base.get("last_status_update_at")) or current_stage_start or project_created
    waiting_days = _days_between(waiting_since) if waiting_for and waiting_since else None

    customer_waiting = _text(base.get("client_waiting_for"))
    customer_waiting_days = _days_between(waiting_since) if customer_waiting and waiting_since else None

    risk_flag = str(base.get("health_status") or "").strip().lower() in RISK_HEALTH
    high_quote = any(str(q.get("quotation_risk") or "").strip().lower() == "high" for q in quotes)
    high_sample = any(str(s.get("sample_status") or "").strip().lower() in {"rejected", "need revision", "failed"} for s in samples)
    risk_age = _days_between(_date_text(base.get("last_status_update_at")) or current_stage_start or project_created) if (risk_flag or high_quote or high_sample) else None
    risk_summary = _text(base.get("main_issue")) or _text(base.get("block_point")) or ("High quotation risk" if high_quote else None) or ("Sample issue" if high_sample else None) or "No active risk flag"

    cards = {
        "Project Age": f"{_days_between(project_created) if project_created else 'Not available'}" + (" days" if project_created else ""),
        "Current Stage": current_stage,
        "Days in Current Stage": f"{days_in_stage} days" if days_in_stage is not None else "Not calculated yet",
        "Waiting For": waiting_for or "No active waiting",
        "Waiting Days": f"{waiting_days} days" if waiting_days is not None else "Not calculated yet",
        "Delay Days": f"{delay_days} days" if delay_days is not None else ("No target set" if not target_date else "On track / no delay"),
        "Risk Age": f"{risk_age} days" if risk_age is not None else "No active risk flag",
        "Customer Waiting Days": f"{customer_waiting_days} days" if customer_waiting_days is not None else "No active customer waiting",
    }

    detailed = []
    for ev in events:
        detailed.append(
            {
                "Date": _date_text(ev.get("event_time")) or ev.get("event_time") or "-",
                "Group": ev.get("event_group") or "-",
                "Event": ev.get("event_type") or "-",
                "Owner": ev.get("owner") or ev.get("operator") or "-",
                "Waiting For": ev.get("waiting_for") or "-",
                "Delay": ev.get("delay_days") if not _is_blank(ev.get("delay_days")) else "-",
                "Risk": ev.get("risk_level") or "-",
                "Customer Impact": ev.get("customer_impact") or "-",
                "Note": ev.get("event_note") or "-",
                "Source": ev.get("source_page") or ev.get("source_module") or "-",
            }
        )

    return {
        "cards": cards,
        "milestones": milestones,
        "events": detailed,
        "raw_events": events,
        "summary": {
            "project_created": project_created,
            "current_stage": current_stage,
            "current_stage_start": current_stage_start,
            "waiting_for": waiting_for,
            "risk_summary": risk_summary,
            "target_date": target_date,
        },
    }


def log_commercial_event(
    *,
    entity_type: str,
    entity_id: str,
    project_id: str | None,
    order_no: str | None = None,
    event_type: str,
    event_group: str = "Commercial",
    operator: str | None = None,
    event_note: str | None = None,
    source_page: str | None = None,
    source_module: str | None = None,
    source_record_id: str | None = None,
    actual_date: str | None = None,
    planned_date: str | None = None,
    waiting_for: str | None = None,
    owner: str | None = None,
    risk_level: str | None = None,
    customer_impact: str | None = None,
    commercial_impact: str | None = None,
) -> None:
    insert_event_log(
        {
            "event_id": new_event_id(),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "project_id": project_id,
            "order_no": order_no,
            "event_time": now_iso(),
            "event_type": event_type,
            "event_group": event_group,
            "operator": operator,
            "event_note": event_note,
            "source_page": source_page or source_module or "Commercial Timeline",
            "actual_date": actual_date,
            "planned_date": planned_date,
            "waiting_for": waiting_for,
            "owner": owner,
            "risk_level": risk_level,
            "customer_impact": customer_impact,
            "commercial_impact": commercial_impact,
            "source_module": source_module,
            "source_record_id": source_record_id,
        }
    )
