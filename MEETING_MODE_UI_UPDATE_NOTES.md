# Meeting Mode UI Update Notes

This package keeps the existing Meeting Mode data and update logic, and updates the UI layout only.

## Updated file

- `pages/5_Meeting_Mode.py`

## Main changes

1. Compressed Meeting Mode page header.
2. Moved operator information into a lighter top control area.
3. Reorganised Meeting View and filters.
4. Added search by Project ID, project name, order number or client code.
5. Added Reset filter button.
6. Changed KPI buttons into clearer KPI-card style labels.
7. Changed active filter display into badge style.
8. Renamed toolbar buttons:
   - Save Weekly Snapshot
   - Generate Summary
   - Hide Summary
   - Download Minutes (.txt)
   - Download Follow-up (.csv)
9. Rebuilt project meeting card layout:
   - Header
   - Why this item is in focus
   - Main Issue / Current Progress / Blocked At / Need From Meeting
   - Next Step with Owner / Target Date / Support From
   - Follow-up Summary
   - More Details / Secondary Info expander
10. Split Meeting Actions into:
   - Primary Actions
   - Secondary Actions
   - Risk / Remove Actions
11. Changed empty field display from `-` to `Not set` in the Meeting Mode UI.
12. Added page-level CSS to hide Streamlit default toolbar/footer on this page.

## Logic not changed

- Existing Meeting Mode action functions are preserved.
- Existing snapshot, summary, minutes and follow-up export logic is preserved.
- Existing meeting follow-up save logic is preserved.
- Existing History / Event Log pathways are preserved.
- No database schema changes are included.
