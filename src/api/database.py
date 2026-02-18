"""
SQLite Persistence Layer

Replaces in-memory dicts with persistent SQLite storage for jobs and feedback.
Uses aiosqlite for async compatibility with FastAPI.

Usage:
    from src.api.database import init_db, upsert_job, get_job, list_jobs, add_feedback

    # At startup
    await init_db()

    # CRUD
    await upsert_job(job_id, {"status": "pending", ...})
    job = await get_job(job_id)
    jobs = await list_jobs(limit=10)
    await add_feedback({"job_id": ..., "rating": 5, ...})
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

import aiosqlite

logger = logging.getLogger(__name__)

# Database path — configurable via env var
DB_PATH = os.environ.get("PODCAST_DB_PATH", "./data/podcast_api.db")

_db_initialized = False


async def _get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db() -> None:
    """
    Initialize the database schema. Idempotent — safe to call multiple times.
    """
    global _db_initialized
    if _db_initialized:
        return

    db = await _get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'pending',
                progress INTEGER NOT NULL DEFAULT 0,
                current_step TEXT NOT NULL DEFAULT 'Initializing',
                created_at TEXT NOT NULL,
                completed_at TEXT,
                request_json TEXT,
                result_json TEXT,
                error TEXT
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                rating INTEGER NOT NULL,
                feedback_type TEXT NOT NULL DEFAULT 'explicit',
                comments TEXT,
                listen_percentage INTEGER,
                would_share INTEGER,
                comparison_id TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(job_id)
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
            CREATE INDEX IF NOT EXISTS idx_feedback_job ON feedback(job_id);
        """)
        await db.commit()
        _db_initialized = True
        logger.info(f"[DB] Initialized at {DB_PATH}")
    finally:
        await db.close()


async def upsert_job(job_id: str, data: Dict[str, Any]) -> None:
    """Insert or update a job record."""
    db = await _get_db()
    try:
        await db.execute(
            """INSERT INTO jobs (job_id, status, progress, current_step, created_at,
                                completed_at, request_json, result_json, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(job_id) DO UPDATE SET
                   status = excluded.status,
                   progress = excluded.progress,
                   current_step = excluded.current_step,
                   completed_at = excluded.completed_at,
                   result_json = excluded.result_json,
                   error = excluded.error
            """,
            (
                job_id,
                data.get("status", "pending"),
                data.get("progress", 0),
                data.get("current_step", "Initializing"),
                data.get("created_at", datetime.now().isoformat()),
                data.get("completed_at"),
                json.dumps(data.get("request")) if data.get("request") else None,
                json.dumps(data.get("result")) if data.get("result") else None,
                data.get("error")
            )
        )
        await db.commit()
    finally:
        await db.close()


async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get a job by ID. Returns None if not found."""
    db = await _get_db()
    try:
        cursor = await db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_job_dict(row)
    finally:
        await db.close()


async def list_jobs(limit: int = 10) -> List[Dict[str, Any]]:
    """List recent jobs, newest first."""
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [_row_to_job_dict(row) for row in rows]
    finally:
        await db.close()


async def count_jobs() -> int:
    """Count total jobs."""
    db = await _get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) FROM jobs")
        row = await cursor.fetchone()
        return row[0]
    finally:
        await db.close()


async def add_feedback(entry: Dict[str, Any]) -> None:
    """Add a feedback entry."""
    db = await _get_db()
    try:
        await db.execute(
            """INSERT INTO feedback (id, job_id, rating, feedback_type, comments,
                                    listen_percentage, would_share, comparison_id, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.get("id", ""),
                entry.get("job_id", ""),
                entry.get("rating", 0),
                entry.get("feedback_type", "explicit"),
                entry.get("comments"),
                entry.get("listen_percentage"),
                1 if entry.get("would_share") else 0 if entry.get("would_share") is not None else None,
                entry.get("comparison_id"),
                entry.get("timestamp", datetime.now().isoformat())
            )
        )
        await db.commit()
    finally:
        await db.close()


async def get_feedback_stats() -> Dict[str, Any]:
    """Get aggregated feedback statistics."""
    db = await _get_db()
    try:
        # Total count and average
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt, AVG(rating) as avg_rating FROM feedback"
        )
        row = await cursor.fetchone()
        total = row[0] or 0
        avg_rating = row[1] or 0

        # By type
        cursor = await db.execute(
            "SELECT feedback_type, COUNT(*) as cnt FROM feedback GROUP BY feedback_type"
        )
        by_type = {row[0]: row[1] for row in await cursor.fetchall()}

        # Rating distribution
        cursor = await db.execute(
            "SELECT rating, COUNT(*) as cnt FROM feedback GROUP BY rating"
        )
        distribution = {str(row[0]): row[1] for row in await cursor.fetchall()}

        return {
            "total_feedback": total,
            "avg_rating": round(avg_rating, 2),
            "feedback_by_type": by_type,
            "rating_distribution": distribution
        }
    finally:
        await db.close()


def _row_to_job_dict(row) -> Dict[str, Any]:
    """Convert a database row to a job dict matching the API format."""
    return {
        "job_id": row["job_id"],
        "status": row["status"],
        "progress": row["progress"],
        "current_step": row["current_step"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
        "request": json.loads(row["request_json"]) if row["request_json"] else None,
        "result": json.loads(row["result_json"]) if row["result_json"] else None,
        "error": row["error"]
    }
