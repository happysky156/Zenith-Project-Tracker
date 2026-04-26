from __future__ import annotations

import hashlib
import hmac
import html
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import streamlit as st
import streamlit.components.v1 as components

from core.dictionaries import COMPANY_EMAIL_DOMAIN, PEOPLE_EMAIL_MAP
from database.connection import execute, get_connection
from database.schema import init_db

SESSION_COOKIE_DAYS = 30
SESSION_STORAGE_KEY = "zenith_project_tracker_session_token"
SESSION_COOKIE_NAME = "zenith_project_tracker_session"
QUERY_SESSION_KEY = "zt_session"
# Streamlit Cloud sometimes blocks iframe JavaScript cookie/localStorage writes.
# Keep the random 30-day session token in the URL as a reliable fallback.
# Do not share a logged-in URL containing zt_session.
KEEP_QUERY_SESSION_FALLBACK = True
AUTH_USER_STATE_KEY = "auth_user"
AUTH_TOKEN_STATE_KEY = "auth_session_token"
USER_ACCESS_CODES_SECTION = "USER_ACCESS_CODES"
# Optional legacy fallback. Only used when USER_ACCESS_CODES is not configured.
ACCESS_CODE_SECRET_NAMES = (
    "INTERNAL_ACCESS_CODE",
    "ZENITH_ACCESS_CODE",
    "APP_ACCESS_CODE",
)


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
    """Read a secret from Streamlit Cloud/local secrets, then environment variables."""
    for name in names:
        value = os.getenv(name) or os.getenv(name.lower())
        if value:
            return str(value).strip()
        try:
            value = st.secrets.get(name)  # type: ignore[attr-defined]
        except Exception:
            value = None
        if value:
            return str(value).strip()
    return None


def _get_secret_section(section_name: str) -> dict[str, str]:
    """Read a TOML section from Streamlit Secrets.

    Streamlit Cloud secrets can contain sections such as:

    [USER_ACCESS_CODES]
    "harley@zenith-ecs.com" = "code-for-harley"

    This helper converts the section to a normal dict and strips empty values.
    """
    try:
        raw_section = st.secrets.get(section_name)  # type: ignore[attr-defined]
    except Exception:
        raw_section = None
    if not raw_section:
        return {}

    try:
        items = dict(raw_section).items()
    except Exception:
        return {}

    cleaned: dict[str, str] = {}
    for key, value in items:
        email = _normalize_email(str(key))
        code = str(value or "").strip()
        if email and code:
            cleaned[email] = code
    return cleaned


def _get_personal_access_codes() -> dict[str, str]:
    return _get_secret_section(USER_ACCESS_CODES_SECTION)


def _get_internal_access_code() -> str | None:
    """Legacy shared-code fallback for older deployments.

    v17.6 expects per-user codes in [USER_ACCESS_CODES]. The shared code is
    only kept as a fallback so the app can still start during migration.
    """
    return _get_secret(*ACCESS_CODE_SECRET_NAMES)


def _is_access_code_configured() -> bool:
    return bool(_get_personal_access_codes() or _get_internal_access_code())


def _get_expected_access_code_for_email(email: str) -> tuple[str | None, str]:
    normalized = _normalize_email(email)
    personal_codes = _get_personal_access_codes()
    if personal_codes:
        return personal_codes.get(normalized), "personal"
    return _get_internal_access_code(), "shared"


def _verify_internal_access_code(email: str, input_code: str | None) -> tuple[bool, str]:
    expected, mode = _get_expected_access_code_for_email(email)
    provided = str(input_code or "").strip()
    if not provided:
        return False, "Please enter your personal internal access code."
    if mode == "personal" and not expected:
        return False, "No personal access code is configured for this email in USER_ACCESS_CODES."
    if not expected:
        return False, "Access code is not configured in Streamlit Secrets."
    if not hmac.compare_digest(provided, expected):
        return False, "Access code is incorrect for this email. Please check your personal code."
    return True, ""


def _code_config_status_by_email() -> dict[str, bool]:
    codes = _get_personal_access_codes()
    return {email.lower(): email.lower() in codes for email in PEOPLE_EMAIL_MAP.values()}


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


