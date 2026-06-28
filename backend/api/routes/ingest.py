"""
Ingest routes — add regulation documents to the corpus at runtime.

POST /ingest            uploads a PDF, starts background ingestion, returns job_id
GET  /ingest/{job_id}   polls job status

Why background? Embedding 750 chunks takes ~20s. A synchronous POST
would time out in most HTTP clients and block the event loop. The
background task pattern is the correct production approach.
"""
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File

from backend.api.schemas import IngestResponse, JobStatus
from backend.ingestion.loader import load_pdf
from backend.ingestion.chunker import chunk_pages
from backend.ingestion.embedder import upsert_chunks

router = APIRouter()

# In-memory job registry — fine for a single-instance deployment.
# For multi-instance, replace with Redis or the SQLite audit DB.
_jobs: Dict[str, JobStatus] = {}


def _run_ingestion(job_id: str, tmp_path: str, filename: str) -> None:
    """Background task: load → chunk → embed → upsert. Updates job registry."""
    job = _jobs[job_id]
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)

    try:
        pages = load_pdf(Path(tmp_path))
        chunks = chunk_pages(pages)
        total = upsert_chunks(chunks)

        job.status = "done"
        job.chunks_written = total
        job.completed_at = datetime.now(timezone.utc)
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        job.completed_at = datetime.now(timezone.utc)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@router.post("/ingest", response_model=IngestResponse, status_code=202, tags=["Ingestion"])
async def ingest(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF regulation document"),
) -> IngestResponse:
    """
    Upload a PDF regulation document for ingestion into the corpus.

    Returns immediately with a job_id. Poll `GET /ingest/{job_id}` to
    track progress. The document is available for querying once status
    is `done`.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    job_id = str(uuid.uuid4())

    # Write to temp file — background task picks it up after the response is sent
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    content = await file.read()
    tmp.write(content)
    tmp.flush()
    tmp.close()

    _jobs[job_id] = JobStatus(
        job_id=job_id,
        filename=file.filename,
        status="pending",
    )

    background_tasks.add_task(_run_ingestion, job_id, tmp.name, file.filename)

    return IngestResponse(
        job_id=job_id,
        filename=file.filename,
        message=f"Ingestion started. Poll GET /ingest/{job_id} for status.",
    )


@router.get("/ingest/{job_id}", response_model=JobStatus, tags=["Ingestion"])
async def ingest_status(job_id: str) -> JobStatus:
    """Poll ingestion job status."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return _jobs[job_id]
