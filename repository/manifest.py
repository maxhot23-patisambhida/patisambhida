"""Manifest generator.

Every compiled book produces a ``manifest.json`` — the canonical entry point.
No consumer should ever scan the repository to learn what a book contains; the
manifest answers every structural question (counts, versions, provenance,
output hash, embedded statistics) in one read.

The ``compileTimestamp`` is provenance and is deliberately NOT part of the
output hash (see schema.CANONICAL_HASH_FILES), so the canonical content stays
deterministic while provenance is still recorded.
"""

from __future__ import annotations

from .schema import REPOSITORY_VERSION


def build_manifest(
    compiled: dict,
    *,
    corpus_id: str,
    output_hash: str,
    statistics: dict,
    compile_timestamp: str,
) -> dict:
    book = compiled["book"]
    stats = compiled["stats"]
    toolchain = compiled.get("toolchain", {})

    counts = {
        "chapters": stats["chapters"],
        "sections": stats["sections"],
        "paragraphs": stats["paragraphs"],
        "citations": stats["citations"],
        "knowledge": stats["knowledgeObjects"],
        "relationships": len(compiled.get("relationships", [])),
        "evidence": stats["knowledgeObjects"],
    }

    return {
        "repositoryVersion": REPOSITORY_VERSION,
        "corpusId": corpus_id,
        "bookId": book["id"],
        "bookNumber": book["number"],
        "title": book["title"],
        "compilerVersion": toolchain.get("compiler"),
        "normalizationVersion": toolchain.get("normalizer"),
        "sourceFile": book["sourceFile"],
        "sourceSha256": book["sourceSha256"],
        "compileTimestamp": compile_timestamp,
        "outputHash": output_hash,
        # Flat counts named exactly as the Office spec requires.
        "knowledgeCount": counts["knowledge"],
        "paragraphCount": counts["paragraphs"],
        "citationCount": counts["citations"],
        "relationshipCount": counts["relationships"],
        "counts": counts,
        "statistics": statistics,
    }
