# AI Meeting Board Layout and Mail Tracker Storage Update - 2026-05-10

## Purpose
This update adjusts the AI functions so they fit the real Meeting Board workflow and clarifies Mail Tracker storage rules.

## Meeting Board changes

### 1. Top Meeting Board layout preserved
The top Meeting Board layout is unchanged:
- Type / Next Step Owner / Follow-up Status / Search filters
- KPI cards
- Save Weekly Snapshot
- Generate Summary
- Hide Summary
- Download Minutes
- Download Follow-up
- Generate AI Meeting Control Pack

### 2. Meeting list and search result dropdown preserved
The Meeting list section remains in the same workflow:
- Search results header
- Search results dropdown
- Selected record opens automatically below

### 3. New two-column workspace below search results
After the selected search result, the page now uses a real meeting workspace layout:
- Left side: Meeting Board selected project/order card and meeting actions
- Right side: AI Meeting Assistant

This allows the user to review the live project card while entering meeting notes into the AI assistant.

### 4. AI Meeting Assistant now links to Meeting Board results
The right-side AI Meeting Assistant no longer shows the large standalone Find Project / Order search area in Meeting Board. Instead, it shows a dropdown linked to the current Meeting Board search results.

The existing AI logic is retained:
- AI generates Meeting Prep draft only
- Existing Record vs AI Suggested Update is still shown
- Selected fields only are written after human confirmation
- Meeting Note is not updated by AI
- Empty AI fields do not clear existing data
- Existing non-empty fields are not selected for overwrite by default

## AI Meeting Control Pack changes

### 1. Business-readable display
The AI Meeting Control Pack is now displayed in a business-readable layout instead of raw technical output.

It includes:
- Executive Summary
- Boss Focus
- Need Decision
- Owner Actions
- Client Follow-up
- Data Gaps
- Source Records inside an expander

### 2. Download format updated
The first download is now:
- `Download Meeting Pack Summary (.md)`

The action-list download is now:
- `Download Follow-up Action List (.xlsx)`

The Excel file contains separate sheets for Summary, Boss Focus, Need Decision, Owner Actions, Client Follow-up, Data Gaps, and Source Records.

### 3. Hide and Clear behavior
The Meeting Control Pack now supports:
- Hide: hides the generated pack but keeps it in the current session
- Clear: removes the generated pack from the current session

## Mail Tracker changes

### 1. Mail Tracker storage rule clarified
Mail Tracker is no longer described as strictly read-only.

The updated rule is:
- Uploaded mail tracker data may be saved into isolated Mail Tracker database tables
- It does not automatically update Sales, Operation, Meeting, RFQ or Supplier records
- Other tabs may link to Mail Tracker records later only through explicit future workflows

### 2. Isolated database tables added
New repository file:
- `database/mail_tracker_repository.py`

It creates two isolated tables when needed:
- `mail_tracker_import_batches`
- `mail_tracker_rows`

### 3. Mail Intelligence page update
The Mail Intelligence page now supports:
- Upload and preview `mail_tracker_clean.xlsx`
- Save uploaded workbook to isolated Mail Tracker database tables
- View recent Mail Tracker import batches
- Keyword / date / project-context AI summary

AI Mail Summary still does not update formal business records automatically.

## Files changed
- `pages/10_Meeting_Board.py`
- `ui/ai_meeting_prep_widget.py`
- `pages/11_Mail_Intelligence.py`
- `services/ai_mail_summary_service.py`
- `database/mail_tracker_repository.py`

## Safety boundaries retained
- No destructive database migration
- No automatic update from AI Meeting Control Pack
- AI Meeting Assistant still requires human confirmation
- Meeting Note is not changed by AI
- Mail Tracker storage is isolated from formal project/order modules
- Existing dropdown sorting and Meeting Board top layout remain unchanged

## Verification
Run completed:

```bash
python -m compileall .
```

Result: passed.
