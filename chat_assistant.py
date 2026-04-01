"""
chat_assistant.py
=================
Multi-provider chat engine for the CV Extractor app.
Supports conversational AI interaction with CV data — restructure,
edit, translate, and prepare CV content before processing into templates.
"""

import json
import os
import re
from pathlib import Path


# ── Provider call wrappers for CHAT mode (multi-turn) ────────────────────────

def chat_openai(messages: list[dict], model: str, api_key: str,
                base_url: str = "https://api.openai.com/v1") -> str:
    """Send chat messages via OpenAI-compatible API. Returns assistant text."""
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=4096,
    )
    return resp.choices[0].message.content or ""


def chat_gemini(messages: list[dict], model: str, api_key: str) -> str:
    """Send chat messages via Gemini API."""
    from google import genai
    from google.genai import types

    # Convert OpenAI-style messages to Gemini contents
    contents = []
    for msg in messages:
        role = "user" if msg["role"] in ("user", "system") else "model"
        contents.append(types.Content(
            role=role,
            parts=[types.Part.from_text(text=msg["content"])],
        ))

    client = genai.Client(api_key=api_key)
    # Ensure Gemini model names have the 'models/' prefix
    actual_model = model if model.startswith("models/") else f"models/{model}"
    resp = client.models.generate_content(model=actual_model, contents=contents)
    return resp.text or ""


def chat_anthropic(messages: list[dict], model: str, api_key: str) -> str:
    """Send chat messages via Anthropic API."""
    import anthropic, httpx

    # Use trust_env=False to completely bypass system HTTP_PROXY / HTTPS_PROXY env vars
    # which can cause spurious 'APIConnectionError' when a local proxy (e.g. port 8080) is set
    transport = httpx.HTTPTransport(proxy=None)
    http_client = httpx.Client(transport=transport, trust_env=False, timeout=httpx.Timeout(120.0))
    client = anthropic.Anthropic(api_key=api_key, http_client=http_client)

    # Separate system message
    system_msg = ""
    chat_msgs = []
    for msg in messages:
        if msg["role"] == "system":
            system_msg += msg["content"] + "\n"
        else:
            chat_msgs.append({"role": msg["role"], "content": msg["content"]})

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_msg.strip() or "You are a helpful assistant for CV processing.",
            messages=chat_msgs,
        )
        return resp.content[0].text or ""
    except anthropic.APIStatusError as e:
        # Give a clear, actionable error for billing/credit issues
        err_body = str(e).lower()
        if "credit" in err_body or "billing" in err_body or "upgrade" in err_body or "purchase" in err_body:
            raise RuntimeError(
                "❌ Anthropic account has no credits. "
                "Please add credits at https://console.anthropic.com/settings/billing — "
                "or switch to a different AI provider (OpenAI, Gemini, etc.)."
            ) from e
        raise


def chat_mistral(messages: list[dict], model: str, api_key: str) -> str:
    """Send chat messages via Mistral API."""
    from mistralai import Mistral
    client = Mistral(api_key=api_key)
    resp = client.chat.complete(model=model, messages=messages)
    return resp.choices[0].message.content or ""


# ── Unified chat dispatch ────────────────────────────────────────────────────

