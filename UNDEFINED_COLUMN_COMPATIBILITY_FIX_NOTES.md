# UndefinedColumn Compatibility Fix Notes

This package fixes the `psycopg.errors.UndefinedColumn` error shown in Project Detail extension tabs and the Client Quotation page.

## Cause

Some Supabase databases may already contain extension tables created by earlier builds, especially `index_snapshots` / market-index related tables. `CREATE TABLE IF NOT EXISTS` does not add new columns to existing tables, so the app could later query fields such as `project_id`, `index_snapshot_id`, or quotation fields that were not present in the older table shape.

## Fix

1. Added an additive extension-column migration step during extension initialisation.
2. Missing columns are added safely with `ALTER TABLE ... ADD COLUMN`.
3. Existing rows are not deleted, overwritten, or migrated destructively.
4. `list_module_records()` now checks existing columns before applying filters or ordering.
5. If a table is still not in the expected shape, the relevant extension view returns an empty list instead of crashing the page.
6. Related-supplier lookups now skip incompatible extension queries instead of breaking the whole Project Detail page.

## Business logic unchanged

- Sales Board unchanged.
- Operation Board unchanged.
- Meeting Mode unchanged.
- Existing Project Detail core fields unchanged.
- Fixed USD conversion remains unchanged: `1 USD = 6.80 RMB/CNY`.
- Order Costs still convert to USD and participate in gross profit calculation.
- `rfq_item_ref` and `order_item_code` naming remains unchanged.

## Deployment note

After uploading this package to GitHub, reboot the Streamlit Cloud app once so the additive migration can run cleanly.
