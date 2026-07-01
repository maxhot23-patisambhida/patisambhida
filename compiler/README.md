# KOS Knowledge Compiler — MVP

> Production Sprint 001 · Office of Knowledge Engineering
> The first production artifact of the Knowledge Operating System.

A **deterministic** compiler that transforms **one PKA book PDF** into
**Canonical Knowledge Objects**. No AI reasoning, no ontology, no graph, no
inference — just a reproducible pipeline. Compiling the same PDF twice produces a
**byte-identical** JSON file.

## Pipeline

```
PDF ─▶ Extract Text ─▶ Normalize ─▶ Split Paragraphs ─▶ Assign Canonical IDs ─▶ Attach Citation ─▶ Export JSON
```

| Stage | Module | Responsibility |
|---|---|---|
| Extract Text | `parser/extract.py` | `pypdf` extraction + book-9/10 legacy-font repair (reused from `scripts/build_content.py`); records source SHA-256 |
| Normalize | `normalizer/normalize.py` | Line-preserving Thai normalization → *canonical page text* (the text every offset points into) |
| Split Paragraphs · IDs · Citations · KOs | `pipeline.py` | Segments paragraphs, assigns chapter/section structure, mints IDs, attaches citations, builds Knowledge Object shells |
| Assign Canonical IDs | `id-generator/ids.py` | Pure structural-position → ID functions |
| Export JSON | `exporter/export.py` | Deterministic serialisation (`sort_keys`, UTF-8, no timestamps) |

## Usage

```bash
# Compile by book number (1–10); output → compiler/out/PKA-B01.json
python -m compiler 1

# Compile an explicit PDF
python -m compiler "web/pdf/ปฏิสัมภิทามรรค ๑ ญาณุทเทส มาติกา ๗๓.pdf"

# Prove reproducibility: compile twice and confirm byte-identical output
python -m compiler 1 --verify

# Custom output directory
python -m compiler 1 --out some/dir
```

As a library:

```python
from compiler.pipeline import compile_book
from compiler.exporter import export_json

doc = compile_book("web/pdf/....pdf")
export_json(doc, "compiler/out")
```

## Output objects

The output document is a single JSON file per book containing six object kinds,
each with a canonical `id` and explicit parent references, plus `pageText` (the
canonical page text the citation offsets index into).

| Object | ID form | Notes |
|---|---|---|
| **Book** | `PKA-B01` | one per PDF; carries source SHA-256, page/char counts |
| **Chapter** | `PKA-B01-CH01` | opens at a structural heading (นิทเทส / ภาณวาระ / มาติกา / อุทเทส / กถา / วรรค) |
| **Section** | `PKA-B01-CH01-S001` | opens at a canonical bracket marker `[๓๐]` (recorded as `markerNumber`) or a sub-heading |
| **Paragraph** | `PKA-B01-CH01-S001-P0001` | contiguous line-run within one page; carries `[start, end]` offset |
| **Citation** | `…-P0001-CIT` | provenance path: `{sourceFile, sourceSha256, page, offset, quote}` — `quote` is the exact page-text slice |
| **Knowledge Object** | `KNW-B01-0001` | one per heading; shaped to the 12 sections of **PKA-SCH-001** |

### Knowledge Object scope

A compiled Knowledge Object is a **shell**: only deterministically-extractable
fields are filled — `identity`, `names.primary`, `citation`, `evidence`,
`language`, `lifecycle: extracted`, provenance. The semantic sections
(`definition`, `classification`, `relationship`) are intentionally left empty.
The compiler performs **no inference**; enrichment is later, governed work.

## Determinism guarantees

- Output JSON is `sort_keys=True`, UTF-8, fixed indent — no construction-order or
  encoding drift.
- **No wall-clock timestamps** anywhere in the output. Provenance is the source
  PDF's SHA-256.
- IDs are pure functions of structural position.
- Extraction is the only environment-dependent step; given the same `pypdf`
  version and PDF bytes it is deterministic. `--verify` proves end-to-end
  reproducibility by compiling twice and comparing bytes.

## Verifying a citation

Every citation round-trips exactly:

```python
import json
d = json.load(open("compiler/out/PKA-B03.json", encoding="utf-8"))
pages = {p["number"]: p["text"] for p in d["pageText"]}
for c in d["citations"]:
    s, e = c["offset"]
    assert c["quote"] == pages[c["page"]][s:e]   # holds for all citations
```

## Dependencies

`pypdf` only (already a project dependency). Standard library otherwise.
