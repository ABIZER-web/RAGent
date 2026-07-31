"""
PHASE 3 (part 1) — Retriever
Two-stage retrieval: fast embedding search for a wide candidate pool,
then cross-encoder re-ranking for accuracy on the final top_k.
Supports per-user knowledge bases and optional query expansion.
"""

from app.embeddings import query_store
from app.reranker import rerank

CANDIDATE_POOL_SIZE = 15


def retrieve_relevant_chunks(user_id: str, question: str, top_k: int = 4,
                              use_rerank: bool = True, source_filter: str = None,
                              extra_queries: list = None):
    """
    extra_queries: optional list of rephrased versions of the question
    (query expansion) — results from all queries are pooled before ranking.
    """
    pool_size = CANDIDATE_POOL_SIZE if use_rerank else top_k
    candidates = query_store(user_id, question, top_k=pool_size, source_filter=source_filter)

    if extra_queries:
        seen_texts = {c["text"] for c in candidates}
        for q in extra_queries:
            for c in query_store(user_id, q, top_k=pool_size, source_filter=source_filter):
                if c["text"] not in seen_texts:
                    candidates.append(c)
                    seen_texts.add(c["text"])

    if not use_rerank or not candidates:
        candidates.sort(key=lambda c: c["score"], reverse=True)
        return candidates[:top_k]

    return rerank(question, candidates, top_k=top_k)
