# Business Control System V1 Update Notes

This update reorganises the system toward the confirmed Zenith Business Control System structure.

## Key changes

- Login/authentication logic is unchanged.
- Existing data is not physically deleted.
- Legacy page files are archived under `archived_pages/` rather than removed.
- Core Sales / Operation / Supplier / Price / Index business logic is preserved.
- `Quality Process Management` is no longer used as a visible page.
- `Process & Risk Control` remains the control-tower page.
- New visible pages include RFQ Board, Order Board, Sample Board, Supplier Board, Meeting Board, Mail Intelligence, AI Assistant Center, Import Center and Settings / Admin.
- Import Center template downloads are reorganised into cleaner tabs and expanders.
- Index Center management is available in Settings / Admin.
- RFQ Board includes a `Market Index` tab that reads the same index data for quotation reference.

## Important principle

Pages can be updated, renamed, hidden or archived. Existing business data is not physically deleted. Old business logic is kept unless explicitly changed later.
