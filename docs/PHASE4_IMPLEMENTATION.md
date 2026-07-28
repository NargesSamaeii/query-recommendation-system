# Phase 4 Implementation Documentation

**Status:** implemented and verified end-to-end, including real LLM output (via a local
Ollama model — see §5a) · **Scope:** the query recommender core from
[`THESIS_PROJECT_PLAN.md`](THESIS_PROJECT_PLAN.md) §7 Phase 4.

This document is a standalone implementation record for Phase 4 — what was built, how it
works, and how it was verified — kept separate from the roadmap per the same convention as
[`PHASE0_PHASE1_IMPLEMENTATION.md`](PHASE0_PHASE1_IMPLEMENTATION.md),
[`PHASE2_IMPLEMENTATION.md`](PHASE2_IMPLEMENTATION.md), and
[`PHASE3_IMPLEMENTATION.md`](PHASE3_IMPLEMENTATION.md). This is **the thesis's actual
contribution** (§2a): everything before this phase (Phases 0-3) built the harness, API
shell, and behavioral-signal input this phase consumes.

---

## 1. Overview

Phase 4 turns the empty `suggestions: []` stub from Phase 2 into a real recommender,
implementing the four-stage pipeline the roadmap specifies:

```
4a  retrieval        -- this user's past queries most similar to the current one
4b  generation        -- LLM proposes a pool of candidate follow-up queries
4c  validation         -- drop candidates with no plausible link to the domain schema
4d  ranking            -- score + diversify what's left down to 3 final suggestions
```

All four live in a new `recommender/core/` package, orchestrated by
`recommender/api/service.py: handle_recommend()` — the same function Phase 2 already
wired into both the FastAPI endpoint and the `gui_v2.py` harness, so no new integration
points were needed; `suggestions` simply stopped being hardcoded to `[]`.

**No real LLM API key was available in this environment** (see the professor-thesis-plan
conversation this session started from — `.env` only had DB passwords, `config.yaml`'s
`api_key` was empty, and the configured local Mistral GGUF path pointed at a different
machine, `C:\Users\dhami\...`). Per the user's explicit instruction, a **placeholder**
`GEMINI_API_KEY` was added to `.env` for now, to be replaced with a real key later. 4b was
therefore built and verified structurally (see §5) rather than against real Gemini output.

---

## 2. 4a — Query-log retrieval (`recommender/core/retrieval.py`)

`retrieve_similar_queries(user_id, query_text, domain=None, top_k=3, history_limit=200)`:

1. Pulls the user's query history from the Phase 2 SQLite log
   (`recommender.query_log.get_user_history()`), optionally scoped to one domain.
2. Excludes exact case-insensitive duplicates of the current query.
3. Embeds the current query plus every candidate history entry with
   `all-mpnet-base-v2` (`sentence-transformers`) — the same model already used
   elsewhere in `web_app` for embedding-based class/property extraction, reused rather
   than introducing a second model.
4. Ranks candidates by cosine similarity (embeddings are pre-normalized, so this is a
   plain dot product) and returns the top-k, each annotated with its `similarity` score.

This directly implements RA-GQR's retrieval step (QR2405.19749v2): the retrieved queries
become few-shot/context material for 4b's prompt, in place of generic hand-curated
examples.

**Cold start**: if the user has no other logged queries, returns `[]` — 4b's prompt
formatter renders this as `"(no prior queries from this user)"` and still functions (GQR's
whole premise is that it doesn't require historical data to work at all).

---

## 3. 4b — Candidate generation (`recommender/core/generation.py`)

`generate_candidates(query_text, similar_queries, behavioral_profile, domain, llm=None,
num_candidates=5)`:

1. `build_prompt()` assembles one prompt from three inputs, per the roadmap's GQR/RA-GQR-
   style structure:
   - the current query,
   - the retrieved similar past queries (§2), rendered as a bulleted list,
   - a compact rendering of the Phase 3 behavioral divergence
     (`profile["divergence"]["stated_top"]` / `["actual_top"]` / `["jaccard_similarity"]`),
     explicitly framed in the prompt as *"what this user says they want"* vs. *"what this
     user actually engages with, which may DIFFER."*
2. The LLM is asked for a **pool of 5** candidates (not the final 3) — deliberately more
   than needed, so 4c/4d have real material to filter/diversify from rather than always
   keeping all 3 by construction.
3. `_parse_suggestions()` strips numbering/bullets/quotes from the LLM's line-per-
   suggestion response format.

**LLM abstraction reuse**: rather than introducing a second provider-switching layer,
this imports `nl2sparql.llm_interface.create_llm` directly from `web_app` (with a
`sys.path` insert mirroring the pattern already used in `gui_v2.py` and
`recommender/core/validation.py`) — per the roadmap §8's own note that this should
"[use] the same per-stage-configurable LLM abstraction already in `config.yaml`."
`generation.py`'s own `_default_llm()` reads `RECOMMENDER_LLM_PROVIDER` (default
`gemini`) and optional `RECOMMENDER_LLM_MODEL`, then hands them to `create_llm(provider=
..., ...)`, so the recommender can run against Gemini, GPT (`openai`), Azure, or Mistral
without code changes — just an env var and that provider's API key. `llm` is still an
injectable parameter so tests don't need a real API call (see §5).

