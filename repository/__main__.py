"""Repository CLI — read-only operations (validate / discover / show).

    python -m repository discover
    python -m repository validate [CORPUS_ID]
    python -m repository show CORPUS_ID BOOK_NUMBER

Writing the repository is done by the compiler (see ``python -m compiler``);
this CLI never mutates the repository.
"""

from __future__ import annotations

import argparse
import sys

from .loader import RepositoryLoader
from .schema import DEFAULT_CORPUS_ROOT
from .validator import validate_corpus, validate_repository


def _cmd_discover(args) -> int:
    loader = RepositoryLoader(args.root)
    corpora = loader.list_corpora()
    if not corpora:
        print("(no corpora found)")
        return 0
    for cid in corpora:
        books = loader.list_books(cid)
        print(f"{cid}  ({len(books)} books)")
        for b in books:
            print(f"  {b['folder']}  {b['bookId']}  knowledge={b.get('knowledgeCount')}  "
                  f"paragraphs={b.get('paragraphCount')}")
    return 0


def _print_report(report) -> int:
    status = "OK" if report.ok else "FAILED"
    print(f"[{status}] {report.context}")
    for w in report.warnings:
        print(f"  warn:  {w}")
    for e in report.errors:
        print(f"  error: {e}")
    if report.ok:
        print(f"  {len(report.warnings)} warning(s), 0 error(s)")
    else:
        print(f"  {len(report.warnings)} warning(s), {len(report.errors)} error(s)")
    return 0 if report.ok else 1


def _cmd_validate(args) -> int:
    if args.corpus:
        report = validate_corpus(args.root, args.corpus)
    else:
        report = validate_repository(args.root)
    return _print_report(report)


def _cmd_show(args) -> int:
    loader = RepositoryLoader(args.root)
    manifest = loader.manifest(args.corpus, args.book)
    import json
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repository", description="Canonical Corpus Repository (read-only)")
    parser.add_argument("--root", default=str(DEFAULT_CORPUS_ROOT), help="repository root")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("discover", help="list corpora and books").set_defaults(func=_cmd_discover)

    v = sub.add_parser("validate", help="validate a corpus (or the whole repository)")
    v.add_argument("corpus", nargs="?", default=None)
    v.set_defaults(func=_cmd_validate)

    s = sub.add_parser("show", help="print a book manifest")
    s.add_argument("corpus")
    s.add_argument("book", type=int)
    s.set_defaults(func=_cmd_show)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
