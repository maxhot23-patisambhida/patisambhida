"""KOS Compiler pipeline — end-to-end orchestration.

    PDF -> Extract Text -> Normalize -> Split Paragraphs
        -> Assign Canonical IDs -> Attach Citation -> Export JSON

Every stage is deterministic. The output document contains six object kinds —
Book, Chapter, Section, Paragraph, Citation, Knowledge Object — each carrying a
canonical ID and explicit parent references, plus the canonical page text the
Citation offsets point into.

Structural rules (deterministic, no inference):
  * Chapter — a new chapter opens at a heading paragraph that names a structural
    unit of the Pali corpus (นิทเทส / ภาณวาระ / มาติกา / อุทเทส / กถา / วรรค) and
    is short (<= 70 chars). Content before the first such heading forms chapter 1,
    titled from the book.
  * Section — within a chapter, a new section opens at a canonical bracketed
    passage marker ([๓๐], [64], ...) — the traditional citation anchors of the
    text — or, failing that, at a (sub)heading. Marker number is recorded.
  * Paragraph — the atomic unit: a contiguous run of lines within one page,
    bounded by blank lines, bracket markers and headings. A paragraph is always a
    contiguous substring of its page's canonical text, so its Citation offset
    round-trips exactly.
  * Knowledge Object — one candidate object per heading paragraph, shaped to the
    12 sections of PKA-SCH-001. Only deterministically-extractable fields are
    filled (identity, primary name, citation, provenance); semantic fields
    (definition, classification, relationship) are left empty for later, governed
    human/AI enrichment. No inference happens here.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from . import SCHEMA_VERSION
from .normalizer import NORMALIZATION_VERSION, normalize_page
from .parser import ExtractedBook, extract_pdf

# Load the hyphen-named id-generator package by file path.
_IDS_PATH = Path(__file__).parent / "id-generator" / "ids.py"
_ids_spec = importlib.util.spec_from_file_location("kos_compiler_ids", _IDS_PATH)
ids = importlib.util.module_from_spec(_ids_spec)
assert _ids_spec and _ids_spec.loader
_ids_spec.loader.exec_module(ids)


# ── deterministic recognisers ────────────────────────────────────────────────

# Bracketed canonical passage marker at the start of a line, e.g. "[๓๐]" / "[64]".
_BRACKET_MARKER = re.compile(r"^\[\s*([๐-๙]+|\d+)\s*\]")
# Numbered heading, e.g. "๑.", "12)", "[5]".
_NUMBERED_HEADING = re.compile(r"^(\[?\d+\]?|[๑-๙][๐-๙]*)[.)]\s+\S")
# Structural keywords that mark a major division (chapter-level).
_CHAPTER_KEYWORDS = ("นิทเทส", "ภาณวาระ", "มาติกา", "อุทเทส", "กถา", "วรรค")
# Heading-flavoured keywords (heading detection, mirrors build_content.detect_headings).
_HEADING_KEYWORDS = _CHAPTER_KEYWORDS + ("ญาณ", "สารบัญ")

_THAI_DIGITS = "๐๑๒๓๔๕๖๗๘๙"


def _marker_to_int(text: str) -> int:
    """Parse a Thai- or Arabic-digit marker string to int."""
    if text and text[0] in _THAI_DIGITS:
        return int("".join(str(_THAI_DIGITS.index(c)) for c in text))
    return int(text)


def _is_heading(line: str) -> bool:
    """Deterministic heading test (a single, already-stripped line)."""
    if not line or len(line) > 90:
        return False
    if _NUMBERED_HEADING.match(line):
        return True
    if len(line) <= 70 and any(k in line for k in _HEADING_KEYWORDS):
        return True
    return False


def _is_chapter_heading(line: str) -> bool:
    return len(line) <= 70 and any(k in line for k in _CHAPTER_KEYWORDS) and _is_heading(line)


# ── Split Paragraphs ─────────────────────────────────────────────────────────

def _segment_page(text: str) -> list[tuple[int, int]]:
    """Split canonical page text into paragraph spans ``(start, end)``.

    Each span is offsets into ``text`` such that ``text[start:end]`` is the exact
    paragraph content (leading/trailing whitespace trimmed). Breaks occur at
    blank lines, bracket markers and headings.
    """
    spans: list[tuple[int, int]] = []
    cur_start: int | None = None
    cur_end: int | None = None

    for m in re.finditer(r"[^\n]*\n?", text):
        if m.start() == m.end():
            break
        line = m.group(0).strip()
        if line == "":  # blank line -> paragraph break
            if cur_start is not None:
                spans.append((cur_start, cur_end))  # type: ignore[arg-type]
                cur_start = cur_end = None
            continue
        starts_block = bool(_BRACKET_MARKER.match(line)) or _is_heading(line)
        if starts_block and cur_start is not None:
            spans.append((cur_start, cur_end))  # type: ignore[arg-type]
            cur_start = cur_end = None
        if cur_start is None:
            cur_start = m.start()
        cur_end = m.end()

    if cur_start is not None:
        spans.append((cur_start, cur_end))  # type: ignore[arg-type]

    # Trim each span to its non-whitespace content.
    trimmed: list[tuple[int, int]] = []
    for start, end in spans:
        chunk = text[start:end]
        lead = len(chunk) - len(chunk.lstrip())
        trail = len(chunk) - len(chunk.rstrip())
        s, e = start + lead, end - trail
        if e > s:
            trimmed.append((s, e))
    return trimmed


# ── pipeline ─────────────────────────────────────────────────────────────────

def compile_book(pdf_path: str | Path, *, fallback_number: int = 1) -> dict:
    """Run the full pipeline on one PDF and return the canonical object document."""
    extracted: ExtractedBook = extract_pdf(pdf_path, fallback_number=fallback_number)
    bn = extracted.number

    # Stage: Normalize -> canonical page text (offsets point into this).
    pages = [
        {"number": p.number, "text": normalize_page(p.raw)}
        for p in extracted.pages
    ]

    chapters: list[dict] = []
    sections: list[dict] = []
    paragraphs: list[dict] = []
    citations: list[dict] = []
    knowledge_objects: list[dict] = []

    chapter_i = 0
    section_i = 0
    para_i = 0
    knw_i = 0
    cur_chapter: dict | None = None
    cur_section: dict | None = None

    def open_chapter(title: str, page_no: int) -> dict:
        nonlocal chapter_i, section_i, cur_section
        chapter_i += 1
        section_i = 0
        cur_section = None
        ch = {
            "id": ids.chapter_id(bn, chapter_i),
            "type": "Chapter",
            "bookId": ids.book_id(bn),
            "index": chapter_i,
            "title": title,
            "startPage": page_no,
            "endPage": page_no,
            "sectionIds": [],
        }
        chapters.append(ch)
        return ch

    def open_section(marker: str | None, marker_num: int | None,
                     title: str | None, page_no: int) -> dict:
        nonlocal section_i, para_i, cur_section
        section_i += 1
        para_i = 0
        sec = {
            "id": ids.section_id(bn, chapter_i, section_i),
            "type": "Section",
            "bookId": ids.book_id(bn),
            "chapterId": cur_chapter["id"],
            "index": section_i,
            "marker": marker,
            "markerNumber": marker_num,
            "title": title,
            "startPage": page_no,
            "endPage": page_no,
            "paragraphIds": [],
        }
        sections.append(sec)
        cur_chapter["sectionIds"].append(sec["id"])
        return sec

    for page in pages:
        text = page["text"]
        page_no = page["number"]
        for start, end in _segment_page(text):
            content = text[start:end]
            first_line = content.split("\n", 1)[0].strip()

            # ── Chapter assignment ──
            if _is_chapter_heading(first_line):
                cur_chapter = open_chapter(first_line, page_no)
            if cur_chapter is None:
                cur_chapter = open_chapter(extracted.title, page_no)
            cur_chapter["endPage"] = page_no

            # ── Section assignment ──
            marker_match = _BRACKET_MARKER.match(first_line)
            if marker_match:
                raw_num = marker_match.group(1)
                cur_section = open_section(
                    marker_match.group(0), _marker_to_int(raw_num), None, page_no
                )
            elif cur_section is None:
                title = first_line if _is_heading(first_line) else None
                cur_section = open_section(None, None, title, page_no)
            elif _is_heading(first_line):
                cur_section = open_section(None, None, first_line, page_no)
            cur_section["endPage"] = page_no

            # ── Paragraph + Canonical ID ──
            para_i += 1
            pid = ids.paragraph_id(bn, chapter_i, section_i, para_i)
            is_heading = _is_heading(first_line)
            para = {
                "id": pid,
                "type": "Paragraph",
                "bookId": ids.book_id(bn),
                "chapterId": cur_chapter["id"],
                "sectionId": cur_section["id"],
                "index": para_i,
                "page": page_no,
                "offset": [start, end],
                "charCount": end - start,
                "isHeading": is_heading,
                "text": content,
                "citationId": None,
            }

            # ── Attach Citation (provenance path) ──
            cid = ids.citation_id(pid)
            citation = {
                "id": cid,
                "type": "Citation",
                "paragraphId": pid,
                "bookId": ids.book_id(bn),
                "sourceFile": extracted.file,
                "sourceSha256": extracted.sha256,
                "page": page_no,
                "offset": [start, end],
                "quote": content,
            }
            para["citationId"] = cid
            paragraphs.append(para)
            citations.append(citation)
            cur_section["paragraphIds"].append(pid)

            # ── Knowledge Object (SCH-001 shell, one per heading) ──
            if is_heading:
                knw_i += 1
                knowledge_objects.append(
                    _knowledge_object(bn, knw_i, first_line, para, citation)
                )

    book = {
        "id": ids.book_id(bn),
        "type": "Book",
        "number": bn,
        "slug": extracted.slug,
        "title": extracted.title,
        "sourceFile": extracted.file,
        "sourceSha256": extracted.sha256,
        "pageCount": len(pages),
        "charCount": sum(len(p["text"]) for p in pages),
        "chapterIds": [c["id"] for c in chapters],
    }

    return {
        "schemaVersion": SCHEMA_VERSION,
        "toolchain": {
            "compiler": SCHEMA_VERSION,
            "normalizer": NORMALIZATION_VERSION,
        },
        "source": {
            "file": extracted.file,
            "sha256": extracted.sha256,
            "pages": len(pages),
        },
        "book": book,
        "chapters": chapters,
        "sections": sections,
        "paragraphs": paragraphs,
        "citations": citations,
        "knowledgeObjects": knowledge_objects,
        "pageText": pages,
        "stats": {
            "chapters": len(chapters),
            "sections": len(sections),
            "paragraphs": len(paragraphs),
            "citations": len(citations),
            "knowledgeObjects": len(knowledge_objects),
        },
    }


def _knowledge_object(book_number: int, index: int, name: str,
                      para: dict, citation: dict) -> dict:
    """Build an SCH-001-shaped Knowledge Object shell (12 sections).

    Deterministic fields only — no semantic inference. Definition,
    classification and relationships stay empty for later governed enrichment.
    """
    kid = ids.knowledge_id(book_number, index)
    return {
        "id": kid,
        "type": "KnowledgeObject",
        "schema": "PKA-SCH-001",
        "identity": {"code": kid},
        "names": {"primary": name, "pali": None, "english": None, "aliases": []},
        "definition": {"text": None},
        "classification": {"type": None},
        "relationship": [],
        "citation": {
            "citationId": citation["id"],
            "sourceFile": citation["sourceFile"],
            "page": citation["page"],
            "offset": citation["offset"],
        },
        "evidence": {"level": "A", "basis": "primary-source-extraction"},
        "language": {"primary": "th", "representations": ["th", "pi"]},
        "quality": {"completeness": "extracted"},
        "approval": {"status": "unreviewed"},
        "lifecycle": {"state": "extracted"},
        "metadata": {
            "sourceParagraphId": para["id"],
            "compiler": SCHEMA_VERSION,
        },
    }
