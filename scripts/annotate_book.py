"""
Generate typography annotations for any book.
Usage: python annotate_book.py book-03
or: python annotate_book.py book-10 50  (pages 1-50 only)
"""

import json, re, random, string, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
BOOK_SLUG = sys.argv[1] if len(sys.argv) > 1 else "book-03"
PAGE_LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else None

BOOK_JSON = ROOT / "web/data" / f"{BOOK_SLUG}.json"
ED_JSON   = ROOT / "web/overrides/editorial-overrides.json"

if not BOOK_JSON.exists():
    print(f"Error: {BOOK_JSON} not found")
    sys.exit(1)

# ── load data ──────────────────────────────────────────────────────────────
book   = json.loads(BOOK_JSON.read_text(encoding="utf-8"))
ed_raw = json.loads(ED_JSON.read_text(encoding="utf-8"))

pages = book["pageData"]
total_pages = min(len(pages), PAGE_LIMIT) if PAGE_LIMIT else len(pages)

# existing entries
existing = ed_raw.get(BOOK_SLUG, {}).get("entries", [])
existing_keys = {(e["type"], e["page"], e["start"], e["end"]) for e in existing}

THAI_NUM = "[๐-๙]"
NUM_PREFIX_RE = re.compile(rf"^({THAI_NUM}+)\.")
PAREN_RE = re.compile(r"\(([^)]+)\)")

COLOR_PALI  = "#8e44ad"
COLOR_META  = "#6c757d"

def gen_id():
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"ann-{suffix}"

new_entries = []

for page_idx in range(total_pages):
    p = pages[page_idx]
    page_num = p["number"]
    text = p["text"]

    offset = 0
    for line in text.split("\n"):
        line_len = len(line)
        line_end = offset + line_len

        # ── Number prefix bold ───────────────────────────────────────────
        m = NUM_PREFIX_RE.match(line)
        if m:
            prefix_end = offset + m.end()
            key_bold = ("bold", page_num, offset, prefix_end)
            if key_bold not in existing_keys:
                new_entries.append({
                    "id": gen_id(),
                    "type": "bold",
                    "page": page_num,
                    "start": offset,
                    "end": prefix_end,
                })
                existing_keys.add(key_bold)

        # ── Pali citation line — color full line ─────────────────────────
        if "~" in line and m:
            key_color = ("color", page_num, offset, line_end)
            if key_color not in existing_keys:
                new_entries.append({
                    "id": gen_id(),
                    "type": "color",
                    "color": COLOR_PALI,
                    "page": page_num,
                    "start": offset,
                    "end": line_end,
                })
                existing_keys.add(key_color)

        # ── Parenthetical meta-text ──────────────────────────────────────
        for pm in PAREN_RE.finditer(line):
            p_start = offset + pm.start()
            p_end   = offset + pm.end()
            key_meta = ("color", page_num, p_start, p_end)
            if key_meta not in existing_keys:
                new_entries.append({
                    "id": gen_id(),
                    "type": "color",
                    "color": COLOR_META,
                    "page": page_num,
                    "start": p_start,
                    "end": p_end,
                })
                existing_keys.add(key_meta)

        offset = line_end + 1

pages_desc = f"pages 1–{total_pages}" if PAGE_LIMIT else f"all {total_pages} pages"
print(f"Generated {len(new_entries)} new annotations for {BOOK_SLUG} ({pages_desc}).")

# ── merge into ed_raw ──────────────────────────────────────────────────────
if BOOK_SLUG not in ed_raw:
    ed_raw[BOOK_SLUG] = {"entries": []}
if "entries" not in ed_raw[BOOK_SLUG]:
    ed_raw[BOOK_SLUG]["entries"] = []

ed_raw[BOOK_SLUG]["entries"].extend(new_entries)

ED_JSON.write_text(
    json.dumps(ed_raw, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print(f"Saved to {ED_JSON}")
print(f"Total {BOOK_SLUG} entries now: {len(ed_raw[BOOK_SLUG]['entries'])}")
