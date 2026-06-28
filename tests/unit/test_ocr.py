"""Unit tests for EUR-Lex OCR artifact cleaning (loader._clean_ocr).

EUR-Lex PDFs from the Official Journal have a systematic OCR defect:
the text renderer inserts spaces at hyphenation points, producing fragments
like "par ty", "ser vice", "fi nancial". These tests verify that every
known pattern is corrected before chunks enter the pipeline.
"""
import pytest
from backend.ingestion.loader import _clean_ocr


@pytest.mark.parametrize("raw, expected", [
    # Core legal / financial terms
    ("par ty",           "party"),
    ("par ties",         "parties"),
    ("ser vice",         "service"),
    ("ser vices",        "services"),
    ("fi nancial",       "financial"),
    ("r isk",            "risk"),
    ("provi de",         "provide"),
    ("provi der",        "provider"),
    ("provi ded",        "provided"),
    ("provi ders",       "providers"),
    ("provi ding",       "providing"),
    # Multi-word management terms
    ("manag ement",      "management"),
    ("monitori ng",      "monitoring"),
    ("oper ational",     "operational"),
    ("oper ations",      "operations"),
    ("im pact",          "impact"),
    ("im pacts",         "impacts"),
    ("im plement",       "implement"),
    ("im plementation",  "implementation"),
    # Regulatory identifiers
    ("enter prise",      "enterprise"),
    ("enter prises",     "enterprises"),
    ("ter minated",      "terminated"),
    ("ter mination",     "termination"),
    ("continge ncy",     "contingency"),
    ("contingenc y",     "contingency"),
    # Critical: article markers — must be fixed before article detection in chunker
    ("Ar ticle 28",      "Article 28"),
    ("Ar ticles 26",     "Articles 26"),
    # EUR cybersecurity compound
    ("cyber security",   "cybersecurity"),
    ("in formation",     "information"),
    ("in f ormation",    "information"),
    ("requir ement",     "requirement"),
    ("requir ements",    "requirements"),
    ("requir ed",        "required"),
    ("refer red",        "referred"),
])
def test_ocr_fixes_known_artifact(raw, expected):
    assert _clean_ocr(raw) == expected


def test_ocr_collapses_multiple_spaces():
    assert _clean_ocr("hello   world") == "hello world"
    assert _clean_ocr("a  b   c") == "a b c"


def test_ocr_fixes_soft_hyphen_linebreak():
    """Words split across lines with a trailing hyphen must be rejoined."""
    assert _clean_ocr("opera-\ntional") == "operational"
    assert _clean_ocr("manage-\nment") == "management"


def test_ocr_is_idempotent():
    """Applying the cleaner twice should produce the same result as once."""
    text = "fi nancial ser vices par ty Ar ticle 28"
    once = _clean_ocr(text)
    twice = _clean_ocr(once)
    assert once == twice


def test_ocr_leaves_clean_text_unchanged():
    """Already-correct text should not be mangled."""
    clean = "The financial party provides services under Article 28."
    result = _clean_ocr(clean)
    assert "financial" in result
    assert "Article 28" in result
    assert "party" in result
    assert "services" in result


def test_ocr_article_fix_enables_detection():
    """After cleaning, 'Ar ticle' becomes 'Article' which the chunker regex can detect."""
    import re
    ARTICLE_RE = re.compile(r'\bArticles?\s+(\d+)', re.IGNORECASE)
    raw = "Ar ticle 28 sets out the requirements"
    cleaned = _clean_ocr(raw)
    matches = ARTICLE_RE.findall(cleaned)
    assert "28" in matches, f"Article detection failed after OCR clean — got: {matches!r}"
