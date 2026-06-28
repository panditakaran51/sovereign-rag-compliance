import json
from pathlib import Path

import ollama
from fastapi import APIRouter
from qdrant_client import QdrantClient

from backend.api.schemas import HealthResponse
from backend.config import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health() -> HealthResponse:
    """
    Liveness + dependency check.
    Returns 200 even when dependencies are degraded — the status field
    tells the caller what is and isn't available. This allows k8s readiness
    probes to distinguish 'app is up but Ollama is still loading' from
    'app is completely down'.
    """
    ollama_status = "ok"
    try:
        ollama.Client(host=settings.ollama_base_url).list()
    except Exception as e:
        ollama_status = f"unavailable: {e}"

    qdrant_status = "ok"
    try:
        QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            check_compatibility=False,
        ).get_collections()
    except Exception as e:
        qdrant_status = f"unavailable: {e}"

    bm25_size = 0
    bm25_path = Path(settings.bm25_corpus_path)
    if bm25_path.exists():
        try:
            bm25_size = len(json.loads(bm25_path.read_text()))
        except Exception:
            pass

    overall = "ok" if ollama_status == "ok" and qdrant_status == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        ollama=ollama_status,
        qdrant=qdrant_status,
        bm25_corpus_size=bm25_size,
    )
