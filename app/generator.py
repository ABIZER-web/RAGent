"""
PHASE 3 (part 2) — Answer Generation
Hybrid chat (documents when relevant, general chat otherwise), streaming,
plus extra Gemini-powered helpers: summarization, quiz generation,
follow-up suggestions, lightweight query expansion, RAG vs no-RAG
comparison, and answer faithfulness checking.

Uses Google's official `google-genai` SDK instead of hand-rolled REST calls.
Google changed the Gemini API key format in 2026 (new "AQ." Auth keys
replacing "AIza..." Standard keys), and the plain REST endpoint has had
rollout issues with the new format for many developers. The official SDK
is maintained by Google and is the most reliable way to stay compatible
with their own auth changes.
"""

import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-flash-latest"  # alias that always points to the current recommended flash model,
                                 # so this doesn't break again on Google's next model rotation

RELEVANCE_THRESHOLD = 0.35

_client = None


def get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def key_is_valid():
    return bool(GEMINI_API_KEY) and GEMINI_API_KEY != "PASTE_YOUR_REAL_GEMINI_KEY_HERE"


def _relevant(chunks):
    return [c for c in chunks if c.get("score", 1.0) >= RELEVANCE_THRESHOLD]


def confidence_label(chunks: list) -> str:
    if not chunks:
        return "N/A"
    top_score = chunks[0].get("score", 0)
    if top_score >= 0.65:
        return "High"
    elif top_score >= RELEVANCE_THRESHOLD:
        return "Medium"
    return "Low"


def _call_gemini(prompt: str, max_tokens: int = 800) -> str:
    client = get_client()
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(max_output_tokens=max_tokens),
    )
    return response.text or ""


def build_contents(question: str, chunks: list, history: list):
    """Builds a list of google.genai types.Content objects for a chat turn."""
    contents = []
    for turn in (history or [])[-10:]:
        role = "user" if turn["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=turn["content"])]))

    if chunks:
        context_blocks = [
            f"[Source {i}: {c['source']}, Page {c['page']}]\n{c['text']}"
            for i, c in enumerate(chunks, start=1)
        ]
        context = "\n\n".join(context_blocks)
        final_text = f"""You are RAGent, a helpful AI assistant. The user has uploaded documents.
Relevant context was found below — use it if it helps answer the question. If the
context doesn't actually answer the question, just answer normally using your own
knowledge and say the documents didn't cover it.

Context:
{context}

Question: {question}"""
    else:
        final_text = f"""You are RAGent, a helpful, friendly AI assistant. Answer the
user's question directly and clearly using your own knowledge (no document context
was relevant/available for this question).

Question: {question}"""

    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=final_text)]))
    return contents


def generate_answer(question: str, chunks: list, history: list = None) -> dict:
    if not key_is_valid():
        return {"answer": "⚠️ No valid Gemini API key found. Add it to .env and restart.", "sources": []}

    relevant_chunks = _relevant(chunks)
    contents = build_contents(question, relevant_chunks, history or [])

    try:
        client = get_client()
        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(max_output_tokens=1200),
        )
        answer_text = response.text or ""
        usage = response.usage_metadata
        total_tokens = usage.total_token_count if usage else 0
    except Exception as e:
        return {"answer": f"⚠️ Gemini API error: {e}", "sources": []}

    sources = [{"source": c["source"], "page": c["page"]} for c in relevant_chunks]
    return {
        "answer": answer_text,
        "sources": sources,
        "confidence": confidence_label(relevant_chunks),
        "tokens": total_tokens,
    }


def generate_answer_stream(question: str, chunks: list, history: list = None):
    """
    Yields answer text incrementally, then a final
    '\\n\\n[[META]]<json with sources/confidence/tokens/retrieved>' marker.
    """
    relevant_chunks = _relevant(chunks)

    if not key_is_valid():
        yield "⚠️ No valid Gemini API key found. Add it to .env and restart."
        meta = {"sources": [], "confidence": "N/A", "tokens": 0, "retrieved": []}
        yield f"\n\n[[META]]{json.dumps(meta)}"
        return

    contents = build_contents(question, relevant_chunks, history or [])
    total_tokens = 0

    try:
        client = get_client()
        stream = client.models.generate_content_stream(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(max_output_tokens=1200),
        )
        for chunk in stream:
            if chunk.text:
                yield chunk.text
            if getattr(chunk, "usage_metadata", None) and chunk.usage_metadata.total_token_count:
                total_tokens = chunk.usage_metadata.total_token_count
    except Exception as e:
        yield f"\n\n⚠️ Gemini API error: {e}"

    meta = {
        "sources": [{"source": c["source"], "page": c["page"]} for c in relevant_chunks],
        "confidence": confidence_label(relevant_chunks),
        "tokens": total_tokens,
        "retrieved": relevant_chunks,
    }
    yield f"\n\n[[META]]{json.dumps(meta)}"