def login_with_internal_code(email: str, access_code: str) -> tuple[bool, str, dict[str, str] | None]:
    """Meeting-friendly login: company email + personal internal access code.

    Each colleague has an individual code in Streamlit Secrets under
    [USER_ACCESS_CODES]. The email identifies the user; the matching personal
    code verifies that this user may log in. After success, the app creates a
    random 30-day device session, so users do not need to enter the code again
    in the same browser unless they log out or clear browser data.
    """
    normalized = _normalize_email(email)

    if not _is_access_code_configured():
        return False, (
            "Personal access codes are not configured. Please add [USER_ACCESS_CODES] "
            "in Streamlit Cloud Secrets."
        ), None

    allowed, message = is_allowed_login_email(normalized)
    if not allowed:
        return False, message, None

    ok_code, code_message = _verify_internal_access_code(normalized, access_code)
    if not ok_code:
        return False, code_message, None

    app_user = get_app_user(normalized)
    if not app_user:
        return False, "This user is not active.", None

    local_session_token = create_device_session(app_user)
    user_dict = app_user.as_dict()
    st.session_state[AUTH_USER_STATE_KEY] = user_dict
    st.session_state[AUTH_TOKEN_STATE_KEY] = local_session_token
    st.session_state["last_login_email"] = normalized
    _update_last_login(app_user.email)
    return True, "Login successful. This browser will be remembered for 30 days.", user_dict


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

    # Avoid last_seen_at writes on each page switch; this keeps meetings fast.
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
    st.session_state.pop("last_login_email", None)


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


def _get_cookie_token() -> str | None:
    """Read the remembered-login cookie when Streamlit exposes request cookies."""
    try:
        context = getattr(st, "context", None)
        cookies = getattr(context, "cookies", None)
        if cookies is not None:
            token = cookies.get(SESSION_COOKIE_NAME)
            if token:
                return str(token)
    except Exception:
        pass
    return None


