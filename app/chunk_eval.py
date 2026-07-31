"""
Chunking strategy comparison.
Re-chunks a user's already-uploaded raw files at several different chunk
sizes, builds a temporary in-memory embedding index for each size (without
touching the persisted knowledge base), and measures retrieval accuracy
against a test set — so you can see which chunk size actually works best.
"""

import os
import numpy as np

from app.ingestion import chunk_document, LOADERS
from app.embeddings import get_model


def _build_temp_index(file_paths_and_names, chunk_size, chunk_overlap):
    model = get_model()
    all_chunks = []
    for path, name in file_paths_and_names:
        try:
            chunks = chunk_document(path, source_name=name, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            all_chunks.extend(chunks)
        except Exception:
            continue

    if not all_chunks:
        return np.zeros((0, 384), dtype=np.float32), []

    texts = [c["text"] for c in all_chunks]
    vectors = model.encode(texts, normalize_embeddings=True)
    return np.array(vectors), all_chunks


def _query_temp_index(vectors, meta, question, top_k=4):
    if vectors.shape[0] == 0:
        return []
    model = get_model()
    q_vector = model.encode([question], normalize_embeddings=True)[0]
    scores = vectors @ q_vector
    top_idx = np.argsort(scores)[::-1][:top_k]
    return [meta[i] for i in top_idx]


def compare_rerank_on_off(user_id: str, test_cases: list, top_k: int = 4):
    """
    Runs the same test cases through retrieval with re-ranking ON vs OFF
    (using the ALREADY-persisted knowledge base — no re-chunking needed)
    and compares hit-rate, to show whether the cross-encoder pass is
    actually earning its extra latency.
    """
    from app.retriever import retrieve_relevant_chunks

    results = {}
    for use_rerank in (True, False):
        hits = 0
        for case in test_cases:
            retrieved = retrieve_relevant_chunks(user_id, case["question"], top_k=top_k, use_rerank=use_rerank)
            combined_text = " ".join(c["text"].lower() for c in retrieved)
            if case["expected_keyword"].lower() in combined_text:
                hits += 1
        accuracy = round((hits / len(test_cases)) * 100, 1) if test_cases else 0
        results["with_rerank" if use_rerank else "without_rerank"] = {
            "accuracy": accuracy, "hits": hits, "total": len(test_cases),
        }
    return results


def compare_chunking_strategies(upload_dir: str, test_cases: list, chunk_sizes: list = None, chunk_overlap: int = 40):
    """
    upload_dir: directory containing the user's originally uploaded files
    test_cases: [{"question": ..., "expected_keyword": ...}, ...]
    chunk_sizes: list of word-counts to test, e.g. [100, 250, 500]
    Returns a list of {chunk_size, accuracy, hits, total}.
    """
    chunk_sizes = chunk_sizes or [100, 250, 500]

    supported_exts = tuple(LOADERS.keys())
    file_paths_and_names = []
    if os.path.isdir(upload_dir):
        for fname in os.listdir(upload_dir):
            if fname.lower().endswith(supported_exts):
                file_paths_and_names.append((os.path.join(upload_dir, fname), fname))

    if not file_paths_and_names:
        return {"error": "No uploaded source files found to re-chunk."}

    results = []
    for size in chunk_sizes:
        vectors, meta = _build_temp_index(file_paths_and_names, size, chunk_overlap)

        hits = 0
        for case in test_cases:
            retrieved = _query_temp_index(vectors, meta, case["question"], top_k=4)
            combined_text = " ".join(c["text"].lower() for c in retrieved)
            if case["expected_keyword"].lower() in combined_text:
                hits += 1

        accuracy = round((hits / len(test_cases)) * 100, 1) if test_cases else 0
        results.append({
            "chunk_size": size,
            "accuracy": accuracy,
            "hits": hits,
            "total": len(test_cases),
            "num_chunks_created": len(meta),
        })

    return {"results": results}
