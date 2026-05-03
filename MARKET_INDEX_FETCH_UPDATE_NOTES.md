# Market Index Fetch Update Notes

This package updates Step 4 to Step 10 for the Zenith Project Tracker market index pipeline.

## Updated / Added Files

1. `requirements.txt`
   - Added `beautifulsoup4`, `lxml`, and `python-dotenv` for robust table parsing and local environment support.

2. `services/market_index_service.py`
   - New shared service for market index config reading, Bank of China exchange-rate fetching, daily record writing, latest record display, and manual override.
   - Supports both table shapes used during the upgrade:
     - `index_code` / `value` style
     - `index_name` / `index_value` style

3. `tools/daily_index_fetch.py`
   - GitHub Actions / local job entry point.
   - Automatically fetches USD/CNY, HKD/CNY, and GBP/CNY from Bank of China.
   - Material, plastic, and freight records are safely carried forward when a previous value exists.
   - If there is no previous value, a Failed row is created so the Index Center clearly shows that manual input is needed.
   - Manual rows for the same date are protected from automatic overwrite.

4. `.github/workflows/daily_index_fetch.yml`
   - Runs daily at 10:30 Beijing/Singapore time.
   - Supports manual run from GitHub Actions using `workflow_dispatch`.
   - Reads `DATABASE_URL` from GitHub repository secrets.

5. `pages/12_Index_Center.py`
   - Updated Streamlit page for viewing latest index records, manually running the fetch, and manually overriding values.
   - Manual overrides are saved as Manual records and protected from automatic overwrite for the same date.

## Important Notes

- This update does not change Sales Board, Operation Board, Meeting Mode, Supplier Details, Client Quotation, or other main business logic.
- No real Supabase write test was performed in this offline package update.
- Before running GitHub Actions, make sure GitHub Repository Secrets contains `DATABASE_URL`.
- The automatic parser currently covers FX only: USD/CNY, HKD/CNY, GBP/CNY.
- SHFE / DCE metal and plastic parser logic can be added later after the exact source field is confirmed.
