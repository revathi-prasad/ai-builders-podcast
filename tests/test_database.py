"""Tests for SQLite persistence layer."""

import os
import pytest
import tempfile
from unittest.mock import patch


@pytest.fixture
async def test_db():
    """Set up a temp database for testing."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")
        with patch.dict(os.environ, {"PODCAST_DB_PATH": db_path}):
            # Reset the module-level state
            import src.api.database as db_mod
            db_mod.DB_PATH = db_path
            db_mod._db_initialized = False

            await db_mod.init_db()
            yield db_mod


@pytest.mark.asyncio
class TestDatabase:
    async def test_init_is_idempotent(self, test_db):
        """Calling init_db twice should not error."""
        await test_db.init_db()
        await test_db.init_db()

    async def test_upsert_and_get_job(self, test_db):
        """Should be able to create and retrieve a job."""
        job_data = {
            "status": "pending",
            "progress": 0,
            "current_step": "Initializing",
            "created_at": "2025-01-01T00:00:00",
        }
        await test_db.upsert_job("test-job-1", job_data)
        job = await test_db.get_job("test-job-1")

        assert job is not None
        assert job["job_id"] == "test-job-1"
        assert job["status"] == "pending"

    async def test_update_job(self, test_db):
        """Updating a job should overwrite mutable fields."""
        await test_db.upsert_job("test-job-2", {
            "status": "pending", "progress": 0,
            "current_step": "Init", "created_at": "2025-01-01T00:00:00"
        })
        await test_db.upsert_job("test-job-2", {
            "status": "completed", "progress": 100,
            "current_step": "Done", "created_at": "2025-01-01T00:00:00",
            "completed_at": "2025-01-01T01:00:00"
        })

        job = await test_db.get_job("test-job-2")
        assert job["status"] == "completed"
        assert job["progress"] == 100

    async def test_list_jobs(self, test_db):
        """Should list jobs in reverse chronological order."""
        for i in range(5):
            await test_db.upsert_job(f"job-{i}", {
                "status": "completed", "progress": 100,
                "current_step": "Done", "created_at": f"2025-01-0{i+1}T00:00:00"
            })

        jobs = await test_db.list_jobs(limit=3)
        assert len(jobs) == 3
        # Newest first
        assert jobs[0]["created_at"] > jobs[1]["created_at"]

    async def test_count_jobs(self, test_db):
        for i in range(3):
            await test_db.upsert_job(f"count-job-{i}", {
                "status": "pending", "progress": 0,
                "current_step": "Init", "created_at": "2025-01-01T00:00:00"
            })
        count = await test_db.count_jobs()
        assert count >= 3

    async def test_get_nonexistent_job(self, test_db):
        job = await test_db.get_job("nonexistent")
        assert job is None

    async def test_add_and_get_feedback(self, test_db):
        await test_db.upsert_job("fb-job", {
            "status": "completed", "progress": 100,
            "current_step": "Done", "created_at": "2025-01-01T00:00:00"
        })
        await test_db.add_feedback({
            "id": "fb-1",
            "job_id": "fb-job",
            "rating": 5,
            "feedback_type": "explicit",
            "comments": "Great podcast!",
            "timestamp": "2025-01-01T00:00:00"
        })
        await test_db.add_feedback({
            "id": "fb-2",
            "job_id": "fb-job",
            "rating": 3,
            "feedback_type": "explicit",
            "timestamp": "2025-01-01T00:00:00"
        })

        stats = await test_db.get_feedback_stats()
        assert stats["total_feedback"] >= 2
        assert stats["avg_rating"] == pytest.approx(4.0, abs=0.1)

    async def test_job_with_result_json(self, test_db):
        """Results should be persisted as JSON."""
        await test_db.upsert_job("json-job", {
            "status": "completed", "progress": 100,
            "current_step": "Done", "created_at": "2025-01-01T00:00:00",
            "result": {"final_script": "Hello world", "quality_score": 0.85}
        })

        job = await test_db.get_job("json-job")
        assert job["result"]["final_script"] == "Hello world"
        assert job["result"]["quality_score"] == 0.85
