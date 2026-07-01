"""Normalizer stage: turn raw extracted page text into *canonical page text*.

This is the text that every Citation offset points into, so it must be stable:
given the same raw input it always produces the same output.

Unlike ``scripts/build_content.py`` (whose ``normalize_text`` collapses every
newline into one, destroying paragraph structure), this normalizer **preserves
line breaks**. The compiler needs them: blank lines and line starts are the
deterministic signals used to split paragraphs downstream. Character-level Thai
repairs are shared with ``build_content`` so fidelity stays identical.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from build_content import repair_thai_pdf_spacing  # noqa: E402

# Bumped whenever the normalization rules below change in a way that alters
# canonical page text. Recorded in every repository manifest.
NORMALIZATION_VERSION = "kos-normalizer/1"

# Sara-am / consonant fragments that PDF extraction splits with a stray space.
# Mirrors the ``replacements`` table in build_content.normalize_text.
_PHRASE_REPAIRS: dict[str, str] = {
    "ท า": "ทำ", "จ า": "จำ", "ส า": "สำ", "ก า": "กำ", "ด า": "ดำ",
    "น า": "นำ", "ค า": "คำ", "อ า": "อำ", "บ า": "บำ", "ล า": "ลำ",
    "ช า": "ชำ", "ร า": "รำ", "ต า": "ตำ",
    "เป ็ น": "เป็น", "เห ็ น": "เห็น", "เช ่ น": "เช่น",
}

_SPACES = re.compile(r"[ \t]+")
_BLANKS = re.compile(r"\n{3,}")


def normalize_page(raw: str) -> str:
    """Normalize one page of raw text while preserving its line structure.

    Steps (all deterministic):
      1. Unify newlines and non-breaking spaces.
      2. Collapse runs of spaces/tabs (never newlines) to a single space.
      3. Apply shared Thai phrase + combining-mark spacing repairs.
      4. Trim each line; drop 3+ blank lines to a single paragraph break.
    """
    text = raw.replace(" ", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = _SPACES.sub(" ", text)

    for source, target in _PHRASE_REPAIRS.items():
        text = text.replace(source, target)

    text = repair_thai_pdf_spacing(text)

    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    text = _BLANKS.sub("\n\n", text)
    return text.strip("\n")
