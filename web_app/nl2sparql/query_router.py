"""
Query routing helper.

Classifies a natural-language question into a route before SPARQL generation.
The router uses few-shot prompting and returns a small structured decision.
"""

import json
import logging
import re
from typing import Any, Dict, Optional


class QueryRouter:
    """LLM-based router that decides whether to use SPARQL or a non-SPARQL path."""

    def __init__(self, llm):
        self.llm = llm
        self.logger = logging.getLogger("nl2sparql.pipeline")
        self.last_prompt = None
        self.last_response = None

    def route(self, question: str, schema_summary: Optional[str] = None) -> Dict[str, Any]:
        """Return a routing decision with route, confidence, and reason."""
        prompt = self._build_prompt(question, schema_summary or "")
        self.last_prompt = prompt
        response_text = ""

        try:
            response_text = self.llm.generate(prompt, max_tokens=180)
        except Exception as exc:
            self.logger.warning("Query routing failed, defaulting to SPARQL: %s", exc)
            self.last_response = ""
            return {
                "route": "sparql",
                "confidence": 0.0,
                "reason": f"Routing failed: {exc}",
                "raw_response": "",
            }

        self.last_response = response_text
        parsed = self._parse_response(response_text)
        parsed["raw_response"] = response_text.strip()
        return parsed

    def _build_prompt(self, question: str, schema_summary: str) -> str:
        examples = """
Question: Which departments have more than 10 employees?
Route: sparql
Reason: A declarative graph query can answer this directly.

Question: Predict which products are likely to need maintenance next month.
Route: analytical
Reason: This asks for a forecast, so a statistical or ML workflow is needed.

Question: Show the top 5 suppliers and explain what factors may drive future delays.
Route: hybrid
Reason: This combines retrieval with an analytical explanation.
""".strip()

        schema_block = schema_summary.strip() if schema_summary.strip() else "(not provided)"

        return (
            "You decide which execution route best fits a user question in a hybrid querying system.\n\n"
            "Choose exactly one route:\n"
            "- sparql: answerable by querying the knowledge graph with SPARQL alone\n"
            "- analytical: requires prediction, forecasting, clustering, classification, ranking models, or other statistical/ML reasoning beyond SPARQL\n"
            "- hybrid: needs both SPARQL retrieval and analytical reasoning\n\n"
            "Do not use keyword matching. Decide from the overall task.\n"
            "Return ONLY valid JSON with keys: route, confidence, reason.\n\n"
            f"Few-shot examples:\n{examples}\n\n"
            f"Schema summary:\n{schema_block}\n\n"
            f"Question:\n\"\"\"{question}\"\"\"\n\n"
            "Return format example:\n"
            '{"route":"sparql","confidence":0.93,"reason":"..."}'
        )

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        default = {
            "route": "sparql",
            "confidence": 0.0,
            "reason": "Unparsed response; defaulted to SPARQL.",
        }
        if not response_text:
            return default

        cleaned = response_text.strip()
        # Try JSON first.
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return self._normalize_parsed(parsed)
        except Exception:
            pass

        # Try extracting the first JSON object from surrounding text.
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    return self._normalize_parsed(parsed)
            except Exception:
                pass

        # Fallback to label search.
        lowered = cleaned.lower()
        route = "sparql"
        if "analytical" in lowered:
            route = "analytical"
        elif "hybrid" in lowered:
            route = "hybrid"
        elif "sparql" in lowered:
            route = "sparql"

        reason = cleaned[:300]
        return {"route": route, "confidence": 0.0, "reason": reason}

    def _normalize_parsed(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        route = str(parsed.get("route", "sparql")).strip().lower()
        if route not in {"sparql", "analytical", "hybrid"}:
            route = "sparql"

        confidence = parsed.get("confidence", 0.0)
        try:
            confidence = float(confidence)
        except Exception:
            confidence = 0.0

        reason = str(parsed.get("reason", "")).strip()
        return {
            "route": route,
            "confidence": confidence,
            "reason": reason,
        }