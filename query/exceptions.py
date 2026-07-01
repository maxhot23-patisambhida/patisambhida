"""Query Engine exceptions — no silent failure."""

from __future__ import annotations


class QueryError(Exception):
    """Base class for all Query Engine errors."""


class RepositoryValidationError(QueryError):
    """The repository failed validation; querying is refused."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        preview = "; ".join(errors[:5])
        more = "" if len(errors) <= 5 else f" (+{len(errors) - 5} more)"
        super().__init__(f"repository failed validation: {preview}{more}")


class NotFoundError(QueryError):
    """Base for lookups that resolve to nothing."""


class CorpusNotFound(NotFoundError):
    def __init__(self, corpus_id: str) -> None:
        super().__init__(f"corpus not found: {corpus_id!r}")


class BookNotFound(NotFoundError):
    def __init__(self, corpus_id: str, book_number: int) -> None:
        super().__init__(f"book {book_number} not found in corpus {corpus_id!r}")


class ObjectNotFound(NotFoundError):
    def __init__(self, kind: str, object_id: str) -> None:
        super().__init__(f"{kind} not found: {object_id!r}")
