"""Paragraph-level queries (including page lookup)."""

from __future__ import annotations

from .exceptions import ObjectNotFound
from .types import Citation, KnowledgeObject, Paragraph, Section


def get_paragraph(engine, corpus_id: str, book_number: int, paragraph_id: str) -> Paragraph:
    engine.ensure_book(corpus_id, book_number)
    index = engine.cache.index(corpus_id, book_number, "paragraphs")
    try:
        return index[paragraph_id]
    except KeyError:
        raise ObjectNotFound("paragraph", paragraph_id) from None


def find_parent(engine, paragraph: Paragraph) -> Section:
    """Paragraph -> its section."""
    index = engine.cache.index(paragraph.corpus_id, paragraph.book_number, "sections")
    try:
        return index[paragraph.section_id]
    except KeyError:
        raise ObjectNotFound("section", paragraph.section_id) from None


def find_children(engine, paragraph: Paragraph) -> list:
    """Paragraph -> its citation, plus any Knowledge Objects sourced from it."""
    children: list = []
    if paragraph.citation_id:
        citations = engine.cache.index(paragraph.corpus_id, paragraph.book_number, "citations")
        if paragraph.citation_id in citations:
            children.append(citations[paragraph.citation_id])
    for ko in engine.cache.collection(paragraph.corpus_id, paragraph.book_number, "knowledge"):
        if ko.source_paragraph_id == paragraph.id:
            children.append(ko)
    return children


def find_by_page(
    engine, page: int, *, corpus_id: str | None = None, book_number: int | None = None
) -> list[Paragraph]:
    """All paragraphs on a given source page."""
    hits: list[Paragraph] = []
    for cid, bn in engine.iter_books(corpus_id, book_number):
        for paragraph in engine.cache.collection(cid, bn, "paragraphs"):
            if paragraph.page == page:
                hits.append(paragraph)
    return hits
