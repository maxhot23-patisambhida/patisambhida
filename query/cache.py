"""Transparent read cache.

The cache sits between the Query Engine and the Repository Loader. It memoises
typed collections, per-kind id indexes, page text and manifests so repeated
queries don't re-read or re-parse files.

The cache is disposable and read-only: it never writes, never mutates canonical
content, and can be cleared at any time without affecting the repository. Every
object it returns is already a typed object from ``types.py`` — raw JSON never
escapes this layer.
"""

from __future__ import annotations

from .types import BUILDERS, Book, Corpus, Manifest


class Cache:
    def __init__(self, loader) -> None:
        self._loader = loader
        self._collections: dict[tuple[str, int, str], tuple] = {}
        self._indexes: dict[tuple[str, int, str], dict] = {}
        self._pages: dict[tuple[str, int], dict[int, str]] = {}
        self._manifests: dict[tuple[str, int], Manifest] = {}
        self._books: dict[tuple[str, int], Book] = {}
        self._corpora: tuple[str, ...] | None = None
        self._corpus_objs: dict[str, Corpus] = {}

    # ── disposability ────────────────────────────────────────────────────
    def clear(self) -> None:
        """Drop every cached value. The repository is unaffected."""
        self._collections.clear()
        self._indexes.clear()
        self._pages.clear()
        self._manifests.clear()
        self._books.clear()
        self._corpus_objs.clear()
        self._corpora = None

    # ── corpus / book discovery ──────────────────────────────────────────
    def corpora(self) -> tuple[str, ...]:
        if self._corpora is None:
            self._corpora = tuple(self._loader.list_corpora())
        return self._corpora

    def corpus(self, corpus_id: str) -> Corpus:
        if corpus_id not in self._corpus_objs:
            self._corpus_objs[corpus_id] = Corpus.from_dict(self._loader.corpus(corpus_id))
        return self._corpus_objs[corpus_id]

    def manifest(self, corpus_id: str, book_number: int) -> Manifest:
        key = (corpus_id, book_number)
        if key not in self._manifests:
            self._manifests[key] = Manifest.from_dict(self._loader.manifest(corpus_id, book_number))
        return self._manifests[key]

    def book(self, corpus_id: str, book_number: int) -> Book:
        key = (corpus_id, book_number)
        if key not in self._books:
            doc = self._loader.book(corpus_id, book_number)
            self._books[key] = Book.from_dict(doc["book"], corpus_id, book_number)
        return self._books[key]

    def page_text(self, corpus_id: str, book_number: int) -> dict[int, str]:
        key = (corpus_id, book_number)
        if key not in self._pages:
            self._pages[key] = dict(self._loader.page_text(corpus_id, book_number))
        return self._pages[key]

    # ── typed collections + indexes ──────────────────────────────────────
    def collection(self, corpus_id: str, book_number: int, kind: str) -> tuple:
        key = (corpus_id, book_number, kind)
        if key not in self._collections:
            build = BUILDERS[kind]
            raw = self._loader.objects(corpus_id, book_number, kind)
            self._collections[key] = tuple(build(d, corpus_id, book_number) for d in raw)
        return self._collections[key]

    def index(self, corpus_id: str, book_number: int, kind: str) -> dict:
        key = (corpus_id, book_number, kind)
        if key not in self._indexes:
            self._indexes[key] = {obj.id: obj for obj in self.collection(corpus_id, book_number, kind)}
        return self._indexes[key]
