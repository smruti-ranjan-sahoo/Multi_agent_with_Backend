import base64
from datetime import datetime
from typing import Any

import requests
import streamlit as st

import os

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
API_V1 = f"{BASE_URL}/api/v1"

PROVIDERS = ["groq", "openai", "anthropic", "gemini"]
MODELS = {
    "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "openai/gpt-oss-120b", "mixtral-8x7b-32768"],
    "openai": ["gpt-4o-mini", "gpt-4o"],
    "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
    "gemini": ["gemini-1.5-flash", "gemini-1.5-pro"],
}
USECASES = {
    "Basic Chat": "basic_chat",
    "Document QA": "document_qa",
    "Multi Agent": "multi_agent",
}

st.set_page_config(page_title="Smruti AgentX", page_icon="sparkles", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700&family=Manrope:wght@500;600;700&display=swap');

:root {
    --bg: #f2f6f9;
    --panel: #ffffff;
    --line: #d9e2ec;
    --ink: #0f172a;
    --muted: #64748b;
    --brand: #0f766e;
    --accent: #ea580c;
}

html, body, [class*="css"] {
    font-family: 'Sora', sans-serif;
}

[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at 15% 0%, #d9f7f2 0%, transparent 28%),
        radial-gradient(circle at 90% 20%, #fff1db 0%, transparent 22%),
        var(--bg);
    color: var(--ink);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #111827 0%, #0b1220 100%);
    border-right: 1px solid rgba(71, 85, 105, 0.5);
}

[data-testid="stSidebar"] * {
    color: #d1d5db;
}

.block-container {
    padding-top: 1rem;
    padding-bottom: 1.2rem;
}

.hero {
    border-radius: 18px;
    border: 1px solid var(--line);
    background: rgba(255, 255, 255, 0.82);
    backdrop-filter: blur(8px);
    padding: 0.9rem 1rem;
    margin-bottom: 0.8rem;
}

.card {
    border-radius: 16px;
    border: 1px solid var(--line);
    background: #fff;
    padding: 0.9rem 1rem;
}

.subtle {
    color: var(--muted);
    font-size: 0.85rem;
}

.status-ok {
    color: #16a34a;
    font-weight: 700;
}

.status-err {
    color: #dc2626;
    font-weight: 700;
}

.brand-title {
    font-size: 1.06rem;
    font-weight: 700;
    color: white;
    margin: 0;
}

.brand-sub {
    font-size: 0.74rem;
    color: #94a3b8;
    margin: 0.1rem 0 0;
}

.thread-chip {
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 0.4rem 0.55rem;
    background: rgba(15, 23, 42, 0.55);
    margin-bottom: 0.4rem;
}

.thread-chip-title {
    font-size: 0.78rem;
    color: #e2e8f0;
    margin: 0;
}

.thread-chip-meta {
    font-size: 0.67rem;
    color: #94a3b8;
    margin: 0.15rem 0 0;
}

.stChatMessage {
    border-radius: 14px;
    border: 1px solid #e2e8f0;
    background: #fff;
    padding: 0.35rem;
}

.stButton > button {
    border-radius: 10px !important;
    font-weight: 600 !important;
}

[data-testid="stSidebar"] .stButton > button {
    background: rgba(30, 41, 59, 0.82) !important;
    color: #f8fafc !important;
    border: 1px solid rgba(71, 85, 105, 0.66) !important;
}

.btn-new [data-testid="stButton"] > button {
    background: #0d9488 !important;
    border: 1px solid #0f766e !important;
    color: #ffffff !important;
    font-weight: 700 !important;
}

.auth-card {
    border: 1px solid #1e3a5f;
    border-radius: 12px;
    background: rgba(5, 19, 45, 0.65);
    padding: 0.65rem;
    margin: 0.5rem 0 0.8rem;
}

.auth-label {
    font-size: 0.7rem;
    letter-spacing: 0.11em;
    text-transform: uppercase;
    color: #93c5fd;
    margin: 0;
}

.auth-value {
    font-size: 0.95rem;
    color: #4ade80;
    margin: 0.35rem 0 0;
    font-weight: 600;
}

.top-chip-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.55rem;
    margin-bottom: 0.75rem;
}

.top-chip {
    border-radius: 999px;
    border: 1px solid #cbd5e1;
    background: rgba(255, 255, 255, 0.88);
    color: #475569;
    font-size: 0.82rem;
    padding: 0.26rem 0.68rem;
}

.top-health {
    margin-left: auto;
    color: #0f766e;
    font-weight: 700;
}

.tabs-shell {
    border: 1px solid #d8e0eb;
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.84);
    padding: 0.65rem;
    margin-bottom: 0.8rem;
}

