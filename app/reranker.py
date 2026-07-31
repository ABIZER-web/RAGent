"""
Re-ranking module.
Plain embedding similarity (cosine/dot-product) is fast but approximate — it
compares question and chunk independently. A cross-encoder reads the question
and chunk TOGETHER and scores how well they actually match, which is slower
but noticeably more accurate. We use it as a second pass: retrieve a wider
candidate pool with embeddings, then re-rank that pool with the cross-encoder.
"""

from sentence_transformers import CrossEncoder

_reranker = None


def get_reranker():
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker


def rerank(question: str, candidates: list, top_k: int = 4):
    """
    candidates: list of chunk dicts (from embeddings.query_store)
    Returns the top_k candidates re-scored by the cross-encoder, with
    each chunk's 'score' replaced by the (normalized-ish) rerank score.
    """
    if not candidates:
        return []

    model = get_reranker()
    pairs = [[question, c["text"]] for c in candidates]
    raw_scores = model.predict(pairs)

    # Squash raw logits into a rough 0-1 range so RELEVANCE_THRESHOLD still works
    scores = [1 / (1 + pow(2.71828, -s)) for s in raw_scores]

    scored = list(zip(candidates, scores))
    scored.sort(key=lambda x: x[1], reverse=True)

    results = []
    for chunk, score in scored[:top_k]:
        new_chunk = dict(chunk)
        new_chunk["score"] = float(score)
        results.append(new_chunk)
    return results
