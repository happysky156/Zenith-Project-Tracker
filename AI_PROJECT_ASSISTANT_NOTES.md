# AI Project Assistant Update

This version adds a read-only AI Project Assistant without changing the existing database schema, business logic, AI Meeting Assistant, or write/update flows.

## Added files

- `services/ai_project_service.py`
  - Searches current Sales / Operation / Dashboard / Project Details / Meeting Mode data.
  - Calls the existing AI client only after deterministic system-record retrieval.
  - If no evidence is found, returns a not-found answer without asking AI to invent an answer.
  - Provides text and CSV export helpers.

- `pages/8_AI_Project_Assistant.py`
  - New Streamlit page.
  - Supports free Chinese / English / bilingual input.
  - Includes AI output language selection: English, Chinese, Bilingual Chinese and English.
  - Displays direct answer first, then evidence by the existing system architecture.
  - Supports `.txt` and `.csv` downloads.

## Safety principles

- No database schema changes.
- No database write actions.
- No changes to AI Meeting Assistant.
- All AI answers are constrained to retrieved system records.
- Search not found = explicit not-found response.


## v17.30 AI Project Assistant Query Logic Upgrade

This update keeps the assistant read-only and does not change database schema, existing business logic, data content, or AI Meeting Assistant.

Key logic:
- Normal questions use natural-language search over current active system records.
- Order-association questions use the existing Sales Board / Dashboard rule:
  - Projects with orders = active Sales Project IDs found in active Operation Project IDs.
  - Projects without orders = active Sales Project IDs not found in active Operation Project IDs.
  - Unlinked operation orders = active Operation Project IDs not found in active Sales Project IDs.
- Result Limit controls display/export rows only; the full order-association count is calculated before limiting.
- Multi-condition queries are narrowed by obvious deterministic filters such as record type, status, and owner.
- Boss-focus questions pull high-attention, meeting-pool, decision/alignment, and Ehab-related evidence.
- Client open-issue questions filter current active issue/follow-up evidence by client keyword.
- Project-history questions read from event_logs_v2 and meeting_snapshots_v2 for the matched project/order.
- Duplicate dataframe columns are removed before Streamlit display/export to avoid Arrow duplicate-column errors.

Safety rules preserved:
- No database writes.
- If no evidence is found, the assistant returns not found instead of inventing an answer.
- AI summary can only use the retrieved system evidence rows.

## v17.31 Final Answer Records Display Upgrade

This update keeps the same read-only design and does not change database schema, data content, business logic, or AI Meeting Assistant.

Display and export changes:
- Main statistic cards now show only:
  - Final Answer Records
  - Sales
  - Operation
- Internal checked/candidate records are not displayed and are not exported.
- Sales Board / Operation Board / Meeting Mode tabs show only final answer records.
- CSV export contains only final answer records shown on the page.
- “Evidence Summary” is renamed to “Based on System Records”.
- “Not Found / Limitations” is renamed to “Search Scope and Limitations”.
- Search-scope wording is simplified to avoid implying that there are hidden extra results.
- The assistant asks the AI model to return `final_source_ids`, then filters display/export records to those final records when available.
- Duplicate records across board and meeting views are de-duplicated for final display, preferring board records unless the user specifically searches Meeting Mode.