.doc-banner {
    border: 1px solid #f2d9a7;
    border-radius: 14px;
    background: #fffaf0;
    padding: 0.78rem 0.9rem;
    margin-bottom: 0.8rem;
}

.doc-banner b {
    color: #111827;
}

.workspace-card {
    border: 1px solid #dbe3ee;
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.96);
    padding: 0.8rem;
    min-height: 420px;
}

.footer-note {
    color: #94a3b8;
    font-size: 0.78rem;
    margin-top: 0.35rem;
}
</style>
""",
    unsafe_allow_html=True,
)


def new_conversation_id() -> str:
    return f"conv_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def default_state() -> dict[str, Any]:
    conversation_id = new_conversation_id()
    return {
        "token": "",
        "username": "",
        "page": "login",
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "usecase": "basic_chat",
        "conversation_id": conversation_id,
        "namespace": conversation_id,
        "thread_title": "New Conversation",
        "threads": [],
        "messages_by_conversation": {},
        "audio_enabled": True,
        "tts_voice": "alloy",
        "tts_speed": 1.0,
        "stt_language": "en",
        "auto_play": False,
        "voice_input_text": "",
    }


def init_state() -> None:
    for key, value in default_state().items():
        if key not in st.session_state:
            st.session_state[key] = value


def auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}


def api_get(path: str, auth: bool = False):
    try:
        return requests.get(
            f"{API_V1}{path}",
            headers=auth_header() if auth else {},
            timeout=20,
        )
    except requests.exceptions.ConnectionError:
        return None


def api_post(path: str, payload: dict[str, Any] | None = None, auth: bool = False):
    headers = {"Content-Type": "application/json"}
    if auth:
        headers.update(auth_header())
    try:
        return requests.post(f"{API_V1}{path}", json=payload, headers=headers, timeout=60)
    except requests.exceptions.ConnectionError:
        return None


def api_upload(path: str, files, data=None, auth: bool = False):
    try:
        return requests.post(
            f"{API_V1}{path}",
            files=files,
            data=data,
            headers=auth_header() if auth else {},
            timeout=120,
        )
    except requests.exceptions.ConnectionError:
        return None


def get_models_for_provider(provider: str) -> list[str]:
    response = api_get(f"/chat/models?provider={provider}", auth=True)
    if response and response.status_code == 200:
        models = response.json().get("models") or []
        if models:
            return models
    return MODELS.get(provider, MODELS["groq"])


def get_conversation_messages(conversation_id: str) -> list[dict[str, Any]]:
    data = st.session_state.messages_by_conversation
    if conversation_id not in data:
        data[conversation_id] = []
    return data[conversation_id]


def summarize_title(text: str) -> str:
    clean = " ".join((text or "").split()).strip()
    if not clean:
        return "New Conversation"
    return clean[:40] + ("..." if len(clean) > 40 else "")


def upsert_thread() -> None:
    conv_id = st.session_state.conversation_id
    messages = get_conversation_messages(conv_id)
    preview = messages[-1]["content"] if messages else "No messages yet"

    entry = {
        "id": conv_id,
        "title": st.session_state.thread_title,
        "updated_at": datetime.now().isoformat(),
        "preview": str(preview)[:90],
    }

    threads = [t for t in st.session_state.threads if t["id"] != conv_id]
    threads.insert(0, entry)
    st.session_state.threads = threads[:20]


def switch_thread(thread_id: str) -> None:
    st.session_state.conversation_id = thread_id
    st.session_state.namespace = thread_id
    selected = next((t for t in st.session_state.threads if t["id"] == thread_id), None)
    st.session_state.thread_title = selected["title"] if selected else "New Conversation"


def start_new_thread() -> None:
    conv_id = new_conversation_id()
    st.session_state.conversation_id = conv_id
    st.session_state.namespace = conv_id
    st.session_state.thread_title = "New Conversation"
    get_conversation_messages(conv_id)
    upsert_thread()


def add_message(role: str, content: str, meta: dict[str, Any] | None = None) -> None:
    messages = get_conversation_messages(st.session_state.conversation_id)
    messages.append({"role": role, "content": content, "meta": meta or {}})
    if role == "user" and st.session_state.thread_title == "New Conversation":
        st.session_state.thread_title = summarize_title(content)
    upsert_thread()


def logout() -> None:
    fresh = default_state()
    for key, value in fresh.items():
        st.session_state[key] = value


def get_available_voices() -> list[str]:
    response = api_get("/chat/audio/voices", auth=True)
    if response and response.status_code == 200:
        voices = response.json().get("voices") or []
        ids = [v.get("id") for v in voices if v.get("id")]
        if ids:
            return ids
    return ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]


def get_available_languages() -> dict[str, str]:
    response = api_get("/chat/audio/languages", auth=True)
    if response and response.status_code == 200:
        langs = response.json().get("languages") or []
        normalized = {item.get("code"): item.get("name") for item in langs if item.get("code") and item.get("name")}
        if normalized:
            return normalized
    return {"en": "English", "es": "Spanish", "fr": "French", "de": "German"}


def transcribe_audio(audio_bytes: bytes) -> str:
    try:
        response = requests.post(
            f"{API_V1}/chat/speech-to-text",
            files={"file": ("audio.wav", audio_bytes, "audio/wav")},
            data={"language": st.session_state.stt_language, "prompt": ""},
            headers=auth_header(),
            timeout=60,
        )
    except requests.exceptions.ConnectionError:
        return ""

    if response.status_code != 200:
        return ""
    payload = response.json()
    return payload.get("text") if payload.get("success") else ""


def synthesize_speech(text: str) -> bytes | None:
    payload = {
        "text": text,
        "voice": st.session_state.tts_voice,
        "speed": st.session_state.tts_speed,
        "language": st.session_state.stt_language,
    }
    try:
        response = requests.post(
            f"{API_V1}/chat/text-to-speech",
            json=payload,
            headers=auth_header(),
            timeout=40,
        )
    except requests.exceptions.ConnectionError:
        return None

    if response.status_code != 200:
        return None
    data = response.json()
    if not data.get("success"):
        return None
    audio_b64 = data.get("audio_base64")
    return base64.b64decode(audio_b64) if audio_b64 else None


def sidebar() -> None:
    with st.sidebar:
        st.markdown(
            """
            <div style='display:flex;align-items:center;gap:0.6rem;'>
                <div style='width:2.15rem;height:2.15rem;border-radius:0.8rem;background:linear-gradient(135deg,#0f766e,#14b8a6,#f59e0b);box-shadow:0 8px 20px rgba(15,118,110,0.32);'></div>
                <div>
                    <p class='brand-title'>Smruti AgentX</p>
                    <p class='brand-sub'>Unified AI Workspace</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<div class='btn-new'>", unsafe_allow_html=True)
        if st.button("+  New Conversation", use_container_width=True):
            start_new_thread()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        auth_status = "Authenticated" if st.session_state.token else "Not authenticated"
        st.markdown(
            f"""
            <div class='auth-card'>
                <p class='auth-label'>Authentication</p>
                <p class='auth-value'>{auth_status}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Open Auth Page", use_container_width=True):
                st.session_state.page = "login"
                st.rerun()
        with col_b:
            if st.button("Logout", use_container_width=True):
                logout()
                st.rerun()

        st.markdown("---")
        if st.button("Chat", use_container_width=True):
            st.session_state.page = "chat"
            st.rerun()
        if st.button("Documents", use_container_width=True):
            st.session_state.page = "upload"
            st.rerun()
        if st.button("System Health", use_container_width=True):
            st.session_state.page = "health"
            st.rerun()
        if st.button("History", use_container_width=True):
            st.session_state.page = "history"
            st.rerun()

        st.markdown("---")
        st.markdown("Recent Threads")
        if not st.session_state.threads:
            st.caption("No threads yet")
        else:
            for thread in st.session_state.threads[:8]:
                st.markdown(
                    f"""
                    <div class='thread-chip'>
                        <p class='thread-chip-title'>{thread['title']}</p>
                        <p class='thread-chip-meta'>{thread['id'][-12:]}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button("Open", key=f"open_{thread['id']}", use_container_width=True):
                    switch_thread(thread["id"])
                    st.session_state.page = "chat"
                    st.rerun()

        st.markdown("---")
        st.markdown("Assistant Settings")

        usecase_label = st.selectbox("Mode", list(USECASES.keys()))
        st.session_state.usecase = USECASES[usecase_label]

        provider = st.selectbox("Provider", PROVIDERS, index=PROVIDERS.index(st.session_state.provider))
        st.session_state.provider = provider

        models = get_models_for_provider(provider)
        selected_index = models.index(st.session_state.model) if st.session_state.model in models else 0
        st.session_state.model = st.selectbox("Model", models, index=selected_index)

        with st.expander("Audio", expanded=False):
            st.session_state.audio_enabled = st.checkbox("Enable audio", value=st.session_state.audio_enabled)
            if st.session_state.audio_enabled:
                voices = get_available_voices()
                voice_idx = voices.index(st.session_state.tts_voice) if st.session_state.tts_voice in voices else 0
                st.session_state.tts_voice = st.selectbox("Voice", voices, index=voice_idx)
                st.session_state.tts_speed = st.slider("Speed", 0.5, 2.0, float(st.session_state.tts_speed), 0.1)
                langs = get_available_languages()
                lang_keys = list(langs.keys())
                lang_idx = lang_keys.index(st.session_state.stt_language) if st.session_state.stt_language in lang_keys else 0
                st.session_state.stt_language = st.selectbox("Language", lang_keys, index=lang_idx, format_func=lambda x: langs.get(x, x))
                st.session_state.auto_play = st.checkbox("Auto play response", value=st.session_state.auto_play)

            st.markdown("---")
            st.caption(f"Signed in as {st.session_state.username or 'guest'}")
            st.caption(f"Current: {st.session_state.thread_title}")


def page_login() -> None:
    st.markdown(
        """
        <div class='hero'>
            <h3 style='margin:0;'>Smruti AgentX</h3>
            <p class='subtle' style='margin:0.25rem 0 0;'>Login to access chat, document QA, and health monitoring.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_login, tab_signup = st.tabs(["Sign In", "Create Account"])

    with tab_login:
        email = st.text_input("Email or username", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login", use_container_width=True, key="login_btn"):
            if not email or not password:
                st.warning("Enter both username/email and password")
            else:
                response = requests.post(
                    f"{API_V1}/auth/login",
                    data={"username": email, "password": password},
                    timeout=30,
                )
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.token = data.get("access_token", "")
                    st.session_state.username = email
                    st.session_state.page = "chat"
                    start_new_thread()
                    st.rerun()
                else:
                    detail = response.json().get("detail") if response.headers.get("content-type", "").startswith("application/json") else response.text
                    st.error(detail or "Login failed")

    with tab_signup:
        full_name = st.text_input("Full name", key="signup_name")
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        confirm = st.text_input("Confirm password", type="password", key="signup_confirm")
        if st.button("Create Account", use_container_width=True, key="signup_btn"):
            if not full_name or not email or not password:
                st.warning("Fill all fields")
            elif password != confirm:
                st.error("Passwords do not match")
            else:
                response = api_post("/auth/register", {"email": email, "password": password, "full_name": full_name})
                if response and response.status_code in (200, 201):
                    st.success("Account created. Please login.")
                else:
                    detail = response.json().get("detail") if response and response.headers.get("content-type", "").startswith("application/json") else "Registration failed"
                    st.error(detail)


def page_chat() -> None:
    sidebar()

    health = api_get("/health")
    health_text = "Systems Operational" if health and health.status_code == 200 else "Backend Offline"

    st.markdown(
        f"""
        <div class='top-chip-row'>
            <span class='top-chip'>Mode: {st.session_state.usecase}</span>
            <span class='top-chip'>Provider: {st.session_state.provider}</span>
            <span class='top-chip'>Model: {st.session_state.model}</span>
            <span class='top-chip'>Audio: STT + TTS enabled</span>
            <span class='top-health'>{health_text}</span>
        </div>
        <div class='tabs-shell'>
            <div class='subtle' style='font-size:0.78rem;'>Quick mode switching</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_chat, tab_doc, tab_multi, tab_health = st.columns(4)
    with tab_chat:
        if st.button("Basic Chat", use_container_width=True, key="tab_basic"):
            st.session_state.usecase = "basic_chat"
            st.session_state.page = "chat"
            st.rerun()
    with tab_doc:
        if st.button("Document QA", use_container_width=True, key="tab_doc"):
            st.session_state.usecase = "document_qa"
            st.session_state.page = "chat"
            st.rerun()
    with tab_multi:
        if st.button("Multi Agent", use_container_width=True, key="tab_multi"):
            st.session_state.usecase = "multi_agent"
            st.session_state.page = "chat"
            st.rerun()
    with tab_health:
        if st.button("System Health", use_container_width=True, key="tab_health"):
            st.session_state.page = "health"
            st.rerun()

    if st.session_state.usecase == "document_qa":
        st.markdown(
            f"""
            <div class='doc-banner'>
                <span style='font-size:1rem;'>No file uploaded</span>
                <span class='subtle'> upload to index in Pinecone</span>
                <span style='float:right;background:#fef3c7;border-radius:999px;padding:0.2rem 0.6rem;color:#92400e;font-size:0.82rem;'>Namespace: {st.session_state.namespace}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    messages = get_conversation_messages(st.session_state.conversation_id)
    st.markdown("<div class='workspace-card'>", unsafe_allow_html=True)
    if not messages:
        st.info("Login and send a message to start the conversation.")

    for i, msg in enumerate(messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg["content"] and st.session_state.audio_enabled:
                if st.button("Play audio", key=f"play_{i}_{st.session_state.conversation_id}"):
                    audio = synthesize_speech(msg["content"])
                    if audio:
                        st.audio(audio, format="audio/mp3")
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.usecase == "document_qa":
        upload_col, ns_col = st.columns([1.4, 1])
        with upload_col:
            uploaded = st.file_uploader(
                "Upload document",
                type=["pdf", "csv", "docx", "pptx", "xlsx", "xls", "txt", "md", "rtf", "json", "html", "htm"],
                key="chat_inline_upload",
            )
            if uploaded and st.button("Upload to Pinecone", use_container_width=True, key="chat_upload_btn"):
                with st.spinner(f"Indexing {uploaded.name}..."):
                    files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
                    response = api_upload("/chat/upload", files=files, data={"namespace": st.session_state.namespace}, auth=True)
                if response and response.status_code == 200:
                    data = response.json()
                    st.success(f"Indexed {data.get('chunks', '?')} chunks")
                else:
                    st.error(response.text if response is not None else "Backend offline")
        with ns_col:
            st.session_state.namespace = st.text_input("Namespace", value=st.session_state.namespace, key="chat_namespace")

    if st.session_state.audio_enabled:
        with st.expander("Voice input", expanded=False):
            audio_file = st.audio_input("Record prompt", key="audio_record")
            if audio_file and st.button("Transcribe"):
                transcript = transcribe_audio(audio_file.getvalue())
                if transcript:
                    st.session_state.voice_input_text = transcript
                    st.success("Voice captured")

    prompt = st.chat_input("Message Smruti AgentX...")
    if st.session_state.voice_input_text:
        st.caption(f"Voice draft: {st.session_state.voice_input_text}")
        if st.button("Use voice draft"):
            prompt = st.session_state.voice_input_text
            st.session_state.voice_input_text = ""

    if prompt and prompt.strip():
        add_message("user", prompt)

        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "provider": st.session_state.provider,
            "model": st.session_state.model,
            "stream": False,
            "conversation_id": st.session_state.conversation_id,
            "usecase": st.session_state.usecase,
            "has_documents": st.session_state.usecase == "document_qa",
            "namespace": st.session_state.namespace,
        }

        with st.spinner("Thinking..."):
            response = api_post("/chat/send", payload, auth=True)

        if response is None:
            reply = "Cannot reach backend."
            meta = {}
        elif response.status_code == 200:
            data = response.json()
            reply = data.get("final_response") or data.get("response") or data.get("message") or str(data)
            meta = {k: v for k, v in data.items() if k not in ("final_response", "response", "message", "messages")}
        elif response.status_code == 401:
            st.error("Session expired")
            logout()
            st.rerun()
            return
        else:
            reply = f"Error {response.status_code}: {response.text}"
            meta = {}

        add_message("assistant", reply, meta=meta)

        if st.session_state.audio_enabled and st.session_state.auto_play and reply:
            audio = synthesize_speech(reply)
            if audio:
                st.audio(audio, format="audio/mp3")

        st.markdown("<div class='footer-note'>Tip: switch to Document QA mode to ask questions from uploaded files.</div>", unsafe_allow_html=True)

        st.rerun()


def page_upload() -> None:
    sidebar()

    st.markdown(
        """
        <div class='hero'>
            <h3 style='margin:0;'>Documents (RAG)</h3>
            <p class='subtle' style='margin:0.25rem 0 0;'>Upload a file and index it in Pinecone for retrieval-based answers.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    namespace = st.text_input("Namespace", value=st.session_state.namespace)
    st.session_state.namespace = namespace.strip() or st.session_state.conversation_id

    uploaded = st.file_uploader("Choose file", type=["pdf", "csv", "docx", "pptx", "xlsx", "xls", "txt", "md", "rtf", "json", "html", "htm"])

    if uploaded and st.button("Upload and index", use_container_width=True):
        with st.spinner(f"Indexing {uploaded.name}..."):
            files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
            response = api_upload("/chat/upload", files=files, data={"namespace": st.session_state.namespace}, auth=True)

        if response and response.status_code == 200:
            data = response.json()
            st.success(f"Indexed {data.get('chunks', '?')} chunks")
            st.session_state.usecase = "document_qa"
        else:
            st.error(response.text if response is not None else "Backend offline")


def page_health() -> None:
    sidebar()

    st.markdown(
        """
        <div class='hero'>
            <h3 style='margin:0;'>System Health</h3>
            <p class='subtle' style='margin:0.25rem 0 0;'>Check API and dependencies status.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("API")
        health = api_get("/health")
        if health and health.status_code == 200:
            st.markdown("<span class='status-ok'>ONLINE</span>", unsafe_allow_html=True)
            st.json(health.json())
        else:
            st.markdown("<span class='status-err'>OFFLINE</span>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("Details")
        details = api_get("/health/details")
        if details and details.status_code == 200:
            st.json(details.json())
        else:
            st.warning("Could not load health details")
        st.markdown("</div>", unsafe_allow_html=True)


def page_history() -> None:
    sidebar()

    st.markdown(
        """
        <div class='hero'>
            <h3 style='margin:0;'>History</h3>
            <p class='subtle' style='margin:0.25rem 0 0;'>Recent threads and conversation logs from this session.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not st.session_state.threads:
        st.info("No conversation history yet")
        return

    for idx, thread in enumerate(st.session_state.threads, start=1):
        with st.expander(f"{idx}. {thread['title']}"):
            st.caption(f"Thread: {thread['id']}")
            st.caption(f"Updated: {thread['updated_at']}")
            st.write(thread.get("preview") or "No preview")
            if st.button("Open this thread", key=f"open_hist_{thread['id']}"):
                switch_thread(thread["id"])
                st.session_state.page = "chat"
                st.rerun()


init_state()

if not st.session_state.token:
    st.session_state.page = "login"

if st.session_state.page == "login":
    page_login()
elif st.session_state.page == "chat":
    page_chat()
elif st.session_state.page == "upload":
    page_upload()
elif st.session_state.page == "health":
    page_health()
elif st.session_state.page == "history":
    page_history()
else:
    st.session_state.page = "chat"
    st.rerun()
