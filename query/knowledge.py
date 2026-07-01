"""Knowledge Object queries."""

from __future__ import annotations

from .exceptions import ObjectNotFound
from .types import Evidence, KnowledgeObject, Paragraph


def get_knowledge_object(engine, corpus_id: str, book_number: int, knowledge_id: str) -> KnowledgeObject:
    engine.ensure_book(corpus_id, book_number)
    index = engine.cache.index(corpus_id, book_number, "knowledge")
    try:
        return index[knowledge_id]
    except KeyError:
        raise ObjectNotFound("knowledge", knowledge_id) from None


def find_parent(engine, ko: KnowledgeObject) -> Paragraph:
    """Knowledge Object -> the paragraph it was extracted from."""
    index = engine.cache.index(ko.corpus_id, ko.book_number, "paragraphs")
    pid = ko.source_paragraph_id
    if pid is None or pid not in index:
        raise ObjectNotFound("paragraph", str(pid))
    return index[pid]


def find_children(engine, ko: KnowledgeObject) -> list[Evidence]:
    """Knowledge Object -> its evidence records."""
    return [
        ev
        for ev in engine.cache.collection(ko.corpus_id, ko.book_number, "evidence")
        if ev.knowledge_id == ko.id
    ]


def find_related(engine, ko: KnowledgeObject) -> list[KnowledgeObject]:
    """Knowledge Objects referenced by this object's relationships.

    Deterministic resolution of declared relationship endpoints — no inference.
    Empty until relationships are populated by later governed work.
    """
    index = engine.cache.index(ko.corpus_id, ko.book_number, "knowledge")
    related: list[KnowledgeObject] = []
    for rel in ko.relationship:
        target = rel.get("to") or rel.get("target") or rel.get("id")
        if target and target in index and target != ko.id:
            related.append(index[target])
    return related


def list_knowledge(engine, corpus_id: str, book_number: int) -> list[KnowledgeObject]:
    engine.ensure_book(corpus_id, book_number)
    return list(engine.cache.collection(corpus_id, book_number, "knowledge"))
