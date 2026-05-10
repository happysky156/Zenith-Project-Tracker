# Dropdown Alphabetical Sort Update

## Scope
This update standardises user-facing dropdown option ordering across non-import pages.

## Updated
- Sample Board dropdowns
- Supplier Board dropdowns, including supplier detail selector
- Meeting Board filters and selection dropdowns
- AI Assistant Center dropdowns
- Common Board filters
- Table jump selector
- Index selector in the shared Index Center view

## Not changed
- Import Center dropdowns and mapping selectors were intentionally not changed.
- Login/authentication logic was not changed.
- Database schema and business logic were not changed.
- Existing data was not deleted or modified.

## Sorting rule
- Dropdown options are sorted alphabetically using case-insensitive sorting.
- Blank option and `All` stay at the top when present.
- Import functionality remains restricted to the authorised Import Center users.
