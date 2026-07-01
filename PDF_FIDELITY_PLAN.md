# PDF Fidelity Plan — Phase 5
## Evolving the Digital Edition Toward High-Fidelity PDF Reproduction

**Status:** Planning only — no code changes.
**Scope:** Book 01 as proof of concept, then all 8 books.
**Constraint:** Static SPA, no backend, no changes to `web/data/`, editorial-only path.

---

## 1. Current Data Model

### 1.1 Book JSON Structure

Each book lives in `web/data/book-NN.json`. Top-level fields:

| Field | Type | Description |
|---|---|---|
| `slug` | `string` | `"book-01"` |
| `number` | `number` | `1` (Thai numeral parsed from filename) |
| `title` | `string` | Full Thai title from PDF filename |
| `file` | `string` | PDF filename (used to build `../pdf/<file>#page=N` link) |
| `pages` | `number` | Total page count |
| `chars` | `number` | Total character count |
| `note` | `string` | Human summary note |
| `firstExcerpt` | `string` | Excerpt from page 1 |
| `pageData` | `PageData[]` | Per-page records |

### 1.2 Page Structure

Each element of `pageData` is a flat object with four fields:

```json
{
  "number": 10,
  "text": "6\nวิหารญาณ สมาปัตตัฏฐญาณ\n๒๙. วิหารนานตฺเต ปญฺญา วิหารฏฺ เฐ ญาณ ~\n...",
  "excerpt": "6 วิหารญาณ สมาปัตตัฏฐญาณ …",
  "headings": [
    "วิหารญาณ สมาปัตตัฏฐญาณ",
    "๒๙. วิหารนานตฺเต ปญฺญา วิหารฏฺ เฐ ญาณ ~",
    "๓๐. สมาปตฺตินานตฺเต ปญฺญา สมาปตฺตฏฺ เฐ ญาณ ~"
  ]
}
```

**Key structural pattern in `text`:**
- Line 1 of each page is typically a standalone running-header character or number extracted from the PDF (e.g. `"ก"`, `"6"`, `"1"`). This is a PDF artifact, not content.
- Remaining lines are the actual content, separated by `\n`.
- No paragraph tags, no font information, no indentation metadata.

### 1.3 Text Storage Format

The text is a **plain UTF-8 string** produced by `pypdf`'s `page.extract_text()`, then cleaned by `normalize_text()` in `scripts/build_content.py`.

Normalizations applied:
- `\xa0` → space
- Multiple spaces/tabs → single space
- Whitespace around newlines → bare `\n`
- Thai PDF spacing artifacts repaired (e.g. `"เป ็ น"` → `"เป็น"`)
- Sara am decomposition normalized

**What is NOT preserved** (stripped by PDF text extraction):
- Font size / font weight (bold, italic)
- Text color
- Text alignment (center, left, right)
- Indentation (tab stops, margins)
- Line spacing / paragraph spacing
- Visual dividers (horizontal rules)
- Column layout

### 1.4 Offsets Available

Editorial entries use **character offsets into `page.text`**. These are:
- Zero-based integer positions in the UTF-8 string
- Inclusive of `\n` characters (newlines count as offset 1)
- Used by both the editorial system and the reader annotation (highlight) system
- No byte offsets or paragraph-level offsets

Example from `web/overrides/editorial-overrides.json` for book-01 page 1:
```json
{ "id": "ed-mqdl40es-7tltb", "type": "italic",   "page": 1, "start": 2, "end": 24 }
{ "id": "ed-mqdl42ws-5b45f", "type": "bold",     "page": 1, "start": 2, "end": 24 }
{ "id": "ed-mqdl49nw-dviuo", "type": "align-center", "page": 1, "start": 2, "end": 24 }
{ "id": "ed-mqdl4i4s-x5sy4", "type": "heading-lg",  "page": 1, "start": 2, "end": 24 }
```

Offset 2 corresponds to the start of `"สารบัญ มาติกา ญาณุทเทส"` (after the `"ก\n"` running header on line 1).

### 1.5 Metadata Available

