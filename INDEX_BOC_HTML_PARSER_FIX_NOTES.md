# Index BOC HTML Parser Fix

## Scope
Only fixes the Bank of China FX parser used by Index Center / daily index fetch.

## Issue fixed
Streamlit Cloud log showed:

`BOC fetch failed: FileNotFoundError: [Errno 2] No such file or directory: <!DOCTYPE html ...>`

The BOC page was fetched successfully, but the parser passed the raw HTML string directly into `pandas.read_html`. In the current pandas environment, the raw HTML string was treated like a file path.

## Fix
- Replaced the fragile `pd.read_html(response.text)` path with a BeautifulSoup parser.
- Parser targets the BOC table with `id="priceTable"`.
- USD / HKD / GBP are parsed from the table rows.
- Middle Rate is still divided by 100 and stored as:
  - 1 USD = X CNY
  - 1 HKD = X CNY
  - 1 GBP = X CNY

## Unchanged
- Freight Israel / Morocco remains Manual + Carry Forward.
- Material indices remain in the automatic parse framework.
- Unique-key duplicate protection remains.
- Login, Sales Board, Operation Board, Project Detail timeline and all other business logic are unchanged.
