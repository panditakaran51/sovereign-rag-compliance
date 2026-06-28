"""
Hybrid retriever — dense (Qdrant) + keyword (BM25), fused via RRF.

Reciprocal Rank Fusion formula: score = Σ 1 / (k + rank_i)
where k=60 is a smoothing constant that prevents top-1 results from
dominating. Two result lists each contribute independently; a chunk
appearing in both gets a higher combined score.

Article-aware retrieval: when the question names specific article numbers,
a targeted pre-fetch of those tagged chunks is injected at the front of
the dense results. Without this, article body text (which doesn't repeat
"Article 28" in every paragraph) ranks too low to appear in top-k.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict

import ollama
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny

from backend.rag.bm25_store import BM25Store
from backend.config import settings

_RRF_K = 60
_ARTICLE_RE = re.compile(r'\bAr\s?ticles?\s+(\d+)', re.IGNORECASE)


@dataclass
class RetrievedChunk:
    text: str
    source_file: str
    page_number: int
    chunk_index: int
    articles: List[str] = field(default_factory=list)
    score: float = 0.0
    dense_rank: int = -1
    bm25_rank: int = -1


def _extract_article_numbers(text: str) -> List[str]:
    """Find all article numbers explicitly mentioned in the query text."""
    return list(set(_ARTICLE_RE.findall(text)))


def _embed_query(question: str) -> List[float]:
    client = ollama.Client(host=settings.ollama_base_url)
    response = client.embeddings(model=settings.ollama_embed_model, prompt=question)
    return response["embedding"]


def _to_chunks(results) -> List[RetrievedChunk]:
    return [
        RetrievedChunk(
            text=r.payload["text"],
            source_file=r.payload["source_file"],
            page_number=r.payload.get("page_number", 0),
            chunk_index=r.payload.get("chunk_index", -1),
            articles=r.payload.get("articles", []),
            score=r.score,
        )
        for r in results
    ]


def _dense_search(
    qdrant: QdrantClient,
    query_vector: List[float],
    k: int,
    article_filter: Optional[List[str]] = None,
) -> List[RetrievedChunk]:
    kwargs = dict(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        limit=k,
        with_payload=True,
    )
    if article_filter:
        kwargs["query_filter"] = Filter(
            must=[FieldCondition(key="articles", match=MatchAny(any=article_filter))]
        )
    return _to_chunks(qdrant.query_points(**kwargs).points)


def _bm25_search(
    query: str,
    k: int,
    article_filter: Optional[List[str]] = None,
) -> List[RetrievedChunk]:
    bm25 = BM25Store(Path(settings.bm25_corpus_path))
    bm25.load()
    results = bm25.search(query, k=k)
    chunks = [
        RetrievedChunk(
            text=r.text,
            source_file=r.source_file,
            page_number=r.page_number,
            chunk_index=r.chunk_index,
            articles=r.articles,
            score=r.bm25_score,
        )
        for r in results
    ]
    if article_filter:
        chunks = [c for c in chunks if any(a in article_filter for a in c.articles)]
    return chunks


def _rrf_fuse(
    dense: List[RetrievedChunk],
    bm25: List[RetrievedChunk],
    top_k: int,
) -> List[RetrievedChunk]:
    rrf_scores: Dict = {}
    chunk_map: Dict = {}

    for rank, chunk in enumerate(dense):
        key = chunk.chunk_index
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (_RRF_K + rank + 1)
        chunk.dense_rank = rank
        chunk_map[key] = chunk

    for rank, chunk in enumerate(bm25):
        key = chunk.chunk_index
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (_RRF_K + rank + 1)
        if key not in chunk_map:
            chunk_map[key] = chunk
        chunk_map[key].bm25_rank = rank

    sorted_keys = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)
    result = []
    for key in sorted_keys[:top_k]:
        c = chunk_map[key]
        c.score = rrf_scores[key]
        result.append(c)
    return result


def retrieve(question: str, top_k: Optional[int] = None) -> List[RetrievedChunk]:
    """
    Hybrid retrieval with article-aware pre-filtering.

    If the question names article numbers (e.g. "Article 28"):
    - Runs a filtered dense search returning ONLY those article's chunks
    - Runs a filtered BM25 search
    - Prepends them to the unfiltered results before RRF fusion
    This ensures article-specific chunks are always in the candidate pool.
    """
    k = top_k or settings.retrieval_top_k
    fetch_k = k * 3

    qdrant = QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        check_compatibility=False,
    )

    query_vector = _embed_query(question)
    mentioned_articles = _extract_article_numbers(question)

    if mentioned_articles:
        # Targeted: fetch chunks tagged for the named articles
        targeted = _dense_search(qdrant, query_vector, k=k, article_filter=mentioned_articles)
        for rank, c in enumerate(targeted):
            c.dense_rank = rank

        # Broad: normal hybrid search for surrounding context
        broad_dense = _dense_search(qdrant, query_vector, k=fetch_k)
        broad_bm25  = _bm25_search(question, k=fetch_k)
        rrf_pool    = _rrf_fuse(broad_dense, broad_bm25, top_k=k)

        # Pin targeted chunks first, fill remainder with RRF results
        pinned_indices = {c.chunk_index for c in targeted}
        context_fill   = [c for c in rrf_pool if c.chunk_index not in pinned_indices]
        pin_slots      = min(len(targeted), max(k // 2, 3))  # at most half the slots
        return (targeted[:pin_slots] + context_fill)[:k]
    else:
        dense_results = _dense_search(qdrant, query_vector, k=fetch_k)
        bm25_results  = _bm25_search(question, k=fetch_k)
        return _rrf_fuse(dense_results, bm25_results, top_k=k)
