# Canonical Corpus Repository

> Production Sprint 002 · Office of Enterprise Architecture
> The permanent storage layer between the Compiler and every consumer.

```
PDF → Corpus Registration → Compiler → Canonical Corpus Repository → Website / HQ / AI Offices / API
```

The Repository is **canonical**; everything else is **projection**. It is
**technology independent**, **deterministic**, and **append-only** (version
history). From this point forward **no consumer reads PDF — or even the
repository JSON — directly.** All reads go through `loader.py`.

## Layout

```
corpus/
  patisambhidamagga/
    corpus.json                 # corpus manifest + registered sources
    BOOK-01/
      manifest.json             # canonical entry point (counts, versions, hash, provenance)
      metadata.json             # descriptive (corpus, ids, source, language)  ── deterministic
      statistics.json           # counts + coverage + provenance (duration, size)
      book.json                 # book object + canonical page text  ── deterministic
      chapters/chapters.json
      sections/sections.json
      paragraphs/paragraphs.json
      citations/citations.json
      knowledge/knowledge.json
      relationships/relationships.json   # empty: the compiler does no inference
      evidence/evidence.json             # projected from each KO's evidence
      versions/0001.json …      # append-only history (one per distinct output hash)
```

Each object folder holds one ordered collection file today; it can be sharded
later (`paragraphs/0001.json`, …) **without redesign** — the loader hides the
on-disk shape. The same layout stores Tripitaka, commentaries, sub-commentaries,
research and lexicons unchanged.

## Components

| File | Role |
|---|---|
| `schema.py` | Repository version, layout, path helpers, canonical JSON serialiser, output-hash function |
| `manager.py` | **Write layer** — create corpus, register source, create book, append versions, discover |
| `manifest.py` | Manifest generator — the canonical entry point |
| `statistics.py` | Statistics generator — counts, coverage, provenance |
| `validator.py` | Pre-publication gate — integrity, ids, citations, relationships, manifest, output hash |
| `loader.py` | **Read layer** — the ONLY way consumers access the repository |
| `__main__.py` | Read-only CLI (`discover` / `validate` / `show`) |

## Usage

The compiler writes the repository automatically on every successful compile:

```bash
python -m compiler 1            # → corpus/patisambhidamagga/BOOK-01/ (+ validate)
```

Read & inspect (never write):

```bash
python -m repository discover
python -m repository validate                 # whole repository
python -m repository validate patisambhidamagga
python -m repository show patisambhidamagga 1 # print a manifest
```

Consume programmatically — **always** via the loader:

```python
from repository import RepositoryLoader
L = RepositoryLoader()

L.list_corpora()                                  # ['patisambhidamagga']
L.manifest("patisambhidamagga", 1)                # canonical entry point, no scanning
kos = L.knowledge("patisambhidamagga", 1)         # all Knowledge Objects
ko  = L.get_knowledge("patisambhidamagga", 1, "KNW-B01-0001")
text = L.resolve_citation("patisambhidamagga", 1, "PKA-B01-CH02-S001-P0001-CIT")
```

## Principles in code

- **Canonical vs projection** — `book.json`, `metadata.json` and the object
  collections are the deterministic canonical content. `manifest.json`,
  `statistics.json` and `versions/` carry provenance and are *excluded* from the
  output hash, so the canonical layer stays byte-stable while timestamps vary.
- **Deterministic** — `schema.canonical_dumps` (sorted keys, UTF-8, fixed
  whitespace) + position-derived IDs from the compiler. Recompiling the same PDF
  leaves the output hash unchanged.
- **Append-only** — `versions/` gains a record only when the output hash changes;
  identical recompiles add nothing.
- **Manifest is the entry point** — every count, version and hash is in
  `manifest.json`; no consumer ever scans object files to learn what a book holds.
- **No runtime / agent / dashboard / AI / inference / enrichment** — this layer
  only stores. `relationships/` is empty by design; `evidence/` is a faithful
  projection of data the compiler already produced.

## Validation gate

`validate_book` / `validate_corpus` / `validate_repository` check folder
integrity, duplicate IDs, missing/broken references, broken citations (offset
round-trip), relationship endpoints, manifest consistency, and that the
recomputed canonical output hash equals the manifest's. A clean report is
required before publication.
