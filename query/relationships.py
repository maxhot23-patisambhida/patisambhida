"""Relationship queries.

The compiler performs no inference, so relationship collections are currently
empty by design. These queries are written against the schema so consumers stay
stable when relationships are populated later by governed work.
"""

from __future__ import annotations

from .exceptions import ObjectNotFound
from .types import KnowledgeObject, Relationship


def list_relationships(engine, corpus_id: str, book_number: int) -> list[Relationship]:
    engine.ensure_book(corpus_id, book_number)
    return list(engine.cache.collection(corpus_id, book_number, "relationships"))


def get_relationship(engine, corpus_id: str, book_number: int, relationship_id: str) -> Relationship:
    engine.ensure_book(corpus_id, book_number)
    index = engine.cache.index(corpus_id, book_number, "relationships")
    try:
        return index[relationship_id]
    except KeyError:
        raise ObjectNotFound("relationship", relationship_id) from None


def resolve_endpoints(engine, relationship: Relationship) -> tuple:
    """Resolve a relationship's (from, to) Knowledge Objects, if present."""
    index = engine.cache.index(relationship.corpus_id, relationship.book_number, "knowledge")
    return (index.get(relationship.from_id), index.get(relationship.to_id))
