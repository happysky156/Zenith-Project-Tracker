# Index History Export Update

Scope: Index Center UI only.

Changes:
- Added a read-only Excel export button in `pages/12_Index_Center.py`.
- The button exports all loaded Daily Market Indices history to `.xlsx`.
- Workbook sheets:
  - `Read Me`
  - `Daily Index History`
  - `Latest Index Summary`
  - `Index Config`
- Export does not write to database and does not change any fetch, calculation, manual override, carry-forward, Index Snapshot, or business logic.
- Increased the page read limit for daily index rows from 3,000 to 100,000 for export coverage.

Unchanged:
- FX fetching
- Metal fetching
- Plastic fetching
- Freight manual + carry-forward
- Sales / Operation / Project Detail / Lifecycle
- Login / View more / Manual Timeline
