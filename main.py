"""Entrypoint for running the recommender API standalone.

Run with: python main.py
(equivalent to `uvicorn recommender.api.app:app --reload --port 8000`)
OpenAPI docs auto-served at http://127.0.0.1:8000/docs.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("recommender.api.app:app", port=8000, reload=True)
