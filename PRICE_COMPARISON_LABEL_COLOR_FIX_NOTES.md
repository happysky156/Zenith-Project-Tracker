# Price Comparison Label Colour Fix

## Scope

This update only changes the compact item caption display in `pages/10_Price_Comparison.py`.

## Change

- Added `_colored_money()` helper for Streamlit-coloured money values in expander captions.
- Updated the RFQ Item Ref / ITM compact caption so the labels stay normal and only the money values are coloured:
  - `Lowest: :green[$19.12]`
  - `Highest: :green[$19.12]`

## Unchanged

- Price Comparison calculations
- Project Unit Total logic
- Selection Decisions
- Import logic
- Supplier / Index / Order / AI Project Assistant logic
- Database schema
