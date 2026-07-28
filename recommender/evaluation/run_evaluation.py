"""Phase 5: evaluation harness for the query recommender core.

Runs the real, already-verified Phase 4 pipeline (recommender/core/) against a small,
fixed set of hand-picked test questions per domain (test_questions.py) and reports:

- schema-groundedness rate (4c's filter_grounded pass rate over the raw candidate pool)
  -- the "suggestion-answerability" analog to ADBIS_2026's SPARQL-correctness table.
- the core ablation this thesis is built around: query-history-only ("Condition A", plain
  GQR) vs. query-history + behavioral-profile ("Condition B", RA-GQR + this thesis's
  stated-vs-actual signal), scored on the same two axes 4d's own ranking already uses
  (history-similarity, behavioral-alignment) plus a proxy-recall check against each eval
  user's held-out watch history (held_out_profile.py).
- a non-LLM classical baseline (classical_baseline.py) for comparison.

Purely additive: does not call handle_recommend() or touch the shared query_log.db used
by the live API/harness (docs/THESIS_PROJECT_PLAN.md SS7 Phase 5). Run as:
    python -m recommender.evaluation.run_evaluation
"""

import json
import logging
import statistics
from pathlib import Path

import pandas as pd

from ..core.generation import generate_candidates
from ..core.ranking import _behavioral_alignment, _history_similarity, _tokenize, rank_and_diversify
from ..core.retrieval import retrieve_similar_queries
from ..core.validation import filter_grounded
from .classical_baseline import generate_baseline_suggestions
from .held_out_profile import build_held_out_profile, held_out_category_tokens
from .test_questions import MOVIE_TEST_QUESTIONS, TOURISM_TEST_QUESTIONS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("recommender.evaluation")

_ROOT = Path(__file__).resolve().parents[2]
_PROFILES_DIR = _ROOT / "recommender" / "output" / "behavioral_profiles"
_SEARCH_LOGS_PATH = _ROOT / "netflix_dataset" / "search_logs.csv"
_OUTPUT_DIR = _ROOT / "recommender" / "output" / "evaluation"

NUM_EVAL_USERS = 3
CUTOFF_QUANTILE = 0.8
NUM_CANDIDATES = 5


def select_eval_users(n=NUM_EVAL_USERS):
    """Movie users with a real profile, >=5 real search_logs rows (so retrieval has real
    history to seed from), and jaccard_similarity == 0 (sharpest stated-vs-actual
    divergence, for the clearest possible ablation contrast). Sorted by user_id for a
    reproducible, deterministic pick."""
    search_counts = pd.read_csv(_SEARCH_LOGS_PATH, usecols=["user_id"])["user_id"].value_counts()

    candidates = []
    for path in sorted(_PROFILES_DIR.glob("profile_*.json")):
        with open(path, "r", encoding="utf-8") as f:
            profile = json.load(f)
        user_id = profile["user_id"]
        jaccard = (profile.get("divergence") or {}).get("jaccard_similarity")
        if jaccard == 0 and search_counts.get(user_id, 0) >= 5:
            candidates.append(user_id)
    return sorted(candidates)[:n]


def _seed_history(user_id, cutoff_date):
    """This user's real pre-cutoff search_logs.csv rows, shaped for
    retrieve_similar_queries(..., history=...) -- keeps the shared query_log.db untouched."""
    search = pd.read_csv(_SEARCH_LOGS_PATH, parse_dates=["search_date"])
    user_search = search[(search["user_id"] == user_id) & (search["search_date"] <= cutoff_date)]
    return [{"query_text": q} for q in user_search["search_query"].tolist()]


def _proxy_hit(suggestions, ground_truth_tokens):
    if not ground_truth_tokens:
        return None
    return any(_tokenize(s) & ground_truth_tokens for s in suggestions)


def _safe_generate(query_text, similar_queries, behavioral_profile, domain):
    try:
        return generate_candidates(query_text, similar_queries, behavioral_profile, domain, num_candidates=NUM_CANDIDATES)
    except Exception as exc:  # LLM call failure shouldn't kill the whole eval run
        logger.warning("Candidate generation failed for domain=%s query=%r: %s", domain, query_text, exc)
        return []


