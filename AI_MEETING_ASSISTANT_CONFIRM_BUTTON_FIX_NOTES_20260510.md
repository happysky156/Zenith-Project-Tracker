# AI Meeting Assistant Confirm Button Fix Notes - 2026-05-10

## Issue fixed
In Meeting Board > AI Meeting Assistant, users could tick fields that were already identical to the current saved system record. When confirming, the system correctly returned "AI draft confirmed, but no field changed", but this was confusing because the Confirm button appeared to have no effect.

## What changed
- Added a `Change Status` column to the AI Suggested Update review table.
- Rows now show whether an AI suggestion will actually change the saved record:
  - `Will change if selected`
  - `Same as current`
  - `No AI value`
- The Confirm button is now enabled only when at least one selected field will actually change the saved system record.
- If a user selects only same-value fields, the page explains why the system will not update.
- If some selected rows are unchanged, the page tells the user those rows will be ignored.
- After a successful update, the page reminds the user to refresh or change the filter/search to see the updated project card values.

## Safety preserved
- AI still does not update Meeting Note.
- Empty AI fields still do not clear existing values.
- Existing non-empty fields are still not selected by default.
- Data is written only after human confirmation.
- No database schema changes were made.
