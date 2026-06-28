"""
Audit logger — DORA-mandated record of every query and response.

DORA Article 30(3) requires financial entities to maintain logs of
AI-assisted decisions. This module writes every query/response pair
to a local SQLite database with a stable query_id for traceability.

Uses aiosqlite so all DB operations are non-blocking in the FastAPI
event loop.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import aiosqlite

from backend.config import settings

_DB_PATH = Path("data/audit.db")


async def init_db() -> None:
    """Create the audit table if it does not exist. Called at app startup."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                query_id        TEXT PRIMARY KEY,
                session_id      TEXT,
                timestamp       TEXT NOT NULL,
                question        TEXT NOT NULL,
                rewritten_query TEXT,
                answer          TEXT,
                sources         TEXT,   -- JSON array of source metadata
                confidence      INTEGER,
                flagged         INTEGER DEFAULT 0,
                duration_ms     INTEGER
            )
        """)
        await db.commit()


async def log_query(
    question: str,
    answer: str,
    sources: list,
    confidence: int,
    flagged: bool,
    duration_ms: int,
    session_id: Optional[str] = None,
    rewritten_query: Optional[str] = None,
) -> str:
    """Write one query+response record. Returns the query_id."""
    query_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    sources_json = json.dumps([
        {
            "document": s.source_file,
            "page": s.page_number,
            "articles": s.articles,
            "excerpt": s.text[:200],
        }
        for s in sources
    ])

    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO audit_log
              (query_id, session_id, timestamp, question, rewritten_query,
               answer, sources, confidence, flagged, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query_id, session_id, timestamp, question, rewritten_query,
                answer, sources_json, confidence, int(flagged), duration_ms,
            ),
        )
        await db.commit()

    return query_id


async def get_audit_log(limit: int = 20, offset: int = 0) -> List[dict]:
    """Return paginated audit log entries, newest first."""
    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT query_id, session_id, timestamp, question,
                   confidence, flagged, duration_ms
            FROM audit_log
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_audit_entry(query_id: str) -> Optional[dict]:
    """Return a single full audit entry by query_id."""
    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM audit_log WHERE query_id = ?", (query_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if row is None:
        return None
    entry = dict(row)
    entry["sources"] = json.loads(entry["sources"] or "[]")
    return entry
