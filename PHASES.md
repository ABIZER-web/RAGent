# RAGent — Development Phases

A 7-phase roadmap from setup to deployment. Use this for your project timeline / Gantt chart in the report.

---

## Phase 1 — Setup & Document Ingestion (Week 1)
**Goal:** Get raw PDFs into clean, structured text.

- Set up Python environment, folder structure, GitHub repo
- Build PDF loader (extract text page-by-page)
- Split text into overlapping chunks (so context isn't lost at boundaries)

**Files:** `app/ingestion.py`
**Deliverable:** Upload a PDF → get back a list of clean text chunks with page numbers attached

---

## Phase 2 — Embeddings & Vector Store (Week 2)
**Goal:** Turn text chunks into searchable vectors.

- Convert each chunk into a vector using a Sentence-Transformers model
- Store vectors + metadata (source file, page number) in ChromaDB
- Test similarity search manually (query → nearest chunks)

**Files:** `app/embeddings.py`, `vectorstore/`
**Deliverable:** A working local vector database you can query and get relevant chunks back

---

## Phase 3 — Retrieval + LLM Answer Generation (Week 3)
**Goal:** The actual "RAG" — this is your core innovation.

- Given a question, retrieve top-k relevant chunks from ChromaDB
- Build a prompt: question + retrieved chunks + instructions ("answer only from context, cite sources")
- Send to LLM (Claude/OpenAI/Groq) and get grounded answer back
- Attach citation (filename + page number) to the answer

**Files:** `app/retriever.py`, `app/generator.py`
**Deliverable:** Ask a question in terminal → get a cited, accurate answer

---

## Phase 4 — Backend API (Week 4)
**Goal:** Wrap the RAG pipeline in a proper API so a frontend can use it.

- Build FastAPI endpoints: `/upload` (add documents), `/ask` (query)
- Handle multiple documents per session
- Add error handling (bad file, empty query, no docs uploaded yet)

**Files:** `app/main.py`
**Deliverable:** A running API you can test with Postman/curl

---

## Phase 5 — Frontend Website (Week 5)
**Goal:** A usable website — this is what people will actually see/demo.

- Build Streamlit chat interface: upload box + chat window
- Show source citations under each answer
- Add chat history within a session
- Basic styling / branding (RAGent logo, tagline, colors)

**Files:** `frontend/streamlit_app.py`
**Deliverable:** A working website — upload a PDF, chat with it, see the answer live

---

## Phase 6 — Testing & Polish (Week 6)
**Goal:** Make it demo-ready and reliable.

- Test with different document types (scanned vs text PDFs, long vs short docs)
- Improve chunk size / retrieval accuracy (tune parameters)
- Handle edge cases: irrelevant question, empty PDF, huge PDF
- Add loading indicators, clean error messages
- Write test questions + expected answers for your demo/viva

**Deliverable:** A bug-free, smooth demo flow

---

## Phase 7 — Deployment (Week 7)
**Goal:** Make it accessible via a public link.

- Deploy backend (Render / Railway free tier)
- Deploy frontend (Streamlit Community Cloud)
- Connect both, test end-to-end on the live link
- Add live link + screenshots to README and final report

**Deliverable:** A live, shareable URL for your RAGent website

---

## Timeline Summary

| Phase | Focus | Week |
|---|---|---|
| 1 | Document Ingestion | 1 |
| 2 | Embeddings & Vector Store | 2 |
| 3 | Retrieval + LLM Generation | 3 |
| 4 | Backend API | 4 |
| 5 | Frontend Website | 5 |
| 6 | Testing & Polish | 6 |
| 7 | Deployment | 7 |

> Adjust week numbers based on your actual project deadline — phases 1–3 are the technical core (prioritize these), phases 5–7 make it presentable and demoable.
