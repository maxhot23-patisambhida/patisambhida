"""Canonical Knowledge Query Engine — Production Sprint 003.

The single, read-only knowledge access layer of the Knowledge Operating System.
Every consumer reads the Canonical Corpus Repository through this engine and
never touches repository files or knows the repository layout.

    from query import open_repository

    repo = open_repository()                 # validates before first query
    book = repo.get_book("patisambhidamagga", 1)
    for hit in repo.search_contains("สุตมยญาณ"):
        print(hit.kind, hit.object_id, hit.snippet)

Principles: Deterministic · Immutable · Typed · Read-only · Technology-independent.
"""

from .repository import QueryEngine, open_repository
from .exceptions import (
    BookNotFound,
    CorpusNotFound,
    ObjectNotFound,
    QueryError,
    RepositoryValidationError,
)
from .types import (
    Book,
    BookRef,
    Chapter,
    Citation,
    Corpus,
    Counts,
    Evidence,
    KnowledgeCitationRef,
    KnowledgeName,
    KnowledgeObject,
    Manifest,
    Paragraph,
    Relationship,
    SearchHit,
    Section,
)

__all__ = [
    "open_repository",
    "QueryEngine",
    # exceptions
    "QueryError",
    "RepositoryValidationError",
    "CorpusNotFound",
    "BookNotFound",
    "ObjectNotFound",
    # types
    "Book",
    "BookRef",
    "Chapter",
    "Section",
    "Paragraph",
    "Citation",
    "KnowledgeObject",
    "KnowledgeName",
    "KnowledgeCitationRef",
    "Evidence",
    "Relationship",
    "Corpus",
    "Counts",
    "Manifest",
    "SearchHit",
]
