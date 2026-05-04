from __future__ import annotations

"""Market index service for Zenith Project Tracker.

This module is intentionally isolated from the main Sales / Operation logic.
It reads the existing index_config table, fetches supported public data, and
writes daily rows to daily_market_indices.

Compatibility note:
The project has used two index table shapes during upgrades:
1) Extension schema: index_name / index_value / daily_index_id
2) Direct schema:    index_code / value / id
The helpers below detect the available columns at runtime so the daily job and
Index Center can work with either shape without changing existing business data.
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation
import re
import uuid
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

try:
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover
    Jsonb = None  # type: ignore

from database.connection import execute, get_connection, using_postgres

BOC_EXCHANGE_RATE_URL = "https://www.bankofchina.com/sourcedb/whpj/enindex_1619.html"
SUPPORTED_BOC_CURRENCIES = {"USD", "HKD", "GBP"}
SMM_BASE_URL = "https://hq.smm.cn"
SMM_STEEL_URL = "https://steel.smm.cn/steel/107"
CCMN_BASE_URL = "https://m.ccmn.cn"

# Metal index policy:
# - Primary auto source: Shanghai Metals Market (SMM / 上海有色网).
# - Fallback auto source: Changjiang Nonferrous Metals Network (CCMN / 长江有色金属网).
# - Each index uses its own page/keywords and an expected value range so a
#   wrong field cannot be written as a false Success.
METAL_INDEX_MAP: dict[str, dict[str, Any]] = {
    "STAINLESS_STEEL_304": {
        "smm_url": "https://hq.smm.cn/h5/sus-304sus-price",
        "smm_keywords": ["304/2B卷不锈钢全国均价", "304/2B卷-毛边无锡不锈钢价格", "304/NO.1卷不锈钢价格", "304/No.1卷无锡不锈钢价格"],
        "ccmn_url": "https://m.ccmn.cn/mbxg/304/",
        "ccmn_keywords": ["304", "不锈钢"],
        "expected_min": Decimal("8000"),
        "expected_max": Decimal("40000"),
        "source_label": "SMM 304 stainless steel spot reference; fallback: Changjiang Nonferrous Metals Network",
        "official_reference": "SMM / Changjiang 304 stainless steel spot reference",
    },
    "CARBON_STEEL": {
        "smm_url": "https://steel.smm.cn/steel/107",
        "smm_keywords": ["SMM中国热轧板卷价格指数", "全国热卷均价", "热轧板卷"],
        "ccmn_url": "https://m.ccmn.cn/mzhuanti/jinsjy/",
        "ccmn_keywords": ["热轧卷板", "热轧板卷", "热卷"],
        "expected_min": Decimal("1500"),
        "expected_max": Decimal("10000"),
        "source_label": "SMM hot-rolled coil / carbon steel spot reference; fallback: Changjiang Nonferrous Metals Network",
        "official_reference": "SMM hot-rolled coil / carbon steel reference",
    },
    "ZINC": {
        "smm_url": "https://hq.smm.cn/h5/zn",
        "smm_keywords": ["长江现货锌锭价格0#", "上海现货锌锭价格0#", "0#"],
        "ccmn_url": "https://m.ccmn.cn/xin/",
        "ccmn_keywords": ["长江现货", "0#锌", "锌"],
        "expected_min": Decimal("10000"),
        "expected_max": Decimal("60000"),
        "source_label": "SMM zinc spot reference; fallback: Changjiang Nonferrous Metals Network",
        "official_reference": "SMM / Changjiang zinc spot reference",
    },
    "ALUMINIUM": {
        "smm_url": "https://hq.smm.cn/h5/alu",
        "smm_keywords": ["上海铝锭价格", "长江铝锭价格", "A00铝"],
        "ccmn_url": "https://m.ccmn.cn/al/",
        "ccmn_keywords": ["长江现货", "A00铝", "铝"],
        "expected_min": Decimal("10000"),
        "expected_max": Decimal("60000"),
        "source_label": "SMM aluminium spot reference; fallback: Changjiang Nonferrous Metals Network",
        "official_reference": "SMM / Changjiang aluminium spot reference",
    },
}
LOCAL_TZ = ZoneInfo("Asia/Singapore")

DEFAULT_INDEX_CONFIGS: list[dict[str, Any]] = [
    {"index_code": "USD_CNY", "index_name": "USD/CNY", "display_name": "USD/CNY", "index_category": "FX", "unit": "rate", "source_name": "Bank of China", "source_url": BOC_EXCHANGE_RATE_URL, "fetch_enabled": 1, "fetch_method": "Web Parse", "fallback_method": "Carry Forward", "active": 1},
    {"index_code": "HKD_CNY", "index_name": "HKD/CNY", "display_name": "HKD/CNY", "index_category": "FX", "unit": "rate", "source_name": "Bank of China", "source_url": BOC_EXCHANGE_RATE_URL, "fetch_enabled": 1, "fetch_method": "Web Parse", "fallback_method": "Carry Forward", "active": 1},
    {"index_code": "GBP_CNY", "index_name": "GBP/CNY", "display_name": "GBP/CNY", "index_category": "FX", "unit": "rate", "source_name": "Bank of China", "source_url": BOC_EXCHANGE_RATE_URL, "fetch_enabled": 1, "fetch_method": "Web Parse", "fallback_method": "Carry Forward", "active": 1},
    {"index_code": "STAINLESS_STEEL_304", "index_name": "Stainless Steel 304", "display_name": "Stainless Steel 304", "index_category": "Metal", "unit": "CNY/ton", "source_name": "SMM / Changjiang Nonferrous", "source_url": "https://hq.smm.cn", "fetch_enabled": 1, "fetch_method": "Web Parse", "fallback_method": "Carry Forward", "active": 1},
    {"index_code": "CARBON_STEEL", "index_name": "Carbon Steel", "display_name": "Carbon Steel", "index_category": "Metal", "unit": "CNY/ton", "source_name": "SMM / Changjiang Nonferrous", "source_url": "https://hq.smm.cn", "fetch_enabled": 1, "fetch_method": "Web Parse", "fallback_method": "Carry Forward", "active": 1},
    {"index_code": "ZINC", "index_name": "Zinc", "display_name": "Zinc", "index_category": "Metal", "unit": "CNY/ton", "source_name": "SMM / Changjiang Nonferrous", "source_url": "https://hq.smm.cn", "fetch_enabled": 1, "fetch_method": "Web Parse", "fallback_method": "Carry Forward", "active": 1},
    {"index_code": "ALUMINIUM", "index_name": "Aluminium", "display_name": "Aluminium", "index_category": "Metal", "unit": "CNY/ton", "source_name": "SMM / Changjiang Nonferrous", "source_url": "https://hq.smm.cn", "fetch_enabled": 1, "fetch_method": "Web Parse", "fallback_method": "Carry Forward", "active": 1},
    {"index_code": "PP", "index_name": "PP", "display_name": "PP", "index_category": "Plastic", "unit": "CNY/ton", "source_name": "DCE", "source_url": "", "fetch_enabled": 1, "fetch_method": "Web Parse", "fallback_method": "Carry Forward", "active": 1},
    {"index_code": "PVC", "index_name": "PVC", "display_name": "PVC", "index_category": "Plastic", "unit": "CNY/ton", "source_name": "DCE", "source_url": "", "fetch_enabled": 1, "fetch_method": "Web Parse", "fallback_method": "Carry Forward", "active": 1},
    {"index_code": "ABS", "index_name": "ABS", "display_name": "ABS", "index_category": "Plastic", "unit": "CNY/ton", "source_name": "Third-party / Manual Confirm", "source_url": "", "fetch_enabled": 1, "fetch_method": "Web Parse", "fallback_method": "Carry Forward", "active": 1},
    {"index_code": "FREIGHT_ISRAEL", "index_name": "Freight to Israel", "display_name": "Freight to Israel", "index_category": "Freight", "unit": "USD/40HQ", "source_name": "Manual / Forwarder", "source_url": "", "fetch_enabled": 0, "fetch_method": "Manual", "fallback_method": "Carry Forward", "active": 1},
    {"index_code": "FREIGHT_MOROCCO", "index_name": "Freight to Morocco", "display_name": "Freight to Morocco", "index_category": "Freight", "unit": "USD/40HQ", "source_name": "Manual / Forwarder", "source_url": "", "fetch_enabled": 0, "fetch_method": "Manual", "fallback_method": "Carry Forward", "active": 1},
]

_DEFAULT_CONFIG_SYNCED = False


@dataclass
class FetchResult:
    value: Decimal | None
    status: str
    fetch_method: str
    source_pub_time: str | None = None
    error_message: str | None = None
    raw_payload: dict[str, Any] | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today_local() -> str:
    return datetime.now(LOCAL_TZ).date().isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"


def _row_to_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    try:
        return dict(row)
    except Exception:
        return {}


def _fetchall(cur) -> list[dict[str, Any]]:
    return [_row_to_dict(row) for row in cur.fetchall()]


def _fetchone(cur) -> dict[str, Any] | None:
    row = cur.fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


def get_table_columns(conn, table_name: str) -> set[str]:
    cur = conn.cursor()
    if using_postgres():
        execute(
            cur,
            """
            select column_name
            from information_schema.columns
            where table_schema = 'public'
              and table_name = ?
            order by ordinal_position
            """,
            (table_name,),
        )
        rows = _fetchall(cur)
        return {str(row.get("column_name")) for row in rows if row.get("column_name")}

    cur.execute(f"PRAGMA table_info({table_name})")
    rows = cur.fetchall()
    return {str(row[1]) for row in rows}


def _safe_decimal(value: Any) -> Decimal | None:
    if value in (None, "", "-"):
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError, TypeError):
        return None


def _safe_float(value: Decimal | float | int | str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _truthy(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "active", "on"}:
        return True
    if text in {"0", "false", "no", "n", "inactive", "off"}:
        return False
    return default


def _normalise_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    text = text.replace("/", "_").replace(" ", "_").replace("-", "_")
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def _normalise_index_config(row: dict[str, Any]) -> dict[str, Any]:
    index_code = row.get("index_code") or row.get("index_name") or row.get("display_name")
    display_name = row.get("display_name") or row.get("index_name") or row.get("index_code")
    index_name = row.get("index_name") or display_name or index_code
    fetch_method = str(row.get("fetch_method") or "manual").strip()

    active_value = row.get("is_active") if "is_active" in row else row.get("active")

    return {
        "raw": row,
        "index_code": _normalise_code(index_code),
        "index_name": str(index_name or index_code or "").strip(),
        "display_name": str(display_name or index_name or index_code or "").strip(),
        "index_category": str(row.get("index_category") or "").strip(),
        "unit": str(row.get("unit") or "").strip(),
        "source_name": str(row.get("source_name") or "").strip(),
        "source_url": str(row.get("source_url") or "").strip(),
        "fetch_method": fetch_method,
        "fallback_method": str(row.get("fallback_method") or "carry_forward").strip(),
        "need_manual_confirm": _truthy(row.get("need_manual_confirm"), default=False),
        "active": _truthy(active_value, default=True),
    }


def ensure_default_index_configs() -> None:
    """Seed/synchronise the standard Index Center configuration.

    This is intentionally narrow and safe: it only creates missing default
    index rows and refreshes default source/fetch settings for those rows. It
    does not touch daily_market_indices or locked index_snapshots.
    """
    global _DEFAULT_CONFIG_SYNCED
    if _DEFAULT_CONFIG_SYNCED:
        return

    conn = get_connection()
    try:
        cols = get_table_columns(conn, "index_config")
        if not cols:
            return
        cur = conn.cursor()

        for cfg in DEFAULT_INDEX_CONFIGS:
            name_col = "index_code" if "index_code" in cols else "index_name"
            key_value = cfg["index_code"] if name_col == "index_code" else cfg["index_name"]
            execute(cur, f"select * from index_config where {name_col} = ? limit 1", (key_value,))
            existing = _fetchone(cur)

            row = {k: v for k, v in cfg.items() if k in cols}
            if "index_config_id" in cols and "index_config_id" not in row:
                row["index_config_id"] = existing.get("index_config_id") if existing else _new_id("IDXCFG")

            if existing:
                # Keep user-specific remarks untouched. Refresh standard fetch/source
                # settings so USD/HKD/GBP and freight behaviour stay correct.
                update_keys = [
                    k for k in row.keys()
                    if k not in {"index_config_id", "remarks"}
                ]
                if update_keys:
                    set_sql = ", ".join([f"{k} = ?" for k in update_keys])
                    pk = "index_config_id" if "index_config_id" in cols and existing.get("index_config_id") else name_col
                    pk_value = existing.get("index_config_id") if pk == "index_config_id" else key_value
                    execute(cur, f"update index_config set {set_sql} where {pk} = ?", [row[k] for k in update_keys] + [pk_value])
            else:
                insert_cols = list(row.keys())
                placeholders = ", ".join(["?" for _ in insert_cols])
                execute(cur, f"insert into index_config ({', '.join(insert_cols)}) values ({placeholders})", [row[k] for k in insert_cols])

        conn.commit()
        _DEFAULT_CONFIG_SYNCED = True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_index_configs() -> list[dict[str, Any]]:
    ensure_default_index_configs()
    conn = get_connection()
    try:
        cols = get_table_columns(conn, "index_config")
        if not cols:
            return []

        order_col = "index_category" if "index_category" in cols else next(iter(cols))
        cur = conn.cursor()
        execute(cur, f"select * from index_config order by {order_col}")
        rows = _fetchall(cur)
        configs = [_normalise_index_config(row) for row in rows]
        return [cfg for cfg in configs if cfg["active"]]
    finally:
        conn.close()


def _currency_from_config(config: dict[str, Any]) -> str | None:
    candidates = [
        config.get("index_code"),
        config.get("index_name"),
        config.get("display_name"),
    ]
    for candidate in candidates:
        text = str(candidate or "").upper().replace("_", "/").replace("-", "/")
        for currency in SUPPORTED_BOC_CURRENCIES:
            if text.startswith(currency) or f"{currency}/CNY" in text:
                return currency
    return None


def _currency_from_boc_cell(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    mapping = {
        "USD": ["USD", "US DOLLAR", "U.S. DOLLAR", "美元"],
        "HKD": ["HKD", "HK DOLLAR", "HONG KONG DOLLAR", "港币", "港幣"],
        "GBP": ["GBP", "POUND", "STERLING", "BRITISH POUND", "英镑", "英鎊"],
    }
    for currency, tokens in mapping.items():
        if any(token in text for token in tokens):
            return currency
    return None


def _parse_boc_exchange_rates(html: str | None = None) -> dict[str, dict[str, Any]]:
    """Parse Bank of China FX rates for USD/HKD/GBP.

    The Bank of China page returns a plain HTML page with a table whose id is
    usually ``priceTable``. A previous implementation passed ``response.text``
    directly into ``pandas.read_html``. In newer pandas versions, a raw HTML
    string can be treated as a file path, which caused errors like
    ``FileNotFoundError: ... <!DOCTYPE html ...>`` in Streamlit Cloud.

    This parser therefore uses BeautifulSoup first and reads the target table
    directly from the parsed DOM. It keeps the conversion rule unchanged:
    BOC middle rates are CNY per 100 units of foreign currency, so the app
    stores Middle Rate / 100 as 1 foreign currency = X CNY.
    """
    if html is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ZenithProjectTracker/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        }
        response = requests.get(BOC_EXCHANGE_RATE_URL, headers=headers, timeout=25)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        html = response.text

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="priceTable")
    if table is None:
        # Fallback: find the table that contains the expected BOC headers.
        for candidate in soup.find_all("table"):
            header_text = " ".join(candidate.get_text(" ", strip=True).split()).lower()
            if "currency name" in header_text and "middle rate" in header_text and "pub time" in header_text:
                table = candidate
                break

    if table is None:
        raise RuntimeError("No Bank of China priceTable found in fetched HTML.")

    result: dict[str, dict[str, Any]] = {}
    for tr in table.find_all("tr"):
        cells = [cell.get_text(" ", strip=True).replace("\xa0", " ").strip() for cell in tr.find_all(["td", "th"])]
        if not cells or cells[0].lower() == "currency name":
            continue
        if len(cells) < 7:
            continue

        currency = _currency_from_boc_cell(cells[0])
        if currency not in SUPPORTED_BOC_CURRENCIES:
            continue

        # BOC columns: Currency, Buying, Cash Buying, Selling, Cash Selling, Middle, Pub Time.
        middle_per_100 = _safe_decimal(cells[5])
        if middle_per_100 is None:
            continue

        value = middle_per_100 / Decimal("100")
        result[currency] = {
            "value": value,
            "source_pub_time": cells[6] if len(cells) > 6 else None,
            "raw_payload": {
                "source": "Bank of China",
                "currency": currency,
                "middle_rate_per_100": str(middle_per_100),
                "stored_value_explanation": f"1 {currency} = {value} CNY",
            },
        }

    missing = sorted(SUPPORTED_BOC_CURRENCIES - set(result.keys()))
    if missing:
        # Keep the fetch resilient: caller will mark only the missing currency as Failed.
        # Returning partial results allows USD/HKD/GBP to succeed independently.
        pass

    return result




def _extract_source_pub_time_from_fields(fields: list[str]) -> str | None:
    text = " ".join(str(item or "") for item in fields)
    date_match = re.search(r"20\d{2}[-/]\d{1,2}[-/]\d{1,2}", text)
    time_match = re.search(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", text)
    if date_match and time_match:
        return f"{date_match.group(0)} {time_match.group(0)}"
    if date_match:
        return date_match.group(0)
    short_date = re.search(r"\b\d{1,2}[-/]\d{1,2}\b", text)
    if short_date:
        return short_date.group(0)
    return None


def _normalise_web_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    text = text.replace("\xa0", " ").replace("—", "-").replace("－", "-")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text


def _metal_expected_range(meta: dict[str, Any]) -> tuple[Decimal, Decimal]:
    return Decimal(str(meta.get("expected_min") or "0")), Decimal(str(meta.get("expected_max") or "999999999"))


def _extract_price_candidates(text: str, expected_min: Decimal, expected_max: Decimal) -> list[Decimal]:
    # Remove dates and percentage fields first so year/month/day and percent
    # changes cannot be selected as prices.
    cleaned = re.sub(r"20\d{2}[-/]\d{1,2}[-/]\d{1,2}", " ", text)
    cleaned = re.sub(r"\b\d{1,2}[-/]\d{1,2}\b", " ", cleaned)
    cleaned = re.sub(r"[+-]?\d+(?:\.\d+)?\s*%", " ", cleaned)
    candidates: list[Decimal] = []
    for raw in re.findall(r"(?<![A-Za-z])[-+]?\d[\d,]*(?:\.\d+)?(?![A-Za-z])", cleaned):
        # Price changes are often explicit +50 / -90. They are far below the
        # metal price range, but skip signed values anyway for extra safety.
        if raw.strip().startswith(("+", "-")):
            continue
        value = _safe_decimal(raw)
        if value is not None and expected_min <= value <= expected_max:
            candidates.append(value)
    return candidates


def _select_representative_price(candidates: list[Decimal]) -> Decimal | None:
    if not candidates:
        return None
    # For spot-price rows, a common pattern is: low, high, average. Prefer the
    # average when it appears as the third value and sits between low/high.
    if len(candidates) >= 3:
        low, high, avg = candidates[0], candidates[1], candidates[2]
        if min(low, high) <= avg <= max(low, high):
            return avg
        # Some SMM index rows repeat the same value three times.
        if low == high == avg:
            return avg
    return candidates[0]


def _extract_price_from_keyword_context(text: str, keywords: list[str], meta: dict[str, Any]) -> tuple[Decimal | None, str | None, str | None]:
    expected_min, expected_max = _metal_expected_range(meta)
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    joined = "\n".join(lines)

    for keyword in keywords:
        if not keyword:
            continue
        # First try line-based context, which works for both SMM mobile pages
        # and CCMN mobile pages.
        for idx, line in enumerate(lines):
            if keyword in line:
                context = " ".join(lines[idx: idx + 10])
                candidates = _extract_price_candidates(context, expected_min, expected_max)
                value = _select_representative_price(candidates)
                if value is not None:
                    return value, _extract_source_pub_time_from_fields([context]), context[:500]

        # Fallback to a regex window around the keyword for pages where the
        # text is minified into one long line.
        pos = joined.find(keyword)
        if pos >= 0:
            context = joined[pos: pos + 900]
            candidates = _extract_price_candidates(context, expected_min, expected_max)
            value = _select_representative_price(candidates)
            if value is not None:
                return value, _extract_source_pub_time_from_fields([context]), context[:500]

    return None, None, None


def _validate_metal_value(index_code: str, value: Decimal | None) -> tuple[bool, str | None]:
    if value is None:
        return False, "No value parsed."
    meta = METAL_INDEX_MAP.get(index_code, {})
    expected_min, expected_max = _metal_expected_range(meta)
    if not (expected_min <= value <= expected_max):
        return False, f"Parsed value {value} outside expected range {expected_min}-{expected_max} CNY/ton."
    return True, None


def _http_get_text(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ZenithProjectTracker/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
    }
    response = requests.get(url, headers=headers, timeout=25)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def _fetch_smm_metal_quotes() -> dict[str, FetchResult]:
    """Fetch metal spot-reference values from Shanghai Metals Market (SMM).

    The parser is intentionally conservative. It searches for an index-specific
    row keyword and validates the parsed price against a broad expected range.
    A wrong field or page-change therefore becomes Failed/Carry Forward instead
    of a false Success.
    """
    results: dict[str, FetchResult] = {}
    for index_code, meta in METAL_INDEX_MAP.items():
        url = str(meta.get("smm_url") or "")
        try:
            html = _http_get_text(url)
            text = _normalise_web_text(html)
            value, pub_time, context = _extract_price_from_keyword_context(text, meta.get("smm_keywords") or [], meta)
            ok, validation_error = _validate_metal_value(index_code, value)
            if not ok:
                raise RuntimeError(validation_error or "SMM parsed value failed validation.")
            results[index_code] = FetchResult(
                value=value,
                status="Success",
                fetch_method="Web Parse",
                source_pub_time=pub_time,
                raw_payload={
                    "source": "SMM / Shanghai Metals Market",
                    "source_url": url,
                    "parsed_context": context,
                    "source_label": meta.get("source_label"),
                    "official_reference": meta.get("official_reference"),
                    "value_source": "SMM spot reference price parsed from index-specific row keywords.",
                },
            )
        except Exception as exc:
            results[index_code] = FetchResult(
                value=None,
                status="Failed",
                fetch_method="Web Parse",
                error_message=f"SMM metal fetch failed: {type(exc).__name__}: {exc}",
                raw_payload={
                    "source": "SMM / Shanghai Metals Market",
                    "source_url": url,
                    "source_label": meta.get("source_label"),
                    "official_reference": meta.get("official_reference"),
                },
            )
    return results


def _fetch_ccmn_metal_quotes() -> dict[str, FetchResult]:
    """Fallback fetch from Changjiang Nonferrous Metals Network (CCMN)."""
    results: dict[str, FetchResult] = {}
    for index_code, meta in METAL_INDEX_MAP.items():
        url = str(meta.get("ccmn_url") or "")
        try:
            html = _http_get_text(url)
            text = _normalise_web_text(html)
            value, pub_time, context = _extract_price_from_keyword_context(text, meta.get("ccmn_keywords") or [], meta)
            ok, validation_error = _validate_metal_value(index_code, value)
            if not ok:
                raise RuntimeError(validation_error or "CCMN parsed value failed validation.")
            results[index_code] = FetchResult(
                value=value,
                status="Success",
                fetch_method="Web Parse",
                source_pub_time=pub_time,
                raw_payload={
                    "source": "Changjiang Nonferrous Metals Network",
                    "source_url": url,
                    "parsed_context": context,
                    "source_label": meta.get("source_label"),
                    "official_reference": meta.get("official_reference"),
                    "value_source": "CCMN fallback spot reference price parsed from index-specific row keywords.",
                },
            )
        except Exception as exc:
            results[index_code] = FetchResult(
                value=None,
                status="Failed",
                fetch_method="Web Parse",
                error_message=f"CCMN metal fetch failed: {type(exc).__name__}: {exc}",
                raw_payload={
                    "source": "Changjiang Nonferrous Metals Network",
                    "source_url": url,
                    "source_label": meta.get("source_label"),
                    "official_reference": meta.get("official_reference"),
                },
            )
    return results


def _fetch_metal_values(target_date: str | None = None) -> dict[str, FetchResult]:
    """Fetch metal reference values with SMM primary and CCMN fallback.

    ``target_date`` is accepted for the common fetch API; public pages normally
    publish the latest spot reference. The captured source publish date/time is
    saved when it can be parsed from the page.
    """
    smm_results = _fetch_smm_metal_quotes()
    final: dict[str, FetchResult] = {}

    missing_or_failed = [
        code for code in METAL_INDEX_MAP
        if code not in smm_results or smm_results[code].value is None
    ]

    ccmn_results: dict[str, FetchResult] = {}
    if missing_or_failed:
        ccmn_results = _fetch_ccmn_metal_quotes()

    for index_code, meta in METAL_INDEX_MAP.items():
        primary = smm_results.get(index_code)
        if primary and primary.value is not None:
            final[index_code] = primary
            continue

        fallback = ccmn_results.get(index_code)
        if fallback and fallback.value is not None:
            final[index_code] = fallback
            continue

        messages = []
        if primary and primary.error_message:
            messages.append(primary.error_message)
        if fallback and fallback.error_message:
            messages.append(fallback.error_message)
        final[index_code] = FetchResult(
            value=None,
            status="Failed",
            fetch_method="Web Parse",
            error_message=" | ".join(messages) or f"No SMM/CCMN metal quote found for {index_code}.",
            raw_payload={
                "source": "SMM primary; Changjiang Nonferrous Metals Network fallback",
                "source_label": meta.get("source_label"),
                "official_reference": meta.get("official_reference"),
            },
        )
    return final


def fetch_external_values(configs: list[dict[str, Any]], target_date: str | None = None) -> dict[str, FetchResult]:
    """Fetch external values once per source and return result by index_code."""
    results: dict[str, FetchResult] = {}

    fx_configs = [cfg for cfg in configs if str(cfg.get("index_category") or "").upper() == "FX"]
    needed_boc = [cfg for cfg in fx_configs if _currency_from_config(cfg) in SUPPORTED_BOC_CURRENCIES]

    boc_rates: dict[str, dict[str, Any]] = {}
    boc_error: str | None = None
    if needed_boc:
        try:
            boc_rates = _parse_boc_exchange_rates()
        except Exception as exc:  # keep the daily job resilient
            boc_error = f"BOC fetch failed: {type(exc).__name__}: {exc}"

    metal_configs = [
        cfg for cfg in configs
        if cfg.get("index_code") in METAL_INDEX_MAP
        and str(cfg.get("fetch_method") or "").strip().lower() in {"web parse", "automatic parse", "api"}
    ]
    metal_results: dict[str, FetchResult] = {}
    if metal_configs:
        metal_results = _fetch_metal_values(target_date=target_date)

    for cfg in configs:
        index_code = cfg["index_code"]
        currency = _currency_from_config(cfg)
        if str(cfg.get("index_category") or "").upper() == "FX" and currency in SUPPORTED_BOC_CURRENCIES:
            if boc_error:
                results[index_code] = FetchResult(None, "Failed", "Web Parse", error_message=boc_error)
            else:
                rate = boc_rates.get(currency)
                if rate:
                    results[index_code] = FetchResult(
                        value=rate["value"],
                        status="Success",
                        fetch_method="Web Parse",
                        source_pub_time=rate.get("source_pub_time"),
                        raw_payload=rate.get("raw_payload"),
                    )
                else:
                    results[index_code] = FetchResult(None, "Failed", "Web Parse", error_message=f"{currency} not found in BOC result.")
        elif index_code in metal_results:
            results[index_code] = metal_results[index_code]
        elif str(cfg.get("index_category") or "").upper() == "FREIGHT" or str(cfg.get("fetch_method") or "").lower() == "manual":
            results[index_code] = FetchResult(
                value=None,
                status="Manual Required",
                fetch_method="Manual",
                error_message="Freight is maintained manually. Add a manual value or let the system carry forward the previous value.",
            )
        else:
            results[index_code] = FetchResult(
                value=None,
                status="Failed",
                fetch_method=str(cfg.get("fetch_method") or "Web Parse"),
                error_message=f"Automatic parser for {cfg.get('display_name') or index_code} is not enabled yet. Use carry-forward or manual override.",
            )

    return results


def _daily_columns() -> set[str]:
    conn = get_connection()
    try:
        return get_table_columns(conn, "daily_market_indices")
    finally:
        conn.close()


def _daily_key_columns(cols: set[str]) -> tuple[str, str]:
    value_col = "index_value" if "index_value" in cols else "value"
    # Prefer index_code whenever it exists. Some Supabase installs have both
    # index_code and index_name, while the unique constraint is on
    # (index_date, index_code). Looking up by index_name first can miss an
    # existing row and then cause a duplicate-key error on insert.
    name_col = "index_code" if "index_code" in cols else "index_name"
    return name_col, value_col


def _read_daily_numeric_value(row: dict[str, Any]) -> Any:
    """Return the first non-empty daily index numeric value across schemas."""
    for key in ("value", "index_value"):
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    return row.get("index_value") if "index_value" in row else row.get("value")


def _daily_order_column(cols: set[str]) -> str:
    if "updated_at" in cols:
        return "updated_at"
    if "last_updated_at" in cols:
        return "last_updated_at"
    if "created_at" in cols:
        return "created_at"
    return "index_date"


def get_previous_daily_value(conn, cols: set[str], config: dict[str, Any], target_date: str) -> Decimal | None:
    name_col, value_col = _daily_key_columns(cols)
    order_col = _daily_order_column(cols)
    key_value = config["index_name"] if name_col == "index_name" else config["index_code"]

    cur = conn.cursor()
    if "value" in cols and "index_value" in cols:
        value_expr = "COALESCE(value, index_value)"
        not_null_expr = "(value is not null or index_value is not null)"
    else:
        value_expr = value_col
        not_null_expr = f"{value_col} is not null"

    execute(
        cur,
        f"""
        select {value_expr} as previous_value
        from daily_market_indices
        where {name_col} = ?
          and index_date < ?
          and {not_null_expr}
        order by index_date desc, {order_col} desc
        limit 1
        """,
        (key_value, target_date),
    )
    row = _fetchone(cur)
    return _safe_decimal(row.get("previous_value")) if row else None


def _calculate_change(value: Decimal | None, previous: Decimal | None) -> tuple[Decimal | None, Decimal | None]:
    if value is None or previous is None:
        return None, None
    change = value - previous
    if previous == 0:
        return change, None
    return change, (change / previous) * Decimal("100")


def _find_existing_daily_row(conn, cols: set[str], config: dict[str, Any], target_date: str) -> dict[str, Any] | None:
    """Return an existing daily row for this index/date using the safest key.

    During the upgrade history, daily_market_indices may contain index_code,
    index_name, or both. Newer tables enforce uniqueness on (index_date,
    index_code), so we check index_code first when it exists. We still fall
    back to index_name/display_name to remain compatible with older rows.
    """
    cur = conn.cursor()
    candidates: list[tuple[str, Any]] = []
    if "index_code" in cols and config.get("index_code"):
        candidates.append(("index_code", config.get("index_code")))
    if "index_name" in cols and config.get("index_name"):
        candidates.append(("index_name", config.get("index_name")))
    if "display_name" in cols and config.get("display_name"):
        candidates.append(("display_name", config.get("display_name")))

    seen: set[tuple[str, str]] = set()
    for col, val in candidates:
        key = (col, str(val))
        if key in seen:
            continue
        seen.add(key)
        execute(
            cur,
            f"select * from daily_market_indices where index_date = ? and {col} = ? limit 1",
            (target_date, val),
        )
        row = _fetchone(cur)
        if row:
            return row
    return None


def _is_manual_row(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    status = str(row.get("fetch_status") or "").strip().lower()
    if status == "manual":
        return True
    if _truthy(row.get("is_manual_override"), default=False):
        return True
    return False


def _update_or_insert_daily(conn, cols: set[str], config: dict[str, Any], target_date: str, result: FetchResult, operator: str, protect_manual: bool = True) -> str:
    existing = _find_existing_daily_row(conn, cols, config, target_date)
    if protect_manual and _is_manual_row(existing):
        return "skipped_manual"

    previous = get_previous_daily_value(conn, cols, config, target_date)
    value = result.value

    # If no new value is available, carry forward the last available value.
    if value is None and previous is not None:
        value = previous
        status = "Carry Forward"
        error_message = result.error_message or "No new value; carried forward from previous available record."
        fetch_method = "Carry Forward"
    elif value is None:
        status = result.status if result.status in {"Manual Required", "Need Confirm"} else "Failed"
        error_message = result.error_message or "No value found and no previous value available."
        fetch_method = result.fetch_method or "Manual"
    else:
        status = result.status or "Success"
        error_message = result.error_message
        fetch_method = result.fetch_method or "Web Parse"

    change_value, change_percent = _calculate_change(value, previous)
    now = _now_iso()

    row: dict[str, Any] = {}

    # Direct/raw schema support.
    if "index_code" in cols:
        row.update(
            {
                "index_date": target_date,
                "index_code": config["index_code"],
                "index_category": config.get("index_category"),
                "display_name": config.get("display_name") or config.get("index_name"),
                "unit": config.get("unit"),
                "source_name": (result.raw_payload or {}).get("source") or config.get("source_name") or ("Bank of China" if str(config.get("index_category") or "").upper() == "FX" else ""),
                "source_url": (result.raw_payload or {}).get("source_url") or config.get("source_url") or (BOC_EXCHANGE_RATE_URL if str(config.get("index_category") or "").upper() == "FX" else ""),
                "source_pub_time": result.source_pub_time,
                "fetch_method": fetch_method,
                "fetch_status": status,
                "error_message": error_message,
                "is_manual_override": False,
                "is_confirmed": status == "Success" and not config.get("need_manual_confirm"),
                "previous_value": _safe_float(previous),
                "change_value": _safe_float(change_value),
                "change_percent": _safe_float(change_percent),
                "updated_at": now,
            }
        )
        # Keep both possible numeric columns in sync. Some Supabase upgrade
        # paths have index_code + index_value, some have index_code + value,
        # and some have both. If only one is populated, the UI can show
        # fetch_status=Success but value=None.
        if "value" in cols:
            row["value"] = _safe_float(value)
        if "index_value" in cols:
            row["index_value"] = _safe_float(value)
        if "confirmed_by_user" in cols:
            row["confirmed_by_user"] = 1 if status == "Success" and not config.get("need_manual_confirm") else 0
        if "updated_by" in cols:
            row["updated_by"] = operator
        if "last_updated_at" in cols:
            row["last_updated_at"] = now

        if "raw_payload" in cols:
            payload = result.raw_payload or {}
            row["raw_payload"] = Jsonb(payload) if using_postgres() and Jsonb is not None else payload
    else:
        # Extension schema support.
        row.update(
            {
                "daily_index_id": existing.get("daily_index_id") if existing else _new_id("DIDX"),
                "index_date": target_date,
                "index_category": config.get("index_category"),
                "index_name": config.get("index_name") or config.get("display_name") or config.get("index_code"),
                "index_value": _safe_float(value),
                "unit": config.get("unit"),
                "source_name": (result.raw_payload or {}).get("source") or config.get("source_name") or ("Bank of China" if str(config.get("index_category") or "").upper() == "FX" else ""),
                "source_url": (result.raw_payload or {}).get("source_url") or config.get("source_url") or (BOC_EXCHANGE_RATE_URL if str(config.get("index_category") or "").upper() == "FX" else ""),
                "source_pub_time": result.source_pub_time,
                "fetch_method": fetch_method,
                "fetch_status": status,
                "previous_value": _safe_float(previous),
                "change_value": _safe_float(change_value),
                "change_percent": _safe_float(change_percent),
                "error_message": error_message,
                "confirmed_by_user": 1 if status == "Success" and not config.get("need_manual_confirm") else 0,
                "last_updated_at": now,
                "updated_by": operator,
            }
        )

    row = {k: v for k, v in row.items() if k in cols}
    cur = conn.cursor()

    if existing:
        pk_col = "daily_index_id" if "daily_index_id" in cols else "id" if "id" in cols else None
        if pk_col and existing.get(pk_col):
            update_cols = [c for c in row.keys() if c != pk_col]
            set_sql = ", ".join([f"{c} = ?" for c in update_cols])
            params = [row[c] for c in update_cols] + [existing.get(pk_col)]
            execute(cur, f"update daily_market_indices set {set_sql} where {pk_col} = ?", params)
        else:
            name_col, _ = _daily_key_columns(cols)
            key_value = config["index_name"] if name_col == "index_name" else config["index_code"]
            update_cols = list(row.keys())
            set_sql = ", ".join([f"{c} = ?" for c in update_cols])
            params = [row[c] for c in update_cols] + [target_date, key_value]
            execute(cur, f"update daily_market_indices set {set_sql} where index_date = ? and {name_col} = ?", params)
        return "updated"

    insert_cols = list(row.keys())
    placeholders = ", ".join(["?" for _ in insert_cols])
    execute(
        cur,
        f"insert into daily_market_indices ({', '.join(insert_cols)}) values ({placeholders})",
        [row[c] for c in insert_cols],
    )
    return "created"


def run_daily_index_fetch(target_date: str | None = None, operator: str = "GitHub Actions") -> dict[str, int]:
    target_date = target_date or today_local()
    configs = list_index_configs()
    results = fetch_external_values(configs, target_date=target_date)

    summary = {
        "configs": len(configs),
        "success": 0,
        "created": 0,
        "updated": 0,
        "carry_forward": 0,
        "failed": 0,
        "manual_required": 0,
        "need_confirm": 0,
        "skipped_manual": 0,
    }

    conn = get_connection()
    try:
        cols = get_table_columns(conn, "daily_market_indices")
        if not cols:
            raise RuntimeError("Table daily_market_indices was not found or has no columns.")

        for cfg in configs:
            result = results.get(cfg["index_code"]) or FetchResult(None, "Failed", "Manual", error_message="No fetch result.")
            action = _update_or_insert_daily(conn, cols, cfg, target_date, result, operator)
            if action in {"created", "updated"}:
                summary[action] += 1
            elif action == "skipped_manual":
                summary["skipped_manual"] += 1

            # Count final status after fallback handling by reading the saved row.
            saved = _find_existing_daily_row(conn, cols, cfg, target_date)
            saved_status = str((saved or {}).get("fetch_status") or "").strip().lower()
            if saved_status == "success":
                summary["success"] += 1
            elif saved_status == "carry forward":
                summary["carry_forward"] += 1
            elif saved_status == "failed":
                summary["failed"] += 1
            elif saved_status == "manual required":
                summary["manual_required"] += 1
            elif saved_status == "need confirm":
                summary["need_confirm"] += 1

        conn.commit()
        return summary
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_daily_indices(limit: int = 2000) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        cols = get_table_columns(conn, "daily_market_indices")
        if not cols:
            return []
        order_col = _daily_order_column(cols)
        cur = conn.cursor()
        execute(
            cur,
            f"select * from daily_market_indices order by index_date desc, {order_col} desc limit ?",
            (limit,),
        )
        return _fetchall(cur)
    finally:
        conn.close()


def normalise_daily_row(row: dict[str, Any]) -> dict[str, Any]:
    index_code = row.get("index_code") or row.get("index_name") or row.get("display_name")
    display_name = row.get("display_name") or row.get("index_name") or row.get("index_code")
    value = _read_daily_numeric_value(row)
    return {
        "index_date": row.get("index_date"),
        "index_code": _normalise_code(index_code),
        "index_category": row.get("index_category"),
        "display_name": display_name,
        "value": value,
        "unit": row.get("unit"),
        "source_name": row.get("source_name"),
        "source_url": row.get("source_url"),
        "source_pub_time": row.get("source_pub_time"),
        "fetch_method": row.get("fetch_method"),
        "fetch_status": row.get("fetch_status"),
        "previous_value": row.get("previous_value"),
        "change_value": row.get("change_value"),
        "change_percent": row.get("change_percent"),
        "error_message": row.get("error_message"),
        "confirmed": row.get("is_confirmed") if "is_confirmed" in row else row.get("confirmed_by_user"),
        "last_updated_at": row.get("updated_at") or row.get("last_updated_at") or row.get("created_at"),
        "raw": row,
    }


def latest_daily_indices() -> list[dict[str, Any]]:
    rows = [normalise_daily_row(row) for row in list_daily_indices(limit=5000)]
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row.get("index_code") or str(row.get("display_name") or "")
        if key and key not in latest:
            latest[key] = row
    return list(latest.values())


def save_manual_index(config: dict[str, Any], index_date: str, value: float, source_name: str, source_url: str, operator: str) -> None:
    result = FetchResult(
        value=Decimal(str(value)),
        status="Manual",
        fetch_method="Manual",
        error_message=None,
        raw_payload={"manual_override": True, "operator": operator},
    )
    conn = get_connection()
    try:
        cols = get_table_columns(conn, "daily_market_indices")
        manual_cfg = dict(config)
        manual_cfg["source_name"] = source_name or config.get("source_name") or "Manual"
        manual_cfg["source_url"] = source_url or config.get("source_url") or ""

        # Reuse writer, then force manual flags/status for clarity.
        _update_or_insert_daily(conn, cols, manual_cfg, index_date, result, operator, protect_manual=False)
        existing = _find_existing_daily_row(conn, cols, manual_cfg, index_date)
        if existing:
            cur = conn.cursor()
            pk_col = "daily_index_id" if "daily_index_id" in cols else "id" if "id" in cols else None
            if pk_col and existing.get(pk_col):
                updates: dict[str, Any] = {"fetch_status": "Manual"}
                if "fetch_method" in cols:
                    updates["fetch_method"] = "Manual"
                if "is_manual_override" in cols:
                    updates["is_manual_override"] = True
                if "is_confirmed" in cols:
                    updates["is_confirmed"] = True
                if "confirmed_by_user" in cols:
                    updates["confirmed_by_user"] = 1
                if "confirmed_at" in cols:
                    updates["confirmed_at"] = _now_iso()
                if "updated_by" in cols:
                    updates["updated_by"] = operator
                if "last_updated_at" in cols:
                    updates["last_updated_at"] = _now_iso()
                if "updated_at" in cols:
                    updates["updated_at"] = _now_iso()

                set_sql = ", ".join([f"{k} = ?" for k in updates])
                execute(cur, f"update daily_market_indices set {set_sql} where {pk_col} = ?", list(updates.values()) + [existing.get(pk_col)])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
