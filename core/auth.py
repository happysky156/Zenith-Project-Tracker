from __future__ import annotations

import hashlib
import html
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import streamlit as st
import streamlit.components.v1 as components

from core.dictionaries import COMPANY_EMAIL_DOMAIN, PEOPLE_EMAIL_MAP
from database.connection import execute, get_connection
from database.schema import init_db

try:
    import requests
except Exception:  # pragma: no cover - handled in UI
    requests = None  # type: ignore


SESSION_COOKIE_DAYS = 30
SESSION_STORAGE_KEY = "zenith_project_tracker_session_token"
QUERY_SESSION_KEY = "zt_session"
AUTH_USER_STATE_KEY = "auth_user"
AUTH_TOKEN_STATE_KEY = "auth_session_token"


@dataclass(frozen=True)
class AuthUser:
    email: str
    display_name: str
    role: str = "editor"

    def as_dict(self) -> dict[str, str]:
        return {"email": self.email, "display_name": self.display_name, "role": self.role}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _normalize_email(email: str | None) -> str:
    return str(email or "").strip().lower()


def _is_company_email(email: str) -> bool:
    return email.endswith(f"@{COMPANY_EMAIL_DOMAIN.lower()}")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _get_secret(*names: str) -> str | None:
    for name in names:
        value = None
        try:
            value = st.secrets.get(name)  # type: ignore[attr-defined]
        except Exception:
            value = None
        if value:
            return str(value).strip()
    return None


def _supabase_settings() -> tuple[str | None, str | None]:
    url = _get_secret("SUPABASE_URL", "supabase_url")
    key = _get_secret("SUPABASE_ANON_KEY", "supabase_anon_key")
    if url:
        url = url.rstrip("/")
    return url, key


def _supabase_headers(anon_key: str) -> dict[str, str]:
    return {
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
        "Content-Type": "application/json",
    }


def _check_supabase_ready() -> tuple[bool, str | None, str | None, str | None]:
    if requests is None:
        return False, None, None, "The 'requests' package is not installed. Please run: pip install -r requirements.txt"
    url, key = _supabase_settings()
    if not url or not key:
        return False, url, key, (
            "Supabase login is not configured yet. Please add SUPABASE_URL and "
            "SUPABASE_ANON_KEY in .streamlit/secrets.toml."
        )
    return True, url, key, None


