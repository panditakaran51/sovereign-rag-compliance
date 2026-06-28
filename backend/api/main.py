"""
Sovereign RAG Compliance — FastAPI application entry point.

Start with:
    uvicorn backend.api.main:app --reload --port 8000
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.audit.logger import init_db
from backend.api.routes import health, query, ingest, sources, audit


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialise the audit DB. Shutdown: nothing to clean up."""
    await init_db()
    yield


app = FastAPI(
    title="Sovereign RAG — EU Financial Compliance API",
    description=(
        "A fully local Retrieval-Augmented Generation system for querying "
        "EU financial regulations (DORA, EU AI Act, BaFin circulars). "
        "Zero data leaves your infrastructure."
    ),
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit (Phase 4)
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(query.router)
app.include_router(ingest.router)
app.include_router(sources.router)
app.include_router(audit.router)
