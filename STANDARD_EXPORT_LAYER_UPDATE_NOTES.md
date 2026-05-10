# Standard Export Layer Update - 2026-05-10

## Purpose
Add a consistent export layer to the main Board pages while keeping Import restricted to authorised users only.

## What changed
A new shared service was added:

- `services/export_service.py`

It provides a reusable `render_standard_export_panel(...)` function for Board pages.

The following pages now include a standard `Export & templates` area:

- `03_RFQ_Board.py`
- `04_Project_Board.py`
- `05_Order_Board.py`
- `06_Sample_Board.py`
- `07_Inspection_Release_Board.py`
- `08_Complaint_CAPA_Board.py`
- `09_Supplier_Board.py`

Each export area supports:

- Export current view
- Export filtered records
- Download import/update template

## Permission principle
- Export is available to all logged-in users.
- Import is still restricted in Import Center to Harley / authorised emails.
- This update does not open Import permissions.

## Data principle
- System records remain the source of truth.
- Excel is a working copy and backup format.
- No existing data is physically deleted.
- No existing Sales / Operation / Supplier / Sample business logic is changed.

## Template principle
Templates are generated from the same central services used by Import Center:

- `services/template_service.py`
- `services/process_management_service.py`

This avoids having two different template definitions in different pages.

## Notes
Some future process templates are available as standard templates even if their import extension is not fully connected yet. Import status still depends on each module's actual import implementation.
