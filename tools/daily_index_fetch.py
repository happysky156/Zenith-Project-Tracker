from __future__ import annotations

"""
Daily Index Fetch
---------------------
Recommended deployment pattern for Streamlit Cloud:
- GitHub Actions runs this script every day.
- The script writes one daily row per configured index into Supabase/PostgreSQL.
- Streamlit only displays, confirms, or manually overrides values.

Current behaviour is deliberately conservative:
- It seeds the fixed index list if missing.
- It carries forward yesterday's value for any active index that does not have a new value.
- External parsers can be added inside fetch_external_value() for fixed sources.

Required environment variable in GitHub Actions:
- DATABASE_URL: PostgreSQL/Supabase connection string.
"""

from datetime import date
from pathlib import Path
import os
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.schema import init_db
from services.upgrade_service import carry_forward_daily_indices, list_module_records, seed_default_index_config, upsert_module_record


def fetch_external_value(config: dict[str, Any]) -> tuple[float | None, str | None]:
    """Return (value, error_message).

    Automatic web parsing stays off by default because material/FX pages can
    change format or require subscriptions. Add fixed-source parsers here after
    your team confirms the exact source and field to read.
    """
    if not int(config.get("fetch_enabled") or 0):
        return None, "fetch_enabled is off; use carry-forward/manual value"
    return None, "no parser configured for this index yet"


def main() -> None:
    if not os.getenv("DATABASE_URL") and not os.getenv("database_url"):
        print("WARNING: DATABASE_URL is not set. The script will use local SQLite if run locally.")

    init_db(force=True)
    seed_default_index_config()
    target_date = date.today().isoformat()

    configs = [row for row in list_module_records("Index Config", limit=500) if int(row.get("active") or 0) == 1]
    success = 0
    failed = 0
    for cfg in configs:
        value, error = fetch_external_value(cfg)
        if value is None:
            failed += 1
            continue
        upsert_module_record(
            "Daily Market Indices",
            {
                "index_date": target_date,
                "index_category": cfg.get("index_category"),
                "index_name": cfg.get("index_name"),
                "index_value": value,
                "unit": cfg.get("unit"),
                "source_name": cfg.get("source_name"),
                "source_url": cfg.get("source_url"),
                "fetch_method": cfg.get("fetch_method") or "API",
                "fetch_status": "Success",
            },
            operator="GitHub Actions",
        )
        success += 1

    carry = carry_forward_daily_indices(target_date=target_date, operator="GitHub Actions")
    print(
        f"Daily index fetch completed for {target_date}. "
        f"Fetched: {success}, no-parser/failed: {failed}, carried-forward-created: {carry.get('created', 0)}, skipped: {carry.get('skipped', 0)}"
    )


if __name__ == "__main__":
    main()
