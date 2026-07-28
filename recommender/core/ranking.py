"""Phase 4d: rank and diversify surviving candidate follow-up queries.

QRMOCCGA-inspired (docs/THESIS_PROJECT_PLAN.md SS7 Phase 4d, s11042-023-15585-6): score
each candidate along the plan's two axes --

- **query-history similarity**: how closely the candidate's wording matches this user's
  own past queries (Phase 4a's retrieval output), a proxy for QRMOCCGA's lexical/co-click
  similarity features.
- **behavioral alignment**: whether the candidate textually references the user's
  *actual* (not just stated) top interest categories from the Phase 3 behavioral
  profile -- the concrete place this thesis's stated-vs-actual signal feeds into ranking.

then greedily selects a diverse top-N via a simple MMR-style penalty on lexical (Jaccard
word) overlap between already-selected picks, so the final suggestions aren't
near-duplicates of each other.
"""

import re


def _tokenize(text):
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _jaccard(tokens_a, tokens_b):
    if not tokens_a and not tokens_b:
        return 0.0
    union = tokens_a | tokens_b
    return len(tokens_a & tokens_b) / len(union) if union else 0.0


def _history_similarity(candidate, similar_queries):
    """Max lexical overlap between `candidate` and any of the user's retrieved past queries."""
    if not similar_queries:
        return 0.0
    candidate_tokens = _tokenize(candidate)
    return max(
        (_jaccard(candidate_tokens, _tokenize(q["query_text"])) for q in similar_queries),
        default=0.0,
    )


def _behavioral_alignment(candidate, behavioral_profile):
    """Fraction of the user's actual-top interest categories referenced in `candidate`."""
    if not behavioral_profile:
        return 0.0
    actual_top = (behavioral_profile.get("divergence") or {}).get("actual_top") or []
    if not actual_top:
        return 0.0
    candidate_tokens = _tokenize(candidate)
    hits = sum(1 for value in actual_top if _tokenize(value) & candidate_tokens)
    return hits / len(actual_top)


def score_candidate(candidate, similar_queries, behavioral_profile, history_weight=0.5, behavior_weight=0.5):
    """Weighted sum of the two QRMOCCGA-inspired axes, each in [0, 1]."""
    return (
        history_weight * _history_similarity(candidate, similar_queries)
        + behavior_weight * _behavioral_alignment(candidate, behavioral_profile)
    )


def rank_and_diversify(candidates, similar_queries, behavioral_profile, top_n=3, diversity_penalty=0.5):
    """Greedily pick up to `top_n` candidates: highest weighted score first, each
    subsequent pick penalized by its max lexical overlap with already-selected picks
    (MMR-style) so near-duplicate suggestions don't all make the final cut.
    """
    if not candidates:
        return []

    scored = [(c, score_candidate(c, similar_queries, behavioral_profile)) for c in candidates]
    selected = []
    remaining = list(scored)

    while remaining and len(selected) < top_n:
        def adjusted_score(item):
            candidate, base_score = item
            if not selected:
                return base_score
            max_overlap = max(_jaccard(_tokenize(candidate), _tokenize(s)) for s in selected)
            return base_score - diversity_penalty * max_overlap

        remaining.sort(key=adjusted_score, reverse=True)
        best_candidate, _ = remaining.pop(0)
        selected.append(best_candidate)

    return selected
