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


## AI Meeting Assistant setup

This build adds a first-version AI Meeting Assistant page. The page lets colleagues search by Project ID, Project Name, Order No, or Client Code; select and confirm one project/order; paste weekly meeting notes; ask DeepSeek to structure the notes into Meeting Prep fields; compare existing records with AI-suggested updates; and save the result into the `ai_update_drafts` table.

The first version does **not** directly overwrite the core Sales or Operation tables. This protects the permanent project database. Confirmed AI output is saved as a draft for later review or future connection to the existing Project / Order Detail update logic.

Add these values to Streamlit Cloud Secrets or local `.streamlit/secrets.toml`:

```toml
[AI]
DEEPSEEK_API_KEY = "sk-your-deepseek-api-key"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
AI_TIMEOUT_SECONDS = 45
AI_MAX_TOKENS = 1200
```

After updating requirements or Secrets, reboot the Streamlit app.

## v17.17 AI Meeting Assistant apply-to-system update

The AI Meeting Assistant can now confirm an AI draft and apply it to the existing Sales / Operation Meeting Prep fields.

Flow:

```text
Search Project / Order
→ Confirm Project ID / Entity ID
→ Paste meeting notes
→ DeepSeek extracts fields
→ Review Existing Record vs AI Suggested Update
→ Confirm AI Draft + Update System
→ Save to ai_update_drafts
→ Update core Sales / Operation record
→ Write Event Timeline log
→ Clear cached read data
```

Safety rules:

- Empty AI fields do not clear existing values.
- AI `Review This Week = Yes` will set `review_this_week = 1`.
- AI `Review This Week = No` will not remove the existing review flag.
- Confirmed applied drafts are marked as `confirmed_applied` in `ai_update_drafts`.
- If no core field changes are detected, the draft is marked as `confirmed_no_change`.
- If the draft is saved but applying fails, the draft is marked as `confirmed_apply_failed`.

## v17.18 AI Meeting Prep Assistant update

This version refines the AI assistant logic:

- The page works as an AI Meeting Prep Assistant.
- `Meeting Note` is treated as a live human meeting-record field and is no longer generated or updated by AI.
- AI output is limited to structured Meeting Prep / follow-up fields.
- Users must review an editable field-level table before applying changes.
- Existing non-empty fields are not selected for overwrite by default.
- Confirm applies only selected fields through the existing detail update/event log pathway.

## Extension layer: quotation, supplier, index, order cost and sample tracking

This package adds an extension layer while keeping the original Sales / Operation business logic unchanged.

### New left-side pages

- Supplier Details
- Price Comparison
- Client Quotation
- Index Center
- Order Details
- Sample Tracking

### Import Center additions

Import Center now has three modes:

1. Core Sales / Operation — original workflow, unchanged.
2. Project ID Create — generates the next non-duplicate Project ID, including archived records and extension tables.
3. Extension Import — imports only into new extension tables.

### New extension tables

- supplier_details
- project_items
- supplier_price_comparisons
- client_quotation_headers
- client_quotation_lines
- index_config
- daily_market_indices
- index_snapshots
- freight_indices
- order_details
- order_costs
- sample_tracking

### Project / Order Detail additions

Project / Order Detail now adds read-only, layered tabs for the new extension records. Large field groups are hidden in expanders by default for speed and readability.

Sales Project detail tabs include:

- Supplier Details
- Project Items
- Price Comparison
- Client Quotation
- Sample Tracking

Operation Order detail tabs include:

- Supplier Details
- Order Details
- Order Costs
- Client Quotation

### Daily Index automation

Use GitHub Actions to run:

```text
tools/daily_index_fetch.py
```

Recommended schedule:

```text
Every day at 10:30 Beijing/Singapore time
```

The included workflow is:

```text
.github/workflows/daily_index_fetch.yml
```

The script currently seeds the fixed index list and carries forward missing values. External parsers should be added only after the company confirms fixed data sources for FX, metals, plastics and freight.

### Default market indices

- USD/CNY
- Stainless Steel 304
- Carbon Steel
- Zinc
- Aluminium
- PP
- ABS
- PVC
- Freight to Israel
- Freight to Morocco
