"""Phase 2: FastAPI skeleton for the recommender API (docs/THESIS_PROJECT_PLAN.md SS7 Phase 2).

Run with: uvicorn recommender.api.app:app --reload --port 8000
(from the repo root, so `recommender` resolves as a package)
OpenAPI docs auto-served at /docs.
"""

from fastapi import FastAPI

from . import schemas
from .service import handle_recommend

app = FastAPI(
    title="Query Recommender API",
    description="Standalone query recommender for preference-aware NL querying over VKGs.",
    version="0.1.0",
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/recommend", response_model=schemas.RecommendResponse)
def recommend(request: schemas.RecommendRequest) -> schemas.RecommendResponse:
    return handle_recommend(request)
