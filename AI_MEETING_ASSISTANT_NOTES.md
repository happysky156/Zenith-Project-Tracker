# AI Meeting Assistant Notes

## v17.17 behaviour

The AI Meeting Assistant now supports the full first workflow:

1. Search by Project Name / Order No / Client Code / Project ID.
2. Search Sales + Operation records.
3. Show candidate projects/orders.
4. User must select one record.
5. System confirms Project ID and Entity ID.
6. User pastes weekly meeting notes.
7. DeepSeek extracts Meeting Prep fields.
8. Page shows Existing Record vs AI Suggested Update.
9. User can save a pending AI draft, or confirm and apply.
10. Confirm and apply saves the AI draft into `ai_update_drafts`, then updates the core Sales / Operation Meeting Prep fields through the existing detail update logic.

## Safety rules

- Empty AI fields do not clear existing database values.
- `review_this_week = Yes` adds the record to this week's review.
- `review_this_week = No` does not remove an existing review flag.
- The update uses the existing Project Detail update path, so event logs and Streamlit cache clearing remain consistent.
- Applied AI updates are written to the event timeline as `AI Meeting Draft Applied` with source page `AI Meeting Assistant`.

## Files added or changed

- `pages/7_AI_Meeting_Assistant.py`
- `services/ai_client.py`
- `services/ai_meeting_service.py`
- `services/ai_apply_service.py`
- `database/ai_repository.py`
- `services/detail_service.py`
- `requirements.txt`
- `.streamlit/secrets.example.toml`
