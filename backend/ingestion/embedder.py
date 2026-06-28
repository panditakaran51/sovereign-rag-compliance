import uuid
from pathlib import Path
from typing import List

import ollama
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from rich.progress import track

from backend.ingestion.chunker import Chunk
from backend.rag.bm25_store import BM25Store
from backend.config import settings

_UUID_NAMESPACE = uuid.UUID("b7e4c9a2-1f3d-4e8b-9c6a-2d5f0e7b1a3c")


def _chunk_id(chunk: Chunk) -> str:
    key = f"{chunk.source_file}::{chunk.chunk_index}::{chunk.text[:64]}"
    return str(uuid.uuid5(_UUID_NAMESPACE, key))


def _embed(text: str) -> List[float]:
    client = ollama.Client(host=settings.ollama_base_url)
    response = client.embeddings(model=settings.ollama_embed_model, prompt=text)
    return response["embedding"]


def _ensure_collection(client: QdrantClient, vector_size: int) -> None:
    existing = [c.name for c in client.get_collections().collections]
    if settings.qdrant_collection not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


def upsert_chunks(chunks: List[Chunk], batch_size: int = 32) -> int:
    """
    Embed chunks → upsert to Qdrant AND update the BM25 corpus.
    Both indices are updated in a single ingest pass so they stay in sync.
    Returns the number of points written to Qdrant.
    """
    qdrant = QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        check_compatibility=False,
    )

    bm25 = BM25Store(Path(settings.bm25_corpus_path))
    bm25.load()  # load existing corpus if any

    points: List[PointStruct] = []
    total = 0
    collection_ready = False

    for chunk in track(chunks, description="Embedding + upserting chunks..."):
        vector = _embed(chunk.text)

        if not collection_ready:
            _ensure_collection(qdrant, len(vector))
            collection_ready = True

        points.append(PointStruct(
            id=_chunk_id(chunk),
            vector=vector,
            payload={
                "text": chunk.text,
                "source_file": chunk.source_file,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "articles": chunk.articles,
            },
        ))

        if len(points) >= batch_size:
            qdrant.upsert(collection_name=settings.qdrant_collection, points=points)
            total += len(points)
            points = []

    if points:
        qdrant.upsert(collection_name=settings.qdrant_collection, points=points)
        total += len(points)

    # Update BM25 after all Qdrant upserts succeed
    bm25.add(chunks)
    bm25.save()

    return total
