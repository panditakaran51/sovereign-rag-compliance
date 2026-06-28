"""
Unified RAG pipeline — single entry point for Phase 2+.

query(question) runs:
  1. Query rewriting    (qwen3:30b-a3b, fast MoE)
  2. Hybrid retrieval   (Qdrant dense + BM25, fused via RRF)
  3. Generation         (qwen3.6:27b, streaming)
  4. Confidence scoring (qwen3:30b-a3b, fast MoE)
"""
from backend.rag.rewriter import rewrite
from backend.rag.retriever import retrieve
from backend.rag.generator import stream_and_collect, Answer


def query(
    question: str,
    on_token=None,
    on_rewrite=None,
) -> Answer:
    """
    Full RAG pipeline.

    Args:
        question:   The user's natural-language question.
        on_token:   Optional callback(token: str) called for each streamed token.
        on_rewrite: Optional callback(rewritten: str) called after query rewriting.

    Returns:
        Answer with .text, .sources, .confidence, .flagged
    """
    rewritten = rewrite(question)
    if on_rewrite:
        on_rewrite(rewritten)

    chunks = retrieve(rewritten)

    return stream_and_collect(question, chunks, on_token=on_token)
