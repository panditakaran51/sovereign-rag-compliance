import re
from dataclasses import dataclass, field
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.ingestion.loader import RawPage
from backend.config import settings

# Matches "Article 28", "Articles 26 and 27", "Ar ticle 28" (OCR artifact with space)
# The (?:\s*t)? handles "Ar ticle" where the 't' gets separated
_ARTICLE_RE = re.compile(r'\bAr\s?ticles?\s+(\d+)', re.IGNORECASE)


def _detect_articles(text: str) -> List[str]:
    """Return all article numbers mentioned in the text, e.g. ['28', '29']."""
    return _ARTICLE_RE.findall(text)


@dataclass
class Chunk:
    text: str
    source_file: str
    page_number: int
    chunk_index: int
    char_start: int
    articles: List[str] = field(default_factory=list)  # e.g. ['28', '29']


def chunk_pages(pages: List[RawPage]) -> List[Chunk]:
    """
    Split raw pages into overlapping chunks.

    Each chunk carries the article numbers detected in its text.
    If a chunk contains no article reference, we propagate the last
    seen article from earlier in the same document — because regulation
    body text often refers to its own article without repeating the header.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: List[Chunk] = []
    global_index = 0
    last_seen_articles: List[str] = []

    for page in pages:
        splits = splitter.split_text(page.text)
        char_cursor = 0

        for split in splits:
            char_start = page.text.find(split, char_cursor)
            if char_start == -1:
                char_start = char_cursor
            char_cursor = char_start + len(split)

            detected = _detect_articles(split)
            if detected:
                last_seen_articles = detected
            # Propagate last seen articles so body text stays linked to its article
            articles = detected if detected else last_seen_articles

            chunks.append(Chunk(
                text=split,
                source_file=page.source_file,
                page_number=page.page_number,
                chunk_index=global_index,
                char_start=char_start,
                articles=articles,
            ))
            global_index += 1

    return chunks
