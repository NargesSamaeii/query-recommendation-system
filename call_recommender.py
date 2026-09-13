"""Example client for the recommender API's POST /recommend and POST /rate endpoints.

Sends every field defined in recommender/api/schemas.py:RecommendRequest, using a
real behavioral-profile user_id (recommender/output/behavioral_profiles/) so the
Phase 3 behavioral signal actually kicks in. Then rates the first returned
suggestion, demonstrating the Phase 7 live star-rating flow: the /recommend
response's query_log_id is passed back into /rate so the rating can be joined to
the request that produced the suggestion.

Run the API first (`python main.py`), then: python call_recommender.py
"""

import requests

BASE_URL = "http://127.0.0.1:8000"

payload = {
    "user_id": "user_00001",
    "domain": "movie",
    "query_text": "Show me sci-fi movies from the last 5 years",
    "generated_sparql": (
        "SELECT ?movie ?title WHERE { "
        "?movie a :Movie ; :title ?title ; :genre :SciFi ; :year ?year . "
        "FILTER(?year >= 2021) }"
    ),
    "result_summary": {"row_count": 12},
    "interaction_data": {"device_type": "web", "action": "search"},
}

if __name__ == "__main__":
    response = requests.post(f"{BASE_URL}/recommend", json=payload)
    response.raise_for_status()
    recommendation = response.json()
    print(recommendation)

    if recommendation["suggestions"]:
        rate_payload = {
            "user_id": payload["user_id"],
            "domain": payload["domain"],
            "suggestion": recommendation["suggestions"][0],
            "stars": 5,
            "query_log_id": recommendation["query_log_id"],
        }
        rate_response = requests.post(f"{BASE_URL}/rate", json=rate_payload)
        rate_response.raise_for_status()
        print(rate_response.json())
