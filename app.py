import streamlit as st
import os
import sys
import tempfile
import json
from pathlib import Path


from streamlit_mic_recorder import mic_recorder
from extractor import get_cv_data, get_identity_data, get_lebenslauf_data
from populator import populate_template, diagnose_template
from lebenslauf_builder import build_lebenslauf_docx
from auth import render_login_page, render_logout_button, render_user_management
from candidates_manager import (
    list_candidates, get_candidate, save_candidate_cv, save_candidate_lebenslauf,
    add_id_document, save_identcheck, delete_candidate, get_cv_path, get_id_paths,
    candidate_name_from_data, fetch_stored_json, CANDIDATES_DIR,
)
from chat_assistant import (
    send_chat_message, build_chat_messages, extract_json_from_response,
    CV_SYSTEM_PROMPT,
)
from extractor import extract_text_from_any

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CV Extractor & Template Populator",
    page_icon="📄",
    layout="wide",
)

# ── Authentication gate ───────────────────────────────────────────────────────
if not render_login_page():
    st.stop()

# ── Constants ─────────────────────────────────────────────────────────────────
JOB_PROFILES = [
    "Schweißer", "Schlosser", "Elektriker", "Lackierer", "Mechaniker",
    "Klempner", "Maurer", "Zimmermann", "Tischler", "Other",
]

AI_PROVIDERS = {
    "OpenAI":    {"models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],              "key_name": "openai_api_key",    "local": False},
    "Gemini":    {"models": ["gemini-1.5-pro", "gemini-1.5-flash", "google/gemini-pro"],               "key_name": "gemini_api_key",    "local": False},
    "Anthropic": {"models": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],                 "key_name": "anthropic_api_key", "local": False},
    "Mistral":   {"models": ["mistral-large-latest", "mistral-small-latest", "open-mistral-7b"],       "key_name": "mistral_api_key",   "local": False},
    "DeepSeek":  {"models": ["deepseek-chat", "deepseek-reasoner"],                                    "key_name": "deepseek_api_key",  "local": False},
    "Grok (xAI)":{"models": ["grok-3", "grok-3-turbo", "grok-3-mini", "grok-2"],                      "key_name": "grok_api_key",      "local": False},
    "Kimi K2":   {"models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],               "key_name": "kimi_api_key",      "local": False},
    "Qwen":      {"models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long"],                      "key_name": "qwen_api_key",      "local": False},
    "Perplexity":{"models": ["sonar-pro", "sonar", "llama-3.1-sonar-large-128k-online"],        "key_name": "perplexity_api_key", "local": False},
    "Ollama":     {"models": ["llama3.3", "llama3.1", "mistral", "gemma3", "phi4", "deepseek-r1"],      "key_name": "ollama_host",       "local": True},
    "TogetherAI": {"models": ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "mistralai/Mixtral-8x7B-Instruct-v0.1"], "key_name": "togetherai_api_key", "local": False},
    "Groq":       {"models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],                        "key_name": "groq_api_key",       "local": False},
    "OpenRouter": {"models": ["anthropic/claude-3.5-sonnet", "google/gemini-2.0-flash-001"],           "key_name": "openrouter_api_key", "local": False},
    "Xiaomi MiMo":{"models": ["mimo-v2-pro", "mimo-v2-mini"],                                          "key_name": "xiaomi_api_key",     "local": False},
}

SETTINGS_FILE = Path(__file__).parent / ".settings.json"
TEMPLATES_DIR = Path(__file__).parent / "templates"
TEMPLATES_DIR.mkdir(exist_ok=True)

# ── Persist settings to JSON ──────────────────────────────────────────────────
def load_settings() -> dict:
    data = {}
    # 1. Try file
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text())
        except Exception:
            pass
    
    # 2. Merge st.secrets if running in Streamlit Cloud (only if it doesn't crash)
    try:
        if hasattr(st, "secrets"):
            # Use dict() conversion inside try to catch parsing errors
            secrets_dict = dict(st.secrets)
            for k, v in secrets_dict.items():
                if k not in data or not data[k]:
                    data[k] = v
    except Exception:
        pass
        
    return data

def save_settings(data: dict):
    SETTINGS_FILE.write_text(json.dumps(data, indent=2))

# ── Session-state bootstrap ───────────────────────────────────────────────────
if "settings" not in st.session_state:
    st.session_state.settings = load_settings()

def cfg(key, default=""):
    # 1. From session_state (user input in UI)
    val = st.session_state.settings.get(key, "").strip()
    if val: return val
    
    # 2. From environment variables (for Docker / Cloud Run deployment)
    # Convert key to uppercase (e.g., openai_api_key -> OPENAI_API_KEY)
    env_val = os.environ.get(key.upper(), "").strip()
    if env_val: return env_val

    return default.strip()

# ── Session history bootstrap ─────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []   # list of {name, provider, model, ts, type}

def _add_history(name: str, provider: str, model: str, record_type: str = "CV"):
    from datetime import datetime
    st.session_state.history.insert(0, {
        "name": name, "provider": provider, "model": model,
        "ts": datetime.now().strftime("%H:%M"), "type": record_type,
    })
    st.session_state.history = st.session_state.history[:10]  # keep last 10

if "extracted_data_buffer" not in st.session_state:
    st.session_state.extracted_data_buffer = None
if "auto_trust_ai" not in st.session_state:
    st.session_state.auto_trust_ai = False

def get_fallback_providers(primary_provider: str) -> list[tuple[str, str, str]]:
    """Return (provider, model, api_key) for every configured provider except the primary."""
    fallbacks = []
    for prov, info in AI_PROVIDERS.items():
        if prov == primary_provider:
            continue
        key = cfg(info["key_name"])
        if info["local"]:
            # For local providers like Ollama, only include if explicitly configured (not just default)
            # or if we want to allow the user to try it. But for fallback, let's be more picky.
            if not key or key == "http://localhost:11434":
                continue
        if key:
            fallbacks.append((prov, info["models"][0], key))
    return fallbacks

# ── Header ─────────────────────────────────────────────────────────────────────
BADGE_LABELS = ["OpenAI", "Gemini", "Anthropic", "Mistral", "DeepSeek", "Grok", "Kimi K2", "Qwen", "Ollama"]
badges_html = "".join(f'<span class="badge">{b}</span>' for b in BADGE_LABELS)

# ── PWA injection ─────────────────────────────────────────────────────────────
# Injects manifest link + SW registration into the page <head>
st.markdown("""
<link rel="manifest" href="/app/static/manifest.json">
<meta name="theme-color" content="#60a5fa">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="CV Extractor">
<link rel="apple-touch-icon" href="/app/static/icons/icon-192.png">
<script>
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/app/static/sw.js')
      .then(r => console.log('SW registered:', r.scope))
      .catch(e => console.warn('SW failed:', e));
  }
</script>
""", unsafe_allow_html=True)

st.markdown(f"""
<style>
    .hero {{ background: linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);
             border-radius:12px; padding:28px 32px; margin-bottom:24px; }}
    .hero h1 {{ color:#e2e8f0; font-size:2rem; margin:0 0 8px 0; }}
    .hero p  {{ color:#94a3b8; margin:0; }}
    .badge   {{ display:inline-block; background:#0f3460; color:#60a5fa;
                border:1px solid #1e40af; border-radius:999px;
                font-size:.75rem; padding:2px 10px; margin-right:6px; margin-top:4px; }}
    
    /* Bento Grid System */
    .bento-grid {{
        display: grid;
        grid-template-columns: repeat(12, 1fr);
        gap: 1.5rem;
        padding: 10px 0;
    }}
    .bento-card {{
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 24px;
        padding: 20px;
        transition: all 0.3s ease;
        height: 100%;
        color: #e2e8f0;
    }}
    .bento-card:hover {{
        border: 1px solid rgba(0, 255, 242, 0.4);
        box-shadow: 0 0 20px rgba(0, 255, 242, 0.05);
    }}
    .bento-title {{
        font-weight: 700;
        font-size: 1.1rem;
        margin-bottom: 12px;
        color: #00fff2;
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    .bento-hero {{ grid-column: span 8; border-left: 4px solid #00fff2; }}
    .bento-side {{ grid-column: span 4; }}
    
    /* Input overrides for Cinematic feel */
    div[data-baseweb="input"] {{
        background: rgba(255,255,255,0.05) !important;
        border-radius: 12px !important;
    }}
</style>
<div class="hero">
  <h1>📄 CV Extractor &amp; Template Populator</h1>
  <p>Upload a CV, pick a job profile and a template — AI extracts the data and fills the document.</p>
  <br/>
  {badges_html}
</div>
""", unsafe_allow_html=True)

