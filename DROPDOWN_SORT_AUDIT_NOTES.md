# Dropdown Sort Audit Notes

Checked active pages and shared UI components for Streamlit selectbox/multiselect dropdowns.

## Result
All active user-facing dropdown lists are now sorted alphabetically where applicable.

## Included checks
- Import Center module selector
- Import Center sheet selector
- Import Center field-mapping selectors
- RFQ / Project / Order / Sample / Supplier boards
- Meeting Board filters and owner/support selectors
- AI Assistant Center filters
- Shared table jump selectors
- Market Index selector

## Notes
- Radio buttons are not dropdowns and were not changed.
- Archived fallback pages under `archived_pages/` are not active Streamlit menu pages and were not used as the main target for dropdown sorting.
- Blank / All options remain pinned at the top where applicable.
- Import logic, export logic, database structure, login logic, and business logic were not changed.
