import streamlit as st
import bcrypt
import yaml
import os
import json
from pathlib import Path
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests

AUTH_CONFIG_FILE = Path(__file__).parent / "auth_config.yaml"
SETTINGS_FILE = Path(__file__).parent / ".settings.json"


def _get_secret(key: str, default: str = "") -> str:
    """Extremely defensive secret grabber to prevent StreamlitSecretNotFoundError."""
    try:
        # Only touch st.secrets if we are relatively sure it won't crash
        if hasattr(st, "secrets"):
            # Use direct access inside try to catch the custom Streamlit exception
            res = st.secrets.get(key)
            if res is not None:
                return str(res)
    except Exception:
        # This catches StreamlitSecretNotFoundError even if not explicitly imported
        pass
    return default


def _load_settings() -> dict:
    data = {}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text())
        except Exception:
            pass
            
    # Merge st.secrets if running in Streamlit Cloud (only if it doesn't crash)
    try:
        if hasattr(st, "secrets"):
            # Convert to dict safely
            secrets_dict = dict(st.secrets)
            for k, v in secrets_dict.items():
                if k not in data or not data[k]:
                    data[k] = v
    except Exception:
        pass
        
    return data


def _load_config() -> dict:
    """Load authentication config from YAML file."""
    if AUTH_CONFIG_FILE.exists():
        with open(AUTH_CONFIG_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _save_config(config: dict):
    """Save authentication config to YAML file."""
    with open(AUTH_CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def get_users() -> dict:
    """Get the users dict from config."""
    config = _load_config()
    return config.get("credentials", {}).get("usernames", {})


def add_user(username: str, name: str, password: str = "", role: str = "user", external_id: str = ""):
    """Add a new user to the config."""
    config = _load_config()
    if "credentials" not in config:
        config["credentials"] = {"usernames": {}}
    if "usernames" not in config["credentials"]:
        config["credentials"]["usernames"] = {}

    user_data = {
        "name": name,
        "role": role,
    }
    if password:
        user_data["password"] = hash_password(password)
    if external_id:
        user_data["external_id"] = external_id

    config["credentials"]["usernames"][username] = user_data
    _save_config(config)


def delete_user(username: str):
    """Remove a user from config."""
    config = _load_config()
    users = config.get("credentials", {}).get("usernames", {})
    if username in users:
        del users[username]
        _save_config(config)


def authenticate(username: str, password: str) -> tuple[bool, dict | None]:
    """
    Authenticate a user.
    Returns (True, user_dict) on success, (False, None) on failure.
    """
    users = get_users()
    user = users.get(username)
    if user and verify_password(password, user.get("password", "")):
        return True, {
            "username": username,
            "name": user.get("name", username),
            "role": user.get("role", "user"),
        }
    return False, None


import urllib.parse
import requests as http_requests


@st.cache_resource
def get_oauth_verifiers() -> dict:
    """Global in-memory store for PKCE verifiers, surviving Streamlit redirects."""
    return {}


def _get_redirect_uri() -> str:
    """
    Detect the correct redirect URI for Google OAuth.
    Tries to read the actual host from Streamlit's request headers first.
    Falls back to env vars, saved settings, then the hardcoded Streamlit Cloud URL.
    """
    # Try to read the real host from Streamlit's context headers (Streamlit >= 1.37)
    try:
        headers = st.context.headers  # type: ignore[attr-defined]
        host = headers.get("host", "") if hasattr(headers, "get") else ""
        if host and "localhost" not in host and "127.0.0.1" not in host:
            return f"https://{host}"
    except (AttributeError, Exception):
        pass

    # Fallback: env var APP_URL
    raw_url = os.environ.get("APP_URL", "") or _get_secret("APP_URL")
    if raw_url and "localhost" not in raw_url:
        return raw_url.rstrip("/")

    # Fallback: saved settings app_url
    settings = _load_settings()
    saved = settings.get("app_url", "")
    if saved and "localhost" not in saved:
        return saved.rstrip("/")

    # Local dev
    return "http://localhost:8501"


def get_google_oauth_url() -> tuple[str, str, str] | tuple[None, None, None]:
    """Build a Google OAuth URL with manual PKCE."""
    settings = _load_settings()
    client_id = settings.get("google_client_id")
    if not client_id:
        return None, None, None

    import secrets
    import hashlib
    import base64
    import os
    
    state = secrets.token_urlsafe(16)
    
    # Generate PKCE verifier and challenge
    verifier_bytes = os.urandom(32)
    code_verifier = base64.urlsafe_b64encode(verifier_bytes).rstrip(b'=').decode('utf-8')
    
    digest = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('utf-8')

    # Determine the redirect URI dynamically based on where the app is actually running.
    # Works for both localhost dev and Streamlit Cloud production.
    app_url = _get_redirect_uri()

    params = {
        "client_id": client_id,
        "redirect_uri": app_url,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    
    # Store the verifier globally so it survives the redirect (session_state gets wiped by the redirect)
    get_oauth_verifiers()[state] = code_verifier

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return auth_url, state, code_verifier


def exchange_google_code(code: str, code_verifier: str) -> dict | None:
    """Exchange auth code for user info using the PKCE verifier."""
    settings = _load_settings()
    client_id = settings.get("google_client_id")
    client_secret = settings.get("google_client_secret")
    if not client_id or not client_secret:
        return None

    # Use the same dynamic redirect URI logic
    app_url = _get_redirect_uri()

    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": app_url,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }
    
    token_resp = http_requests.post(
        "https://oauth2.googleapis.com/token",
        data=data,
        timeout=10,
    )
    if not token_resp.ok:
        raise Exception(f"Google Token Error: {token_resp.text}")
    tokens = token_resp.json()

    # Decode the ID token payload (no verification needed for email/name — we trust Google's TLS)
    import base64, json as _json
    payload_b64 = tokens["id_token"].split(".")[1]
    payload_b64 += "==" * (4 - len(payload_b64) % 4)  # fix padding
    return _json.loads(base64.b64decode(payload_b64))


def get_google_auth_flow():
    """Legacy compatibility shim — returns True if Google creds are configured."""
    settings = _load_settings()
    return bool(settings.get("google_client_id") and settings.get("google_client_secret"))


def init_default_users():
    """Create the config file with default admin user if it doesn't exist."""
    if not AUTH_CONFIG_FILE.exists():
        config = {
            "credentials": {
                "usernames": {
                    "admin": {
                        "name": "Administrator",
                        "password": hash_password("admin123"),
                        "role": "admin",
                    },
                    "cris": {
                        "name": "Cris",
                        "password": hash_password("cris2024"),
                        "role": "admin",
                    },
                }
            },
            "cookie": {
                "name": "cv_extractor_auth",
                "key": "cv_extractor_secret_key_2024",
                "expiry_days": 30,
            },
        }
        _save_config(config)


def render_login_page() -> bool:
    """
    Render the login page. Returns True if user is authenticated.
    Must be called at the top of app.py before any other content.
    """
    # Initialize default users if needed
    init_default_users()

    # Check if already authenticated
    if st.session_state.get("authenticated", False):
        return True

    # ── Handle Google OAuth Callback ──────────────────────────────────
    if "code" in st.query_params:
        code = st.query_params.get("code")
        state = st.query_params.get("state", "")
        try:
            # Retrieve the verifier from the server-global cache
            verifier = get_oauth_verifiers().pop(state, None)
            if not verifier:
                st.error("❌ Login-Sitzung abgelaufen oder ungültig. Bitte erneut versuchen.")
            else:
                id_info = exchange_google_code(code, verifier)
                if not id_info:
                    st.error("❌ Google-Konfiguration fehlt (Client ID/Secret nicht gesetzt).")
                else:
                    email = id_info.get("email")
                    name = id_info.get("name", email)
                    sub = id_info.get("sub")

                    users = get_users()
                    if email not in users:
                        add_user(email, name, role="user", external_id=sub)

                    user_data = get_users().get(email)
                st.session_state["authenticated"] = True
                st.session_state["user_info"] = {
                    "username": email,
                    "name": user_data.get("name", name),
                    "role": user_data.get("role", "user"),
                }
                st.query_params.clear()
                st.success(f"✅ Willkommen, {st.session_state.user_info['name']}!")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Google Login fehlgeschlagen: {e}")


    # Initialize view state
    if "auth_view" not in st.session_state:
        st.session_state.auth_view = "login"

    # ── Custom CSS for the login page ────────────────────────────────────
    st.markdown("""
    <style>
        /* Hide default Streamlit elements on login page */
        [data-testid="stSidebar"] { display: none; }

        .login-container {
            max-width: 440px;
            margin: 0 auto;
            padding: 20px 0;
        }
        .login-hero {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            border-radius: 16px;
            padding: 40px 32px 32px;
            text-align: center;
            margin-bottom: 24px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        .login-hero .logo-icon {
            font-size: 3.5rem;
            margin-bottom: 8px;
        }
        .login-hero h1 {
            color: #e2e8f0;
            font-size: 1.75rem;
            margin: 0 0 4px 0;
            font-weight: 700;
            letter-spacing: 0.5px;
        }
        .login-hero p {
            color: #94a3b8;
            margin: 0;
            font-size: 0.9rem;
        }
        .login-form-card {
            background: rgba(30, 41, 59, 0.4);
            border: 1px solid rgba(100, 116, 139, 0.2);
            border-radius: 12px;
            padding: 28px 24px;
            backdrop-filter: blur(10px);
        }
        .login-footer {
            text-align: center;
            color: #64748b;
            font-size: 0.78rem;
            margin-top: 16px;
        }
        .provider-badges {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 6px;
            margin-top: 14px;
        }
        .provider-badges .badge {
            display: inline-block;
            background: #0f3460;
            color: #60a5fa;
            border: 1px solid #1e40af;
            border-radius: 999px;
            font-size: 0.7rem;
            padding: 2px 10px;
        }
        .google-btn-link {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            background: white;
            color: #3c4043;
            border: 1px solid #dadce0;
            border-radius: 8px;
            padding: 10px 24px;
            margin-top: 16px;
            text-decoration: none;
            font-size: 14px;
            font-weight: 500;
            transition: background 0.2s, box-shadow 0.2s;
            box-shadow: 0 1px 2px rgba(60,64,67,0.3);
        }
        .google-btn-link:hover {
            background: #f8f9fa;
            box-shadow: 0 1px 3px rgba(60,64,67,0.3);
            text-decoration: none;
            color: #3c4043;
        }
        .google-btn-link img {
            width: 18px;
            height: 18px;
        }
    </style>
    """, unsafe_allow_html=True)

    # ── Hero header ──────────────────────────────────────────────────────
    badges = ["OpenAI", "Gemini", "Anthropic", "Mistral", "DeepSeek", "Grok", "Kimi K2", "Qwen", "Ollama"]
    badges_html = "".join(f'<span class="badge">{b}</span>' for b in badges)

    st.markdown(f"""
    <div class="login-container">
        <div class="login-hero">
            <div class="logo-icon">📄</div>
            <h1>CV Extractor</h1>
            <p>AI-Powered CV Processing & Template Populator</p>
            <div class="provider-badges">
                {badges_html}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        if st.session_state.auth_view == "login":
            render_login_form()
        else:
            render_signup_form()

        st.markdown(
            '<div class="login-footer">'
            "🔒 Zugangsdaten beim Administrator anfragen<br>"
            "CD International GmbH — Personaldienstleistung"
            "</div>",
            unsafe_allow_html=True,
        )

    return False


def render_login_form():
    """Render the login form."""
    st.markdown("#### 🔐 Anmeldung")
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("👤 Benutzername", placeholder="Benutzername eingeben", key="login_username")
        password = st.text_input("🔑 Passwort", type="password", placeholder="Passwort eingeben", key="login_password")
        submit = st.form_submit_button("🚀 Einloggen", type="primary", use_container_width=True)

    if submit:
        if not username or not password:
            st.error("⚠️ Bitte Benutzername und Passwort eingeben.")
        else:
            ok, user_info = authenticate(username, password)
            if ok:
                st.session_state["authenticated"] = True
                st.session_state["user_info"] = user_info
                st.success(f"✅ Willkommen, {user_info['name']}!")
                st.rerun()
            else:
                st.error("❌ Falscher Benutzername oder Passwort.")

    # Google Login Button
    google_configured = get_google_auth_flow()  # returns True/False now
    if google_configured:
        auth_url, state, verifier = get_google_oauth_url()
        # Verifier is stored inside get_google_oauth_url via get_oauth_verifiers()
        st.markdown(f"""
        <div style="text-align: center; margin: 15px 0; color: #64748b; font-size: 0.8rem;">ODER</div>
        <a href="{auth_url}" target="_self" class="google-btn-link">
            <img src="https://www.gstatic.com/images/branding/product/1x/gsa_512dp.png" alt="Google">
            Login mit Google
        </a>
        <br>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align: center; margin: 15px 0; color: #64748b; font-size: 0.8rem;">ODER</div>
        """, unsafe_allow_html=True)
        if st.button("🔴 Login mit Google (Nicht konfiguriert)", use_container_width=True):
            st.info("Bitte Google Client ID & Secret in den **⚙️ Einstellungen** hinterlegen.")

    if st.button("Kein Konto? Jetzt registrieren", use_container_width=True):
        st.session_state.auth_view = "signup"
        st.rerun()


def render_signup_form():
    """Render the signup form."""
    st.markdown("#### ✨ Registrierung")
    with st.form("signup_form", clear_on_submit=False):
        new_name = st.text_input("👤 Anzeigename", placeholder="Max Mustermann", key="signup_name")
        new_username = st.text_input("📧 Benutzername / E-Mail", placeholder="max@beispiel.de", key="signup_username")
        new_password = st.text_input("🔒 Passwort", type="password", placeholder="Passwort wählen", key="signup_password")
        new_password_confirm = st.text_input("🔒 Passwort bestätigen", type="password", placeholder="Passwort wiederholen", key="signup_password_confirm")
        submit = st.form_submit_button("✨ Konto erstellen", type="primary", use_container_width=True)

    if submit:
        if not new_name or not new_username or not new_password:
            st.error("⚠️ Bitte alle Felder ausfüllen.")
        elif new_password != new_password_confirm:
            st.error("⚠️ Passwörter stimmen nicht überein.")
        elif new_username in get_users():
            st.error(f"⚠️ Benutzername '{new_username}' existiert bereits.")
        else:
            add_user(new_username, new_name, new_password, role="user")
            st.success("✅ Konto erfolgreich erstellt! Du kannst dich jetzt einloggen.")
            st.session_state.auth_view = "login"
            st.rerun()

    if st.button("Bereits ein Konto? Zum Login", use_container_width=True):
        st.session_state.auth_view = "login"
        st.rerun()


def render_logout_button():
    """Render a logout button in the sidebar."""
    user_info = st.session_state.get("user_info", {})
    st.sidebar.markdown(f"👤 **{user_info.get('name', 'User')}**")
    st.sidebar.caption(f"Rolle: {user_info.get('role', 'user').title()}")
    if st.sidebar.button("🚪 Abmelden", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["user_info"] = None
        st.rerun()


def render_user_management():
    """Render admin-only user management UI (for the Settings tab)."""
    user_info = st.session_state.get("user_info", {})
    if user_info.get("role") != "admin":
        st.warning("⚠️ Nur Administratoren können Benutzer verwalten.")
        return

    st.markdown("### 👥 Benutzerverwaltung")

    users = get_users()

    # Show existing users
    if users:
        st.markdown("**Aktuelle Benutzer:**")
        for uname, udata in users.items():
            col_info, col_del = st.columns([4, 1])
            role_icon = "👑" if udata.get("role") == "admin" else "👤"
            col_info.markdown(
                f"{role_icon} **{udata.get('name', uname)}** (`{uname}`) "
                f"— {udata.get('role', 'user').title()}"
            )
            if uname != user_info.get("username"):  # Can't delete yourself
                if col_del.button("🗑️", key=f"del_user_{uname}", help=f"Benutzer {uname} löschen"):
                    delete_user(uname)
                    st.success(f"✅ Benutzer '{uname}' gelöscht.")
                    st.rerun()
    else:
        st.info("Keine Benutzer vorhanden.")

    # Add new user form
    st.divider()
    st.markdown("**➕ Neuen Benutzer anlegen:**")
    with st.form("add_user_form", clear_on_submit=True):
        nu_col1, nu_col2 = st.columns(2)
        with nu_col1:
            new_username = st.text_input("Benutzername", placeholder="max.mustermann")
            new_name = st.text_input("Anzeigename", placeholder="Max Mustermann")
        with nu_col2:
            new_password = st.text_input("Passwort", type="password", placeholder="••••••••")
            new_role = st.selectbox("Rolle", ["user", "admin"])

        if st.form_submit_button("💾 Benutzer anlegen", type="primary"):
            if not new_username or not new_password or not new_name:
                st.error("⚠️ Alle Felder sind Pflichtfelder.")
            elif new_username in users:
                st.error(f"⚠️ Benutzername '{new_username}' existiert bereits.")
            else:
                add_user(new_username, new_name, new_password, new_role)
                st.success(f"✅ Benutzer '{new_username}' angelegt!")
                st.rerun()

    # Change own password
    st.divider()
    st.markdown("**🔑 Eigenes Passwort ändern:**")
    with st.form("change_pw_form", clear_on_submit=True):
        old_pw = st.text_input("Aktuelles Passwort", type="password")
        new_pw = st.text_input("Neues Passwort", type="password")
        new_pw2 = st.text_input("Neues Passwort bestätigen", type="password")
        if st.form_submit_button("🔄 Passwort ändern"):
            if not old_pw or not new_pw:
                st.error("⚠️ Bitte alle Felder ausfüllen.")
            elif new_pw != new_pw2:
                st.error("⚠️ Neue Passwörter stimmen nicht überein.")
            else:
                ok, _ = authenticate(user_info["username"], old_pw)
                if ok:
                    config = _load_config()
                    config["credentials"]["usernames"][user_info["username"]]["password"] = hash_password(new_pw)
                    _save_config(config)
                    st.success("✅ Passwort geändert!")
                else:
                    st.error("❌ Aktuelles Passwort ist falsch.")
