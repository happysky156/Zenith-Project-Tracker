from __future__ import annotations

"""Daily market index fetch job.

Run modes:
- GitHub Actions: scheduled every day using DATABASE_URL from repository secrets.
- Local test: python tools/daily_index_fetch.py

Current automatic sources:
- Bank of China exchange-rate page for USD/CNY, HKD/CNY and GBP/CNY.
- Shanghai Metals Market (SMM) for metal indices, with Changjiang Nonferrous Metals Network (CCMN) as fallback.

Other material / plastic / freight indices are handled conservatively:
- If there is a previous value, today's row is created as Carry Forward.
- If there is no previous value, today's row is created as Failed / Manual Required
  so Index Center clearly shows that manual input is needed.
"""

from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.market_index_service import run_daily_index_fetch


def _has_database_url() -> bool:
    return bool((os.getenv("DATABASE_URL") or os.getenv("database_url") or "").strip())


def main() -> None:
    running_in_github_actions = os.getenv("GITHUB_ACTIONS", "").lower() == "true"

    if running_in_github_actions and not _has_database_url():
        raise SystemExit("DATABASE_URL is required for GitHub Actions daily index fetch.")

    if not _has_database_url():
        print(
            "WARNING: DATABASE_URL is not set. "
            "This is allowed only for local testing; production automation must use Supabase/PostgreSQL."
        )

    summary = run_daily_index_fetch(operator="GitHub Actions")
    print("Daily market index fetch completed.")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
