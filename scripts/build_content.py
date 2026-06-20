from __future__ import annotations

import json
import re
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "web" / "pdf"
DATA_DIR = ROOT / "web" / "data"

# ── Book-10: PUA chars (U+F700–U+F7FF) จากฟอนต์ไทยเก่า Windows encoding ──────
# แต่ละ PUA char map กลับเป็น Thai Unicode ที่ถูกต้อง
_PUA_MAP: dict[str, str] = {
    "": "•",   # bullet
    "": "ิ",   # sara i (alt position)
    "": "ี",   # sara ii (alt position)
    "": "ึ",   # sara ue (alt position)
    "": "ื",   # sara uee (alt position)
    "": "่",   # mai ek (alt position)
    "": "้",   # mai tho (stacking position)
    "": "่",   # mai ek
    "": "้",   # mai tho
    "": "๊",   # mai tri
    "": "๋",   # mai chattawa
    "": "์",   # thanthakat
    "": "ํ",   # nikhahit (Pali)
    "": "ั",   # sara a
    "": "ฺ",   # phinthu (Pali)
    "": "็",   # maitaikhu
    "": "่",   # mai ek (stacking with sara ii)
    "": "้",   # mai tho (stacking)
    "": "่",
    "": "ั",
}

_PUA_RE = re.compile("|".join(re.escape(k) for k in _PUA_MAP))


def fix_pua_encoding(text: str) -> str:
    """แก้ PUA chars จากฟอนต์ไทย Windows เก่า (book-10)."""
    return _PUA_RE.sub(lambda m: _PUA_MAP[m.group()], text)


# ── Book-09: ASCII ทำหน้าที่เป็น Thai diacritics จาก font encoding ──────────
# ใช้เฉพาะเมื่อ ASCII char ปรากฏอยู่หลัง Thai character (lookbehind)
# แต่ละ ASCII char map เป็น Thai combining mark
_ASCII_DIACRITIC_MAP: dict[str, str] = {
    "=": "่",   # mai ek (most common, 3677x)
    "9": "้",   # mai tho (2197x)
    "H": "็",   # maitaikhu (806x)
    "M": "ั",   # sara a (367x)
    "b": "์",   # thanthakat (271x)
    "*": "่",   # mai ek alt (148x)
    "<": "้",   # mai tho alt (132x)
    "w": "ั",   # sara a alt (110x)
    "r": "ิ",   # sara i (49x)
    "P": "็",   # maitaikhu alt (45x)
    "6": "็",   # maitaikhu alt (42x)
    "R": "้",   # mai tho alt (38x)
    "Q": "่",   # mai ek alt (30x)
    "5": "ั",   # sara a alt (27x)
    ":": "ั",   # sara a alt (27x)
    "A": "ัฏ",  # sara a + ฏ consonant ligature (สติปัฏฐาน, อัฏฐ etc.)
    "7": "็",   # maitaikhu alt (20x)
    "S": "้",   # mai tho alt (19x)
    "u": "้",   # mai tho alt (18x)
    "o": "่",   # mai ek alt (17x)
    "Y": "์",   # thanthakat alt
    "#": "่",   # mai ek alt
    "'": "่",   # mai ek alt (apostrophe)
    "W": "ั",   # sara a alt
    "@": "",    # noise char — remove
    # ── ชุดที่ 2: พบจากการวิเคราะห์ซ้ำ ──────────────────────────────────
    "O": "์",   # thanthakat (องค์, ชฌงค์)
    "N": "์",   # thanthakat alt
    "X": "ั",   # sara a (วิปัสสนา)
    "a": "ั",   # sara a alt
    "G": "ั",   # sara a alt
    "E": "ั",   # sara a alt (โสตาปัตติ)
    "$": "ั",   # sara a alt
    "L": "ิ",   # sara i (ปิติ)
    "y": "ิ",   # sara i alt (เปิด)
    "i": "ิ",   # sara i alt
    "d": "ิ",   # sara i alt
    "h": "ิ",   # sara i alt
    ">": "้",   # mai tho (ด้วย)
    "3": "้",   # mai tho alt
    "e": "้",   # mai tho alt (ฟุ้ง)
    "_": "้",   # mai tho alt
    "4": "้",   # mai tho alt
    "?": "็",   # maitaikhu alt (เป็น)
    "8": "็",   # maitaikhu alt
    "c": "่",   # mai ek alt
    "I": "่",   # mai ek alt (ร่วม)
    "2": "่",   # mai ek alt
}

