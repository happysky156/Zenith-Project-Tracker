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

CPO_21CP_BASE_URL = "https://intl.21cp.com"

# Plastic index policy:
# - Source: China Plastics Online / 中塑在线 (21cp.com)
# - Public pages are used as a safe reference for East China market average prices.
# - Each plastic index uses its own symbol page and broad expected range so a
#   wrong field cannot be written as a false Success.
PLASTIC_INDEX_MAP: dict[str, dict[str, Any]] = {
    "PVC": {
        "url": "https://intl.21cp.com/avg_area/list/-PVC.html",
        "keywords": ["PVC", "PVC by Calcium Carbide Process", "PVC by Vinyl Process"],
        "preferred_labels": ["PVC"],
        "expected_min": Decimal("3000"),
        "expected_max": Decimal("20000"),
        "source_label": "China Plastics Online East China PVC market average price reference",
        "official_reference": "21cp.com PVC market average price",
    },
    "PP": {
        "url": "https://intl.21cp.com/avg_area/list/-PP.html",
        "keywords": ["PP", "Injection PP", "Raffia PP", "Fibre PP", "Transparent PP"],
        "preferred_labels": ["PP", "Injection PP"],
        "expected_min": Decimal("4000"),
        "expected_max": Decimal("25000"),
        "source_label": "China Plastics Online East China PP market average price reference",
        "official_reference": "21cp.com PP market average price",
    },
    "ABS": {
        "url": "https://intl.21cp.com/avg_area/list/-ABS.html",
        "keywords": ["Mid to high end domestically produced ABS", "Mid to low end domestically produced ABS", "Imported ABS", "ABS"],
        "preferred_labels": ["Mid to high end domestically produced ABS", "Mid to low end domestically produced ABS"],
        "expected_min": Decimal("6000"),
        "expected_max": Decimal("40000"),
        "source_label": "China Plastics Online East China ABS market average price reference",
        "official_reference": "21cp.com ABS market average price",
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
    {"index_code": "PP", "index_name": "PP", "display_name": "PP", "index_category": "Plastic", "unit": "CNY/ton", "source_name": "China Plastics Online / 21cp.com", "source_url": "https://intl.21cp.com/avg_area/list/-PP.html", "fetch_enabled": 1, "fetch_method": "Web Parse", "fallback_method": "Carry Forward", "active": 1},
    {"index_code": "PVC", "index_name": "PVC", "display_name": "PVC", "index_category": "Plastic", "unit": "CNY/ton", "source_name": "China Plastics Online / 21cp.com", "source_url": "https://intl.21cp.com/avg_area/list/-PVC.html", "fetch_enabled": 1, "fetch_method": "Web Parse", "fallback_method": "Carry Forward", "active": 1},
    {"index_code": "ABS", "index_name": "ABS", "display_name": "ABS", "index_category": "Plastic", "unit": "CNY/ton", "source_name": "China Plastics Online / 21cp.com", "source_url": "https://intl.21cp.com/avg_area/list/-ABS.html", "fetch_enabled": 1, "fetch_method": "Web Parse", "fallback_method": "Carry Forward", "active": 1},
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


def _plastic_expected_range(meta: dict[str, Any]) -> tuple[Decimal, Decimal]:
    return Decimal(str(meta.get("expected_min") or "0")), Decimal(str(meta.get("expected_max") or "999999999"))


def _validate_plastic_value(index_code: str, value: Decimal | None) -> tuple[bool, str | None]:
    if value is None:
        return False, "No value parsed."
    meta = PLASTIC_INDEX_MAP.get(index_code, {})
    expected_min, expected_max = _plastic_expected_range(meta)
    if not (expected_min <= value <= expected_max):
        return False, f"Parsed value {value} outside expected range {expected_min}-{expected_max} CNY/ton."
    return True, None


def _extract_21cp_price(text: str, meta: dict[str, Any]) -> tuple[Decimal | None, str | None, str | None]:
    """Extract a plastic market-average price from a 21cp.com page.

    The English intl.21cp pages are intentionally preferred because their text
    is stable and includes clear lines like:
      PP / 8000 yuan/ton ... Date Updated: 2026-03-04
      PVC / 5300 yuan/ton ... Date Updated: 2026-03-19
      Mid to high end domestically produced ABS / 14450 yuan/ton ...

    The parser only selects numbers followed by yuan/ton and validates the
    final value against an index-specific range.
    """
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    joined = "\n".join(lines)
    expected_min, expected_max = _plastic_expected_range(meta)
    labels = list(meta.get("preferred_labels") or []) + list(meta.get("keywords") or [])

    def find_price_in_context(context: str) -> tuple[Decimal | None, str | None]:
        # Prefer values explicitly followed by yuan/ton. This avoids selecting
        # change amounts, dates, percentages, phone numbers, or page links.
        for raw in re.findall(r"(?<![A-Za-z])([0-9][0-9,]*(?:\.[0-9]+)?)\s*yuan\s*/\s*ton", context, flags=re.IGNORECASE):
            value = _safe_decimal(raw)
            if value is not None and expected_min <= value <= expected_max:
                return value, context[:500]
        # Some pages may translate or compact the unit; fallback to a tight
        # window but still use the broad price range.
        candidates = _extract_price_candidates(context, expected_min, expected_max)
        value = _select_representative_price(candidates)
        if value is not None:
            return value, context[:500]
        return None, None

    for label in labels:
        if not label:
            continue
        for idx, line in enumerate(lines):
            if label == line or label in line:
                context = " ".join(lines[idx: idx + 4])
                value, ctx = find_price_in_context(context)
                if value is not None:
                    return value, _extract_source_pub_time_from_fields([context]), ctx
        pos = joined.find(label)
        if pos >= 0:
            context = joined[pos: pos + 700]
            value, ctx = find_price_in_context(context)
            if value is not None:
                return value, _extract_source_pub_time_from_fields([context]), ctx

    return None, None, None


def _fetch_21cp_plastic_quotes() -> dict[str, FetchResult]:
    """Fetch PP/PVC/ABS reference prices from China Plastics Online (21cp.com)."""
    results: dict[str, FetchResult] = {}
    for index_code, meta in PLASTIC_INDEX_MAP.items():
        url = str(meta.get("url") or "")
        try:
            html = _http_get_text(url)
            text = _normalise_web_text(html)
            value, pub_time, context = _extract_21cp_price(text, meta)
            ok, validation_error = _validate_plastic_value(index_code, value)
            if not ok:
                raise RuntimeError(validation_error or "21cp parsed value failed validation.")
            results[index_code] = FetchResult(
                value=value,
                status="Success",
                fetch_method="Web Parse",
                source_pub_time=pub_time,
                raw_payload={
                    "source": "China Plastics Online / 21cp.com",
                    "source_url": url,
                    "parsed_context": context,
                    "source_label": meta.get("source_label"),
                    "official_reference": meta.get("official_reference"),
                    "value_source": "21cp.com East China market average price parsed from product-specific page.",
                },
            )
        except Exception as exc:
            results[index_code] = FetchResult(
                value=None,
                status="Failed",
                fetch_method="Web Parse",
                error_message=f"21cp plastic fetch failed: {type(exc).__name__}: {exc}",
                raw_payload={
                    "source": "China Plastics Online / 21cp.com",
                    "source_url": url,
                    "source_label": meta.get("source_label"),
                    "official_reference": meta.get("official_reference"),
                },
            )
    return results


def _fetch_plastic_values(target_date: str | None = None) -> dict[str, FetchResult]:
    """Fetch plastic reference values from 21cp.com.

    ``target_date`` is accepted for the common fetch API. The public pages show
    the latest market-average price available for each plastic category; the
    page's own Date Updated field is captured as source_pub_time when present.
    """
    return _fetch_21cp_plastic_quotes()


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

    plastic_configs = [
        cfg for cfg in configs
        if cfg.get("index_code") in PLASTIC_INDEX_MAP
        and str(cfg.get("fetch_method") or "").strip().lower() in {"web parse", "automatic parse", "api"}
    ]
    plastic_results: dict[str, FetchResult] = {}
    if plastic_configs:
        plastic_results = _fetch_plastic_values(target_date=target_date)

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
        elif index_code in plastic_results:
            results[index_code] = plastic_results[index_code]
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
    _ensure_index_alert_schema()
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
        # Generate internal alert events after the daily values are written.
        # This is safe and read-only with respect to index values/snapshots.
        try:
            alert_summary = run_index_alert_evaluation(target_date=target_date, operator=operator)
            summary["alert_events"] = alert_summary.get("events", 0)
        except Exception as alert_exc:
            summary["alert_error"] = str(alert_exc)
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

# -----------------------------------------------------------------------------
# Index alert rules / events and quotation snapshot locking
# -----------------------------------------------------------------------------

def _ensure_index_alert_schema() -> None:
    """Ensure extension tables exist before alert/snapshot helpers run.

    This keeps Index Center and GitHub Actions safe when they are opened before
    another extension page has initialised the schema.
    """
    try:
        from database.schema import init_extension_db
        init_extension_db()
    except Exception:
        # The caller will still surface any real table/column error from its own
        # read/write step.  Avoid hiding the original problem with an init error.
        pass


def _alert_thresholds_for_category(category: Any) -> tuple[float, float]:
    text = str(category or "").strip().lower()
    if text == "fx":
        return 0.5, 1.0
    if text in {"metal", "plastic"}:
        return 3.0, 5.0
    if text == "freight":
        return 5.0, 10.0
    return 3.0, 5.0


def _normalise_alert_type(value: Any) -> str:
    text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    if "baseline" in text:
        return "Fixed Baseline"
    if "snapshot" in text:
        return "Snapshot Deviation"
    if "daily" in text:
        return "Daily Change"
    return str(value or "").strip() or "Snapshot Deviation"


def _normalise_direction(value: Any) -> str:
    text = str(value or "Both").strip().lower()
    if text in {"up", "increase", "higher"}:
        return "Up"
    if text in {"down", "decrease", "lower"}:
        return "Down"
    return "Both"


def ensure_default_index_alert_rules() -> None:
    """Seed safe default alert rules without overwriting user thresholds.

    First version policy:
    - Snapshot Deviation rules are active by default because they protect locked
      client quotations against market movement.
    - Fixed Baseline rules are created inactive by default; users enable them
      after setting a manual baseline value.
    - Daily Change is already visible in the current index table, so no default
      Daily Change event rule is created here.
    """
    _ensure_index_alert_schema()
    configs = list_index_configs()
    if not configs:
        return

    conn = get_connection()
    try:
        cols = get_table_columns(conn, "index_alert_rules")
        if not cols:
            return
        cur = conn.cursor()
        now = _now_iso()
        for cfg in configs:
            index_code = _normalise_code(cfg.get("index_code") or cfg.get("index_name"))
            if not index_code:
                continue
            medium, high = _alert_thresholds_for_category(cfg.get("index_category"))
            for alert_type, active in [("Snapshot Deviation", 1), ("Fixed Baseline", 0)]:
                execute(
                    cur,
                    "select * from index_alert_rules where index_code = ? and alert_type = ? limit 1",
                    (index_code, alert_type),
                )
                existing = _fetchone(cur)
                if existing:
                    continue
                row = {
                    "alert_rule_id": _new_id("IDXALR"),
                    "index_code": index_code,
                    "index_name": cfg.get("display_name") or cfg.get("index_name") or index_code,
                    "index_category": cfg.get("index_category"),
                    "alert_type": alert_type,
                    "direction": "Both",
                    "medium_threshold_percent": medium,
                    "high_threshold_percent": high,
                    "baseline_value": None,
                    "active": active,
                    "remarks": "Default rule. Fixed Baseline stays inactive until a baseline value is set.",
                    "created_at": now,
                    "created_by": "System",
                    "updated_at": now,
                    "updated_by": "System",
                }
                insert_cols = [c for c in row if c in cols]
                placeholders = ", ".join(["?" for _ in insert_cols])
                execute(cur, f"insert into index_alert_rules ({', '.join(insert_cols)}) values ({placeholders})", [row[c] for c in insert_cols])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_index_alert_rules(include_inactive: bool = True) -> list[dict[str, Any]]:
    ensure_default_index_alert_rules()
    conn = get_connection()
    try:
        cols = get_table_columns(conn, "index_alert_rules")
        if not cols:
            return []
        cur = conn.cursor()
        sql = "select * from index_alert_rules"
        params: list[Any] = []
        if not include_inactive and "active" in cols:
            sql += " where coalesce(active, 0) = 1"
        sql += " order by index_category, index_code, alert_type"
        execute(cur, sql, params)
        return _fetchall(cur)
    finally:
        conn.close()


def save_index_alert_rule(rule: dict[str, Any], operator: str = "User") -> str:
    """Create/update one alert rule from Index Center.

    This only changes alert configuration. It never changes daily index values
    or locked quotation snapshots.
    """
    _ensure_index_alert_schema()
    conn = get_connection()
    try:
        cols = get_table_columns(conn, "index_alert_rules")
        if not cols:
            raise RuntimeError("Table index_alert_rules was not found or has no columns.")
        now = _now_iso()
        index_code = _normalise_code(rule.get("index_code"))
        alert_type = _normalise_alert_type(rule.get("alert_type"))
        if not index_code:
            raise ValueError("Index Code is required.")
        if not alert_type:
            raise ValueError("Alert Type is required.")
        cur = conn.cursor()
        execute(cur, "select * from index_alert_rules where index_code = ? and alert_type = ? limit 1", (index_code, alert_type))
        existing = _fetchone(cur)
        row = {
            "alert_rule_id": existing.get("alert_rule_id") if existing else _new_id("IDXALR"),
            "index_code": index_code,
            "index_name": rule.get("index_name") or index_code,
            "index_category": rule.get("index_category"),
            "alert_type": alert_type,
            "direction": _normalise_direction(rule.get("direction")),
            "medium_threshold_percent": _safe_float(rule.get("medium_threshold_percent")),
            "high_threshold_percent": _safe_float(rule.get("high_threshold_percent")),
            "baseline_value": _safe_float(rule.get("baseline_value")),
            "active": 1 if _truthy(rule.get("active"), default=True) else 0,
            "remarks": rule.get("remarks"),
            "updated_at": now,
            "updated_by": operator,
        }
        if not existing:
            row["created_at"] = now
            row["created_by"] = operator
            insert_cols = [c for c in row if c in cols]
            placeholders = ", ".join(["?" for _ in insert_cols])
            execute(cur, f"insert into index_alert_rules ({', '.join(insert_cols)}) values ({placeholders})", [row[c] for c in insert_cols])
        else:
            update_cols = [c for c in row if c in cols and c != "alert_rule_id"]
            set_sql = ", ".join([f"{c} = ?" for c in update_cols])
            execute(cur, f"update index_alert_rules set {set_sql} where alert_rule_id = ?", [row[c] for c in update_cols] + [existing.get("alert_rule_id")])
        conn.commit()
        return str(row["alert_rule_id"])
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _is_rule_active(rule: dict[str, Any]) -> bool:
    return _truthy(rule.get("active"), default=False)


def _rule_matches_direction(rule: dict[str, Any], change_percent: float | None) -> bool:
    if change_percent is None:
        return False
    direction = _normalise_direction(rule.get("direction"))
    if direction == "Up" and change_percent <= 0:
        return False
    if direction == "Down" and change_percent >= 0:
        return False
    return True


def _alert_level(rule: dict[str, Any], change_percent: float | None) -> str | None:
    if change_percent is None:
        return None
    if not _rule_matches_direction(rule, change_percent):
        return None
    magnitude = abs(float(change_percent))
    high = _safe_float(rule.get("high_threshold_percent"))
    medium = _safe_float(rule.get("medium_threshold_percent"))
    if high is not None and magnitude >= high:
        return "High"
    if medium is not None and magnitude >= medium:
        return "Medium"
    return None


def _rule_lookup(rules: list[dict[str, Any]], alert_type: str) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for rule in rules:
        if not _is_rule_active(rule):
            continue
        if _normalise_alert_type(rule.get("alert_type")) != alert_type:
            continue
        lookup[_normalise_code(rule.get("index_code"))] = rule
    return lookup


def _latest_index_lookup() -> dict[str, dict[str, Any]]:
    return {str(row.get("index_code") or ""): row for row in latest_daily_indices() if row.get("index_code")}


def _upsert_index_alert_event(event: dict[str, Any], operator: str = "System") -> str:
    _ensure_index_alert_schema()
    conn = get_connection()
    try:
        cols = get_table_columns(conn, "index_alert_events")
        if not cols:
            raise RuntimeError("Table index_alert_events was not found or has no columns.")
        cur = conn.cursor()
        # One alert per day/type/index/snapshot-or-project/baseline combination.
        where = ["alert_date = ?", "alert_type = ?", "index_code = ?"]
        params: list[Any] = [event.get("alert_date"), event.get("alert_type"), event.get("index_code")]
        for col in ["related_snapshot_id", "related_project_id", "related_client_quote_id", "related_quote_version"]:
            if col in cols:
                val = event.get(col)
                if val in (None, ""):
                    where.append(f"({col} is null or {col} = '')")
                else:
                    where.append(f"{col} = ?")
                    params.append(val)
        execute(cur, f"select * from index_alert_events where {' and '.join(where)} limit 1", params)
        existing = _fetchone(cur)
        now = _now_iso()
        row = dict(event)
        row.setdefault("alert_event_id", existing.get("alert_event_id") if existing else _new_id("IDXEVT"))
        row.setdefault("alert_status", existing.get("alert_status") if existing else "New")
        row.setdefault("created_at", existing.get("created_at") if existing else now)
        row.setdefault("created_by", existing.get("created_by") if existing else operator)
        if existing:
            update_cols = [c for c in row if c in cols and c not in {"alert_event_id", "created_at", "created_by", "review_note", "reviewed_at", "reviewed_by"}]
            # Do not reopen a reviewed/closed alert just because the page re-evaluates.
            if str(existing.get("alert_status") or "").lower() in {"reviewed", "closed"}:
                update_cols = [c for c in update_cols if c != "alert_status"]
            set_sql = ", ".join([f"{c} = ?" for c in update_cols])
            if set_sql:
                execute(cur, f"update index_alert_events set {set_sql} where alert_event_id = ?", [row[c] for c in update_cols] + [existing.get("alert_event_id")])
        else:
            insert_cols = [c for c in row if c in cols]
            placeholders = ", ".join(["?" for _ in insert_cols])
            execute(cur, f"insert into index_alert_events ({', '.join(insert_cols)}) values ({placeholders})", [row[c] for c in insert_cols])
        conn.commit()
        return str(row.get("alert_event_id"))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_index_alert_events(limit: int = 1000, project_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    _ensure_index_alert_schema()
    conn = get_connection()
    try:
        cols = get_table_columns(conn, "index_alert_events")
        if not cols:
            return []
        where: list[str] = []
        params: list[Any] = []
        if project_id and "related_project_id" in cols:
            where.append("related_project_id = ?")
            params.append(project_id)
        if status and "alert_status" in cols:
            where.append("alert_status = ?")
            params.append(status)
        sql = "select * from index_alert_events"
        if where:
            sql += " where " + " and ".join(where)
        sql += " order by alert_date desc, alert_level desc, created_at desc limit ?"
        params.append(limit)
        cur = conn.cursor()
        execute(cur, sql, params)
        return _fetchall(cur)
    finally:
        conn.close()


def update_index_alert_event_status(alert_event_id: str, status: str, review_note: str, operator: str = "User") -> None:
    _ensure_index_alert_schema()
    conn = get_connection()
    try:
        cols = get_table_columns(conn, "index_alert_events")
        if not cols:
            return
        updates = {"alert_status": status, "review_note": review_note, "reviewed_at": _now_iso(), "reviewed_by": operator}
        updates = {k: v for k, v in updates.items() if k in cols}
        if not updates:
            return
        set_sql = ", ".join([f"{k} = ?" for k in updates])
        cur = conn.cursor()
        execute(cur, f"update index_alert_events set {set_sql} where alert_event_id = ?", list(updates.values()) + [alert_event_id])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _read_all_index_snapshots() -> list[dict[str, Any]]:
    _ensure_index_alert_schema()
    conn = get_connection()
    try:
        cols = get_table_columns(conn, "index_snapshots")
        if not cols:
            return []
        cur = conn.cursor()
        order_col = "locked_at" if "locked_at" in cols else "snapshot_date"
        execute(cur, f"select * from index_snapshots order by {order_col} desc")
        return _fetchall(cur)
    finally:
        conn.close()


def _snapshot_points(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    # New unified snapshot columns.
    if snapshot.get("index_code") and snapshot.get("snapshot_value") not in (None, ""):
        points.append({
            "index_code": _normalise_code(snapshot.get("index_code")),
            "index_name": snapshot.get("index_display_name") or snapshot.get("index_code"),
            "index_category": snapshot.get("index_category"),
            "reference_value": _safe_float(snapshot.get("snapshot_value")),
            "unit": snapshot.get("snapshot_unit"),
            "snapshot": snapshot,
        })
        return points

    # Compatibility with older dedicated columns.
    legacy_candidates = [
        (snapshot.get("exchange_rate_pair"), snapshot.get("exchange_rate_value"), "FX", "rate"),
        (snapshot.get("material_index_name"), snapshot.get("material_index_value"), "Material", snapshot.get("material_index_unit")),
        (snapshot.get("freight_index_name") or snapshot.get("freight_route"), snapshot.get("freight_index_value"), "Freight", snapshot.get("freight_unit")),
    ]
    for name, value, category, unit in legacy_candidates:
        ref = _safe_float(value)
        if name and ref is not None:
            points.append({
                "index_code": _normalise_code(name),
                "index_name": name,
                "index_category": category,
                "reference_value": ref,
                "unit": unit,
                "snapshot": snapshot,
            })
    return points


def _calc_percent(latest_value: float | None, reference_value: float | None) -> tuple[float | None, float | None]:
    if latest_value is None or reference_value is None:
        return None, None
    change_value = latest_value - reference_value
    if reference_value == 0:
        return change_value, None
    return change_value, (change_value / reference_value) * 100


def run_index_alert_evaluation(target_date: str | None = None, operator: str = "System") -> dict[str, int]:
    """Evaluate Fixed Baseline and Snapshot Deviation rules and write events.

    Daily Change is already visible in Daily Market Indices; users can enable it
    later by adding Daily Change rules, but the first system focus is quotation
    risk control through Fixed Baseline and Snapshot Deviation.
    """
    target_date = target_date or today_local()
    ensure_default_index_alert_rules()
    rules = list_index_alert_rules(include_inactive=False)
    latest = _latest_index_lookup()
    summary = {"rules": len(rules), "fixed_baseline": 0, "snapshot_deviation": 0, "events": 0}

    # Fixed Baseline rules: latest value vs user-maintained baseline.
    for rule in rules:
        alert_type = _normalise_alert_type(rule.get("alert_type"))
        if alert_type != "Fixed Baseline":
            continue
        index_code = _normalise_code(rule.get("index_code"))
        latest_row = latest.get(index_code)
        baseline = _safe_float(rule.get("baseline_value"))
        latest_value = _safe_float((latest_row or {}).get("value"))
        change_value, change_percent = _calc_percent(latest_value, baseline)
        level = _alert_level(rule, change_percent)
        if not level:
            continue
        _upsert_index_alert_event({
            "alert_date": target_date,
            "alert_type": "Fixed Baseline",
            "index_code": index_code,
            "index_name": rule.get("index_name") or (latest_row or {}).get("display_name") or index_code,
            "index_category": rule.get("index_category") or (latest_row or {}).get("index_category"),
            "alert_level": level,
            "direction": "Up" if (change_percent or 0) > 0 else "Down",
            "reference_value": baseline,
            "latest_value": latest_value,
            "change_value": change_value,
            "change_percent": change_percent,
            "alert_status": "New",
            "source_note": "Latest index value compared with manual baseline value.",
        }, operator=operator)
        summary["fixed_baseline"] += 1
        summary["events"] += 1

    # Snapshot Deviation rules: latest value vs locked quotation snapshot.
    snapshot_rules = _rule_lookup(rules, "Snapshot Deviation")
    if snapshot_rules:
        for snapshot in _read_all_index_snapshots():
            for point in _snapshot_points(snapshot):
                index_code = _normalise_code(point.get("index_code"))
                rule = snapshot_rules.get(index_code)
                latest_row = latest.get(index_code)
                if not rule or not latest_row:
                    continue
                latest_value = _safe_float(latest_row.get("value"))
                reference_value = _safe_float(point.get("reference_value"))
                change_value, change_percent = _calc_percent(latest_value, reference_value)
                level = _alert_level(rule, change_percent)
                if not level:
                    continue
                _upsert_index_alert_event({
                    "alert_date": target_date,
                    "alert_type": "Snapshot Deviation",
                    "index_code": index_code,
                    "index_name": point.get("index_name") or latest_row.get("display_name") or index_code,
                    "index_category": rule.get("index_category") or latest_row.get("index_category") or point.get("index_category"),
                    "alert_level": level,
                    "direction": "Up" if (change_percent or 0) > 0 else "Down",
                    "reference_value": reference_value,
                    "latest_value": latest_value,
                    "change_value": change_value,
                    "change_percent": change_percent,
                    "related_project_id": snapshot.get("project_id"),
                    "related_client_quote_id": snapshot.get("client_quote_id"),
                    "related_quote_version": snapshot.get("quote_version"),
                    "related_snapshot_id": snapshot.get("index_snapshot_id"),
                    "alert_status": "New",
                    "source_note": "Latest index value compared with locked client quotation snapshot.",
                }, operator=operator)
                summary["snapshot_deviation"] += 1
                summary["events"] += 1
    return summary


def lock_client_quotation_index_snapshots(
    client_quote: dict[str, Any],
    selected_indices: list[str],
    operator: str = "User",
    rfq_item_ref: str | None = None,
    snapshot_date: str | None = None,
) -> dict[str, int]:
    """Lock current index values for one client quotation.

    Existing snapshots for the same quote/index are not overwritten.  Historical
    quotation evidence remains fixed even when Daily Market Indices change later.
    """
    _ensure_index_alert_schema()
    snapshot_date = snapshot_date or today_local()
    selected_codes = {_normalise_code(code) for code in selected_indices if _normalise_code(code)}
    if not selected_codes:
        return {"created": 0, "skipped_existing": 0, "missing_latest": 0}
    latest = _latest_index_lookup()
    conn = get_connection()
    summary = {"created": 0, "skipped_existing": 0, "missing_latest": 0}
    try:
        cols = get_table_columns(conn, "index_snapshots")
        if not cols:
            raise RuntimeError("Table index_snapshots was not found or has no columns.")
        cur = conn.cursor()
        now = _now_iso()
        project_id = client_quote.get("project_id")
        client_quote_id = client_quote.get("client_quote_id")
        quote_version = client_quote.get("quote_version")
        for index_code in selected_codes:
            latest_row = latest.get(index_code)
            if not latest_row or _safe_float(latest_row.get("value")) is None:
                summary["missing_latest"] += 1
                continue
            # Prevent duplicate locked snapshot for the same quote/index.
            duplicate_found = False
            if "index_code" in cols:
                execute(
                    cur,
                    "select 1 from index_snapshots where client_quote_id = ? and project_id = ? and coalesce(quote_version, '') = coalesce(?, '') and index_code = ? limit 1",
                    (client_quote_id, project_id, quote_version, index_code),
                )
                duplicate_found = cur.fetchone() is not None
            if duplicate_found:
                summary["skipped_existing"] += 1
                continue
            display_name = latest_row.get("display_name") or index_code
            category = latest_row.get("index_category")
            value = _safe_float(latest_row.get("value"))
            unit = latest_row.get("unit")
            row = {
                "index_snapshot_id": _new_id("SNAP"),
                "client_quote_id": client_quote_id,
                "project_id": project_id,
                "rfq_item_ref": rfq_item_ref,
                "quote_version": quote_version,
                "snapshot_date": snapshot_date,
                "index_code": index_code,
                "index_category": category,
                "index_display_name": display_name,
                "snapshot_value": value,
                "snapshot_unit": unit,
                "snapshot_source_status": latest_row.get("fetch_status"),
                "source_name": latest_row.get("source_name"),
                "source_url": latest_row.get("source_url"),
                "locked_at": now,
                "locked_by": operator,
                "remarks": "Locked from Client Quotation page. Daily Market Indices after this date will not change this snapshot.",
            }
            # Fill legacy columns so existing pages can still read the snapshot.
            if str(category or "").lower() == "fx":
                row.update({"exchange_rate_pair": display_name, "exchange_rate_value": value, "exchange_rate_source": latest_row.get("source_name")})
            elif str(category or "").lower() == "freight":
                row.update({"freight_index_name": display_name, "freight_index_value": value, "freight_route": display_name, "freight_unit": unit})
            else:
                row.update({"material_index_name": display_name, "material_index_value": value, "material_index_unit": unit})
            insert_cols = [c for c in row if c in cols]
            placeholders = ", ".join(["?" for _ in insert_cols])
            execute(cur, f"insert into index_snapshots ({', '.join(insert_cols)}) values ({placeholders})", [row[c] for c in insert_cols])
            summary["created"] += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    # New snapshots may immediately trigger deviation alerts if already outside thresholds.
    try:
        run_index_alert_evaluation(target_date=snapshot_date, operator=operator)
    except Exception:
        pass
    return summary
