# AI Business Page Embedded Update Notes - 2026-05-10

## Purpose
This update adjusts the AI functions so they are embedded into the relevant business pages and support the current workflow. The goal is not to create more standalone AI pages, but to make AI work inside Meeting Board, Process & Risk Control, and Mail Intelligence.

## Key changes

### 1. AI Meeting Assistant integrated into Meeting Board
- Removed the standalone `pages/15_AI_Meeting_Assistant.py` page from the left navigation.
- Archived the previous standalone page as:
  - `archived_pages/15_AI_Meeting_Assistant_integrated_into_meeting_board_20260510.py`
- Added reusable widget:
  - `ui/ai_meeting_prep_widget.py`
- Embedded the assistant inside:
  - `pages/10_Meeting_Board.py`
- The embedded assistant supports:
  - search by Project ID / Project Name / Order No / Client Code
  - select Sales or Operation record
  - paste meeting/pre-meeting input
  - generate AI Meeting Prep draft
  - review Existing Record vs AI Suggested Update
  - manually select fields to apply
  - confirm selected fields before updating system records
- Meeting Note remains protected and is not updated by AI.

### 2. AI Meeting Control Pack remains in Meeting Board
- `Generate AI Meeting Control Pack` remains in `pages/10_Meeting_Board.py`.
- It uses the current visible Meeting Board rows after filters.
- It remains read-only.
- It does not update Meeting Note or Meeting Prep fields.

### 3. AI Process Risk Summary made easier to find
- `AI Process Risk Summary` is still available inside each process tab.
- Added a visible AI Process Risk Summary section to the Overview tab in:
  - `pages/02_Process_Risk_Control.py`
- Users can select a process code and generate a read-only process risk review from the main control center.
- AI does not change process status or write change impact assessment.

### 4. Mail Intelligence enhanced as read-only Mail Tracker analysis
- Updated:
  - `pages/11_Mail_Intelligence.py`
  - `services/ai_mail_summary_service.py`
- Mail Tracker remains import-and-view only.
- It does not create Project IDs.
- It does not write to Sales / Operation / Meeting / RFQ / Supplier records.
- Added AI Mail Search & Summary controls:
  - keyword search
  - date filter: all, last 7 days, last 14 days, last 30 days, custom range
  - optional Project Name / Project ID / Order No search
  - system project context matching through existing project search logic
  - matched mail row preview
- If no keywords or project context are provided, it summarises all uploaded mail rows.

### 5. Event source wording updated
- Confirmed AI Meeting Prep updates are now logged with source page:
  - `Meeting Board AI Meeting Prep Assistant`

## Safety boundaries kept
- AI Project Assistant remains read-only.
- AI Meeting Control Pack remains read-only.
- Mail Tracker remains read-only and cannot write project records.
- AI Meeting Prep Assistant only writes selected fields after user confirmation.
- AI cannot update Meeting Note.
- AI cannot create Project IDs.
- AI cannot automatically update Sales, Operation, RFQ, Supplier or Process records from Mail Tracker.

## Files changed
- `pages/10_Meeting_Board.py`
- `pages/11_Mail_Intelligence.py`
- `pages/02_Process_Risk_Control.py`
- `services/ai_mail_summary_service.py`
- `services/ai_apply_service.py`
- `ui/ai_meeting_prep_widget.py`
- moved `pages/15_AI_Meeting_Assistant.py` to `archived_pages/15_AI_Meeting_Assistant_integrated_into_meeting_board_20260510.py`

## Validation
- Python compile check passed:
  - `python -m compileall .`

## Important deployment note
After deployment, please open these pages and check the workflow:
1. Meeting Board → Generate AI Meeting Control Pack
2. Meeting Board → AI Meeting Prep Assistant expander
3. Process & Risk Control → Overview → AI Process Risk Summary
4. Mail Intelligence → upload `mail_tracker_clean.xlsx` → keyword/date/project search → Generate AI Mail Summary
