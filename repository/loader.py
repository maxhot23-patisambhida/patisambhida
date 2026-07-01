"""Repository Loader — the ONLY read path into the Canonical Corpus Repository.

The website, dashboard, runtime and AI offices access the repository through
this layer and never read the JSON files directly. This keeps the on-disk format
an implementation detail: it can shard, compress or migrate without breaking any
consumer.

All methods are read-only. The loader never writes.
"""

from __future__ import annotations

import json
from pathlib import Path

from .schema import (
    CORPUS_FILE,
    DEFAULT_CORPUS_ROOT,
    OBJECT_KINDS,
    book_dir,
    corpus_dir,
    object_file,
)


class RepositoryNotFound(FileNotFoundError):
    """Raised when a requested corpus / book / object does not exist."""


def _read_json(path: Path):
    if not path.is_file():
        raise RepositoryNotFound(str(path))
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


class RepositoryLoader:
    def __init__(self, corpus_root: str | Path = DEFAULT_CORPUS_ROOT) -> None:
        self.root = Path(corpus_root)

    # ── discovery ────────────────────────────────────────────────────────
    def list_corpora(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(
            p.name for p in self.root.iterdir()
            if p.is_dir() and (p / CORPUS_FILE).is_file()
        )

    def corpus(self, corpus_id: str) -> dict:
        return _read_json(corpus_dir(self.root, corpus_id) / CORPUS_FILE)

    def list_books(self, corpus_id: str) -> list[dict]:
        """Book summaries from the corpus file — no object scanning."""
        return list(self.corpus(corpus_id).get("books", []))

    # ── book-level canonical files ───────────────────────────────────────
    def manifest(self, corpus_id: str, book_number: int) -> dict:
        return _read_json(book_dir(self.root, corpus_id, book_number) / "manifest.json")

    def metadata(self, corpus_id: str, book_number: int) -> dict:
        return _read_json(book_dir(self.root, corpus_id, book_number) / "metadata.json")

    def statistics(self, corpus_id: str, book_number: int) -> dict:
        return _read_json(book_dir(self.root, corpus_id, book_number) / "statistics.json")

    def book(self, corpus_id: str, book_number: int) -> dict:
        return _read_json(book_dir(self.root, corpus_id, book_number) / "book.json")

    def page_text(self, corpus_id: str, book_number: int) -> dict[int, str]:
        """Map of page number -> canonical page text."""
        pages = self.book(corpus_id, book_number).get("pageText", [])
        return {p["number"]: p["text"] for p in pages}

    # ── object collections ───────────────────────────────────────────────
    def objects(self, corpus_id: str, book_number: int, kind: str) -> list[dict]:
        if kind not in OBJECT_KINDS:
            raise ValueError(f"unknown object kind: {kind!r}")
        bdir = book_dir(self.root, corpus_id, book_number)
        return _read_json(object_file(bdir, kind))

    def chapters(self, corpus_id, book_number): return self.objects(corpus_id, book_number, "chapters")
    def sections(self, corpus_id, book_number): return self.objects(corpus_id, book_number, "sections")
    def paragraphs(self, corpus_id, book_number): return self.objects(corpus_id, book_number, "paragraphs")
    def citations(self, corpus_id, book_number): return self.objects(corpus_id, book_number, "citations")
    def knowledge(self, corpus_id, book_number): return self.objects(corpus_id, book_number, "knowledge")
    def relationships(self, corpus_id, book_number): return self.objects(corpus_id, book_number, "relationships")
    def evidence(self, corpus_id, book_number): return self.objects(corpus_id, book_number, "evidence")

    # ── object-by-id access ──────────────────────────────────────────────
    def get_object(self, corpus_id: str, book_number: int, kind: str, object_id: str) -> dict:
        for obj in self.objects(corpus_id, book_number, kind):
            if obj.get("id") == object_id:
                return obj
        raise RepositoryNotFound(f"{kind} {object_id!r} not in book {book_number}")

    def get_paragraph(self, corpus_id, book_number, object_id):
        return self.get_object(corpus_id, book_number, "paragraphs", object_id)

    def get_citation(self, corpus_id, book_number, object_id):
        return self.get_object(corpus_id, book_number, "citations", object_id)

    def get_knowledge(self, corpus_id, book_number, object_id):
        return self.get_object(corpus_id, book_number, "knowledge", object_id)

    # ── convenience ──────────────────────────────────────────────────────
    def resolve_citation(self, corpus_id: str, book_number: int, citation_id: str) -> str:
        """Return the exact source text a citation points to (offset round-trip)."""
        citation = self.get_citation(corpus_id, book_number, citation_id)
        pages = self.page_text(corpus_id, book_number)
        start, end = citation["offset"]
        return pages[citation["page"]][start:end]
