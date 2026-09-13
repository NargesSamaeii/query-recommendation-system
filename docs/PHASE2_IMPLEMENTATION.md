# Phase 2 Implementation Documentation

**Status:** implemented and verified · **Scope:** the recommender API contract and query log
store from [`THESIS_PROJECT_PLAN.md`](THESIS_PROJECT_PLAN.md) §7 Phase 2.

This document is a standalone implementation record for Phase 2 — what was built, how it works,
and how it was verified — kept separate from the roadmap document per the same convention as
[`PHASE0_PHASE1_IMPLEMENTATION.md`](PHASE0_PHASE1_IMPLEMENTATION.md) and
[`PHASE3_IMPLEMENTATION.md`](PHASE3_IMPLEMENTATION.md). Like Phase 3, this phase **is** part of
the actual thesis deliverable (§2a): it is the persistence and contract layer that Phase 4 (the
query recommender core) will be built inside.

---

## 1. Overview

Per the scope narrowing agreed with the professor (§2a), the thesis contribution is a
**standalone model + API** — any caller (the external app, or this repo's own dev
harness) integrates it by calling an endpoint, not by embedding UI. Phase 2's job is to stand up
that boundary before any recommendation logic exists behind it:

1. A concrete **request/response contract** for `POST /recommend`, so the interface is fixed and
   callers can integrate against it independently of when Phase 4's actual recommendation logic
   lands.
2. A **persistent, user-keyed query log** — nothing like it existed anywhere in the repo before
   this phase — that every `/recommend` call appends to, and that Phase 4a (query-log retrieval,
   RA-GQR-style) will read from.
3. A `user_id` field threaded through the internal dev/test harness (`gui_v2.py`) so it can
   exercise the same contract end-to-end during development, without depending on the external
   app's integration timeline.

Scope: domain-agnostic. The contract and log store accept any `domain` string; they don't encode
Movie- or Tourism-specific assumptions. (Phase 3's behavioral profile, which this API's
`interaction_data` field is expected to eventually carry a rendering of, is Movie-only today —
see [`PHASE3_IMPLEMENTATION.md`](PHASE3_IMPLEMENTATION.md).)

---

## 2. What was built

```
recommender/
├── query_log.py            # SQLite-backed query log store
├── api/
│   ├── schemas.py           # RecommendRequest / RecommendResponse (pydantic)
│   ├── service.py           # handle_recommend() — shared request handler
│   └── app.py                # FastAPI app exposing POST /recommend, GET /health
└── output/
    └── query_log.db          # SQLite file (gitignored-scale artifact, created at runtime)
```

`recommender/behavioral_profile.py` (Phase 3) is untouched and lives alongside these as a sibling
module in the same `recommender/` package.

### 2.1 The contract (`recommender/api/schemas.py`)

```python
class RecommendRequest(BaseModel):
    user_id: str
    domain: str
    query_text: str
    generated_sparql: Optional[str] = None
    result_summary: Optional[Any] = None
    interaction_data: Optional[dict] = None

class RecommendResponse(BaseModel):
    suggestions: list[str] = Field(default_factory=list)
```

This matches the roadmap's §7 Phase 2 contract sketch exactly, with one explicit gap left open:
`interaction_data` stays an untyped `Optional[dict]` rather than a fixed schema, because its real
shape depends on the **open dependency in §2a/§8** — what the external app
actually logs per user (queries, clicks, dwell time, etc.). That confirmation hasn't happened
yet, so typing it further now would mean guessing.

### 2.2 The query log store (`recommender/query_log.py`)

A single SQLite table, created on first use:

```sql
CREATE TABLE query_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    query_text TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    generated_sparql TEXT,
    result_summary TEXT
);
CREATE INDEX idx_query_log_user_domain ON query_log(user_id, domain);
```

Two functions:

- `log_query(user_id, domain, query_text, generated_sparql=None, result_summary=None,
  timestamp=None)` — appends one row. `timestamp` defaults to UTC now if not supplied.
  `result_summary` is JSON-serialized automatically if given a dict/list, so callers can pass
  structured summaries (e.g. `{"row_count": 12}`) without pre-serializing.
- `get_user_history(user_id, domain=None, limit=50)` — most recent rows for a user, optionally
  scoped to one domain. This is the function Phase 4a's embedding-based similar-query retrieval
  will call to build its candidate pool.