`recommender/core/generation.py` also now calls `load_dotenv()` itself (pointed at the
repo-root `.env`), rather than depending on `web_app`'s `Config` class having already
loaded it — this was a real bug caught during verification (§5): calling
`handle_recommend()` directly, without first constructing a `web_app` `Config` object,
left `GEMINI_API_KEY` unset even though `.env` had it, because nothing had called
`load_dotenv()` yet. `recommender/` needs to work standalone (e.g. `uvicorn
recommender.api.app:app` with no `web_app` code running at all), so it can't rely on that
side effect.

---

## 4. 4c — Schema-grounding validation (`recommender/core/validation.py`)

### 4.1 What the roadmap originally specified

*"Run each candidate query's implied entities/classes through the pipeline's own
`ClassRelevanceEvaluator`/`PropertyEvaluator` (or a lighter standalone check) to confirm
it's answerable against the currently loaded domain schema before it's ever shown to the
user"* — directly mitigating the hallucination/faithfulness risk documented in the
KGGLLMRecommendation roadmap paper and empirically observed in ADBIS_2026 (~30%
SPARQL-incorrectness rate on their factual question set).

### 4.2 Why the first two implementations were rejected

**Attempt 1 — reuse `ClassRelevanceEvaluator`'s embedding mode directly.** This method
uses *relative* thresholding: it keeps every class scoring `>= mean - std` across the
schema's own classes. With only 7-11 classes per domain, this reliably selects at least
one class for *any* input, including completely unrelated text. Verified directly:
`ClassRelevanceEvaluator(method="embedding").evaluate("Best pizza recipe", ...)` against
the Tourism schema returned a non-empty class list — i.e. "grounded: True" for a query
with nothing to do with tourism.

**Attempt 2 — an absolute cosine-similarity floor.** Computed raw cosine similarity
between the candidate query and each class's embedded description
(`EmbeddingEvaluator.build_class_description()`, same `all-mpnet-base-v2` model as 4a),
requiring the max score across all classes to clear a fixed floor. This was calibrated
against a small set of control (clearly off-topic) phrases and probe (genuinely in-domain)
phrases:

| Query | Domain | Max cosine similarity | Best-matching class |
|---|---|---|---|
| Top rated action movies from the 2010s | movie | 0.275 | Movie |
| Movies directed by Christopher Nolan | movie | 0.302 | Movie |
| Documentaries produced in Canada | movie | 0.288 | Country |
| Best pizza recipe (control) | movie | 0.175 | SubscriptionPlan |
| How to fix a flat tire (control) | movie | 0.094 | Country |
| **Churches in Verona** | tourism | 0.163 | Location |
| **Roman Churches in Verona** | tourism | 0.154 | Location |
| **Free Churches in Verona** | tourism | **0.092** | Location |
| Events happening this weekend | tourism | 0.401 | Event |
| Art categories available | tourism | 0.601 | ArtCategory |
| Best pizza recipe (control) | tourism | 0.064 | Tour |
| **How to fix a flat tire (control)** | tourism | **0.112** | Tour |
| Latest news about the stock market (control) | tourism | 0.004 | — |

