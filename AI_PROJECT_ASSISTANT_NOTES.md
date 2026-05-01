# AI Project Assistant Update

This version adds a read-only AI Project Assistant without changing the existing database schema, business logic, AI Meeting Assistant, or write/update flows.

## Added files

- `services/ai_project_service.py`
  - Searches current Sales / Operation / Dashboard / Project Details / Meeting Mode data.
  - Excludes archived records by default by using the existing repository read functions.
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
- Archived records are excluded by default.
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
- Archived records are excluded by default.
- If no evidence is found, the assistant returns not found instead of inventing an answer.
- AI summary can only use the retrieved system evidence rows.
