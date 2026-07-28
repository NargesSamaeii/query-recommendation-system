"""Phase 3: builds, per Movie-domain user, stated (search) vs. actual (watch) interest
nodes plus a divergence summary — the empirical evidence for the thesis's core claim that
stated and real preferences diverge. Output feeds the recommender API's behavioral signal
(docs/THESIS_PROJECT_PLAN.md §7 Phase 3/4)."""

import json
import re
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "netflix_dataset"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
PROFILES_DIR = OUTPUT_DIR / "behavioral_profiles"
WATCH_WINDOW_DAYS = 7
TOP_N = 5

NODE_COLUMNS = ["genre_primary", "content_type", "country_of_origin"]
NODE_CATEGORY_NAMES = {
    "genre_primary": "Genre",
    "content_type": "Content Type",
    "country_of_origin": "Country",
}


def load_data():
    movies = pd.read_csv(DATA_DIR / "movies.csv")
    watch = pd.read_csv(DATA_DIR / "watch_history.csv", parse_dates=["watch_date"])
    search = pd.read_csv(DATA_DIR / "search_logs.csv", parse_dates=["search_date"])

    for col in NODE_COLUMNS:
        movies[col] = movies[col].fillna("Unknown")

    watch = watch.dropna(subset=["user_id", "movie_id"]).merge(
        movies[["movie_id", "title", *NODE_COLUMNS, "genre_secondary"]],
        on="movie_id",
        how="left",
    )
    return movies, watch, search


def build_vocabulary(movies):
    values = set()
    for col in (*NODE_COLUMNS, "genre_secondary"):
        values.update(v for v in movies[col].dropna().unique() if v != "Unknown")
    # longest-first so e.g. "Stand-up Comedy" matches before a bare "Comedy" would
    return sorted(values, key=len, reverse=True)


def build_vocabulary_patterns(vocabulary):
    # word-boundary match: plain substring would let e.g. "Movie" (a content_type value)
    # spuriously match inside the plural "movies", or "War" match inside "warrior"
    return {v: re.compile(r"\b" + re.escape(v.lower()) + r"\b") for v in vocabulary}


def infer_categories(search_query, vocabulary_patterns):
    query = str(search_query).lower()
    return [v for v, pattern in vocabulary_patterns.items() if pattern.search(query)]


def enrich_search_logs(search, vocabulary):
    search = search.copy()
    patterns = build_vocabulary_patterns(vocabulary)
    search["inferred_categories"] = search["search_query"].apply(lambda q: infer_categories(q, patterns))
    return search


def completion_weight(row):
    if row["action"] == "completed":
        return 1.0
    if pd.notna(row["progress_percentage"]):
        return max(0.05, min(1.0, row["progress_percentage"] / 100.0))
    return 0.3


def link_search_to_watch(search_enriched, watch, window_days=WATCH_WINDOW_DAYS):
    """Temporal join: for each search with an inferred category, find the user's next watch
    within `window_days` and flag whether it matches what they said they wanted — the
    concrete "stated vs. actual" artifact (docs/THESIS_PROJECT_PLAN.md §3.3)."""
    searches = search_enriched[search_enriched["inferred_categories"].map(bool)].copy()
    searches = searches.sort_values("search_date")
    watch_cols = ["user_id", "watch_date", "movie_id", "title", "genre_primary", "genre_secondary", "content_type"]
    watch_sorted = watch[watch_cols].sort_values("watch_date")

    linked = pd.merge_asof(
        searches,
        watch_sorted,
        left_on="search_date",
        right_on="watch_date",
        by="user_id",
        direction="forward",
        tolerance=pd.Timedelta(days=window_days),
        suffixes=("", "_watched"),
    )
    linked = linked.dropna(subset=["movie_id"]).copy()
    linked["matched_stated_intent"] = linked.apply(
        lambda r: bool(set(r["inferred_categories"]) & {r["genre_primary"], r["genre_secondary"], r["content_type"]}),
        axis=1,
    )
    return linked


def compute_actual_nodes_table(watch):
    watch = watch.copy()
    watch["weight"] = watch.apply(completion_weight, axis=1)
    watch["period"] = watch["watch_date"].dt.to_period("M").astype(str)

    frames = []
    for column in NODE_COLUMNS:
        grouped = watch.groupby(["user_id", "period", column])["weight"].sum().reset_index(name="weighted_interactions")
        totals = grouped.groupby(["user_id", "period"])["weighted_interactions"].sum().reset_index(name="period_total")
        merged = grouped.merge(totals, on=["user_id", "period"])
        merged["intensity"] = (merged["weighted_interactions"] / merged["period_total"]).round(2)
        merged["category"] = NODE_CATEGORY_NAMES[column]
        merged = merged.rename(columns={column: "value"})
        frames.append(merged[["user_id", "period", "category", "value", "intensity", "weighted_interactions"]])

    result = pd.concat(frames, ignore_index=True)
    result["signal"] = "actual"
    return result


