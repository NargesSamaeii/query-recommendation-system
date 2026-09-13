"""Phase 7: live-evaluation report over real user star ratings (recommender/ratings.py).

Complementary to run_evaluation.py's offline ablation, which scores suggestions against
held-out historical logs. This script instead reports what real users actually said about
the suggestions they were shown -- mean stars and rating counts, per domain and per
suggestion, straight from the ratings.db populated by POST /rate
(docs/THESIS_PROJECT_PLAN.md SS7a Phase 7).

Purely additive: only reads recommender/output/ratings.db, does not call the recommender
or touch query_log.db. Run as:
    python -m recommender.evaluation.ratings_summary
"""

import json
import statistics
from collections import defaultdict
from pathlib import Path

from ..ratings import get_ratings

_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "recommender" / "output" / "evaluation"


def _mean(values):
    values = list(values)
    return round(statistics.mean(values), 3) if values else None


def summarize(ratings):
    """Mean stars and count, overall / per domain / per (domain, suggestion)."""
    by_domain = defaultdict(list)
    by_suggestion = defaultdict(list)
    for r in ratings:
        by_domain[r["domain"]].append(r["stars"])
        by_suggestion[(r["domain"], r["suggestion"])].append(r["stars"])

    return {
        "overall": {"n_ratings": len(ratings), "mean_stars": _mean(r["stars"] for r in ratings)},
        "by_domain": {
            domain: {"n_ratings": len(stars), "mean_stars": _mean(stars)}
            for domain, stars in sorted(by_domain.items())
        },
        "by_suggestion": [
            {"domain": domain, "suggestion": suggestion, "n_ratings": len(stars), "mean_stars": _mean(stars)}
            for (domain, suggestion), stars in sorted(by_suggestion.items())
        ],
    }


def write_summary_md(summary, path):
    lines = ["# Live Star-Rating Evaluation Summary\n"]
    lines.append(
        f"Total ratings collected: {summary['overall']['n_ratings']}, "
        f"overall mean stars: {summary['overall']['mean_stars']}\n"
    )

    lines.append("## By domain\n")
    lines.append("| Domain | # ratings | Mean stars |")
    lines.append("|---|---|---|")
    for domain, row in summary["by_domain"].items():
        lines.append(f"| {domain} | {row['n_ratings']} | {row['mean_stars']} |")

    lines.append("\n## By suggestion\n")
    lines.append("| Domain | Suggestion | # ratings | Mean stars |")
    lines.append("|---|---|---|---|")
    for row in summary["by_suggestion"]:
        lines.append(f"| {row['domain']} | {row['suggestion']} | {row['n_ratings']} | {row['mean_stars']} |")

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ratings = get_ratings()

    if not ratings:
        print("No ratings collected yet -- call POST /rate at least once (see call_recommender.py).")
        return

    summary = summarize(ratings)
    (_OUTPUT_DIR / "ratings_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_summary_md(summary, _OUTPUT_DIR / "ratings_summary.md")

    print(f"Wrote {_OUTPUT_DIR / 'ratings_summary.json'} and {_OUTPUT_DIR / 'ratings_summary.md'}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
