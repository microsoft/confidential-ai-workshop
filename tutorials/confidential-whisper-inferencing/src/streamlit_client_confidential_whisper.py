# streamlit_client.py
import os
import json
import tempfile
import asyncio
import requests
import streamlit as st
from html import escape

# =========================
# ⚙️ Page Configuration
# =========================
st.set_page_config(page_title="LLM Client (Confidential GPU)", layout="wide")

# Try to import pyohttp (attested OHTTP client). If missing, we'll show a warning near the audio section.
try:
    import pyohttp  # from microsoft/attested-ohttp-client
    HAS_PYOHTTP = True
except Exception:
    HAS_PYOHTTP = False

# =========================
# 🎨 Styles
# =========================
CUSTOM_CSS = """
<style>
/* General chat styling */
[data-testid="stChatMessage"] pre, [data-testid="stChatMessage"] code {
  white-space: pre-wrap !important;
  word-break: break-word !important;
}

/* Thinking block style (light gray, monospace) */
.thinking {
  color: #9aa0a6;            /* light gray */
  background: #f5f5f7;       /* light background */
  border-radius: 6px;
  padding: 10px 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 0.92rem;
  line-height: 1.45;
  border: 1px solid #e6e6ea;
  overflow-wrap: anywhere;
}

/* Small badge for thinking expander title */
.thinking-title {
  font-weight: 600;
  color: #5f6368;
}

/* Status container (streaming) */
.streaming-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 6px;
  border-radius: 50%;
  background: #10b981; /* green */
  animation: pulse 1.2s infinite;
}
@keyframes pulse {
  0% { transform: scale(0.90); opacity: 0.7; }
  50% { transform: scale(1.20); opacity: 1.0; }
  100% { transform: scale(0.90); opacity: 0.7; }
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# =========================
# Session state
# =========================
if "messages" not in st.session_state:
    # Message history sent to model (without <think>)
    st.session_state.messages = []

if "turns" not in st.session_state:
    # Rich history for display: also memorize 'think' of each response
    # Each item: {"role": "user|assistant|system", "content": "...", "think": "...(optional)"}
    st.session_state.turns = []

# =========================
# Utilities (LLM call)
# =========================
def build_headers(api_key: str, header_mode: str):
    """
    Builds authentication headers.
    - header_mode: "X-API-Key" or "Authorization: Bearer"
    """
    headers = {"Content-Type": "application/json"}
    if api_key:
        if header_mode == "X-API-Key":
            headers["X-API-Key"] = api_key
        else:
            headers["Authorization"] = f"Bearer {api_key}"
    return headers


def parse_and_stream_tokens(
    incoming_text: str,
    state: dict,
    think_placeholder,
    chat_placeholder,
    thinking_spinner=None,
):
    """
    Incremental parsing to support <think> ... </think> tags potentially fragmented between chunks.
    """
    TAG_OPEN = "<think>"
    TAG_CLOSE = "</think>"
    MAX_TAG_LEN = max(len(TAG_OPEN), len(TAG_CLOSE))

    print(incoming_text, flush=True, end="")
    state["pending"] += incoming_text

    def flush_outside_text(text):
        if text:
            state["visible_text"] += text
            chat_placeholder.markdown(state["visible_text"])

    def flush_thinking_text(text):
        if text:
            if not state["thinking_active"] and thinking_spinner:
                thinking_spinner.markdown("🤔 *Thinking...*")
                state["thinking_active"] = True
            state["think_text"] += text
            think_placeholder.markdown(
                f"<div class='thinking'>{escape(state['think_text'])}</div>",
                unsafe_allow_html=True
            )

    while True:
        if state["in_think"]:
            idx_close = state["pending"].find(TAG_CLOSE)
            if idx_close == -1:
                if len(state["pending"]) > (MAX_TAG_LEN - 1):
                    consume = len(state["pending"]) - (MAX_TAG_LEN - 1)
                    chunk, state["pending"] = state["pending"][:consume], state["pending"][consume:]
                    flush_thinking_text(chunk)
                break
            else:
                before_close = state["pending"][:idx_close]
                flush_thinking_text(before_close)
                state["pending"] = state["pending"][idx_close + len(TAG_CLOSE):]
                state["in_think"] = False
        else:
            idx_open = state["pending"].find(TAG_OPEN)
            if idx_open == -1:
                if len(state["pending"]) > (MAX_TAG_LEN - 1):
                    consume = len(state["pending"]) - (MAX_TAG_LEN - 1)
                    chunk, state["pending"] = state["pending"][:consume], state["pending"][consume:]
                    flush_outside_text(chunk)
                break
            else:
                before_open = state["pending"][:idx_open]
                flush_outside_text(before_open)
                state["pending"] = state["pending"][idx_open + len(TAG_OPEN):]
                state["in_think"] = True


def finalize_pending(state: dict, think_placeholder, chat_placeholder, thinking_spinner=None):
    """
    At the end of the stream, push the rest of 'pending' to the right place.
    """
    if state["pending"]:
        if state["in_think"]:
            if not state["thinking_active"] and thinking_spinner:
                thinking_spinner.markdown("🤔 *Thinking...*")
                state["thinking_active"] = True
            state["think_text"] += state["pending"]
            think_placeholder.markdown(
                f"<div class='thinking'>{escape(state['think_text'])}</div>",
                unsafe_allow_html=True
            )
        else:
            state["visible_text"] += state["pending"]
            chat_placeholder.markdown(state["visible_text"])
        state["pending"] = ""

    if state["thinking_active"] and thinking_spinner:
        thinking_spinner.empty()


def stream_chat_completions(
    server_url: str,
    api_key: str,
    header_mode: str,
    model: str,
    messages: list,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    verify_ssl: bool = True,
):
    """
    Sends a chat/completions request in streaming mode (OpenAI-like format).
    Returns (assistant_visible_text, assistant_think_text).
    """
    headers = build_headers(api_key, header_mode)
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    assistant_container = st.chat_message("assistant")
    top_line = assistant_container.empty()  # status area "streaming..."
    with assistant_container:
        exp = st.expander("🧠 View reasoning (stream)", expanded=False)
        with exp:
            thinking_spinner = st.empty()
            think_placeholder = st.empty()
        chat_placeholder = st.empty()

    top_line.markdown("<span class='streaming-dot'></span>Streaming in progress…", unsafe_allow_html=True)

    parse_state = {
        "pending": "",
        "in_think": False,
        "think_text": "",
        "visible_text": "",
        "thinking_active": False,
    }

    try:
        with requests.post(
            server_url,
            headers=headers,
            json=payload,
            stream=True,
            timeout=(10, 180),
            verify=verify_ssl,
        ) as resp:
            resp.raise_for_status()

            for raw in resp.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                if raw.startswith("data:"):
                    data = raw[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    try:
                        token = event["choices"][0]["delta"].get("content", "")
                    except Exception:
                        token = ""
                    if token:
                        parse_and_stream_tokens(
                            token,
                            parse_state,
                            think_placeholder=think_placeholder,
                            chat_placeholder=chat_placeholder,
                            thinking_spinner=thinking_spinner,
                        )

        finalize_pending(parse_state, think_placeholder, chat_placeholder, thinking_spinner)
        top_line.empty()
        return parse_state["visible_text"], parse_state["think_text"]

    except requests.exceptions.RequestException as e:
        top_line.empty()
        if thinking_spinner:
            thinking_spinner.empty()
        st.error(f"Server connection error: {e}")
        st.info("Check the URL, API Key, that the service is running, and network rules.")
        return "", ""

# =========================
# OHTTP helper functions (from Microsoft sample, lightly wrapped)
# =========================
def download_kms_certificate(kms_url: str, output_file: str):
    """
    Fetches the service certificate from the Confidential KMS.
    (Matches Microsoft sample; 'verify=False' mirrors their snippet.)
    """
    resp = requests.get(kms_url.rstrip("/") + "/node/network", verify=False)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch KMS certificate: HTTP {resp.status_code}")
    cert_pem = resp.json().get("service_certificate", "")
    if not cert_pem:
        raise RuntimeError("KMS response missing 'service_certificate'")
    with open(output_file, "w") as f:
        f.write(cert_pem)


async def ohttp_infer_whisper(target_uri: str, api_key: str, audio_path: str, kms_url: str):
    """
    Async call to Confidential Whisper via OHTTP (pyohttp).
    Returns the raw response text (JSON string).
    """
    # Prepare per-run kms cert
    with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as tf:
        kms_cert_path = tf.name
    try:
        download_kms_certificate(kms_url, kms_cert_path)
        client = pyohttp.OhttpClient(kms_url, kms_cert_path)

        form_fields = {"file": "@" + audio_path, "response_format": "json"}
        outer_headers = {"api-key": api_key}

        response = await client.post(target_uri, form_fields=form_fields, outer_headers=outer_headers)
        status = response.status()
        chunks = []
        while True:
            c = await response.chunk()
            if c is None:
                break
            chunks.append(bytes(c))
        body = b"".join(chunks).decode("utf-8", errors="replace")

        if status != 200:
            raise RuntimeError(f"OHTTP Whisper failed: HTTP {status}\n{body}")
        return body
    finally:
        try:
            os.remove(kms_cert_path)
        except Exception:
            pass


def transcribe_with_ohttp(target_uri: str, api_key: str, kms_url: str, uploaded_file) -> str:
    """
    Wrapper to accept a Streamlit-uploaded file, save to tmp, and run the async OHTTP infer.
    Returns the transcript text (best effort to parse JSON and grab 'text').
    """
    if not HAS_PYOHTTP:
        raise RuntimeError("pyohttp not installed. Build from https://github.com/microsoft/attested-ohttp-client "
                           "(`./scripts/build-pyohttp.sh` then `pip install target/wheels/*.whl`).")

    # Persist upload to a temp path
    suffix = "." + (uploaded_file.name.split(".")[-1] if "." in uploaded_file.name else "bin")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
        tf.write(uploaded_file.read())
        tmp_path = tf.name

    try:
        body = asyncio.run(ohttp_infer_whisper(target_uri, api_key, tmp_path, kms_url))
        # Try JSON parse, fallback to raw
        try:
            j = json.loads(body)
            if isinstance(j, dict) and "text" in j:
                return j["text"]
        except Exception:
            pass
        return body
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


# =========================
# Sidebar (Configuration)
# =========================
with st.sidebar:
    st.subheader("⚙️ Server Configuration")
    server_url = st.text_input(
        "Server URL (chat/completions)",
        value="https://my-conf-llm.eastus2.cloudapp.azure.com/v1/chat/completions",
        help="Ex.: https://<host>/v1/chat/completions",
    )
    model_name = st.text_input(
        "Model (name/path)",
        value="/dev/shm/decrypted_model",
        help="Model name or path (ex.: /dev/shm/decrypted_model)",
    )
    header_mode = st.selectbox("Authentication Mode", options=["X-API-Key", "Authorization: Bearer"], index=0)
    api_key = st.text_input("API Key (for your vLLM)", type="password", placeholder="••••••••")
    temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.2, step=0.05)
    max_tokens = st.slider("Max response tokens", min_value=128, max_value=32000, value=2048, step=128)
    verify_ssl = st.toggle("Verify SSL certificate (vLLM)", value=True, help="Disable if you have a self-signed certificate (not recommended)")

    st.markdown("---")
    st.subheader("🔐 Confidential Whisper (OHTTP)")
    whisper_target = st.text_input(
        "Whisper Target URI (OHTTP)",
        value="https://<your-conf-whisper-endpoint>/audio/transcriptions?api-version=2024-10-21",
        help="Copy the transcription endpoint URL for your Confidential Whisper deployment."
    )
    whisper_key = st.text_input("Whisper API Key", type="password", placeholder="••••••••")
    kms_url = st.text_input(
        "KMS URL",
        value="https://accconfinferenceproduction.confidential-ledger.azure.com",
        help="Microsoft Confidential Inferencing KMS URL"
    )
    auto_ask_vllm = st.checkbox("After transcribing, ask my vLLM automatically", value=True)

    st.markdown("---")
    if st.button("🗑️ Reset conversation"):
        st.session_state.messages = []
        st.session_state.turns = []
        st.rerun()


# =========================
# Headers
# =========================
st.title("🤖 Client for Confidential GPU Inference")
st.caption("Multi-turn chat • Streaming • Clear reasoning via expander • Text + Confidential Whisper (OHTTP) audio input")

# =========================
# History Display
# =========================
for msg in st.session_state.turns:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("think"):
            with st.expander("🧠 View reasoning"):
                st.markdown(f"<div class='thinking'>{escape(msg['think'])}</div>", unsafe_allow_html=True)

# =========================
# Audio transcription (OHTTP)
# =========================
st.markdown("### 🎙️ Transcribe audio via **Confidential Whisper (OHTTP)**")
if not HAS_PYOHTTP:
    st.warning("`pyohttp` not installed. Build it from Microsoft's repo and `pip install` the wheel "
               "(see https://github.com/microsoft/attested-ohttp-client).")

audio_file = st.file_uploader("Upload audio (e.g., .mp3, .wav, .m4a)", type=["mp3","wav","m4a","ogg","mp4"], accept_multiple_files=False)

if st.button("🔐 Transcribe with OHTTP", disabled=(audio_file is None or not HAS_PYOHTTP)):
    if not whisper_target or not whisper_key or not kms_url:
        st.error("Please set Whisper Target URI, Whisper API Key, and KMS URL in the sidebar.")
    else:
        with st.spinner("Calling OHTTP → Confidential Whisper…"):
            try:
                transcript = transcribe_with_ohttp(whisper_target.strip(), whisper_key.strip(), kms_url.strip(), audio_file)
                st.success("Transcription received.")
                st.markdown("**Transcript**")
                st.code(transcript or "(empty)")

                # Log the transcript in chat, then (optionally) ask vLLM about it
                st.chat_message("user").markdown(f"*(Audio transcript)*\n\n{transcript}")
                st.session_state.turns.append({"role": "user", "content": transcript})
                st.session_state.messages.append({"role": "user", "content": transcript})

                if auto_ask_vllm:
                    visible, think = stream_chat_completions(
                        server_url=server_url.strip(),
                        api_key=api_key.strip(),
                        header_mode=header_mode,
                        model=model_name.strip(),
                        messages=st.session_state.messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        verify_ssl=verify_ssl,
                    )
                    if visible or think:
                        st.session_state.turns.append({"role": "assistant", "content": visible, "think": think})
                        st.session_state.messages.append({"role": "assistant", "content": visible})

            except Exception as e:
                st.error(f"OHTTP transcription failed: {e}")

st.markdown("---")

# =========================
# Text Input & Streaming to your vLLM
# =========================
if user_prompt := st.chat_input("Ask your question…"):
    st.chat_message("user").markdown(user_prompt)
    st.session_state.turns.append({"role": "user", "content": user_prompt})
    st.session_state.messages.append({"role": "user", "content": user_prompt})

    visible, think = stream_chat_completions(
        server_url=server_url.strip(),
        api_key=api_key.strip(),
        header_mode=header_mode,
        model=model_name.strip(),
        messages=st.session_state.messages,
        temperature=temperature,
        max_tokens=max_tokens,
        verify_ssl=verify_ssl,
    )

    if visible or think:
        st.session_state.turns.append({"role": "assistant", "content": visible, "think": think})
        st.session_state.messages.append({"role": "assistant", "content": visible})
    else:
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
            st.session_state.messages.pop()