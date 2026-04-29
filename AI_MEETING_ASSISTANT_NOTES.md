# AI Meeting Assistant - First Runnable Version

This package adds a first-version AI Meeting Assistant to Zenith Project Tracker.

## Added files

- `pages/7_AI_Meeting_Assistant.py`
- `services/ai_client.py`
- `services/ai_meeting_service.py`
- `database/ai_repository.py`

## Updated files

- `requirements.txt` adds `openai>=1.40.0`
- `.streamlit/secrets.example.toml` adds `[AI]` DeepSeek API settings
- `README.md` adds AI setup notes

## What this version does

1. Colleague enters Project Name / Order No / Client Code / Project ID.
2. System searches Sales + Operation data.
3. System shows candidate records.
4. Colleague must select one project/order.
5. System confirms Project ID before AI processing.
6. Colleague pastes meeting notes.
7. DeepSeek structures the notes into Meeting Prep fields.
8. Page shows Existing Record vs AI Suggested Update.
9. Colleague clicks Save / Confirm.
10. Result is saved into `ai_update_drafts`.

## Important safety design

This first version does not directly overwrite the core `sales_projects` or `operation_orders` tables. It only saves AI output into `ai_update_drafts`. This protects the core project database from AI mistakes.

## Streamlit Secrets

Add this to Streamlit Cloud Secrets or local `.streamlit/secrets.toml`:

```toml
[AI]
DEEPSEEK_API_KEY = "sk-your-deepseek-api-key"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
AI_TIMEOUT_SECONDS = 45
AI_MAX_TOKENS = 1200
```

After updating requirements or secrets, reboot the Streamlit app.