def generate_comparison(question: str, chunks: list, history: list = None) -> dict:
    with_rag = generate_answer(question, chunks, history=history)
    without_rag = generate_answer(question, [], history=history)
    return {"with_rag": with_rag, "without_rag": without_rag}


def expand_query(question: str) -> list:
    if not key_is_valid():
        return []
    try:
        prompt = f"""Rewrite this question in 2 different ways that mean the same thing,
to help a search engine find related content. Return ONLY the 2 rewrites, one per line,
no numbering, no extra text.

Question: {question}"""
        result = _call_gemini(prompt, max_tokens=150)
        lines = [l.strip("-• ").strip() for l in result.strip().split("\n") if l.strip()]
        return lines[:2]
    except Exception:
        return []


def summarize_text(text: str, source_name: str) -> str:
    if not key_is_valid():
        return "⚠️ No valid Gemini API key found."
    try:
        prompt = f"""Summarize the following document in 5-8 clear bullet points,
covering the key ideas. Document name: {source_name}

{text[:12000]}"""
        return _call_gemini(prompt, max_tokens=800)
    except Exception as e:
        return f"⚠️ Could not summarize: {e}"


def generate_quiz(text: str, source_name: str, num_questions: int = 5) -> list:
    if not key_is_valid():
        return []
    try:
        prompt = f"""Based on the document below, create exactly {num_questions} multiple-choice
questions to test understanding. Return ONLY valid JSON, no markdown fences, no extra text,
in this exact format:
[
  {{"question": "...", "options": ["A", "B", "C", "D"], "correct_index": 0, "explanation": "..."}}
]

Document name: {source_name}

{text[:12000]}"""
        result = _call_gemini(prompt, max_tokens=1500)
        cleaned = result.strip().strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        return json.loads(cleaned)
    except Exception:
        return []


def suggest_followups(question: str, answer: str) -> list:
    if not key_is_valid():
        return []
    try:
        prompt = f"""Given this Q&A exchange, suggest 3 short, natural follow-up questions
the user might want to ask next. Return ONLY the 3 questions, one per line, no numbering.

Q: {question}
A: {answer[:1000]}"""
        result = _call_gemini(prompt, max_tokens=150)
        lines = [l.strip("-• ").strip() for l in result.strip().split("\n") if l.strip()]
        return lines[:3]
    except Exception:
        return []


def check_faithfulness(question: str, answer: str, chunks: list) -> dict:
    if not chunks:
        return {"checked": False, "faithful": None, "explanation": "No document context was used for this answer."}
    if not key_is_valid():
        return {"checked": False, "faithful": None, "explanation": "No valid API key."}

    context = "\n\n".join(f"[Source {i+1}]\n{c['text']}" for i, c in enumerate(chunks))
    prompt = f"""You are a strict fact-checker. Given the CONTEXT and an ANSWER that was
supposedly derived from it, determine if the answer is actually supported by the context.

Respond in EXACTLY this format, nothing else:
VERDICT: <SUPPORTED or NOT_SUPPORTED or PARTIALLY_SUPPORTED>
REASON: <one short sentence>

CONTEXT:
{context}

ANSWER TO CHECK:
{answer}"""

    try:
        result = _call_gemini(prompt, max_tokens=150)
        lines = result.strip().split("\n")
        verdict_line = next((l for l in lines if l.upper().startswith("VERDICT:")), "VERDICT: UNKNOWN")
        reason_line = next((l for l in lines if l.upper().startswith("REASON:")), "REASON: ")

        verdict = verdict_line.split(":", 1)[1].strip().upper()
        reason = reason_line.split(":", 1)[1].strip()

        faithful_map = {"SUPPORTED": True, "NOT_SUPPORTED": False, "PARTIALLY_SUPPORTED": "partial"}
        return {"checked": True, "faithful": faithful_map.get(verdict, None), "explanation": reason}
    except Exception as e:
        return {"checked": False, "faithful": None, "explanation": f"Check failed: {e}"}
