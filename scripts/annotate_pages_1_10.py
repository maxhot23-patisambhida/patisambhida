"""
Generate typography annotations for Book 01 pages 1–10.

Rules:
  - All pages 1-10: bold the Thai-numeral number prefix (๑. ๒. etc.)
  - Pages 5-10: color full Pali citation lines (contain ~) in purple (#8e44ad)
  - All pages 1-10: color parenthetical meta-text (...) in green (#1e8449)

Writes new entries into web/overrides/editorial-overrides.json
without duplicating existing entries.
"""

import json, re, random, string, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
BOOK_JSON = ROOT / "web/data/book-01.json"
ED_JSON   = ROOT / "web/overrides/editorial-overrides.json"

# ── load data ──────────────────────────────────────────────────────────────
book   = json.loads(BOOK_JSON.read_text(encoding="utf-8"))
ed_raw = json.loads(ED_JSON.read_text(encoding="utf-8"))

pages = book["pageData"]  # list, index = page_number - 1

# existing entries — collect (type, page, start, end) to avoid exact dupes
existing = ed_raw.get("book-01", {}).get("entries", [])
existing_keys = {(e["type"], e["page"], e["start"], e["end"]) for e in existing}

# Thai numeral regex: ๐-๙ = U+0E50–U+0E59
THAI_NUM = "[๐-๙]"
# Line starts with one or more Thai numerals followed by "."
NUM_PREFIX_RE = re.compile(rf"^({THAI_NUM}+)\.")
# Parenthetical text anywhere in a line
PAREN_RE = re.compile(r"\(([^)]+)\)")

COLOR_PALI  = "#8e44ad"   # purple — Pali citation
COLOR_META  = "#6c757d"   # muted grey — parenthetical meta

def gen_id():
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"ann-{suffix}"

new_entries = []

for page_idx in range(len(pages)):  # all pages in book
    p = pages[page_idx]
    page_num = p["number"]
    text = p["text"]
    is_content_page = page_num >= 5  # pages 1-4 TOC, 5+ content

    # Walk line by line, track character offset
    offset = 0
    for line in text.split("\n"):
        line_len = len(line)
        line_end = offset + line_len

        # ── Number prefix bold ───────────────────────────────────────────
        m = NUM_PREFIX_RE.match(line)
        if m:
            prefix_end = offset + m.end()  # end of "๑." (not including space)
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

        # ── Pali citation line (contains ~) — color full line ────────────
        if is_content_page and "~" in line and m:
            key_pali = (COLOR_PALI, page_num, offset, line_end)
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
            # include the parentheses themselves
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

        offset = line_end + 1  # +1 for the \n

print(f"Generated {len(new_entries)} new annotations.")

# ── merge into ed_raw ──────────────────────────────────────────────────────
if "book-01" not in ed_raw:
    ed_raw["book-01"] = {"entries": []}
if "entries" not in ed_raw["book-01"]:
    ed_raw["book-01"]["entries"] = []

ed_raw["book-01"]["entries"].extend(new_entries)

ED_JSON.write_text(
    json.dumps(ed_raw, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print(f"Saved to {ED_JSON}")
print(f"Total book-01 entries now: {len(ed_raw['book-01']['entries'])}")
