from pathlib import Path
from dataclasses import dataclass

from pypdf import PdfReader


@dataclass
class RawPage:
    text: str
    page_number: int      # 1-indexed, as printed in the regulation
    source_file: str      # basename of the PDF


def load_pdf(path: Path) -> list[RawPage]:
    """Extract text from every page of a PDF, one RawPage per page."""
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages.append(RawPage(
                text=text,
                page_number=i + 1,
                source_file=path.name,
            ))
    return pages


def load_directory(directory: Path, glob: str = "*.pdf") -> list[RawPage]:
    """Load all PDFs from a directory."""
    pages = []
    for pdf_path in sorted(directory.glob(glob)):
        pages.extend(load_pdf(pdf_path))
    return pages