def compute_stated_nodes_table(search_enriched):
    search_enriched = search_enriched.copy()
    search_enriched["period"] = search_enriched["search_date"].dt.to_period("M").astype(str)
    exploded = search_enriched.explode("inferred_categories").dropna(subset=["inferred_categories"])
    if exploded.empty:
        return pd.DataFrame(columns=["user_id", "period", "category", "value", "intensity", "searches", "signal"])

    grouped = exploded.groupby(["user_id", "period", "inferred_categories"]).size().reset_index(name="searches")
    totals = grouped.groupby(["user_id", "period"])["searches"].sum().reset_index(name="period_total")
    merged = grouped.merge(totals, on=["user_id", "period"])
    merged["intensity"] = (merged["searches"] / merged["period_total"]).round(2)
    merged["category"] = "Stated Interest"
    merged = merged.rename(columns={"inferred_categories": "value"})
    merged["signal"] = "stated"
    return merged[["user_id", "period", "category", "value", "intensity", "searches", "signal"]]


def top_n_per_user(scores_df, top_n=TOP_N):
    ranked = scores_df.sort_values("intensity", ascending=False)
    return ranked.groupby("user_id")["value"].apply(lambda s: list(s.head(top_n)))


def compute_divergence(actual_table, stated_table, top_n=TOP_N):
    actual_scores = actual_table.groupby(["user_id", "value"])["intensity"].sum().reset_index()
    stated_scores = stated_table.groupby(["user_id", "value"])["intensity"].sum().reset_index()

    actual_top = top_n_per_user(actual_scores, top_n)
    stated_top = top_n_per_user(stated_scores, top_n)

    divergence = pd.DataFrame({"actual_top": actual_top, "stated_top": stated_top})
    divergence["actual_top"] = divergence["actual_top"].apply(lambda v: v if isinstance(v, list) else [])
    divergence["stated_top"] = divergence["stated_top"].apply(lambda v: v if isinstance(v, list) else [])

    def jaccard(row):
        a, b = set(row["actual_top"]), set(row["stated_top"])
        if not a and not b:
            return None
        union = a | b
        return round(len(a & b) / len(union), 2) if union else None

    divergence["overlap"] = divergence.apply(lambda r: sorted(set(r["actual_top"]) & set(r["stated_top"])), axis=1)
    divergence["jaccard_similarity"] = divergence.apply(jaccard, axis=1)
    return divergence


def write_user_profiles(actual_table, stated_table, divergence):
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    nodes_table = pd.concat([actual_table, stated_table], ignore_index=True)

    for user_id, group in nodes_table.groupby("user_id"):
        nodes = [
            {
                "category": row["category"],
                "value": row["value"],
                "signal": row["signal"],
                "intensity": row["intensity"],
                "time_window": {"type": "monthly", "value": row["period"]},
                "support": (
                    {"weighted_interactions": round(row["weighted_interactions"], 2)}
                    if row["signal"] == "actual"
                    else {"searches": int(row["searches"])}
                ),
            }
            for _, row in group.iterrows()
        ]
        div = divergence.loc[user_id] if user_id in divergence.index else None
        profile = {
            "user_id": user_id,
            "domain": "Movie",
            "nodes": nodes,
            "divergence": {
                "actual_top": div["actual_top"] if div is not None else [],
                "stated_top": div["stated_top"] if div is not None else [],
                "overlap": div["overlap"] if div is not None else [],
                "jaccard_similarity": div["jaccard_similarity"] if div is not None else None,
            },
        }
        with open(PROFILES_DIR / f"profile_{user_id}.json", "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)


def main():
    print("Loading netflix_dataset CSVs...")
    movies, watch, search = load_data()

    print("Building catalog vocabulary and enriching search logs...")
    vocabulary = build_vocabulary(movies)
    search_enriched = enrich_search_logs(search, vocabulary)

    print("Linking searches to subsequent watches (temporal join)...")
    linked = link_search_to_watch(search_enriched, watch)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    linked_out = linked.drop(columns=["inferred_categories"]).assign(
        inferred_categories=linked["inferred_categories"].apply(lambda c: ";".join(c))
    )
    linked_out.to_csv(OUTPUT_DIR / "search_watch_links.csv", index=False)

    print("Computing actual (watch) and stated (search) interest nodes...")
    actual_table = compute_actual_nodes_table(watch)
    stated_table = compute_stated_nodes_table(search_enriched)

    print("Computing per-user stated-vs-actual divergence...")
    divergence = compute_divergence(actual_table, stated_table)

    print(f"Writing per-user profiles to {PROFILES_DIR} ...")
    write_user_profiles(actual_table, stated_table, divergence)

    n_users_with_both = divergence.dropna(subset=["jaccard_similarity"]).shape[0]
    n_users_total = divergence.shape[0]
    n_zero_overlap = (divergence["jaccard_similarity"] == 0).sum()
    avg_jaccard = divergence["jaccard_similarity"].dropna().mean()

    print("\n--- Summary ---")
    print(f"Users with a behavioral profile: {n_users_total}")
    print(f"Users with both stated and actual top interests: {n_users_with_both}")
    print(f"Users with zero overlap (fully divergent): {n_zero_overlap}")
    print(f"Average Jaccard similarity (stated vs. actual): {avg_jaccard:.2f}")
    print(f"Search->watch links found: {len(linked)} (see {OUTPUT_DIR / 'search_watch_links.csv'})")


if __name__ == "__main__":
    main()
