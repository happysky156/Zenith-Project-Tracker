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


def main() -> None:
    if not os.getenv("DATABASE_URL") and not os.getenv("database_url"):
        print("WARNING: DATABASE_URL is not set. The script will use the app's configured fallback if available.")

    summary = run_daily_index_fetch(operator="GitHub Actions")
    print("Daily market index fetch completed.")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
