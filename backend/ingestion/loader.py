import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

from pypdf import PdfReader


@dataclass
class RawPage:
    text: str
    page_number: int      # 1-indexed, as printed in the regulation
    source_file: str      # basename of the PDF


# EUR-Lex PDFs from the official journal have a known OCR artifact: the
# text renderer inserts a space after every 2-3 characters at hyphenation
# points, producing fragments like "par ty", "ser vice", "fi nancial".
# These rules are ordered from most-specific to most-general.
_OCR_FIXES = [
    # Common legal/financial terms split by OCR
    (r'\bpar ty\b',         'party'),
    (r'\bpar ties\b',       'parties'),
    (r'\bser vice\b',       'service'),
    (r'\bser vices\b',      'services'),
    (r'\bfi nancial\b',     'financial'),
    (r'\br isk\b',          'risk'),
    (r'\bprovi de\b',       'provide'),
    (r'\bprovi der\b',      'provider'),
    (r'\bprovi ded\b',      'provided'),
    (r'\bprovi ders\b',     'providers'),
    (r'\bprovi ding\b',     'providing'),
    (r'\bcontinge ncy\b',   'contingency'),
    (r'\bcontingenc y\b',   'contingency'),
    (r'\bmanag ement\b',    'management'),
    (r'\bmonitori ng\b',    'monitoring'),
    (r'\brefer red\b',      'referred'),
    (r'\brequir ed\b',      'required'),
    (r'\brequir ement\b',   'requirement'),
    (r'\brequir ements\b',  'requirements'),
    (r'\benter prises\b',   'enterprises'),
    (r'\benter prise\b',    'enterprise'),
    (r'\bcontractual ar rang', 'contractual arrang'),
    (r'\baar rang ement\b', 'arrangement'),
    (r'\baar rang ements\b','arrangements'),
    (r'\bim pact\b',        'impact'),
    (r'\bim pacts\b',       'impacts'),
    (r'\bim plement\b',     'implement'),
    (r'\bim plementation\b','implementation'),
    (r'\bter minated\b',    'terminated'),
    (r'\bter mination\b',   'termination'),
    (r'\boper ational\b',   'operational'),
    (r'\boper ations\b',    'operations'),
    (r'\bin f ormation\b',  'information'),
    (r'\bin formation\b',   'information'),
    (r'\bcyber security\b', 'cybersecurity'),
    # Fix "Ar ticle" → "Article" (critical for article detection in chunker)
    (r'\bAr ticle\b',       'Article'),
    (r'\bAr ticles\b',      'Articles'),
    # Remove soft-hyphen line breaks: "opera-\ntional" → "operational"
    (r'(\w)-\n(\w)',        r'\1\2'),
    # Collapse multiple spaces
    (r'  +',                ' '),
]

_COMPILED_FIXES = [(re.compile(p, re.IGNORECASE), r) for p, r in _OCR_FIXES]


def _clean_ocr(text: str) -> str:
    """Apply EUR-Lex OCR artifact corrections to raw extracted text."""
    for pattern, replacement in _COMPILED_FIXES:
        text = pattern.sub(replacement, text)
    return text


def load_pdf(path: Path) -> List[RawPage]:
    """Extract and OCR-clean text from every page of a PDF."""
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages):
        raw = page.extract_text() or ""
        text = _clean_ocr(raw.strip())
        if text:
            pages.append(RawPage(
                text=text,
                page_number=i + 1,
                source_file=path.name,
            ))
    return pages


def load_directory(directory: Path, glob: str = "*.pdf") -> List[RawPage]:
    """Load and clean all PDFs from a directory."""
    pages = []
    for pdf_path in sorted(directory.glob(glob)):
        pages.extend(load_pdf(pdf_path))
    return pages
