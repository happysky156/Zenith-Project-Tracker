# Index Center Negative Value Display Fix

## Scope

This update only adjusts `pages/12_Index_Center.py`.

## Fix

- Converts Index Center numeric display columns (`value`, `previous_value`, `change_value`, `change_percent`) to numeric floats before Streamlit display/export.
- Adds consistent Streamlit column formatting for index numeric columns.
- Fixes small negative values such as `-0.0066` being displayed incorrectly as `0.0-66`.

## Not changed

- No database schema changes.
- No fetch logic changes.
- No index calculation logic changes.
- No GitHub Actions workflow changes.
- No Price Comparison / AI Project Assistant / Supplier / Order logic changes.
