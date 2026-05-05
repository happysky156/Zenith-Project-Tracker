# Price Comparison Value Color Rule Update

This update only changes the compact value colour display in `pages/10_Price_Comparison.py`.

## Updated RFQ item caption rules

1. One valid quote
   - Lowest value: green
   - Highest value: green
   - Gap: `Single quote only` in neutral text

2. Multiple valid quotes, but lowest equals highest
   - Lowest value: green
   - Highest value: green
   - Gap: `0.0%` in neutral text

3. Multiple valid quotes and lowest differs from highest
   - Lowest value: green
   - Highest value: red
   - Gap value: orange

Only display formatting was changed. Price calculation, supplier comparison, import logic, selection decisions, database schema, AI Project Assistant, Index Center, Order Details and all other business logic remain unchanged.
