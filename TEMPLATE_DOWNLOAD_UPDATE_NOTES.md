# Template Download Update Notes

## Scope
This update adds read-only Excel template downloads to Import Center.

Added templates:
- Sales Import Template
- Operation Import Template
- Supplier Details Template
- Price Comparison Template
- Order Details Template
- Sample Tracking Template

## Safety
- No database schema change.
- No business logic change.
- No import logic change.
- No Sales / Operation / Archive / Meeting Mode / Order Details calculation logic change.
- The existing Import Center permission guard remains unchanged: only `harley@zenith-ecs.com` can access the Import Center page.

## How templates work
Each downloaded workbook includes:
- `Template` sheet: technical import headers in row 1 and one example row in row 2.
- `Field Guide` sheet: field name, display name, required status, data type, and description.
- `Instructions` sheet: usage notes.

Important: keep row 1 field names unchanged when importing back into the system.

## Delivery date note
The core Operation Board import currently only imports:
- `project_id`
- `client_code`
- `order_no`
- `reference_link`

The core `operation_orders` table has `target_date` for meeting/follow-up target date, but it does not currently have a dedicated `target_delivery_date` field.

The extension `Order Details` table already has:
- `target_delivery_date`
- `actual_delivery_date`
- `shipment_date`

Recommended approach for now: use `Order Details.target_delivery_date` for delivery-date control. This keeps the original core database and business logic unchanged.
