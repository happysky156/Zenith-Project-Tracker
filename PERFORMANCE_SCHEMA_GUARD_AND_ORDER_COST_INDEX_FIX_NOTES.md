# v18 Performance Fix - Schema Guard + Order Cost Indexing

## Purpose

This update fixes the slow loading that can reappear after deploying schema compatibility changes to Streamlit Cloud + Supabase.

## What changed

1. Extension schema initialisation now has a fast readiness check.
   - If the critical v18 columns already exist, the app skips the heavy full extension DDL path.
   - This avoids repeated remote `information_schema` checks and index creation attempts after each reboot.

2. Order Details financial display now fetches only relevant Order Costs.
   - Earlier code could fetch many/all Order Costs even when only 100-300 Order Details rows were shown.
   - The new logic filters cost rows by the visible order numbers/project IDs.

3. Order Cost matching is now pre-aggregated.
   - Earlier batch logic still scanned all cost rows for each order detail row.
   - The new logic builds cost summary dictionaries first, then calculates each row in O(1) style.

4. Fixed USD conversion remains unchanged.
   - USD is kept as USD.
   - RMB/CNY is converted using fixed rate 1 USD = 6.80 CNY.
   - Order Costs are also converted to USD before Gross Profit calculation.

5. No core business data is changed.
   - Sales / Operation / Meeting Mode logic is not changed.
   - Existing records are not deleted or overwritten.

## Recommended deployment step

After uploading to GitHub, run:

```text
Manage app -> Reboot app
```

Then test:

1. Order Details page
2. Project Detail -> Order Details / Order Costs tabs
3. Client Quotation page
4. Project Detail -> History / Client Quotation tabs

Expected result: normal pages should not hang for minutes.
