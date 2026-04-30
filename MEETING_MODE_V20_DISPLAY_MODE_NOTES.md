# v17.20 Meeting Mode display-mode update

This update keeps the existing database schema and business update logic unchanged. It only changes the Meeting Mode page rendering and interaction layout.

## Main changes

1. Team Detail and Boss Summary now use different display layouts.
   - Team Detail: full working card, full follow-up editor, full meeting action groups.
   - Boss Summary: concise decision-focused card and only the core decision action buttons.

2. Why this item is in focus now uses reason tags instead of repeating detailed field content.
   - Examples: Due / Follow-up, Need Decision, Blocked / Risk, Repeated Issue, Review This Week.

3. Follow-up Summary no longer repeats Owner or Support From.
   - Owner / Target Date / Support From remain in the Next Step card.
   - Follow-up Summary now focuses on status information only.

4. More Details / Secondary Info and Open Meeting Follow-up are displayed on the same row in Team Detail.

5. Meeting Actions are more compact.
   - Primary Actions
   - Secondary Actions
   - Risk / Remove Actions

6. Risk / Remove Actions have stronger visual styling.
   - High-Risk Follow-up: orange style.
   - Remove from Meeting: red style.

7. Remove from Meeting now requires confirmation before applying the action.

## Files changed

- pages/5_Meeting_Mode.py

## Not changed

- Database schema
- Meeting action backend logic
- History / event-log writing logic
- Dashboard / board data source logic
- Import logic
