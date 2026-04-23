# Zenith Project Tracker

A Streamlit-based internal project and weekly meeting tracker.

## What this build supports
- Split master-data import for **Sales** and **Operation**
- Automatic Sales ↔ Operation linking through **Project ID**
- High-frequency board actions
- One shared **Project / Order Detail** page for Sales Project / Operation Order
- Weekly Meeting actions and weekly snapshots
- Quick meeting note capture during live meetings
- SQLite for local testing, or PostgreSQL for shared cloud deployment

## Local setup (Windows PowerShell)
```powershell
cd path\to\Zenith_project_tracker
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

## Database modes
### 1) Local testing: SQLite
Leave `DATABASE_URL` empty. The app will create `project_tracker.db` automatically in the project folder.

### 2) Shared deployment: PostgreSQL
Set `DATABASE_URL` in Streamlit secrets or environment variables.

Example:
```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST:6543/postgres?sslmode=require"
```

## Important notes
- `Acting User` is still selected manually per page. This build does **not** include true login-based auto-identification yet.
- SQLite is fine for local testing and single-user use.
- For Shenzhen / Guangzhou / home-office shared use, PostgreSQL is strongly recommended.

## Logging
A file log is created automatically at:

```text
logs/project_tracker.log
```

## UI branding
Place your company logo at `assets/Zenith.png`. If the file is missing, the app will show a simple Zenith text badge instead.
