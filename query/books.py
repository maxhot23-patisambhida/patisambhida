"""Book-level queries."""

from __future__ import annotations

from .types import Book, Chapter


def list_books(engine, corpus_id: str) -> list[Book]:
    engine.ensure_corpus(corpus_id)
    corpus = engine.cache.corpus(corpus_id)
    return [engine.cache.book(corpus_id, ref.number) for ref in corpus.books]


def get_book(engine, corpus_id: str, book_number: int) -> Book:
    engine.ensure_book(corpus_id, book_number)
    return engine.cache.book(corpus_id, book_number)


def find_children(engine, book: Book) -> list[Chapter]:
    """Book -> its chapters, in order."""
    index = engine.cache.index(book.corpus_id, book.book_number, "chapters")
    return [index[cid] for cid in book.chapter_ids if cid in index]