# ── Sidebar — Recent Candidates ──────────────────────────────────────────────
with st.sidebar:
    render_logout_button()
    st.divider()
    
    st.markdown("### 📋 Recent Candidates")
    
    # Get all candidates from disk
    from candidates_manager import list_candidates
    sc_cands = list_candidates()
    # Sort by mtime if possible, but manager might already have it or we sort here
    # Our manager already provides last_modified (formatted string). 
    # Let's just use the list.
    
    if not sc_cands:
        st.caption("No candidates processed yet.")
    else:
        for c in sc_cands[:10]:
            name = c["name"]
            folder = c["folder"]
            # Icons based on files present
            icons = ""
            if c["has_cv"]:         icons += "📄"
            if c["has_lebenslauf"]:   icons += "📋"
            if c["has_id"]:          icons += "🪪"
            if c["has_identcheck"]:  icons += "✅"
            
            with st.container(border=True):
                c_col1, c_col2 = st.columns([4, 1])
                c_col1.markdown(f"**{name}**")
                c_col1.caption(f"{icons} {c['last_modified']}")
                
                # Hidden button to select this candidate
                if c_col2.button("📂", key=f"side_open_{folder}", help="Open Project"):
                    st.session_state.k_select_folder = folder
                    st.toast(f"Switched to: {name}")

                # JSON Sync to Bento Hero Card
                if st.sidebar.button(f"🔄 Sync {name}", key=f"sync_{folder}", use_container_width=True):
                    # 1. Fetch data
                    saved_data = fetch_stored_json(folder)
                    cv_file_path = get_cv_path(folder)
                    
                    # 2. Sync to Buffer
                    if saved_data and cv_file_path:
                        st.session_state.extracted_data_buffer = {
                            "data": saved_data,
                            "cv_path": cv_file_path,
                            "cv_name": Path(cv_file_path).name,
                            "cv_buffer": open(cv_file_path, "rb").read(),
                            "tpl_path": str(TEMPLATES_DIR / "Schweißer_template.docx"), # Fallback tpl
                            "provider": "Saved",
                            "model": "Historical",
                            "status": "synced",
                            "final_path": str(CANDIDATES_DIR / folder / "Populated_CV.docx")
                        }
                        st.session_state.active_tab = "🚀 Process CV"
                        st.toast(f"Synchronized {name} to Review Station!")
                        st.rerun()
                    else:
                        st.error("Could not find extraction data for this candidate.")

    if st.button("🗑️ Clear Local History", use_container_width=True):
        st.session_state.history = []  # Keep legacy history clear for now
        st.rerun()

st.sidebar.title("🧭 Navigation")
nav_options = [
    "🚀 Process CV", "👥 Candidates", "📁 Templates", 
    "🪪 Identcheck", "📜 Lebenslauf", "⚙️ Settings"
]
if "active_tab" not in st.session_state:
    st.session_state.active_tab = nav_options[0]

active_tab = st.sidebar.radio("Go to", nav_options, index=nav_options.index(st.session_state.active_tab))
st.session_state.active_tab = active_tab

# Assistant Launcher in Sidebar
st.sidebar.divider()
st.sidebar.subheader("🎙️ AI Assistant")
with st.sidebar.expander("💬 Chat & Voice Commands", expanded=False):
    # Assistant configuration
    c1, c2 = st.columns(2)
    chat_provider = c1.selectbox("Provider", list(AI_PROVIDERS.keys()), key="chat_side_prov", index=0)
    chat_model = c2.selectbox("Model", AI_PROVIDERS[chat_provider]["models"], key="chat_side_model")
    
    st.caption("Choose STT Provider:")
    stt_prov = st.radio("STT", ["OpenAI", "Deepgram", "Eleven Labs"], horizontal=True, key="stt_side_prov", label_visibility="collapsed")
    
    st.markdown("---")
    
    # 🎤 Microphone Recorder
    footer_cols = st.columns([1, 4])
    with footer_cols[0]:
        audio = mic_recorder(
            start_prompt="🎙️",
            stop_prompt="🛑",
            key='side_mic',
            use_container_width=False,
        )
    
    transcribed_text = ""
    if audio:
        stt_key_map = {
            "OpenAI": ("OpenAI", "openai_api_key"),
            "Deepgram": ("Deepgram", "deepgram_api_key"),
            "Eleven Labs": ("Eleven Labs", "elevenlabs_api_key")
        }
        actual_prov, key_name = stt_key_map[stt_prov]
        stt_api_key = cfg(key_name)
        
        if stt_api_key:
            with st.spinner("Transcribing..."):
                from chat_assistant import transcribe_audio
                try:
                    transcribed_text = transcribe_audio(audio['bytes'], actual_prov, stt_api_key)
                    if transcribed_text:
                        st.info(f"You said: {transcribed_text}")
                except Exception as e:
                    st.error(f"STT Error: {e}")
        else:
            st.error(f"Missing {actual_prov} API key.")

    # Chat History Display
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    
    for msg in st.session_state.chat_messages[-5:]: # Show last 5
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat Input
    side_input = st.chat_input("Ask or speak...")
    
    prompt = None
    if side_input:
        prompt = side_input
    elif transcribed_text:
        if "last_side_stt" not in st.session_state or st.session_state.last_side_stt != transcribed_text:
            prompt = transcribed_text
            st.session_state.last_side_stt = transcribed_text

    if prompt:
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("AI is thinking..."):
                try:
                    # Get current candidate context if available
                    cv_ctx, id_ctx = None, None
                    if "k_select_folder" in st.session_state:
                         from candidates_manager import get_cv_path, get_id_paths
                         cv_p = get_cv_path(st.session_state.k_select_folder)
                         if cv_p: cv_ctx = extract_text_from_any(cv_p)
                         id_ps = get_id_paths(st.session_state.k_select_folder)
                         if id_ps: id_ctx = "\n".join([extract_text_from_any(p) for p in id_ps])

                    from chat_assistant import build_chat_messages, send_chat_message
                    full_msgs = build_chat_messages(
                        st.session_state.chat_messages,
                        cv_text=cv_ctx,
                        id_text=id_ctx,
                        context_name=st.session_state.active_tab
                    )
                    resp = send_chat_message(full_msgs, chat_provider, chat_model, cfg(AI_PROVIDERS[chat_provider]["key_name"]))
                    st.markdown(resp)
                    st.session_state.chat_messages.append({"role": "assistant", "content": resp})
                except Exception as e:
                    st.error(f"Error: {e}")

    if st.button("🗑️ Clear", key="clear_side_chat"):
        st.session_state.chat_messages = []
        st.rerun()

