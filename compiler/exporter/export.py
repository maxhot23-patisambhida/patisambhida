"""Exporter stage: serialise the compiled document to canonical JSON.

Serialisation is deterministic so that compiling the same PDF twice yields a
byte-identical file:
  * ``sort_keys=True``           — key order independent of dict construction
  * ``ensure_ascii=False``       — Thai/Pali stays as UTF-8, not \\u escapes
  * fixed indent + separators    — stable whitespace
  * no timestamps                — provenance is the source sha256, not wall-clock
"""

from __future__ import annotations

import json
from pathlib import Path


def to_json_bytes(document: dict) -> bytes:
    """Render the document to canonical UTF-8 JSON bytes."""
    text = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        separators=(",", ": "),
    )
    return (text + "\n").encode("utf-8")


def export_json(document: dict, out_dir: str | Path) -> Path:
    """Write ``{book-id}.json`` into ``out_dir`` and return the path."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{document['book']['id']}.json"
    path.write_bytes(to_json_bytes(document))
    return path
