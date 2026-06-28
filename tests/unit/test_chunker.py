"""Unit tests for article-aware chunking.

The chunker has two jobs:
1. Detect article numbers in chunk text via regex.
2. Propagate the last-seen article number to subsequent body chunks
   so that regulation body text (which doesn't repeat "Article 28"
   in every paragraph) stays linked to its article for retrieval.
"""
import pytest
from typing import List
from backend.ingestion.chunker import _detect_articles, chunk_pages
from backend.ingestion.loader import RawPage


# ── Article detection ────────────────────────────────────────────────────────

def test_detect_single_article():
    assert _detect_articles("Under Article 28 of DORA") == ["28"]


def test_detect_plural_keyword():
    assert _detect_articles("Articles 26 establish requirements") == ["26"]


def test_detect_multiple_articles_separate():
    result = _detect_articles("Article 28 and Article 29 apply together")
    assert "28" in result
    assert "29" in result


def test_detect_ocr_variant_with_space():
    """Regex handles the 'Ar ticle' OCR artifact natively (before OCR clean)."""
    result = _detect_articles("Ar ticle 28 requires ICT risk management")
    assert "28" in result


def test_detect_returns_empty_for_plain_text():
    assert _detect_articles("This regulation establishes general requirements.") == []


def test_detect_case_insensitive():
    assert _detect_articles("ARTICLE 28") == ["28"]
    assert _detect_articles("article 12") == ["12"]


# ── chunk_pages ──────────────────────────────────────────────────────────────

def _make_pages(*texts: str, source: str = "test.pdf") -> List[RawPage]:
    return [
        RawPage(text=t, page_number=i + 1, source_file=source)
        for i, t in enumerate(texts)
    ]


def test_chunks_carry_source_metadata():
    pages = _make_pages("Article 28. Financial entities shall maintain ICT risk frameworks.")
    chunks = chunk_pages(pages)
    assert len(chunks) >= 1
    for c in chunks:
        assert c.source_file == "test.pdf"
        assert c.page_number == 1


def test_chunk_indices_are_sequential():
    """chunk_index must be contiguous starting at 0 across all pages."""
    pages = _make_pages("x" * 2000, "y" * 2000)
    chunks = chunk_pages(pages)
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(indices)))


def test_article_tag_set_on_header_chunk():
    text = "Article 28. Financial entities shall implement ICT risk management frameworks."
    pages = _make_pages(text)
    chunks = chunk_pages(pages)
    chunk_with_article = next((c for c in chunks if "28" in c.articles), None)
    assert chunk_with_article is not None, "No chunk tagged with Article 28"


def test_article_propagates_to_body_chunks():
    """
    Body text after an article header must inherit the article tag.
    This is the core invariant: retrieval for "Article 28" must surface
    body text that describes Article 28 even if it doesn't repeat the header.
    """
    header = "Article 28. Entities shall manage ICT risk.\n\n"
    body = "body_text " * 100  # enough text to force a second chunk
    pages = _make_pages(header + body)
    chunks = chunk_pages(pages)

    # At least two chunks (header + body overflow)
    assert len(chunks) >= 2

    # Find the first chunk tagged 28 (article header chunk)
    first_tagged = next((i for i, c in enumerate(chunks) if "28" in c.articles), None)
    assert first_tagged is not None, "Article 28 not detected in any chunk"

    # The immediately following chunk must also carry "28" via propagation
    if first_tagged + 1 < len(chunks):
        next_chunk = chunks[first_tagged + 1]
        assert "28" in next_chunk.articles, (
            f"Propagation failed: chunk {first_tagged + 1} has articles={next_chunk.articles!r}"
        )


def test_no_article_propagation_across_documents():
    """
    Article numbers from one document must not leak into a second document's
    chunks. chunk_pages resets last_seen_articles per call — each ingest
    job calls chunk_pages once per PDF, so this is naturally isolated.
    """
    pages1 = _make_pages("Article 5. General provisions apply here. " * 20, source="doc1.pdf")
    pages2 = _make_pages("General provisions and requirements. " * 20, source="doc2.pdf")

    chunks1 = chunk_pages(pages1)
    chunks2 = chunk_pages(pages2)

    # doc2 should start with no inherited articles
    first_chunk_doc2 = chunks2[0]
    assert first_chunk_doc2.articles != ["5"], (
        "Article '5' from doc1 leaked into doc2's first chunk — propagation crosses documents"
    )