The Movie domain separates cleanly (in-domain floor ≈0.275, control ceiling ≈0.175 — any
threshold in between works). **The Tourism domain does not**: *"Free Churches in
Verona"* — one of the professor's own three canonical example suggestions, quoted
verbatim in this document's §2 — scores **0.092**, *below* the off-topic control phrase
*"How to fix a flat tire"* at **0.112**. No single threshold can accept the former while
rejecting the latter. A z-score (relative-to-the-query's-own-mean/std) variant was also
tried and rejected for the same reason: with only 7-11 classes, the *maximum* of a small
sample is reliably 1.3-2.3 standard deviations above the mean regardless of whether the
query is on-topic — confirmed empirically (`"Best pizza recipe"` against the Movie schema
scored z=2.31, a *higher* z-score than several genuinely in-domain movie queries).

**Root cause**: both domains' m-schema class descriptions are extremely sparse —
generated purely from SHACL cardinality constraints (e.g. `"Art has exactly 1 Art Class
ID. Art has at least 1 Art Name."`), with no `rdfs:comment` descriptions and no
`sh:example` instance values in either source `.ttl` file. The Tourism ontology's
`Art`/`ArtCategory` classes carry essentially no text a general-purpose sentence
embedding could relate to English words like "church" — that correspondence only exists
via the literal Italian category value `"Chiese"` in the live database, which isn't
present anywhere in the schema metadata being embedded. (This is presumably why the real
NL2SPARQL pipeline's own entity-linking stage exists as a *separate*, LLM-driven step —
class-level embedding alone was never meant to resolve this kind of gap on its own.)

### 4.3 What shipped instead

Given that finding, `is_schema_grounded()` uses the absolute-cosine-floor mechanism from
Attempt 2, but with `DEFAULT_THRESHOLD = 0.05` — low enough to only reject genuinely
degenerate candidates (near-zero or negative similarity to *every* class in the schema,
like `"Latest news about the stock market"` at 0.004) while admitting everything else,
including borderline-but-valid phrasings like `"Free Churches in Verona"`. This is
explicitly a coarse sanity filter, not a precision hallucination guard — documented as
such directly in the module's docstring, and in the roadmap's Phase 4 status note.
`filter_grounded(candidates, domain)` applies it to a list, preserving order.

This is a genuine, reportable limitation for the thesis's evaluation chapter: **automatic
schema-grounding of natural-language candidate suggestions, at the class-description
level, was not achievable with acceptable precision given how sparse this project's
source ontologies are** — a stronger version would require enriching class descriptions
with real catalog/instance values pulled from the live Ontop SPARQL endpoints (a concrete,
scoped follow-up, not attempted here).

---

## 5. 4d — Ranking / diversity (`recommender/core/ranking.py`)

`rank_and_diversify(candidates, similar_queries, behavioral_profile, top_n=3,
diversity_penalty=0.5)`:

1. **Scoring** (`score_candidate()`): a weighted sum of two QRMOCCGA-inspired axes
   (s11042-023-15585-6), each normalized to `[0, 1]`:
   - `_history_similarity()` — max Jaccard word overlap between the candidate and any of
     the user's retrieved similar past queries (§2's output).
   - `_behavioral_alignment()` — fraction of the behavioral profile's `actual_top`
     interest categories (Phase 3) whose words appear in the candidate text. This is the
     concrete place the thesis's stated-vs-actual signal enters ranking: a candidate that
     textually references what the user *actually watches*, not just what they typed,
     scores higher on this axis.
2. **Diversification**: a greedy MMR-style loop — repeatedly pick the highest-scoring
   remaining candidate, penalized by its max Jaccard word overlap with already-selected
   picks (`diversity_penalty=0.5`), so the final 3 aren't near-duplicates of each other.

QRMOCCGA's own contribution (a cooperative co-evolutionary genetic algorithm) was
explicitly out of scope to reimplement, per the roadmap's own framing (§4.4) — only its
*feature ideas* (word-overlap/click-overlap similarity, a two-objective split) were
borrowed, exactly as planned.

---

## 6. Verification performed

**4a in isolation**: seeded `user_00001`'s query log with 4 varied movie queries via
`log_query()`, then called `retrieve_similar_queries("user_00001", "Show me exciting
action films", domain="movie", top_k=3)`. Correctly ranked `"Action movies"` (0.79
cosine) and `"Best action movies with high ratings"` (0.765) above `"Romantic comedies"`
(0.371), excluding unrelated seeded queries entirely.

