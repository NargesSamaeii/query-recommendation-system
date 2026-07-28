"""Phase 2: persistent, user-keyed query log store backing the recommender API.

Every /recommend call is appended here; Phase 4a's query-log retrieval step
reads from this table (docs/THESIS_PROJECT_PLAN.md SS7 Phase 2/4a).
"""

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "output" / "query_log.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS query_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    query_text TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    generated_sparql TEXT,
    result_summary TEXT
);
CREATE INDEX IF NOT EXISTS idx_query_log_user_domain ON query_log(user_id, domain);
"""


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


def log_query(user_id, domain, query_text, generated_sparql=None, result_summary=None, timestamp=None):
    """Append one row to the log. Returns the new row's id.

    `result_summary` may be a dict/list (serialized to JSON text) or a plain string.
    """
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    if isinstance(result_summary, (dict, list)):
        result_summary = json.dumps(result_summary, ensure_ascii=False)
    with closing(_connect()) as conn:
        cur = conn.execute(
            "INSERT INTO query_log (user_id, domain, query_text, timestamp, generated_sparql, result_summary) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, domain, query_text, ts, generated_sparql, result_summary),
        )
        conn.commit()
        return cur.lastrowid


def get_user_history(user_id, domain=None, limit=50):
    """Most recent queries for a user, optionally scoped to one domain.

    This is the retrieval source for Phase 4a (embedding-based similar-query lookup).
    """
    with closing(_connect()) as conn:
        conn.row_factory = sqlite3.Row
        if domain:
            rows = conn.execute(
                "SELECT * FROM query_log WHERE user_id = ? AND domain = ? ORDER BY timestamp DESC LIMIT ?",
                (user_id, domain, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM query_log WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]
