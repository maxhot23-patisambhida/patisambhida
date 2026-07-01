"""Deterministic search and id lookup.

No AI, no embeddings, no semantic ranking, no inference — only deterministic
retrieval. Results are returned in a stable order (book order, then a fixed kind
order, then collection order) so the same query always yields the same list.

Searchable text fields per kind:
  book       title
  chapter    title
  section    title, marker
  paragraph  text
  citation   quote
  knowledge  primary name, pali, english, aliases
"""

from __future__ import annotations

import re

from .exceptions import ObjectNotFound
from .types import SearchHit

# Object kinds scanned for id lookup, in deterministic order.
_ID_KINDS = ("chapters", "sections", "paragraphs", "citations", "knowledge", "evidence", "relationships")

# Kinds searched by the text searches, in deterministic order.
_TEXT_KINDS = ("book", "chapter", "section", "paragraph", "citation", "knowledge")


def _snippet(value: str, start: int, end: int, pad: int = 30) -> str:
    lo = max(0, start - pad)
    hi = min(len(value), end + pad)
    prefix = "…" if lo > 0 else ""
    suffix = "…" if hi < len(value) else ""
    return f"{prefix}{value[lo:hi]}{suffix}".replace("\n", " ")


def _searchable(engine, corpus_id, book_number, kinds):
    """Yield (corpus_id, book_number, kind, obj, field, value) for searchable fields."""
    for cid, bn in engine.iter_books(corpus_id, book_number):
        if "book" in kinds:
            book = engine.cache.book(cid, bn)
            yield (cid, bn, "book", book, "title", book.title)
        if "chapter" in kinds:
            for ch in engine.cache.collection(cid, bn, "chapters"):
                yield (cid, bn, "chapter", ch, "title", ch.title)
        if "section" in kinds:
            for sec in engine.cache.collection(cid, bn, "sections"):
                yield (cid, bn, "section", sec, "title", sec.title or "")
                yield (cid, bn, "section", sec, "marker", sec.marker or "")
        if "paragraph" in kinds:
            for para in engine.cache.collection(cid, bn, "paragraphs"):
                yield (cid, bn, "paragraph", para, "text", para.text)
        if "citation" in kinds:
            for cit in engine.cache.collection(cid, bn, "citations"):
                yield (cid, bn, "citation", cit, "quote", cit.quote)
        if "knowledge" in kinds:
            for ko in engine.cache.collection(cid, bn, "knowledge"):
                yield (cid, bn, "knowledge", ko, "name", ko.names.primary)
                if ko.names.pali:
                    yield (cid, bn, "knowledge", ko, "pali", ko.names.pali)
                if ko.names.english:
                    yield (cid, bn, "knowledge", ko, "english", ko.names.english)
                for alias in ko.names.aliases:
                    yield (cid, bn, "knowledge", ko, "alias", alias)


def _run(engine, predicate, locate, *, kinds, corpus_id, book_number) -> list[SearchHit]:
    kinds = tuple(kinds) if kinds is not None else _TEXT_KINDS
    hits: list[SearchHit] = []
    for cid, bn, kind, obj, field, value in _searchable(engine, corpus_id, book_number, kinds):
        if not value:
            continue
        span = predicate(value)
        if span is None:
            continue
        start, end = locate(value, span)
        hits.append(SearchHit(
            corpus_id=cid, book_number=bn, kind=kind, object_id=obj.id,
            field=field, snippet=_snippet(value, start, end), obj=obj,
        ))
    return hits


def search_contains(engine, query, *, kinds=None, corpus_id=None, book_number=None) -> list[SearchHit]:
    """Case-insensitive substring search."""
    needle = query.casefold()

    def predicate(value: str):
        idx = value.casefold().find(needle)
        return idx if idx >= 0 else None

    def locate(value: str, idx: int):
        return (idx, idx + len(query))

    return _run(engine, predicate, locate, kinds=kinds, corpus_id=corpus_id, book_number=book_number)


# search_text is the general-purpose text search (alias of contains).
def search_text(engine, query, *, kinds=None, corpus_id=None, book_number=None) -> list[SearchHit]:
    return search_contains(engine, query, kinds=kinds, corpus_id=corpus_id, book_number=book_number)


def search_exact(engine, query, *, kinds=None, corpus_id=None, book_number=None) -> list[SearchHit]:
    """Whole-field exact equality (case-sensitive)."""
    def predicate(value: str):
        return True if value == query else None

    def locate(value: str, _):
        return (0, len(value))

    return _run(engine, predicate, locate, kinds=kinds, corpus_id=corpus_id, book_number=book_number)


def search_prefix(engine, query, *, kinds=None, corpus_id=None, book_number=None) -> list[SearchHit]:
    """Case-insensitive field prefix match."""
    needle = query.casefold()

    def predicate(value: str):
        return True if value.casefold().startswith(needle) else None

    def locate(value: str, _):
        return (0, len(query))

    return _run(engine, predicate, locate, kinds=kinds, corpus_id=corpus_id, book_number=book_number)


def search_regex(engine, pattern, *, flags=0, kinds=None, corpus_id=None, book_number=None) -> list[SearchHit]:
    """Deterministic regular-expression search (re.search per field)."""
    compiled = re.compile(pattern, flags)

    def predicate(value: str):
        return compiled.search(value)

    def locate(value: str, match):
        return (match.start(), match.end())

    return _run(engine, predicate, locate, kinds=kinds, corpus_id=corpus_id, book_number=book_number)


def find_by_id(engine, object_id, *, corpus_id=None, book_number=None):
    """Resolve any object by its canonical id to a typed object."""
    for cid, bn in engine.iter_books(corpus_id, book_number):
        book = engine.cache.book(cid, bn)
        if book.id == object_id:
            return book
        for kind in _ID_KINDS:
            index = engine.cache.index(cid, bn, kind)
            if object_id in index:
                return index[object_id]
    raise ObjectNotFound("object", object_id)
