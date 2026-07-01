"""ID generator stage: assign canonical, deterministic identifiers.

Every ID is a pure function of structural position (book number + chapter /
section / paragraph index). The same input therefore always yields the same ID
— a hard requirement for reproducibility. IDs are hierarchical and human-
readable so provenance is legible at a glance.

  Book             PKA-B01
  Chapter          PKA-B01-CH01
  Section          PKA-B01-CH01-S001
  Paragraph        PKA-B01-CH01-S001-P0001
  Citation         PKA-B01-CH01-S001-P0001-CIT
  Knowledge Object KNW-B01-0001

The ``KNW-Bnn-NNNN`` form follows the ``KNW-0001 .. KNW-NNNN`` convention of
PKA-SCH-001 (Knowledge Schema Standard), namespaced by book so per-book
compilation never collides.
"""

from __future__ import annotations


def book_id(book_number: int) -> str:
    return f"PKA-B{book_number:02d}"


def chapter_id(book_number: int, chapter_index: int) -> str:
    return f"{book_id(book_number)}-CH{chapter_index:02d}"


def section_id(book_number: int, chapter_index: int, section_index: int) -> str:
    return f"{chapter_id(book_number, chapter_index)}-S{section_index:03d}"


def paragraph_id(
    book_number: int, chapter_index: int, section_index: int, paragraph_index: int
) -> str:
    base = section_id(book_number, chapter_index, section_index)
    return f"{base}-P{paragraph_index:04d}"


def citation_id(para_id: str) -> str:
    return f"{para_id}-CIT"


def knowledge_id(book_number: int, knowledge_index: int) -> str:
    return f"KNW-B{book_number:02d}-{knowledge_index:04d}"
