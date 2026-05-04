from __future__ import annotations

from collections import defaultdict
from datetime import date
from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from core.auth import require_login
from services.upgrade_service import list_module_records, upsert_module_record
from ui.theme import apply_theme, render_page_header
from ui.upgrade_ui import render_upgrade_css, render_upgrade_intro, render_metric_grid, render_layered_records


apply_theme()
render_upgrade_css()
current_user = require_login()
operator = current_user["display_name"]

render_page_header("Price Comparison", "Supplier-side cost quotations by Project ID + RFQ Item Ref + Supplier.")
render_upgrade_intro(
    "Supplier Price Comparison",
    "Compare supplier quotations by project and RFQ item. Use this page to see price gaps, quotation completeness and supplier-side quotation risk before client quotation.",
)


# -----------------------------------------------------------------------------
# Helpers: display only. Do not change import, database, or business logic.
# -----------------------------------------------------------------------------


def _txt(value: Any, default: str = "-") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.lower() in {"none", "nan", "nat"}:
        return default
    return text


def _num(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"none", "nan", "-"}:
        return None
    text = text.replace(",", "").replace("$", "").replace("¥", "").replace("￥", "")
    try:
        return float(text)
    except Exception:
        return None


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "selected", "recommended"}


def _money(value: Any, currency: str | None = None) -> str:
    number = _num(value)
    if number is None:
        return "-"
    cur = _txt(currency, "").upper()
    prefix = "$" if cur in {"USD", "US$"} else ""
    return f"{prefix}{number:,.2f}" if abs(number) < 100000 else f"{prefix}{number:,.0f}"


def _price(row: dict[str, Any]) -> float | None:
    return _num(row.get("supplier_unit_cost"))


def _is_supplier_matched(row: dict[str, Any]) -> bool:
    return bool(_txt(row.get("supplier_id"), ""))


