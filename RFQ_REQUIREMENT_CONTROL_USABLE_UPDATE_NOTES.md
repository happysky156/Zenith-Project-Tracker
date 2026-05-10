# RFQ Requirement Control Usable Update Notes

## Purpose
This update moves QP-01 from a read-only process design into a usable process extension.

## Main changes
- Renamed the process page to **Process & Risk Control** / **Business Process & Risk Control Center**.
- Added the additive extension table `rfq_requirement_control`.
- Added **RFQ Requirement Control** as an Extension Import module.
- RFQ templates can now be downloaded, filled, uploaded through Import Center, saved into the system, and displayed in QP-01.
- QP-01 Process Records View now prioritizes imported RFQ Requirement Control records.
- If no RFQ Control records exist yet, QP-01 falls back to active Sales Board projects as reference data.
- Import Center now defaults to the `Template` sheet when an uploaded workbook contains that sheet.

## Scope protection
- Core Sales Board logic was not changed.
- Core Operation Board logic was not changed.
- Order Details, Supplier Details, Sample Tracking and Price Comparison business logic were not changed.
- Import Center permission remains unchanged: only the allowed Harley account can import.
- Other QP processes remain read-only design views.

## How to use
1. Open **Process & Risk Control**.
2. Download the QP-01 RFQ template from the QP-01 tab or Import Center.
3. Fill the `Template` sheet, or map fields manually during import.
4. Go to Import Center > Extension Import.
5. Select **RFQ Requirement Control**.
6. Upload the Excel file and select the `Template` sheet.
7. Preview, validate, and confirm import.
8. Return to Process & Risk Control > QP-01 RFQ to view imported records.
