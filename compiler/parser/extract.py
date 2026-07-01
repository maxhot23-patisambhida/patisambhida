"""Parser stage: extract raw text from a PKA book PDF.

Uses ``pypdf`` — the same library as ``scripts/build_content.py`` — so the
compiler's extraction matches the project's canonical digitisation. Book-9 and
book-10 carry legacy-font encoding damage; the raw-text repairs that fix it
(``fix_ascii_diacritics`` / ``fix_pua_encoding``) are reused from the same
script as the single source of truth for those OCR corrections.

Extraction is the only environment-dependent step in the whole compiler: given
the same ``pypdf`` version and the same PDF bytes, ``extract_pdf`` is
deterministic. The returned ``sha256`` lets any consumer verify the exact input.
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

# Reuse the project's canonical Thai/OCR repairs and digit helpers.
_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from build_content import (  # noqa: E402  (path injected above)
    fix_ascii_diacritics,
    fix_pua_encoding,
    thai_digit_to_int,
)


@dataclass(frozen=True)
class ExtractedPage:
    number: int          # 1-based page number
    raw: str             # raw (font-repaired) extracted text, pre-normalization


@dataclass(frozen=True)
class ExtractedBook:
    number: int          # book number (1..10)
    slug: str            # e.g. "book-01"
    title: str           # PDF stem
    file: str            # PDF file name
    sha256: str          # hash of the source PDF bytes
    pages: tuple[ExtractedPage, ...]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _apply_font_repair(book_number: int, raw: str) -> str:
    """Apply book-specific legacy-font repairs to raw extracted text."""
    if book_number == 10:
        return fix_pua_encoding(raw)
    if book_number == 9:
        return fix_ascii_diacritics(raw)
    return raw


def extract_pdf(pdf_path: str | Path, *, fallback_number: int = 1) -> ExtractedBook:
    """Extract raw, font-repaired text from a PKA book PDF, page by page."""
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")

    number = thai_digit_to_int(path.stem) or fallback_number
    slug = f"book-{number:02d}"
    reader = PdfReader(str(path))

    pages: list[ExtractedPage] = []
    for page_index, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        raw = _apply_font_repair(number, raw)
        pages.append(ExtractedPage(number=page_index, raw=raw))

    return ExtractedBook(
        number=number,
        slug=slug,
        title=path.stem,
        file=path.name,
        sha256=_sha256(path),
        pages=tuple(pages),
    )
