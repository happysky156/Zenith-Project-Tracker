# Quality Process Management Phase 1 Update

## Scope
This update adds a read-only `Quality Process Management` page and keeps existing business logic unchanged.

## What changed
- Added `pages/15_Quality_Process_Management.py`.
- Added `services/process_management_service.py` with central process definitions, control points, quality process template definitions, and export helpers.
- Updated `pages/1_Import_Center.py` so Import Center can also download the same Quality Process templates from the central process template service.

## What did not change
- No database schema changes.
- No Sales / Operation / Order Details / Supplier Details business logic changes.
- No import logic changes.
- Import Center permission remains restricted to `harley@zenith-ecs.com`.
- AI-assisted summary and change impact assessment are not connected in Phase 1. The page only documents the future button-triggered logic.

## New page structure
`Quality Process Management` contains:
- Overview
- QP-01 RFQ Requirement Control
- QP-02 Sample Control
- QP-03 Order Setup Control
- QP-04 Inspection & Shipment Release Control
- QP-05 Quality Complaint Closure
- SV-01 Supplier Management
- History

## Template source consistency
Quality Process templates are generated from `services/process_management_service.py` and can be downloaded from:
- Import Center
- The corresponding tab in Quality Process Management

This avoids maintaining two separate template sources.

## Phase 1 limitation
The page maps existing records where possible and provides process documents/templates/export buttons. It does not write process records into new extension tables yet.
