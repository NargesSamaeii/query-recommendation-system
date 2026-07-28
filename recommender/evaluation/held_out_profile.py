"""Phase 5: a temporally held-out variant of the Phase 3 behavioral profile, for honest
proxy-ground-truth evaluation.

`recommender/behavioral_profile.py`'s production profiles are built from a user's *entire*
watch history -- fine for the live recommender, but useless as ground truth for evaluating
it (the "correct answer" would already be baked into the input). This module reuses that
same module's functions, but splits one user's watch history at a per-user date cutoff:
everything before it is treated as "known" (used to build the profile the recommender is
allowed to see), everything after it is held out as a proxy for "what the user went on to
actually want next" (docs/THESIS_PROJECT_PLAN.md SS7 Phase 5, "Proxy ground truth").
"""

from .. import behavioral_profile as bp


def build_held_out_profile(user_id, cutoff_quantile=0.8):
    """Return (profile_dict, held_out_watch_rows, cutoff_date) for one user.

    `profile_dict` is shaped like a normal Phase 3 profile (just the `divergence` block --
    the only part the recommender core actually reads) but built only from watch/search
    activity at or before the per-user cutoff date. `held_out_watch_rows` is the
    remaining (post-cutoff) watch_history rows, used as proxy ground truth: a suggestion
    "hits" if it textually references one of these rows' genre/country/content-type.
    Returns (None, empty df, None) if the user has no watch history at all.
    """
    movies, watch, search = bp.load_data()
    user_watch = watch[watch["user_id"] == user_id].sort_values("watch_date")
    if user_watch.empty:
        return None, user_watch, None

    cutoff_date = user_watch["watch_date"].quantile(cutoff_quantile)
    train_watch = user_watch[user_watch["watch_date"] <= cutoff_date]
    held_out_watch = user_watch[user_watch["watch_date"] > cutoff_date]

    user_search = search[search["user_id"] == user_id]
    vocabulary = bp.build_vocabulary(movies)
    search_enriched = bp.enrich_search_logs(user_search, vocabulary)
    train_search = search_enriched[search_enriched["search_date"] <= cutoff_date]

    actual_table = bp.compute_actual_nodes_table(train_watch)
    stated_table = bp.compute_stated_nodes_table(train_search)
    divergence = bp.compute_divergence(actual_table, stated_table)

    if user_id in divergence.index:
        div_row = divergence.loc[user_id]
        divergence_block = {
            "actual_top": div_row["actual_top"],
            "stated_top": div_row["stated_top"],
            "overlap": div_row["overlap"],
            "jaccard_similarity": div_row["jaccard_similarity"],
        }
    else:
        divergence_block = {"actual_top": [], "stated_top": [], "overlap": [], "jaccard_similarity": None}

    profile = {"user_id": user_id, "domain": "Movie", "divergence": divergence_block}
    return profile, held_out_watch, cutoff_date


def held_out_category_tokens(held_out_watch):
    """Flatten the held-out rows' genre/country/content-type values into a lowercase
    token set, for checking whether a suggestion string references any of them."""
    if held_out_watch is None or held_out_watch.empty:
        return set()
    tokens = set()
    for column in ("genre_primary", "genre_secondary", "country_of_origin", "content_type"):
        for value in held_out_watch[column].dropna().unique():
            tokens.update(str(value).lower().split())
    return tokens