**4b in isolation**: called `build_prompt()` directly and inspected the rendered prompt
text (confirmed all three input sections — current query, retrieved history, behavioral
divergence — render correctly for `user_00001`'s real Phase 3 profile). Called
`generate_candidates(..., llm=MockLLM())` with a hand-written mock returning a
numbered/bulleted list; confirmed `_parse_suggestions()` correctly stripped numbering,
bullets, and quotes down to 3 clean strings.

**4b against the real (placeholder-key) Gemini path**: confirmed `GeminiLLM()`
construction succeeds (the key is present, just not valid), and that `.generate()` fails
cleanly with `400 API key not valid ... reason: "API_KEY_INVALID"` — i.e. the integration
is correctly wired and will work as soon as a real key replaces the placeholder, without
any code changes.

**4c in isolation**: see the calibration table in §4.2. Final `is_schema_grounded()`
implementation re-verified against 4 cases: `"Free Churches in Verona"` (tourism) →
`True`, `"Roman Churches in Verona"` (tourism) → `True`, `"Top rated action movies"`
(movie) → `True`, `"Latest news about the stock market"` (tourism) → `False` — all
matching expected outcomes.

**4d in isolation**: fed a hand-built pool of 5 candidates (one near-duplicate of query
history, two behaviorally-aligned, one off-axis, one more history-similar) through
`rank_and_diversify(..., top_n=3)`. Correctly picked the history-similar candidate first,
then diversified into the two behaviorally-aligned candidates rather than picking a
near-duplicate of the first pick.

**Full chain, end-to-end, mocked LLM**: patched `recommender.core.generation.GeminiLLM`
with a mock returning 5 fixed candidates, then called the real
`recommender.api.service.handle_recommend()` (the actual production code path, not a
reimplementation) for `user_00001` / `movie` / *"Show me exciting action films."* Result
(note: after the later `create_llm`-factory migration described in §3, the equivalent
patch target is `recommender.core.generation._default_llm`, not `GeminiLLM` directly):

```
War documentaries produced in the USA
Crime thrillers with high ratings
Adventure movies set during wartime
```

The top-ranked suggestion is the one most strongly aligned with `user_00001`'s *actual*
top interest categories (`Movie, USA, Canada, Adventure, War` per their Phase 3 profile)
rather than a plain paraphrase of the stated query about "action films" — a concrete,
working demonstration of the thesis's central premise (conditioning on real behavior, not
just query text).

**Full chain, end-to-end, real HTTP, placeholder key**: started `uvicorn
recommender.api.app:app`, `POST /recommend` with the same request. Server log confirms
the full path executed (log → retrieval → generation attempt → the same
`API_KEY_INVALID` failure as above, caught and logged as a warning, not a crash) and the
HTTP response was `200 OK` with `{"suggestions": []}` — i.e. the degrade-gracefully
behavior in `handle_recommend()`'s `try/except` around candidate generation works over
the real transport, not just in-process.

**Not yet done**: a qualitative/quantitative evaluation of suggestion quality — that's
Phase 5, not Phase 4.

---

## 5a. Real-LLM verification (2026-07-28): Gemini/OpenAI keys blocked, Ollama used instead

Both cloud providers were dead ends in this environment: the `OPENAI_API_KEY` in `.env`
returns `insufficient_quota` (no billing configured on the account; `gpt-4` itself is also
not accessible to this key) and the `GEMINI_API_KEY` returns `RESOURCE_EXHAUSTED` with
`limit: 0` for every model's free tier (the key's Google project has no free-tier
allowance enabled — its `AQ.Ab8...` format also doesn't match a typical AI Studio key,
which normally starts `AIzaSy...`). Neither is a code problem; both need account/billing
fixes outside this repo before they can be used.

Rather than block Phase 5 on that, a **new `ollama` provider** was added to
`web_app/nl2sparql/llm_interface.py` (`OllamaLLM`, using `requests` against Ollama's
`/api/generate` HTTP endpoint — no API key, no quota) and wired into `create_llm()`
alongside the existing gemini/mistral/openai/azure providers. This was chosen over the
already-existing local `MistralLLM` class because that class depends on
`llama-cpp-python` (a non-trivial C++ build on Windows) plus a manually-downloaded Q2_K
quantized GGUF file (low quality); Ollama is a single Docker image with pre-optimized
quantization and no compilation step.

