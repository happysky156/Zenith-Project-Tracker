# Login setup note — v17.6 personal internal access-code version

This version uses a meeting-friendly login method:

```text
company email + personal internal access code + 30-day remembered browser session
```

It does **not** send Supabase Email OTP, so it does not depend on Resend / SMTP email delivery.

## Streamlit Cloud Secrets

In Streamlit Cloud, open:

```text
Manage app → Settings → Secrets
```

Add your database URL and one code per colleague:

```toml
[USER_ACCESS_CODES]
"ehab@zenith-ecs.com" = "EhabPrivateCode"
"camille@zenith-ecs.com" = "CamillePrivateCode"
"candy@zenith-ecs.com" = "CandyPrivateCode"
"harley@zenith-ecs.com" = "HarleyPrivateCode"
"maria@zenith-ecs.com" = "MariaPrivateCode"
"mark@zenith-ecs.com" = "MarkPrivateCode"
"sandy@zenith-ecs.com" = "SandyPrivateCode"
"sophia@zenith-ecs.com" = "SophiaPrivateCode"
"tiffany@zenith-ecs.com" = "TiffanyPrivateCode"

DATABASE_URL = "postgresql://USER:PASSWORD@HOST:6543/postgres?sslmode=require"
```

Important:

- Keep the email keys in quotation marks.
- Do not upload real codes to GitHub.
- Use different codes for different colleagues.
- After saving Secrets, reboot the Streamlit app.

## Login rules

- The user must enter an email under `@zenith-ecs.com`.
- The email must exist and be active in the `app_users` table.
- The email must have a matching code in `[USER_ACCESS_CODES]`.
- Default users are seeded from `core/dictionaries.py`.
- After successful login, the app creates a random 30-day device session in `app_user_sessions`.
- The browser stores only the random session token, not the personal access code.

## Changing one colleague's code

To change only Sandy's code, update only this line in Streamlit Secrets:

```toml
[USER_ACCESS_CODES]
"sandy@zenith-ecs.com" = "NewSandyCode"
```

Then reboot the app. Existing 30-day sessions remain valid unless the user logs out or their session is revoked in the database.

## If someone leaves or should not use the system

Best options:

1. Remove their line from `[USER_ACCESS_CODES]`, and reboot the app.
2. Or set their `active` value to `0` in the `app_users` table.
3. Revoke any existing session in `app_user_sessions` if immediate removal is needed.

## Legacy shared code

`INTERNAL_ACCESS_CODE` is still supported only as a fallback for migration. Once `[USER_ACCESS_CODES]` is configured, the app uses personal codes and ignores the shared code.
