"""Typed objects returned by the Query Engine.

Every query returns one of these frozen dataclasses — never raw JSON. Each
object carries its ``corpus_id`` and ``book_number`` so it can be navigated
(parent / children / related) without the consumer knowing repository layout.

The ``from_dict`` builders are the single place that maps the repository's
on-disk field names to the typed API; if the repository format evolves, only
these change and consumers stay stable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

Offset = tuple[int, int]


def _offset(value) -> Offset:
    a, b = value
    return (int(a), int(b))


# ── structural objects ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class Book:
    corpus_id: str
    book_number: int
    id: str
    number: int
    slug: str
    title: str
    source_file: str
    source_sha256: str
    page_count: int
    char_count: int
    chapter_ids: tuple[str, ...]
    kind: str = "book"

    @classmethod
    def from_dict(cls, d: dict, corpus_id: str, book_number: int) -> "Book":
        return cls(
            corpus_id=corpus_id,
            book_number=book_number,
            id=d["id"],
            number=d["number"],
            slug=d["slug"],
            title=d["title"],
            source_file=d["sourceFile"],
            source_sha256=d["sourceSha256"],
            page_count=d["pageCount"],
            char_count=d["charCount"],
            chapter_ids=tuple(d.get("chapterIds", [])),
        )


@dataclass(frozen=True)
class Chapter:
    corpus_id: str
    book_number: int
    id: str
    book_id: str
    index: int
    title: str
    start_page: int
    end_page: int
    section_ids: tuple[str, ...]
    kind: str = "chapter"

    @classmethod
    def from_dict(cls, d: dict, corpus_id: str, book_number: int) -> "Chapter":
        return cls(
            corpus_id=corpus_id,
            book_number=book_number,
            id=d["id"],
            book_id=d["bookId"],
            index=d["index"],
            title=d["title"],
            start_page=d["startPage"],
            end_page=d["endPage"],
            section_ids=tuple(d.get("sectionIds", [])),
        )


@dataclass(frozen=True)
class Section:
    corpus_id: str
    book_number: int
    id: str
    book_id: str
    chapter_id: str
    index: int
    marker: Optional[str]
    marker_number: Optional[int]
    title: Optional[str]
    start_page: int
    end_page: int
    paragraph_ids: tuple[str, ...]
    kind: str = "section"

    @classmethod
    def from_dict(cls, d: dict, corpus_id: str, book_number: int) -> "Section":
        return cls(
            corpus_id=corpus_id,
            book_number=book_number,
            id=d["id"],
            book_id=d["bookId"],
            chapter_id=d["chapterId"],
            index=d["index"],
            marker=d.get("marker"),
            marker_number=d.get("markerNumber"),
            title=d.get("title"),
            start_page=d["startPage"],
            end_page=d["endPage"],
            paragraph_ids=tuple(d.get("paragraphIds", [])),
        )


@dataclass(frozen=True)
class Paragraph:
    corpus_id: str
    book_number: int
    id: str
    book_id: str
    chapter_id: str
    section_id: str
    index: int
    page: int
    offset: Offset
    char_count: int
    is_heading: bool
    text: str
    citation_id: Optional[str]
    kind: str = "paragraph"

    @classmethod
    def from_dict(cls, d: dict, corpus_id: str, book_number: int) -> "Paragraph":
        return cls(
            corpus_id=corpus_id,
            book_number=book_number,
            id=d["id"],
            book_id=d["bookId"],
            chapter_id=d["chapterId"],
            section_id=d["sectionId"],
            index=d["index"],
            page=d["page"],
            offset=_offset(d["offset"]),
            char_count=d["charCount"],
            is_heading=d["isHeading"],
            text=d["text"],
            citation_id=d.get("citationId"),
        )


@dataclass(frozen=True)
class Citation:
    corpus_id: str
    book_number: int
    id: str
    paragraph_id: str
    book_id: str
    source_file: str
    source_sha256: str
    page: int
    offset: Offset
    quote: str
    kind: str = "citation"

    @classmethod
    def from_dict(cls, d: dict, corpus_id: str, book_number: int) -> "Citation":
        return cls(
            corpus_id=corpus_id,
            book_number=book_number,
            id=d["id"],
            paragraph_id=d["paragraphId"],
            book_id=d["bookId"],
            source_file=d["sourceFile"],
            source_sha256=d["sourceSha256"],
            page=d["page"],
            offset=_offset(d["offset"]),
            quote=d["quote"],
        )


# ── knowledge objects ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class KnowledgeName:
    primary: str
    pali: Optional[str]
    english: Optional[str]
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class KnowledgeCitationRef:
    citation_id: str
    source_file: str
    page: int
    offset: Offset


@dataclass(frozen=True)
class KnowledgeObject:
    corpus_id: str
    book_number: int
    id: str
    code: str
    schema: str
    names: KnowledgeName
    definition: Optional[str]
    classification: Optional[str]
    citation: KnowledgeCitationRef
    evidence_level: Optional[str]
    evidence_basis: Optional[str]
    language_primary: str
    representations: tuple[str, ...]
    completeness: Optional[str]
    approval_status: Optional[str]
    lifecycle_state: Optional[str]
    source_paragraph_id: Optional[str]
    relationship: tuple[dict, ...]
    kind: str = "knowledge"

    @classmethod
    def from_dict(cls, d: dict, corpus_id: str, book_number: int) -> "KnowledgeObject":
        names = d.get("names", {})
        citation = d.get("citation", {})
        evidence = d.get("evidence", {})
        language = d.get("language", {})
        return cls(
            corpus_id=corpus_id,
            book_number=book_number,
            id=d["id"],
            code=d.get("identity", {}).get("code", d["id"]),
            schema=d.get("schema", ""),
            names=KnowledgeName(
                primary=names.get("primary", ""),
                pali=names.get("pali"),
                english=names.get("english"),
                aliases=tuple(names.get("aliases", [])),
            ),
            definition=d.get("definition", {}).get("text"),
            classification=d.get("classification", {}).get("type"),
            citation=KnowledgeCitationRef(
                citation_id=citation.get("citationId", ""),
                source_file=citation.get("sourceFile", ""),
                page=citation.get("page", 0),
                offset=_offset(citation.get("offset", [0, 0])),
            ),
            evidence_level=evidence.get("level"),
            evidence_basis=evidence.get("basis"),
            language_primary=language.get("primary", ""),
            representations=tuple(language.get("representations", [])),
            completeness=d.get("quality", {}).get("completeness"),
            approval_status=d.get("approval", {}).get("status"),
            lifecycle_state=d.get("lifecycle", {}).get("state"),
            source_paragraph_id=d.get("metadata", {}).get("sourceParagraphId"),
            relationship=tuple(d.get("relationship", [])),
        )


@dataclass(frozen=True)
class Evidence:
    corpus_id: str
    book_number: int
    id: str
    knowledge_id: str
    level: Optional[str]
    basis: Optional[str]
    citation_id: Optional[str]
    kind: str = "evidence"

    @classmethod
    def from_dict(cls, d: dict, corpus_id: str, book_number: int) -> "Evidence":
        return cls(
            corpus_id=corpus_id,
            book_number=book_number,
            id=d["id"],
            knowledge_id=d["knowledgeId"],
            level=d.get("level"),
            basis=d.get("basis"),
            citation_id=d.get("citationId"),
        )


@dataclass(frozen=True)
class Relationship:
    corpus_id: str
    book_number: int
    id: str
    rel_type: Optional[str]
    from_id: Optional[str]
    to_id: Optional[str]
    kind: str = "relationship"

    @classmethod
    def from_dict(cls, d: dict, corpus_id: str, book_number: int) -> "Relationship":
        return cls(
            corpus_id=corpus_id,
            book_number=book_number,
            id=d.get("id", ""),
            rel_type=d.get("type") or d.get("relType"),
            from_id=d.get("from") or d.get("source"),
            to_id=d.get("to") or d.get("target"),
        )


# ── corpus / manifest ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BookRef:
    book_id: str
    number: int
    title: str
    folder: str
    output_hash: Optional[str]
    knowledge_count: Optional[int]
    paragraph_count: Optional[int]
    kind: str = "book_ref"

    @classmethod
    def from_dict(cls, d: dict) -> "BookRef":
        return cls(
            book_id=d["bookId"],
            number=d["bookNumber"],
            title=d.get("title", ""),
            folder=d.get("folder", ""),
            output_hash=d.get("outputHash"),
            knowledge_count=d.get("knowledgeCount"),
            paragraph_count=d.get("paragraphCount"),
        )


@dataclass(frozen=True)
class Corpus:
    id: str
    title: str
    repository_version: str
    books: tuple[BookRef, ...]
    kind: str = "corpus"

    @classmethod
    def from_dict(cls, d: dict) -> "Corpus":
        return cls(
            id=d["corpusId"],
            title=d.get("title", ""),
            repository_version=d.get("repositoryVersion", ""),
            books=tuple(BookRef.from_dict(b) for b in d.get("books", [])),
        )


@dataclass(frozen=True)
class Counts:
    chapters: int
    sections: int
    paragraphs: int
    citations: int
    knowledge: int
    relationships: int
    evidence: int

    @classmethod
    def from_dict(cls, d: dict) -> "Counts":
        return cls(
            chapters=d.get("chapters", 0),
            sections=d.get("sections", 0),
            paragraphs=d.get("paragraphs", 0),
            citations=d.get("citations", 0),
            knowledge=d.get("knowledge", 0),
            relationships=d.get("relationships", 0),
            evidence=d.get("evidence", 0),
        )


@dataclass(frozen=True)
class Manifest:
    corpus_id: str
    book_id: str
    book_number: int
    title: str
    compiler_version: Optional[str]
    normalization_version: Optional[str]
    repository_version: Optional[str]
    source_file: str
    source_sha256: str
    compile_timestamp: Optional[str]
    output_hash: str
    counts: Counts
    kind: str = "manifest"

    @classmethod
    def from_dict(cls, d: dict) -> "Manifest":
        return cls(
            corpus_id=d["corpusId"],
            book_id=d["bookId"],
            book_number=d["bookNumber"],
            title=d.get("title", ""),
            compiler_version=d.get("compilerVersion"),
            normalization_version=d.get("normalizationVersion"),
            repository_version=d.get("repositoryVersion"),
            source_file=d.get("sourceFile", ""),
            source_sha256=d.get("sourceSha256", ""),
            compile_timestamp=d.get("compileTimestamp"),
            output_hash=d.get("outputHash", ""),
            counts=Counts.from_dict(d.get("counts", {})),
        )


# ── search ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SearchHit:
    corpus_id: str
    book_number: int
    kind: str
    object_id: str
    field: str
    snippet: str
    obj: object  # the typed domain object (Paragraph, KnowledgeObject, ...)


# kind -> builder, for the cache to construct collections generically.
BUILDERS = {
    "chapters": Chapter.from_dict,
    "sections": Section.from_dict,
    "paragraphs": Paragraph.from_dict,
    "citations": Citation.from_dict,
    "knowledge": KnowledgeObject.from_dict,
    "relationships": Relationship.from_dict,
    "evidence": Evidence.from_dict,
}
