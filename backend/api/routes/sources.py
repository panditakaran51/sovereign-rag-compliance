import json
from pathlib import Path
from typing import List

from fastapi import APIRouter

from backend.api.schemas import SourceDocument
from backend.config import settings

router = APIRouter()


@router.get("/sources", response_model=List[SourceDocument], tags=["Corpus"])
async def list_sources() -> List[SourceDocument]:
    """
    List all documents currently ingested into the corpus.
    Derived from the BM25 corpus file — the single source of truth
    for what is and isn't queryable.
    """
    bm25_path = Path(settings.bm25_corpus_path)
    if not bm25_path.exists():
        return []

    corpus = json.loads(bm25_path.read_text())

    # Group chunks by source file
    docs: dict = {}
    for chunk in corpus:
        fname = chunk["source_file"]
        if fname not in docs:
            docs[fname] = {"chunk_count": 0, "articles": set()}
        docs[fname]["chunk_count"] += 1
        docs[fname]["articles"].update(chunk.get("articles", []))

    return [
        SourceDocument(
            filename=fname,
            chunk_count=info["chunk_count"],
            articles_found=sorted(info["articles"], key=lambda x: int(x) if x.isdigit() else 0),
        )
        for fname, info in sorted(docs.items())
    ]
