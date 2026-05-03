# PostgreSQL PoolTimeout Fix Notes

## Issue

The Streamlit Cloud log showed:

```text
psycopg_pool.PoolTimeout: couldn't get a connection after 20.00 sec
```

The traceback was raised from `database/connection.py` while trying to get a connection from the optional app-side `psycopg_pool`.

## Root cause

This is a database connection handling issue, not a Sales Revenue / USD conversion calculation issue.

The app was using a small client-side PostgreSQL connection pool on top of Supabase's own pooler. When several Streamlit reruns/pages tried to initialise extension tables or read extension modules at the same time, the local pool could be temporarily exhausted.

The repeated log message:

```text
rolling back returned connection: <psycopg.Connection [INTRANS] ...>
```

also means some read-only SELECT calls returned connections while a transaction was still open. This is common with psycopg, but it can flood logs and slow down connection reuse.

## Fix

`database/connection.py` has been updated:

1. The app-side psycopg connection pool is now disabled by default.
2. The app now uses short-lived direct PostgreSQL connections by default.
3. If app-side pooling is intentionally needed later, it can be enabled with:

```toml
ENABLE_POSTGRES_POOL = "true"
```

4. Pooled connections, if enabled, are rolled back before being returned to the pool so they are not returned in `INTRANS` state.
5. If the optional pool is temporarily exhausted, the app falls back to a direct PostgreSQL connection instead of failing the page.

## What did not change

This fix does not change:

- Sales / Operation core data logic
- Meeting Mode logic
- Import business logic
- Order Details business fields
- Fixed exchange rate logic
- Sales Revenue / Supplier Cost / Order Cost / Gross Profit calculation rules

## Deployment step

After uploading this package to GitHub, reboot the Streamlit Cloud app once.
