"""
Generate typography annotations for Book 02 pages 1–10.
Same rules as Book 01:
  - Bold number prefix (๑. ๒. etc.)
  - Purple (#8e44ad) on Pali citation lines (contain ~)
  - Grey (#6c757d) on parenthetical meta-text (...)
"""

import json, re, random, string, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
BOOK_JSON = ROOT / "web/data/book-02.json"
ED_JSON   = ROOT / "web/overrides/editorial-overrides.json"

# ── load data ──────────────────────────────────────────────────────────────
book   = json.loads(BOOK_JSON.read_text(encoding="utf-8"))
ed_raw = json.loads(ED_JSON.read_text(encoding="utf-8"))

pages = book["pageData"]

# existing entries — collect (type, page, start, end) to avoid exact dupes
existing = ed_raw.get("book-02", {}).get("entries", [])
existing_keys = {(e["type"], e["page"], e["start"], e["end"]) for e in existing}

# Thai numeral regex
THAI_NUM = "[๐-๙]"
NUM_PREFIX_RE = re.compile(rf"^({THAI_NUM}+)\.")
PAREN_RE = re.compile(r"\(([^)]+)\)")

COLOR_PALI  = "#8e44ad"
COLOR_META  = "#6c757d"

def gen_id():
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"ann-b2-{suffix}"

new_entries = []

for page_idx in range(min(10, len(pages))):  # pages 1–10 (or fewer if book is shorter)
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

print(f"Generated {len(new_entries)} new annotations for Book 02 pages 1–10.")

# ── merge into ed_raw ──────────────────────────────────────────────────────
if "book-02" not in ed_raw:
    ed_raw["book-02"] = {"entries": []}
if "entries" not in ed_raw["book-02"]:
    ed_raw["book-02"]["entries"] = []

ed_raw["book-02"]["entries"].extend(new_entries)

ED_JSON.write_text(
    json.dumps(ed_raw, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print(f"Saved to {ED_JSON}")
print(f"Total book-02 entries now: {len(ed_raw['book-02']['entries'])}")
