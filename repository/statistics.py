"""Statistics generator.

Produces ``statistics.json`` from a compiled document. Structural counts and
coverage are deterministic; compilation duration, output size and timestamp are
provenance (excluded from the canonical output hash).
"""

from __future__ import annotations


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    # Round to keep the value stable across platforms.
    return round(numerator / denominator, 6)


def build_statistics(
    compiled: dict,
    *,
    output_size_bytes: int,
    compile_duration_seconds: float | None,
    compile_timestamp: str,
) -> dict:
    book = compiled["book"]
    stats = compiled["stats"]
    toolchain = compiled.get("toolchain", {})

    paragraphs = compiled["paragraphs"]
    with_citation = sum(1 for p in paragraphs if p.get("citationId"))
    heading_paras = sum(1 for p in paragraphs if p.get("isHeading"))

    return {
        "books": 1,
        "pages": book["pageCount"],
        "characters": book["charCount"],
        "chapters": stats["chapters"],
        "sections": stats["sections"],
        "paragraphs": stats["paragraphs"],
        "knowledgeObjects": stats["knowledgeObjects"],
        "citations": stats["citations"],
        "relationships": len(compiled.get("relationships", [])),
        "coverage": {
            "citation": _ratio(with_citation, len(paragraphs)),
            "headingKnowledge": _ratio(heading_paras, len(paragraphs)),
        },
        "compilerVersion": toolchain.get("compiler"),
        "normalizationVersion": toolchain.get("normalizer"),
        # provenance
        "compilationDurationSeconds": compile_duration_seconds,
        "outputSizeBytes": output_size_bytes,
        "compileTimestamp": compile_timestamp,
    }
