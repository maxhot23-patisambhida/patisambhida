"""KOS Compiler CLI.

Every successful compilation writes the Canonical Corpus Repository — the
permanent storage layer every consumer reads from. The standalone single-file
JSON is now an optional debug artifact (``--single-file``).

    python -m compiler <book-number | pdf-path> [options]

Examples:
    python -m compiler 1                  # compile Book 1 -> corpus/patisambhidamagga/BOOK-01/
    python -m compiler 1 --verify         # also prove the canonical output is reproducible
    python -m compiler 3 --single-file    # also dump compiler/out/PKA-B03.json
    python -m compiler 1 --no-repo        # compile only, write nothing to the repository
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .exporter import export_json, to_json_bytes
from .parser.extract import thai_digit_to_int
from .pipeline import compile_book

_ROOT = Path(__file__).resolve().parents[1]
_PDF_DIR = _ROOT / "web" / "pdf"
_DEFAULT_OUT = Path(__file__).resolve().parent / "out"

_DEFAULT_CORPUS_ID = "patisambhidamagga"
_DEFAULT_CORPUS_TITLE = "ปฏิสัมภิทามรรค"


def _resolve_pdf(target: str) -> tuple[Path, int]:
    """Resolve a CLI target (book number or path) to (pdf_path, fallback_number)."""
    path = Path(target)
    if path.is_file():
        return path, thai_digit_to_int(path.stem) or 1
    if target.isdigit():
        number = int(target)
        for pdf in _PDF_DIR.glob("*.pdf"):
            if (thai_digit_to_int(pdf.stem) or 0) == number:
                return pdf, number
        raise SystemExit(f"No PDF for book number {number} in {_PDF_DIR}")
    raise SystemExit(f"Target is neither an existing file nor a book number: {target!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="compiler", description="KOS Knowledge Compiler (MVP)")
    parser.add_argument("target", help="book number (1-10) or path to a PDF")
    parser.add_argument("--corpus", default=_DEFAULT_CORPUS_ID, help="corpus id")
    parser.add_argument("--corpus-title", default=_DEFAULT_CORPUS_TITLE, help="corpus title")
    parser.add_argument("--repo-root", default=None, help="repository root (default: ./corpus)")
    parser.add_argument("--no-repo", action="store_true", help="do not write the repository")
    parser.add_argument("--single-file", action="store_true",
                        help="also dump the combined JSON to --out")
    parser.add_argument("--out", default=str(_DEFAULT_OUT), help="single-file output directory")
    parser.add_argument("--verify", action="store_true",
                        help="compile twice and confirm byte-identical canonical output")
    args = parser.parse_args(argv)

    pdf_path, fallback = _resolve_pdf(args.target)

    start = time.perf_counter()
    document = compile_book(pdf_path, fallback_number=fallback)
    duration = round(time.perf_counter() - start, 6)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if args.verify:
        again = compile_book(pdf_path, fallback_number=fallback)
        if to_json_bytes(document) != to_json_bytes(again):
            print("REPRODUCIBILITY FAILED: second compile differs", file=sys.stderr)
            return 1
        print("reproducibility OK (canonical output byte-identical across two compiles)")

    print(f"Compiled {pdf_path.name}")
    print(f"  book={document['book']['id']} sha256={document['source']['sha256'][:12]}…")
    print("  " + "  ".join(f"{k}={v}" for k, v in document["stats"].items()))

    if args.single_file:
        out_path = export_json(document, args.out)
        print(f"  single-file -> {out_path}")

    if not args.no_repo:
        from repository.manager import RepositoryManager
        from repository.validator import validate_book

        kwargs = {} if args.repo_root is None else {"corpus_root": args.repo_root}
        manager = RepositoryManager(**kwargs)
        bdir = manager.create_book(
            args.corpus,
            document,
            corpus_title=args.corpus_title,
            compile_timestamp=timestamp,
            compile_duration_seconds=duration,
        )
        report = validate_book(bdir)
        print(f"  repository -> {bdir}")
        if report.ok:
            print(f"  validation OK (0 errors, {len(report.warnings)} warnings)")
        else:
            print(f"  VALIDATION FAILED ({len(report.errors)} errors):", file=sys.stderr)
            for err in report.errors[:10]:
                print(f"    - {err}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
