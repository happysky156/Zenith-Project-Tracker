# v17.25 Meeting Mode Links and Dropdown Update

Scope: Meeting Mode related UI and link-support fields only.

Changes included:

1. Meeting Mode focus cards are kept as quick filters.
2. The previous "Showing" status strip is hidden.
3. Filtered meeting results are shown through a Project Details style `Search results` dropdown.
4. The dropdown defaults to the first item and only the selected item is expanded below.
5. `Project Link` is displayed from the existing `reference_link` field. It is read-only in Meeting Mode.
6. `Meeting Reference Links` support up to three fixed link slots per Sales / Operation record.
7. Each Meeting Reference Link has a Label and URL.
8. Empty links are shown as disabled buttons.
9. Saving Meeting Reference Links writes to the current Sales / Operation record and creates an Event Log entry.

Files changed:

- `pages/5_Meeting_Mode.py`
- `services/meeting_service.py`
- `database/schema.py`

Business logic intentionally preserved:

- Meeting pool logic is unchanged.
- KPI / focus card filter logic is unchanged.
- Meeting action logic is unchanged.
- Meeting follow-up logic is unchanged.
- Project Link is not edited in Meeting Mode.
