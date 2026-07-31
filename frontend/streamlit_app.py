"""
PHASE 5 — Frontend Website
Full-featured RAGent chat app:
 - Multi-user login/register
 - Multi-chat sidebar (new / rename / delete), persisted to disk
 - PDF/DOCX/TXT/CSV upload (multi-file) + paste-text
 - Adjustable chunk size/overlap, source filter, query expansion toggle
 - Streaming answers with a "thinking" status indicator
 - Confidence badges + "sources considered" transparency panel
 - PDF preview with highlighted citation text
 - Document summarizer + quiz generator
 - Follow-up question suggestions
 - Thumbs up/down feedback
 - Token usage tracker
 - Export chat as Markdown
 - Dark/light theme toggle
 - Evaluation dashboard tab
 - Basic voice-input helper (browser speech-to-text, copy into chat box)
"""

import streamlit as st
import requests
import json
import uuid
import base64
import time
import os
from stream_client import start_stream, drain_queue

# API_URL resolution order: Streamlit Cloud secrets -> environment variable -> localhost default.
# This lets the exact same code run locally (backend on localhost:8000) and in production
# (backend deployed on Render, URL set as a secret/env var) with zero code changes.
try:
    API_URL = st.secrets["API_URL"]
except Exception:
    API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="RAGent", page_icon="🤖", layout="wide")

# ---------------- Theme ----------------
if "theme" not in st.session_state:
    st.session_state.theme = "dark"

def inject_theme():
    if st.session_state.theme == "light":
        st.markdown("""
            <style>
            .stApp { background-color: #ffffff; color: #111111; }
            section[data-testid="stSidebar"] { background-color: #f3f3f3; }
            </style>
        """, unsafe_allow_html=True)
    st.markdown("""
        <style>
        .stChatMessage { border-radius: 16px; padding: 4px 2px; }
        #MainMenu, footer {visibility: hidden;}

        /* Rounded pill-style buttons throughout, closer to ChatGPT/Gemini */
        .stButton > button {
            border-radius: 20px !important;
        }

        /* Icon-only popover trigger buttons (attach / mic) rendered as round icon buttons */
        div[data-testid="stPopover"] > div > button {
            border-radius: 50% !important;
            width: 42px !important;
            height: 42px !important;
            padding: 0 !important;
            font-size: 18px !important;
        }

        /* Sidebar chat list buttons: left-aligned, tighter */
        section[data-testid="stSidebar"] .stButton > button {
            text-align: left;
            border-radius: 10px !important;
        }

        /* Profile popover trigger pinned bottom, pill-shaped */
        section[data-testid="stSidebar"] div[data-testid="stPopover"] > div > button {
            border-radius: 20px !important;
            width: 100% !important;
            height: auto !important;
            text-align: left;
            padding: 8px 14px !important;
        }
        </style>
    """, unsafe_allow_html=True)

inject_theme()

# ---------------- Auth (multi-user) ----------------
if "authed" not in st.session_state:
    st.session_state.authed = False
if "username" not in st.session_state:
    st.session_state.username = None

def backend_is_up():
    try:
        requests.get(f"{API_URL}/", timeout=3)
        return True
    except Exception:
        return False

