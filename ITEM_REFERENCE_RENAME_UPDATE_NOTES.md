# Item Reference Rename Update Notes

This package separates RFQ-stage item references from order-stage item codes.

## Final field rules

- Price Comparison / RFQ / quotation-stage modules use `rfq_item_ref`.
- Order Details / Order Costs use `order_item_code`.
- The system must not automatically treat `rfq_item_ref` and `order_item_code` as the same value.
- Project-level linking remains based on `project_id`.
- Order-level linking remains based on `order_no`.

## Updated modules

- Project Items: `item_code` -> `rfq_item_ref`
- Supplier Price Comparison: `item_code` -> `rfq_item_ref`
- Client Quotation Lines: `item_code` -> `rfq_item_ref`
- Index Snapshot: `item_code` -> `rfq_item_ref`
- Sample Tracking: `item_code` -> `rfq_item_ref`
- Order Details: `item_code` -> `order_item_code`
- Order Costs: `item_code` -> `order_item_code`

## Import behavior

- Price Comparison requires `rfq_item_ref`.
- Order Details does not require `order_item_code`; blank values are allowed.
- During the transition, Excel headers named `Item Code` are still accepted by the Import Center and mapped according to module context:
  - Price/RFQ modules: `Item Code` -> `rfq_item_ref`
  - Order modules: `Item Code` -> `order_item_code`

## Database safety

The schema migration is additive/safe:

- Existing extension columns named `item_code` are renamed in place when possible.
- If both old and new columns exist, the new field is backfilled from the old field only when the new field is blank.
- No Sales / Operation / Meeting / Project Detail core tables are changed by this rename.