# ═══════════════════════════════════════════════════════════════════
# TAB 1 — PROCESS CV
# ═══════════════════════════════════════════════════════════════════
if active_tab == "🚀 Process CV":
    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.subheader("Configuration")
        st.info("💡 **Missing models?** Add your API keys in the **⚙️ Settings** tab to enable them.")

        provider = st.selectbox(
            "🤖 AI Provider", list(AI_PROVIDERS.keys()),
            index=list(AI_PROVIDERS.keys()).index(cfg("provider", "OpenAI"))
                  if cfg("provider", "OpenAI") in AI_PROVIDERS else 0,
        )
        model = st.selectbox("Model", AI_PROVIDERS[provider]["models"], index=0)

        job_role = st.selectbox(
            "💼 Job Profile", JOB_PROFILES,
            index=JOB_PROFILES.index(cfg("default_job_role", "Schweißer"))
                  if cfg("default_job_role", "Schweißer") in JOB_PROFILES else 0,
        )
        if job_role == "Other":
            job_role = st.text_input("Enter custom job role")

        st.divider()
        st.markdown("**📝 Word Template**")
        template_source = st.radio("Source", ["Upload now", "Saved templates"], label_visibility="collapsed")
        chosen_template_path = None
        if template_source == "Saved templates":
            saved_tpls = list(TEMPLATES_DIR.glob("*.docx"))
            if saved_tpls:
                sel = st.selectbox("Choose template", [f.name for f in saved_tpls])
                chosen_template_path = TEMPLATES_DIR / sel
            else:
                st.info("No saved templates yet. Upload one in the **Templates** tab.")

    with col_right:
        st.subheader("Upload CV")
        cv_file = st.file_uploader("CV file (PDF or DOCX)", type=["pdf", "docx"], label_visibility="collapsed")
        if template_source == "Upload now":
            st.subheader("Upload Template")
            template_file = st.file_uploader("Word template (DOCX)", type=["docx"], label_visibility="collapsed")
        else:
            template_file = None

        st.divider()
        run = st.button("⚡ Process CV", type="primary", use_container_width=True, disabled=cv_file is None)

        if run:
            is_local = AI_PROVIDERS[provider]["local"]
            api_key  = cfg(AI_PROVIDERS[provider]["key_name"]) or (
                "http://localhost:11434" if is_local else ""
            )
            if not api_key and not is_local:
                st.error(f"❌ No {provider} API key found. Please add it in the **⚙️ Settings** tab.")
            elif template_source == "Upload now" and template_file is None:
                st.warning("⚠️ Please upload a Word template or choose a saved one.")
            elif template_source == "Saved templates" and chosen_template_path is None:
                st.warning("⚠️ No saved template selected.")
            else:
                _prog = st.progress(0, text="📂 Reading CV file…")
                try:
                    # Step 1 — save CV to temp
                    suffix = Path(cv_file.name).suffix
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(cv_file.getbuffer())
                        cv_path = tmp.name

                    _prog.progress(25, text="🤖 Sending to AI for extraction…")

                    if template_file:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                            tmp.write(template_file.getbuffer())
                            tpl_path = tmp.name
                    else:
                        tpl_path = str(chosen_template_path)

                    # Step 2 — AI extraction (with auto-fallback on 401 / error)
                    _used_provider, _used_model = provider, model
                    extracted = None
                    _errors = []
                    
                    # Try primary + fallbacks
                    attempt_list = [(provider, model, api_key)] + get_fallback_providers(provider)
                    for _p, _m, _k in attempt_list:
                        try:
                            extracted = get_lebenslauf_data([cv_path], job_role=job_role, provider=_p, model=_m, api_key=_k)
                            _used_provider, _used_model = _p, _m
                            if _p != provider:
                                st.toast(f"⚠️ {provider} failed → switched to **{_p}**", icon="🔄")
                            break
                        except Exception as _e:
                            err_msg = str(_e)
                            # If it's a connection error to localhost/Ollama, keep it brief
                            if "Connection error" in err_msg and "11434" in err_msg:
                                _errors.append(f"{_p}: Connection refused (Ollama not running?)")
                            else:
                                _errors.append(f"{_p}: {err_msg}")
                            continue

                    if extracted is None:
                        combined_errs = "\n".join([f"- {e}" for e in _errors])
                        raise RuntimeError(f"All providers failed:\n{combined_errs}")
                    
                    extracted["job_role"] = job_role or extracted.get("job_role", "N/A")
                    
                    # Instead of auto-generating, push to Buffer for Human Review
                    st.session_state.extracted_data_buffer = {
                        "data": extracted,
                        "cv_path": cv_path,
                        "cv_name": cv_file.name,
                        "cv_buffer": cv_file.getbuffer(),
                        "tpl_path": tpl_path,
                        "provider": _used_provider,
                        "model": _used_model,
                        "status": "ready"
                    }
                    
                    if st.session_state.auto_trust_ai:
                        # Auto-approve if toggle is ON
                        cand_name = candidate_name_from_data(extracted)
                        _add_history(cand_name, _used_provider, _used_model, "CV")
                        out_name = f"Populated_{Path(cv_file.name).stem}.docx"
                        out_path = os.path.join(tempfile.gettempdir(), out_name)
                        populate_template(tpl_path, out_path, extracted)
                        save_candidate_cv(cand_name, cv_file.getbuffer(), cv_file.name, extracted, out_path)
                        st.session_state.extracted_data_buffer["final_path"] = out_path
                        st.session_state.extracted_data_buffer["status"] = "synced"
                        st.toast("Anti-Gravity Mode: AI Trust Sync successful!")

                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    st.error(f"❌ Error: {e}")
                finally:
                    _prog.empty()

        # ── 🔍 BENTO REVIEW BRIDGE ───────────────────────────────────
        if st.session_state.extracted_data_buffer:
            buf = st.session_state.extracted_data_buffer
            ext = buf["data"]
            
            st.divider()
            st.markdown("### 🔍 Human-in-the-Loop Review")
            st.caption("Verify and optimize the AI-extracted metadata before synchronizing to Candidate Vault.")

            # Layout manually as Streamlit columns don't easily mirror CSS grid spans 
            # while maintaining reactive widgets, but we wrap them in our CSS classes.
            col_b1, col_b2 = st.columns([2, 1])

            with col_b1:
                st.markdown('<div class="bento-card bento-hero">', unsafe_allow_html=True)
                st.markdown('<div class="bento-title">✨ Hero Review Station</div>', unsafe_allow_html=True)
                
                c_edit1, c_edit2 = st.columns(2)
                with c_edit1:
                    default_name = ext.get("name", "") or f"{ext.get('vorname', '')} {ext.get('nachname', '')}".strip()
                    rev_name = st.text_input("Name", value=default_name, key="rev_name")
                    
                    default_dob = ext.get("geburtsdatum", ext.get("birth_date", ""))
                    rev_dob = st.text_input("Birth Date", value=default_dob, key="rev_dob")
                    
                    rev_email = st.text_input("Email", value=ext.get("email", ""), key="rev_email")
                with c_edit2:
                    default_role = ext.get("job_role", "")
                    rev_role = st.text_input("Current Role", value=default_role, key="rev_role")
                    
                    default_pob = ext.get("geburtsort", ext.get("birth_place", ""))
                    rev_pob = st.text_input("Birth Place", value=default_pob, key="rev_pob")
                    
                    default_nat = ext.get("nationality", "") or ext.get("staatsangehoerigkeit", "")
                    rev_nationality = st.text_input("Nationality", value=default_nat, key="rev_nat")
                
                default_sum = ext.get("profile_summary", "") or ext.get("zusammenfassung", "")
                rev_summary = st.text_area("German Synthesis / Summary", value=default_sum, height=180, key="rev_summary")
                
                # --- SYNC BUFFER ---
                ext["name"] = rev_name
                if " " in rev_name:
                    ext["vorname"], ext["nachname"] = rev_name.split(" ", 1)
                else:
                    ext["vorname"] = ""; ext["nachname"] = rev_name
                
                ext["email"] = rev_email
                ext["job_role"] = rev_role
                ext["nationality"] = rev_nationality
                ext["staatsangehoerigkeit"] = rev_nationality
                ext["profile_summary"] = rev_summary
                ext["zusammenfassung"] = rev_summary
                
                # New fields sync
                ext["birth_date"] = rev_dob; ext["geburtsdatum"] = rev_dob
                ext["birth_place"] = rev_pob; ext["geburtsort"] = rev_pob

                st.markdown('</div>', unsafe_allow_html=True)

            with col_b2:
                st.markdown('<div class="bento-card">', unsafe_allow_html=True)
                st.markdown('<div class="bento-title">⚙️ Automation Vault</div>', unsafe_allow_html=True)
                st.session_state.auto_trust_ai = st.toggle("Trust AI (Anti-Gravity Mode)", value=st.session_state.auto_trust_ai, help="Skip review and auto-generate documents")
                
                st.info(f"AI Provider: **{buf['provider']}**\nModel: `{buf['model']}`")
                
                if buf["status"] == "ready":
                    if st.button("✨ Approve & Synchronize", type="primary", use_container_width=True):
                        try:
                            c_name = candidate_name_from_data(ext)
                            out_name = f"Populated_{Path(buf['cv_name']).stem}.docx"
                            out_path = os.path.join(tempfile.gettempdir(), out_name)
                            
                            _add_history(c_name, buf["provider"], buf["model"], "CV")
                            populate_template(buf["tpl_path"], out_path, ext)
                            save_candidate_cv(c_name, buf["cv_buffer"], buf["cv_name"], ext, out_path)
                            
                            st.session_state.extracted_data_buffer["status"] = "synced"
                            st.session_state.extracted_data_buffer["final_path"] = out_path
                            st.success("Synchronized successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Sync failed: {e}")
                else:
                    st.success("✅ Document Finalized")
                    with open(buf["final_path"], "rb") as f:
                        st.download_button("⬇️ Download Final Word Doc", data=f, file_name=f"Populated_{Path(buf['cv_name']).stem}.docx", use_container_width=True)
                    if st.button("🔄 Process New CV", use_container_width=True):
                        st.session_state.extracted_data_buffer = None
                        st.rerun()
                
                st.markdown('</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════
# TAB 2 — TEMPLATES
# ═══════════════════════════════════════════════════════════════════
if active_tab == "📁 Templates":
    st.subheader("📁 Manage Templates")
    st.markdown("Upload and store Word (.docx) templates for each job profile. Saved templates appear in the **Process CV** tab.")
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Upload a new template**")
        tpl_job = st.selectbox("Associate with job profile", JOB_PROFILES, key="tpl_job_sel")
        tpl_upload = st.file_uploader("DOCX template", type=["docx"], key="tpl_uploader")
        tpl_name_override = st.text_input("Custom filename (optional)", placeholder=f"{tpl_job}_template.docx")
        st.divider()
        st.subheader("🤖 Automation & Trust")
        auto_val = st.checkbox("Trust AI (Anti-Gravity Mode)", value=st.session_state.settings.get("auto_trust_ai", False), help="Bypass the review bridge and auto-generate documents after extraction.")
        st.session_state.settings["auto_trust_ai"] = auto_val
        st.session_state.auto_trust_ai = auto_val

        if st.button("💾 Save Template", type="primary"):
            if tpl_upload is None:
                st.warning("Please upload a DOCX file first.")
            else:
                fname = tpl_name_override.strip() or f"{tpl_job.replace(' ','_')}_template.docx"
                if not fname.endswith(".docx"):
                    fname += ".docx"
                (TEMPLATES_DIR / fname).write_bytes(tpl_upload.getbuffer())
                st.success(f"✅ Saved as **{fname}**")

    with col_b:
        st.markdown("**Saved templates**")
        saved_list = sorted(TEMPLATES_DIR.glob("*.docx"))
        if saved_list:
            for f in saved_list:
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"📄 `{f.name}`  \n<small>{f.stat().st_size // 1024} KB</small>", unsafe_allow_html=True)
                if c2.button("🗑️", key=f"del_{f.name}", help=f"Delete {f.name}"):
                    f.unlink()
                    st.rerun()
        else:
            st.info("No templates saved yet.")

