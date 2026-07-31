"""
Semantic caching.
If a new question is semantically very similar to one we've already answered
(for this user, in this knowledge-base state), return the cached answer
instantly instead of burning another Gemini API call. Saves quota and is
much faster for the user.
"""

import os
import json
import time
import numpy as np

CACHE_DIR = "data/cache"
os.makedirs(CACHE_DIR, exist_ok=True)

SIMILARITY_THRESHOLD = 0.93
MAX_CACHE_ENTRIES = 200


def _paths(user_id: str):
    d = CACHE_DIR
    return (
        os.path.join(d, f"{user_id}_vectors.npy"),
        os.path.join(d, f"{user_id}_meta.json"),
    )


def _load(user_id: str):
    vpath, mpath = _paths(user_id)
    if os.path.exists(vpath) and os.path.exists(mpath):
        vectors = np.load(vpath)
        with open(mpath, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return vectors, meta
    return np.zeros((0, 384), dtype=np.float32), []


def _save(user_id: str, vectors, meta):
    vpath, mpath = _paths(user_id)
    np.save(vpath, vectors)
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(meta, f)


def lookup(user_id: str, question_vector: np.ndarray):
    """Returns a cached entry dict if a close-enough match exists, else None."""
    vectors, meta = _load(user_id)
    if vectors.shape[0] == 0:
        return None

    scores = vectors @ question_vector
    best_idx = int(np.argmax(scores))
    if scores[best_idx] >= SIMILARITY_THRESHOLD:
        entry = dict(meta[best_idx])
        entry["cache_similarity"] = float(scores[best_idx])
        return entry
    return None


def store(user_id: str, question: str, question_vector: np.ndarray, answer: str, sources: list, confidence: str):
    vectors, meta = _load(user_id)

    entry = {
        "question": question,
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
        "timestamp": time.time(),
    }

    if vectors.shape[0] >= MAX_CACHE_ENTRIES:
        # drop the oldest entry to make room
        oldest_idx = min(range(len(meta)), key=lambda i: meta[i]["timestamp"])
        vectors = np.delete(vectors, oldest_idx, axis=0)
        meta.pop(oldest_idx)

    vectors = np.vstack([vectors, question_vector.reshape(1, -1)]) if vectors.shape[0] else question_vector.reshape(1, -1)
    meta.append(entry)

    _save(user_id, vectors, meta)


def clear(user_id: str):
    _save(user_id, np.zeros((0, 384), dtype=np.float32), [])
