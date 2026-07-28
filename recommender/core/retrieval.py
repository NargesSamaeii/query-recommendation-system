"""Phase 4a: retrieve a user's past queries most semantically similar to their current
one, from the query log built in Phase 2 (recommender/query_log.py).

RA-GQR-style (docs/THESIS_PROJECT_PLAN.md SS7 Phase 4a, QR2405.19749v2): these retrieved
queries become the few-shot examples for Phase 4b's LLM candidate generation, in place
of generic hand-curated examples.
"""

from sentence_transformers import SentenceTransformer

from ..query_log import get_user_history

# Same embedding model already used elsewhere in web_app's embedding-based class/property
# extraction (web_app/nl2sparql/embedding_evaluator_v2.py) -- reused here for consistency,
# not re-derived.
_MODEL_NAME = "all-mpnet-base-v2"
_model = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def retrieve_similar_queries(user_id, query_text, domain=None, top_k=3, history_limit=200, history=None):
    """Return up to `top_k` of this user's past queries most similar to `query_text`.

    Each result is the original query_log row dict plus a `similarity` field (cosine,
    0-1), ranked descending. Excludes exact case-insensitive duplicates of the current
    query. Returns [] if the user has no other logged queries (cold start).

    `history` is normally left None, which reads from the shared query_log SQLite store
    (recommender/query_log.py) as usual. Phase 5's evaluation harness passes a pre-built
    list of {"query_text": ...} rows instead (sourced from netflix_dataset/search_logs.csv)
    so it can seed realistic per-user retrieval context without writing synthetic rows
    into the production log used by the live API/harness.
    """
    if history is None:
        history = get_user_history(user_id, domain=domain, limit=history_limit)
    candidates = [
        row for row in history
        if row["query_text"].strip().lower() != query_text.strip().lower()
    ]
    if not candidates:
        return []

    model = _get_model()
    texts = [query_text] + [row["query_text"] for row in candidates]
    embeddings = model.encode(texts, normalize_embeddings=True)
    query_vec, candidate_vecs = embeddings[0], embeddings[1:]
    similarities = candidate_vecs @ query_vec  # cosine similarity, both sides normalized

    ranked = sorted(zip(candidates, similarities), key=lambda pair: pair[1], reverse=True)
    return [
        {**row, "similarity": round(float(sim), 4)}
        for row, sim in ranked[:top_k]
    ]
