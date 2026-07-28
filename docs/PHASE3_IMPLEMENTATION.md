# Phase 3 Implementation Documentation

**Status:** first pass implemented and verified · **Scope:** the behavioral preference profile
("real interaction" signal) from [`THESIS_PROJECT_PLAN.md`](THESIS_PROJECT_PLAN.md) §7 Phase 3.

This document is a standalone implementation record for Phase 3 — what was built, how it works,
and how it was verified — kept separate from the roadmap document per the same convention as
[`PHASE0_PHASE1_IMPLEMENTATION.md`](PHASE0_PHASE1_IMPLEMENTATION.md). Unlike Phase 0/1, this phase
**is** part of the actual thesis deliverable (§2a): it produces the behavioral signal that Phase 4
(the query recommender core) will condition candidate suggestions on.

---

## 1. Overview

The professor's core research premise (attributed to "Jerry's" analysis in the scoping email) is
that a user's *stated* preferences (what they type into a search box) and their *actual* behavior
(what they watch, and how much of it) often diverge — and that a good query recommender must
condition on both, not just query history. Phase 3 builds the empirical substrate for that claim
on the Movie domain: for each user, a machine-readable summary of what they say they want vs. what
they actually engage with, plus a quantified divergence score between the two.

This is implemented as a standalone script, `recommender/behavioral_profile.py`, living in a new
top-level `recommender/` directory that is the start of the actual thesis deliverable — kept
separate from `profile_geneartion/` (the earlier Streamlit tool from the "as-is" architecture),
which remains a reference for the interest-node JSON shape but is not extended in place.

Scope: Movie domain only. Tourism has no per-user behavioral signal to condition on (decided in
Phase 0 — see [`PHASE0_PHASE1_IMPLEMENTATION.md`](PHASE0_PHASE1_IMPLEMENTATION.md) §3.3/§5), so
the stated-vs-actual analysis is only realizable on Movie today.

---

## 2. Inputs and outputs

