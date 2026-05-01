# v17.28 Project Detail Archive Confirm Fix

## Issue fixed
The Archive button could remain grey when the user typed the Project ID, because the previous confirmation rule only accepted `selected_record_id`.

For Operation records, `selected_record_id` is usually the Order No, so typing the linked Project ID was not accepted even though the UI said "Project ID / Order No".

## Updated behaviour
The Archive / Restore confirmation now accepts any of the following values for the selected record:
- selected record ID
- Project ID
- Order No
- linked orders, split by comma / semicolon / pipe / newline

The comparison is case-insensitive and trims spaces.

## Business logic unchanged
- Archive still hides the record only.
- Archive does not delete the record.
- Restore logic is unchanged.
- Board / Meeting Mode / AI logic is unchanged.
