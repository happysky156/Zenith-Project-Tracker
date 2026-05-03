# v18 Fixed USD Conversion Update

## Scope

This update standardises commercial/order monetary calculations to USD using a fixed business exchange rate:

```text
1 USD = 6.80 RMB / CNY
```

No live exchange-rate API or automatic market index is used for this conversion.

## Updated logic

### 1. Currency normalisation

The system recognises the following as CNY/RMB input:

```text
RMB, CNY, rmb, cny, 人民币, ¥, CN¥
```

These are converted to USD by:

```text
USD amount = original amount / 6.80
```

USD input is stored directly as USD.

### 2. Order Details

The following Order Details fields are normalised to USD before calculation:

```text
client_unit_price
supplier_unit_cost
```

Then the system calculates:

```text
Sales Revenue (USD) = client_unit_price_usd × order_qty
Supplier Cost (USD) = supplier_unit_cost_usd × order_qty
Gross Profit (USD) = Sales Revenue (USD) - Supplier Cost (USD) - Extra Cost (USD)
```

### 3. Order Costs

The following Order Costs field is normalised to USD:

```text
cost_amount
```

If the user inputs `680 RMB` or `680 CNY`, the system stores it as:

```text
100 USD
```

Order Costs are included in the Order Details gross profit calculation as USD.

### 4. Client Quotation Lines and Supplier Price Comparison

For consistency, the same fixed conversion is also applied to commercial quotation fields when a line-level `currency` field is provided.

Affected monetary fields include:

```text
supplier_unit_cost
client_unit_price
estimated_extra_cost
tooling_cost
sample_cost
packing_cost
```

### 5. Page display update

The Order Details page metric label was changed from:

```text
Revenue
```

to:

```text
Sales Revenue (USD)
```

The page intro now explains that RMB/CNY input is converted using the fixed rate.

## Notes

- This update does not change Sales Board, Operation Board, Meeting Mode, Project Detail core records, or existing weekly meeting logic.
- This update does not use real-time exchange rates.
- This update does not require legacy data migration because the v18 order/cost data has not started processing yet.
