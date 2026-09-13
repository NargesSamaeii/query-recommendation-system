"""Live user-feedback store: star ratings on individual recommender suggestions.

Requested by the professor (2026-09-11 email) as a way to evaluate suggestions
directly from users, complementary to the offline Phase 5 ablation
(recommender/evaluation/run_evaluation.py), which scores against held-out
historical logs rather than live feedback. Mirrors query_log.py's SQLite
pattern (docs/THESIS_PROJECT_PLAN.md SS7a Phase 7).
"""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "output" / "ratings.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_log_id INTEGER,
    user_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    suggestion TEXT NOT NULL,
    stars INTEGER NOT NULL,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ratings_domain ON ratings(domain);
CREATE INDEX IF NOT EXISTS idx_ratings_query_log_id ON ratings(query_log_id);
"""


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


def add_rating(user_id, domain, suggestion, stars, query_log_id=None, timestamp=None):
    """Record one star rating (1-5) for one suggested follow-up query. Returns the new row's id."""
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    with closing(_connect()) as conn:
        cur = conn.execute(
            "INSERT INTO ratings (query_log_id, user_id, domain, suggestion, stars, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (query_log_id, user_id, domain, suggestion, stars, ts),
        )
        conn.commit()
        return cur.lastrowid


def get_ratings(domain=None, limit=1000):
    """Most recent ratings, optionally scoped to one domain -- the read side for the live
    rating-based evaluation report (recommender/evaluation/ratings_summary.py)."""
    with closing(_connect()) as conn:
        conn.row_factory = sqlite3.Row
        if domain:
            rows = conn.execute(
                "SELECT * FROM ratings WHERE domain = ? ORDER BY timestamp DESC LIMIT ?",
                (domain, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ratings ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