SQLite (not Postgres) was chosen for this store specifically because it's a single-file,
zero-infrastructure store appropriate for a thesis-scale log that doesn't need to be shared across
processes beyond one local API server — consistent with the project's existing pattern of using
the lightest tool that fits (e.g. JSON-per-user files in Phase 3, not a database).

### 2.3 The request handler (`recommender/api/service.py`)

```python
def handle_recommend(request: RecommendRequest) -> RecommendResponse:
    log_query(
        user_id=request.user_id,
        domain=request.domain,
        query_text=request.query_text,
        generated_sparql=request.generated_sparql,
        result_summary=request.result_summary,
    )
    return RecommendResponse(suggestions=[])
```

This function is the single place both the HTTP endpoint and the dev harness call — see §3 for
why. Its only job in this phase is to validate the request shape (via pydantic) and persist it;
`suggestions` is always `[]` here. Candidate generation is Phase 4 and will replace the final
line with the actual retrieval → LLM generation → schema-validation → ranking pipeline (roadmap
§7 Phase 4a–4d), without needing to change the function's signature or the contract.

### 2.4 The FastAPI app (`recommender/api/app.py`)

```python
app = FastAPI(title="Query Recommender API", version="0.1.0")

@app.get("/health")
def health(): ...

@app.post("/recommend", response_model=RecommendResponse)
def recommend(request: RecommendRequest) -> RecommendResponse:
    return handle_recommend(request)
```

Run with `uvicorn recommender.api.app:app --reload --port 8000` from the repo root (so
`recommender` resolves as a package). OpenAPI docs are auto-served at `/docs` — this satisfies
the roadmap's §7 Phase 4e note to "document it with an OpenAPI spec so integration doesn't
require reading the source," done early since FastAPI generates it for free from the pydantic
models above.

### 2.5 Harness integration (`web_app/nl2sparql/gui_v2.py`)

Three changes:

1. **Import path**: `recommender/` lives at the repo root, a sibling of `web_app/`, not a
   subpackage of it. `gui_v2.py` now inserts `Path(__file__).resolve().parents[2]` (the repo
   root) onto `sys.path` before importing `recommender.api.schemas`/`recommender.api.service`,
   guarded by a `try/except ImportError` so the rest of the harness still works if the
   `recommender` package isn't importable for some reason.
2. **User picker**: a new "👤 User" sidebar section (placed right after domain selection) with a
   text input bound to `st.session_state.user_id`, defaulting to `"user_00001"` — chosen to match
   the Movie-domain behavioral-profile id scheme (`recommender/output/behavioral_profiles/
   profile_user_00001.json`, …) so a developer can immediately cross-reference a Phase 3 profile
   with the id typed here.
3. **Post-query call**: after `process_question()` returns and results are displayed, the harness
   builds a `RecommendRequest` from the just-answered question (`user_id` from the sidebar,
   `domain` from `st.session_state.active_domain`, `query_text` the question itself,
   `generated_sparql` from `results["sparql_query"]`, `result_summary` a `{"row_count": ...}`
   dict derived from `results["query_results"]["results"]["bindings"]`), calls
   `handle_recommend()`, and renders a new "💡 Suggested Follow-up Queries" section. Since
   `suggestions` is always empty right now, this section currently shows a caption — *"(Phase 4
   recommender not implemented yet — this query was logged for it.)"* — instead of a suggestion
   list. The call is wrapped in try/except so a recommender-side failure never breaks the
   pipeline-results display the rest of the harness depends on.

---

## 3. Design decision: in-process call, not HTTP, from the harness

The roadmap's Phase 2 bullet reads: *"thread a `user_id` parameter through
`NL2SPARQLPipeline.answer_question()` so it can exercise the same API contract end-to-end during
development."* Read literally, this could mean the harness should make a real HTTP `POST
http://localhost:8000/recommend` call to a separately-running `uvicorn` process.

That was deliberately not what was implemented. Instead, `handle_recommend()` is a plain Python
function in `recommender/api/service.py`, imported directly by both `recommender/api/app.py` (for
the real HTTP endpoint) and `gui_v2.py` (for the harness). Reasoning:

- **Same contract either way.** The request/response *shape* — the actual thing "exercising the
  contract" is meant to validate — is identical whether it's invoked over HTTP or as a direct
  function call, since both paths go through the same `RecommendRequest`/`RecommendResponse`
  pydantic models and the same `handle_recommend()` logic.
