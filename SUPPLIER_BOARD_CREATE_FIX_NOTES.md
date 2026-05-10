# Supplier Board Create Fix Notes

This update keeps the new page title as **Supplier Board** while preserving the old backend business logic and module key **Supplier Details**.

## Changed

- Fixed the Add new supplier form in `pages/09_Supplier_Board.py`.
- The create action now calls `upsert_module_record(MODULE_NAME, ...)`, where `MODULE_NAME = "Supplier Details"`.

## Not changed

- Project ID Create remains in Import Center.
- Login logic is unchanged.
- Database structure is unchanged.
- Existing Supplier Details logic is unchanged.
- Existing data is not deleted.

## Export status note

This package does not add a full standard export layer to every board tab. Several pages already have export buttons, but Project / Order / Sample / Supplier boards still need a separate standardised export update if full all-user export coverage is required.
