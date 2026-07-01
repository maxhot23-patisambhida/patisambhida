"""Rebuild only books 9 and 10 with the encoding fixes."""
import sys, json
sys.path.insert(0, 'F:/Patisambhida/scripts')
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
from pypdf import PdfReader
from build_content import (
    fix_pua_encoding, fix_ascii_diacritics,
    normalize_text, make_excerpt, detect_headings,
    thai_digit_to_int, slug_for, BOOK_NOTES,
)

PDF_DIR = Path('F:/Patisambhida/web/pdf')
DATA_DIR = Path('F:/Patisambhida/web/data')

TARGET_BOOKS = {9, 10}

pdfs = sorted(PDF_DIR.glob("*.pdf"), key=lambda p: thai_digit_to_int(p.stem) or 0)

for idx, pdf_path in enumerate(pdfs, start=1):
    number = thai_digit_to_int(pdf_path.stem) or idx
    if number not in TARGET_BOOKS:
        continue

    slug = slug_for(pdf_path, idx)
    print(f"Building {slug} ({pdf_path.name})...")

    reader = PdfReader(str(pdf_path))
    pages = []
    char_count = 0
    for page_index, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        if number == 10:
            raw = fix_pua_encoding(raw)
        elif number == 9:
            raw = fix_ascii_diacritics(raw)
        text = normalize_text(raw)
        char_count += len(text)
        pages.append({
            "number": page_index,
            "text": text,
            "excerpt": make_excerpt(text),
            "headings": detect_headings(text),
        })

    book = {
        "slug": slug,
        "number": number,
        "title": pdf_path.stem,
        "file": pdf_path.name,
        "pages": len(pages),
        "chars": char_count,
        "note": BOOK_NOTES.get(number, ""),
        "firstExcerpt": pages[0]["excerpt"] if pages else "",
    }

    out_path = DATA_DIR / f"{slug}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({**book, "pageData": pages}, f, ensure_ascii=False, separators=(",", ":"))

    print(f"  -> {len(pages)} pages, {char_count} chars written to {out_path.name}")

    # Quick verify
    remaining_bad = sum(
        1 for p in pages
        for c in p['text']
        if 0xF700 <= ord(c) <= 0xF7FF
    )
    print(f"  -> PUA chars remaining: {remaining_bad}")

print("\nDone.")
