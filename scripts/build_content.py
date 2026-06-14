from __future__ import annotations

import json
import re
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "pdf"
DATA_DIR = ROOT / "web" / "data"

BOOK_NOTES = {
    1: "มาติกาและญาณุทเทส เหมาะสำหรับใช้เป็นแผนที่ภาพรวมของญาณ ๗๓",
    2: "สุตมยญาณ อภิญเญยยนิทเทส ปฐมภาณวาระ มีบาลีและคำอธิบายสลับกัน",
    3: "อภิญเญยยนิทเทส ทุติยภาณวาระ ว่าด้วยธรรม ๓๑ ในขณะแห่งอริยมรรค",
    4: "ปริญเญยยนิทเทสที่ ๒ เนื้อหาอธิบายต่อเนื่องและมีหัวข้อธรรมจำนวนมาก",
    5: "ปหาตัพพนิทเทสตอนต้น ว่าด้วยธรรมที่ควรละ",
    6: "ปหาตัพพนิทเทส ทุติยภาณวาระ เล่ม ๑ เป็นคำอธิบายยาวต่อเนื่อง",
    7: "ปหาตัพพะ ทติยะ ภาค ๒ ต่อเนื่องเรื่องอิทธิบาทและมรรคภาวนา",
    8: "ปหาตัพพะ ทุติยะ ภาค ๓ จบ ว่าด้วยคุณธรรมและโลกุตตรธรรม",
}


def thai_digit_to_int(text: str) -> int | None:
    digits = "๐๑๒๓๔๕๖๗๘๙"
    found = re.search(r"[๑๒๓๔๕๖๗๘๙]", text)
    if not found:
        return None
    return digits.index(found.group(0))


def slug_for(path: Path, fallback: int) -> str:
    number = thai_digit_to_int(path.stem) or fallback
    return f"book-{number:02d}"


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)

    replacements = {
        "ท า": "ทำ",
        "จ า": "จำ",
        "ส า": "สำ",
        "ก า": "กำ",
        "ด า": "ดำ",
        "น า": "นำ",
        "ค า": "คำ",
        "อ า": "อำ",
        "บ า": "บำ",
        "ล า": "ลำ",
        "ช า": "ชำ",
        "ร า": "รำ",
        "ต า": "ตำ",
        "เป ็ น": "เป็น",
        "เห ็ น": "เห็น",
        "เช ่ น": "เช่น",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)

    text = repair_thai_pdf_spacing(text)

    return text.strip()


def repair_thai_pdf_spacing(text: str) -> str:
    """Fix conservative Thai spacing artifacts from PDF text extraction."""
    phrase_replacements = {
        "\u0e40\u0e1b\u0e47 \u0e19": "\u0e40\u0e1b\u0e47\u0e19",  # เป็ น
        "\u0e40\u0e2b\u0e47 \u0e19": "\u0e40\u0e2b\u0e47\u0e19",  # เห็ น
        "\u0e40\u0e0a\u0e48 \u0e19": "\u0e40\u0e0a\u0e48\u0e19",  # เช่ น
        "\u0e25 \u0e49\u0e32": "\u0e25\u0e49\u0e33",              # ล ้า -> ล้ำ
        "\u0e04\u0e23\u0e2d\u0e1a\u0e07 \u0e32": "\u0e04\u0e23\u0e2d\u0e1a\u0e07\u0e33",  # ครอบง า
        "\u0e23 \u0e48\u0e32\u0e44\u0e23": "\u0e23\u0e48\u0e33\u0e44\u0e23",              # ร ่าไร
    }
    for source, target in phrase_replacements.items():
        text = text.replace(source, target)

    # Spaces before Thai combining marks cannot be word boundaries.
    text = re.sub(
        r"([\u0E01-\u0E3A\u0E40-\u0E44])\s+([\u0E31\u0E34-\u0E3A\u0E47-\u0E4E])",
        r"\1\2",
        text,
    )
    # Tone mark split from sara aa, e.g. กล้ า -> กล้า.
    text = re.sub(r"([\u0E48-\u0E4B])\s+(\u0E32)", r"\1\2", text)
    # Normalize decomposed sara am from PDF extraction, e.g. ลํ้า -> ล้ำ.
    text = re.sub(
        r"([\u0E01-\u0E2E])\u0E4D([\u0E48-\u0E4B]?)\u0E32",
        lambda match: f"{match.group(1)}{match.group(2)}\u0E33",
        text,
    )

    return text


def make_excerpt(text: str, limit: int = 180) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def detect_headings(text: str) -> list[str]:
    headings: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or len(line) > 90:
            continue
        if re.match(r"^(\[?\d+\]?|[๑-๙][๐-๙]*)[.)]?\s+", line):
            headings.append(line)
        elif any(word in line for word in ("นิทเทส", "ญาณ", "ภาณวาระ", "สารบัญ", "มาติกา")) and len(line) <= 70:
            headings.append(line)
        if len(headings) >= 6:
            break
    return headings


def build() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    catalog = {"title": "ปฏิสัมภิทามรรค", "books": []}

    for idx, pdf_path in enumerate(pdfs, start=1):
        slug = slug_for(pdf_path, idx)
        number = thai_digit_to_int(pdf_path.stem) or idx
        reader = PdfReader(str(pdf_path))
        pages = []
        char_count = 0
        for page_index, page in enumerate(reader.pages, start=1):
            raw = page.extract_text() or ""
            text = normalize_text(raw)
            char_count += len(text)
            pages.append(
                {
                    "number": page_index,
                    "text": text,
                    "excerpt": make_excerpt(text),
                    "headings": detect_headings(text),
                }
            )

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
        catalog["books"].append(book)

        with (DATA_DIR / f"{slug}.json").open("w", encoding="utf-8") as f:
            json.dump({**book, "pageData": pages}, f, ensure_ascii=False, separators=(",", ":"))

    catalog["totalPages"] = sum(book["pages"] for book in catalog["books"])
    catalog["totalChars"] = sum(book["chars"] for book in catalog["books"])
    with (DATA_DIR / "catalog.json").open("w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print(f"Built {len(catalog['books'])} books, {catalog['totalPages']} pages.")


if __name__ == "__main__":
    build()
