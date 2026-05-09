# Import Center Permission Update

## Purpose
Protect database integrity by restricting Excel import access to the authorised system owner only.

## Authorised Import User
- harley@zenith-ecs.com

## Updated File
- `pages/1_Import_Center.py`

## What Changed
A page-level permission guard was added immediately after login verification. If the logged-in user's email is not `harley@zenith-ecs.com`, the Import Center page stops before any upload, preview, archive, or import workflow is shown.

## What Did Not Change
- No database schema changes.
- No business logic changes.
- No import service changes.
- No Sales / Operation / Project / Order / Archive logic changes.
- No changes to Dashboard, Meeting Mode, AI Project Assistant, Supplier Details, Price Comparison, Order Details, or Sample Tracking.

## Security Logic
The guard uses the logged-in user's email from the existing authentication session:

```python
ALLOWED_IMPORT_CENTER_EMAILS = {"harley@zenith-ecs.com"}
```

Only this email can use Import Center. Other logged-in users can still view normal pages but cannot access import operations.

## Note
The Streamlit sidebar may still show the Import Center page name because it is a multipage app. The actual import function is protected at page level and cannot be used by unauthorised users.
