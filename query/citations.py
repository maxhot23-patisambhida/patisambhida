"""Citation-level queries (including source lookup and offset resolution)."""

from __future__ import annotations

from .exceptions import ObjectNotFound
from .types import Citation, Paragraph


def get_citation(engine, corpus_id: str, book_number: int, citation_id: str) -> Citation:
    engine.ensure_book(corpus_id, book_number)
    index = engine.cache.index(corpus_id, book_number, "citations")
    try:
        return index[citation_id]
    except KeyError:
        raise ObjectNotFound("citation", citation_id) from None


def find_parent(engine, citation: Citation) -> Paragraph:
    """Citation -> the paragraph it belongs to."""
    index = engine.cache.index(citation.corpus_id, citation.book_number, "paragraphs")
    try:
        return index[citation.paragraph_id]
    except KeyError:
        raise ObjectNotFound("paragraph", citation.paragraph_id) from None


def resolve(engine, citation: Citation) -> str:
    """Return the exact source text the citation's offset points to.

    Verifies the offset round-trips against canonical page text; raises if not.
    """
    pages = engine.cache.page_text(citation.corpus_id, citation.book_number)
    text = pages.get(citation.page)
    if text is None:
        raise ObjectNotFound("page", f"{citation.book_number}:{citation.page}")
    start, end = citation.offset
    resolved = text[start:end]
    if resolved != citation.quote:
        raise ObjectNotFound("citation-offset", citation.id)
    return resolved


def find_by_source(
    engine, source_file: str, *, corpus_id: str | None = None, book_number: int | None = None
) -> list[Citation]:
    """All citations whose provenance is a given source file."""
    hits: list[Citation] = []
    for cid, bn in engine.iter_books(corpus_id, book_number):
        for citation in engine.cache.collection(cid, bn, "citations"):
            if citation.source_file == source_file:
                hits.append(citation)
    return hits
