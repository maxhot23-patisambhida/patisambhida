"""Chapter-level queries."""

from __future__ import annotations

from .exceptions import ObjectNotFound
from .types import Book, Chapter, Section


def get_chapter(engine, corpus_id: str, book_number: int, chapter_id: str) -> Chapter:
    engine.ensure_book(corpus_id, book_number)
    index = engine.cache.index(corpus_id, book_number, "chapters")
    try:
        return index[chapter_id]
    except KeyError:
        raise ObjectNotFound("chapter", chapter_id) from None


def find_parent(engine, chapter: Chapter) -> Book:
    """Chapter -> its book."""
    return engine.cache.book(chapter.corpus_id, chapter.book_number)


def find_children(engine, chapter: Chapter) -> list[Section]:
    """Chapter -> its sections, in order."""
    index = engine.cache.index(chapter.corpus_id, chapter.book_number, "sections")
    return [index[sid] for sid in chapter.section_ids if sid in index]
