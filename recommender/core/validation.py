"""Phase 4c: schema-grounding validation for candidate follow-up queries.

Mitigates the well-documented LLM+KG hallucination/faithfulness risk
(KGGLLMRecommendation roadmap paper) and ADBIS_2026's own measured ~30%
SPARQL-incorrectness rate on their factual question set: a candidate query is never
shown to the user without first confirming it has *some* semantic relationship to the
currently loaded domain schema (docs/THESIS_PROJECT_PLAN.md SS7 Phase 4c).

IMPORTANT CALIBRATION FINDING (see docs/PHASE4_IMPLEMENTATION.md for the full writeup):
this is deliberately a weak/coarse filter, not a precision grounding check. Two stronger
designs were tried and rejected empirically:

1. ClassRelevanceEvaluator's own embedding mode uses *relative* thresholding
   (score >= mean - std across the schema's own classes) -- verified to always select
   at least one class regardless of whether the input has anything to do with the
   domain (e.g. "Best pizza recipe" against the Tourism schema still "passed").
2. An *absolute* cosine-similarity floor (this module's first version) was calibrated
   against control (clearly off-topic) phrases, but the Tourism schema's class
   descriptions are so sparse (plain SHACL cardinality boilerplate, e.g. "Art has
   exactly 1 Art Class ID. Art has at least 1 Art Name." -- no rdfs:comment, no
   sh:example values) that the professor's own example query "Free Churches in Verona"
   scored *lower* (0.092) than an off-topic control phrase, "How to fix a flat tire"
   (0.112). Any threshold strict enough to reject genuine noise would also reject that
   canonical example.

Given that finding, this module only rejects candidates with a near-zero/negative max
cosine similarity to every class in the schema -- true degenerate hallucinations, not
borderline-but-valid suggestions. A stronger check would require enriching class
descriptions with real catalog/instance values pulled from the live SPARQL endpoints
(flagged as follow-up work, not built here).
"""

import json
import sys
from pathlib import Path

_WEB_APP_ROOT = Path(__file__).resolve().parents[2] / "web_app"
if str(_WEB_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_WEB_APP_ROOT))

from sentence_transformers import util  # noqa: E402
from nl2sparql.embedding_evaluator_v2 import EmbeddingEvaluator  # noqa: E402

_SCHEMA_DIR = _WEB_APP_ROOT / "data" / "output"

# Deliberately low -- see module docstring. Only rejects candidates with essentially no
# semantic relationship to any class in the schema (near-zero/negative cosine); it is
# NOT calibrated to separate in-domain from off-topic phrasing, which the empirical
# tests in docs/PHASE4_IMPLEMENTATION.md showed is not reliably possible against these
# schemas' sparse class descriptions without rejecting valid queries.
DEFAULT_THRESHOLD = 0.05

_evaluator = None
_class_embedding_cache = {}


def _get_evaluator():
    global _evaluator
    if _evaluator is None:
        _evaluator = EmbeddingEvaluator("all-mpnet-base-v2")
    return _evaluator


def _load_class_embeddings(domain):
    if domain not in _class_embedding_cache:
        schema_path = _SCHEMA_DIR / f"{domain}_mschema.json"
        if not schema_path.exists():
            raise FileNotFoundError(f"No m-schema found for domain '{domain}' at {schema_path}")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_json = json.load(f)

        evaluator = _get_evaluator()
        classes_dict = schema_json.get("classes", {})
        class_names = [evaluator.normalize_class_id(name) for name in classes_dict.keys()]
        descriptions = [
            evaluator.build_class_description(evaluator.normalize_class_id(name), data)
            for name, data in classes_dict.items()
        ]
        embeddings = evaluator.encode(descriptions) if descriptions else None
        _class_embedding_cache[domain] = (class_names, embeddings)
    return _class_embedding_cache[domain]


def is_schema_grounded(candidate_query, domain, threshold=DEFAULT_THRESHOLD):
    """True if `candidate_query`'s max cosine similarity to any class description in
    `domain`'s active schema meets `threshold`."""
    class_names, class_embeddings = _load_class_embeddings(domain)
    if not class_names or class_embeddings is None:
        return False
    evaluator = _get_evaluator()
    query_embedding = evaluator.encode(candidate_query)
    scores = util.cos_sim(query_embedding, class_embeddings)[0]
    return bool(scores.max().item() >= threshold)


def filter_grounded(candidate_queries, domain, threshold=DEFAULT_THRESHOLD):
    """Return only the candidates that pass `is_schema_grounded`, preserving order."""
    return [q for q in candidate_queries if is_schema_grounded(q, domain, threshold=threshold)]