**Inputs** — read directly from `netflix_dataset/` CSVs (not the Ontop VKG; this is offline batch
analysis over the raw source data, same substrate as Phase 0's `postgres-movie` load):

- `movies.csv` — catalog, used to build a controlled vocabulary of genre/content-type/country
  values.
- `watch_history.csv` — the **actual** signal (105,000 rows: `action`, `progress_percentage`,
  `watch_date`, `movie_id`).
- `search_logs.csv` — the **stated** signal (26,500 rows: free-text `search_query`, `search_date`,
  no `movie_id` — the exact gap flagged in the roadmap's §3.3).

**Outputs**, written to `recommender/output/`:

- `behavioral_profiles/profile_<user_id>.json` — one file per user with both signals and a
  divergence summary (schema in §4).
- `search_watch_links.csv` — the flat table of every search successfully linked to a subsequent
  watch (see §3.3), one row per link.

---

## 3. Methodology (`recommender/behavioral_profile.py`)

### 3.1 Catalog vocabulary and search-query tagging

`build_vocabulary()` collects every distinct non-"Unknown" value across `movies.csv`'s
`genre_primary`, `genre_secondary`, `content_type`, and `country_of_origin` columns, sorted
longest-first (so a multi-word value like `"Stand-up Comedy"` is checked before a shorter value
like `"Comedy"` could match part of it).

`infer_categories()` tags each free-text `search_query` with every vocabulary value it contains,
matched via a **word-boundary regex** (`\bvalue\b`), not a plain substring check. This was a
deliberate fix during implementation: an early substring version let `content_type="Movie"`
spuriously match inside the plural word "movies" in almost every query, and `"War"` would have
matched inside words like "warrior". Word-boundary matching eliminates both false-positive classes.

### 3.2 Actual-interest weighting

`completion_weight()` turns each `watch_history` row into a 0.05–1.0 weight: `1.0` if
`action == "completed"`, otherwise the row's `progress_percentage / 100` (floored at `0.05`), or
`0.3` if progress is missing. This operationalizes "actual interest" as *how much of something a
user engaged with*, not just whether a watch event exists at all — a user who starts and abandons
five thrillers should count for less than one who finishes one.

`compute_actual_nodes_table()` groups weighted watches by `(user_id, month, category-value)`,
divides by that user-month's total weighted interactions to get a relative **intensity** (0–1,
matching `profile_geneartion`'s existing relative-share convention — see roadmap §3.1), and
labels each row `signal: "actual"`.

### 3.3 Stated-interest weighting and the search→watch temporal join

`compute_stated_nodes_table()` mirrors the same relative-intensity computation for search logs:
per `(user_id, month, inferred category)`, intensity = share of that user-month's tagged searches.
Labeled `signal: "stated"`.

Separately, `link_search_to_watch()` implements the search→watch temporal-join heuristic flagged
as an unmet gap in the roadmap (§3.3: *"there is no existing key linking a `search_logs` row to a
specific movie in `watch_history`"*). For every search with at least one inferred category, it
finds that user's **next watch within a 7-day window** (`pd.merge_asof`, `direction="forward"`,
`tolerance=7 days`) and flags `matched_stated_intent`: whether any inferred category from the
search actually appears in the watched movie's genre/content-type. This produces a concrete,
row-level artifact — not just an aggregate score — of whether a stated intent was followed by
matching behavior.

### 3.4 Divergence scoring

`compute_divergence()` takes each user's top-5 actual categories and top-5 stated categories
(by summed intensity) and computes:

- `overlap` — the set intersection of the two top-5 lists.
- `jaccard_similarity` — `|intersection| / |union|`, `None` if the user has neither signal.

This single number is the per-user "how much does what they say match what they do" score that
Phase 4's candidate generation and ranking will consume as the behavioral divergence signal.

---

## 4. Output schema

`profile_<user_id>.json`:

```json
{
  "user_id": "user_00001",
  "domain": "Movie",
  "nodes": [
    {
      "category": "Genre | Content Type | Country | Stated Interest",
      "value": "<category value>",
      "signal": "actual | stated",
      "intensity": 0.0-1.0,
      "time_window": { "type": "monthly", "value": "YYYY-MM" },
      "support": { "weighted_interactions": <float> } | { "searches": <int> }
    }
  ],
  "divergence": {
    "actual_top": ["<top-5 actual categories by intensity>"],
    "stated_top": ["<top-5 stated categories by intensity>"],
    "overlap": ["<categories in both>"],
    "jaccard_similarity": 0.0-1.0
  }
}
```

This is structurally analogous to `profile_geneartion`'s existing `nodi_interesse` shape (same
category/value/intensity/time-window fields), extended with the `signal` field that distinguishes
stated from actual, and the top-level `divergence` block that summarizes the gap between them.

---

## 5. Verification performed

Ran against the full `netflix_dataset` (1,040 movies, 10,300 users, 105,000 watch rows, 26,500
search rows):

| Metric | Value |
|---|---|
| Users with a behavioral profile written | 10,000 of 10,300 (300 users have no watch history) |
| Search→watch links found (7-day window) | 1,179 |
| Average stated-vs-actual Jaccard similarity | **0.01** |
| Users with zero overlap between top-5 stated and top-5 actual | **9,399 / 10,000** |

Spot-checked one profile directly (`profile_user_00001.json`): actual top-5 = `["Movie", "USA",
"Canada", "Adventure", "War"]` (mix of content-type/country/genre values, expected since all three
category types share one ranking pool), stated top-5 = `["Action"]` (only one tagged search in
this user's log), overlap = `[]`, Jaccard = `0.0` — consistent with the aggregate numbers above.

Confirmed the word-boundary fix (§3.1) is doing its job: manually checked that searches containing
"movies" (plural) no longer spuriously tag `content_type="Movie"`, and that "warrior"-type queries
no longer spuriously tag `genre="War"`.

---

## 6. Interpretation and limitations

- **The near-zero average Jaccard similarity (0.01) is a striking number**, and it is consistent
  in *direction* with the professor's own framing example (a user types "romantic movie" but
  consistently watches American comedies) — but it should not be reported as a validated
  real-world divergence rate. `netflix_dataset` is Faker-generated synthetic data with **no true
  causal link** between a search string and a later watch event; a search and a subsequent watch
  being uncorrelated is exactly what you'd expect from random generation, so this number reflects
  the heuristic's behavior on synthetic data at least as much as it reflects any real
  "stated ≠ actual" phenomenon. This caveat is carried over verbatim from the roadmap's Phase 3
  status note and §8 risk list, and should be stated explicitly as a limitation in the thesis text
  rather than presented as an empirical finding about real users.
- **The 7-day linking window is a heuristic choice**, not derived from data — a different window
  would produce a different (though likely still low) link count and divergence number. Worth a
  sensitivity check (e.g. re-running at 3/14/30 days) if this number is used quantitatively in the
  thesis rather than just descriptively.
- **Not yet incorporated**: recency weighting (older watches count the same as recent ones) and
  `reviews.csv` sentiment as a third signal — both left for a later iteration if the divergence
  signal needs refining for Phase 4, per the roadmap's Phase 3 checklist.
- **Worth re-running once/if real interaction data becomes available** (per the roadmap's open
  dependency, §8) as a comparison point against this synthetic-data baseline.

---

## 7. Pointers

- [`THESIS_PROJECT_PLAN.md`](THESIS_PROJECT_PLAN.md) — full roadmap; §7 Phase 3 status note and
  §8 risk list carry the same synthetic-data caveat as §6 above.
- [`PHASE0_PHASE1_IMPLEMENTATION.md`](PHASE0_PHASE1_IMPLEMENTATION.md) — the Movie VKG/dataset
  harness this phase's input data comes from.
- `recommender/behavioral_profile.py` — the implementation; run via `python behavioral_profile.py`
  from the `recommender/` directory (reads `../netflix_dataset/`, writes `output/`).
- Phase 4 (query recommender core, not yet built) is the next consumer of this phase's output —
  see roadmap §7 Phase 4b, which explicitly names "a compact rendering of the Phase 3 behavioral
  summary" as a candidate-generation prompt input.
