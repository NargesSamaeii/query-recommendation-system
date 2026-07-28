"""Phase 5: a non-LLM classical baseline for comparison against the LLM-based recommender.

Not a reimplementation of either literature baseline (docs/THESIS_PROJECT_PLAN.md SS4.1/4.4)
-- QRMOCCGA's cooperative co-evolutionary GA and ADBIS_2026's own frequency-based analytical
module are both out of scope to reimplement (per the roadmap's own framing). This borrows
their shared idea instead: recommend directly from the user's *actual* behavioral signal,
via a fixed template, with no model call at all. Comparing this against the LLM pipeline's
suggestions is the "how would a simple, non-LLM, log-mining approach do" evaluation point
the roadmap's Phase 5 section explicitly asks for.
"""


def generate_baseline_suggestions(behavioral_profile, top_n=3):
    """Return up to `top_n` templated suggestions from a user's actual-top categories.

    Categories not already present in `stated_top` are preferred (novelty over what the
    user already typed), falling back to the remaining actual-top categories if there
    aren't enough novel ones. Returns [] if there's no behavioral profile at all (e.g.
    Tourism, which has none by design -- docs/THESIS_PROJECT_PLAN.md SS7 Phase 0).
    """
    if not behavioral_profile:
        return []
    divergence = behavioral_profile.get("divergence") or {}
    actual_top = divergence.get("actual_top") or []
    stated_top = set(divergence.get("stated_top") or [])

    novel = [c for c in actual_top if c not in stated_top]
    fallback = [c for c in actual_top if c in stated_top]
    ordered_categories = (novel + fallback)[:top_n]

    return [f"{category} movies" for category in ordered_categories]
