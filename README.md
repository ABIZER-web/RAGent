# RAGent 🤖📚
**Your documents. Your answers. Cited and true.**

> A full-featured AI document intelligence assistant built on Retrieval-Augmented Generation (RAG). Upload documents, chat naturally, get accurate answers backed by real citations — with multi-user accounts, streaming responses, semantic caching, and built-in evaluation tools to measure and prove retrieval quality.

---

## 📌 Problem Statement

Students, researchers, and professionals deal with large volumes of documents but face real friction:

- ❌ Manual search (Ctrl+F) only finds exact keywords, not meaning or context
- ❌ General AI chatbots don't know the content of your specific documents
- ❌ Reading through 50–100+ page PDFs to find one answer wastes hours
- ❌ AI answers can't usually be traced back to a verifiable source (hallucination risk)

**RAGent** solves this by combining document retrieval with AI generation — giving accurate, source-grounded answers instead of guesses, and it doesn't stop being useful when your question has nothing to do with your documents either (it just chats normally).

---

## 💡 What RAGent Does

1. **Upload** — Add PDFs, DOCX, TXT, or CSV files, or just paste text directly
2. **Ask** — Ask questions in natural language via a streaming chat interface
3. **Retrieve** — Searches your documents by meaning (embedding similarity), then re-ranks the top candidates with a cross-encoder for accuracy
4. **Generate** — An LLM (Gemini) reads the relevant sections and writes a grounded answer — or, if nothing relevant was found, answers normally like any AI assistant
5. **Verify** — Every answer gets a confidence badge, and a second AI pass can check whether the answer is actually supported by the retrieved text (faithfulness/groundedness check)
6. **Cite** — See exactly which document and page an answer came from, with an optional highlighted PDF preview

---

## 🎯 Target Users

- **Students** — Upload semester notes/textbooks → ask concept questions → get instant, cited explanations, plus auto-generated quizzes to test yourself
- **Researchers** — Upload multiple papers → ask comparative questions across them
- **Anyone** — Any long document (reports, manuals, policies) they need to query quickly

---

## 🏗️ How It Works (RAG Pipeline)

```
User uploads document(s) or pastes text
        ↓
Document Loader → extracts raw text (PDF/DOCX/TXT/CSV)
        ↓
Text Splitter → breaks text into overlapping chunks (adjustable size)
        ↓
Embedding Model → converts each chunk into a vector (Sentence-Transformers, local & free)
        ↓
Vector Store → chunks + vectors persisted per-user on disk
        ↓
User asks a question
        ↓
Check semantic cache → if a near-identical question was answered before, return instantly
        ↓
Embedding search → retrieve a wide candidate pool of relevant chunks
        ↓
Cross-encoder re-ranking → re-score candidates for real relevance, keep the best few
        ↓
Retrieved chunks + question + conversation history → sent to Gemini
        ↓
Gemini streams back a grounded answer (or a normal answer if no chunks were relevant)
        ↓
Answer + citations + confidence badge + optional faithfulness check shown to the user
```

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Language | Python | |
| Backend framework | FastAPI | Async REST API, auto docs, clean validation |
| Frontend framework | Streamlit | Fast to build a real chat UI without hand-rolling JS |
| Document loading | pypdf, python-docx, csv, plain text | No external binary dependencies (Windows-friendly) |
| Embeddings | Sentence-Transformers (`all-MiniLM-L6-v2`) | Local, free, no API cost |
| Re-ranking | Cross-Encoder (`ms-marco-MiniLM-L-6-v2`) | Second-pass accuracy boost over raw embedding similarity |
| Vector storage | Plain NumPy arrays + JSON metadata, per-user | Zero extra infra — no external vector DB needed |
| PDF preview/highlighting | PyMuPDF (fitz) | No poppler/external binary needed, cross-platform |
| LLM | Google Gemini (`gemini-flash-latest`), via the official `google-genai` SDK | Free tier, and the SDK stays in sync with Google's own auth changes |
| Auth | Custom salted-hash accounts (`app/users.py`) | Simple, dependency-free multi-user support |
| Deployment | Render (backend) + Streamlit Community Cloud (frontend) | Both have workable free tiers |

> 🔐 All API keys, credentials, and account details are stored separately in `PRIVATE_README.md` (gitignored — never pushed to GitHub). See `.env.example` for the variables you need to set yourself.

---

## 📂 Project Structure

