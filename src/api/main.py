"""
FastAPI Backend for AI Podcast Generator

This module provides the REST API for the React frontend.
It handles:
- Podcast generation requests
- File uploads (PDFs, audio)
- Progress tracking via WebSockets
- Feedback collection

Run with: uvicorn src.api.main:app --reload
"""

import os
import uuid
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.api.runner import run_generation_workflow
from src.api.database import init_db, upsert_job, get_job, list_jobs, count_jobs, add_feedback, get_feedback_stats as db_get_feedback_stats

# Create FastAPI app
app = FastAPI(
    title="AI Podcast Generator API",
    description="Multi-agent podcast generation system",
    version="2.0.0"
)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cache for active job progress (fast WebSocket updates during generation)
# Completed/failed jobs are persisted to SQLite
_active_jobs: Dict[str, Dict[str, Any]] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    await init_db()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ContentInput(BaseModel):
    """A single content input"""
    type: str = Field(..., description="Content type: document, audio, url, topic, text")
    source: str = Field(..., description="File path, URL, or text content")


class GenerateRequest(BaseModel):
    """Request to generate a podcast"""
    user_request: str = Field(..., description="User's description of what they want")
    contents: List[ContentInput] = Field(default_factory=list, description="Input content")
    target_language: str = Field(default="english", description="Target language")
    target_duration_minutes: int = Field(default=10, ge=1, le=60)
    episode_format: str = Field(default="conversation", description="conversation, interview, monologue")
    audience_level: str = Field(default="intermediate", description="beginner, intermediate, expert")


class GenerateResponse(BaseModel):
    """Response after starting generation"""
    job_id: str
    status: str
    message: str


class JobStatus(BaseModel):
    """Status of a generation job"""
    job_id: str
    status: str  # pending, processing, completed, failed
    progress: int  # 0-100
    current_step: str
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class FeedbackRequest(BaseModel):
    """User feedback on generated podcast"""
    job_id: str
    rating: int = Field(..., ge=1, le=5)
    feedback_type: str = Field(default="explicit")  # explicit, pairwise, implicit
    comments: Optional[str] = None
    listen_percentage: Optional[int] = None
    would_share: Optional[bool] = None


class FeedbackResponse(BaseModel):
    """Response after submitting feedback"""
    success: bool
    message: str


# ============================================================================
# ROUTES
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "AI Podcast Generator API",
        "version": "2.0.0",
        "status": "healthy"
    }


@app.get("/api/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "api": "up",
            "knowledge_graph": "up",  # Would check actual KG connection
            "llm": "configured" if os.environ.get("ANTHROPIC_API_KEY") else "not_configured"
        }
    }


@app.post("/api/generate", response_model=GenerateResponse)
async def generate_podcast(request: GenerateRequest, background_tasks: BackgroundTasks):
    """
    Start podcast generation.

    This immediately returns a job_id. Use /api/jobs/{job_id} to track progress.
    """
    job_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    # Store in both DB (persistence) and cache (fast WebSocket updates)
    job_data = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "current_step": "Initializing",
        "created_at": now,
        "completed_at": None,
        "request": request.model_dump(),
        "result": None,
        "error": None
    }
    _active_jobs[job_id] = job_data
    await upsert_job(job_id, job_data)

    # Start generation in background
    background_tasks.add_task(run_generation, job_id, request)

    return GenerateResponse(
        job_id=job_id,
        status="pending",
        message="Podcast generation started. Use /api/jobs/{job_id} to track progress."
    )