def _render_browser_token_loader() -> None:
    storage_key = html.escape(SESSION_STORAGE_KEY)
    cookie_name = html.escape(SESSION_COOKIE_NAME)
    query_key = html.escape(QUERY_SESSION_KEY)
    components.html(
        f"""
        <script>
        (function() {{
            const storageKey = "{storage_key}";
            const cookieName = "{cookie_name}";
            const queryKey = "{query_key}";

            function rootWindow() {{
                try {{ return window.parent || window; }} catch (e) {{ return window; }}
            }}
            function readCookie(doc, name) {{
                try {{
                    const prefix = name + "=";
                    const parts = (doc.cookie || "").split(";");
                    for (let i = 0; i < parts.length; i++) {{
                        const part = parts[i].trim();
                        if (part.indexOf(prefix) === 0) {{
                            return decodeURIComponent(part.substring(prefix.length));
                        }}
                    }}
                }} catch (e) {{}}
                return null;
            }}

            const root = rootWindow();
            let token = null;
            try {{ token = root.localStorage.getItem(storageKey); }} catch (e) {{}}
            if (!token) {{ token = readCookie(root.document || document, cookieName); }}
            if (!token) {{ return; }}

            try {{
                const url = new URL(root.location.href);
                if (!url.searchParams.get(queryKey)) {{
                    url.searchParams.set(queryKey, token);
                    root.location.replace(url.toString());
                }}
            }} catch (e) {{}}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def _render_store_browser_token(token: str) -> None:
    safe_token = html.escape(token)
    storage_key = html.escape(SESSION_STORAGE_KEY)
    cookie_name = html.escape(SESSION_COOKIE_NAME)
    max_age = SESSION_COOKIE_DAYS * 24 * 60 * 60
    components.html(
        f"""
        <script>
        (function() {{
            const token = "{safe_token}";
            const storageKey = "{storage_key}";
            const cookieName = "{cookie_name}";
            const maxAge = {max_age};

            function rootWindow() {{
                try {{ return window.parent || window; }} catch (e) {{ return window; }}
            }}
            const root = rootWindow();

            // Best effort only. Some Streamlit Cloud/component iframe contexts block
            // parent-window cookie/localStorage writes, so the Python code also keeps
            // a query-parameter fallback. Do not force a browser reload here.
            try {{ root.localStorage.setItem(storageKey, token); }} catch (e) {{}}
            try {{
                const cookie = cookieName + "=" + encodeURIComponent(token)
                    + "; Max-Age=" + maxAge + "; Path=/; SameSite=Lax; Secure";
                (root.document || document).cookie = cookie;
            }} catch (e) {{}}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def _render_clear_browser_token(reload: bool = True) -> None:
    storage_key = html.escape(SESSION_STORAGE_KEY)
    cookie_name = html.escape(SESSION_COOKIE_NAME)
    query_key = html.escape(QUERY_SESSION_KEY)
    reload_js = "setTimeout(function() { try { root.location.reload(); } catch(e) {} }, 350);" if reload else ""
    components.html(
        f"""
        <script>
        (function() {{
            const storageKey = "{storage_key}";
            const cookieName = "{cookie_name}";
            const queryKey = "{query_key}";
            function rootWindow() {{
                try {{ return window.parent || window; }} catch (e) {{ return window; }}
            }}
            const root = rootWindow();
            try {{ root.localStorage.removeItem(storageKey); }} catch (e) {{}}
            try {{ (root.document || document).cookie = cookieName + "=; Max-Age=0; Path=/; SameSite=Lax; Secure"; }} catch (e) {{}}
            try {{
                const url = new URL(root.location.href);
                url.searchParams.delete(queryKey);
                root.history.replaceState(null, "", url.toString());
            }} catch (e) {{}}
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
                Please use your <span class="zl-rule">@{COMPANY_EMAIL_DOMAIN}</span> company email
                and your personal internal access code. After successful login, this browser will be remembered
                for {SESSION_COOKIE_DAYS} days unless you log out or clear browser data.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not _is_access_code_configured():
        st.warning("USER_ACCESS_CODES is not configured in Streamlit Secrets yet.")

    with st.form("auth_internal_code_form"):
        default_email = st.session_state.get("last_login_email", "")
        email = st.text_input("Company email", value=default_email, placeholder=f"harley@{COMPANY_EMAIL_DOMAIN}")
        access_code = st.text_input("Personal internal access code", type="password", placeholder="Your personal internal access code")
        submitted = st.form_submit_button("Login", type="primary")

    if submitted:
        ok, message, user = login_with_internal_code(email, access_code)
        if ok:
            token = st.session_state.get(AUTH_TOKEN_STATE_KEY)
            if token:
                # Set the URL fallback immediately and render the browser-storage
                # script without forcing an immediate rerun. On Streamlit Cloud,
                # forcing rerun too quickly can prevent the iframe JavaScript from
                # writing localStorage/cookie, which causes users to log in again
                # after closing the browser or restarting the computer.
                try:
                    st.query_params[QUERY_SESSION_KEY] = str(token)
                except Exception:
                    pass
                _render_store_browser_token(str(token))
            st.success(message)
            st.info("Login saved. Click Continue to enter the tracker. This gives the browser time to save the 30-day login token.")
            if st.button("Continue to tracker", type="primary", key="auth_continue_after_login"):
                st.rerun()
            st.stop()
        else:
            st.error(message)

    with st.expander("Allowed company users in this version", expanded=False):
        code_status = _code_config_status_by_email()
        personal_mode = bool(_get_personal_access_codes())
        allowed = []
        for name, email in PEOPLE_EMAIL_MAP.items():
            if personal_mode:
                status = "code configured" if code_status.get(email.lower()) else "code missing"
                allowed.append(f"{name} — {email} — {status}")
            else:
                allowed.append(f"{name} — {email}")
        st.write("\n".join(allowed))


def require_login() -> dict[str, str]:
    """Block every page until a company email user is authenticated.

    Fast path: page switches use only st.session_state and do not touch the
    remote database. Browser remember-me tokens are checked only when the
    current Streamlit session has no authenticated user.
    """
    current = get_current_user()
    if current:
        render_current_user_sidebar()
        return current

    cookie_token = _get_cookie_token()
    query_token = _get_query_value(QUERY_SESSION_KEY)
    browser_token = cookie_token or query_token
    if browser_token:
        user = verify_device_session(browser_token)
        if user:
            st.session_state[AUTH_USER_STATE_KEY] = user.as_dict()
            st.session_state[AUTH_TOKEN_STATE_KEY] = browser_token
            # Keep query token as a reliable remember-me fallback on Streamlit Cloud.
            # It is a random session token stored hashed in the database, not a password.
            if not KEEP_QUERY_SESSION_FALLBACK and query_token:
                _clear_query_params()
            st.rerun()
        else:
            _render_clear_browser_token(reload=False)
            _clear_query_params()

    render_login_page()
    st.stop()