_THAI_BLOCK = "฀-๿"
# match iff immediately preceded by a Thai character
_ASCII_DIAC_RE = re.compile(
    f"(?<=[{_THAI_BLOCK}])({'|'.join(re.escape(k) for k in _ASCII_DIACRITIC_MAP)})"
)


def fix_ascii_diacritics(text: str) -> str:
    """แก้ ASCII chars ที่ถูก font เก่า map ไว้แทน Thai diacritics (book-09)."""
    # @A compound: @ is noise, A = ัฏ — ต้องจัดการก่อน lookbehind จะทำงาน
    text = re.sub(r'(?<=[฀-๿])@A', 'ัฏ', text)
    text = _ASCII_DIAC_RE.sub(lambda m: _ASCII_DIACRITIC_MAP[m.group(1)], text)
    return _fix_book09_wrong_mai(text)


def _fix_book09_wrong_mai(text: str) -> str:
    """แก้ ็ ที่ถูก map ผิดจาก H — ใน context ที่ควรเป็น ่ หรือ ั."""
    # [พยัญชนะ]็า ไม่มีใน Thai จริง — ควรเป็น ่า
    text = re.sub(r'(?<=[ก-ฮ])็า', '่า', text)
    # สระ ู/ุ + ็ ไม่มี — ควรเป็น ่ (อยู่, กลุ่ม ฯลฯ)
    text = text.replace('ู็', 'ู่')
    text = text.replace('ุ็', 'ุ่')
    # ไม็ → ไม่ (ไม่ = not, common word)
    text = text.replace('ไม็', 'ไม่')
    # ล็ว → ล่ว (ล่วง)
    text = text.replace('ล็ว', 'ล่ว')
    # ป็ส → ปัส (วิปัสสนา)
    text = text.replace('ป็ส', 'ปัส')
    return text


BOOK_NOTES = {
    1: "มาติกาและญาณุทเทส เหมาะสำหรับใช้เป็นแผนที่ภาพรวมของญาณ ๗๓",
    2: "สุตมยญาณ อภิญเญยยนิทเทส ปฐมภาณวาระ มีบาลีและคำอธิบายสลับกัน",
    3: "อภิญเญยยนิทเทส ทุติยภาณวาระ ว่าด้วยธรรม ๓๑ ในขณะแห่งอริยมรรค",
    4: "ปริญเญยยนิทเทสที่ ๒ เนื้อหาอธิบายต่อเนื่องและมีหัวข้อธรรมจำนวนมาก",
    5: "ปหาตัพพนิทเทสตอนต้น ว่าด้วยธรรมที่ควรละ",
    6: "ปหาตัพพนิทเทส ทุติยภาณวาระ เล่ม ๑ เป็นคำอธิบายยาวต่อเนื่อง",
    7: "ปหาตัพพะ ทติยะ ภาค ๒ ต่อเนื่องเรื่องอิทธิบาทและมรรคภาวนา",
    8: "ปหาตัพพะ ทุติยะ ภาค ๓ จบ ว่าด้วยคุณธรรมและโลกุตตรธรรม",
    9: "ภาเวตัพพนิทเทส ว่าด้วยธรรมที่ควรเจริญ ตอนต้น",
    10: "ภาเวตัพพนิทเทส ว่าด้วยธรรมที่ควรเจริญ ต่อเนื่อง",
}


def thai_digit_to_int(text: str) -> int | None:
    digits = "๐๑๒๓๔๕๖๗๘๙"
    found = re.search(r"[๐-๙]+", text)
    if not found:
        return None
    return int("".join(str(digits.index(c)) for c in found.group(0)))


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
    pdfs = sorted(PDF_DIR.glob("*.pdf"), key=lambda p: thai_digit_to_int(p.stem) or 0)
    catalog = {"title": "ปฏิสัมภิทามรรค", "books": []}

    for idx, pdf_path in enumerate(pdfs, start=1):
        slug = slug_for(pdf_path, idx)
        number = thai_digit_to_int(pdf_path.stem) or idx
        reader = PdfReader(str(pdf_path))
        pages = []
        char_count = 0
        for page_index, page in enumerate(reader.pages, start=1):
            raw = page.extract_text() or ""
            # แก้ encoding จากฟอนต์เก่า ก่อน normalize
            if number == 10:
                raw = fix_pua_encoding(raw)
            elif number == 9:
                raw = fix_ascii_diacritics(raw)
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
