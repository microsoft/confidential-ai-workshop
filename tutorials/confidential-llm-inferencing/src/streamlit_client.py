import json
import requests
import streamlit as st
from html import escape

# =========================
# ⚙️ Page Configuration
# =========================
st.set_page_config(page_title="LLM Client (Confidential GPU)", layout="wide")

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
# 🧠 Session state
# =========================
if "messages" not in st.session_state:
    # Message history sent to model (without <think>)
    st.session_state.messages = []

if "turns" not in st.session_state:
    # Rich history for display: we also memorize the 'think' of each response
    # Each item: {"role": "user|assistant|system", "content": "...", "think": "...(optional)"}
    st.session_state.turns = []

# =========================
# Utilities
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
    Updates in real time:
      - the 'thinking' placeholder (gray) when in_think == True
      - the 'chat' placeholder (normal) otherwise

    'state' contains:
      - state["pending"]: pending text to detect fragmented tags
      - state["in_think"]: bool
      - state["think_text"]: accumulation for expander
      - state["visible_text"]: accumulation for chat display
      - state["thinking_active"]: bool to track if spinner is shown
    """
    TAG_OPEN = "<think>"
    TAG_CLOSE = "</think>"
    MAX_TAG_LEN = max(len(TAG_OPEN), len(TAG_CLOSE))

    # Adds the new chunk
    state["pending"] += incoming_text

    # We'll consume 'pending' progressively while keeping a small "queue"
    # to avoid breaking tags split on chunk boundaries.
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
            think_placeholder.markdown(f"<div class='thinking'>{escape(state['think_text'])}</div>", unsafe_allow_html=True)

    while True:
        if state["in_think"]:
            # Look for closing tag
            idx_close = state["pending"].find(TAG_CLOSE)
            if idx_close == -1:
                # Nothing to close in this chunk -> we can purge everything except a small "queue"
                if len(state["pending"]) > (MAX_TAG_LEN - 1):
                    consume = len(state["pending"]) - (MAX_TAG_LEN - 1)
                    chunk, state["pending"] = state["pending"][:consume], state["pending"][consume:]
                    flush_thinking_text(chunk)
                break
            else:
                # Found the closing tag, flush the thinking part
                before_close = state["pending"][:idx_close]
                flush_thinking_text(before_close)
                # Skip the closing tag
                state["pending"] = state["pending"][idx_close + len(TAG_CLOSE):]
                state["in_think"] = False
                # continue the loop to process the rest in the same pending
        else:
            # We're outside thinking, look for opening
            idx_open = state["pending"].find(TAG_OPEN)
            if idx_open == -1:
                # No opening -> we can send everything to chat except a small "queue"
                if len(state["pending"]) > (MAX_TAG_LEN - 1):
                    consume = len(state["pending"]) - (MAX_TAG_LEN - 1)
                    chunk, state["pending"] = state["pending"][:consume], state["pending"][consume:]
                    flush_outside_text(chunk)
                break
            else:
                # Send what's before the opening to chat, then switch to thinking mode
                before_open = state["pending"][:idx_open]
                flush_outside_text(before_open)
                # Skip the opening tag
                state["pending"] = state["pending"][idx_open + len(TAG_OPEN):]
                state["in_think"] = True
                # continue to potentially process the rest immediately


def finalize_pending(state: dict, think_placeholder, chat_placeholder, thinking_spinner=None):
    """
    At the end of the stream, we push the rest of 'pending' to the right place.
    """
    if state["pending"]:
        if state["in_think"]:
            if not state["thinking_active"] and thinking_spinner:
                thinking_spinner.markdown("🤔 *Thinking...*")
                state["thinking_active"] = True
            state["think_text"] += state["pending"]
            think_placeholder.markdown(f"<div class='thinking'>{escape(state['think_text'])}</div>", unsafe_allow_html=True)
        else:
            state["visible_text"] += state["pending"]
            chat_placeholder.markdown(state["visible_text"])
        state["pending"] = ""
    
    # Clear the thinking spinner when done
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
    Streams live in the UI via placeholders provided by the caller.
    """
    headers = build_headers(api_key, header_mode)
    print(messages)
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # Visual container for assistant response
    assistant_container = st.chat_message("assistant")
    top_line = assistant_container.empty()  # status area "streaming..."
    with assistant_container:
        exp = st.expander("🧠 View reasoning (stream)", expanded=False)
        with exp:
            thinking_spinner = st.empty()  # spinner for reasoning
            think_placeholder = st.empty()      # thinking (light gray)
        chat_placeholder = st.empty()        # visible text (normal)

    # Streaming indicator
    top_line.markdown("<span class='streaming-dot'></span>Streaming in progress…", unsafe_allow_html=True)

    # Parser state
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
                # Typical SSE format: "data: {...}" or "data: [DONE]"
                if raw.startswith("data:"):
                    data = raw[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        # malformed line
                        continue
                    # Get the delta content (OpenAI-like streaming)
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

        # End of stream: flush remaining pending
        finalize_pending(parse_state, think_placeholder, chat_placeholder, thinking_spinner)
        top_line.empty()  # remove streaming badge

        return parse_state["visible_text"], parse_state["think_text"]

    except requests.exceptions.RequestException as e:
        top_line.empty()
        if thinking_spinner:
            thinking_spinner.empty()
        st.error(f"Server connection error: {e}")
        st.info("Check the URL, API Key, that the service is running, and network rules.")
        return "", ""


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
    api_key = st.text_input("API Key", type="password", placeholder="••••••••")
    temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.2, step=0.05)
    max_tokens = st.slider("Max response tokens", min_value=128, max_value=32000, value=2048, step=128)
    verify_ssl = st.toggle("Verify SSL certificate", value=True, help="Disable if you have a self-signed certificate (not recommended)")

    st.markdown("---")
    if st.button("🗑️ Reset conversation"):
        st.session_state.messages = []
        st.session_state.turns = []
        st.rerun()


# =========================
# Header
# =========================
st.title("🤖 Client for Confidential GPU Inference")
st.caption("Multi‑turn chat • Streaming • Clear reasoning via expander • Configurable server & API Key")

# =========================
# History Display
# =========================
# Display past turns (without re-streaming).
for msg in st.session_state.turns:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("think"):
            with st.expander("🧠 View reasoning"):
                st.markdown(f"<div class='thinking'>{escape(msg['think'])}</div>", unsafe_allow_html=True)

# =========================
# User Input & Streaming
# =========================
if user_prompt := st.chat_input("Ask your question…"):
    # 1) Display and store on UI side
    st.chat_message("user").markdown(user_prompt)
    st.session_state.turns.append({"role": "user", "content": user_prompt})

    # 2) Add to context sent to model (without <think>)
    st.session_state.messages.append({"role": "user", "content": user_prompt})

    # 3) Send to server and stream live (with <think> parsing)
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

    # 4) Store the "clean" response (without <think> tags), and the reasoning separately
    if visible or think:
        st.session_state.turns.append({"role": "assistant", "content": visible, "think": think})
        # Important: we do NOT send the 'think' to the next turn, only the visible part
        st.session_state.messages.append({"role": "assistant", "content": visible})
    else:
        # In case of error, remove the last user message to avoid a broken context
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
            st.session_state.messages.pop()