```
RAGent/
├── README.md                  # This file
├── PRIVATE_README.md          # Your real credentials (gitignored, not in repo)
├── DEPLOYMENT.md              # Step-by-step free hosting guide
├── PHASES.md                  # Development roadmap / phases
├── .env.example                # Safe template for environment variables
├── .gitignore
├── render.yaml                 # Render deployment blueprint
├── runtime.txt                 # Pinned Python version for Render
├── requirements.txt            # Backend dependencies
├── test_gemini_key.py          # Standalone script to test your Gemini key
│
├── app/                         # FastAPI backend
│   ├── main.py                   # All API endpoints
│   ├── ingestion.py               # Document loading + text chunking
│   ├── embeddings.py              # Embedding model + per-user vector store
│   ├── retriever.py                # Two-stage retrieval (embed + rerank)
│   ├── reranker.py                  # Cross-encoder re-ranking
│   ├── generator.py                  # Gemini calls: chat, summarize, quiz, faithfulness, etc.
│   ├── cache.py                       # Semantic caching for repeated questions
│   ├── chunk_eval.py                   # Chunking-strategy & rerank A/B comparison tools
│   ├── users.py                         # Account creation/login (salted hashes)
│   ├── feedback.py                       # Thumbs up/down logging
│   ├── pdf_preview.py                     # Highlighted PDF page rendering
│   └── rate_limiter.py                     # Per-user rate limiting
│
├── frontend/                    # Streamlit chat app
│   ├── streamlit_app.py           # Full UI: chat, sidebar, eval dashboard, etc.
│   ├── stream_client.py            # Threaded streaming client (enables Stop button)
│   └── requirements.txt             # Lightweight deps for Streamlit Cloud
│
├── data/                         # Local runtime data (gitignored)
│   ├── uploaded_docs/<user>/        # Raw uploaded files, per user
│   ├── users.json                    # Account credentials (hashed)
│   ├── chats_<user>.json              # Saved chat sessions
│   ├── cache/                          # Semantic cache
│   └── feedback/                        # Feedback logs
│
└── vectorstore/<user>/            # Per-user embedding vectors + metadata (gitignored)
```

---

## ⚙️ Local Setup

1. Clone the repository
   ```bash
   git clone <your-repo-url>
   cd RAGent
   ```

2. Create a virtual environment and install dependencies
   ```bash
   python -m venv venv
   source venv/bin/activate      # Windows: .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. Set up environment variables
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` and fill in:
   - `GEMINI_API_KEY` — get a free one at aistudio.google.com → "Get API key"
   - `APP_USERNAME` / `APP_PASSWORD` — your admin login (change from the defaults!)

   Quick sanity check before running the full app:
   ```bash
   python test_gemini_key.py
   ```

4. Run the backend (Terminal 1)
   ```bash
   uvicorn app.main:app --reload
   ```

5. Run the frontend (Terminal 2)
   ```bash
   streamlit run frontend/streamlit_app.py
   ```

6. Open the app, log in (or create an account), upload a document, and start chatting.

---

## 🚀 Deployment

Ready to put this on the internet? See **[DEPLOYMENT.md](DEPLOYMENT.md)** for the
full free-hosting walkthrough — Render for the backend, Streamlit Community
Cloud for the frontend, including environment variable setup, CORS locking,
and a troubleshooting table.

---

## ✨ Key Features

**Core RAG**
- 📄 Multi-file upload: PDF, DOCX, TXT, CSV — all at once
- ✍️ Add knowledge by pasting text directly, no file needed
- 🔍 Two-stage retrieval: embedding search + cross-encoder re-ranking
- 🧭 Optional query expansion — rephrases your question to improve recall
- 🎯 Scope questions to a single document via a dropdown filter
- 🤖 Hybrid chat — uses your documents when relevant, answers normally otherwise
- 👁️ Full transparency — see exactly which chunks were retrieved, with PDF preview + highlighting

**Chat experience**
- ⚡ Streaming answers with a live "thinking" indicator
- ⏹️ Genuine stop-generation button (built on a background thread + queue)
- 💬 Multiple chats, sidebar history — new / rename / delete, persisted to disk
- 🧠 Full multi-turn conversation memory per chat
- ➕ Attach documents and 🎤 voice input directly from the chat bar
- 📋 Copy-to-clipboard, ⬇️ export any chat as Markdown

**Trust & accuracy tooling**
- 🟢🟡🔴 Confidence badges on every answer
- ✅ Answer faithfulness check — a second AI pass verifies groundedness
- ⚖️ RAG vs. no-RAG comparison — see exactly what your documents add
- 📐 Chunking-strategy comparison — test multiple chunk sizes, see which retrieves best
- 🎯 Re-ranking A/B comparison — proves the cross-encoder step is worth it
- 📊 Evaluation dashboard — run your own test Q&A sets against retrieval

**Productivity extras**
- 📝 One-click document summarizer
- 🧩 Auto-generated multiple-choice quiz from any document
- 💡 Suggested follow-up questions after every answer
- 👍👎 Feedback logging + summary dashboard
- ⚡ Semantic caching — near-duplicate questions answered instantly, no extra API call

**Accounts & platform**
- 👤 Multi-user accounts, each with a fully separate private knowledge base
- 🚦 Per-user rate limiting to stay within Gemini's free tier
- 🌗 Dark/light theme toggle
- 🔢 Token usage tracker

---

## 🧪 Testing

This project was built with backend logic tested at every stage — not just
written and hoped to work. If you want to verify the backend yourself:

```bash
# Quick check that your Gemini key actually works
python test_gemini_key.py
```

The API also exposes interactive docs once running — visit
`http://localhost:8000/docs` (FastAPI's auto-generated Swagger UI) to try
every endpoint manually.

---

## 🚀 Possible Future Improvements

- Persistent storage on a real database (currently local files — fine for a
  demo, but a paid host/database would be needed for production-grade persistence)
- Multi-document synthesis (answering questions that span several documents with separate citations)
- Hybrid keyword + semantic search (catches exact terms/acronyms embeddings sometimes miss)
- Message editing / regenerate response
- Bulk quiz export as a printable file

---

## 📄 License

Developed for academic purposes as part of the BE (IT) Major Project — Sem VII, 2026.