# ═══════════════════════════════════════════════════════════════════
# TAB 3 — SETTINGS
# ═══════════════════════════════════════════════════════════════════
if active_tab == "⚙️ Settings":
    st.subheader("⚙️ Settings")
    st.caption("Keys are stored locally in `.settings.json` in the app directory. They never leave your machine.")

    from extractor import validate_key as _validate_key

    st.markdown("### 🔑 API Keys")
    st.caption(
        "Keys are stored in `.settings.json` and never leave your machine.  "
        "Click **🔍** next to any key to test it before saving."
    )

    KEY_DEFS = [
        ("OpenAI",     "openai_api_key",     "sk-…",                  "🟢"),
        ("Gemini",     "gemini_api_key",     "AIza…",                 "🔵"),
        ("Anthropic",  "anthropic_api_key",  "sk-ant-…",              "🟣"),
        ("Mistral",    "mistral_api_key",    "…",                     "🌊"),
        ("DeepSeek",   "deepseek_api_key",   "sk-…",                  "🔷"),
        ("Grok (xAI)", "grok_api_key",       "xai-…",                 "⚡"),
        ("Kimi K2",    "kimi_api_key",       "sk-…",                  "🌙"),
        ("Qwen",       "qwen_api_key",       "sk-…",                  "🐋"),
        ("Perplexity", "perplexity_api_key", "pplx-…",                "🧠"),
        ("TogetherAI", "togetherai_api_key", "tgp_v1_…",              "🚀"),
        ("Groq",       "groq_api_key",       "gsk_…",                 "🏎️"),
        ("OpenRouter", "openrouter_api_key", "sk-or-v1-…",            "🌐"),
        ("Xiaomi MiMo","xiaomi_api_key",     "sk-…",                  "📱"),
        ("Ollama",     "ollama_host",        "http://localhost:11434", "🦙"),
        ("Deepgram",   "deepgram_api_key",   "Token …",               "🎙️"),
        ("Eleven Labs","elevenlabs_api_key", "xi-api-key …",          "🗣️"),
    ]

    # Bootstrap staging state
    if "key_staging" not in st.session_state:
        st.session_state.key_staging = {k: cfg(k) for _, k, _, _ in KEY_DEFS}
        # Add Google keys if not present
        st.session_state.key_staging["google_client_id"] = cfg("google_client_id")
        st.session_state.key_staging["google_client_secret"] = cfg("google_client_secret")
    if "key_test_results" not in st.session_state:
        st.session_state.key_test_results = {}

    st.markdown("### 🌐 Google OAuth")
    st.caption("Needed for 'Login with Google'. Get these from your Google Cloud Console.")
    co1, co2 = st.columns(2)
    with co1:
        g_client_id = st.text_input("Google Client ID", value=st.session_state.key_staging.get("google_client_id", ""), placeholder="...apps.googleusercontent.com")
    with co2:
        g_client_secret = st.text_input("Google Client Secret", value=st.session_state.key_staging.get("google_client_secret", ""), type="password")
    
    # Update staging with Google keys too
    st.session_state.key_staging["google_client_id"] = g_client_id
    st.session_state.key_staging["google_client_secret"] = g_client_secret

    c1, c2 = st.columns(2)
    for idx, (prov_name, key_name, placeholder, icon) in enumerate(KEY_DEFS):
        col = c1 if idx % 2 == 0 else c2
        with col:
            is_ollama = (prov_name == "Ollama")
            st.markdown(f"{icon} **{prov_name}**" + (" *(local – no key needed)*" if is_ollama else ""))
            inp_col, btn_col = st.columns([5, 1])
            with inp_col:
                new_val = st.text_input(
                    f"_{prov_name} key_",
                    value=st.session_state.key_staging.get(key_name, ""),
                    type="default" if is_ollama else "password",
                    placeholder=placeholder,
                    key=f"staging_{key_name}",
                    label_visibility="collapsed",
                )
                st.session_state.key_staging[key_name] = new_val
            with btn_col:
                if st.button("🔍", key=f"test_{key_name}", help=f"Test {prov_name} connection"):
                    test_val = (st.session_state.key_staging.get(key_name) or "").strip()
                    if not test_val:
                        st.session_state.key_test_results[key_name] = ("warn", "⚠️ Enter a key first")
                    else:
                        first_model = AI_PROVIDERS.get(prov_name, {}).get("models", [""])[0]
                        ok, msg = _validate_key(prov_name, test_val, first_model)
                        st.session_state.key_test_results[key_name] = ("ok" if ok else "err", msg)
                    st.rerun()
            result = st.session_state.key_test_results.get(key_name)
            if result:
                kind, msg = result
                if kind == "ok":   st.success(msg)
                elif kind == "warn": st.warning(msg)
                else:              st.error(msg)

    st.divider()
    st.markdown("### 🎛️ Defaults")
    cd1, cd2 = st.columns(2)
    with cd1:
        def_provider = st.selectbox(
            "Default AI Provider", list(AI_PROVIDERS.keys()),
            index=list(AI_PROVIDERS.keys()).index(cfg("provider", "OpenAI"))
                  if cfg("provider", "OpenAI") in AI_PROVIDERS else 0,
            key="settings_def_provider",
        )
    with cd2:
        def_job = st.selectbox(
            "Default Job Profile", JOB_PROFILES,
            index=JOB_PROFILES.index(cfg("default_job_role", "Schweißer"))
                  if cfg("default_job_role", "Schweißer") in JOB_PROFILES else 0,
            key="settings_def_job",
        )

    if st.button("💾 Save All Settings", type="primary", use_container_width=True):
        new_settings = {k: (st.session_state.key_staging.get(k) or "").strip() for _, k, _, _ in KEY_DEFS}
        new_settings["google_client_id"] = (st.session_state.key_staging.get("google_client_id") or "").strip()
        new_settings["google_client_secret"] = (st.session_state.key_staging.get("google_client_secret") or "").strip()
        new_settings["ollama_host"] = new_settings.get("ollama_host") or "http://localhost:11434"
        
        # New provider keys
        new_settings["deepgram_api_key"] = (st.session_state.key_staging.get("deepgram_api_key") or "").strip()
        new_settings["elevenlabs_api_key"] = (st.session_state.key_staging.get("elevenlabs_api_key") or "").strip()
        new_settings["togetherai_api_key"] = (st.session_state.key_staging.get("togetherai_api_key") or "").strip()
        new_settings["groq_api_key"] = (st.session_state.key_staging.get("groq_api_key") or "").strip()
        new_settings["openrouter_api_key"] = (st.session_state.key_staging.get("openrouter_api_key") or "").strip()
        new_settings["xiaomi_api_key"] = (st.session_state.key_staging.get("xiaomi_api_key") or "").strip()

        new_settings["provider"]         = def_provider
        new_settings["default_job_role"] = def_job
        save_settings(new_settings)
        st.session_state.settings = new_settings
        # Refresh staging
        st.session_state.key_staging = {k: new_settings.get(k, "") for _, k, _, _ in KEY_DEFS}
        st.session_state.key_staging["google_client_id"] = new_settings.get("google_client_id", "")
        st.session_state.key_staging["google_client_secret"] = new_settings.get("google_client_secret", "")
        st.success("✅ Settings saved!")

    # ── Status panel ──────────
    st.divider()
    st.markdown("### 🟢 Key Status")
    status_cols = st.columns(len(AI_PROVIDERS))
    for i, (prov, info) in enumerate(AI_PROVIDERS.items()):
        key = cfg(info["key_name"])
        if info["local"]:
            status = f"🟢 {key or 'localhost:11434'}"
        else:
            status = "🟢 Set" if key else "🔴 Missing"
        status_cols[i].metric(prov, status)

    # ── User Management (admin only) ──────────────────────────────────
    st.divider()
    render_user_management()

# ═══════════════════════════════════════════════════════════════════
# TAB 4 — IDENTCHECK
# ═══════════════════════════════════════════════════════════════════

