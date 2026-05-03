# Schema Index Compatibility Fix

## Problem fixed

Streamlit Cloud showed this error when opening Supplier Details:

```text
psycopg.errors.UndefinedColumn: column "index_name" does not exist
```

The error came from `database/schema.py` during extension database initialisation.
The previous static index SQL tried to create this index:

```sql
CREATE INDEX IF NOT EXISTS idx_daily_indices_date_name
ON daily_market_indices(index_date, index_name);
```

However, the market-index tables created in Supabase for the automatic fetch pipeline use the newer schema:

```text
index_code / value / display_name
```

not the older extension schema:

```text
index_name / index_value
```

## Code change

Updated `database/schema.py` so extension indexes are created only when the target table and target columns actually exist.

This makes the code compatible with both table shapes:

- New Supabase market-index schema: `index_code`, `value`
- Older extension/local schema: `index_name`, `index_value`

## Safety

This fix does **not**:

- delete any data
- drop any table
- add fake `index_name` columns to your Supabase table
- change Supplier Details business logic
- change Project / Order / Meeting Mode logic

It only makes schema initialisation skip incompatible index definitions safely.

## Files changed

```text
database/schema.py
SCHEMA_INDEX_COMPATIBILITY_FIX_NOTES.md
```