def get_app_user(email: str) -> AuthUser | None:
    """Return an active application user from app_users."""
    init_db()
    normalized = _normalize_email(email)
    if not normalized:
        return None
    conn = get_connection()
    cur = conn.cursor()
    execute(
        cur,
        """
        SELECT email, display_name, role, active
        FROM app_users
        WHERE lower(email) = lower(?)
        """,
        (normalized,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    active = int(row["active"] or 0)
    if not active:
        return None
    return AuthUser(
        email=str(row["email"]).lower(),
        display_name=str(row["display_name"]),
        role=str(row["role"] or "editor"),
    )


def is_allowed_login_email(email: str) -> tuple[bool, str]:
    normalized = _normalize_email(email)
    if not normalized:
        return False, "Please enter your company email."
    if not _is_company_email(normalized):
        return False, f"Only @{COMPANY_EMAIL_DOMAIN} company email addresses can log in."
    app_user = get_app_user(normalized)
    if not app_user:
        return False, "This company email is not active in the Zenith user list. Please ask the system owner to add it first."
    return True, ""


def send_login_otp(email: str) -> tuple[bool, str]:
    """Send Supabase email OTP after local company-domain and app-user checks."""
    normalized = _normalize_email(email)
    allowed, message = is_allowed_login_email(normalized)
    if not allowed:
        return False, message

    ready, url, anon_key, error = _check_supabase_ready()
    if not ready:
        return False, error or "Supabase is not configured."

    try:
        response = requests.post(  # type: ignore[union-attr]
            f"{url}/auth/v1/otp",
            headers=_supabase_headers(str(anon_key)),
            json={"email": normalized, "create_user": True},
            timeout=20,
        )
    except Exception as exc:
        return False, f"Failed to contact Supabase Auth: {exc}"

    if response.status_code >= 400:
        detail = ""
        try:
            payload = response.json()
            detail = payload.get("msg") or payload.get("message") or str(payload)
        except Exception:
            detail = response.text
        return False, f"Failed to send verification code: {detail}"

    st.session_state["pending_login_email"] = normalized
    return True, "Verification code sent. Please check your company email."


def verify_login_otp(email: str, token: str) -> tuple[bool, str, dict[str, str] | None]:
    normalized = _normalize_email(email)
    code = str(token or "").strip().replace(" ", "")
    if not code:
        return False, "Please enter the verification code.", None

    allowed, message = is_allowed_login_email(normalized)
    if not allowed:
        return False, message, None

    app_user = get_app_user(normalized)
    if not app_user:
        return False, "This user is not active.", None

    ready, url, anon_key, error = _check_supabase_ready()
    if not ready:
        return False, error or "Supabase is not configured.", None

    try:
        response = requests.post(  # type: ignore[union-attr]
            f"{url}/auth/v1/verify",
            headers=_supabase_headers(str(anon_key)),
            json={"email": normalized, "token": code, "type": "email"},
            timeout=20,
        )
    except Exception as exc:
        return False, f"Failed to verify the code with Supabase Auth: {exc}", None

    if response.status_code >= 400:
        detail = ""
        try:
            payload = response.json()
            detail = payload.get("msg") or payload.get("message") or str(payload)
        except Exception:
            detail = response.text
        return False, f"Verification failed: {detail}", None

    local_session_token = create_device_session(app_user)
    user_dict = app_user.as_dict()
    st.session_state[AUTH_USER_STATE_KEY] = user_dict
    st.session_state[AUTH_TOKEN_STATE_KEY] = local_session_token
    _update_last_login(app_user.email)
    return True, "Login successful.", user_dict


def _update_last_login(email: str) -> None:
    conn = get_connection()
    cur = conn.cursor()
    execute(cur, "UPDATE app_users SET last_login_at = ? WHERE lower(email) = lower(?)", (_to_iso(_utc_now()), email))
    conn.commit()
    conn.close()


def create_device_session(user: AuthUser) -> str:
    init_db()
    token = secrets.token_urlsafe(48)
    now = _utc_now()
    expires_at = now + timedelta(days=SESSION_COOKIE_DAYS)
    conn = get_connection()
    cur = conn.cursor()
    execute(
        cur,
        """
        INSERT INTO app_user_sessions
            (session_token_hash, email, display_name, role, created_at, expires_at, last_seen_at, revoked)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (_token_hash(token), user.email, user.display_name, user.role, _to_iso(now), _to_iso(expires_at), _to_iso(now)),
    )
    conn.commit()
    conn.close()
    return token


def verify_device_session(token: str | None) -> AuthUser | None:
    init_db()
    if not token:
        return None
    conn = get_connection()
    cur = conn.cursor()
    execute(
        cur,
        """
        SELECT s.email, s.display_name, s.role, s.expires_at, s.revoked, u.active
        FROM app_user_sessions s
        LEFT JOIN app_users u ON lower(u.email) = lower(s.email)
        WHERE s.session_token_hash = ?
        """,
        (_token_hash(str(token)),),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    revoked = int(row["revoked"] or 0)
    active = int(row["active"] or 0)
    expires_at = _parse_iso(row["expires_at"])
    if revoked or not active or not expires_at or expires_at <= _utc_now():
        conn.close()
        return None

    execute(cur, "UPDATE app_user_sessions SET last_seen_at = ? WHERE session_token_hash = ?", (_to_iso(_utc_now()), _token_hash(str(token))))
    conn.commit()
    conn.close()
    return AuthUser(email=str(row["email"]).lower(), display_name=str(row["display_name"]), role=str(row["role"] or "editor"))


def revoke_current_session() -> None:
    token = st.session_state.get(AUTH_TOKEN_STATE_KEY)
    if token:
        try:
            conn = get_connection()
            cur = conn.cursor()
            execute(cur, "UPDATE app_user_sessions SET revoked = 1 WHERE session_token_hash = ?", (_token_hash(str(token)),))
            conn.commit()
            conn.close()
        except Exception:
            pass
    st.session_state.pop(AUTH_USER_STATE_KEY, None)
    st.session_state.pop(AUTH_TOKEN_STATE_KEY, None)
    st.session_state.pop("pending_login_email", None)


def get_current_user() -> dict[str, str] | None:
    value = st.session_state.get(AUTH_USER_STATE_KEY)
    if isinstance(value, dict) and value.get("email") and value.get("display_name"):
        return value
    return None


def get_current_display_name(default: str = "") -> str:
    user = get_current_user()
    return str(user.get("display_name") if user else default)


def _get_query_value(key: str) -> str | None:
    try:
        value = st.query_params.get(key)
        if isinstance(value, list):
            return str(value[0]) if value else None
        return str(value) if value else None
    except Exception:
        return None


def _clear_query_params() -> None:
    try:
        st.query_params.clear()
    except Exception:
        pass


def _render_browser_token_loader() -> None:
    storage_key = html.escape(SESSION_STORAGE_KEY)
    query_key = html.escape(QUERY_SESSION_KEY)
    components.html(
        f"""
        <script>
        (function() {{
            const storageKey = "{storage_key}";
            const queryKey = "{query_key}";
            const token = window.localStorage.getItem(storageKey);
            const url = new URL(window.location.href);
            if (token && !url.searchParams.get(queryKey)) {{
                url.searchParams.set(queryKey, token);
                window.location.replace(url.toString());
            }}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def _render_store_browser_token(token: str) -> None:
    safe_token = html.escape(token)
    storage_key = html.escape(SESSION_STORAGE_KEY)
    query_key = html.escape(QUERY_SESSION_KEY)
    components.html(
        f"""
        <script>
        (function() {{
            const storageKey = "{storage_key}";
            const queryKey = "{query_key}";
            window.localStorage.setItem(storageKey, "{safe_token}");
            const url = new URL(window.location.href);
            url.searchParams.delete(queryKey);
            window.history.replaceState(null, "", url.toString());
            setTimeout(function() {{ window.location.reload(); }}, 500);
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def _render_clear_browser_token(reload: bool = True) -> None:
    storage_key = html.escape(SESSION_STORAGE_KEY)
    query_key = html.escape(QUERY_SESSION_KEY)
    reload_js = "setTimeout(function() { window.location.reload(); }, 350);" if reload else ""
    components.html(
        f"""
        <script>
        (function() {{
            const storageKey = "{storage_key}";
            const queryKey = "{query_key}";
            window.localStorage.removeItem(storageKey);
            const url = new URL(window.location.href);
            url.searchParams.delete(queryKey);
            window.history.replaceState(null, "", url.toString());
            {reload_js}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def render_current_user_sidebar() -> None:
    user = get_current_user()
    if not user:
        return
    with st.sidebar:
        st.markdown("---")
        st.caption("Logged in as")
        st.markdown(f"**{user.get('display_name')}**")
        st.caption(user.get("email", ""))
        if st.button("Logout", key="auth_logout_button"):
            revoke_current_session()
            _render_clear_browser_token(reload=True)
            st.stop()


def _render_login_css() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 2.2rem !important; max-width: 980px !important; }
        .zl-card {
            background: #ffffff;
            border: 1px solid #e8e8eb;
            border-radius: 24px;
            padding: 1.35rem 1.45rem;
            box-shadow: 0 12px 34px rgba(17,17,17,0.055);
            margin-top: 1rem;
        }
        .zl-kicker { color: #c5161d; font-size: 0.78rem; font-weight: 850; letter-spacing: 0.1em; text-transform: uppercase; }
        .zl-title { color: #111111; font-size: 1.65rem; font-weight: 850; letter-spacing: -0.03em; margin-top: 0.18rem; }
        .zl-text { color: #5f636b; font-size: 0.94rem; line-height: 1.5; margin-top: 0.5rem; }
        .zl-rule { color: #111111; font-weight: 720; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_login_page() -> None:
    _render_login_css()
    _render_browser_token_loader()

    st.markdown(
        f"""
        <div class="zl-card">
            <div class="zl-kicker">Zenith Project Tracker</div>
            <div class="zl-title">Company login required</div>
            <div class="zl-text">
                Please use your <span class="zl-rule">@{COMPANY_EMAIL_DOMAIN}</span> company email.
                After the first successful login, this browser will be remembered for {SESSION_COOKIE_DAYS} days unless you log out or clear browser data.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("auth_send_code_form"):
        default_email = st.session_state.get("pending_login_email", "")
        email = st.text_input("Company email", value=default_email, placeholder=f"harley@{COMPANY_EMAIL_DOMAIN}")
        send_submitted = st.form_submit_button("Send verification code", type="primary")

    if send_submitted:
        ok, message = send_login_otp(email)
        if ok:
            st.success(message)
        else:
            st.error(message)

    pending_email = st.session_state.get("pending_login_email")
    with st.form("auth_verify_code_form"):
        verify_email = st.text_input("Email for verification", value=pending_email or "", placeholder=f"harley@{COMPANY_EMAIL_DOMAIN}")
        code = st.text_input("Verification code", placeholder="6-digit code from email")
        verify_submitted = st.form_submit_button("Login")

    if verify_submitted:
        ok, message, user = verify_login_otp(verify_email, code)
        if ok:
            st.success(message)
            token = st.session_state.get(AUTH_TOKEN_STATE_KEY)
            if token:
                _render_store_browser_token(str(token))
            st.stop()
        else:
            st.error(message)

    with st.expander("Allowed company users in phase 1", expanded=False):
        allowed = [f"{name} — {email}" for name, email in PEOPLE_EMAIL_MAP.items()]
        st.write("\n".join(allowed))


def require_login() -> dict[str, str]:
    """Block every page until a company email user is authenticated."""
    init_db()

    current = get_current_user()
    if current:
        render_current_user_sidebar()
        return current

    query_token = _get_query_value(QUERY_SESSION_KEY)
    if query_token:
        user = verify_device_session(query_token)
        if user:
            st.session_state[AUTH_USER_STATE_KEY] = user.as_dict()
            st.session_state[AUTH_TOKEN_STATE_KEY] = query_token
            _clear_query_params()
            st.rerun()
        else:
            _render_clear_browser_token(reload=False)
            _clear_query_params()

    render_login_page()
    st.stop()
