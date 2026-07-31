"""
PHASE 2 — Embeddings & Vector Store
Sentence-Transformers embeddings + a simple local NumPy vector store.
Namespaced per-user so each account has its own separate knowledge base.
"""

import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer

_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _paths(user_id: str):
    store_dir = os.path.join("vectorstore", user_id)
    os.makedirs(store_dir, exist_ok=True)
    return (
        os.path.join(store_dir, "vectors.npy"),
        os.path.join(store_dir, "meta.json"),
    )


def _load_store(user_id: str):
    vectors_path, meta_path = _paths(user_id)
    if os.path.exists(vectors_path) and os.path.exists(meta_path):
        vectors = np.load(vectors_path)
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return vectors, meta
    return np.zeros((0, 384), dtype=np.float32), []


def _save_store(user_id: str, vectors, meta):
    vectors_path, meta_path = _paths(user_id)
    np.save(vectors_path, vectors)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)


def add_chunks_to_store(user_id: str, chunks: list):
    if not chunks:
        return 0

    model = get_model()
    texts = [c["text"] for c in chunks]
    new_vectors = model.encode(texts, normalize_embeddings=True)

    vectors, meta = _load_store(user_id)
    vectors = np.vstack([vectors, new_vectors]) if vectors.shape[0] else np.array(new_vectors)
    meta.extend(chunks)

    _save_store(user_id, vectors, meta)
    return len(chunks)


def query_store(user_id: str, question: str, top_k: int = 4, source_filter: str = None):
    """Returns top_k chunks by embedding similarity. Optionally scoped to one source file."""
    vectors, meta = _load_store(user_id)
    if vectors.shape[0] == 0:
        return []

    if source_filter and source_filter != "All documents":
        keep_idx = [i for i, m in enumerate(meta) if m["source"] == source_filter]
        if not keep_idx:
            return []
        vectors = vectors[keep_idx]
        meta = [meta[i] for i in keep_idx]

    model = get_model()
    q_vector = model.encode([question], normalize_embeddings=True)[0]

    scores = vectors @ q_vector
    top_idx = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_idx:
        c = meta[idx]
        results.append({
            "text": c["text"],
            "source": c["source"],
            "page": c["page"],
            "score": float(scores[idx]),
        })
    return results


def embed_text(text: str) -> np.ndarray:
    """Embeds a single piece of text — used by the semantic cache."""
    model = get_model()
    return model.encode([text], normalize_embeddings=True)[0]


def has_documents(user_id: str):
    vectors, _ = _load_store(user_id)
    return vectors.shape[0] > 0


def list_sources(user_id: str):
    _, meta = _load_store(user_id)
    return sorted(set(m["source"] for m in meta))


def clear_store(user_id: str):
    _save_store(user_id, np.zeros((0, 384), dtype=np.float32), [])