def run_movie_ablation(user_ids):
    per_call = []
    baseline_rows = []

    for user_id in user_ids:
        profile, held_out_watch, cutoff_date = build_held_out_profile(user_id, CUTOFF_QUANTILE)
        if profile is None:
            logger.warning("No watch history for %s, skipping", user_id)
            continue
        ground_truth_tokens = held_out_category_tokens(held_out_watch)
        history = _seed_history(user_id, cutoff_date)
        logger.info("Eval user %s: cutoff=%s, held_out_watch_rows=%d, seeded_history=%d",
                    user_id, cutoff_date, len(held_out_watch), len(history))

        baseline_suggestions = generate_baseline_suggestions(profile)
        baseline_grounded = filter_grounded(baseline_suggestions, "movie") if baseline_suggestions else []
        baseline_rows.append({
            "user_id": user_id,
            "suggestions": baseline_suggestions,
            "grounded_count": len(baseline_grounded),
            "candidate_count": len(baseline_suggestions),
            "behavioral_alignment": _mean(_behavioral_alignment(s, profile) for s in baseline_suggestions),
            "proxy_hit": _proxy_hit(baseline_suggestions, ground_truth_tokens),
        })

        for question in MOVIE_TEST_QUESTIONS:
            similar_queries = retrieve_similar_queries(user_id, question, domain="movie", history=history)

            for condition, cond_profile in (("A_history_only", None), ("B_history_plus_behavior", profile)):
                candidates = _safe_generate(question, similar_queries, cond_profile, "movie")
                grounded = filter_grounded(candidates, "movie") if candidates else []
                suggestions = rank_and_diversify(grounded, similar_queries, cond_profile, top_n=3)

                per_call.append({
                    "user_id": user_id,
                    "question": question,
                    "condition": condition,
                    "candidate_count": len(candidates),
                    "grounded_count": len(grounded),
                    "suggestions": suggestions,
                    # scored against the REAL held-out profile regardless of condition --
                    # this is the ground-truth measurement, not what the pipeline saw.
                    "behavioral_alignment": _mean(_behavioral_alignment(s, profile) for s in suggestions),
                    "history_similarity": _mean(_history_similarity(s, similar_queries) for s in suggestions),
                    "proxy_hit": _proxy_hit(suggestions, ground_truth_tokens),
                })

    return per_call, baseline_rows


def run_tourism_pass():
    per_call = []
    for question in TOURISM_TEST_QUESTIONS:
        similar_queries = retrieve_similar_queries("tourism_demo_user", question, domain="tourism", history=[])
        candidates = _safe_generate(question, similar_queries, None, "tourism")
        grounded = filter_grounded(candidates, "tourism") if candidates else []
        suggestions = rank_and_diversify(grounded, similar_queries, None, top_n=3)
        per_call.append({
            "question": question,
            "candidate_count": len(candidates),
            "grounded_count": len(grounded),
            "suggestions": suggestions,
        })
    return per_call


def _mean(values):
    values = list(values)
    return round(statistics.mean(values), 3) if values else 0.0


def _rate(numerator_total, denominator_total):
    return round(numerator_total / denominator_total, 3) if denominator_total else 0.0


def aggregate_movie(per_call, baseline_rows):
    by_condition = {}
    for condition in ("A_history_only", "B_history_plus_behavior"):
        rows = [r for r in per_call if r["condition"] == condition]
        hits = [r["proxy_hit"] for r in rows if r["proxy_hit"] is not None]
        by_condition[condition] = {
            "n_calls": len(rows),
            "groundedness_rate": _rate(sum(r["grounded_count"] for r in rows), sum(r["candidate_count"] for r in rows)),
            "behavioral_alignment_at3": _mean(r["behavioral_alignment"] for r in rows),
            "history_similarity_at3": _mean(r["history_similarity"] for r in rows),
            "proxy_recall_at3": _rate(sum(hits), len(hits)) if hits else None,
        }

    baseline_hits = [r["proxy_hit"] for r in baseline_rows if r["proxy_hit"] is not None]
    by_condition["classical_baseline"] = {
        "n_calls": len(baseline_rows),
        "groundedness_rate": _rate(sum(r["grounded_count"] for r in baseline_rows), sum(r["candidate_count"] for r in baseline_rows)),
        "behavioral_alignment_at3": _mean(r["behavioral_alignment"] for r in baseline_rows),
        "proxy_recall_at3": _rate(sum(baseline_hits), len(baseline_hits)) if baseline_hits else None,
    }
    return by_condition


