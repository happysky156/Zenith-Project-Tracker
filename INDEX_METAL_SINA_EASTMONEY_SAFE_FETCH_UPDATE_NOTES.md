# Index Metal Sina/Eastmoney Safe Fetch Update

This update changes the metal-index automatic fetch source.

## Scope

Only Index Center / Daily Index Fetch logic is changed. Login, Sales Board, Operation Board, Project Detail, lifecycle labels, Manual Timeline, Freight manual carry-forward, and Index Snapshot locking logic are unchanged.

## Metal Source Policy

- Primary source: Sina Finance Futures
- Fallback source: Eastmoney Futures
- Official reference retained in raw payload: SHFE

Supported metal indices:

- Stainless Steel 304
- Carbon Steel
- Zinc
- Aluminium

## Safe Failure Behaviour

Each index is processed independently. If Sina and Eastmoney fail for a metal index, that index falls back to Carry Forward when a previous value exists, or Failed when no previous value exists. This does not affect USD/HKD/GBP FX fetching or Freight manual maintenance.
