# Index Alert + Quotation Snapshot Update Notes

This update adds internal index risk tracking while keeping the existing daily index fetch, quotation, supplier, order, sales and operation business logic unchanged.

## Added

- `index_alert_rules` table for user-maintained thresholds.
- `index_alert_events` table for generated, traceable alerts.
- Index Center tabs:
  - Overview
  - Alert Rules & Events
  - Manual Override / Confirm
  - All Daily Records
  - Index Config Records
- Fixed Baseline alert support:
  - Latest index value vs manually maintained baseline value.
- Snapshot Deviation alert support:
  - Latest index value vs locked client quotation index snapshot.
- Client Quotation page snapshot lock workflow:
  - Select a client quotation.
  - Select latest index values.
  - Lock them as quotation snapshots.
  - Existing locked snapshots are not overwritten.
- Project Detail → Client Quotation tab alert section:
  - Shows project-linked quotation index alerts only.
- Daily index fetch now attempts to generate alert events after the daily values are written.

## Preserved

- Daily Market Indices still record daily values as before.
- Manual override / confirm logic remains unchanged.
- Existing All Daily Records and Index Config Records are preserved, but moved into tabs.
- Locked snapshots are historical quotation evidence and do not change when daily index values change later.
- No external notification is added yet. Alerts are internal system records only.

## Alert policy

- Daily Change is already visible in existing Daily Market Indices and is not forced into default alert events.
- Snapshot Deviation rules are active by default using category thresholds.
- Fixed Baseline rules are created inactive by default and should be enabled after setting a baseline value.
