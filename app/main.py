"""
PHASE 4 — Backend API
Endpoints (all namespaced per-user via a `user` form field):
  /register, /login          — account management
  /upload, /add_text         — knowledge base building
  /ask, /ask_stream          — chat (hybrid RAG + general), streaming variant
  /clear_docs, /sources      — knowledge base management
  /save_chats, /load_chats   — chat persistence
  /eval                      — retrieval accuracy testing
  /summarize, /quiz          — document tools
  /followups                 — suggested next questions
  /feedback                  — thumbs up/down logging
  /preview_source            — highlighted PDF page image
"""

import os
import json
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.ingestion import chunk_document, split_text, LOADERS
from app.embeddings import (
    add_chunks_to_store, has_documents, clear_store, list_sources, query_store, embed_text,
)
from app.retriever import retrieve_relevant_chunks
from app.generator import (
    generate_answer, generate_answer_stream, expand_query,
    summarize_text, generate_quiz, suggest_followups, generate_comparison,
    check_faithfulness,
)
from app.rate_limiter import check_rate_limit
from app.users import create_user, verify_user
from app.feedback import log_feedback, get_feedback_summary
from app.pdf_preview import render_highlighted_page
from app import cache as semantic_cache
from app.chunk_eval import compare_chunking_strategies, compare_rerank_on_off

app = FastAPI(title="RAGent API")

# In production, set ALLOWED_ORIGINS to your Streamlit Cloud URL
# (comma-separated if multiple), e.g. "https://your-app.streamlit.app".
# Defaults to "*" (allow all) which is fine for a demo/personal deployment.
_allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "*")
allowed_origins = [o.strip() for o in _allowed_origins_env.split(",")] if _allowed_origins_env != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

SUPPORTED_EXTENSIONS = set(LOADERS.keys())


def upload_dir_for(user_id: str) -> str:
    path = os.path.join(DATA_DIR, "uploaded_docs", user_id)
    os.makedirs(path, exist_ok=True)
    return path


def chats_path_for(user_id: str) -> str:
    return os.path.join(DATA_DIR, f"chats_{user_id}.json")


# ---------------- RAG vs no-RAG comparison ----------------
@app.post("/compare")
async def compare(
    user: str = Form(...),
    question: str = Form(...),
    top_k: int = Form(4),
    use_rerank: bool = Form(True),
):
    if not question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    allowed, message = check_rate_limit(user)
    if not allowed:
        raise HTTPException(status_code=429, detail=message)

    chunks = (
        retrieve_relevant_chunks(user, question, top_k=top_k, use_rerank=use_rerank)
        if has_documents(user) else []
    )
    return generate_comparison(question, chunks)


# ---------------- Chunking strategy comparison ----------------
@app.post("/eval_chunking")
async def eval_chunking(user: str = Form(...), test_set: str = Form(...), chunk_sizes: str = Form("[100,250,500]")):
    try:
        cases = json.loads(test_set)
        sizes = json.loads(chunk_sizes)
    except Exception:
        raise HTTPException(status_code=400, detail="test_set/chunk_sizes must be valid JSON.")

    upload_dir = upload_dir_for(user)
    result = compare_chunking_strategies(upload_dir, cases, chunk_sizes=sizes)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/eval_rerank")
async def eval_rerank(user: str = Form(...), test_set: str = Form(...)):
    try:
        cases = json.loads(test_set)
    except Exception:
        raise HTTPException(status_code=400, detail="test_set must be valid JSON.")
    if not has_documents(user):
        raise HTTPException(status_code=400, detail="Upload at least one document first.")

    return compare_rerank_on_off(user, cases)


# ---------------- Semantic cache management ----------------
@app.post("/check_cache")
async def check_cache(user: str = Form(...), question: str = Form(...)):
    q_vector = embed_text(question)
    cached = semantic_cache.lookup(user, q_vector)
    if cached:
        return {"hit": True, **cached}
    return {"hit": False}


@app.post("/store_cache")
async def store_cache(user: str = Form(...), question: str = Form(...),
                       answer: str = Form(...), sources: str = Form("[]"),
                       confidence: str = Form("N/A")):
    try:
        parsed_sources = json.loads(sources)
    except Exception:
        parsed_sources = []
    q_vector = embed_text(question)
    semantic_cache.store(user, question, q_vector, answer, parsed_sources, confidence)
    return {"status": "stored"}


@app.post("/clear_cache")
async def clear_cache(user: str = Form(...)):
    semantic_cache.clear(user)
    return {"status": "cleared"}


