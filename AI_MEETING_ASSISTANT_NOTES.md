# AI Meeting Assistant v17.18 Notes

## Purpose

This page is now positioned as an **AI Meeting Prep Assistant**, not a Meeting Note writer.

The assistant helps colleagues convert messy pre-meeting or weekly follow-up input into structured Meeting Prep / follow-up fields.

## Important rule for Meeting Note

`Meeting Note` is reserved for live human notes during the actual meeting.

Therefore this version:

- does not ask AI to generate `meeting_note`
- does not show `Meeting Note` in the AI review table
- does not write AI content into the `meeting_note` database field
- stores AI's short summary only in the AI draft as `ai_summary_for_review`

## Workflow

1. Search by Project ID, Project Name, Order No, or Client Code.
2. Select one Sales Project or Operation Order.
3. Confirm the selected Project ID / entity.
4. Paste colleague input or pre-meeting information.
5. Generate AI Meeting Prep draft.
6. Review a field-level table.
7. Tick only the fields to apply.
8. Confirm selected fields and update the system.
9. The update goes through the existing detail update pathway and writes an event log.

## Safety logic

- Empty AI fields do not clear existing data.
- Existing non-empty fields are not selected for overwrite by default.
- User can manually tick a field to overwrite it.
- `Review This Week = Yes` can add an item to review.
- `Review This Week = No` does not remove an existing review flag.
- Meeting Note is not changed by this assistant.


## v17.21 Apply visibility fix

- Non-empty AI suggestions are now ticked by default when they differ from the existing value.
- Existing values are still protected because users can untick any row before confirming, and empty AI fields never clear existing data.
- Confirm success now shows a database read-back table for the selected record, so users can immediately see what was actually saved.
- The selected target is shown as `Sales / Project ID` or `Operation / Order No` to avoid confusion between linked Sales and Operation records.
- Meeting Note is still not changed by the AI assistant.