- **Less development friction.** Requiring a Streamlit developer to also keep a second `uvicorn`
  process running, healthy, and pointed at the same `query_log.db`, just to see a "suggestions"
  section render during `streamlit run`, is friction the contract doesn't need to impose. Also
  `NL2SPARQLPipeline.answer_question()` itself was not modified to take a `user_id` — the
  recommender call happens in `gui_v2.py` *after* `answer_question()` returns, because it needs
  the finished SPARQL query and result count as inputs, which don't exist until the pipeline has
  already run.
- **The real HTTP path still exists and was verified independently** (§4) — external callers
  (the external app) are unaffected by this choice; they only ever see the HTTP surface.

If a future need arises for the harness to test the *actual* HTTP transport (e.g. once
Phase 4 adds latency/timeout behavior worth exercising realistically), swapping the harness's
direct call for a `requests.post(...)` call is a small, isolated change — the contract itself
doesn't move.

---

## 4. Verification performed

**HTTP path**: started `uvicorn recommender.api.app:app --port 8000` from the repo root.

```
POST /recommend  {"user_id":"user_00001","domain":"movie","query_text":"Action movies","result_summary":{"count":3}}
→ 200 {"suggestions":[]}

GET /health
→ 200 {"status":"ok"}
```

Confirmed the corresponding row landed in `recommender/output/query_log.db`:

```
{'id': 1, 'user_id': 'user_00001', 'domain': 'movie', 'query_text': 'Action movies',
 'timestamp': '2026-07-25T15:19:10.007544+00:00', 'generated_sparql': None,
 'result_summary': '{"count": 3}'}
```

**In-process path (mirroring how `gui_v2.py` imports it)**: from a working directory of
`web_app/` (matching where Streamlit actually runs from), inserted the repo root onto `sys.path`
exactly as `gui_v2.py`'s `Path(__file__).resolve().parents[2]` does, imported
`recommender.api.service.handle_recommend`, and called it with a second sample request. Confirmed
a second row (`id=2`, `user_id="user_00002"`) was appended to the same `query_log.db` — proving
the import resolution the harness relies on actually works from its real runtime working
directory, not just from the repo root.

**Syntax/import check on `gui_v2.py`** after the edits: `ast.parse()` on the full file succeeded
(no syntax errors introduced by the new sidebar section or post-query call block).

Not done in this pass: a full manual Streamlit click-through of the new sidebar field and
suggestions section (no browser tool available in this environment — same limitation noted in
Phase 1's verification record). Worth a quick manual sanity pass before relying on this for a
live demo.

---

## 5. Interpretation and limitations

- **`suggestions` is always `[]`.** This is expected and correct for this phase — Phase 4 is
  where candidate generation happens. The contract, log store, and harness wiring are all in
  place specifically so Phase 4 can be implemented purely inside `handle_recommend()` without
  touching the API surface or the harness again.
- **`interaction_data` is unused so far.** Neither `handle_recommend()` nor the harness populates
  or reads it yet; it exists in the contract as a placeholder for the still-unconfirmed shape of
  what the external app logs (§2a/§8). Until that's confirmed, Phase 3's `netflix_dataset`-derived
  behavioral profiles (keyed by the same `user_id` convention used in the harness's default) are
  the practical stand-in signal Phase 4 will condition on instead.
- **SQLite is a single-writer store.** Fine for one local dev API process; if this ever needs to
  serve concurrent write-heavy traffic (unlikely at thesis-demo scale), it would need revisiting —
  not a concern raised by the professor or anywhere in the roadmap, noted here only for
  completeness.
- **No authentication, rate-limiting, or input sanitization beyond pydantic's type validation** —
  appropriate for a thesis-scope local dev API, not for a production deployment. Not called out as
  a requirement anywhere in the roadmap, so intentionally out of scope.

---

## 6. Pointers

- [`THESIS_PROJECT_PLAN.md`](THESIS_PROJECT_PLAN.md) — full roadmap; §7 Phase 2 status note
  mirrors this document's summary.
- [`PHASE3_IMPLEMENTATION.md`](PHASE3_IMPLEMENTATION.md) — the behavioral-profile signal Phase 4
  will combine with this phase's query log.
- `recommender/api/service.py: handle_recommend()` — the single extension point for Phase 4;
  everything else in this phase (contract, log store, harness wiring) is meant to stay stable
  while that function's body grows from a stub into the real recommender pipeline.
- `recommender/query_log.py: get_user_history()` — the read-side function Phase 4a's
  RA-GQR-style retrieval step will call.
