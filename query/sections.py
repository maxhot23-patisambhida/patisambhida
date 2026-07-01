"""Section-level queries (including marker lookup)."""

from __future__ import annotations

from .exceptions import ObjectNotFound
from .types import Chapter, Paragraph, Section


def get_section(engine, corpus_id: str, book_number: int, section_id: str) -> Section:
    engine.ensure_book(corpus_id, book_number)
    index = engine.cache.index(corpus_id, book_number, "sections")
    try:
        return index[section_id]
    except KeyError:
        raise ObjectNotFound("section", section_id) from None


def find_parent(engine, section: Section) -> Chapter:
    """Section -> its chapter."""
    index = engine.cache.index(section.corpus_id, section.book_number, "chapters")
    try:
        return index[section.chapter_id]
    except KeyError:
        raise ObjectNotFound("chapter", section.chapter_id) from None


def find_children(engine, section: Section) -> list[Paragraph]:
    """Section -> its paragraphs, in order."""
    index = engine.cache.index(section.corpus_id, section.book_number, "paragraphs")
    return [index[pid] for pid in section.paragraph_ids if pid in index]


def find_by_marker(
    engine, marker_number: int, *, corpus_id: str | None = None, book_number: int | None = None
) -> list[Section]:
    """All sections carrying a given canonical bracket marker number."""
    hits: list[Section] = []
    for cid, bn in engine.iter_books(corpus_id, book_number):
        for section in engine.cache.collection(cid, bn, "sections"):
            if section.marker_number == marker_number:
                hits.append(section)
    return hits