if not st.session_state.authed:
    st.markdown(
        """
        <style>
        .ragent-hero {
            text-align: center;
            margin-top: 40px;
            margin-bottom: 8px;
        }
        .ragent-hero h1 {
            font-size: 46px;
            margin-bottom: 0;
            background: linear-gradient(90deg, #7c3aed, #06b6d4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .ragent-tagline {
            text-align: center;
            color: #9ca3af;
            font-size: 16px;
            margin-bottom: 28px;
        }
        .ragent-feature-row {
            display: flex;
            justify-content: center;
            gap: 28px;
            margin: 24px 0 36px 0;
            flex-wrap: wrap;
        }
        .ragent-feature {
            text-align: center;
            font-size: 13px;
            color: #9ca3af;
            max-width: 140px;
        }
        .ragent-feature .icon { font-size: 26px; display:block; margin-bottom:4px; }
        </style>

        <div class="ragent-hero"><h1>RAGent 🤖</h1></div>
        <p class="ragent-tagline">Your documents. Your answers. Cited and true.</p>

        <div class="ragent-feature-row">
            <div class="ragent-feature"><span class="icon">📄</span>Upload PDFs, DOCX, TXT, CSV</div>
            <div class="ragent-feature"><span class="icon">⚡</span>Streaming, cited answers</div>
            <div class="ragent-feature"><span class="icon">🧩</span>Quizzes & summaries</div>
            <div class="ragent-feature"><span class="icon">🔒</span>Private, per-account knowledge base</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not backend_is_up():
        st.error("⚠️ Backend not reachable. Start it with `uvicorn app.main:app --reload` first.")
        st.stop()

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        with st.container(border=True):
            tab_login, tab_register = st.tabs(["🔑 Log in", "✨ Create account"])

            with tab_login:
                username = st.text_input("Username", key="login_user", placeholder="your username")
                password = st.text_input("Password", type="password", key="login_pass", placeholder="••••••••")
                if st.button("Log in", use_container_width=True, type="primary"):
                    try:
                        res = requests.post(f"{API_URL}/login", data={"username": username, "password": password}, timeout=10)
                        if res.status_code == 200:
                            st.session_state.authed = True
                            st.session_state.username = username
                            st.rerun()
                        else:
                            st.error(res.json().get("detail", "Login failed."))
                    except Exception as e:
                        st.error(f"Login error: {e}")
                st.caption("Default admin account: admin / ragent123 (change in .env)")

            with tab_register:
                new_username = st.text_input("Choose a username", key="reg_user", placeholder="e.g. yourname")
                new_password = st.text_input("Choose a password", type="password", key="reg_pass", placeholder="••••••••")
                if st.button("Create account", use_container_width=True, type="primary"):
                    if not new_username or not new_password:
                        st.warning("Fill in both fields.")
                    else:
                        try:
                            res = requests.post(f"{API_URL}/register", data={"username": new_username, "password": new_password}, timeout=10)
                            if res.status_code == 200:
                                st.success("Account created! Switch to 'Log in' tab.")
                            else:
                                st.error(res.json().get("detail", "Registration failed."))
                        except Exception as e:
                            st.error(f"Registration error: {e}")
    st.stop()

USER = st.session_state.username

# ---------------- Session state ----------------
def load_chats_from_backend():
    try:
        res = requests.get(f"{API_URL}/load_chats", params={"user": USER}, timeout=5)
        if res.status_code == 200:
            data = res.json().get("chats")
            if data:
                return data
    except Exception:
        pass
    return None


def save_chats_to_backend():
    try:
        requests.post(f"{API_URL}/save_chats", data={"user": USER, "payload": json.dumps(st.session_state.chats)}, timeout=5)
    except Exception:
        pass


if "chats" not in st.session_state:
    loaded = load_chats_from_backend()
    if loaded:
        st.session_state.chats = loaded
        st.session_state.active_chat = list(loaded.keys())[0]
    else:
        first_id = str(uuid.uuid4())
        st.session_state.chats = {first_id: {"title": "New Chat", "messages": []}}
        st.session_state.active_chat = first_id

if "docs_uploaded" not in st.session_state:
    st.session_state.docs_uploaded = []
if "session_tokens" not in st.session_state:
    st.session_state.session_tokens = 0


def new_chat():
    new_id = str(uuid.uuid4())
    st.session_state.chats[new_id] = {"title": "New Chat", "messages": []}
    st.session_state.active_chat = new_id
    save_chats_to_backend()


def delete_chat(chat_id):
    del st.session_state.chats[chat_id]
    if not st.session_state.chats:
        new_chat()
    elif st.session_state.active_chat == chat_id:
        st.session_state.active_chat = list(st.session_state.chats.keys())[0]
    save_chats_to_backend()


def export_chat_markdown(chat):
    lines = [f"# {chat['title']}\n"]
    for m in chat["messages"]:
        who = "**You:**" if m["role"] == "user" else "**RAGent:**"
        lines.append(f"{who} {m['content']}\n")
        if m.get("sources"):
            srcs = ", ".join(f"{s['source']} (p.{s['page']})" for s in m["sources"])
            lines.append(f"*Sources: {srcs}*\n")
    return "\n".join(lines)


def copy_button(text: str, key: str):
    """Renders a small 'Copy' button that copies `text` to the clipboard via JS."""
    safe_text = json.dumps(text)  # safely escape for embedding in JS
    st.components.v1.html(f"""
        <button onclick='navigator.clipboard.writeText({safe_text})'
                style="padding:4px 10px;font-size:12px;border-radius:6px;border:1px solid #666;
                       background:transparent;color:inherit;cursor:pointer;">
            📋 Copy
        </button>
    """, height=32)


def get_sources_list():
    try:
        res = requests.get(f"{API_URL}/sources", params={"user": USER}, timeout=5)
        if res.status_code == 200:
            return res.json()["sources"]
    except Exception:
        pass
    return []


# ---------------- Sidebar ----------------
with st.sidebar:
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
            <span style="font-size:22px;">🤖</span>
            <span style="font-size:20px;font-weight:700;">RAGent</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("➕ New chat", use_container_width=True, type="primary"):
        new_chat()
        st.rerun()

    st.markdown("#### Chats")
    for chat_id, chat in list(st.session_state.chats.items())[::-1]:
        label = chat["title"] if chat["title"] else "New Chat"
        is_active = chat_id == st.session_state.active_chat
        c1, c2 = st.columns([5, 1])
        with c1:
            if st.button(("🟢 " if is_active else "💬 ") + label, key=f"chat_{chat_id}", use_container_width=True):
                st.session_state.active_chat = chat_id
                st.rerun()
        with c2:
            if st.button("🗑️", key=f"del_{chat_id}"):
                delete_chat(chat_id)
                st.rerun()

    with st.expander("✏️ Rename current chat"):
        active = st.session_state.chats[st.session_state.active_chat]
        new_title = st.text_input("Title", value=active["title"], key="rename_input")
        if st.button("Save title", use_container_width=True):
            active["title"] = new_title
            save_chats_to_backend()
            st.rerun()

    st.divider()
    st.markdown("### 📄 Knowledge Base")

    if not backend_is_up():
        st.error("⚠️ Backend not reachable.")

    with st.expander("⚙️ Retrieval settings"):
        chunk_size = st.slider("Chunk size (words)", 100, 500, 250, step=25)
        chunk_overlap = st.slider("Chunk overlap (words)", 0, 150, 40, step=10)
        use_rerank = st.checkbox("Use re-ranking (more accurate, slightly slower)", value=True)
        use_query_expansion = st.checkbox("Use query expansion (extra API call, better recall)", value=False)

    tab_pdf, tab_text = st.tabs(["Upload Files", "Paste Text"])

    with tab_pdf:
        uploaded_files = st.file_uploader(
            "Upload PDF / DOCX / TXT / CSV",
            type=["pdf", "docx", "txt", "csv"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
        if uploaded_files and st.button("Add Files", use_container_width=True):
            with st.spinner(f"Processing {len(uploaded_files)} file(s)..."):
                files_payload = [("files", (f.name, f.getvalue())) for f in uploaded_files]
                try:
                    res = requests.post(
                        f"{API_URL}/upload",
                        files=files_payload,
                        data={"user": USER, "chunk_size": chunk_size, "chunk_overlap": chunk_overlap},
                        timeout=120,
                    )
                    if res.status_code == 200:
                        for r in res.json()["results"]:
                            if "error" in r:
                                st.error(f"{r['filename']}: {r['error']}")
                            else:
                                st.success(f"Added {r['chunks_added']} chunks from {r['filename']}")
                                st.session_state.docs_uploaded.append(r["filename"])
                    else:
                        st.error(f"Upload failed: {res.text}")
                except Exception as e:
                    st.error(f"Upload failed: {e}")

    with tab_text:
        text_title = st.text_input("Title for this text", placeholder="e.g. Lecture Notes Unit 3")
        pasted_text = st.text_area("Paste your text here", height=150)
        if st.button("Add Text", use_container_width=True):
            if not pasted_text.strip():
                st.warning("Paste some text first.")
            else:
                with st.spinner("Adding text..."):
                    try:
                        res = requests.post(
                            f"{API_URL}/add_text",
                            data={
                                "user": USER, "title": text_title or "Pasted Text", "text": pasted_text,
                                "chunk_size": chunk_size, "chunk_overlap": chunk_overlap,
                            },
                            timeout=60,
                        )
                        if res.status_code == 200:
                            data = res.json()
                            st.success(f"Added {data['chunks_added']} chunks from '{data['filename']}'")
                            st.session_state.docs_uploaded.append(data["filename"])
                        else:
                            st.error(f"Failed: {res.text}")
                    except Exception as e:
                        st.error(f"Failed: {e}")

    sources_list = get_sources_list()
    if sources_list:
        st.markdown("**Loaded sources:**")
        for name in sources_list:
            st.markdown(f"- {name}")

        with st.expander("📝 Document tools"):
            tool_source = st.selectbox("Choose a document", sources_list, key="tool_source")
            if st.button("Summarize", use_container_width=True):
                with st.spinner("Summarizing..."):
                    try:
                        res = requests.post(f"{API_URL}/summarize", data={"user": USER, "source": tool_source}, timeout=60)
                        if res.status_code == 200:
                            st.markdown(res.json()["summary"])
                        else:
                            st.error(res.text)
                    except Exception as e:
                        st.error(str(e))

            if st.button("🧩 Generate Quiz (5 Qs)", use_container_width=True):
                with st.spinner("Generating quiz..."):
                    try:
                        res = requests.post(f"{API_URL}/quiz", data={"user": USER, "source": tool_source, "num_questions": 5}, timeout=60)
                        if res.status_code == 200:
                            st.session_state["quiz_data"] = res.json()["questions"]
                        else:
                            st.error(res.text)
                    except Exception as e:
                        st.error(str(e))

        if st.button("🗑️ Clear all documents", use_container_width=True):
            try:
                requests.post(f"{API_URL}/clear_docs", data={"user": USER}, timeout=10)
                st.session_state.docs_uploaded = []
                st.success("Knowledge base cleared.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to clear: {e}")

    st.divider()
    st.caption("Powered by Gemini · Hybrid RAG + Chat")

    # ---- Profile section (bottom of sidebar, ChatGPT-style) ----
    st.divider()
    initial = USER[0].upper() if USER else "?"
    with st.popover(f"🔵 {initial}   {USER}", use_container_width=True):
        st.markdown(f"**{USER}**")
        st.caption(f"🔢 Tokens used this session: {st.session_state.session_tokens}")
        st.divider()

        theme_label = "☀️ Switch to Light mode" if st.session_state.theme == "dark" else "🌙 Switch to Dark mode"
        if st.button(theme_label, use_container_width=True):
            st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
            st.rerun()

        if st.button("🚪 Log out", use_container_width=True):
            st.session_state.authed = False
            st.session_state.username = None
            st.session_state.pop("chats", None)
            st.rerun()

# ---------------- Main tabs ----------------
main_tab, eval_tab = st.tabs(["💬 Chat", "📊 Evaluation Dashboard"])

with main_tab:
    active_chat = st.session_state.chats[st.session_state.active_chat]

    header_l, header_m, header_r = st.columns([4, 2, 1])
    with header_l:
        st.markdown(f"<h2 style='margin-bottom:0;'>{active_chat['title']}</h2>", unsafe_allow_html=True)
        st.caption("Ask about your documents, or just chat normally — RAGent handles both.")
    with header_m:
        source_options = ["All documents"] + get_sources_list()
        source_filter = st.selectbox("Scope to document", source_options, label_visibility="collapsed")
    with header_r:
        md = export_chat_markdown(active_chat)
        st.download_button("⬇️ Export", md, file_name=f"{active_chat['title']}.md", use_container_width=True)

    st.divider()

    for idx, msg in enumerate(active_chat["messages"]):
        avatar = "🧑" if msg["role"] == "user" else "🤖"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])
            if msg.get("from_cache"):
                st.caption(f"⚡ Served from cache (similarity {msg.get('cache_similarity', 0):.2f}) — instant, no API call used")
            if msg.get("confidence") and msg["confidence"] != "N/A":
                badge_color = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(msg["confidence"], "")
                st.caption(f"{badge_color} Confidence: {msg['confidence']}")
            if msg.get("faithfulness"):
                st.caption(msg["faithfulness"])
            if msg["role"] == "assistant":
                copy_button(msg["content"], key=f"copy_{idx}")
            if msg.get("sources"):
                with st.expander("📎 Sources"):
                    for s in msg["sources"]:
                        col_a, col_b = st.columns([4, 1])
                        with col_a:
                            st.markdown(f"- **{s['source']}**, Page {s['page']}")
                        with col_b:
                            if s["source"].lower().endswith(".pdf"):
                                if st.button("👁️ Preview", key=f"prev_{idx}_{s['source']}_{s['page']}"):
                                    try:
                                        res = requests.get(f"{API_URL}/preview_source", params={
                                            "user": USER, "source": s["source"], "page": s["page"],
                                            "highlight": msg["content"][:100],
                                        }, timeout=30)
                                        if res.status_code == 200:
                                            img_b64 = res.json()["image_base64"]
                                            st.image(base64.b64decode(img_b64))
                                        else:
                                            st.error(res.json().get("detail", "Preview failed."))
                                    except Exception as e:
                                        st.error(str(e))
            if msg.get("role") == "assistant" and msg.get("followups"):
                st.caption("Follow-up ideas:")
                fcols = st.columns(len(msg["followups"]))
                for fi, followup in enumerate(msg["followups"]):
                    with fcols[fi]:
                        if st.button(followup, key=f"fu_{idx}_{fi}"):
                            st.session_state["pending_question"] = followup
                            st.rerun()
            if msg.get("role") == "assistant":
                fb_col1, fb_col2, _ = st.columns([1, 1, 8])
                with fb_col1:
                    if st.button("👍", key=f"up_{idx}"):
                        try:
                            requests.post(f"{API_URL}/feedback", data={
                                "user": USER, "question": active_chat["messages"][idx-1]["content"] if idx > 0 else "",
                                "answer": msg["content"], "rating": "up"}, timeout=10)
                            st.toast("Thanks for the feedback!")
                        except Exception:
                            pass
                with fb_col2:
                    if st.button("👎", key=f"down_{idx}"):
                        try:
                            requests.post(f"{API_URL}/feedback", data={
                                "user": USER, "question": active_chat["messages"][idx-1]["content"] if idx > 0 else "",
                                "answer": msg["content"], "rating": "down"}, timeout=10)
                            st.toast("Thanks — we'll use this to improve.")
                        except Exception:
                            pass

    with st.expander("⚖️ RAG vs. No-RAG Comparison"):
        st.caption("See exactly what your documents add — the same question answered with and without them.")
        compare_q = st.text_input("Question to compare", key="compare_question")
        if st.button("Run Comparison", use_container_width=True):
            if not compare_q.strip():
                st.warning("Type a question first.")
            else:
                with st.spinner("Running both versions..."):
                    try:
                        res = requests.post(f"{API_URL}/compare", data={"user": USER, "question": compare_q}, timeout=60)
                        if res.status_code == 200:
                            data = res.json()
                            col_rag, col_norag = st.columns(2)
                            with col_rag:
                                st.markdown("**🟢 With RAG (your documents)**")
                                st.info(data["with_rag"]["answer"])
                                if data["with_rag"].get("sources"):
                                    srcs = ", ".join(f"{s['source']} (p.{s['page']})" for s in data["with_rag"]["sources"])
                                    st.caption(f"Sources: {srcs}")
                            with col_norag:
                                st.markdown("**⚪ Without RAG (general knowledge only)**")
                                st.warning(data["without_rag"]["answer"])
                        else:
                            st.error(res.text)
                    except Exception as e:
                        st.error(str(e))

    # ---- Quick-action icon row, right above the input (attach + mic) ----
    icon_col1, icon_col2, spacer = st.columns([1, 1, 10])

    with icon_col1:
        with st.popover("➕", help="Attach a document"):
            st.markdown("**Add a document to this chat's knowledge base**")
            quick_file = st.file_uploader(
                "Upload", type=["pdf", "docx", "txt", "csv"],
                label_visibility="collapsed", key="quick_attach_uploader",
            )
            if quick_file and st.button("Upload & analyze", use_container_width=True, key="quick_attach_btn"):
                with st.spinner(f"Processing {quick_file.name}..."):
                    try:
                        res = requests.post(
                            f"{API_URL}/upload",
                            files=[("files", (quick_file.name, quick_file.getvalue()))],
                            data={"user": USER, "chunk_size": 250, "chunk_overlap": 40},
                            timeout=120,
                        )
                        if res.status_code == 200:
                            for r in res.json()["results"]:
                                if "error" in r:
                                    st.error(f"{r['filename']}: {r['error']}")
                                else:
                                    st.success(f"Added {r['chunks_added']} chunks from {r['filename']}")
                                    st.session_state.docs_uploaded.append(r["filename"])
                                    st.session_state["pending_question"] = (
                                        f"I just uploaded {r['filename']}. Please analyze it and summarize the key points."
                                    )
                                    st.rerun()
                        else:
                            st.error(f"Upload failed: {res.text}")
                    except Exception as e:
                        st.error(f"Upload failed: {e}")

    with icon_col2:
        with st.popover("🎤", help="Voice input"):
            st.markdown("**Speak your question**")
            st.caption("Chrome recommended. Click Start, speak, then copy the result into the chat box below.")
            st.components.v1.html("""
                <div style="font-family: sans-serif;">
                  <button id="micBtn" style="padding:8px 14px;border-radius:8px;border:none;background:#444;color:white;cursor:pointer;">🎤 Start</button>
                  <p id="micOutput" style="margin-top:8px;padding:8px;border:1px solid #666;border-radius:6px;min-height:40px;color:white;background:#222;"></p>
                  <button id="copyBtn" style="padding:6px 12px;font-size:12px;border-radius:6px;border:1px solid #666;background:transparent;color:white;cursor:pointer;">📋 Copy text</button>
                  <script>
                    const btn = document.getElementById('micBtn');
                    const out = document.getElementById('micOutput');
                    const copyBtn = document.getElementById('copyBtn');
                    let recognizing = false;
                    let recognition;
                    if ('webkitSpeechRecognition' in window) {
                      recognition = new webkitSpeechRecognition();
                      recognition.continuous = false;
                      recognition.interimResults = false;
                      recognition.lang = 'en-US';
                      recognition.onresult = (e) => { out.innerText = e.results[0][0].transcript; };
                      recognition.onend = () => { recognizing = false; btn.innerText = '🎤 Start'; };
                      btn.onclick = () => {
                        if (!recognizing) { recognition.start(); recognizing = true; btn.innerText = '⏹️ Stop'; }
                        else { recognition.stop(); }
                      };
                      copyBtn.onclick = () => { navigator.clipboard.writeText(out.innerText); };
                    } else {
                      out.innerText = 'Speech recognition not supported in this browser. Try Chrome.';
                      btn.disabled = true;
                    }
                  </script>
                </div>
            """, height=140)

    question = st.chat_input("Ask anything, or ask about your uploaded documents...")
    if "pending_question" in st.session_state:
        question = st.session_state.pop("pending_question")

    # Starting a brand new question: kick off caching check, then either
    # show a cached answer immediately or start a background stream.
    if question and "active_stream" not in st.session_state:
        active_chat["messages"].append({"role": "user", "content": question})
        if active_chat["title"] == "New Chat":
            active_chat["title"] = question[:40] + ("..." if len(question) > 40 else "")

        history_payload = [
            {"role": m["role"], "content": m["content"]}
            for m in active_chat["messages"][:-1]
        ]

        cache_hit = None
        if not history_payload:
            try:
                cache_res = requests.post(f"{API_URL}/check_cache", data={"user": USER, "question": question}, timeout=10)
                if cache_res.status_code == 200 and cache_res.json().get("hit"):
                    cache_hit = cache_res.json()
            except Exception:
                pass

        if cache_hit:
            active_chat["messages"].append({
                "role": "assistant", "content": cache_hit["answer"], "sources": cache_hit.get("sources", []),
                "confidence": cache_hit.get("confidence", "N/A"), "followups": [], "from_cache": True,
                "cache_similarity": cache_hit.get("cache_similarity", 0),
            })
            save_chats_to_backend()
            st.rerun()
        else:
            handle = start_stream(f"{API_URL}/ask_stream", {
                "user": USER, "question": question, "top_k": 4,
                "history": json.dumps(history_payload),
                "use_rerank": use_rerank,
                "use_query_expansion": use_query_expansion,
                "source_filter": source_filter,
            })
            st.session_state.active_stream = {
                "handle": handle, "question": question, "history_payload": history_payload,
                "accumulated": "",
            }
            st.rerun()

    # Actively polling an in-progress stream
    if "active_stream" in st.session_state:
        stream_info = st.session_state.active_stream
        handle = stream_info["handle"]

        with st.chat_message("assistant", avatar="🤖"):
            new_text = drain_queue(handle)
            stream_info["accumulated"] += new_text
            full_answer = stream_info["accumulated"]
            display_text = full_answer.split("[[META]]")[0]

            if not handle.done:
                st.markdown(display_text + "▌")
                if st.button("⏹️ Stop generating", key="stop_gen_btn"):
                    handle.request_stop()
                time.sleep(0.1)
                st.rerun()
            else:
                # drain anything left, then finalize
                final_drain = drain_queue(handle)
                full_answer += final_drain
                display_text = full_answer.split("[[META]]")[0]

                sources, confidence, tokens_used, retrieved = [], "N/A", 0, []
                if "[[META]]" in full_answer:
                    _, meta_json = full_answer.split("[[META]]", 1)
                    try:
                        meta = json.loads(meta_json)
                        sources = meta.get("sources", [])
                        confidence = meta.get("confidence", "N/A")
                        tokens_used = meta.get("tokens", 0)
                        retrieved = meta.get("retrieved", [])
                    except Exception:
                        pass

                st.markdown(display_text)
                st.session_state.session_tokens += tokens_used

                if confidence != "N/A":
                    badge_color = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(confidence, "")
                    st.caption(f"{badge_color} Confidence: {confidence}")

                if sources:
                    with st.expander("📎 Sources"):
                        for s in sources:
                            st.markdown(f"- **{s['source']}**, Page {s['page']}")

                # Faithfulness / groundedness check (only meaningful if RAG chunks were used)
                faithfulness_note = None
                if retrieved and "⚠️" not in display_text and "stopped by user" not in display_text:
                    try:
                        fc_res = requests.post(f"{API_URL}/check_faithfulness", data={
                            "question": stream_info["question"], "answer": display_text,
                            "retrieved": json.dumps(retrieved),
                        }, timeout=20)
                        if fc_res.status_code == 200:
                            fc = fc_res.json()
                            if fc.get("checked"):
                                icon = {"True": "✅", "False": "⚠️", "partial": "🟡"}.get(str(fc["faithful"]), "❔")
                                label = {"True": "Grounded in your documents", "False": "Not well supported by your documents",
                                          "partial": "Partially supported"}.get(str(fc["faithful"]), "Unclear")
                                faithfulness_note = f"{icon} {label} — {fc.get('explanation', '')}"
                    except Exception:
                        pass
                if faithfulness_note:
                    st.caption(faithfulness_note)

                # Cache this fresh answer (only if no history, no error, wasn't stopped early)
                if (not stream_info["history_payload"] and "⚠️" not in display_text
                        and "stopped by user" not in display_text):
                    try:
                        requests.post(f"{API_URL}/store_cache", data={
                            "user": USER, "question": stream_info["question"], "answer": display_text,
                            "sources": json.dumps(sources), "confidence": confidence,
                        }, timeout=10)
                    except Exception:
                        pass

                followups = []
                if "stopped by user" not in display_text:
                    try:
                        fu_res = requests.post(f"{API_URL}/followups", data={
                            "question": stream_info["question"], "answer": display_text}, timeout=20)
                        if fu_res.status_code == 200:
                            followups = fu_res.json().get("suggestions", [])
                    except Exception:
                        pass

                active_chat["messages"].append({
                    "role": "assistant", "content": display_text, "sources": sources,
                    "confidence": confidence, "followups": followups, "from_cache": False,
                    "faithfulness": faithfulness_note,
                })
                save_chats_to_backend()
                del st.session_state.active_stream
                st.rerun()


    if st.session_state.get("quiz_data"):
        st.divider()
        st.markdown("### 🧩 Quiz")
        for qi, q in enumerate(st.session_state["quiz_data"]):
            st.markdown(f"**{qi+1}. {q['question']}**")
            choice = st.radio("Choose one:", q["options"], key=f"quiz_{qi}", label_visibility="collapsed")
            if st.button("Check", key=f"quizcheck_{qi}"):
                correct = q["options"][q["correct_index"]]
                if choice == correct:
                    st.success(f"Correct! {q.get('explanation', '')}")
                else:
                    st.error(f"Not quite — correct answer: {correct}. {q.get('explanation', '')}")
        if st.button("Close quiz"):
            del st.session_state["quiz_data"]
            st.rerun()

with eval_tab:
    st.markdown("### 📊 Retrieval Evaluation")
    st.caption("Test how well RAGent retrieves the right content for known questions.")

    if "eval_cases" not in st.session_state:
        st.session_state.eval_cases = [{"question": "", "expected_keyword": ""}]

    for i, case in enumerate(st.session_state.eval_cases):
        c1, c2, c3 = st.columns([3, 2, 1])
        with c1:
            case["question"] = st.text_input(f"Question {i+1}", value=case["question"], key=f"eq_{i}")
        with c2:
            case["expected_keyword"] = st.text_input("Expected keyword", value=case["expected_keyword"], key=f"ek_{i}")
        with c3:
            if st.button("Remove", key=f"rm_{i}") and len(st.session_state.eval_cases) > 1:
                st.session_state.eval_cases.pop(i)
                st.rerun()

    if st.button("+ Add test case"):
        st.session_state.eval_cases.append({"question": "", "expected_keyword": ""})
        st.rerun()

    if st.button("▶️ Run Evaluation", type="primary"):
        valid_cases = [c for c in st.session_state.eval_cases if c["question"].strip() and c["expected_keyword"].strip()]
        if not valid_cases:
            st.warning("Add at least one question + expected keyword.")
        else:
            with st.spinner("Running evaluation..."):
                try:
                    res = requests.post(f"{API_URL}/eval", data={"user": USER, "test_set": json.dumps(valid_cases)}, timeout=60)
                    if res.status_code == 200:
                        data = res.json()
                        st.metric("Retrieval Accuracy", f"{data['accuracy']}%", f"{data['hits']}/{data['total']} hits")
                        for r in data["results"]:
                            icon = "✅" if r["hit"] else "❌"
                            st.markdown(f"{icon} **{r['question']}** — expected `{r['expected_keyword']}` — top source: {r['top_source']}")
                    else:
                        st.error(f"Evaluation failed: {res.text}")
                except Exception as e:
                    st.error(f"Evaluation failed: {e}")

    st.divider()
    st.markdown("### 📐 Chunking Strategy Comparison")
    st.caption("Re-chunks your uploaded documents at different sizes and measures retrieval "
               "accuracy for each, using the same test cases above. Great evidence for your project report.")

    chunk_size_options = st.multiselect(
        "Chunk sizes to test (words)", [50, 100, 150, 250, 350, 500], default=[100, 250, 500]
    )

    if st.button("▶️ Run Chunking Comparison"):
        valid_cases = [c for c in st.session_state.eval_cases if c["question"].strip() and c["expected_keyword"].strip()]
        if not valid_cases:
            st.warning("Add at least one test case above first.")
        elif not chunk_size_options:
            st.warning("Pick at least one chunk size to test.")
        else:
            with st.spinner("Re-chunking and re-testing at each size... this may take a moment."):
                try:
                    res = requests.post(f"{API_URL}/eval_chunking", data={
                        "user": USER, "test_set": json.dumps(valid_cases),
                        "chunk_sizes": json.dumps(sorted(chunk_size_options)),
                    }, timeout=120)
                    if res.status_code == 200:
                        results = res.json()["results"]
                        best = max(results, key=lambda r: r["accuracy"])
                        st.success(f"Best performing chunk size: **{best['chunk_size']} words** ({best['accuracy']}% accuracy)")
                        for r in results:
                            st.markdown(
                                f"**{r['chunk_size']} words** — {r['accuracy']}% accuracy "
                                f"({r['hits']}/{r['total']} hits, {r['num_chunks_created']} chunks created)"
                            )
                        chart_data = {r["chunk_size"]: r["accuracy"] for r in results}
                        st.bar_chart(chart_data)
                    else:
                        st.error(res.json().get("detail", res.text))
                except Exception as e:
                    st.error(str(e))

    st.divider()
    st.markdown("### 🎯 Re-ranking A/B Comparison")
    st.caption("Tests your uploaded documents with the cross-encoder re-ranker ON vs OFF, "
               "using the same test cases above, to show whether it's actually worth the extra latency.")

    if st.button("▶️ Run Re-rank Comparison"):
        valid_cases = [c for c in st.session_state.eval_cases if c["question"].strip() and c["expected_keyword"].strip()]
        if not valid_cases:
            st.warning("Add at least one test case above first.")
        else:
            with st.spinner("Testing with and without re-ranking..."):
                try:
                    res = requests.post(f"{API_URL}/eval_rerank", data={
                        "user": USER, "test_set": json.dumps(valid_cases),
                    }, timeout=60)
                    if res.status_code == 200:
                        data = res.json()
                        c1, c2 = st.columns(2)
                        with c1:
                            st.metric("With re-ranking", f"{data['with_rerank']['accuracy']}%",
                                      f"{data['with_rerank']['hits']}/{data['with_rerank']['total']} hits")
                        with c2:
                            st.metric("Without re-ranking", f"{data['without_rerank']['accuracy']}%",
                                      f"{data['without_rerank']['hits']}/{data['without_rerank']['total']} hits")
                        diff = data['with_rerank']['accuracy'] - data['without_rerank']['accuracy']
                        if diff > 0:
                            st.success(f"Re-ranking improved accuracy by {diff:.1f} percentage points.")
                        elif diff < 0:
                            st.warning(f"Re-ranking performed {abs(diff):.1f} points worse on this test set — try more test cases for a clearer signal.")
                        else:
                            st.info("No difference on this test set — try adding more/harder test cases.")
                    else:
                        st.error(res.json().get("detail", res.text))
                except Exception as e:
                    st.error(str(e))

    st.divider()
    st.markdown("### ⚡ Semantic Cache")
    st.caption("Repeated/similar questions are answered instantly from cache instead of calling Gemini again.")
    if st.button("🗑️ Clear cache for this account"):
        try:
            requests.post(f"{API_URL}/clear_cache", data={"user": USER}, timeout=10)
            st.success("Cache cleared.")
        except Exception as e:
            st.error(str(e))

    st.divider()
    st.markdown("### 👍👎 Feedback Summary")
    try:
        res = requests.get(f"{API_URL}/feedback_summary", params={"user": USER}, timeout=10)
        if res.status_code == 200:
            fb = res.json()
            c1, c2, c3 = st.columns(3)
            c1.metric("👍 Positive", fb["up"])
            c2.metric("👎 Negative", fb["down"])
            c3.metric("Total rated", fb["total"])
    except Exception:
        st.caption("No feedback data yet.")
