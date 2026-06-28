"""
Query routes — the core of the API.

POST /query        → synchronous JSON (works with curl, Swagger, any HTTP client)
POST /query/stream → Server-Sent Events (tokens appear live in the browser)

Both routes call the same pipeline.query() function. The difference is only
in how the response is delivered. This is the correct design: transport
mechanism and business logic are separated.
"""
import json
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.api.schemas import QueryRequest, QueryResponse, Source
from backend.audit.logger import log_query
from backend.rag.pipeline import query as rag_query
from backend.rag.rewriter import rewrite
from backend.rag.retriever import retrieve
from backend.rag.generator import stream_and_collect

router = APIRouter()


def _to_sources(chunks) -> list[Source]:
    return [
        Source(
            document=c.source_file,
            page=c.page_number,
            articles=c.articles,
            excerpt=c.text[:300],
            dense_rank=c.dense_rank if c.dense_rank >= 0 else None,
            bm25_rank=c.bm25_rank if c.bm25_rank >= 0 else None,
            rrf_score=round(c.score, 6),
        )
        for c in chunks
    ]


@router.post("/query", response_model=QueryResponse, tags=["RAG"])
async def query(request: QueryRequest) -> QueryResponse:
    """
    Submit a compliance question and receive a cited answer.

    The pipeline runs: query rewriting → hybrid retrieval → LLM generation
    → confidence scoring. All steps complete before the response is returned.

    Use `POST /query/stream` if you need tokens to appear progressively.
    """
    t0 = time.perf_counter()

    rewritten = rewrite(request.question)
    chunks = retrieve(rewritten)
    answer = stream_and_collect(request.question, chunks)

    duration_ms = int((time.perf_counter() - t0) * 1000)

    query_id = await log_query(
        question=request.question,
        answer=answer.text,
        sources=answer.sources,
        confidence=answer.confidence,
        flagged=answer.flagged,
        duration_ms=duration_ms,
        session_id=request.session_id,
        rewritten_query=rewritten,
    )

    return QueryResponse(
        query_id=query_id,
        question=request.question,
        answer=answer.text,
        sources=_to_sources(answer.sources),
        confidence=answer.confidence,
        flagged=answer.flagged,
        timestamp=datetime.now(timezone.utc),
        duration_ms=duration_ms,
    )


@router.post("/query/stream", tags=["RAG"])
async def query_stream(request: QueryRequest) -> StreamingResponse:
    """
    Submit a compliance question and receive a token-by-token SSE stream.

    Event types:
    - `token`    : one text token from the LLM
    - `metadata` : final JSON object with sources, confidence, query_id
    - `error`    : error message if the pipeline fails

    Frontend usage (JavaScript):
        const es = new EventSource('/query/stream');
        es.addEventListener('token', e => append(e.data));
        es.addEventListener('metadata', e => showSources(JSON.parse(e.data)));
    """
    async def event_generator():
        t0 = time.perf_counter()
        collected_tokens = []
        try:
            rewritten = rewrite(request.question)
            if rewritten != request.question:
                yield f"event: rewrite\ndata: {json.dumps(rewritten)}\n\n"

            chunks = retrieve(rewritten)

            def on_token(token: str):
                collected_tokens.append(token)

            # Run sync generation in a way that yields tokens
            # We buffer tokens and flush them in the async generator
            import threading, queue as _queue
            token_queue: _queue.Queue = _queue.Queue()
            done_event = threading.Event()
            answer_holder = []

            def run_generation():
                ans = stream_and_collect(
                    request.question,
                    chunks,
                    on_token=lambda t: token_queue.put(t),
                )
                answer_holder.append(ans)
                done_event.set()

            thread = threading.Thread(target=run_generation, daemon=True)
            thread.start()

            while not done_event.is_set() or not token_queue.empty():
                try:
                    token = token_queue.get(timeout=0.05)
                    yield f"event: token\ndata: {json.dumps(token)}\n\n"
                except _queue.Empty:
                    continue

            thread.join()
            answer = answer_holder[0]
            duration_ms = int((time.perf_counter() - t0) * 1000)

            query_id = await log_query(
                question=request.question,
                answer=answer.text,
                sources=answer.sources,
                confidence=answer.confidence,
                flagged=answer.flagged,
                duration_ms=duration_ms,
                session_id=request.session_id,
                rewritten_query=rewritten,
            )

            metadata = {
                "query_id": query_id,
                "confidence": answer.confidence,
                "flagged": answer.flagged,
                "duration_ms": duration_ms,
                "sources": [
                    {
                        "document": c.source_file,
                        "page": c.page_number,
                        "articles": c.articles,
                        "excerpt": c.text[:300],
                    }
                    for c in answer.sources
                ],
            }
            yield f"event: metadata\ndata: {json.dumps(metadata)}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering for SSE
        },
    )