if active_tab == "🪪 Identcheck":
    st.subheader("🪪 Identcheck Vorlage")
    st.markdown(
        "Upload an **ID document, passport scan, or CV** and the AI extracts "
        "all identity fields — then fills your **Identcheck Word template** automatically."
    )

    IDENT_TPL_DIR = Path(__file__).parent / "ident_templates"
    IDENT_TPL_DIR.mkdir(exist_ok=True)

    ic_col_left, ic_col_right = st.columns([1, 2])

    with ic_col_left:
        st.markdown('<div class="bento-card">', unsafe_allow_html=True)
        st.markdown('<div class="bento-title">⚙️ AI Configuration</div>', unsafe_allow_html=True)
        ic_provider = st.selectbox(
            "Provider", list(AI_PROVIDERS.keys()), label_visibility="collapsed",
            key="ic_provider",
            index=list(AI_PROVIDERS.keys()).index(cfg("provider", "OpenAI"))
                  if cfg("provider", "OpenAI") in AI_PROVIDERS else 0,
        )
        ic_model = st.selectbox(
            "Model", AI_PROVIDERS[ic_provider]["models"],
            key="ic_model", index=0, label_visibility="collapsed",
        )

        st.divider()
        st.markdown("**📝 Identcheck Template**")
        ic_tpl_src = st.radio(
            "Tpl source", ["Upload now", "Saved Identcheck templates"],
            key="ic_tpl_src", label_visibility="collapsed",
        )
        ic_chosen_tpl = None
        if ic_tpl_src == "Saved Identcheck templates":
            saved_ident = list(IDENT_TPL_DIR.glob("*.docx"))
            if saved_ident:
                ic_sel = st.selectbox("Template", [f.name for f in saved_ident], key="ic_sel")
                ic_chosen_tpl = IDENT_TPL_DIR / ic_sel
            else:
                st.info("No Identcheck templates saved yet. Upload one below.")

        st.divider()
        st.markdown("**💾 Save Identcheck Template**")
        ic_tpl_up = st.file_uploader("Upload Identcheck DOCX template", type=["docx"], key="ic_tpl_up")
        ic_tpl_name = st.text_input("Template name", placeholder="identcheck_vorlage.docx", key="ic_tpl_name")
        if st.button("💾 Save", key="ic_save_tpl"):
            if ic_tpl_up is None:
                st.warning("Upload a DOCX file first.")
            else:
                fname = ic_tpl_name.strip() or "identcheck_vorlage.docx"
                if not fname.endswith(".docx"): fname += ".docx"
                (IDENT_TPL_DIR / fname).write_bytes(ic_tpl_up.getbuffer())
                st.success(f"✅ Saved as **{fname}**")
                st.rerun()

    with ic_col_right:
        st.markdown("**📂 Upload Document to Scan**")
        ic_doc = st.file_uploader(
            "ID scan, passport, or CV (PDF / DOCX)",
            type=["pdf", "docx"], key="ic_doc", label_visibility="collapsed",
        )
        if ic_tpl_src == "Upload now":
            st.markdown("**📝 Upload Identcheck Template**")
            ic_tpl_now = st.file_uploader(
                "Identcheck Word template (DOCX)", type=["docx"],
                key="ic_tpl_now", label_visibility="collapsed",
            )
        else:
            ic_tpl_now = None

        st.divider()
        ic_run = st.button(
            "🔍 Extract & Fill Identcheck", type="primary",
            use_container_width=True, disabled=ic_doc is None, key="ic_run",
        )

        if ic_run:
            ic_api_key = cfg(AI_PROVIDERS[ic_provider]["key_name"])
            is_local   = AI_PROVIDERS[ic_provider]["local"]
            if not ic_api_key and not is_local:
                st.error(f"❌ No {ic_provider} API key. Add it in **⚙️ Settings**.")
            elif ic_tpl_src == "Upload now" and ic_tpl_now is None:
                st.warning("⚠️ Please upload an Identcheck template or choose a saved one.")
            elif ic_tpl_src == "Saved Identcheck templates" and ic_chosen_tpl is None:
                st.warning("⚠️ No saved Identcheck template selected.")
            else:
                with st.spinner(f"Extracting identity data via {ic_provider} …"):
                    try:
                        # Write uploaded doc to temp
                        suffix = Path(ic_doc.name).suffix
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                            tmp.write(ic_doc.getbuffer())
                            ic_doc_path = tmp.name

                        # Write template
                        if ic_tpl_now:
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                                tmp.write(ic_tpl_now.getbuffer())
                                ic_tpl_path = tmp.name
                        else:
                            ic_tpl_path = str(ic_chosen_tpl)

                        # Extract identity data
                        ident_data = get_identity_data(
                            ic_doc_path, provider=ic_provider,
                            model=ic_model,
                            api_key=ic_api_key or ("http://localhost:11434" if is_local else ""),
                        )

                        st.success("✅ Identity data extracted!")

                        # Use Bento Layout for Identity Review
                        st.markdown('<div class="bento-grid">', unsafe_allow_html=True)
                        
                        # Hero Card (Span 8)
                        st.markdown('<div class="bento-card bento-hero">', unsafe_allow_html=True)
                        st.markdown('<div class="bento-title">📋 Extracted Identity Fields</div>', unsafe_allow_html=True)
                        
                        col_f1, col_f2 = st.columns(2)
                        with col_f1:
                            ident_data["full_name"]       = st.text_input("Full Name",        value=ident_data.get("full_name","") or "")
                            ident_data["birth_date"]      = st.text_input("Birth Date",       value=ident_data.get("birth_date","") or "")
                            ident_data["birth_place"]     = st.text_input("Place of Birth",   value=ident_data.get("birth_place","") or "")
                            ident_data["nationality"]     = st.text_input("Nationality",      value=ident_data.get("nationality","") or "")
                        with col_f2:
                            ident_data["document_type"]   = st.text_input("Document Type",    value=ident_data.get("document_type","") or "")
                            ident_data["document_number"] = st.text_input("Document Number",  value=ident_data.get("document_number","") or "")
                            ident_data["document_expiry_date"]      = st.text_input("Expiry Date",           value=ident_data.get("document_expiry_date","") or "")
                            ident_data["residence_permit_expiry"]   = st.text_input("Permit Expiry",         value=ident_data.get("residence_permit_expiry","") or "")
                        
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        # Action Card (Span 4)
                        st.markdown('<div class="bento-card bento-side">', unsafe_allow_html=True)
                        st.markdown('<div class="bento-title">💿 Finalize</div>', unsafe_allow_html=True)
                        
                        # Populate and offer download
                        ic_out_name = f"Identcheck_{Path(ic_doc.name).stem}.docx"
                        ic_out_path = os.path.join(tempfile.gettempdir(), ic_out_name)
                        populate_template(ic_tpl_path, ic_out_path, ident_data)

                        with open(ic_out_path, "rb") as f:
                            st.download_button(
                                label="⬇️ Download Word",
                                data=f,
                                file_name=ic_out_name,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True,
                            )
                        
                        st.divider()
                        with st.expander("Raw Data", expanded=False):
                            st.json(ident_data)
                        
                        st.markdown('</div>', unsafe_allow_html=True)
                        st.markdown('</div>', unsafe_allow_html=True)
                    except Exception as e:
                        err_msg = str(e)
                        if "Connection error" in err_msg and "11434" in err_msg:
                            st.error(f"❌ Connection error: {ic_provider} at localhost:11434 is not reachable. Is Ollama running?")
                        else:
                            st.error(f"❌ Error: {e}")

# ═══════════════════════════════════════════════════════════════════
# TAB 5 — LEBENSLAUF GENERATOR
# ═══════════════════════════════════════════════════════════════════
LEBEN_JOB_PROFILES = [
    "Schweißer", "Schlosser", "Mechaniker", "Elektriker", "Lackierer",
    "Klempner", "Maurer", "Zimmermann", "Tischler", "Other",
]

