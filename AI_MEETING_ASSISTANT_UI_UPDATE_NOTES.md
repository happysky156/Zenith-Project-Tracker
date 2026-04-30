# v17.21 AI Meeting Assistant UI Display Update

This update changes only the display layer of the AI Meeting Assistant page.

## Updated file

- `pages/7_AI_Meeting_Assistant.py`

## Changes

1. Removed the two always-visible instruction banners under the AI Meeting Assistant header.
   - The page now starts directly from the step workflow after the header.

2. Moved the Step 4 review section outside the right-side column.
   - The review table now uses the full page width after Step 1 / Step 2 / Step 3.
   - This gives more room to compare Existing Record and AI Suggested Update.

3. Simplified the AI review table to four visible columns:
   - `Apply`
   - `Field`
   - `Existing Record`
   - `AI Suggested Update`

4. Hid `Field Key` from the UI.
   - The internal field-key mapping is preserved for the apply logic.
   - A fallback mapping from Field label to Field Key was added so the update logic remains stable.

5. Adjusted the review table layout.
   - Existing Record and AI Suggested Update are given more space.
   - The data editor has a fixed height so the header remains easier to work with during vertical scrolling.

## Not changed

- No database schema changes.
- No AI extraction logic changes.
- No draft save logic changes.
- No apply-to-system logic changes.
- No Meeting Note logic changes.
- No Sales / Operation core table update logic changes.
