"""Repository Validator — everything required before publication.

Verifies, for each book:
  * Folder integrity  — required files and object folders present
  * Missing IDs       — every cross-reference resolves
  * Duplicate IDs     — every id unique within its kind
  * Broken citations  — every citation offset round-trips against page text
  * Broken relationships — relationship endpoints resolve to knowledge objects
  * Manifest consistency — counts / ids / source hash agree with content
  * Output hash       — recomputed canonical hash equals the manifest's

A clean report is the gate the Repository must pass before any consumer reads it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .loader import RepositoryLoader
from .schema import (
    BOOK_ROOT_FILES,
    DEFAULT_CORPUS_ROOT,
    OBJECT_KINDS,
    VERSIONS_DIR,
    book_dir,
    compute_output_hash,
    object_file,
)


@dataclass
class Report:
    context: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def extend(self, other: "Report") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


def _ids(objects: list[dict]) -> list[str]:
    return [o.get("id") for o in objects]


def _check_unique(report: Report, kind: str, objects: list[dict]) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for oid in _ids(objects):
        if oid in seen:
            dupes.add(oid)
        seen.add(oid)
    for d in sorted(dupes):
        report.error(f"duplicate id in {kind}: {d}")
    return seen


def _check_refs(report: Report, label: str, refs, valid: set[str]) -> None:
    for ref in refs:
        if ref is not None and ref not in valid:
            report.error(f"broken reference ({label}): {ref}")


def validate_book(book_dir_path: str | Path) -> Report:
    bdir = Path(book_dir_path)
    report = Report(context=str(bdir))

    # 1. Folder integrity
    for fname in BOOK_ROOT_FILES:
        if not (bdir / fname).is_file():
            report.error(f"missing file: {fname}")
    for kind in OBJECT_KINDS:
        if not object_file(bdir, kind).is_file():
            report.error(f"missing object file: {kind}/{kind}.json")
    if not (bdir / VERSIONS_DIR).is_dir() or not list((bdir / VERSIONS_DIR).glob("*.json")):
        report.error("missing version history")
    if report.errors:
        return report  # cannot continue without the files

    import json

    def load(name):
        return json.loads((bdir / name).read_text(encoding="utf-8"))

    def load_kind(kind):
        return json.loads(object_file(bdir, kind).read_text(encoding="utf-8"))

    manifest = load("manifest.json")
    book_doc = load("book.json")
    collections = {kind: load_kind(kind) for kind in OBJECT_KINDS}

    # 2. Duplicate ids + id sets per kind
    id_sets = {k: _check_unique(report, k, collections[k]) for k in OBJECT_KINDS}
    chapters = collections["chapters"]
    sections = collections["sections"]
    paragraphs = collections["paragraphs"]
    citations = collections["citations"]
    knowledge = collections["knowledge"]
    evidence = collections["evidence"]
    relationships = collections["relationships"]

    # 3. Missing IDs / referential integrity
    _check_refs(report, "section.chapterId", (s.get("chapterId") for s in sections), id_sets["chapters"])
    _check_refs(report, "paragraph.chapterId", (p.get("chapterId") for p in paragraphs), id_sets["chapters"])
    _check_refs(report, "paragraph.sectionId", (p.get("sectionId") for p in paragraphs), id_sets["sections"])
    _check_refs(report, "paragraph.citationId", (p.get("citationId") for p in paragraphs), id_sets["citations"])
    _check_refs(report, "citation.paragraphId", (c.get("paragraphId") for c in citations), id_sets["paragraphs"])
    _check_refs(report, "knowledge.sourceParagraphId",
                (k.get("metadata", {}).get("sourceParagraphId") for k in knowledge), id_sets["paragraphs"])
    _check_refs(report, "knowledge.citationId",
                (k.get("citation", {}).get("citationId") for k in knowledge), id_sets["citations"])
    _check_refs(report, "evidence.knowledgeId", (e.get("knowledgeId") for e in evidence), id_sets["knowledge"])
    _check_refs(report, "evidence.citationId", (e.get("citationId") for e in evidence), id_sets["citations"])

    # 4. Broken relationships (endpoints must resolve to knowledge objects)
    for rel in relationships:
        for endpoint_key in ("from", "to", "source", "target"):
            ep = rel.get(endpoint_key)
            if ep is not None and ep not in id_sets["knowledge"]:
                report.error(f"broken relationship endpoint ({endpoint_key}): {ep}")

    # 5. Broken citations (offset round-trip against canonical page text)
    pages = {p["number"]: p["text"] for p in book_doc.get("pageText", [])}
    broken = 0
    for c in citations:
        text = pages.get(c.get("page"))
        if text is None:
            report.error(f"citation references missing page {c.get('page')}: {c.get('id')}")
            continue
        start, end = c.get("offset", [0, 0])
        if c.get("quote") != text[start:end]:
            broken += 1
    if broken:
        report.error(f"broken citations (offset mismatch): {broken}")

    # 6. Manifest consistency
    expected_counts = {
        "chapters": len(chapters),
        "sections": len(sections),
        "paragraphs": len(paragraphs),
        "citations": len(citations),
        "knowledge": len(knowledge),
        "relationships": len(relationships),
        "evidence": len(evidence),
    }
    for kind, expected in expected_counts.items():
        actual = manifest.get("counts", {}).get(kind)
        if actual != expected:
            report.error(f"manifest count mismatch [{kind}]: manifest={actual} actual={expected}")
    if manifest.get("bookId") != book_doc.get("book", {}).get("id"):
        report.error("manifest.bookId does not match book.json")
    if manifest.get("sourceSha256") != book_doc.get("book", {}).get("sourceSha256"):
        report.error("manifest.sourceSha256 does not match book.json")

    # 7. Output hash
    recomputed = compute_output_hash(bdir)
    if recomputed != manifest.get("outputHash"):
        report.error(
            f"output hash mismatch: manifest={manifest.get('outputHash')[:12]}… "
            f"recomputed={recomputed[:12]}…"
        )

    return report


def validate_corpus(corpus_root: str | Path, corpus_id: str) -> Report:
    loader = RepositoryLoader(corpus_root)
    report = Report(context=f"corpus:{corpus_id}")
    try:
        books = loader.list_books(corpus_id)
    except FileNotFoundError:
        report.error(f"corpus not found: {corpus_id}")
        return report
    for summary in books:
        bdir = book_dir(corpus_root, corpus_id, summary["bookNumber"])
        report.extend(validate_book(bdir))
    return report


def validate_repository(corpus_root: str | Path = DEFAULT_CORPUS_ROOT) -> Report:
    loader = RepositoryLoader(corpus_root)
    report = Report(context=f"repository:{corpus_root}")
    corpora = loader.list_corpora()
    if not corpora:
        report.warn("no corpora found")
    for cid in corpora:
        report.extend(validate_corpus(corpus_root, cid))
    return report
