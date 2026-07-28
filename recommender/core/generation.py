"""Phase 4b: LLM candidate generation for the query recommender core.

GQR/RA-GQR-style (docs/THESIS_PROJECT_PLAN.md SS7 Phase 4b, QR2405.19749v2): build one
prompt from (i) the current query, (ii) this user's retrieved similar past queries
(Phase 4a) as lexical/behavioral context, and (iii) a compact rendering of the Phase 3
stated-vs-actual behavioral divergence, then ask the LLM to generate 3 candidate
follow-up queries directly -- no query-log-trained model needed, which is GQR's whole
point (it solves cold start).

Reuses web_app's existing per-stage LLM abstraction (nl2sparql.llm_interface) rather than
introducing a second one, per docs/THESIS_PROJECT_PLAN.md SS8's own recommendation. Goes
through that module's `create_llm` factory (not a hardcoded provider class) so the
provider is switchable via RECOMMENDER_LLM_PROVIDER without code changes.
"""

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

# recommender/ must work standalone (e.g. via `uvicorn recommender.api.app:app`), so it
# can't rely on web_app's Config class having already called load_dotenv() -- do it here.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

_WEB_APP_ROOT = Path(__file__).resolve().parents[2] / "web_app"
if str(_WEB_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_WEB_APP_ROOT))

from nl2sparql.llm_interface import create_llm  # noqa: E402


def _default_llm():
    """Build the default LLM via web_app's multi-provider factory.

    Provider defaults to Gemini but is switchable to gpt/openai/azure/mistral via
    RECOMMENDER_LLM_PROVIDER, so the recommender can run against either provider without
    code changes. Model name defaults to each provider's own default unless
    RECOMMENDER_LLM_MODEL is set.
    """
    provider = os.getenv("RECOMMENDER_LLM_PROVIDER", "gemini")
    model_name = os.getenv("RECOMMENDER_LLM_MODEL")
    kwargs = {"model_name": model_name} if model_name else {}
    return create_llm(provider=provider, **kwargs)


def _format_similar_queries(similar_queries):
    if not similar_queries:
        return "(no prior queries from this user)"
    return "\n".join(f'- "{q["query_text"]}"' for q in similar_queries)


def _format_behavioral_summary(behavioral_profile):
    if not behavioral_profile:
        return "(no behavioral profile available for this user)"
    divergence = behavioral_profile.get("divergence", {})
    stated = ", ".join(divergence.get("stated_top") or []) or "(none)"
    actual = ", ".join(divergence.get("actual_top") or []) or "(none)"
    jaccard = divergence.get("jaccard_similarity")
    return (
        f"What this user says they want (stated, from past search queries): {stated}\n"
        f"What this user actually engages with (actual, from watch behavior): {actual}\n"
        f"Overlap between stated and actual (0 = no overlap, 1 = identical): "
        f"{jaccard if jaccard is not None else 'unknown'}"
    )


def build_prompt(query_text, similar_queries, behavioral_profile, domain, num_candidates=3):
    """Assemble the GQR/RA-GQR-style candidate-generation prompt.

    `num_candidates` can ask for more than the final 3 shown to the user -- Phase 4d
    (ranking.rank_and_diversify) then downselects from this larger pool, which gives
    diversification something real to choose between instead of always keeping all 3.
    """
    return f"""You are a query recommender for a natural-language search system over a {domain} knowledge graph.

A user just asked: "{query_text}"

Here are some of this user's past queries (most similar to the current one listed first):
{_format_similar_queries(similar_queries)}

Here is what is known about this user's real behavior, which may DIFFER from what they say they want:
{_format_behavioral_summary(behavioral_profile)}

Task: suggest exactly {num_candidates} follow-up queries this user would plausibly want to ask next.
Do not just paraphrase the current query -- each suggestion should narrow, broaden, or
pivot it in a genuinely useful direction. When the user's actual behavior diverges from
their stated query, let at least one suggestion lean toward what they actually engage
with, not just what they literally typed.

Respond with exactly {num_candidates} lines, each a single follow-up query and nothing else -- no
numbering, no explanation, no quotation marks.
"""


def _parse_suggestions(raw_response, expected=3):
    lines = [line.strip() for line in (raw_response or "").splitlines() if line.strip()]
    cleaned = []
    for line in lines:
        line = re.sub(r"^\d+[.)]\s*", "", line)  # strip leading "1. " / "1) "
        line = re.sub(r"^[-*]\s*", "", line)  # strip leading "- " / "* "
        line = line.strip("\"' ")
        if line:
            cleaned.append(line)
    return cleaned[:expected]


def generate_candidates(query_text, similar_queries, behavioral_profile, domain, llm=None, num_candidates=5):
    """Return up to `num_candidates` candidate follow-up query strings.

    `llm` is injectable (must expose `.generate(prompt) -> str`) for testing without a
    real API call; defaults to `_default_llm()` (Gemini unless RECOMMENDER_LLM_PROVIDER
    says otherwise). Defaults to a pool of 5 rather than the final 3 shown to the user --
    Phase 4c (validation) and 4d (ranking) need a pool to filter/select from.
    """
    if llm is None:
        llm = _default_llm()
    prompt = build_prompt(query_text, similar_queries, behavioral_profile, domain, num_candidates=num_candidates)
    raw_response = llm.generate(prompt)
    return _parse_suggestions(raw_response, expected=num_candidates)
