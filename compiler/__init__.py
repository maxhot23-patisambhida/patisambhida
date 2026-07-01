"""KOS Knowledge Compiler — Production Sprint 001 (MVP).

A deterministic, reproducible pipeline that transforms one PKA book PDF into
Canonical Knowledge Objects (Book / Chapter / Section / Paragraph / Citation /
Knowledge Object).

No AI reasoning. No ontology. No graph. No inference. Running twice on the same
input produces byte-identical output.

Pipeline:  PDF -> Extract Text -> Normalize -> Split Paragraphs
           -> Assign Canonical IDs -> Attach Citation -> Export JSON
"""

SCHEMA_VERSION = "kos-compiler/1"
