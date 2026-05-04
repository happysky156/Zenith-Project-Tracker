# Index Center SHFE Metal Safe Fetch Update

Scope: Index Center / Daily Market Indices only.

This update adds a safe SHFE metal fetch framework for:
- Stainless Steel 304
- Carbon Steel
- Zinc
- Aluminium

Design principles:
- USD/CNY, HKD/CNY and GBP/CNY Bank of China FX parsing remains unchanged.
- Freight to Israel / Morocco remains Manual + Carry Forward.
- Each metal index is fetched and saved independently.
- SHFE failures do not affect FX, freight, or other index rows.
- If SHFE fetch fails but a previous value exists, the system carries forward the previous value.
- If SHFE fetch fails and no previous value exists, the row is marked Failed with an error message.

Implementation notes:
- Uses the official SHFE daily data `.dat` endpoint pattern.
- Looks back over recent calendar days to handle non-trading days.
- Selects a representative contract by open interest / volume, preferring settlement price and falling back to close price.
- Keeps existing business logic, login logic, lifecycle labels, manual freight behavior, and index snapshot behavior unchanged.
