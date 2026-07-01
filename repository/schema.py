"""Repository schema: the deterministic conventions every component shares.

Holds the repository version, the on-disk layout, path helpers, the canonical
JSON serialiser, and the canonical output-hash function. Pure data + pure
functions — no I/O state — so the layout stays technology independent and
identical for every corpus (Tripitaka, commentaries, lexicons, ...).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPOSITORY_VERSION = "kos-repository/1"

# Object folders under each BOOK-NN directory. Each holds one ordered
# collection file ``<kind>.json`` (and may be sharded later without redesign).
OBJECT_KINDS: tuple[str, ...] = (
    "chapters",
    "sections",
    "paragraphs",
    "citations",
    "knowledge",
    "relationships",
    "evidence",
)

# Files written at the BOOK-NN root.
BOOK_ROOT_FILES: tuple[str, ...] = (
    "book.json",
    "metadata.json",
    "manifest.json",
    "statistics.json",
)

VERSIONS_DIR = "versions"
CORPUS_FILE = "corpus.json"

# Default location of the repository (sibling of compiler/ at the project root).
DEFAULT_CORPUS_ROOT = Path(__file__).resolve().parents[1] / "corpus"

# Canonical content for the output hash — deterministic files only.
# Manifest, statistics and versions/ carry provenance and are EXCLUDED, so the
# hash is stable across compiles even though timestamps differ.
CANONICAL_HASH_FILES: tuple[str, ...] = (
    "book.json",
    "metadata.json",
) + tuple(f"{kind}/{kind}.json" for kind in OBJECT_KINDS)


def canonical_dumps(obj) -> bytes:
    """Serialise to canonical, deterministic UTF-8 JSON bytes."""
    text = json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        separators=(",", ": "),
    )
    return (text + "\n").encode("utf-8")


def book_folder_name(book_number: int) -> str:
    return f"BOOK-{book_number:02d}"


def corpus_dir(root: str | Path, corpus_id: str) -> Path:
    return Path(root) / corpus_id


def book_dir(root: str | Path, corpus_id: str, book_number: int) -> Path:
    return corpus_dir(root, corpus_id) / book_folder_name(book_number)


def object_file(book_dir_path: str | Path, kind: str) -> Path:
    return Path(book_dir_path) / kind / f"{kind}.json"


def compute_output_hash(book_dir_path: str | Path) -> str:
    """SHA-256 over the canonical content files in a fixed order.

    Recomputable from the repository alone (used by both the manager when
    writing and the validator when checking), so the two always agree.
    """
    base = Path(book_dir_path)
    digest = hashlib.sha256()
    for rel in CANONICAL_HASH_FILES:
        path = base / rel
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes() if path.is_file() else b"")
        digest.update(b"\0")
    return digest.hexdigest()
