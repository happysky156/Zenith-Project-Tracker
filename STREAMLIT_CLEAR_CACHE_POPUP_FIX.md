# v17.24 Streamlit Clear Caches Popup Fix

## Issue
When selecting or copying text in the app, Streamlit Cloud may show the built-in **Clear caches** dialog.

This is caused by Streamlit's developer shortcut / developer toolbar, not by the Project Tracker business logic.
Streamlit uses the `C` key as a developer shortcut for Clear cache when focus is not inside an input element.

## Fix
Updated `.streamlit/config.toml`:

```toml
[client]
toolbarMode = "viewer"
```

This hides Streamlit developer options such as Clear cache from viewers and reduces accidental Clear cache dialog triggering during normal use.

## Business Logic
No app business logic, database logic, AI logic, Meeting Mode logic, Sales logic, Operation logic, or Project Detail logic was changed.
Only Streamlit client toolbar configuration was updated.

## Deployment
After uploading to GitHub / Streamlit Cloud:

1. Commit and push this version.
2. In Streamlit Cloud, use **Manage app → Reboot app**.
3. Hard refresh the browser if needed.
4. If you are logged in as the Streamlit Cloud app owner, the platform's **Manage app** button may still appear, but the Clear cache developer option should no longer interrupt normal field selection/copying.