- `page.number`: PDF page number (1-indexed, matches PDF viewer `#page=N`)
- `page.headings[]`: heuristically detected short lines (see §4 for reliability)
- `book.file`: PDF filename for back-linking
- `catalog.json`: book-level summary (title, page count, total chars)

No coordinate data, no font metrics, no glyph positions.

---

## 2. Current Editorial Layer

### 2.1 All Supported Entry Types

Defined in `app.js:409`:
```js
const EDITORIAL_TYPES = new Set([
  "bold", "italic", "color", "replace", "heading-lg", "heading-md", "heading-sm",
  "image-block",
  ...LAYOUT_TYPES   // align-center, align-left, align-right, indent, spacing-top, spacing-bottom
]);
```

Full inventory:

| Type | Category | Visual Effect | Has Params |
|---|---|---|---|
| `bold` | Inline | `font-weight: 700` | — |
| `italic` | Inline | `font-style: oblique 12deg` | — |
| `color` | Inline | `color: <value>` | `color` (hex) |
| `replace` | Inline | Swap text in range | `replacement` (string) |
| `heading-lg` | Block | 1.8em, bold, block display | — |
| `heading-md` | Block | 1.4em, bold, block display | — |
| `heading-sm` | Block | 1.2em, semi-bold, block display | — |
| `image-block` | Point insert | `<figure>` with `<img>` | `image`, `caption` |
| `align-center` | Layout | `text-align: center`, block | — |
| `align-left` | Layout | `text-align: left`, block | — |
| `align-right` | Layout | `text-align: right`, block | — |
| `indent` | Layout | `text-indent: 2em`, block | — |
| `spacing-top` | Layout | `margin-top: 1.5em`, block | — |
| `spacing-bottom` | Layout | `margin-bottom: 1.5em`, block | — |

**Color presets** (stored as hex in `color` field):
| Preset | Hex | Meaning |
|---|---|---|
| Blue | `#0d6efd` | คำสำคัญ / IMPORTANT |
| Purple | `#8e44ad` | คำบาลี / PALI |
| Green | `#1e8449` | คำอธิบาย / COMMENTARY |
| Red | `#c0392b` | ตรวจสอบ / REVIEW |

### 2.2 Storage Format

Stored in two layers:
1. **Baseline file** `web/overrides/editorial-overrides.json`:
   ```json
   { "book-01": { "entries": [ {...entry...} ] } }
   ```
2. **Admin overlay** `localStorage["psm.editorial"]`:
   ```json
   { "entries": [...added...], "removed": [...tombstone ids...] }
   ```

Each entry (minimum fields):
```json
{
  "id": "ed-<timestamp>-<random>",
  "type": "bold",
  "page": 5,
  "start": 120,
  "end": 145
}
```

Optional fields: `color` (color type), `replacement` (replace type), `image` + `caption` (image-block type).

### 2.3 Rendering Pipeline

`renderAnnotatedText(text, annotations, query, editorial)` in `app.js:921`:

1. Build `noteRanges` — reader highlights (private, `localStorage["psm.annotations"]`)
2. Build `searchRanges` — current search query matches
3. Build `formats` — all inline editorial (bold/italic/color/heading/layout)
4. Build `replaceRanges` — replacement ops (consume text)
5. Build `imageBlocks` — point-insertion images
6. Merge replace + image into sorted `ops` list
7. Emit via `emitNormal(from, to)` — slices text at all boundaries, calls `wrapChunk`
8. `wrapChunk` applies layers inside-out: mark → bold → italic → color → highlight → block (heading + layout)

**Key constraints of the current renderer:**
- All types operate on **character-offset ranges in a single flat string** — no paragraph model
- Block-level types (`heading-*`, `align-*`, `indent`, `spacing-*`) are rendered as `<span class="...">`, not semantic block elements — they visually behave as blocks via `display: block` in CSS
- Multiple formats can overlap the same range (e.g. `bold` + `heading-lg` + `align-center` on same span)
- A `replace` entry replaces the raw text in that range; it does not interact with `formats` for that same range
- `image-block` uses `start == end` (zero-width anchor) and is injected between text chunks

