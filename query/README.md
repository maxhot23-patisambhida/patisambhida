# Canonical Knowledge Query Engine

> Production Sprint 003 · Office of Enterprise Architecture
> The single, read-only knowledge access layer of the Knowledge Operating System.

```
Compiler creates Knowledge → Repository preserves Knowledge → Query Engine reveals Knowledge
```

Every consumer — website, dashboard, AI offices, runtime, API — reads the
Canonical Corpus Repository **only** through this engine. No consumer touches
repository files or knows the repository layout, so the repository stays free to
evolve internally without breaking anyone.

**Repository is storage. Query Engine is access.**

## Principles

Deterministic · Immutable · Typed · Read-only · Technology-independent ·
Repository-driven. Every function returns a **typed object** (`types.py`) — never
raw JSON. No AI, no embeddings, no semantic search, no inference: only
deterministic retrieval.

## Package layout

| File | Role |
|---|---|
| `repository.py` | `open_repository()` + the `QueryEngine` facade (the public API) |
| `books.py` `chapters.py` `sections.py` `paragraphs.py` `citations.py` `knowledge.py` `relationships.py` | per-object getters, parent/children navigation, kind-specific finders |
| `search.py` | `find_by_id` + deterministic `search_text/exact/prefix/contains/regex` |
| `cache.py` | transparent, disposable read cache over the Repository Loader |
| `types.py` | frozen typed objects + `from_dict` builders (the only layout-aware code) |
| `exceptions.py` | typed errors — no silent failure |
| `tests/` | real tests against compiled Book 1 + Book 3 (no mocks) |

## Usage

```python
from query import open_repository

repo = open_repository()                       # validates BEFORE the first query

# discovery — stable when new corpora (Tripitaka, commentaries, …) are added
repo.list_corpora()                            # [Corpus(...)]
repo.list_books("patisambhidamagga")           # [Book(...), ...]

# object access (typed)
book = repo.get_book("patisambhidamagga", 1)
chapter = repo.get_chapter("patisambhidamagga", 1, book.chapter_ids[0])
para = repo.get_paragraph("patisambhidamagga", 1, "PKA-B01-CH02-S001-P0001")
ko = repo.get_knowledge_object("patisambhidamagga", 1, "KNW-B01-0001")

# navigation
repo.find_parent(para)                         # -> Section
repo.find_children(chapter)                    # -> [Section, ...]
repo.find_related(ko)                          # -> [KnowledgeObject, ...]
repo.find_by_id("PKA-B01-CH01")                # any object, by canonical id

# finders
repo.find_by_page(1, corpus_id="patisambhidamagga", book_number=3)
repo.find_by_marker(30, corpus_id="patisambhidamagga", book_number=3)
repo.find_by_source(book.source_file)

# deterministic search
repo.search_contains("สุตมยญาณ")
repo.search_exact("๑. มาติกา ~ หัวข้อญาณ ๗๓", kinds=["knowledge"])
repo.search_prefix("สุต")
repo.search_regex("ญาณ$", kinds=["paragraph"])

# citations resolve to exact source text (offset round-trip, verified)
repo.resolve_citation(para.citation_id, corpus_id="patisambhidamagga", book_number=1)
```

`search_*` return `SearchHit` (corpus, book, kind, object_id, field, snippet, and
the typed `obj`). All results are returned in a stable order.

## Validation (no silent failure)

`open_repository()` runs the repository validator **before the first query**.
A broken repository (missing files, duplicate/missing ids, broken citations,
manifest/hash mismatch) raises `RepositoryValidationError` immediately rather
than failing quietly later. Pass `validate=False` only for trusted fast paths.

## Cache

A transparent read cache memoises typed collections, indexes, page text and
manifests. It is **disposable** (`repo.clear_cache()`) and **never mutates
canonical content** — the repository is permanent, the cache is not.

## Future compatibility

The API takes `(corpus_id, book_number)` and discovers corpora dynamically, so
adding Tripitaka, commentaries, sub-commentaries, research or lexicons requires
**no consumer code changes**. Only `types.py:from_dict` is layout-aware; if the
repository format evolves, consumers stay stable.

## Tests

```bash
python query/tests/test_query_engine.py      # compiles Book 1 + 3, runs every query
```

Real repositories only — no mocks, no fabricated data.

## Relationship to the Repository Loader

The Query Engine is built on `repository/loader.py` (no duplicated file logic).
From Sprint 003 onward the **loader is internal to the repository package**; all
external knowledge access goes through this engine.
