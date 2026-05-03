# Order Details Speed Fix

## Purpose

This version fixes the Order Details page loading issue where the page could stay blank for several minutes on Streamlit Cloud + Supabase.

## Root cause

The previous Order Details display path recalculated each Order Detail row by querying Order Costs separately. This created an N+1 database query pattern:

```text
1 query to load Order Details
+ 1 query per Order Detail row to load matching Order Costs
```

On a remote PostgreSQL/Supabase deployment, this can be very slow and can also increase connection pressure.

## Fix

- Order Costs are now fetched once in batch for Order Details display.
- Extra Cost and Gross Profit are calculated in Python memory for the loaded rows.
- The existing business rule is kept:
  - Order-level costs with blank Order Item Code are still included.
  - Item-level costs with matching Order Item Code are included.
  - Order Details with blank Order Item Code keep the previous broad matching behaviour.
- Fixed currency conversion is kept:
  - `1 USD = 6.80 RMB / CNY`
  - RMB/CNY amounts are converted to USD.
  - Order Costs are also converted to USD.
- The Order Details page now defaults to loading 300 recent rows, with an option to increase to 100 / 300 / 500 / 1000 / 2000 rows.
- A small load-time caption is shown so performance can be checked directly on the page.

## What was not changed

- No Sales Board logic changed.
- No Operation Board logic changed.
- No Meeting Mode logic changed.
- No existing business records are deleted or overwritten by this performance fix.
- The fixed USD conversion rule remains unchanged.
