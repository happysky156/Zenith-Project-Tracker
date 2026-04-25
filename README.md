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
- Phase-1 company login with Supabase Email One-Time Password
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
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-supabase-anon-key"

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
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-supabase-anon-key"
DATABASE_URL = "postgresql://USER:PASSWORD@HOST:6543/postgres?sslmode=require"
```

`DATABASE_URL` is strongly recommended for shared use. Without it, Streamlit will use local SQLite, which is only suitable for local testing or temporary single-user testing.

## Login rules

Phase-1 login uses these rules:

- Only company emails under `@zenith-ecs.com` can log in.
- The email must exist in the internal `app_users` table.
- Default users are seeded from `core/dictionaries.py`.
- Example mapping: `harley@zenith-ecs.com` → `Harley`.
- After successful OTP login, the same browser is remembered for 30 days unless the user logs out or clears browser data.

To change default people or emails, edit:

```text
core/dictionaries.py
```

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
