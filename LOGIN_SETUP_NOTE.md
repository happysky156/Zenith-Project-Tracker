# Phase-1 Login Setup Note

## Login rule

This version requires login before any page can be viewed or operated.

Allowed login condition:

1. The email must end with `@zenith-ecs.com`.
2. The email must exist and be active in the internal `app_users` table.

Default users are automatically seeded from `core/dictionaries.py`:

```text
Harley  -> harley@zenith-ecs.com
Sandy   -> sandy@zenith-ecs.com
Maria   -> maria@zenith-ecs.com
```

## Local setup

Create this file locally:

```text
.streamlit/secrets.toml
```

Example:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-supabase-anon-key"
```

Then run:

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Same-device memory

After a successful Email OTP login, this browser stores a local session token for 30 days.
The database only stores the hash of the token, not the raw token.

The user needs to log in again if:

- They use a different computer or browser.
- They use incognito/private mode.
- They clear browser data.
- They click Logout.
- The 30-day local session expires.

## Automatic user recording

The following fields now use the logged-in user automatically:

- Acting User
- Imported by
- Last Updated By
- Event Log Operator
- Meeting Update As

Users no longer need to manually select their name for these operation-recording fields.
