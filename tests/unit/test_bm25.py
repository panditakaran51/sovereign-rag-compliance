"""Unit tests for the BM25 keyword index.

BM25 is the sparse retrieval half of the hybrid RAG pipeline. Tests verify:
- Tokenisation filters short tokens
- Search returns the most keyword-relevant chunk
- Zero-result behaviour on an empty store
- Corpus round-trips correctly through JSON serialisation
- Article metadata survives save/load
"""
import json
import tempfile
from pathlib import Path
from typing import List, Optional

import pytest

from backend.ingestion.chunker import Chunk
from backend.rag.bm25_store import BM25Store, _tokenize


# ── Tokeniser ────────────────────────────────────────────────────────────────

def test_tokenize_lowercases():
    tokens = _tokenize("Article DORA ICT")
    assert all(t == t.lower() for t in tokens)


def test_tokenize_filters_single_char_tokens():
    tokens = _tokenize("a b c risk")
    assert "a" not in tokens
    assert "b" not in tokens
    assert "risk" in tokens


def test_tokenize_splits_on_punctuation():
    tokens = _tokenize("Article 28(2)(c)")
    assert "article" in tokens
    assert "28" in tokens


def test_tokenize_empty_string():
    assert _tokenize("") == []


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_chunk(text: str, idx: int = 0, articles: Optional[List[str]] = None) -> Chunk:
    return Chunk(
        text=text,
        source_file="test.pdf",
        page_number=1,
        chunk_index=idx,
        char_start=0,
        articles=articles or [],
    )


# ── Search ───────────────────────────────────────────────────────────────────

def test_search_returns_most_relevant_chunk():
    with tempfile.TemporaryDirectory() as tmp:
        store = BM25Store(Path(tmp) / "corpus.json")
        store.add([
            _make_chunk("DORA requires ICT risk management frameworks", idx=0),
            _make_chunk("Tax obligations for financial reporting entities", idx=1),
            _make_chunk("General prudential requirements for credit institutions", idx=2),
        ])
        results = store.search("ICT risk management", k=3)
        assert results, "Expected at least one result"
        assert results[0].chunk_index == 0, (
            f"ICT risk chunk should rank first, got chunk_index={results[0].chunk_index}"
        )


def test_search_empty_store_returns_empty():
    with tempfile.TemporaryDirectory() as tmp:
        store = BM25Store(Path(tmp) / "corpus.json")
        assert store.search("anything", k=5) == []


def test_search_zero_score_chunks_excluded():
    """Chunks with no keyword overlap should not appear in results."""
    with tempfile.TemporaryDirectory() as tmp:
        store = BM25Store(Path(tmp) / "corpus.json")
        store.add([
            _make_chunk("completely unrelated content about weather forecasts", idx=0),
        ])
        results = store.search("ICT risk DORA Article 28", k=5)
        # No overlap → BM25 score 0 → excluded
        assert results == []


def test_search_respects_k_limit():
    with tempfile.TemporaryDirectory() as tmp:
        store = BM25Store(Path(tmp) / "corpus.json")
        chunks = [_make_chunk(f"ICT risk management chunk {i}", idx=i) for i in range(10)]
        store.add(chunks)
        results = store.search("ICT risk", k=3)
        assert len(results) <= 3


# ── Persistence ──────────────────────────────────────────────────────────────

def test_save_creates_parent_directories():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "deep" / "nested" / "corpus.json"
        store = BM25Store(path)
        store.add([_make_chunk("test", idx=0)])
        store.save()
        assert path.exists()


def test_save_and_load_round_trip():
    # Need 3+ chunks so the relevant term appears in a minority — BM25 IDF is 0
    # when a term appears in exactly half a 2-doc corpus.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "corpus.json"
        store = BM25Store(path)
        store.add([
            _make_chunk("Article 28 ICT risk requirements management", idx=0, articles=["28"]),
            _make_chunk("Article 30 third-party provider contractual obligations", idx=1, articles=["30"]),
            _make_chunk("General prudential reporting framework credit institutions", idx=2),
        ])
        store.save()

        store2 = BM25Store(path)
        store2.load()
        results = store2.search("ICT risk", k=3)

        assert len(results) >= 1, "Expected at least one result after round-trip"
        top = results[0]
        assert top.chunk_index == 0, f"ICT risk chunk should rank first, got {top.chunk_index}"
        assert top.articles == ["28"], f"Article metadata lost in round-trip: got {top.articles!r}"


def test_load_on_missing_file_is_noop():
    """Loading from a path that doesn't exist should not raise — index stays empty."""
    with tempfile.TemporaryDirectory() as tmp:
        store = BM25Store(Path(tmp) / "does_not_exist.json")
        store.load()
        assert store.search("anything") == []


def test_corpus_json_is_valid_after_save():
    """Saved file must be valid JSON so other tooling can read it."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "corpus.json"
        store = BM25Store(path)
        store.add([_make_chunk("risk management Article 28", idx=0, articles=["28"])])
        store.save()

        with open(path) as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert data[0]["chunk_index"] == 0
        assert data[0]["articles"] == ["28"]
        assert "text" in data[0]