def aggregate_tourism(per_call):
    return {
        "n_calls": len(per_call),
        "groundedness_rate": _rate(sum(r["grounded_count"] for r in per_call), sum(r["candidate_count"] for r in per_call)),
    }


def write_summary_md(movie_agg, tourism_agg, movie_per_call, tourism_per_call, user_ids, path):
    lines = ["# Phase 5 Evaluation Summary\n"]
    lines.append(f"Eval users (Movie): {', '.join(user_ids)}\n")

    lines.append("## Movie domain: ablation + classical baseline\n")
    lines.append("| Condition | # calls | Groundedness rate | Behavioral alignment@3 | History similarity@3 | Proxy recall@3 |")
    lines.append("|---|---|---|---|---|---|")
    for key, label in (
        ("A_history_only", "A: history-only (plain GQR)"),
        ("B_history_plus_behavior", "B: history + behavior (this thesis)"),
        ("classical_baseline", "Classical baseline (non-LLM template)"),
    ):
        row = movie_agg[key]
        lines.append(
            f"| {label} | {row['n_calls']} | {row['groundedness_rate']} | "
            f"{row['behavioral_alignment_at3']} | {row.get('history_similarity_at3', '-')} | "
            f"{row['proxy_recall_at3']} |"
        )

    lines.append("\n## Tourism domain: groundedness only (no behavioral profile by design)\n")
    lines.append(f"- # calls: {tourism_agg['n_calls']}, groundedness rate: {tourism_agg['groundedness_rate']}\n")

    lines.append("## Representative qualitative examples (Movie)\n")
    seen_questions = set()
    for row in movie_per_call:
        key = (row["user_id"], row["question"])
        if key in seen_questions:
            continue
        pair = [r for r in movie_per_call if r["user_id"] == row["user_id"] and r["question"] == row["question"]]
        if len(pair) < 2:
            continue
        seen_questions.add(key)
        a = next(r for r in pair if r["condition"] == "A_history_only")
        b = next(r for r in pair if r["condition"] == "B_history_plus_behavior")
        lines.append(f"**{row['user_id']} / \"{row['question']}\"**\n")
        lines.append(f"- A (history-only): {a['suggestions']}")
        lines.append(f"- B (history+behavior): {b['suggestions']}\n")

    lines.append("## Representative qualitative examples (Tourism)\n")
    for row in tourism_per_call:
        lines.append(f"- \"{row['question']}\" -> {row['suggestions']}")

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    user_ids = select_eval_users()
    logger.info("Selected eval users: %s", user_ids)
    if not user_ids:
        raise RuntimeError("No eligible eval users found (need profile + >=5 search_logs rows + jaccard==0)")

    movie_per_call, baseline_rows = run_movie_ablation(user_ids)
    tourism_per_call = run_tourism_pass()

    movie_agg = aggregate_movie(movie_per_call, baseline_rows)
    tourism_agg = aggregate_tourism(tourism_per_call)

    results = {
        "config": {
            "eval_users": user_ids,
            "cutoff_quantile": CUTOFF_QUANTILE,
            "num_candidates": NUM_CANDIDATES,
            "movie_questions": MOVIE_TEST_QUESTIONS,
            "tourism_questions": TOURISM_TEST_QUESTIONS,
        },
        "movie": {"per_call": movie_per_call, "baseline": baseline_rows, "aggregate": movie_agg},
        "tourism": {"per_call": tourism_per_call, "aggregate": tourism_agg},
    }

    (_OUTPUT_DIR / "results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    write_summary_md(movie_agg, tourism_agg, movie_per_call, tourism_per_call, user_ids, _OUTPUT_DIR / "summary.md")

    logger.info("Wrote %s and %s", _OUTPUT_DIR / "results.json", _OUTPUT_DIR / "summary.md")
    print("\n--- Movie aggregate ---")
    print(json.dumps(movie_agg, indent=2))
    print("\n--- Tourism aggregate ---")
    print(json.dumps(tourism_agg, indent=2))


if __name__ == "__main__":
    main()
