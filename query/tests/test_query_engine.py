"""Real integration tests for the Query Engine.

No mocks, no fabricated data: this compiles Book 1 and Book 3 from the actual
PDFs into a temporary Canonical Corpus Repository and runs every query against
it. Runnable directly (``python query/tests/test_query_engine.py``) — exits
non-zero on any failure — and also discoverable by pytest (the ``test_*``
function).
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from compiler.parser.extract import thai_digit_to_int  # noqa: E402
from compiler.pipeline import compile_book  # noqa: E402
from query import (  # noqa: E402
    Book,
    Chapter,
    Citation,
    Corpus,
    KnowledgeObject,
    Manifest,
    Paragraph,
    RepositoryValidationError,
    SearchHit,
    Section,
    open_repository,
)
from query.exceptions import BookNotFound, ObjectNotFound  # noqa: E402
from repository.manager import RepositoryManager  # noqa: E402

CORPUS = "patisambhidamagga"
PDF_DIR = _ROOT / "web" / "pdf"


class Checker:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def check(self, cond: bool, msg: str) -> None:
        if cond:
            self.passed += 1
        else:
            self.failed += 1
            print(f"  FAIL: {msg}")

    def eq(self, a, b, msg: str) -> None:
        self.check(a == b, f"{msg} (got {a!r}, expected {b!r})")


def _pdf_for(number: int) -> Path:
    for pdf in PDF_DIR.glob("*.pdf"):
        if (thai_digit_to_int(pdf.stem) or 0) == number:
            return pdf
    raise FileNotFoundError(f"no PDF for book {number}")


def build_repository(root: Path) -> None:
    manager = RepositoryManager(root)
    for number in (1, 3):
        doc = compile_book(_pdf_for(number), fallback_number=number)
        manager.create_book(CORPUS, doc, corpus_title="ปฏิสัมภิทามรรค")


def run_checks(root: Path) -> Checker:
    c = Checker()
    repo = open_repository(root)  # validates before first query

    # ── discovery ────────────────────────────────────────────────────────
    corpora = repo.list_corpora()
    c.check(all(isinstance(x, Corpus) for x in corpora), "list_corpora returns Corpus")
    c.eq([x.id for x in corpora], [CORPUS], "one corpus discovered")

    books = repo.list_books(CORPUS)
    c.check(all(isinstance(b, Book) for b in books), "list_books returns Book")
    c.eq(sorted(b.number for b in books), [1, 3], "books 1 and 3 present")

    book1 = repo.get_book(CORPUS, 1)
    c.check(isinstance(book1, Book) and book1.number == 1, "get_book(1) typed")
    c.check(book1.page_count > 0 and book1.char_count > 0, "book1 has pages/chars")

    # ── manifest consistency with collections ────────────────────────────
    man = repo.get_manifest(CORPUS, 3)
    c.check(isinstance(man, Manifest), "get_manifest returns Manifest")
    c.eq(man.counts.paragraphs, len(repo.cache.collection(CORPUS, 3, "paragraphs")),
         "manifest paragraph count matches collection")
    c.eq(man.counts.knowledge, len(repo.cache.collection(CORPUS, 3, "knowledge")),
         "manifest knowledge count matches collection")

    # ── hierarchy navigation ─────────────────────────────────────────────
    chapter = repo.get_chapter(CORPUS, 1, book1.chapter_ids[0])
    c.check(isinstance(chapter, Chapter), "get_chapter typed")
    c.eq(repo.find_parent(chapter).id, book1.id, "chapter.find_parent == book")
    chapters = repo.find_children(book1)
    c.check(chapters and all(isinstance(x, Chapter) for x in chapters), "book.find_children -> chapters")
    c.eq([x.id for x in chapters], list(book1.chapter_ids), "children order matches chapter_ids")

    sections = repo.find_children(chapter)
    c.check(sections and all(isinstance(x, Section) for x in sections), "chapter.find_children -> sections")
    section = sections[0]
    c.eq(repo.find_parent(section).id, chapter.id, "section.find_parent == chapter")

    paras = repo.find_children(section)
    c.check(paras and all(isinstance(x, Paragraph) for x in paras), "section.find_children -> paragraphs")
    para = paras[0]
    c.eq(repo.find_parent(para).id, section.id, "paragraph.find_parent == section")

    # ── citation + offset round-trip ─────────────────────────────────────
    cit = repo.get_citation(CORPUS, 1, para.citation_id)
    c.check(isinstance(cit, Citation), "get_citation typed")
    c.eq(repo.find_parent(cit).id, para.id, "citation.find_parent == paragraph")
    c.eq(repo.resolve_citation(cit), cit.quote, "resolve_citation round-trips to quote")
    c.eq(repo.resolve_citation(cit.id, corpus_id=CORPUS, book_number=1), cit.quote,
         "resolve_citation by id round-trips")

    # ── knowledge objects ────────────────────────────────────────────────
    kos = repo.list_knowledge(CORPUS, 1)
    c.check(kos and all(isinstance(k, KnowledgeObject) for k in kos), "list_knowledge typed")
    ko = kos[0]
    c.check(bool(ko.names.primary), "knowledge object has primary name")
    parent_para = repo.find_parent(ko)
    c.check(isinstance(parent_para, Paragraph) and parent_para.is_heading,
            "knowledge.find_parent -> heading paragraph")
    evidence = repo.find_children(ko)
    c.check(len(evidence) == 1 and evidence[0].knowledge_id == ko.id,
            "knowledge.find_children -> its evidence")
    c.eq(repo.find_related(ko), [], "knowledge.find_related empty (no inference)")

    # ── find_by_id across kinds ──────────────────────────────────────────
    c.eq(repo.find_by_id(book1.id).id, book1.id, "find_by_id resolves book")
    c.eq(repo.find_by_id(chapter.id).id, chapter.id, "find_by_id resolves chapter")
    c.eq(repo.find_by_id(para.id).id, para.id, "find_by_id resolves paragraph")
    c.eq(repo.find_by_id(cit.id).id, cit.id, "find_by_id resolves citation")
    c.eq(repo.find_by_id(ko.id).id, ko.id, "find_by_id resolves knowledge")
    try:
        repo.find_by_id("PKA-DOES-NOT-EXIST")
        c.check(False, "find_by_id raises on missing id")
    except ObjectNotFound:
        c.check(True, "find_by_id raises ObjectNotFound on missing id")

    # ── finders: page / marker / source ──────────────────────────────────
    page1 = repo.find_by_page(1, corpus_id=CORPUS, book_number=3)
    c.check(page1 and all(p.page == 1 for p in page1), "find_by_page returns page-1 paragraphs")

    marked = repo.find_by_marker(30, corpus_id=CORPUS, book_number=3)
    c.check(any(s.marker_number == 30 for s in marked), "find_by_marker(30) finds section")

    src = repo.get_book(CORPUS, 3).source_file
    by_src = repo.find_by_source(src, corpus_id=CORPUS, book_number=3)
    c.eq(len(by_src), len(repo.cache.collection(CORPUS, 3, "citations")),
         "find_by_source returns all citations of that source")
    c.check(all(x.source_file == src for x in by_src), "find_by_source results match source")

    # ── search (deterministic, typed) ────────────────────────────────────
    hits = repo.search_contains("ญาณ", book_number=1)
    c.check(hits and all(isinstance(h, SearchHit) for h in hits), "search_contains returns SearchHit")
    c.check(all(hasattr(h.obj, "kind") for h in hits), "search hits carry typed objects, not raw JSON")
    again = repo.search_contains("ญาณ", book_number=1)
    c.eq([h.object_id for h in hits], [h.object_id for h in again], "search is deterministic")

    exact = repo.search_exact(ko.names.primary, kinds=["knowledge"], book_number=1)
    c.check(any(h.object_id == ko.id for h in exact), "search_exact finds KO by exact name")

    prefix = repo.search_prefix(ko.names.primary[:4], kinds=["knowledge"], book_number=1)
    c.check(any(h.object_id == ko.id for h in prefix), "search_prefix finds KO by name prefix")

    regex = repo.search_regex("ญาณ", book_number=1, kinds=["paragraph"])
    c.check(all(isinstance(h, SearchHit) for h in regex), "search_regex returns SearchHit")
    regex2 = repo.search_regex("ญาณ", book_number=1, kinds=["paragraph"])
    c.eq([h.object_id for h in regex], [h.object_id for h in regex2], "search_regex deterministic")

    # ── cache is transparent + disposable ────────────────────────────────
    before = [h.object_id for h in repo.search_contains("ญาณ", book_number=1)]
    repo.clear_cache()
    after = [h.object_id for h in repo.search_contains("ญาณ", book_number=1)]
    c.eq(before, after, "results identical after cache clear")

    # ── error handling (no silent failure) ───────────────────────────────
    try:
        repo.get_book(CORPUS, 99)
        c.check(False, "get_book(99) should raise")
    except BookNotFound:
        c.check(True, "get_book missing -> BookNotFound")

    return c


def test_query_engine() -> None:
    """pytest entry point — builds a real repo in a temp dir and runs all checks."""
    tmp = Path(tempfile.mkdtemp(prefix="kos-query-test-"))
    try:
        build_repository(tmp)
        checker = run_checks(tmp)
        assert checker.failed == 0, f"{checker.failed} query checks failed"
        _assert_validation_rejects_broken(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _assert_validation_rejects_broken(good_root: Path) -> None:
    """The engine must refuse a broken repository before the first query."""
    import json
    broken = Path(tempfile.mkdtemp(prefix="kos-query-broken-"))
    try:
        shutil.copytree(good_root / CORPUS, broken / CORPUS)
        cit_path = broken / CORPUS / "BOOK-03" / "citations" / "citations.json"
        data = json.loads(cit_path.read_text(encoding="utf-8"))
        data[0]["quote"] = "__TAMPERED__"
        cit_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        try:
            open_repository(broken)
            raise AssertionError("open_repository accepted a broken repository")
        except RepositoryValidationError:
            pass  # expected
    finally:
        shutil.rmtree(broken, ignore_errors=True)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="kos-query-test-"))
    try:
        print("Building real repository (Book 1 + Book 3) ...")
        build_repository(tmp)
        checker = run_checks(tmp)
        print("Checking validation rejects a broken repository ...")
        try:
            _assert_validation_rejects_broken(tmp)
            checker.passed += 1
            print("  validation correctly rejects broken repository")
        except AssertionError as exc:
            checker.failed += 1
            print(f"  FAIL: {exc}")
        print(f"\n{checker.passed} passed, {checker.failed} failed")
        return 0 if checker.failed == 0 else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
