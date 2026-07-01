"""The Query Engine facade — the single knowledge access layer.

``open_repository()`` returns a :class:`QueryEngine`, the ONLY read interface to
the Canonical Corpus Repository. Consumers (website, dashboard, AI offices,
runtime, API) call its methods and never touch repository files or know the
repository layout. The engine is built on the Repository Loader (no duplicated
file logic), adds typing, caching and deterministic search, and validates the
repository before the first query.
"""

from __future__ import annotations

from pathlib import Path

from repository.loader import RepositoryLoader
from repository.schema import DEFAULT_CORPUS_ROOT
from repository.validator import validate_corpus, validate_repository

from . import books as _books
from . import chapters as _chapters
from . import citations as _citations
from . import knowledge as _knowledge
from . import paragraphs as _paragraphs
from . import relationships as _relationships
from . import search as _search
from . import sections as _sections
from .cache import Cache
from .exceptions import BookNotFound, CorpusNotFound, QueryError
from .types import (
    Book,
    Chapter,
    Citation,
    Corpus,
    KnowledgeObject,
    Manifest,
    Paragraph,
    Relationship,
    Section,
)


def open_repository(root: str | Path | None = None, *, validate: bool = True) -> "QueryEngine":
    """Open the repository for querying.

    Validation runs before the first query is possible (``validate=True``); a
    broken repository raises :class:`RepositoryValidationError` rather than
    failing silently later.
    """
    engine = QueryEngine(root if root is not None else DEFAULT_CORPUS_ROOT)
    if validate:
        engine.validate()
    return engine


