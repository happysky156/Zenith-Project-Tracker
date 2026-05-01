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