@app.get("/")
def health_check():
    return {"status": "RAGent API is running"}


# ---------------- Auth ----------------
@app.post("/register")
async def register(username: str = Form(""), password: str = Form("")):
    ok, message = create_user(username, password)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"status": "ok", "message": message}


@app.post("/login")
async def login(username: str = Form(""), password: str = Form("")):
    if not username.strip() or not password.strip():
        raise HTTPException(status_code=400, detail="Username and password cannot be empty.")
    if not verify_user(username, password):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return {"status": "ok"}


# ---------------- Knowledge base ----------------
@app.post("/upload")
async def upload_documents(
    user: str = Form(...),
    files: list[UploadFile] = File(...),
    chunk_size: int = Form(250),
    chunk_overlap: int = Form(40),
):
    results = []
    save_dir = upload_dir_for(user)

    for file in files:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in SUPPORTED_EXTENSIONS:
            results.append({"filename": file.filename, "error": f"Unsupported type {ext}"})
            continue

        save_path = os.path.join(save_dir, file.filename)
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        try:
            chunks = chunk_document(save_path, source_name=file.filename,
                                     chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            if not chunks:
                results.append({"filename": file.filename, "error": "No extractable text found"})
                continue
            added = add_chunks_to_store(user, chunks)
            results.append({"filename": file.filename, "chunks_added": added})
        except Exception as e:
            results.append({"filename": file.filename, "error": str(e)})

    return {"results": results}


@app.post("/add_text")
async def add_text(
    user: str = Form(...),
    title: str = Form(""),
    text: str = Form(""),
    chunk_size: int = Form(250),
    chunk_overlap: int = Form(40),
):
    if not text.strip():
        raise HTTPException(status_code=400, detail="Pasted text cannot be empty.")

    source_name = title.strip() or "Pasted Text"
    pieces = split_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = [{"text": p, "source": source_name, "page": 1} for p in pieces]

    added = add_chunks_to_store(user, chunks)
    return {"filename": source_name, "chunks_added": added}


@app.post("/clear_docs")
async def clear_docs(user: str = Form(...)):
    clear_store(user)
    return {"status": "cleared"}


@app.get("/sources")
async def get_sources(user: str):
    return {"sources": list_sources(user)}


# ---------------- Chat ----------------
@app.post("/ask")
async def ask_question(
    user: str = Form(...),
    question: str = Form(""),
    top_k: int = Form(4),
    history: str = Form("[]"),
    use_rerank: bool = Form(True),
    use_query_expansion: bool = Form(False),
    source_filter: str = Form(None),
    use_cache: bool = Form(True),
):
    if not question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # Only use the semantic cache for fresh questions (no conversation history) —
    # cached answers don't account for multi-turn context.
    if use_cache and history in ("[]", "", None):
        q_vector = embed_text(question)
        cached = semantic_cache.lookup(user, q_vector)
        if cached:
            return {
                "answer": cached["answer"],
                "sources": cached["sources"],
                "confidence": cached["confidence"],
                "tokens": 0,
                "from_cache": True,
                "cache_similarity": cached["cache_similarity"],
            }

    allowed, message = check_rate_limit(user)
    if not allowed:
        raise HTTPException(status_code=429, detail=message)

    try:
        parsed_history = json.loads(history)
    except Exception:
        parsed_history = []

    extra_queries = expand_query(question) if use_query_expansion else None

    chunks = (
        retrieve_relevant_chunks(user, question, top_k=top_k, use_rerank=use_rerank,
                                  source_filter=source_filter, extra_queries=extra_queries)
        if has_documents(user) else []
    )
    result = generate_answer(question, chunks, history=parsed_history)
    result["retrieved"] = chunks
    result["from_cache"] = False

    if use_cache and not parsed_history and "⚠️" not in result["answer"]:
        try:
            q_vector = embed_text(question)
            semantic_cache.store(user, question, q_vector, result["answer"],
                                  result.get("sources", []), result.get("confidence", "N/A"))
        except Exception:
            pass

    return result


@app.post("/ask_stream")
async def ask_question_stream(
    user: str = Form(...),
    question: str = Form(""),
    top_k: int = Form(4),
    history: str = Form("[]"),
    use_rerank: bool = Form(True),
    use_query_expansion: bool = Form(False),
    source_filter: str = Form(None),
):
    if not question.strip():
        def empty_gen():
            yield "⚠️ Question cannot be empty."
        return StreamingResponse(empty_gen(), media_type="text/plain")

    allowed, message = check_rate_limit(user)
    if not allowed:
        def err_gen():
            yield message
        return StreamingResponse(err_gen(), media_type="text/plain")

    try:
        parsed_history = json.loads(history)
    except Exception:
        parsed_history = []

    extra_queries = expand_query(question) if use_query_expansion else None

    chunks = (
        retrieve_relevant_chunks(user, question, top_k=top_k, use_rerank=use_rerank,
                                  source_filter=source_filter, extra_queries=extra_queries)
        if has_documents(user) else []
    )

    def gen():
        for piece in generate_answer_stream(question, chunks, parsed_history):
            yield piece

    return StreamingResponse(gen(), media_type="text/plain")


# ---------------- Chat persistence ----------------
@app.post("/save_chats")
async def save_chats(user: str = Form(...), payload: str = Form(...)):
    with open(chats_path_for(user), "w", encoding="utf-8") as f:
        f.write(payload)
    return {"status": "saved"}


@app.get("/load_chats")
async def load_chats(user: str):
    path = chats_path_for(user)
    if not os.path.exists(path):
        return {"chats": None}
    with open(path, "r", encoding="utf-8") as f:
        return {"chats": json.load(f)}


# ---------------- Evaluation ----------------
@app.post("/eval")
async def evaluate(user: str = Form(...), test_set: str = Form(...)):
    try:
        cases = json.loads(test_set)
    except Exception:
        raise HTTPException(status_code=400, detail="test_set must be valid JSON.")

    results = []
    hits = 0
    for case in cases:
        chunks = retrieve_relevant_chunks(user, case["question"], top_k=4, use_rerank=True)
        combined_text = " ".join(c["text"].lower() for c in chunks)
        hit = case["expected_keyword"].lower() in combined_text
        hits += int(hit)
        results.append({
            "question": case["question"],
            "expected_keyword": case["expected_keyword"],
            "hit": hit,
            "top_source": chunks[0]["source"] if chunks else None,
        })

    accuracy = round((hits / len(cases)) * 100, 1) if cases else 0
    return {"results": results, "accuracy": accuracy, "total": len(cases), "hits": hits}


# ---------------- Document tools ----------------
@app.post("/summarize")
async def summarize(user: str = Form(...), source: str = Form(...)):
    chunks = query_store(user, source, top_k=200, source_filter=source)
    if not chunks:
        raise HTTPException(status_code=404, detail="No content found for that source.")
    full_text = "\n".join(c["text"] for c in chunks)
    summary = summarize_text(full_text, source)
    return {"summary": summary}


@app.post("/quiz")
async def quiz(user: str = Form(...), source: str = Form(...), num_questions: int = Form(5)):
    chunks = query_store(user, source, top_k=200, source_filter=source)
    if not chunks:
        raise HTTPException(status_code=404, detail="No content found for that source.")
    full_text = "\n".join(c["text"] for c in chunks)
    questions = generate_quiz(full_text, source, num_questions=num_questions)
    if not questions:
        raise HTTPException(status_code=500, detail="Could not generate quiz — try again.")
    return {"questions": questions}


@app.post("/followups")
async def followups(question: str = Form(...), answer: str = Form(...)):
    return {"suggestions": suggest_followups(question, answer)}


@app.post("/check_faithfulness")
async def faithfulness(question: str = Form(...), answer: str = Form(...), retrieved: str = Form("[]")):
    try:
        chunks = json.loads(retrieved)
    except Exception:
        chunks = []
    return check_faithfulness(question, answer, chunks)


# ---------------- Feedback ----------------
@app.post("/feedback")
async def feedback(user: str = Form(...), question: str = Form(...),
                    answer: str = Form(...), rating: str = Form(...)):
    if rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="rating must be 'up' or 'down'.")
    count = log_feedback(user, question, answer, rating)
    return {"status": "logged", "total_feedback": count}


@app.get("/feedback_summary")
async def feedback_summary(user: str):
    return get_feedback_summary(user)


# ---------------- PDF preview ----------------
@app.get("/preview_source")
async def preview_source(user: str, source: str, page: int, highlight: str):
    save_dir = upload_dir_for(user)
    pdf_path = os.path.join(save_dir, source)

    if not source.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Preview is only available for PDF sources.")
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Original PDF file not found on server.")

    try:
        image_b64 = render_highlighted_page(pdf_path, page, highlight)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"image_base64": image_b64}