class QueryEngine:
    def __init__(self, root: str | Path = DEFAULT_CORPUS_ROOT) -> None:
        self.root = Path(root)
        self._loader = RepositoryLoader(self.root)
        self.cache = Cache(self._loader)

    # ── validation (no silent failure) ───────────────────────────────────
    def validate(self, corpus_id: str | None = None) -> None:
        from .exceptions import RepositoryValidationError
        report = validate_corpus(self.root, corpus_id) if corpus_id else validate_repository(self.root)
        if not report.ok:
            raise RepositoryValidationError(report.errors)

    # ── scope helpers (single scan implementation) ───────────────────────
    def ensure_corpus(self, corpus_id: str) -> None:
        if corpus_id not in self.cache.corpora():
            raise CorpusNotFound(corpus_id)

    def book_numbers(self, corpus_id: str) -> list[int]:
        self.ensure_corpus(corpus_id)
        return sorted(ref.number for ref in self.cache.corpus(corpus_id).books)

    def ensure_book(self, corpus_id: str, book_number: int) -> None:
        if book_number not in self.book_numbers(corpus_id):
            raise BookNotFound(corpus_id, book_number)

    def iter_books(self, corpus_id: str | None = None, book_number: int | None = None):
        """Deterministic iterator over (corpus_id, book_number) in scope."""
        corpora = [corpus_id] if corpus_id is not None else list(self.cache.corpora())
        for cid in corpora:
            self.ensure_corpus(cid)
            for bn in self.book_numbers(cid):
                if book_number is None or bn == book_number:
                    yield (cid, bn)

    def clear_cache(self) -> None:
        """Drop the transparent cache. The repository is unaffected."""
        self.cache.clear()

    # ── discovery ────────────────────────────────────────────────────────
    def list_corpora(self) -> list[Corpus]:
        return [self.cache.corpus(cid) for cid in self.cache.corpora()]

    def get_corpus(self, corpus_id: str) -> Corpus:
        self.ensure_corpus(corpus_id)
        return self.cache.corpus(corpus_id)

    def list_books(self, corpus_id: str) -> list[Book]:
        return _books.list_books(self, corpus_id)

    def get_manifest(self, corpus_id: str, book_number: int) -> Manifest:
        self.ensure_book(corpus_id, book_number)
        return self.cache.manifest(corpus_id, book_number)

    # ── object getters ───────────────────────────────────────────────────
    def get_book(self, corpus_id: str, book_number: int) -> Book:
        return _books.get_book(self, corpus_id, book_number)

    def get_chapter(self, corpus_id: str, book_number: int, chapter_id: str) -> Chapter:
        return _chapters.get_chapter(self, corpus_id, book_number, chapter_id)

    def get_section(self, corpus_id: str, book_number: int, section_id: str) -> Section:
        return _sections.get_section(self, corpus_id, book_number, section_id)

    def get_paragraph(self, corpus_id: str, book_number: int, paragraph_id: str) -> Paragraph:
        return _paragraphs.get_paragraph(self, corpus_id, book_number, paragraph_id)

    def get_citation(self, corpus_id: str, book_number: int, citation_id: str) -> Citation:
        return _citations.get_citation(self, corpus_id, book_number, citation_id)

    def get_knowledge_object(self, corpus_id: str, book_number: int, knowledge_id: str) -> KnowledgeObject:
        return _knowledge.get_knowledge_object(self, corpus_id, book_number, knowledge_id)

    def list_knowledge(self, corpus_id: str, book_number: int) -> list[KnowledgeObject]:
        return _knowledge.list_knowledge(self, corpus_id, book_number)

    def list_relationships(self, corpus_id: str, book_number: int) -> list[Relationship]:
        return _relationships.list_relationships(self, corpus_id, book_number)

    # ── navigation (dispatch by object kind) ─────────────────────────────
    def find_by_id(self, object_id: str, *, corpus_id=None, book_number=None):
        return _search.find_by_id(self, object_id, corpus_id=corpus_id, book_number=book_number)

    def find_parent(self, obj):
        kind = getattr(obj, "kind", None)
        if kind == "chapter":
            return _chapters.find_parent(self, obj)
        if kind == "section":
            return _sections.find_parent(self, obj)
        if kind == "paragraph":
            return _paragraphs.find_parent(self, obj)
        if kind == "citation":
            return _citations.find_parent(self, obj)
        if kind == "knowledge":
            return _knowledge.find_parent(self, obj)
        if kind == "evidence":
            return self.get_knowledge_object(obj.corpus_id, obj.book_number, obj.knowledge_id)
        if kind == "book":
            return self.get_corpus(obj.corpus_id)
        raise QueryError(f"no parent defined for kind: {kind!r}")

    def find_children(self, obj) -> list:
        kind = getattr(obj, "kind", None)
        if kind == "book":
            return _books.find_children(self, obj)
        if kind == "chapter":
            return _chapters.find_children(self, obj)
        if kind == "section":
            return _sections.find_children(self, obj)
        if kind == "paragraph":
            return _paragraphs.find_children(self, obj)
        if kind == "knowledge":
            return _knowledge.find_children(self, obj)
        return []

    def find_related(self, obj) -> list:
        if getattr(obj, "kind", None) == "knowledge":
            return _knowledge.find_related(self, obj)
        return []

    # ── finders ──────────────────────────────────────────────────────────
    def find_by_source(self, source_file: str, *, corpus_id=None, book_number=None) -> list[Citation]:
        return _citations.find_by_source(self, source_file, corpus_id=corpus_id, book_number=book_number)

    def find_by_page(self, page: int, *, corpus_id=None, book_number=None) -> list[Paragraph]:
        return _paragraphs.find_by_page(self, page, corpus_id=corpus_id, book_number=book_number)

    def find_by_marker(self, marker_number: int, *, corpus_id=None, book_number=None) -> list[Section]:
        return _sections.find_by_marker(self, marker_number, corpus_id=corpus_id, book_number=book_number)

    # ── search ───────────────────────────────────────────────────────────
    def search_text(self, query, *, kinds=None, corpus_id=None, book_number=None):
        return _search.search_text(self, query, kinds=kinds, corpus_id=corpus_id, book_number=book_number)

    def search_contains(self, query, *, kinds=None, corpus_id=None, book_number=None):
        return _search.search_contains(self, query, kinds=kinds, corpus_id=corpus_id, book_number=book_number)

    def search_exact(self, query, *, kinds=None, corpus_id=None, book_number=None):
        return _search.search_exact(self, query, kinds=kinds, corpus_id=corpus_id, book_number=book_number)

    def search_prefix(self, query, *, kinds=None, corpus_id=None, book_number=None):
        return _search.search_prefix(self, query, kinds=kinds, corpus_id=corpus_id, book_number=book_number)

    def search_regex(self, pattern, *, flags=0, kinds=None, corpus_id=None, book_number=None):
        return _search.search_regex(self, pattern, flags=flags, kinds=kinds, corpus_id=corpus_id, book_number=book_number)

    # ── citation resolution ──────────────────────────────────────────────
    def resolve_citation(self, citation, *, corpus_id=None, book_number=None) -> str:
        """Resolve a Citation (or citation id) to its exact source text."""
        if isinstance(citation, str):
            if corpus_id is None or book_number is None:
                raise QueryError("resolve_citation by id requires corpus_id and book_number")
            citation = self.get_citation(corpus_id, book_number, citation)
        return _citations.resolve(self, citation)
