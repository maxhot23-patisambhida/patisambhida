"""Repository Manager — the write layer.

Responsibilities (per the Sprint 002 spec):
  * create corpus
  * register source (Corpus Registration step)
  * create book (write the full canonical layout for one compiled book)
  * load book (delegates to the loader)
  * validate repository (delegates to the validator)
  * discover corpus

Writes are deterministic for canonical content; only provenance (timestamps,
durations) varies between runs. Version history under ``versions/`` is
append-only: a new version record is added only when the canonical output hash
changes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .loader import RepositoryLoader
from .manifest import build_manifest
from .schema import (
    CORPUS_FILE,
    DEFAULT_CORPUS_ROOT,
    OBJECT_KINDS,
    REPOSITORY_VERSION,
    VERSIONS_DIR,
    book_dir,
    book_folder_name,
    canonical_dumps,
    compute_output_hash,
    corpus_dir,
    object_file,
)
from .statistics import build_statistics


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _evidence_objects(compiled: dict) -> list[dict]:
    """Project the evidence already embedded in each Knowledge Object.

    This is reorganisation of existing canonical data, not enrichment — no new
    knowledge is created.
    """
    out: list[dict] = []
    for ko in compiled["knowledgeObjects"]:
        ev = ko.get("evidence", {})
        out.append({
            "id": f"{ko['id']}-EV",
            "type": "Evidence",
            "knowledgeId": ko["id"],
            "level": ev.get("level"),
            "basis": ev.get("basis"),
            "citationId": ko.get("citation", {}).get("citationId"),
        })
    return out


class RepositoryManager:
    def __init__(self, corpus_root: str | Path = DEFAULT_CORPUS_ROOT) -> None:
        self.root = Path(corpus_root)

    # ── corpus ───────────────────────────────────────────────────────────
    def create_corpus(self, corpus_id: str, title: str) -> Path:
        """Create a corpus directory + corpus.json (idempotent)."""
        cdir = corpus_dir(self.root, corpus_id)
        cdir.mkdir(parents=True, exist_ok=True)
        cfile = cdir / CORPUS_FILE
        if not cfile.is_file():
            corpus = {
                "repositoryVersion": REPOSITORY_VERSION,
                "corpusId": corpus_id,
                "title": title,
                "books": [],
                "sources": [],
            }
            cfile.write_bytes(canonical_dumps(corpus))
        return cdir

    def _read_corpus(self, corpus_id: str) -> dict:
        return RepositoryLoader(self.root).corpus(corpus_id)

    def _write_corpus(self, corpus_id: str, corpus: dict) -> None:
        (corpus_dir(self.root, corpus_id) / CORPUS_FILE).write_bytes(canonical_dumps(corpus))

    def register_source(
        self, corpus_id: str, *, source_file: str, source_sha256: str, book_number: int
    ) -> None:
        """Record a source in the corpus registry (Corpus Registration).

        Append-only and idempotent: re-registering the same sha256 updates in
        place rather than duplicating.
        """
        corpus = self._read_corpus(corpus_id)
        sources = corpus.setdefault("sources", [])
        record = {
            "bookNumber": book_number,
            "file": source_file,
            "sha256": source_sha256,
        }
        for i, existing in enumerate(sources):
            if existing.get("sha256") == source_sha256:
                sources[i] = record
                break
        else:
            sources.append(record)
        sources.sort(key=lambda s: s.get("bookNumber", 0))
        self._write_corpus(corpus_id, corpus)

    # ── book ─────────────────────────────────────────────────────────────
    def create_book(
        self,
        corpus_id: str,
        compiled: dict,
        *,
        corpus_title: str | None = None,
        compile_timestamp: str | None = None,
        compile_duration_seconds: float | None = None,
    ) -> Path:
        """Write the full canonical layout for one compiled book. Returns its dir."""
        book = compiled["book"]
        number = book["number"]
        compile_timestamp = compile_timestamp or _utc_now_iso()

        self.create_corpus(corpus_id, corpus_title or corpus_id)
        bdir = book_dir(self.root, corpus_id, number)

        # 1. Object collections (deterministic canonical content).
        collections = {
            "chapters": compiled["chapters"],
            "sections": compiled["sections"],
            "paragraphs": compiled["paragraphs"],
            "citations": compiled["citations"],
            "knowledge": compiled["knowledgeObjects"],
            "relationships": compiled.get("relationships", []),
            "evidence": _evidence_objects(compiled),
        }
        for kind in OBJECT_KINDS:
            target = object_file(bdir, kind)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(canonical_dumps(collections[kind]))

        # 2. book.json (book object + canonical page text the offsets index).
        book_doc = {
            "schemaVersion": compiled.get("schemaVersion"),
            "toolchain": compiled.get("toolchain", {}),
            "book": book,
            "pageText": compiled.get("pageText", []),
        }
        (bdir / "book.json").write_bytes(canonical_dumps(book_doc))

        # 3. metadata.json (descriptive, deterministic).
        metadata = {
            "corpusId": corpus_id,
            "bookId": book["id"],
            "bookNumber": number,
            "slug": book["slug"],
            "title": book["title"],
            "sourceFile": book["sourceFile"],
            "sourceSha256": book["sourceSha256"],
            "language": {"primary": "th", "representations": ["th", "pi"]},
        }
        (bdir / "metadata.json").write_bytes(canonical_dumps(metadata))

        # 4. Canonical output hash (over the files written above only).
        output_hash = compute_output_hash(bdir)

        # 5. statistics.json + manifest.json (carry provenance; not hashed).
        statistics = build_statistics(
            compiled,
            output_size_bytes=self._book_size_bytes(bdir),
            compile_duration_seconds=compile_duration_seconds,
            compile_timestamp=compile_timestamp,
        )
        (bdir / "statistics.json").write_bytes(canonical_dumps(statistics))

        manifest = build_manifest(
            compiled,
            corpus_id=corpus_id,
            output_hash=output_hash,
            statistics=statistics,
            compile_timestamp=compile_timestamp,
        )
        (bdir / "manifest.json").write_bytes(canonical_dumps(manifest))

        # 6. Append version history if the canonical content changed.
        self._append_version(bdir, manifest, output_hash, compile_timestamp)

        # 7. Register source + record book in the corpus.
        self.register_source(
            corpus_id,
            source_file=book["sourceFile"],
            source_sha256=book["sourceSha256"],
            book_number=number,
        )
        self._record_book(corpus_id, manifest)
        return bdir

    def _book_size_bytes(self, bdir: Path) -> int:
        return sum(p.stat().st_size for p in bdir.rglob("*.json") if p.is_file())

    def _append_version(self, bdir: Path, manifest: dict, output_hash: str, timestamp: str) -> None:
        vdir = bdir / VERSIONS_DIR
        vdir.mkdir(parents=True, exist_ok=True)
        existing = sorted(p for p in vdir.glob("[0-9]" * 4 + ".json"))
        if existing:
            import json
            last = json.loads(existing[-1].read_text(encoding="utf-8"))
            if last.get("outputHash") == output_hash:
                return  # unchanged — append-only, no duplicate
        version_number = len(existing) + 1
        record = {
            "version": version_number,
            "outputHash": output_hash,
            "sourceSha256": manifest["sourceSha256"],
            "compilerVersion": manifest["compilerVersion"],
            "normalizationVersion": manifest["normalizationVersion"],
            "repositoryVersion": REPOSITORY_VERSION,
            "compileTimestamp": timestamp,
            "counts": manifest["counts"],
        }
        (vdir / f"{version_number:04d}.json").write_bytes(canonical_dumps(record))

    def _record_book(self, corpus_id: str, manifest: dict) -> None:
        corpus = self._read_corpus(corpus_id)
        books = corpus.setdefault("books", [])
        summary = {
            "bookId": manifest["bookId"],
            "bookNumber": manifest["bookNumber"],
            "title": manifest["title"],
            "folder": book_folder_name(manifest["bookNumber"]),
            "outputHash": manifest["outputHash"],
            "knowledgeCount": manifest["knowledgeCount"],
            "paragraphCount": manifest["paragraphCount"],
        }
        for i, existing in enumerate(books):
            if existing.get("bookId") == manifest["bookId"]:
                books[i] = summary
                break
        else:
            books.append(summary)
        books.sort(key=lambda b: b.get("bookNumber", 0))
        self._write_corpus(corpus_id, corpus)

    # ── delegation ───────────────────────────────────────────────────────
    def load_book(self, corpus_id: str, book_number: int) -> dict:
        return RepositoryLoader(self.root).book(corpus_id, book_number)

    def discover_corpus(self) -> dict:
        loader = RepositoryLoader(self.root)
        return {
            cid: loader.list_books(cid) for cid in loader.list_corpora()
        }

    def validate(self, corpus_id: str | None = None):
        from .validator import validate_corpus, validate_repository
        if corpus_id is None:
            return validate_repository(self.root)
        return validate_corpus(self.root, corpus_id)