def _project_options(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({_txt(r.get("project_id"), "") for r in rows if _txt(r.get("project_id"), "")})


def _item_options(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({_txt(r.get("rfq_item_ref"), "") for r in rows if _txt(r.get("rfq_item_ref"), "")})


def _supplier_options(rows: list[dict[str, Any]]) -> list[str]:
    values: set[str] = set()
    for r in rows:
        code = _txt(r.get("supplier_code"), "")
        name = _txt(r.get("supplier_name"), "")
        label = code or name
        if label:
            values.add(label)
    return sorted(values)


def _apply_filters(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    st.markdown("### Search and filter")
    c1, c2, c3, c4 = st.columns([1.2, 1.0, 1.0, 1.2])
    search = c1.text_input("Search", placeholder="Project ID, item, supplier, remarks...", key="price_comp_search")
    project = c2.selectbox("Project ID", ["All"] + _project_options(rows), key="price_comp_project")
    item = c3.selectbox("RFQ Item Ref", ["All"] + _item_options(rows), key="price_comp_item")
    supplier = c4.selectbox("Supplier", ["All"] + _supplier_options(rows), key="price_comp_supplier")

    filtered = rows
    if project != "All":
        filtered = [r for r in filtered if _txt(r.get("project_id"), "") == project]
    if item != "All":
        filtered = [r for r in filtered if _txt(r.get("rfq_item_ref"), "") == item]
    if supplier != "All":
        filtered = [
            r
            for r in filtered
            if supplier in {_txt(r.get("supplier_code"), ""), _txt(r.get("supplier_name"), "")}
        ]
    if search:
        keyword = search.strip().lower()
        filtered = [r for r in filtered if any(keyword in str(v or "").lower() for v in r.values())]
    return filtered


def _group_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(_txt(row.get("project_id")), _txt(row.get("rfq_item_ref")))] .append(row)
    return dict(sorted(groups.items(), key=lambda item: (item[0][0], item[0][1])))


def _comparison_table_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    sorted_rows = sorted(
        rows,
        key=lambda r: (
            _price(r) is None,
            _price(r) if _price(r) is not None else 10**12,
            _txt(r.get("supplier_code")),
        ),
    )
    for r in sorted_rows:
        output.append(
            {
                "Supplier Code": _txt(r.get("supplier_code")),
                "Supplier Name": _txt(r.get("supplier_name")),
                "Unit Cost": _money(r.get("supplier_unit_cost"), r.get("currency")),
                "Currency": _txt(r.get("currency")),
                "MOQ": _txt(r.get("moq")),
                "Lead Time": _txt(r.get("lead_time")),
                "Price Term": _txt(r.get("price_term")),
                "Tooling Cost": _money(r.get("tooling_cost"), r.get("currency")),
                "Quote Date": _txt(r.get("quote_date")),
                "Recommended": "Yes" if _boolish(r.get("recommended_supplier")) else "No",
                "Selected": "Yes" if _boolish(r.get("selected_supplier")) else "No",
                "Quality": _txt(r.get("quotation_quality")),
                "Risk": _txt(r.get("quotation_risk")),
                "Remarks": _txt(r.get("remarks")),
            }
        )
    return output


def _required_quote_fields() -> list[tuple[str, str]]:
    return [
        ("supplier_unit_cost", "Price"),
        ("currency", "Currency"),
        ("moq", "MOQ"),
        ("lead_time", "Lead Time"),
        ("quote_date", "Quote Date"),
        ("supplier_code", "Supplier Code"),
        ("supplier_name", "Supplier Name"),
    ]


def _completeness(row: dict[str, Any]) -> tuple[int, list[str], str]:
    missing = [label for field, label in _required_quote_fields() if not _txt(row.get(field), "")]
    if not _is_supplier_matched(row):
        # This is a review flag rather than a hard missing field. Keep it visible.
        missing.append("Supplier Master Match")
    total = len(_required_quote_fields()) + 1
    score = int(round((total - len(missing)) / total * 100)) if total else 0
    explicit_risk = _txt(row.get("quotation_risk"), "")
    if explicit_risk:
        risk = explicit_risk
    elif _price(row) is None or "Supplier Master Match" in missing:
        risk = "High"
    elif len(missing) >= 3:
        risk = "Medium"
    elif missing:
        risk = "Low"
    else:
        risk = "Low"
    return max(0, score), missing, risk


def _build_completeness_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        score, missing, risk = _completeness(r)
        out.append(
            {
                "Project ID": _txt(r.get("project_id")),
                "RFQ Item Ref": _txt(r.get("rfq_item_ref")),
                "Supplier Code": _txt(r.get("supplier_code")),
                "Supplier Name": _txt(r.get("supplier_name")),
                "Unit Cost": _money(r.get("supplier_unit_cost"), r.get("currency")),
                "MOQ": _txt(r.get("moq")),
                "Lead Time": _txt(r.get("lead_time")),
                "Quote Date": _txt(r.get("quote_date")),
                "Supplier Matched": "Yes" if _is_supplier_matched(r) else "Review",
                "Completeness": f"{score}%",
                "Risk": risk,
                "Missing / Review Points": ", ".join(missing) if missing else "-",
            }
        )
    return out


def _build_saving_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for (project_id, rfq_item_ref), group in _group_rows(rows).items():
        priced = [r for r in group if _price(r) is not None]
        if not priced:
            out.append(
                {
                    "Project ID": project_id,
                    "RFQ Item Ref": rfq_item_ref,
                    "Suppliers": len(group),
                    "Lowest Supplier": "-",
                    "Lowest Price": "-",
                    "Highest Price": "-",
                    "Average Price": "-",
                    "Price Gap": "-",
                    "Saving %": "-",
                    "Review": "No valid price",
                }
            )
            continue
        prices = [_price(r) for r in priced if _price(r) is not None]
        assert prices
        low = min(prices)
        high = max(prices)
        avg = sum(prices) / len(prices)
        low_row = next(r for r in priced if _price(r) == low)
        gap = high - low
        saving = (gap / high * 100) if high else 0
        out.append(
            {
                "Project ID": project_id,
                "RFQ Item Ref": rfq_item_ref,
                "Suppliers": len(group),
                "Lowest Supplier": _txt(low_row.get("supplier_code")) or _txt(low_row.get("supplier_name")),
                "Lowest Price": _money(low, low_row.get("currency")),
                "Highest Price": _money(high, low_row.get("currency")),
                "Average Price": _money(avg, low_row.get("currency")),
                "Price Gap": _money(gap, low_row.get("currency")),
                "Saving %": f"{saving:.1f}%" if len(prices) > 1 else "-",
                "Review": "Single quote only" if len(prices) == 1 else "-",
            }
        )
    return out


def _table(data: list[dict[str, Any]], *, key: str) -> None:
    if not data:
        st.info("No records to display.")
        return
    df = pd.DataFrame(data)
    # Keep Excel/Arrow rendering safe by converting object-like values to display strings.
    for col in df.columns:
        df[col] = df[col].map(lambda v: "-" if v is None else str(v))
    st.dataframe(df, hide_index=True, width="stretch", key=key)


def _render_item_cards(rows: list[dict[str, Any]]) -> None:
    grouped = _group_rows(rows)
    if not grouped:
        st.info("No matching supplier quote records.")
        return
    for (project_id, item_ref), group in grouped.items():
        prices = [_price(r) for r in group if _price(r) is not None]
        supplier_count = len({_txt(r.get("supplier_code")) or _txt(r.get("supplier_name")) for r in group})
        lowest = min(prices) if prices else None
        highest = max(prices) if prices else None
        gap = (highest - lowest) if lowest is not None and highest is not None else None
        gap_pct = (gap / highest * 100) if gap is not None and highest else None
        risks = [_completeness(r)[2] for r in group]
        high_risk_count = sum(1 for r in risks if str(r).lower() == "high")
        title = f"{project_id} / {item_ref}"
        caption = (
            f"Suppliers: {supplier_count} | Lowest: {_money(lowest, group[0].get('currency'))} | "
            f"Gap: {f'{gap_pct:.1f}%' if gap_pct is not None and len(prices) > 1 else '-'} | High risk: {high_risk_count}"
        )
        with st.expander(f"{title} — {caption}", expanded=False):
            _table(_comparison_table_rows(group), key=f"compare_{project_id}_{item_ref}")


rows = list_module_records("Supplier Price Comparison", limit=5000)
completed = sum(1 for r in rows if str(r.get("comparison_status") or "").lower() == "completed")
selected = sum(1 for r in rows if _boolish(r.get("selected_supplier")))
recommended = sum(1 for r in rows if _boolish(r.get("recommended_supplier")))
projects = len({r.get("project_id") for r in rows if r.get("project_id")})
items = len({(r.get("project_id"), r.get("rfq_item_ref")) for r in rows if r.get("project_id") and r.get("rfq_item_ref")})
suppliers = len({_txt(r.get("supplier_code"), "") or _txt(r.get("supplier_name"), "") for r in rows if (_txt(r.get("supplier_code"), "") or _txt(r.get("supplier_name"), ""))})
render_metric_grid(
    {
        "Quote Records": len(rows),
        "Projects": projects,
        "Item Groups": items,
        "Suppliers": suppliers,
        "Selected": selected,
        "Recommended": recommended,
        "Completed": completed,
        "In Progress": max(0, len(rows) - completed),
    }
)

with st.expander("Add supplier quote", expanded=False):
    with st.form("supplier_quote_form"):
        c1, c2, c3 = st.columns(3)
        project_id = c1.text_input("Project ID")
        rfq_item_ref = c2.text_input("RFQ Item Ref")
        quote_round = c3.text_input("Quote Round", value="1")
        c1, c2, c3 = st.columns(3)
        supplier_code = c1.text_input("Supplier Code")
        supplier_name = c2.text_input("Supplier Name")
        quote_date = c3.date_input("Quote Date", value=None)
        c1, c2, c3, c4 = st.columns(4)
        supplier_unit_cost = c1.number_input("Supplier Unit Cost", min_value=0.0, step=0.01, value=0.0)
        currency = c2.text_input("Currency", value="USD")
        price_term = c3.text_input("Price Term")
        lead_time = c4.text_input("Lead Time")
        c1, c2 = st.columns(2)
        recommended_supplier = c1.checkbox("Recommended Supplier")
        selected_supplier = c2.checkbox("Selected Supplier")
        with st.expander("Risk / missing info", expanded=False):
            quotation_quality = st.selectbox("Quotation Quality", ["", "Complete", "Partial", "Poor"])
            quotation_risk = st.selectbox("Quotation Risk", ["", "Low", "Medium", "High"])
            missing_info = st.text_area("Missing Information", height=80)
            selection_reason = st.text_area("Selection Reason", height=80)
        remarks = st.text_area("Remarks", height=80)
        submitted = st.form_submit_button("Save Supplier Quote", type="primary")
        if submitted:
            if not project_id.strip() or not rfq_item_ref.strip() or not supplier_name.strip():
                st.error("Project ID, RFQ Item Ref and Supplier Name are required.")
            else:
                upsert_module_record(
                    "Supplier Price Comparison",
                    {
                        "project_id": project_id,
                        "rfq_item_ref": rfq_item_ref,
                        "supplier_code": supplier_code,
                        "supplier_name": supplier_name,
                        "quote_round": quote_round,
                        "quote_date": quote_date.isoformat() if quote_date else None,
                        "supplier_unit_cost": supplier_unit_cost,
                        "currency": currency,
                        "price_term": price_term,
                        "lead_time": lead_time,
                        "recommended_supplier": recommended_supplier,
                        "selected_supplier": selected_supplier,
                        "quotation_quality": quotation_quality,
                        "quotation_risk": quotation_risk,
                        "missing_info": missing_info,
                        "selection_reason": selection_reason,
                        "remarks": remarks,
                    },
                    operator=operator,
                )
                st.success("Supplier quote saved.")
                st.rerun()

filtered = _apply_filters(rows)

st.markdown("---")
view_tab, risk_tab, saving_tab, raw_tab = st.tabs(
    [
        "1. Project / Item / Supplier Comparison",
        "2. Quote Completeness / Risk",
        "3. Price Difference / Saving",
        "Raw Records",
    ]
)

with view_tab:
    st.markdown("### Project → Item → Supplier comparison")
    st.caption("Main working view. Each RFQ Item Ref groups supplier quotations under the same Project ID.")
    _render_item_cards(filtered)

with risk_tab:
    st.markdown("### Quote completeness and risk view")
    st.caption("Shows whether each supplier quote has the minimum information needed for usable comparison.")
    risk_rows = _build_completeness_rows(filtered)
    high_count = sum(1 for r in risk_rows if r.get("Risk") == "High")
    review_count = sum(1 for r in risk_rows if r.get("Supplier Matched") == "Review")
    render_metric_grid({"Rows Checked": len(risk_rows), "High Risk": high_count, "Supplier Review": review_count, "Ready / Low Risk": sum(1 for r in risk_rows if r.get("Risk") == "Low")})
    _table(risk_rows, key="price_risk_table")

with saving_tab:
    st.markdown("### Price difference and saving view")
    st.caption("Highlights lowest supplier, highest supplier and potential saving range for each Project ID + RFQ Item Ref.")
    saving_rows = _build_saving_rows(filtered)
    _table(saving_rows, key="price_saving_table")

with raw_tab:
    st.markdown("### Raw supplier price records")
    st.caption("Original extension records are kept here for audit and troubleshooting.")
    render_layered_records(
        "Supplier Price Comparison",
        filtered,
        key_prefix="price_page",
        summary_field="comparison_status",
        preview_columns=[
            "project_id",
            "rfq_item_ref",
            "supplier_code",
            "supplier_name",
            "quote_round",
            "supplier_unit_cost",
            "currency",
            "moq",
            "lead_time",
            "recommended_supplier",
            "selected_supplier",
            "comparison_status",
        ],
    )
