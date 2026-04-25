# Zenith Project Tracker

A Streamlit-based internal tracker for Sales, Operation, Project Detail, Import Center, Field Setup, and Weekly Meeting review.

## Current build

This GitHub-clean build includes:

- Dashboard page
- Sales Board
- Operation Board
- Project / Order Detail page
- Import Center
- Weekly Meeting Mode
- Field Setup
- SQLite local testing mode
- PostgreSQL / Supabase database mode for shared cloud deployment
- Meeting-friendly login with company email + personal internal access code
- 30-day same-browser login memory
- Automatic user recording for `Acting User`, `Imported by`, `Last Updated By`, and event-log operator fields

## Folder structure

```text
Zenith_project_tracker/
├─ app.py
├─ Dashboard.py
├─ requirements.txt
├─ .gitignore
├─ .streamlit/
│  ├─ config.toml
│  └─ secrets.example.toml
├─ assets/
├─ core/
├─ database/
├─ pages/
├─ services/
├─ tools/
├─ ui/
├─ utils/
└─ logs/
```

## Local run

```powershell
cd Zenith_project_tracker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

## Local secrets

For local testing, copy:

```text
.streamlit/secrets.example.toml
```

to:

```text
.streamlit/secrets.toml
```

Then fill in your real values:

```toml
[USER_ACCESS_CODES]
"harley@zenith-ecs.com" = "HarleyPrivateCode"
"sandy@zenith-ecs.com" = "SandyPrivateCode"
"maria@zenith-ecs.com" = "MariaPrivateCode"

# Recommended for Streamlit Cloud shared deployment:
DATABASE_URL = "postgresql://USER:PASSWORD@HOST:6543/postgres?sslmode=require"
```

Do **not** upload `.streamlit/secrets.toml` to GitHub.

## Streamlit Cloud deployment

1. Upload this folder to a GitHub repository.
2. In Streamlit Cloud, create a new app from that repository.
3. Main file path: `app.py`.
4. Add the following values in Streamlit Cloud Secrets:

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

`DATABASE_URL` is strongly recommended for shared use. Without it, Streamlit will use local SQLite, which is only suitable for local testing or temporary single-user testing.

## Login rules

This version uses a meeting-friendly login method:

- Users log in with company email + personal internal access code.
- Only company emails under `@zenith-ecs.com` can log in.
- The email must exist in the internal `app_users` table.
- The email must have a matching code in `[USER_ACCESS_CODES]`.
- Default users are seeded from `core/dictionaries.py`.
- Example mapping: `harley@zenith-ecs.com` → `Harley`.
- After successful login, the same browser is remembered for 30 days unless the user logs out or clears browser data.
- Supabase Email OTP / Resend / SMTP is **not required** in this version.

To change default people or emails, edit:

```text
core/dictionaries.py
```

To change one colleague's code, update their line in `[USER_ACCESS_CODES]` in Streamlit Cloud Secrets, then reboot the app.

## Database notes

- Local testing: SQLite database file `project_tracker.db` is created automatically.
- Cloud/shared deployment: use Supabase PostgreSQL through `DATABASE_URL`.
- The app initializes and migrates required tables automatically at startup.

## GitHub clean notes

This package intentionally excludes:

- `.streamlit/secrets.toml`
- `.env`
- local `.db` files
- Python cache files
- local log files
- virtual environment folders

## v17.6 personal internal-code login fix

This package replaces the shared internal access code with per-user personal access codes:

- No email sending, no Resend limit, no SMTP dependency.
- Each colleague has a separate code in `[USER_ACCESS_CODES]`.
- Email + matching code identifies the user and controls login.
- Login state is still remembered in the browser for 30 days using a secure random device token saved in `app_user_sessions`.
- Page switches first use `st.session_state`, so authenticated users do not re-check the database on every page.
- Browser remember-me uses a cookie plus a localStorage fallback bridge.
- Database schema initialisation is guarded so it runs once per Streamlit process instead of on every rerun.
- Dashboard, board, detail and meeting read models use short Streamlit data caching.
- Any database write clears cached read data so meeting updates appear immediately.
- PostgreSQL connections use a small psycopg pool when `psycopg-pool` is installed.

After deployment, please use **Manage app → Reboot app** once after updating Secrets or requirements.
