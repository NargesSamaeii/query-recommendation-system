"""Phase 2/4e request handler, shared by the FastAPI endpoint (app.py) and the
gui_v2.py dev harness, so both exercise the identical contract
(docs/THESIS_PROJECT_PLAN.md SS7 Phase 2/4e).

Orchestrates the Phase 4 recommender core: retrieval (4a) -> candidate generation
(4b) -> schema-grounding validation (4c) -> ranking/diversification (4d). Any failure
in that chain (most likely 4b, which needs a real LLM API key) degrades to an empty
`suggestions` list rather than failing the request -- the query is always logged
regardless, since that's this function's other job (feeding future retrieval).
"""

import json
import logging
from pathlib import Path

from . import schemas
from ..query_log import log_query
from ..core.retrieval import retrieve_similar_queries
from ..core.generation import generate_candidates
from ..core.validation import filter_grounded
from ..core.ranking import rank_and_diversify

logger = logging.getLogger("recommender.api.service")

_PROFILES_DIR = Path(__file__).resolve().parent.parent / "output" / "behavioral_profiles"


def _load_behavioral_profile(user_id):
    """Phase 3 output. Movie-domain only today (docs/THESIS_PROJECT_PLAN.md SS7 Phase 0/3)
    -- returns None for users/domains with no profile on disk, which every downstream
    function here already treats as "no behavioral signal available".
    """
    profile_path = _PROFILES_DIR / f"profile_{user_id}.json"
    if not profile_path.exists():
        return None
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load behavioral profile for %s: %s", user_id, exc)
        return None


def handle_recommend(request: schemas.RecommendRequest) -> schemas.RecommendResponse:
    log_query(
        user_id=request.user_id,
        domain=request.domain,
        query_text=request.query_text,
        generated_sparql=request.generated_sparql,
        result_summary=request.result_summary,
    )

    similar_queries = retrieve_similar_queries(request.user_id, request.query_text, domain=request.domain)
    behavioral_profile = _load_behavioral_profile(request.user_id)

    try:
        candidates = generate_candidates(
            request.query_text, similar_queries, behavioral_profile, request.domain,
        )
    except Exception as exc:
        logger.warning("Candidate generation failed for user=%s domain=%s: %s", request.user_id, request.domain, exc)
        return schemas.RecommendResponse(suggestions=[])

    try:
        grounded = filter_grounded(candidates, request.domain)
    except FileNotFoundError as exc:
        logger.warning("Schema grounding unavailable for domain=%s: %s", request.domain, exc)
        grounded = candidates

    suggestions = rank_and_diversify(grounded, similar_queries, behavioral_profile, top_n=3)
    return schemas.RecommendResponse(suggestions=suggestions)
