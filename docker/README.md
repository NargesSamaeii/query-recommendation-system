# Phase 0 VKG stack (Movie + Tourism)

Brings up two Postgres databases and two Ontop SPARQL endpoints, one pair per domain, per
`docs/THESIS_PROJECT_PLAN.md` §7 Phase 0.

| Service | Purpose | Host port |
|---|---|---|
| `postgres-movie` | loads `netflix_dataset/*.csv` on first start | 5433 |
| `postgres-tourism` | restores `Verona_Tourism_Ontop/tourismdb_jan 1.backup` (PostGIS) on first start | 5434 |
| `ontop-movie` | SPARQL endpoint over `netfilx_sparql/` mapping+ontology | 8081 (`/sparql`) |
| `ontop-tourism` | SPARQL endpoint over `Verona_Tourism_Ontop/` mapping+ontology | 8082 (`/sparql`) |
| `ollama` | local LLM server for the recommender (Phase 4b), no API key/quota needed | 11434 |

## First-time setup

```bash
cp .env.example .env   # already done for local dev; edit if you want your own passwords

# The ontop/ontop image ships with no JDBC drivers under /opt/ontop/jdbc, so both ontop-*
# services will fail with "Cannot load the driver: org.postgresql.Driver" unless this jar is
# present (docker/jdbc/*.jar is gitignored -- fetch it once):
mkdir -p docker/jdbc
curl -sSL -o docker/jdbc/postgresql.jar \
  https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar

docker compose up -d
```

Postgres data loading/restoring only happens the *first* time each Postgres container starts
against an empty volume. To force a full reload later (e.g. after editing `docker/movie/init.sql`
or `docker/tourism/restore.sh`), you must drop the corresponding named volume first:

```bash
docker compose down
docker volume rm recomendation_system_postgres-movie-data      # or -tourism-data
docker compose up -d
```

`postgres-tourism`'s restore of the ~280MB dump can take several minutes on first start --
check progress with `docker compose logs -f postgres-tourism`.

## Verifying data loaded correctly

```bash
docker compose exec postgres-movie psql -U postgres -d netflix_vkg -c "SELECT count(*) FROM movies;"
docker compose exec postgres-movie psql -U postgres -d netflix_vkg -c "SELECT count(*) FROM watch_history;"
docker compose exec postgres-tourism psql -U postgres -d tourismdb -c "SELECT count(*) FROM art;"
docker compose exec postgres-tourism psql -U postgres -d tourismdb -c "SELECT count(*) FROM event;"
```

Expected row counts: `movies` 1040, `users` 10300, `watch_history` 105000, `search_logs` 26500,
`reviews` 15450, `recommendation_logs` 52000; `art` 41, `event` 1416, `calendar` 10640,
`location` 1600.

## Browsing the graphs visually

`docker/sparql-browser.html` is a dependency-free HTML page -- just double-click it to open in a
browser (no server needed). It talks directly to `localhost:8081`/`:8082` from the page's own
JavaScript, which works because both `ontop-*` services set `ONTOP_CORS_ALLOWED_ORIGINS: "*"`.
It has buttons for common queries (class list + instance counts, property usage, a raw triple
sample, the "Chiese" churches query) and a free-text query box for anything else.

## Smoke-testing the SPARQL endpoints

```bash
curl -s -G http://localhost:8081/sparql \
  --data-urlencode 'query=PREFIX : <http://www.semanticweb.org/exogame/ontologies/2026/4/untitled-ontology-57#> SELECT ?movie ?title WHERE { ?movie :title ?title } LIMIT 5' \
  -H "Accept: application/sparql-results+json"

curl -s -G http://localhost:8082/sparql \
  --data-urlencode 'query=PREFIX ex: <http://example.org/> SELECT ?cat ?name WHERE { ?cat a ex:ArtCategory ; ex:artcatname_it ?name } LIMIT 20' \
  -H "Accept: application/sparql-results+json"
```

The second query should return "Chiese" (churches) among the `ArtCategory` names -- matching
the professor's example question.

## Ollama (recommender LLM, Phase 4b)

`RECOMMENDER_LLM_PROVIDER=ollama` (the default in `.env.example`) points the recommender's
candidate-generation step at this local container instead of a paid Gemini/OpenAI key --
see `docs/PHASE4_IMPLEMENTATION.md` §5a for why. After `docker compose up -d`, pull the
model once (persisted in the `ollama-data` volume, not re-downloaded on restart):

```bash
docker exec ollama ollama pull llama3.1:8b
```

Swapping back to a real Gemini/OpenAI key later needs no code changes -- just change
`RECOMMENDER_LLM_PROVIDER`/`RECOMMENDER_LLM_MODEL` in `.env`.

## Secrets

Real passwords live only in the gitignored `.env` file at the repo root and are passed to
Ontop directly as `ONTOP_DB_USER`/`ONTOP_DB_PASSWORD`/`ONTOP_DB_URL` environment variables (see
`docker-compose.yml`) -- no `.properties` file with a plaintext password is used by this stack.
The pre-existing `netfilx_sparql/netflix_ontology.properties` file is a legacy/standalone-CLI
artifact, not consumed here; its plaintext password has been replaced with a `CHANGEME`
placeholder.

## Known limitations (Phase 0 scope)

- Tourism has **no per-user data** by design decision -- `log_vc` (anonymous VeronaCard visits)
  is not mapped. Tourism is catalog-query-only; Movie carries all user-selection/behavior work.
- `art_all.obda`'s `art-image-mapping`/`art-to-image-mapping` were dropped (the `art_images`
  table they referenced doesn't exist in the backup). `ex:ArtImage`/`ex:hasImage` stay declared
  in `art_all.ttl` but are unpopulated.
- The Netflix dataset has genuine duplicate id values baked in (a "teaching-ready" data-quality
  feature) -- table columns are intentionally *not* `PRIMARY KEY`/`UNIQUE`, so Ontop mappings
  may occasionally emit conflicting triples for the same generated IRI. This is a known,
  documented limitation of the synthetic dataset, not a mapping bug.
