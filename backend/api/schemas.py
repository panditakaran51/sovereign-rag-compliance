from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
import uuid


class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        examples=["What are the ICT third-party risk requirements under DORA Article 28?"],
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session ID for follow-up question tracking",
    )


class Source(BaseModel):
    document: str
    page: int
    articles: List[str]
    excerpt: str
    dense_rank: Optional[int] = None
    bm25_rank: Optional[int] = None
    rrf_score: Optional[float] = None


class QueryResponse(BaseModel):
    query_id: str
    question: str
    answer: str
    sources: List[Source]
    confidence: int = Field(ge=1, le=5)
    flagged: bool
    timestamp: datetime
    duration_ms: int


class IngestResponse(BaseModel):
    job_id: str
    filename: str
    status: str = "accepted"
    message: str


class JobStatus(BaseModel):
    job_id: str
    filename: str
    status: str                    # pending | running | done | failed
    chunks_written: Optional[int] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class SourceDocument(BaseModel):
    filename: str
    chunk_count: int
    articles_found: List[str]


class HealthResponse(BaseModel):
    status: str                    # ok | degraded
    ollama: str
    qdrant: str
    bm25_corpus_size: int


class AuditEntry(BaseModel):
    query_id: str
    session_id: Optional[str]
    timestamp: datetime
    question: str
    confidence: int
    flagged: bool
    duration_ms: int


class AuditLogResponse(BaseModel):
    total_shown: int
    offset: int
    entries: List[AuditEntry]