if active_tab == "📜 Lebenslauf":
    st.subheader("📋 Lebenslauf Generator — Vorlage-Stil")
    st.markdown(
        "Lade Lebenslauf, Ausweis und weitere Dokumente hoch. "
        "Die KI extrahiert alle Informationen und erstellt ein **Word-Dokument nach Vorlage** "
        "(KANDIDATENPROFIL-Format) auf Deutsch."
    )

    ll_col_left, ll_col_right = st.columns([1, 2])

    with ll_col_left:
        st.markdown("**🤖 AI Provider**")
        ll_provider = st.selectbox(
            "Provider", list(AI_PROVIDERS.keys()), label_visibility="collapsed",
            key="ll_provider",
            index=list(AI_PROVIDERS.keys()).index(cfg("provider", "OpenAI"))
                  if cfg("provider", "OpenAI") in AI_PROVIDERS else 0,
        )
        ll_model = st.selectbox(
            "Model", AI_PROVIDERS[ll_provider]["models"],
            key="ll_model", index=0, label_visibility="collapsed",
        )

        st.divider()
        st.markdown("**💼 Berufsfeld / Job-Profil**")
        ll_job_role = st.selectbox(
            "Berufsfeld", LEBEN_JOB_PROFILES,
            key="ll_job_role", label_visibility="collapsed",
        )
        if ll_job_role == "Other":
            ll_job_role = st.text_input(
                "Berufsbezeichnung eingeben", key="ll_job_custom",
                placeholder="z.B. Kranführer, Rohrschlosser …"
            ) or "Other"

        st.divider()
        st.info(
            "💡 **Tipp:** Für beste Ergebnisse nutze **GPT-4o** oder **Gemini 2.0 Flash** "
            "— beide unterstützen Bild-OCR für Ausweisscans."
        )

    with ll_col_right:
        st.markdown("**📂 Lebenslauf (PDF, DOCX, JPG, PNG)** — Pflichtfeld")
        ll_cv_files = st.file_uploader(
            "Lebenslauf hochladen",
            type=["pdf", "docx", "jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="ll_cv_files", label_visibility="collapsed",
        )

        st.markdown("**🪪 Ausweis / Reisepass (optional, PDF, JPG, PNG)**")
        ll_id_files = st.file_uploader(
            "Ausweis hochladen",
            type=["pdf", "jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="ll_id_files", label_visibility="collapsed",
        )

        st.markdown("**📎 Weitere Dokumente (optional)** — z.B. Zertifikate, Zeugnisse")
        ll_extra_files = st.file_uploader(
            "Weitere Dokumente",
            type=["pdf", "docx", "jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="ll_extra_files", label_visibility="collapsed",
        )

        st.divider()
        st.markdown("**📝 Word-Vorlage (Kandidatenprofil)**")
        ll_tpl_source = st.radio("Vorlage-Quelle", ["Built-in Styling", "Upload now", "Saved templates"], horizontal=True, key="ll_tpl_source")
        ll_tpl_path = None
        ll_tpl_file = None
        
        if ll_tpl_source == "Saved templates":
            saved_tpls = list(TEMPLATES_DIR.glob("*.docx"))
            if saved_tpls:
                sel = st.selectbox("Vorlage wählen", [f.name for f in saved_tpls], key="ll_tpl_sel")
                ll_tpl_path = str(TEMPLATES_DIR / sel)
            else:
                st.info("No saved templates yet.")
        elif ll_tpl_source == "Upload now":
            ll_tpl_file = st.file_uploader("Vorlage (.docx) hochladen", type=["docx"], key="ll_tpl_file")

        # ── 🛠️ TEMPLATE DIAGNOSTICS (Moved out of expander for visibility) ──
        st.markdown('<div class="bento-card">', unsafe_allow_html=True)
        st.markdown('<div class="bento-title">🛠️ Vorlagen-Check</div>', unsafe_allow_html=True)
        st.caption("Verifiziere deine Word-Vorlage auf Korrektheit, bevor du generierst.")
        
        diag_path = None
        if ll_tpl_source == "Saved templates" and ll_tpl_path:
            diag_path = ll_tpl_path
        elif ll_tpl_source == "Upload now" and ll_tpl_file:
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                tmp.write(ll_tpl_file.getvalue())
                diag_path = tmp.name

        if st.button("🔍 Check Template Format", key="ll_btn_diag_visible", use_container_width=True, disabled=not diag_path):
            with st.spinner("Scanne nach Jinja-Tags..."):
                res = diagnose_template(diag_path)
                if res["error"]:
                    st.error(f"❌ Syntaxfehler gefunden!\n\n**Genaue Ursache:**\n```\n{res['error']}\n```")
                    st.info("💡 **TIPP:** Öffne die Word-Vorlage. Prüfe ob alle `{% for %}` auch ein `{% endfor %}` haben.")
                elif res["count"] == 0:
                    st.warning("⚠️ **0 Tags gefunden!**")
                    st.caption("Das System denkt, deine Vorlage ist ein statisches Word-Dokument. Wahrscheinlich wurden die `{ {` Klammern von Word zerrissen.")
                else:
                    st.success(f"✅ **{res['count']} Variablen** erfolgreich erkannt!")
                    st.code(", ".join(res["tags"]), language="text")
        st.markdown('</div>', unsafe_allow_html=True)

        st.divider()
        ll_run = st.button(
            "⚡ Lebenslauf generieren", type="primary",
            use_container_width=True,
            disabled=(not ll_cv_files),
            key="ll_run",
        )

        if ll_run:
            ll_api_key = cfg(AI_PROVIDERS[ll_provider]["key_name"])
            is_local   = AI_PROVIDERS[ll_provider]["local"]
            
            if ll_tpl_source == "Upload now" and ll_tpl_file is None:
                st.warning("⚠️ Bitte lade eine Word-Vorlage hoch.")
            elif ll_tpl_source == "Saved templates" and ll_tpl_path is None:
                st.warning("⚠️ Keine Vorlage ausgewählt.")
            elif not ll_api_key and not is_local:
                st.error(f"❌ Kein {ll_provider} API-Key. Bitte im **⚙️ Einstellungen**-Tab eintragen.")
            else:
                _ll_prog = st.progress(0, text="📂 Dokumente werden eingelesen …")
                try:
                    import tempfile
                    from pathlib import Path as _Path

                    saved_paths: list[str] = []

                    # Save template if uploaded
                    current_tpl_path = ll_tpl_path
                    if ll_tpl_file:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                            tmp.write(ll_tpl_file.getbuffer())
                            current_tpl_path = tmp.name

                    # Save CV files
                    for uf in (ll_cv_files or []):
                        with tempfile.NamedTemporaryFile(
                            delete=False, suffix=_Path(uf.name).suffix
                        ) as tmp:
                            tmp.write(uf.getbuffer())
                            saved_paths.append(tmp.name)

                    # Save ID files (appended after CV)
                    for uf in (ll_id_files or []):
                        with tempfile.NamedTemporaryFile(
                            delete=False, suffix=_Path(uf.name).suffix
                        ) as tmp:
                            tmp.write(uf.getbuffer())
                            saved_paths.append(tmp.name)

                    # Save extra files
                    for uf in (ll_extra_files or []):
                        with tempfile.NamedTemporaryFile(
                            delete=False, suffix=_Path(uf.name).suffix
                        ) as tmp:
                            tmp.write(uf.getbuffer())
                            saved_paths.append(tmp.name)

                    # Step 2 — AI extraction
                    resolved_api = ll_api_key or ("http://localhost:11434" if is_local else "")
                    ll_data = get_lebenslauf_data(
                        file_paths=saved_paths,
                        job_role=ll_job_role,
                        provider=ll_provider,
                        model=ll_model,
                        api_key=resolved_api,
                    )
                    
                    # Fix NameError by defining it here
                    ll_cand_name = candidate_name_from_data(ll_data)
                    _add_history(ll_cand_name, ll_provider, ll_model, "Lebenslauf")

                    # Store to Buffer for Review in Tab 5
                    st.session_state.ll_extract_buffer = {
                        "data": ll_data,
                        "tpl_path": current_tpl_path,
                        "tpl_name": ll_tpl_file.name if ll_tpl_file else (sel if ll_tpl_source == "Saved templates" else "Built-in Styling"),
                        "job_role": ll_job_role,
                        "provider": ll_provider,
                        "model": ll_model,
                        "cand_name": ll_cand_name,
                        "status": "ready"
                    }
                    st.toast(f"✅ Extraction Successful for {ll_cand_name}!")

                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    st.error(f"❌ Error: {e}")
                finally:
                    _ll_prog.empty()

        # ── 🔍 LEBENSLAUF REVIEW BRIDGE ──────────────────────────────
        if "ll_extract_buffer" in st.session_state and st.session_state.ll_extract_buffer:
            ll_buf = st.session_state.ll_extract_buffer
            ll_ext = ll_buf["data"]
            
            st.divider()
            st.markdown("### 🔍 Profile Review Station")
            st.caption("Verify and optimize data before generating the custom Word document.")

            ll_col_b1, ll_col_b2 = st.columns([2, 1])

            with ll_col_b1:
                st.markdown('<div class="bento-card bento-hero">', unsafe_allow_html=True)
                st.markdown('<div class="bento-title">✨ Hero Details</div>', unsafe_allow_html=True)
                
                ll_c1, ll_c2 = st.columns(2)
                with ll_c1:
                    ll_def_name = ll_ext.get("name", "") or f"{ll_ext.get('vorname', '')} {ll_ext.get('nachname', '')}".strip()
                    ll_rev_name = st.text_input("Name", value=ll_def_name, key="ll_rev_name_ext")
                    ll_rev_dob = st.text_input("Birth Date", value=ll_ext.get("geburtsdatum", ll_ext.get("birth_date", "")), key="ll_rev_dob_ext")
                with ll_c2:
                    ll_rev_role = st.text_input("Job Profile", value=ll_ext.get("job_role", ll_buf["job_role"]), key="ll_rev_role_ext")
                    ll_rev_nat = st.text_input("Nationality", value=ll_ext.get("nationality", ll_ext.get("staatsangehoerigkeit", "")), key="ll_rev_nat_ext")
                
                ll_rev_summary = st.text_area("Synthesis", value=ll_ext.get("profile_summary", ll_ext.get("zusammenfassung", "")), height=150, key="ll_rev_summary_ext")
                
                # Sync edits to buffer immediately
                ll_ext["name"] = ll_rev_name
                if " " in ll_rev_name:
                    ll_ext["vorname"], ll_ext["nachname"] = ll_rev_name.split(" ", 1)
                else:
                    ll_ext["nachname"] = ll_rev_name
                
                ll_ext["job_role"] = ll_rev_role
                ll_ext["nationality"] = ll_rev_nat
                ll_ext["profile_summary"] = ll_rev_summary
                ll_ext["birth_date"] = ll_rev_dob
                # Mirror German
                ll_ext["zusammenfassung"] = ll_rev_summary
                ll_ext["geburtsdatum"] = ll_rev_dob
                ll_ext["staatsangehoerigkeit"] = ll_rev_nat
                
                st.markdown('</div>', unsafe_allow_html=True)

                # ── 📊 DATA INSPECTOR ───────────────────────────────────
                st.markdown('<div class="bento-card">', unsafe_allow_html=True)
                st.markdown('<div class="bento-title">📊 Data Inspector</div>', unsafe_allow_html=True)
                st.caption("Check exactly what was extracted. Empty lists = missing data in the output document!")

                # Quick summary badges
                bildung_count = len(ll_ext.get("bildung", []))
                wb_count = len(ll_ext.get("weiterbildung", []))
                jobs_count = len(ll_ext.get("berufserfahrung", ll_ext.get("employment_history", [])))
                lang_count = len(ll_ext.get("sprachen", ll_ext.get("language_skills", [])))

                badge_cols = st.columns(4)
                badge_cols[0].metric("Berufserfahrung", jobs_count, delta="entries" if jobs_count else None, delta_color="normal")
                badge_cols[1].metric("Bildung", bildung_count, delta="✅" if bildung_count else "⚠️ EMPTY", delta_color="normal" if bildung_count else "inverse")
                badge_cols[2].metric("Weiterbildung", wb_count, delta="✅" if wb_count else "⚠️ EMPTY", delta_color="normal" if wb_count else "inverse")
                badge_cols[3].metric("Sprachen", lang_count, delta="✅" if lang_count else "⚠️ EMPTY", delta_color="normal" if lang_count else "inverse")

                with st.expander("🔍 Full Extracted Data (JSON)", expanded=(bildung_count == 0)):
                    # Show a trimmed view with key education/language fields first
                    key_fields = {
                        "bildung": ll_ext.get("bildung", []),
                        "weiterbildung": ll_ext.get("weiterbildung", []),
                        "berufserfahrung (first entry)": ll_ext.get("berufserfahrung", ll_ext.get("employment_history", []))[:1],
                        "sprachen": ll_ext.get("sprachen", ll_ext.get("language_skills", [])),
                        "faehigkeiten": ll_ext.get("faehigkeiten", []),
                    }
                    st.json(key_fields)
                    st.caption("---")
                    st.caption("Full raw data:")
                    st.json(ll_ext)
                
                # ── ✏️ MANUAL JSON EDITOR ──────────────────────────────
                st.markdown("---")
                st.markdown("**✏️ Fix Missing Data Manually**")
                st.caption("If 'Bildung' or 'Weiterbildung' is empty above, paste the correct data here and click Apply. Use exact JSON format.")
                
                edit_tabs = st.tabs(["Bildung (Schule/Uni)", "Weiterbildung (Kurse)"])
                
                with edit_tabs[0]:
                    default_bildung = json.dumps(ll_ext.get("bildung", []), indent=2, ensure_ascii=False)
                    new_bildung_str = st.text_area(
                        "Bildungsdaten (JSON)", value=default_bildung, height=150,
                        key="ll_manual_bildung",
                        help='Format: [{"jahre": "2000-2004", "einrichtung": "Schule", "abschluss": "Abschluss"}]'
                    )
                    if st.button("✅ Apply Bildung", key="ll_apply_bildung"):
                        try:
                            new_bildung = json.loads(new_bildung_str)
                            if isinstance(new_bildung, list):
                                ll_ext["bildung"] = new_bildung
                                ll_buf["data"]["bildung"] = new_bildung
                                st.success(f"✅ Bildung updated with {len(new_bildung)} entries!")
                            else:
                                st.error("Must be a JSON list [ ... ]")
                        except json.JSONDecodeError as e:
                            st.error(f"Invalid JSON: {e}")
                
                with edit_tabs[1]:
                    default_wb = json.dumps(ll_ext.get("weiterbildung", []), indent=2, ensure_ascii=False)
                    new_wb_str = st.text_area(
                        "Weiterbildungsdaten (JSON)", value=default_wb, height=150,
                        key="ll_manual_wb",
                        help='Format: [{"jahre": "2015", "anbieter": "TÜV", "kurs": "ISO 9606-1"}]'
                    )
                    if st.button("✅ Apply Weiterbildung", key="ll_apply_wb"):
                        try:
                            new_wb = json.loads(new_wb_str)
                            if isinstance(new_wb, list):
                                ll_ext["weiterbildung"] = new_wb
                                ll_buf["data"]["weiterbildung"] = new_wb
                                st.success(f"✅ Weiterbildung updated with {len(new_wb)} entries!")
                            else:
                                st.error("Must be a JSON list [ ... ]")
                        except json.JSONDecodeError as e:
                            st.error(f"Invalid JSON: {e}")

                st.markdown('</div>', unsafe_allow_html=True)

            with ll_col_b2:
                st.markdown('<div class="bento-card">', unsafe_allow_html=True)
                st.markdown('<div class="bento-title">🚀 Output Factory</div>', unsafe_allow_html=True)
                
                st.info(f"AI: **{ll_buf['provider']}**")
                st.success(f"📌 **Active Template:** `{ll_buf.get('tpl_name', 'Default')}`")

                if ll_buf["status"] == "ready":
                    if st.button("✨ Approve & Generate Document", type="primary", use_container_width=True, key="ll_btn_approve"):
                        try:
                            # Build output path
                            ll_out_name = f"Lebenslauf_{ll_ext.get('nachname', 'Kandidat')}_{ll_buf['job_role']}.docx"
                            ll_out_path = os.path.join(tempfile.gettempdir(), ll_out_name)
                            
                            # Populating logic
                            if ll_buf["tpl_path"]:
                                populate_template(ll_buf["tpl_path"], ll_out_path, ll_ext)
                            else:
                                build_lebenslauf_docx(ll_ext, job_role=ll_buf["job_role"], output_path=ll_out_path)
                            
                            # Final candidate sync
                            save_candidate_lebenslauf(ll_buf["cand_name"], ll_ext, ll_out_path)
                            
                            ll_buf["final_path"] = ll_out_path
                            ll_buf["final_name"] = ll_out_name
                            ll_buf["status"] = "synced"
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to generate Word: {e}")
                
                if ll_buf["status"] == "synced":
                    st.success("✅ File Ready!")
                    with open(ll_buf["final_path"], "rb") as f:
                        st.download_button(
                            "⬇️ Download Lebenslauf",
                            data=f,
                            file_name=ll_buf["final_name"],
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                            key="ll_btn_dl"
                        )
                    if st.button("🔄 New Generation", key="ll_btn_reset"):
                        st.session_state.ll_extract_buffer = None
                        st.rerun()

                st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# TAB 6 — KANDIDATEN (Candidates)
# ═══════════════════════════════════════════════════════════════════
IDENT_TPL_DIR_K = Path(__file__).parent / "ident_templates"

if active_tab == "👥 Candidates":
    st.subheader("👥 Kandidaten — Verwaltung")
    st.markdown(
        "Alle verarbeiteten Kandidaten werden hier gespeichert. "
        "Du kannst CVs **erneut verarbeiten**, **ID-Dokumente hinzufügen** "
        "und **Identcheck-Vorlagen automatisch ausfüllen lassen**."
    )

    candidates = list_candidates()

    if not candidates:
        st.info(
            "📭 Noch keine Kandidaten vorhanden. "
            "Verarbeite einen CV im **🚀 Process CV** oder **📋 Lebenslauf** Tab — "
            "der Kandidat wird automatisch hier gespeichert."
        )
    else:
        k_col_left, k_col_right = st.columns([1, 3])

        with k_col_left:
            st.markdown("**📋 Kandidatenliste**")

            # Build display names with status icons
            display_names = []
            folder_to_idx = {}
            for i, c in enumerate(candidates):
                icons = ""
                if c["has_cv"]:        icons += "📄"
                if c["has_lebenslauf"]:  icons += "📋"
                if c["has_id"]:         icons += "🪪"
                if c["has_identcheck"]: icons += "✅"
                display_names.append(f"{icons} {c['name']}  ({c['last_modified']})")
                folder_to_idx[c["folder"]] = i

            # Logic to handle sidebar-initiated selection
            default_index = 0
            if "k_select_folder" in st.session_state:
                requested_folder = st.session_state.k_select_folder
                if requested_folder in folder_to_idx:
                    default_index = folder_to_idx[requested_folder]

            selected_idx = st.selectbox(
                "Kandidat wählen", range(len(display_names)),
                format_func=lambda i: display_names[i],
                index=default_index,
                key="k_select", label_visibility="collapsed",
            )
            sel_candidate = candidates[selected_idx]
            sel_folder = sel_candidate["folder"]
            # Sync back just in case
            st.session_state.k_select_folder = sel_folder

            st.caption(f"📁 {sel_candidate['file_count']} Dateien")

            st.divider()

            # Delete candidate
            if st.button("🗑️ Kandidat löschen", use_container_width=True, key="k_del"):
                delete_candidate(sel_folder)
                st.success("✅ Gelöscht!")
                st.rerun()

        with k_col_right:
            cand_data = get_candidate(sel_folder)
            st.markdown(f"### 📂 {cand_data.get('name', sel_folder)}")

            # ── Documents overview ───────────────────────────────────
            doc_tabs = st.tabs(["📄 CV Daten", "📋 Lebenslauf", "🪪 ID & Identcheck", "🔄 Erneut verarbeiten"])

            # ─── Sub-tab: CV Data ────────────────────────────────────
            with doc_tabs[0]:
                if cand_data.get("extracted_data"):
                    st.markdown("**Extrahierte CV-Daten:**")
                    with st.expander("📊 JSON anzeigen", expanded=False):
                        st.json(cand_data["extracted_data"])

                    # Download populated CV
                    pop_files = cand_data["files"].get("populated_cv", [])
                    if pop_files:
                        with open(pop_files[0], "rb") as f:
                            st.download_button(
                                "⬇️ Populated CV herunterladen",
                                data=f, file_name="Populated_CV.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True,
                            )
                    # Download JSON
                    st.download_button(
                        "⬇️ JSON exportieren",
                        data=json.dumps(cand_data["extracted_data"], indent=2, ensure_ascii=False),
                        file_name=f"{sel_folder}_data.json",
                        mime="application/json", use_container_width=True,
                    )
                else:
                    st.info("Keine CV-Daten vorhanden. Verarbeite den CV erneut im Tab '🔄'.")

            # ─── Sub-tab: Lebenslauf ─────────────────────────────────
            with doc_tabs[1]:
                if cand_data.get("lebenslauf_data"):
                    st.markdown("**Lebenslauf-Daten:**")
                    with st.expander("📊 JSON anzeigen", expanded=False):
                        st.json(cand_data["lebenslauf_data"])

                    ll_files = cand_data["files"].get("lebenslauf", [])
                    if ll_files:
                        with open(ll_files[0], "rb") as f:
                            st.download_button(
                                "⬇️ Lebenslauf herunterladen",
                                data=f, file_name="Lebenslauf.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True,
                            )
                else:
                    st.info("Kein Lebenslauf vorhanden. Erstelle einen im **📋 Lebenslauf** Tab.")

            # ─── Sub-tab: ID & Identcheck ────────────────────────────
            with doc_tabs[2]:
                st.markdown("**🪪 ID-Dokument hochladen**")
                k_id_file = st.file_uploader(
                    "ID-Scan (JPG, PNG, PDF)", type=["jpg", "jpeg", "png", "pdf"],
                    key=f"k_id_upload_{sel_folder}",
                    label_visibility="collapsed",
                )
                if k_id_file:
                    if st.button("💾 ID-Dokument speichern", key="k_save_id"):
                        saved_path = add_id_document(sel_folder, k_id_file.getbuffer(), k_id_file.name)
                        st.success(f"✅ Gespeichert: {Path(saved_path).name}")
                        st.rerun()

                # Show existing ID scans
                id_paths = get_id_paths(sel_folder)
                if id_paths:
                    st.markdown("**Gespeicherte ID-Scans:**")
                    for ip in id_paths:
                        ip_name = Path(ip).name
                        ip_ext = Path(ip).suffix.lower()
                        if ip_ext in (".jpg", ".jpeg", ".png"):
                            st.image(ip, caption=ip_name, width=300)
                        else:
                            st.markdown(f"📄 `{ip_name}`")

                st.divider()
                st.markdown("**🪪 Identcheck ausfüllen**")
                st.caption(
                    "Wähle einen AI-Provider und ein Identcheck-Template. "
                    "Die KI extrahiert Name, Geburtsdatum, Geburtsort, Dokumentnummer und Ablaufdatum "
                    "aus dem ID-Scan und füllt das Template automatisch."
                )

                k_ic_col1, k_ic_col2 = st.columns(2)
                with k_ic_col1:
                    k_ic_provider = st.selectbox(
                        "AI Provider", list(AI_PROVIDERS.keys()),
                        key="k_ic_provider", label_visibility="collapsed",
                    )
                    k_ic_model = st.selectbox(
                        "Model", AI_PROVIDERS[k_ic_provider]["models"],
                        key="k_ic_model", index=0, label_visibility="collapsed",
                    )
                with k_ic_col2:
                    # Identcheck template selection
                    saved_ident_tpls = list(IDENT_TPL_DIR_K.glob("*.docx")) if IDENT_TPL_DIR_K.exists() else []
                    if saved_ident_tpls:
                        k_ic_tpl = st.selectbox(
                            "Identcheck Template", [f.name for f in saved_ident_tpls],
                            key="k_ic_tpl", label_visibility="collapsed",
                        )
                        k_ic_tpl_path = IDENT_TPL_DIR_K / k_ic_tpl
                    else:
                        st.warning("⚠️ Kein Identcheck-Template vorhanden. Lade eines hoch im **🪪 Identcheck** Tab.")
                        k_ic_tpl_path = None

                k_ic_run = st.button(
                    "🪪 Identcheck extrahieren & ausfüllen",
                    type="primary", use_container_width=True,
                    disabled=(not id_paths or k_ic_tpl_path is None),
                    key="k_ic_run",
                )

                if k_ic_run and id_paths and k_ic_tpl_path:
                    k_ic_api_key = cfg(AI_PROVIDERS[k_ic_provider]["key_name"])
                    is_local = AI_PROVIDERS[k_ic_provider]["local"]
                    if not k_ic_api_key and not is_local:
                        st.error(f"❌ Kein {k_ic_provider} API-Key. Bitte im **⚙️ Settings** Tab eintragen.")
                    else:
                        with st.spinner(f"🪪 Identcheck: Extrahiere Daten via {k_ic_provider} …"):
                            try:
                                # Use first ID scan
                                ident_data = get_identity_data(
                                    id_paths[0],
                                    provider=k_ic_provider,
                                    model=k_ic_model,
                                    api_key=k_ic_api_key or ("http://localhost:11434" if is_local else ""),
                                )

                                # Fill identcheck template
                                ic_out_path = os.path.join(
                                    str(cand_data["dir_path"]), "Identcheck_Filled.docx"
                                )
                                populate_template(str(k_ic_tpl_path), ic_out_path, ident_data)

                                # Save identcheck data
                                save_identcheck(sel_folder, ident_data, ic_out_path)

                                st.success("✅ Identcheck erfolgreich ausgefüllt!")

                                with st.expander("📊 Identcheck-Daten", expanded=False):
                                    st.json(ident_data)

                                with open(ic_out_path, "rb") as f:
                                    st.download_button(
                                        "⬇️ Identcheck herunterladen",
                                        data=f, file_name="Identcheck_Filled.docx",
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                        use_container_width=True,
                                    )
                            except Exception as e:
                                st.error(f"❌ Fehler bei Identcheck: {e}")

                # Show existing identcheck
                if cand_data.get("identcheck_data"):
                    st.divider()
                    st.markdown("**✅ Vorhandener Identcheck:**")
                    with st.expander("📊 Identcheck-Daten anzeigen", expanded=False):
                        st.json(cand_data["identcheck_data"])
                    ic_files = cand_data["files"].get("identcheck_doc", [])
                    if ic_files:
                        with open(ic_files[0], "rb") as f:
                            st.download_button(
                                "⬇️ Identcheck-Dokument herunterladen",
                                data=f, file_name="Identcheck_Filled.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True, key="k_dl_ic",
                            )

            # ─── Sub-tab: Re-process ─────────────────────────────────
            with doc_tabs[3]:
                st.markdown("**🔄 CV erneut verarbeiten**")
                st.caption(
                    "Verarbeitet den gespeicherten Original-CV erneut mit der KI, "
                    "ohne dass du die Datei erneut hochladen musst."
                )

                cv_path = get_cv_path(sel_folder)
                if cv_path:
                    st.success(f"📄 Original-CV vorhanden: `{Path(cv_path).name}`")

                    k_rp_col1, k_rp_col2 = st.columns(2)
                    with k_rp_col1:
                        k_rp_provider = st.selectbox(
                            "AI Provider", list(AI_PROVIDERS.keys()),
                            key="k_rp_provider", label_visibility="collapsed",
                        )
                        k_rp_model = st.selectbox(
                            "Model", AI_PROVIDERS[k_rp_provider]["models"],
                            key="k_rp_model", index=0, label_visibility="collapsed",
                        )
                    with k_rp_col2:
                        k_rp_job = st.selectbox(
                            "Job Profil", JOB_PROFILES, key="k_rp_job",
                            label_visibility="collapsed",
                        )
                        # Template selection
                        k_rp_saved_tpls = list(TEMPLATES_DIR.glob("*.docx"))
                        if k_rp_saved_tpls:
                            k_rp_tpl_sel = st.selectbox(
                                "Template", [f.name for f in k_rp_saved_tpls],
                                key="k_rp_tpl", label_visibility="collapsed",
                            )
                            k_rp_tpl_path = TEMPLATES_DIR / k_rp_tpl_sel
                        else:
                            k_rp_tpl_path = None
                            st.warning("⚠️ Kein Template vorhanden.")

                    k_rp_run = st.button(
                        "🔄 Erneut verarbeiten", type="primary",
                        use_container_width=True, key="k_rp_run",
                        disabled=(k_rp_tpl_path is None),
                    )

                    if k_rp_run and k_rp_tpl_path:
                        k_rp_api_key = cfg(AI_PROVIDERS[k_rp_provider]["key_name"])
                        is_local = AI_PROVIDERS[k_rp_provider]["local"]
                        if not k_rp_api_key and not is_local:
                            st.error(f"❌ Kein {k_rp_provider} API-Key.")
                        else:
                            _rp_prog = st.progress(0, text="🤖 Verarbeite CV erneut …")
                            try:
                                _rp_prog.progress(30, text=f"🤖 Sende an {k_rp_provider} …")
                                rp_extracted = get_cv_data(
                                    cv_path, provider=k_rp_provider,
                                    model=k_rp_model,
                                    api_key=k_rp_api_key or ("http://localhost:11434" if is_local else ""),
                                )
                                rp_extracted["job_role"] = k_rp_job

                                _rp_prog.progress(60, text="📝 Vorlage wird ausgefüllt …")
                                rp_out_path = os.path.join(str(cand_data["dir_path"]), "Populated_CV.docx")
                                populate_template(str(k_rp_tpl_path), rp_out_path, rp_extracted)

                                # Update saved data
                                rp_cand_name = candidate_name_from_data(rp_extracted)
                                with open(cv_path, "rb") as f:
                                    cv_bytes = f.read()
                                save_candidate_cv(
                                    rp_cand_name, cv_bytes,
                                    Path(cv_path).name, rp_extracted, rp_out_path,
                                )

                                _rp_prog.progress(100, text="✅ Fertig!")
                                st.success("✅ CV erneut verarbeitet!")

                                with st.expander("📊 Neue Daten", expanded=True):
                                    st.json(rp_extracted)

                                with open(rp_out_path, "rb") as f:
                                    st.download_button(
                                        "⬇️ Neues Dokument herunterladen",
                                        data=f, file_name="Populated_CV.docx",
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                        use_container_width=True,
                                    )

                            except Exception as e:
                                st.error(f"❌ Fehler: {e}")
                            finally:
                                _rp_prog.empty()
                else:
                    st.warning("⚠️ Kein Original-CV vorhanden. Lade einen neuen CV im **🚀 Process CV** Tab hoch.")


# Sidebar Assistant covers chat now.
st.markdown("---")
st.caption("Built with ❤️ using OpenAI · Gemini · Anthropic · Mistral · DeepSeek · Grok · Kimi · Qwen · Ollama and Streamlit")