CHAT_DISPATCH = {
    "OpenAI":      lambda msgs, model, key: chat_openai(msgs, model, key, "https://api.openai.com/v1"),
    "Gemini":      chat_gemini,
    "Anthropic":   chat_anthropic,
    "Mistral":     chat_mistral,
    "DeepSeek":    lambda msgs, model, key: chat_openai(msgs, model, key, "https://api.deepseek.com/v1"),
    "Grok (xAI)":  lambda msgs, model, key: chat_openai(msgs, model, key, "https://api.x.ai/v1"),
    "Kimi K2":     lambda msgs, model, key: chat_openai(msgs, model, key, "https://api.moonshot.cn/v1"),
    "Qwen":        lambda msgs, model, key: chat_openai(msgs, model, key, "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    "Perplexity":  lambda msgs, model, key: chat_openai(msgs, model, key, "https://api.perplexity.ai"),
    "Ollama":      lambda msgs, model, key: chat_openai(
        msgs, model, "ollama",
        (key.rstrip("/") if key.startswith("http") else "http://localhost:11434") + "/v1"
    ),
    "TogetherAI":  lambda msgs, model, key: chat_openai(msgs, model, key, "https://api.together.xyz/v1"),
    "Groq":        lambda msgs, model, key: chat_openai(msgs, model, key, "https://api.groq.com/openai/v1"),
    "OpenRouter":  lambda msgs, model, key: chat_openai(msgs, model, key, "https://openrouter.ai/api/v1"),
    "Xiaomi MiMo": lambda msgs, model, key: chat_openai(msgs, model, key, "https://api.xiaomimimo.com/v1"),
}


def send_chat_message(
    messages: list[dict],
    provider: str,
    model: str,
    api_key: str,
) -> str:
    """
    Send a list of chat messages to the specified provider.
    Returns the assistant's response text.
    """
    if provider not in CHAT_DISPATCH:
        raise ValueError(f"Unknown provider '{provider}'. Choose from: {list(CHAT_DISPATCH)}")

    return CHAT_DISPATCH[provider](messages, model, api_key)


# ── CV context system prompt ─────────────────────────────────────────────────

CV_SYSTEM_PROMPT = """Du bist ein professioneller HR-Assistent und CV-Spezialist für die Personalvermittlung.
Deine Aufgaben:
1. CV-Daten analysieren, umstrukturieren und verbessern
2. Fehlende Informationen aus Ausweis-/Reisepassscans ergänzen (Geburtsort, Geburtstag, Ablaufdatum)
3. Berufserfahrung, Fähigkeiten und Qualifikationen professionell formulieren
4. Antworten hauptsächlich auf Deutsch, außer der Benutzer spricht Englisch

Wenn der Benutzer eine Datei hochlädt (CV oder Ausweis), analysiere den Inhalt und biete Verbesserungen an.

---
Wenn der Benutzer dich bittet, einen **Identcheck** zu erstellen (z.B. "Fülle den Identcheck aus" oder "Erstelle Identcheck"),
extrahiere folgende Felder aus dem Ausweis/Reisepass/CV-Text und gib sie als JSON zurück:

```json
{
  "first_name": "Vorname",
  "last_name": "Nachname",
  "full_name": "Nachname, Vorname",
  "birth_date": "TT.MM.JJJJ",
  "birth_place": "Stadt, Land",
  "nationality": "Staatsangehörigkeit",
  "gender": "Männlich | Weiblich | null",
  "document_type": "Personalausweis | Reisepass | Aufenthaltstitel | Sonstige",
  "document_number": "Dokumentnummer",
  "document_issue_date": "TT.MM.JJJJ oder null",
  "document_expiry_date": "TT.MM.JJJJ",
  "document_issuing_authority": "Ausstellende Behörde oder Land",
  "residence_permit_type": "null oder Permittyp",
  "residence_permit_number": "null",
  "residence_permit_expiry": "null oder TT.MM.JJJJ",
  "work_permit": "Ja | Nein | Unbeschränkt | null",
  "work_permit_expiry": "null oder TT.MM.JJJJ",
  "address": "null oder Adresse",
  "phone": "null",
  "email": "null",
  "checked_by": null,
  "check_date": null,
  "notes": null
}
```

Wichtige Regeln für den Identcheck:
- Verwende `null` für alle Felder, die nicht im Dokument gefunden werden.
- Datumsformat immer TT.MM.JJJJ.
- Vorname und Nachname separat UND als full_name ausgeben.

---
Wenn der Benutzer dich bittet, CV-Daten als JSON zu exportieren, verwende das folgende Format:

```json
{
  "name": "Nachname, Vorname",
  "birth_date": "TT.MM.JJJJ",
  "nationality": "...",
  "job_role": "Schweißer | Elektriker | etc.",
  "employment_history": [
    {
      "employer": "Firmenname",
      "position": "Position",
      "duties": ["Aufgabe 1", "Aufgabe 2"],
      "start_date": "MM/JJJJ",
      "end_date": "MM/JJJJ oder present"
    }
  ],
  "education": {
    "higher_education": [{"years": "JJJJ-JJJJ", "institution": "Name", "field": "Fach"}],
    "further_training": [{"years": "JJJJ-JJJJ", "institution": "Name", "field": "Kurs"}]
  },
  "language_skills": [{"language": "Deutsch", "level": "B2"}],
  "profile_summary": "Professionelle Zusammenfassung auf Deutsch"
}
```

Sei präzise, professionell und hilfsbereit."""


def build_chat_messages(
    chat_history: list[dict],
    cv_text: str | None = None,
    id_text: str | None = None,
    context_name: str | None = None,
) -> list[dict]:
    """
    Build the messages list for the AI, including system prompt
    and optional CV and ID document context.
    """
    messages = [{"role": "system", "content": CV_SYSTEM_PROMPT}]
    
    if context_name:
        messages.append({
            "role": "system",
            "content": f"AKTUELLER BEREICH: {context_name}. Hilf dem Benutzer spezifisch bei Fragen zu diesem Bereich."
        })

    if cv_text:
        messages.append({
            "role": "system",
            "content": f"Der Benutzer hat folgende CV-Daten hochgeladen:\n\n{cv_text}",
        })

    if id_text:
        messages.append({
            "role": "system",
            "content": (
                "Der Benutzer hat zusätzlich ein Ausweisdokument (Personalausweis / Reisepass) hochgeladen. "
                "Extrahiere daraus Geburtsort, Geburtsdatum, Ablaufdatum, Dokumentnummer und andere relevante Felder.\n\n"
                f"AUSWEISTEXT:\n{id_text}"
            ),
        })

    messages.extend(chat_history)
    return messages


def extract_json_from_response(text: str) -> dict | None:
    """
    Try to extract a JSON object from AI response text.
    Returns the parsed dict or None if no JSON found.
    """
    # Try to find JSON in code fences
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    return None


def transcribe_audio(audio_bytes: bytes, provider: str, api_key: str) -> str:
    """
    Transcribe audio bytes to text using the selected provider.
    Supported: OpenAI (Whisper), Deepgram, Eleven Labs.
    """
    if not audio_bytes:
        return ""
    
    if not api_key or not str(api_key).strip():
        raise ValueError(f"No API key provided for {provider} STT. Please add it in ⚙️ Settings.")

    if provider == "OpenAI":
        from openai import OpenAI
        import tempfile
        # IMPORTANT: Always use api.openai.com directly — ignore OPENAI_BASE_URL env var
        # which might be set to OpenRouter or other proxy that doesn't support Whisper
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.openai.com/v1",  # force direct — never use OPENAI_BASE_URL
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            with open(tmp_path, "rb") as f:
                resp = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f
                )
            return resp.text
        finally:
            os.unlink(tmp_path)

    elif provider == "Deepgram":
        import requests
        url = "https://api.deepgram.com/v1/listen?smart_format=true&model=nova-2&language=de"
        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "audio/wav"
        }
        resp = requests.post(url, headers=headers, data=audio_bytes, timeout=30)
        resp.raise_for_status()
        return resp.json()["results"]["channels"][0]["alternatives"][0]["transcript"]

    elif provider == "Eleven Labs":
        import requests
        url = "https://api.elevenlabs.io/v1/speech-to-text"
        headers = {"xi-api-key": api_key}
        files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
        data = {"model_id": "scribe_v1"}  # current ElevenLabs STT model
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=30)
        resp.raise_for_status()
        return resp.json()["text"]

    else:
        raise ValueError(f"STT not supported for provider: {provider}")