### 2.4 Limitations

1. **No paragraph model**: The text is a flat string. There is no `<p>` element, no concept of "this newline ends a paragraph." Structural types must be applied per character range.
2. **Newlines are invisible**: `\n` chars in `page.text` are rendered as-is in the `innerHTML`. The browser collapses them unless CSS `white-space: pre-wrap` or similar is set. (Check `styles.css` for the page text container's whitespace handling.)
3. **Overlapping block types**: If two block-level editorial entries overlap on the same range, only one will "win" visually (the last one applied in `wrapChunk`). Partial overlaps create nested spans that may render unexpectedly.
4. **`replace` vs `formats` independence**: A replaced span does not apply bold/italic styling — it outputs only the replacement string, bypassing `wrapChunk`.
5. **No multi-page entries**: Every entry is scoped to a single page. Cross-page structural elements (e.g., a section heading that spans a page break) cannot be expressed.
6. **Admin-only tooling**: All entries require the admin panel (Ctrl+Shift+E). There is no scripted import path.

---

## 3. Structure Layer Feasibility

The editorial architecture can support new semantic types without redesign. The renderer already treats unknown inline/block types gracefully — `EDITORIAL_TYPES` just needs to include the new type name, and CSS needs the corresponding class.

### 3.1 Type-by-Type Analysis

**`heading` / `subheading`**

Already exists as `heading-lg`, `heading-md`, `heading-sm`. No new type needed; just more editorial entries.

- Feasibility: **Already supported**
- Complexity: Low (curation effort, not code)
- Risk: None

---

**`quote`**

A block quotation — indented, visually distinguished. The existing `indent` + `spacing-top` + `spacing-bottom` combination produces a quasi-quote layout. A dedicated `quote` type would give a semantic CSS class and enable distinct styling (e.g., left border).

- Feasibility: **High**
- Complexity: Low
  - Add `"quote"` to `EDITORIAL_TYPES` and `LAYOUT_TYPES`
  - Add `.ed-quote { display: block; border-left: 3px solid var(--accent-line); padding-left: 1em; margin: 0.8em 0; font-style: oblique 6deg; }` to CSS
  - Add button to admin panel layout row
- Risk: Low — purely additive, no changes to renderer logic

---

**`indent`**

Already exists. `text-indent: 2em` on a block span.

- Feasibility: **Already supported**
- Complexity: None
- Risk: None

---

**`divider`**

A horizontal rule to separate sections — analogous to `image-block` in that it is a zero-width anchor point (`start == end`), not a text range. Would render as `<hr class="ed-divider">`.

- Feasibility: **High**
- Complexity: Low-Medium
  - New type `"divider"` in `EDITORIAL_TYPES`
  - Handled in the `ops` pipeline alongside `image-block` (it is a point injection)
  - CSS: `.ed-divider { display: block; border: none; border-top: 1px solid var(--paper-border); margin: 1.2em 0; }`
  - Admin panel needs a point-insertion mode (currently only `image-block` uses this)
- Risk: Low. The `ops` pipeline already handles point insertions.

---

**`emphasis`**

Equivalent to `italic` + `color` (purple, `#8e44ad`) for Pali terms. Redundant with `pali-term` below. Not recommended as a separate type.

- Feasibility: **Already coverable** via `italic` + `color` combination
- Complexity: None (use existing types)
- Risk: None

---

**`pali-term`**

A named semantic color preset for Pali vocabulary. Currently achievable with `color: "#8e44ad"`. A dedicated `pali-term` type would encode the semantic meaning rather than just a color, making it easier to query, filter, or restyle globally.

- Feasibility: **High**
- Complexity: Low
  - Add `"pali-term"` to `EDITORIAL_TYPES`
  - In `wrapChunk`, treat `pali-term` as `color = "#8e44ad"` (or a CSS variable)
  - In admin panel, add `"คำบาลี"` button that inserts `pali-term` instead of `color`
  - Stats panel gains a `pali-term` counter
- Risk: Low. Purely additive.

---

**`reference-block`**

A citation or cross-reference block — styled like a smaller, indented paragraph with a distinct background. Could model the [bracket] references common in the PDFs (e.g., `[๓๐]`).

- Feasibility: **Medium**
- Complexity: Medium
  - New type in `EDITORIAL_TYPES`
  - CSS class `.ed-reference-block { display: block; background: var(--paper-alt); padding: 0.3em 0.8em; border-radius: 3px; font-size: 0.9em; margin: 0.4em 0; }`
  - Admin panel needs a new button
- Risk: Low. The bracket markers `[๓๐]` are preserved in the extracted text; admin can select them manually.

---

### 3.2 Summary Table

| Type | Status | Code Changes | CSS Changes | Admin Panel Changes |
|---|---|---|---|---|
| `heading-lg/md/sm` | ✅ Exists | None | None | None |
| `quote` | 🟡 New | 3 lines | 1 rule | 1 button |
| `indent` | ✅ Exists | None | None | None |
| `divider` | 🟡 New | ~15 lines | 1 rule | 1 button (point mode) |
| `pali-term` | 🟡 New | ~5 lines | Optional | 1 button |
| `reference-block` | 🟡 New | 3 lines | 1 rule | 1 button |
| `emphasis` | ✅ Coverable | None | None | None |

All new types fit cleanly into the existing architecture. No redesign is needed.

---

## 4. PDF ↔ JSON Page Mapping

### 4.1 Current Assumptions

`build_content.py` uses:
```python
for page_index, page in enumerate(reader.pages, start=1):
    pages.append({ "number": page_index, ... })
```

And the app links back to the PDF using:
```js
const pdfHref = `../pdf/${encodeURIComponent(book.file)}#page=${page.number}`;
```

**This is a direct 1:1 mapping**: PDF reader page N → JSON `pageData[N-1]` (0-indexed array, 1-indexed `number`).

### 4.2 Reliability

**High for most pages.** The PDF files are single-volume documents (not scans with missing pages), and `pypdf` reads all physical pages sequentially. Book 01 has 212 PDF pages → 212 JSON pages.

Validated observation: The first line of `page.text` often contains a standalone PDF running header (e.g., `"ก"`, `"6"`, `"1"`), which confirms the sequence matches the PDF's internal page label.

### 4.3 Risks

| Risk | Likelihood | Impact |
|---|---|---|
| PDF has blank/cover pages not in text extraction | Low | Medium — offset by 1 or more |
| Two-column layout collapses into reordered text | Medium | High — content reordered within a page |
| Page labels in PDF differ from physical page order | Low | Low — the `#page=N` link uses physical order |
| Thai ligatures split across extraction boundaries | Low | Low — text normalization repairs most |
| Offset drift from future PDF re-extraction | Medium | High — all editorial offsets become invalid |

### 4.4 Edge Cases

1. **Cover / blank pages**: Book 01 page 1 shows `"ก"` as first character — this appears to be the PDF's "page ก" label (Thai alphabet pagination used in prefaces). The content starts at offset 2. This is consistent and predictable.

2. **Running headers**: Each page begins with a short header line (page number or section label). In Book 01 page 10: `"6\n"` precedes the real content. This `\n` at offset 1 means real content starts at offset 2. Editorial entries already account for this (e.g., `start: 2` in the existing book-01 entries).

3. **Column text**: If a PDF page has two columns, `pypdf` may reorder or interleave the text. No evidence of this in Book 01 (appears single-column), but Books 6-8 (longer commentary pages) may have it.

4. **Re-extraction invalidation**: If `build_content.py` is ever re-run with a different PDF or different `pypdf` version, all character offsets in `editorial-overrides.json` become invalid. This is the **highest structural risk** of the entire approach. The editorial layer has no checksum or version binding to the source text.

### 4.5 Conclusion on Mapping

For Book 01 (and likely all 8 books): **PDF page N reliably corresponds to `pageData[N-1]`**. The PDF link system already works. Editorial entries anchored to `page` + `start`/`end` will correctly round-trip to the PDF. The main operational risk is offset invalidation on re-extraction.

---

## 5. Fidelity Analysis — Book 01

Book 01 is the table-of-contents (TOC) and index volume. It has a higher density of structural elements than the commentary books.

### 5.1 What Can Be Recovered

**Headings** — `Medium`

The `headings[]` field already detects most headings heuristically (199/212 pages have detected headings). However, the detector picks up too many items — numbered list items are flagged alongside true section headings. Manual curation via `heading-lg/md/sm` editorial entries is needed to promote the right lines. The offset of any line can be located by searching the page text. For Book 01, headings are visually obvious (larger font in PDF), but character offsets must be found manually since font size is lost.

**Bold text** — `Hard`

PDF text extraction strips all font weight. Bold text in the PDF (Pali terms, section titles mid-paragraph) appears as plain text in JSON. To recover it, an editor must compare the PDF page visually and manually select the corresponding text range. No automation is possible with the current extraction pipeline. Estimated count: several hundred bold spans across Book 01.

**Centered text** — `Hard`

All alignment metadata is lost. Centered headers (e.g., main titles, chapter labels) appear as plain lines in the text. Recovery requires visual comparison to PDF and manual `align-center` entries. However, many centered texts also appear at line boundaries (isolated short lines), making them detectable by pattern if the admin can identify them by position.

**Paragraph structure** — `Hard`

The text uses `\n` as a line separator, but there is no semantic paragraph break marker. In the PDF, paragraph breaks are indicated by larger vertical spacing between blocks of text. This is completely absent in the extracted text. Recovery would require inserting `spacing-bottom` or `spacing-top` editorial entries at paragraph boundaries, identified only by visual PDF inspection. This is feasible but labor-intensive.

**Spacing (line and paragraph)** — `Very Hard`

Line spacing and vertical rhythm from the PDF are invisible in the plain text. Only approximate recovery is possible via `spacing-top` and `spacing-bottom` editorial entries at manually identified positions. No tooling exists to assist. For Book 01, the TOC pages have a regular list structure where spacing is implied by the numbered list format — somewhat easier than prose paragraphs.

**Dividers** — `Very Hard`

Horizontal rules and decorative section dividers from the PDF are completely absent in extracted text. No character is emitted for them. Recovery requires: (a) identifying their position in the PDF, (b) finding the nearest character offset in the corresponding JSON page, (c) inserting a `divider` editorial entry (which does not yet exist as a type). This is possible but requires both a new type and manual curation.

**Lists** — `Medium`

Thai numeral lists (e.g., `๑. สุตมยญาณุทเทส`) are largely preserved as text because the list markers are part of the extracted characters. The structure is visible in the raw text. Recovery requires `indent` entries (already supported) or `reference-block` entries. For Book 01's TOC, the numbered items are fully preserved in text and only need alignment/indent styling.

### 5.2 Summary Ranking

| Feature | Difficulty | Notes |
|---|---|---|
| Headings | Medium | Heuristic detection exists; manual promotion to `heading-*` |
| Bold text | Hard | No font metadata; requires visual PDF comparison |
| Centered text | Hard | No alignment metadata; requires visual PDF comparison |
| Paragraph structure | Hard | No paragraph model in text; `spacing-*` entries needed |
| Spacing | Very Hard | Line/paragraph spacing completely lost |
| Dividers | Very Hard | Not in extracted text at all; requires new type + manual work |
| Lists | Medium | Thai numeral markers preserved; `indent` applies |

---

## 6. Recommended Architecture

### Option A: Extend Existing Editorial Layer

Add new semantic types to `EDITORIAL_TYPES`. New types like `quote`, `divider`, `pali-term`, `reference-block` follow the same storage and rendering path as current types.

**Pros:**
- Zero redesign; existing admin panel, storage, export, undo/redo all work immediately
- New entries go into `editorial-overrides.json` alongside existing bold/heading entries
- Search remains unaffected (operates on raw text, not editorial)
- Backward compatible: old entries continue to work

**Cons:**
- Editorial overrides file grows large with many entries per book
- No distinction between "fidelity restoration" entries and "admin commentary" entries
- Admin panel shows all types mixed together

---

### Option B: Dedicated Structure Layer

A separate `structure-overrides.json` with its own JSON schema, renderer, and admin UI. Structure entries express semantic document structure (paragraph, section, quote, divider) independently from the editorial commentary layer.

**Pros:**
- Cleaner conceptual separation (document structure vs. editorial annotation)
- Could support future features (accessibility headings, outline navigation from structure)

**Cons:**
- Requires a second pass through the renderer
- Admin panel needs a second panel or a mode toggle
- Export, import, undo/redo must be duplicated
- No benefit over Option A for the static SPA constraint
- Significantly more code to maintain

---

### Option C: Hybrid Model ✅ Recommended

Extend the editorial layer (Option A) with two targeted additions:

1. **Semantic color types**: Add `pali-term` as a named alias for the purple color — no visual change, semantic upgrade.
2. **Point-injection types**: Add `divider` using the same `start == end` mechanism as `image-block`.
3. **Block semantic types**: Add `quote` and `reference-block` as layout variants (same as `align-center` / `indent` family).

All new types live in `EDITORIAL_TYPES`. A `STRUCTURE_TYPES` constant (a subset) can group them for display in the admin panel (separate row or section heading in the UI), without requiring a separate storage layer.

**Why this over B:** The existing editorial architecture already handles heterogeneous type sets cleanly. The renderer, storage, export, and admin panel all work generically by type string — adding new types is trivial. A full separation (Option B) would cost several days of work for no gain within the static SPA constraint.

**Architecture diagram:**

```
editorial-overrides.json
└── book-01.entries[]
    ├── bold / italic / color / replace    ← Inline commentary
    ├── heading-lg / md / sm               ← Document structure (existing)
    ├── align-* / indent / spacing-*       ← Layout (existing)
    ├── image-block                        ← Point insert (existing)
    ├── quote / reference-block            ← NEW: semantic blocks
    ├── pali-term                          ← NEW: semantic inline
    └── divider                            ← NEW: point insert

renderAnnotatedText()
├── formats[]  →  wrapChunk()             ← inline + block types
├── ops[]      →  emitNormal() + inject   ← replace + point inserts
│   ├── image-block
│   └── divider (NEW, same path)
└── searchRanges / noteRanges             ← unaffected
```

---

## 7. Phase Plan

### Phase 5.1 — Proof of Concept (Book 01, Pages 1–20)

**Goal:** Validate that the editorial architecture can reproduce the PDF's visual structure on a small sample. Add the minimum new types, test rendering, measure effort.

**Tasks:**
1. Add `pali-term`, `quote`, `divider`, `reference-block` to `EDITORIAL_TYPES`
2. Add `divider` to the `ops` point-injection pipeline in `renderAnnotatedText`
3. Add CSS classes for the new types
4. Add new buttons to the admin panel layout row
5. Manually annotate pages 1–20 of Book 01 from PDF comparison:
   - Mark all headings with `heading-lg/md/sm`
   - Mark all centered text with `align-center`
   - Mark Pali terms with `pali-term`
   - Insert `divider` entries at visual section breaks
   - Mark paragraph indents with `indent`
6. Export and commit `editorial-overrides.json`
7. Side-by-side PDF/web comparison: measure structural fidelity

**Effort:** 2–4 days (1 day code, 1–3 days curation for 20 pages)
**Risks:**
- Offset location for bold/centered text requires visual PDF hunting — tedious
- No tooling to semi-automate offset detection
**Expected fidelity gain:** Structural headings and alignment visible on TOC pages; dividers approximate section breaks

---

### Phase 5.2 — Full Book 01 (212 Pages)

**Goal:** Complete structural annotation of Book 01. Establish workflow and per-page effort estimate for scaling.

**Prerequisites:** Phase 5.1 complete; code stable.

**Tasks:**
1. Annotate all 212 pages of Book 01 from PDF comparison
2. Build a lightweight helper tool (or spreadsheet) to record: page N → offset of line start → type
3. Establish naming conventions: what qualifies as `heading-lg` vs `heading-md`
4. Validate: open each annotated page in the reader and compare to PDF screenshot
5. Commit final `editorial-overrides.json` for Book 01

**Effort:** 2–4 weeks (manual curation; ~15–30 min/page × 212 pages)
**Risks:**
- Commentary pages (pages 40+) have denser prose — harder to identify paragraph boundaries
- Pali quotation blocks may need `quote` type for every occurrence
- Offset errors accumulate — need a per-page review pass
**Expected fidelity gain:**
- 100% headings covered
- ~70% of centered text covered
- ~50% of bold text covered (most prominent uses)
- ~30% of paragraph spacing recovered (major paragraph breaks only)
- Dividers at all major section breaks

---

### Phase 5.3 — All 8 Books

**Goal:** Scale the annotation workflow to all 1830 pages.

**Prerequisites:** Phase 5.2 complete; workflow documented; per-page effort validated.

**Tasks:**
1. Apply Phase 5.2 workflow to Books 02–08
2. Books 02–08 are commentary books — more prose, fewer structural elements per page
3. Prioritize: headings first (highest fidelity gain), then bold terms, then alignment
4. Consider semi-automated tooling: a script that pre-identifies short isolated lines as heading candidates and outputs `{ page, start, end, candidate_type }` JSON for admin review
5. Final review pass: PDF vs. web screenshot comparison for each book

**Effort:** 6–12 weeks (scaled from Phase 5.2; Books 06–08 are 280–308 pages each)
**Risks:**
- Re-extraction invalidation (see §4.3): if PDFs are ever re-processed, all offsets reset. **Mitigation**: freeze `web/data/*.json` permanently (already a hard constraint) and add a hash of `page.text` to each editorial entry as a sanity check.
- Effort may be underestimated for Books 06–08 (454k and 482k chars respectively)
- Structural patterns differ across books — each book may need its own annotation conventions
**Expected fidelity gain (all books):**
- Headings: ~90% recovery (Easy/Medium features)
- Bold Pali terms: ~60% recovery (most prominent occurrences)
- Centered text: ~50% recovery
- Paragraph spacing: ~20% recovery (major breaks only)
- Dividers: ~30% recovery (major section breaks)
- Overall visual resemblance to PDF: moderate (structural skeleton visible, not pixel-perfect)

---

## 8. Key Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Offset invalidation on re-extraction | High | Hard constraint: never re-run `build_content.py`. Store `page.text` hash in editorial metadata. |
| Manual curation errors (wrong offset) | Medium | Per-page review pass; admin can select text in reader to get offsets interactively |
| Pali rendering (Thai oblique) in `pali-term` | Low | Existing `ed-italic` uses `oblique 12deg` — same will apply |
| Admin panel overload (too many buttons) | Low | Group new types in a collapsible "Structure" row |
| Scope creep to Books 02–08 before Book 01 done | Medium | Complete Phase 5.2 fully before starting Phase 5.3 |

---

## 9. What This Plan Does NOT Address

- **Pixel-perfect reproduction**: The goal is semantic/structural fidelity, not exact layout match.
- **Automated bold detection**: Without font metadata from the PDF, bold text cannot be detected programmatically with the current stack. This requires either `pypdf`'s font extraction APIs (complex, would modify `build_content.py`) or visual AI assistance.
- **Two-column layout detection**: If any PDF pages use two-column text, the current extractor reorders the content. Fixing this would require changes to `build_content.py` and is out of scope.
- **Accessibility headings**: The `ed-heading` spans are visual only (`<span>`, not `<h1>`/`<h2>`). Upgrading to semantic HTML headings would require renderer changes and is a separate task.

---

*Generated 2026-06-15 from codebase investigation of `web/app.js`, `web/data/book-01.json`, `web/overrides/editorial-overrides.json`, `scripts/build_content.py`, `web/knowledge.js`, and `web/styles.css`.*