@app.get("/api/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get the status of a generation job"""
    # Check active cache first (faster for in-progress jobs)
    if job_id in _active_jobs:
        return JobStatus(**_active_jobs[job_id])

    # Fall back to database (persisted completed jobs)
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(**job)


@app.get("/api/jobs")
async def list_all_jobs(limit: int = 10):
    """List recent jobs"""
    db_jobs = await list_jobs(limit=limit)
    total = await count_jobs()

    return {
        "jobs": [JobStatus(**job) for job in db_jobs],
        "total": total
    }


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file for processing.

    Returns a file_id that can be used in generate requests.
    """
    # Create uploads directory
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)

    # Generate unique filename
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1] if file.filename else ""
    file_path = os.path.join(upload_dir, f"{file_id}{ext}")

    # Save file
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "path": file_path,
        "size": len(content),
        "content_type": file.content_type
    }


@app.get("/api/download/{job_id}")
async def download_audio(job_id: str):
    """Download the generated audio file"""
    job = _active_jobs.get(job_id) or await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")

    audio_path = (job.get("result") or {}).get("audio_file_path")
    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Audio file not found")

    return FileResponse(
        audio_path,
        media_type="audio/mpeg",
        filename=f"podcast_{job_id[:8]}.mp3"
    )


@app.get("/api/script/{job_id}")
async def get_script(job_id: str):
    """Get the generated script"""
    job = _active_jobs.get(job_id) or await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")

    result = job.get("result") or {}
    return {
        "job_id": job_id,
        "script": result.get("final_script", ""),
        "segments": result.get("segments", []),
        "quality_score": result.get("quality_score", 0.0),
        "fm_reward": result.get("fm_reward", 0.0),
        "verification_results": result.get("verification_results", [])
    }


@app.post("/api/feedback", response_model=FeedbackResponse)
async def submit_feedback(feedback: FeedbackRequest):
    """
    Submit feedback on a generated podcast.

    This is used for the RL training pipeline.
    Supports explicit ratings, pairwise comparisons, and implicit signals.
    """
    job = _active_jobs.get(feedback.job_id) or await get_job(feedback.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Store feedback in DB
    feedback_entry = {
        "id": str(uuid.uuid4()),
        "job_id": feedback.job_id,
        "rating": feedback.rating,
        "feedback_type": feedback.feedback_type,
        "comments": feedback.comments,
        "listen_percentage": feedback.listen_percentage,
        "would_share": feedback.would_share,
        "timestamp": datetime.now().isoformat()
    }

    await add_feedback(feedback_entry)

    return FeedbackResponse(
        success=True,
        message="Thank you for your feedback!"
    )


class PairwiseFeedbackRequest(BaseModel):
    """Pairwise comparison feedback"""
    winner_job_id: str
    loser_job_id: str
    feedback_type: str = Field(default="pairwise")
    comments: Optional[str] = None


@app.post("/api/feedback/pairwise", response_model=FeedbackResponse)
async def submit_pairwise_feedback(feedback: PairwiseFeedbackRequest):
    """
    Submit pairwise comparison feedback.

    Used when showing users two podcast versions and asking which is better.
    This provides strong signal for RL preference learning (like DPO/RLHF).
    """
    # Validate both jobs exist
    winner = _active_jobs.get(feedback.winner_job_id) or await get_job(feedback.winner_job_id)
    if not winner:
        raise HTTPException(status_code=404, detail="Winner job not found")
    loser = _active_jobs.get(feedback.loser_job_id) or await get_job(feedback.loser_job_id)
    if not loser:
        raise HTTPException(status_code=404, detail="Loser job not found")

    # Store comparison feedback
    feedback_entry = {
        "id": str(uuid.uuid4()),
        "feedback_type": "pairwise",
        "job_id": feedback.winner_job_id,
        "rating": 5,  # Winner gets implicit high rating
        "comments": feedback.comments,
        "timestamp": datetime.now().isoformat()
    }

    await add_feedback(feedback_entry)

    # Also store implicit negative for loser (for analysis)
    loser_entry = {
        "id": str(uuid.uuid4()),
        "feedback_type": "pairwise_implicit",
        "job_id": feedback.loser_job_id,
        "rating": 2,  # Loser gets implicit lower rating
        "comparison_id": feedback_entry["id"],
        "timestamp": datetime.now().isoformat()
    }
    await add_feedback(loser_entry)

    return FeedbackResponse(
        success=True,
        message="Thank you for your comparison!"
    )


@app.get("/api/feedback/stats")
async def feedback_stats():
    """Get feedback statistics (for dashboard)"""
    return await db_get_feedback_stats()


# ============================================================================
# WEBSOCKET FOR REAL-TIME UPDATES
# ============================================================================

@app.websocket("/ws/jobs/{job_id}")
async def websocket_job_updates(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time job updates.

    Connect to receive progress updates for a specific job.
    """
    await websocket.accept()

    try:
        while True:
            # Use in-memory cache for fast polling
            job = _active_jobs.get(job_id)
            if not job:
                # Try DB as fallback
                job = await get_job(job_id)
            if not job:
                await websocket.send_json({"error": "Job not found"})
                break

            await websocket.send_json({
                "job_id": job_id,
                "status": job["status"],
                "progress": job["progress"],
                "current_step": job["current_step"]
            })

            if job["status"] in ["completed", "failed"]:
                break

            await asyncio.sleep(1)  # Update every second

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()


# ============================================================================
# BACKGROUND TASK
# ============================================================================

async def run_generation(job_id: str, request: GenerateRequest):
    """
    Background task to run podcast generation.

    Uses the LangGraph workflow runner with FM monitors and quality checkers.
    Updates both in-memory cache (for WebSocket) and SQLite (for persistence).
    """
    def progress_callback(progress: int, step: str):
        """Update job progress in real-time (in-memory for speed)"""
        if job_id in _active_jobs:
            _active_jobs[job_id]["progress"] = progress
            _active_jobs[job_id]["current_step"] = step

    try:
        # Update status
        _active_jobs[job_id]["status"] = "processing"

        # Convert request to dict for runner
        request_dict = {
            "user_request": request.user_request,
            "contents": [c.model_dump() for c in request.contents],
            "target_language": request.target_language,
            "target_duration_minutes": request.target_duration_minutes,
            "episode_format": request.episode_format,
            "audience_level": request.audience_level
        }

        # Run the actual LangGraph workflow
        result = await run_generation_workflow(request_dict, progress_callback)

        # Update job with result
        if result.get("success"):
            _active_jobs[job_id]["status"] = "completed"
            _active_jobs[job_id]["progress"] = 100
            _active_jobs[job_id]["current_step"] = "Done"
            _active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
            _active_jobs[job_id]["result"] = {
                "final_script": result.get("final_script", ""),
                "audio_file_path": result.get("audio_file_path"),
                "quality_score": result.get("quality_score", 0.0),
                "fm_reward": result.get("fm_reward", 0.0),
                "duration_minutes": result.get("duration_minutes", request.target_duration_minutes),
                "segments": result.get("segments", []),
                "verification_results": result.get("verification_results", []),
                "metadata": result.get("metadata", {})
            }
        else:
            _active_jobs[job_id]["status"] = "failed"
            _active_jobs[job_id]["error"] = result.get("error", "Unknown error")
            _active_jobs[job_id]["current_step"] = "Failed"

    except Exception as e:
        _active_jobs[job_id]["status"] = "failed"
        _active_jobs[job_id]["error"] = str(e)
        _active_jobs[job_id]["current_step"] = "Failed"

    # Persist final state to SQLite and clean up cache
    await upsert_job(job_id, _active_jobs[job_id])
    _active_jobs.pop(job_id, None)


# ============================================================================
# APP FACTORY
# ============================================================================

def create_app() -> FastAPI:
    """Create and configure the FastAPI app"""
    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
