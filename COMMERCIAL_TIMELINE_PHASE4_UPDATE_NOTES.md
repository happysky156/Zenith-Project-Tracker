# Commercial Timeline Phase 4 Update

This build adds a management-oriented lifecycle timeline without changing the original Sales, Operation, Meeting Mode, login or board logic.

## Added

- Commercial lifecycle service: `services/timeline_service.py`
- Project Detail > History now shows:
  - Management Time Control cards
  - Lifecycle Bar
  - Lifecycle milestone details
  - Commercial / Management Timeline
  - Original event logs in a collapsed expander
- Extension module save/import/update actions now write commercial timeline events where a Project ID / Order No is available.
- Event log table is extended additively with timeline metadata fields:
  - planned_date, actual_date, delay_days, date_source
  - waiting_for, owner, risk_level
  - customer_impact, commercial_impact
  - source_module, source_record_id
- Index Snapshot / Daily Market Indices compatibility columns are added safely for earlier Supabase table shapes.
- Extension row reads now skip missing incompatible tables/columns safely rather than crashing the page.

## Management time dimensions

- Project Age
- Days in Current Stage
- Waiting For / Waiting Days
- Planned vs Actual / Delay Days
- Risk Age
- Customer Waiting Days

## Lifecycle milestones

Project Created → Supplier Added → RFQ Sent → Supplier Quote Received → Price Comparison Completed → Client Quotation V1 Created → Index Snapshot Locked → Client Quotation Sent → Sample Requested → Sample Sent to Client → Client Approved Sample → Order Created → Production Follow-up → Inspection Completed → Shipment Completed → Final Cost Updated → Gross Profit Confirmed → Project Closed

## Data philosophy

- System auto-recorded dates are the primary source.
- Module data is used for automatic inference when a direct event is missing.
- Manual/planned dates can be added later without breaking the current UI.
- Missing nodes show placeholders instead of causing page errors.