**Infrastructure**: a new `ollama` service was added to `docker-compose.yml` (image
`ollama/ollama`, port `11434:11434`, named volume `ollama-data` for model persistence,
consistent with the existing Postgres/Ontop services' pattern). `llama3.1:8b` (4.9GB) was
pulled into the container via `docker exec ollama ollama pull llama3.1:8b`. `.env` /
`.env.example` were updated: `RECOMMENDER_LLM_PROVIDER=ollama`,
`RECOMMENDER_LLM_MODEL=llama3.1:8b`, `OLLAMA_BASE_URL=http://localhost:11434`.

**Verified end-to-end against real output** (not mocked): both `generate_candidates()`
directly and the full production path `handle_recommend()` (the same function the FastAPI
endpoint and `gui_v2.py` harness both call) were run for `user_00001` / movie domain /
*"Show me exciting action films"*. `handle_recommend()` result:

```json
{
  "suggestions": [
    "War movies with high ratings on IMDB",
    "Movies that combine action and adventure genres",
    "Films starring actors from Canada or USA"
  ]
}
```

The top-ranked suggestion references *War* and the other two reference *Canada/USA* —
all three are in `user_00001`'s behavioral-profile `actual_top` categories
(`Movie, USA, Canada, Adventure, War`), not just a paraphrase of the stated query about
"action films." This is the same qualitative pattern already observed with the mocked-LLM
run in §6, now reproduced with genuine model output.

**Latency**: ~18-22s per `/recommend` call on this machine (CPU-only Docker container, no
GPU passthrough). Acceptable for offline Phase 5 evaluation runs, but worth noting as a
real deployment-latency concern distinct from suggestion quality — not addressed here.

**Remaining limitation**: this validates the *pipeline*, not the *provider* originally
planned (Gemini). If a funded Gemini/OpenAI key becomes available later, `RECOMMENDER_LLM_PROVIDER`
can be flipped back with no code changes — the abstraction was already provider-agnostic
before this change, Ollama is simply an additional option, not a replacement.

---

## 7. Interpretation and limitations

- **The 4c grounding check is intentionally weak** — see §4.3. This should be reported in
  the thesis as an explicit, empirically-justified limitation, not silently shipped as if
  it were the precision filter originally planned. The calibration table in §4.2 is
  itself a small but genuine piece of results-chapter material: it demonstrates a real
  failure mode (sparse ontology metadata undermining embedding-based grounding) with a
  concrete, professor-supplied example query.
- **4b is now verified against real LLM output** (§5a), via a local Ollama model rather
  than the originally-planned Gemini — both cloud keys available in this environment hit
  billing/quota walls unrelated to the code. Suggestion quality from `llama3.1:8b` looks
  sound on the one worked example so far; a systematic quality check across more
  users/queries is Phase 5's job, not this phase's.
- **`num_candidates=5` (the pool size 4b asks for) is an arbitrary choice**, not derived
  from data — worth a sensitivity check (e.g. pool sizes of 4/6/8) once real LLM output is
  available, since a larger pool gives 4d's diversification more to work with at the cost
  of more tokens per request.
- **The behavioral-alignment axis in 4d only works for the Movie domain today**, since
  Phase 3 profiles only exist for Movie users (per the Phase 0 decision that Tourism stays
  catalog-only) — `_behavioral_alignment()` correctly returns `0.0` when no profile
  exists, so Tourism recommendations degrade to history-similarity-only ranking rather
  than erroring, but this means the thesis's core "stated vs. actual" contribution is only
  demonstrable end-to-end on Movie, consistent with every earlier phase's own scoping note.

---

## 8. Pointers

- [`THESIS_PROJECT_PLAN.md`](THESIS_PROJECT_PLAN.md) — full roadmap; §7 Phase 4 status
  note mirrors this document's summary.
- [`PHASE2_IMPLEMENTATION.md`](PHASE2_IMPLEMENTATION.md) — the API contract and query log
  this phase reads from and is orchestrated through (`handle_recommend()`).
- [`PHASE3_IMPLEMENTATION.md`](PHASE3_IMPLEMENTATION.md) — the behavioral-profile signal
  4b's prompt and 4d's ranking both condition on.
- `recommender/core/` — the implementation: `retrieval.py` (4a), `generation.py` (4b),
  `validation.py` (4c, with the full calibration reasoning in its module docstring),
  `ranking.py` (4d).
- Phase 5 (evaluation, not yet started) is the next consumer of this phase's output — in
  particular the roadmap's planned ablation (query-history-only vs. +behavioral-profile
  ranking) is now directly runnable by toggling `behavior_weight` in
  `ranking.score_candidate()`.
