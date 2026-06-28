"""
BM25 keyword index — runs alongside Qdrant for hybrid retrieval.

Why BM25 + dense vectors?
- Dense (nomic-embed-text): understands semantic meaning, finds conceptually
  related passages even without exact keyword overlap.
- BM25: exact keyword match, critical for legal identifiers like
  "Article 28(2)(c)", "RTS", "TLPT" that embeddings treat as arbitrary tokens.
- Together (fused via RRF): you get the best of both.
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from rank_bm25 import BM25Okapi

from backend.ingestion.chunker import Chunk


def _tokenize(text: str) -> List[str]:
    """Lowercase, split on whitespace/punctuation, remove short tokens."""
    tokens = re.findall(r'\b\w+\b', text.lower())
    return [t for t in tokens if len(t) > 1]


@dataclass
class BM25Result:
    text: str
    source_file: str
    page_number: int
    chunk_index: int
    articles: List[str]
    bm25_score: float


class BM25Store:
    """
    Persistent BM25 index over the regulation corpus.

    The corpus is stored as a JSON file (list of chunk metadata + text).
    On load, the BM25Okapi index is rebuilt in memory from that file.
    This is fast (< 1s for thousands of chunks) and avoids storing
    pickle files which can break across Python versions.
    """

    def __init__(self, path: Path):
        self.path = path
        self._corpus: List[dict] = []
        self._index: Optional[BM25Okapi] = None

    def load(self) -> None:
        """Load corpus from disk and rebuild the BM25 index."""
        if not self.path.exists():
            return
        with open(self.path) as f:
            self._corpus = json.load(f)
        if self._corpus:
            tokenized = [_tokenize(entry["text"]) for entry in self._corpus]
            self._index = BM25Okapi(tokenized)

    def add(self, chunks: List[Chunk]) -> None:
        """Append chunks to the corpus and rebuild the index."""
        for chunk in chunks:
            self._corpus.append({
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "source_file": chunk.source_file,
                "page_number": chunk.page_number,
                "articles": chunk.articles,
            })
        tokenized = [_tokenize(entry["text"]) for entry in self._corpus]
        self._index = BM25Okapi(tokenized)

    def save(self) -> None:
        """Persist corpus to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._corpus, f)

    def search(self, query: str, k: int = 10) -> List[BM25Result]:
        """Return top-k chunks by BM25 score."""
        if not self._index or not self._corpus:
            return []
        tokens = _tokenize(query)
        scores = self._index.get_scores(tokens)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        results = []
        for i in top_indices:
            if scores[i] > 0:
                entry = self._corpus[i]
                results.append(BM25Result(
                    text=entry["text"],
                    source_file=entry["source_file"],
                    page_number=entry["page_number"],
                    chunk_index=entry["chunk_index"],
                    articles=entry.get("articles", []),
                    bm25_score=float(scores[i]),
                ))
        return results
