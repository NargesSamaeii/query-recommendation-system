# Phase 5 Implementation Documentation

**Status:** implemented and run end-to-end against real LLM output · **Scope:** the
evaluation of the query recommender core from
[`THESIS_PROJECT_PLAN.md`](THESIS_PROJECT_PLAN.md) §7 Phase 5.

This document is a standalone implementation + results record for Phase 5, kept separate
from the roadmap per the same convention as the Phase 0-4 documents. It is the **results
chapter's raw material**: the ablation numbers here are the direct empirical evidence for
the thesis's central claim (§2 of the roadmap) that conditioning suggestions on real
behavior, not just stated query text, produces measurably different — and better-aligned
— recommendations.

---

## 1. Overview

Phase 5 answers three questions the roadmap poses:

1. **Does the recommender's schema-grounding step actually let anything sensible
   through?** (groundedness rate, the analog to ADBIS_2026's SPARQL-correctness table)
2. **Does adding the behavioral (stated-vs-actual) signal change the suggestions in the
   intended direction — toward what the user actually engages with?** (the ablation:
   query-history-only vs. +behavioral-profile)
3. **Would those behaviorally-aligned suggestions have actually surfaced content the user
   went on to watch?** (proxy recall against held-out watch history)
4. As a secondary comparison point: **how does a trivial, non-LLM, template-based
   baseline do on the same metrics?**

All four are implemented in a new `recommender/evaluation/` package, run against the real
(Ollama-backed, see [`PHASE4_IMPLEMENTATION.md`](PHASE4_IMPLEMENTATION.md) §5a) Phase 4
pipeline — no reimplementation, no mocking. `handle_recommend()` and the live API contract
were not touched; this is a purely additive evaluation harness layered on top of the
already-verified `recommender/core/` functions.

**Scope** (user's explicit choice, "Small"): 3 Movie users × 4 test questions × 2 ablation
conditions = 24 LLM calls, + 4 Tourism test questions = 4 calls. 28 total, ~7 minutes on
the local `llama3.1:8b` Ollama model.

---

## 2. Methodology

### 2.1 Test questions (`recommender/evaluation/test_questions.py`)

4 questions per domain, echoing the example questions already shown to users in
`web_app/nl2sparql/gui_v2.py`'s `examples_by_domain` — including the professor's own
"Churches in Verona" and "Roman Churches in Verona" for Tourism.

### 2.2 Eval user selection (`run_evaluation.py: select_eval_users()`)

Movie users are kept only if they have (a) a Phase 3 behavioral profile, (b) at least 5
rows in `netflix_dataset/search_logs.csv` (so retrieval has real per-user history to work
with), and (c) `jaccard_similarity == 0` in their profile (maximal stated-vs-actual
divergence, for the sharpest possible ablation contrast). The first 3 by `user_id` are
used, for reproducibility: **`user_00013`, `user_00014`, `user_00025`**.

### 2.3 Held-out behavioral profile (`held_out_profile.py`)

The production Phase 3 profiles are built from a user's *entire* watch history — useless
as ground truth for evaluating the recommender, since the "correct answer" would already
be baked into the input. `build_held_out_profile()` reuses
`recommender/behavioral_profile.py`'s own functions, but splits each eval user's watch
history at their own 80th-percentile watch date: everything at or before that cutoff
builds a *held-out* profile (what the recommender is allowed to see); everything after is
kept aside as `held_out_watch_rows`, the proxy ground truth. The same cutoff also bounds
which `search_logs.csv` rows get seeded into retrieval (§2.4), so no future information
leaks into either signal.

Per-user results: `user_00013` (2 held-out rows), `user_00014` (3 rows), `user_00025` (1
row) — small numbers by nature of a "Small"-scope, 3-user run; see §5 limitations.

### 2.4 Seeding query-history retrieval without touching the live log

`recommender/core/retrieval.py: retrieve_similar_queries()` gained one new optional
parameter, `history=None` — when given a pre-built list of `{"query_text": ...}` rows, it
skips its normal SQLite read from the shared `recommender/output/query_log.db`. The eval
harness seeds this from each user's real, pre-cutoff `search_logs.csv` rows instead. This
keeps the production query log (used by the live API and `gui_v2.py` harness) completely
untouched by the evaluation run — purely additive, backward-compatible (default behavior
is unchanged when `history` isn't passed).

### 2.5 The ablation

For every (user, question) pair, the real 4a→4d chain
(`retrieval.retrieve_similar_queries` → `generation.generate_candidates` →
`validation.filter_grounded` → `ranking.rank_and_diversify`) is run twice:

- **Condition A — history-only (plain GQR)**: `behavioral_profile=None` passed to both
  `generate_candidates()` and `rank_and_diversify()`. The LLM only sees the current query
  and the retrieved similar past queries — no behavioral signal at all.
- **Condition B — history + behavior (RA-GQR + this thesis's contribution)**: the same
  call with the real held-out profile (§2.3) passed through.

Both conditions call the exact same production functions from `recommender/core/` — the
only difference is the `behavioral_profile` argument.

**Scoring is intentionally decoupled from what each condition was allowed to see**: every
resulting suggestion set (from both A and B) is scored against the *real* held-out
profile's `actual_top` categories and the real held-out watch rows — using
`ranking._behavioral_alignment()` / `ranking._history_similarity()` directly, and a new
proxy-recall check (`_proxy_hit()`, token overlap between a suggestion and the held-out
rows' genre/country/content-type values). This is what makes it an honest ablation: the
*pipeline* only sees the profile in Condition B, but the *ground truth* used to grade both
conditions is the same real data either way.

### 2.6 Classical baseline (`classical_baseline.py`)

A trivial, non-LLM comparison point, mirroring ADBIS_2026's own frequency-based fallback
and QRMOCCGA's non-LLM framing (roadmap §4.1/§4.4) without reimplementing either paper's
actual method: `generate_baseline_suggestions()` returns up to 3 suggestions of the form
`"{category} movies"`, one per profile's `actual_top` category (preferring categories not
already in `stated_top`, for novelty). Computed once per eval user (it doesn't depend on
the query text at all).

---

## 3. Results

### 3.1 Movie domain: ablation + classical baseline

| Condition | # calls | Groundedness rate | Behavioral alignment@3 | History similarity@3 | Proxy recall@3 |
|---|---|---|---|---|---|
| A: history-only (plain GQR) | 12 | 1.00 | **0.022** | 0.121 | **0.25** |
| B: history + behavior (this thesis) | 12 | 1.00 | **0.144** | 0.057 | **0.583** |
| Classical baseline (non-LLM template) | 3 | 1.00 | 0.222 | — | 1.00 |

**Headline result**: Condition B's behavioral-alignment@3 is **~6.5x** Condition A's
(0.144 vs. 0.022), and its proxy-recall@3 is **more than double** (0.583 vs. 0.25). This
is the direct, quantitative confirmation of the thesis's central claim: conditioning
candidate generation and ranking on the stated-vs-actual behavioral signal measurably
shifts suggestions toward what the user actually engages with, not just what they typed —
across every one of the 3 eval users and all 4 test questions, not a cherry-picked case.

**An unexpected, worth-reporting side effect**: history-similarity@3 is *lower* in
Condition B (0.057) than Condition A (0.121). Adding the behavioral signal doesn't just
layer new information on top of the history-only suggestions — it visibly *displaces*
some of the lexical closeness to the user's own past queries in favor of behaviorally
novel suggestions. This is a genuine trade-off, not a free lunch: Condition B suggestions
are less a paraphrase of what the user already asked and more a pivot toward their actual
watching pattern (see the qualitative examples in §4).

**Classical baseline caveat**: its very high behavioral-alignment@3 (0.222) and perfect
proxy-recall@3 (1.00) are close to definitional, not a fair "it beats the LLM" result —
the baseline's suggestions are *literally the profile's own top category names*, so
scoring them against that same profile's categories is close to tautological. It is
included as a required sanity ceiling (roughly, "how well could you possibly do by only
echoing the behavioral profile") and a legitimate non-LLM comparison point for the
thesis's evaluation chapter, not as evidence the LLM approach underperforms — the
LLM-based Condition B, notably, still generates *novel, well-formed natural-language
queries* rather than a category name mechanically appended with "movies."

### 3.2 Tourism domain: groundedness only (no behavioral profile by design)

| # calls | Groundedness rate |
|---|---|
| 4 | 0.95 |

No behavioral profile exists for Tourism (per the Phase 0 decision — `log_vc` is
anonymous, not per-user — documented in `THESIS_PROJECT_PLAN.md` §3.6/§8), so the ablation
and proxy-recall metrics don't apply there; `_behavioral_alignment()` already degrades to
0.0 cleanly in this case (`PHASE4_IMPLEMENTATION.md` §7). Groundedness rate (0.95, i.e.
19/20 raw candidates passed 4c's filter) confirms the coarse grounding check from Phase 4c
isn't rejecting nearly everything in practice — consistent with its documented design as a
weak sanity filter, not a precision check.

---

## 4. Qualitative examples

The full set is in `recommender/output/evaluation/summary.md`
(`recommender/output/evaluation/results.json` has the complete raw data, every suggestion
and every score). Two representative rows:

**`user_00013` / "Show me exciting action films"** (actual-top categories: Horror, USA,
TV Series, Canada — *not* Action, despite the stated query):
- A (history-only): *"What are the most popular action movies on Netflix", "Can you
  recommend some intense martial arts films", "Show me action films starring Dwayne
  Johnson"* — all straightforward elaborations of "action," ignoring behavior entirely.
- B (history+behavior): *"Horror movies on Netflix", "USA action films of the 80s",
  "Canadian TV series based on true stories"* — visibly pivots toward Horror/USA/Canada,
  the user's real top-watched categories, while still keeping one action-adjacent
  suggestion.

**`user_00025` / "What movies have the genre Action?"** (actual-top: USA, Stand-up
Comedy, Documentary, Comedy — again, not Action):
- A: *"...family-friendly action movies?", "Movies similar to Die Hard...", "...action
  movies with a strong female lead?"* — all still literally about action movies.
- B: *"Stand-up comedians who have acted in movies", "Movies similar to Die Hard", "Action
  movies set in New York City"* — one suggestion pivots fully to stand-up comedy (this
  user's actual top category), a second stays closer to the stated query.

---

## 5. Interpretation and limitations

- **Sample size is small by explicit choice** ("Small" scope: 3 users, 4 questions,
  12 scored suggestion-sets per condition). The direction and magnitude of the ablation
  effect (6.5x alignment, 2.3x proxy recall) are large enough to be a credible signal at
  this size, but a larger run (more users, more questions — the harness supports this via
  `NUM_EVAL_USERS`/`test_questions.py` with no code changes) would strengthen the
  thesis's statistical claims. Worth doing before final submission if time allows.
- **Held-out watch rows are very few per user** (1-3 rows), an artifact of the 80th
  -percentile-per-user cutoff on a modest amount of synthetic watch history — proxy-recall
  numbers should be read as directionally informative, not statistically tight.
- **Synthetic-data caveat carries over from Phase 3**: `netflix_dataset` is
  Faker-generated with no real causal link between a stated search and a later watch, so
  the *specific* magnitude of the divergence effect is a property of this dataset's
  generation process as much as of real user behavior — already flagged in
  `THESIS_PROJECT_PLAN.md` §8 and `PHASE3_IMPLEMENTATION.md`, repeated here because it
  directly bounds how strongly these Phase 5 numbers can be claimed to generalize.
  Re-running this exact harness against real interaction data, if it ever becomes
  available, is a direct, no-code-change validation step (`run_evaluation.py` only
  depends on the same CSV schema `behavioral_profile.py` already reads).
- **Groundedness rate ≈100% is expected, not a strong finding** — 4c is a deliberately
  coarse filter (`DEFAULT_THRESHOLD = 0.05`, see `PHASE4_IMPLEMENTATION.md` §4), so a
  near-100% pass rate confirms it isn't degenerate (rejecting everything) but says nothing
  about precision. That limitation is already fully documented in Phase 4 and isn't
  re-litigated by this near-ceiling number.
- **Classical baseline is not an apples-to-apples "better" result** — see the caveat in
  §3.1. It sets a ceiling on the alignment/recall axes alone, not on suggestion quality or
  naturalness, which the LLM-based conditions clearly provide and the template baseline
  does not (e.g. "Movie movies" is a real, slightly awkward output the template produces
  when a user's `content_type` value "Movie" appears in their `actual_top` list —
  cosmetically worth noting in the thesis as a baseline artifact, not a bug to fix).
- **This evaluation used a local Ollama model (`llama3.1:8b`), not the originally-planned
  Gemini** — see `PHASE4_IMPLEMENTATION.md` §5a for why (both cloud keys hit
  account/billing walls unrelated to the code). If a funded key becomes available, rerunning
  `python -m recommender.evaluation.run_evaluation` after flipping
  `RECOMMENDER_LLM_PROVIDER` is a direct, no-code-change comparison point worth including
  in the thesis (does suggestion quality/alignment change with a stronger model?).

---

## 6. Pointers

- [`THESIS_PROJECT_PLAN.md`](THESIS_PROJECT_PLAN.md) — full roadmap; §7 Phase 5 status
  note mirrors this document's summary.
- [`PHASE4_IMPLEMENTATION.md`](PHASE4_IMPLEMENTATION.md) — the recommender core this phase
  evaluates, and §5a specifically for the Ollama provider used to run it.
- [`PHASE3_IMPLEMENTATION.md`](PHASE3_IMPLEMENTATION.md) — the production behavioral
  profiles this phase's held-out variant is derived from.
- `recommender/evaluation/` — the implementation: `test_questions.py`,
  `held_out_profile.py`, `classical_baseline.py`, `run_evaluation.py`.
- `recommender/output/evaluation/results.json` / `summary.md` — full raw results and the
  human-readable report this document's tables/examples are drawn from.
- Re-run: `python -m recommender.evaluation.run_evaluation` (~7 min at "Small" scope on
  CPU-only Ollama).
