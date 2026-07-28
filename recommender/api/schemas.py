"""Phase 2 API contract (docs/THESIS_PROJECT_PLAN.md SS7 Phase 2).

`interaction_data`'s exact shape is an open dependency (SS8: depends on what the
bachelor students' external app actually logs per user) -- kept as a free-form
dict placeholder until that's confirmed.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    user_id: str
    domain: str
    query_text: str
    generated_sparql: Optional[str] = None
    result_summary: Optional[Any] = None
    interaction_data: Optional[dict] = None


class RecommendResponse(BaseModel):
    suggestions: list[str] = Field(default_factory=list)
