/* knowledge.js — ชั้นความรู้: normalize/ค้นหา, สารบัญ, หัวข้อ, ดัชนีธรรม
   ทำงานบน pageData ที่ generate ไว้แล้ว ไม่แตะไฟล์ใน /web/data */

/* ───────────── Thai text normalization ─────────────
   แก้ปัญหาจาก PDF extraction:
   - เลขไทย ↔ เลขอารบิก          → แปลงเป็นอารบิกทั้งคู่
   - กํา (นิคหิต+า) ↔ กำ (สระอำ)  → ทั้งคู่ยุบเป็น "า" (ตัดนิคหิต)
   - "ท า" ↔ "ทำ" (ช่องว่างแทรก)  → ตัด whitespace ทั้งหมดออก
   - "นั ้น" ↔ "นั้น"               → ตัด whitespace แก้วรรณยุกต์หลุด
   การยุบ ำ→า ทำให้ค้น "ทำ" เจอ "ท า" ได้ (ยอม fuzzy ขึ้นเล็กน้อยเพื่อ recall) */

const THAI_DIGITS = "๐๑๒๓๔๕๖๗๘๙";

function normalizeChar(ch) {
  const thaiIndex = THAI_DIGITS.indexOf(ch);
  if (thaiIndex >= 0) return String(thaiIndex);
  if (ch === "ํ") return ""; // นิคหิต ◌ํ
  if (ch === "ำ") return "า"; // ำ → า
  if (/[\s​﻿]/.test(ch)) return "";
  return ch.toLowerCase();
}

export function normalizeQuery(str) {
  let out = "";
  for (const ch of str) out += normalizeChar(ch);
  return out;
}

/* สร้างข้อความ normalized พร้อม map กลับไป offset เดิม (ใช้ highlight ต้นฉบับ) */
function buildNorm(text) {
  let norm = "";
  const map = [];
  for (let i = 0; i < text.length; i += 1) {
    const replaced = normalizeChar(text[i]);
    for (let k = 0; k < replaced.length; k += 1) {
      norm += replaced[k];
      map.push(i);
    }
  }
  return { norm, map };
}

const normCache = new WeakMap();

function getNorm(page) {
  let entry = normCache.get(page);
  if (!entry) {
    entry = buildNorm(page.text || "");
    normCache.set(page, entry);
  }
  return entry;
}

/* ตัวอักษรไทยที่ "ต่อคำ" ได้ (พยัญชนะ สระ วรรณยุกต์) — ใช้เช็คขอบเขตคำในโหมด exact */
const THAI_WORD_CHAR = /[ก-ฮะ-ฺเ-๎]/;

function isWordBoundary(text, start, end) {
  const before = text[start - 1];
  const after = text[end];
  return !(before && THAI_WORD_CHAR.test(before)) && !(after && THAI_WORD_CHAR.test(after));
}

/* คืน [start, end) ใน "ข้อความต้นฉบับ" ของทุกตำแหน่งที่พบ query
   exact: ตัดตำแหน่งที่คำติดอยู่ในคำอื่น เช่น "มรรค" ใน "อริยมรรค"
   (ข้อจำกัด: ช่องว่างแทรกจาก PDF กลางคำ เช่น "อริย มรรค" จะผ่านเช็ค exact) */
export function findMatches(page, query, limit = 50, exact = false) {
  const nq = normalizeQuery(query);
  if (!nq) return [];
  const { norm, map } = getNorm(page);
  const text = page.text || "";
  const ranges = [];
  let from = 0;
  while (ranges.length < limit) {
    const at = norm.indexOf(nq, from);
    if (at < 0) break;
    const range = [map[at], map[at + nq.length - 1] + 1];
    if (!exact || isWordBoundary(text, range[0], range[1])) ranges.push(range);
    from = at + nq.length;
  }
  return ranges;
}

export function pageHasMatch(page, normQuery) {
  return getNorm(page).norm.includes(normQuery);
}

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  })[ch]);
}

/* ไฮไลต์ข้อความต้นฉบับด้วย ranges จาก normalized search */
export function highlightText(text, query) {
  if (!query) return escapeHtml(text);
  const ranges = findMatches({ text }, query, 500);
  if (!ranges.length) return escapeHtml(text);
  let out = "";
  let cursor = 0;
  for (const [start, end] of ranges) {
    if (start < cursor) continue;
    out += escapeHtml(text.slice(cursor, start));
    out += `<mark>${escapeHtml(text.slice(start, end))}</mark>`;
    cursor = end;
  }
  out += escapeHtml(text.slice(cursor));
  return out;
}

/* ตัด context รอบ match แรก (ทำงานบน offset ต้นฉบับ ไฮไลต์ซ้ำได้) */
export function makeSnippet(page, query, before = 60, after = 110) {
  const text = page.text || "";
  const ranges = findMatches(page, query, 1);
  if (!ranges.length) return text.slice(0, before + after);
  const [start, end] = ranges[0];
  const from = Math.max(0, start - before);
  const to = Math.min(text.length, end + after);
  return `${from > 0 ? "…" : ""}${text.slice(from, to)}${to < text.length ? "…" : ""}`;
}

/* ───────────── สารบัญ (TOC) ─────────────
   headings ใน pageData คือ "บรรทัดเน้น" จาก PDF เกือบทุกหน้า ไม่ใช่หัวข้อจริงทั้งหมด
   จึงแยก 2 ชั้น: หัวข้อหลัก (ตาม pattern โครงสร้างคัมภีร์) กับหัวข้อรายหน้า (บรรทัดแรกของหน้า) */

const MAJOR_RULES = [
  { type: "สารบัญ", re: /^สารบัญ/ },
  { type: "มาติกา", re: /^(มาติกา|[๐-๙0-9]+\.\s*มาติกา)/ },
  { type: "บาลี", re: /^บาลี\s/ },
  { type: "วาระ", re: /^วาระที่\s*[๐-๙0-9]/ },
  { type: "ภาณวาระ", re: /ภาณวาระ\s*(\(เล่ม\s*[๐-๙0-9]+\))?\s*$/ },
  { type: "นิทเทส", re: /นิทเทส(ที่\s*[๐-๙0-9]+|วาระ)?\s*$/ },
  { type: "กถา", re: /กถาที่\s*[๐-๙0-9]/ },
  { type: "ข้อบาลี", re: /^\[(เทียบ|[๐-๙0-9]+\])/ },
  { type: "ข้อธรรม", re: /^[๐-๙0-9]+\.\s+\S.*ธมฺมา\s+(ปหาตพฺพ|ภาเวตพฺพ|สจฺฉิกาตพฺพ|อภิญฺเญยฺ|ปริญฺเญยฺ)/ },
  { type: "จบ", re: /^จบ\s?\S/ },
];

function classifyMajor(heading) {
  const h = heading.trim();
  if (h.length > 80) return null;
  if (h.includes("~") && h.length > 45) return null;
  for (const rule of MAJOR_RULES) {
    if (rule.re.test(h)) return rule.type;
  }
  return null;
}

/* ความเชื่อมั่นของหัวข้อหลักจาก heuristic — ช่วยจัดลำดับการตรวจมือ */
const STRONG_TYPES = new Set(["สารบัญ", "ภาณวาระ", "วาระ", "ข้อบาลี", "บาลี"]);

export function headingConfidence(entry) {
  if (entry.added) return "กำหนดเอง";
  if (STRONG_TYPES.has(entry.type) && entry.title.length <= 60) return "สูง";
  if (!entry.title.includes("~") && entry.title.length <= 60) return "สูง";
  return "กลาง";
}

/* merge override จาก /web/overrides/toc-overrides.json ทับผล heuristic
   remove: จับคู่ด้วย page + title ขึ้นต้น (title ว่าง = ลบทุกหัวข้อหลักของหน้านั้น)
   add: เพิ่มหัวข้อหลักใหม่ */
function applyTocOverrides(entries, override) {
  if (!override) return entries;
  let out = entries;
  if (Array.isArray(override.remove) && override.remove.length) {
    out = out.filter((entry) => !(entry.major && override.remove.some((r) =>
      r.page === entry.page && (!r.title || entry.title.startsWith(r.title))
    )));
  }
  if (Array.isArray(override.add) && override.add.length) {
    const adds = override.add
      .filter((a) => Number(a.page) >= 1)
      .map((a) => ({
        page: Number(a.page),
        title: String(a.title || `หน้า ${a.page}`).trim(),
        type: a.type || "หัวข้อ",
        major: true,
        added: true,
      }));
    out = out.concat(adds).sort((a, b) => a.page - b.page);
  }
  return out;
}

/* TOC: รวมหัวข้อหลักทุกตัว + หัวข้อนำของแต่ละหน้า (สำหรับโหมด "ทุกหน้า") */
export function buildToc(book, override = null) {
  const entries = [];
  let lastTitle = "";
  for (const page of book.pageData) {
    const headings = Array.isArray(page.headings) ? page.headings : [];
    let pageHasMajor = false;
    for (const heading of headings) {
      const type = classifyMajor(heading);
      if (type) {
        const title = heading.trim();
        if (title !== lastTitle) {
          entries.push({ page: page.number, title, type, major: true });
          lastTitle = title;
          pageHasMajor = true;
        }
      }
    }
    if (!pageHasMajor && headings.length) {
      const title = headings[0].trim();
      if (title && title !== lastTitle) {
        entries.push({ page: page.number, title, type: "หน้า", major: false });
        lastTitle = title;
      }
    }
  }
  return applyTocOverrides(entries, override);
}

/* ───────────── หัวข้อ (sections) ─────────────
   conservative: หัวข้อหลักเป็นจุดเริ่ม จบก่อนหัวข้อหลักถัดไป
   ถ้าเล่มไม่มีหัวข้อหลักที่หน้า ๑ เพิ่ม "ตอนต้น" คลุมช่วงแรกให้ครบ */

const SECTION_TYPES = new Set(["สารบัญ", "มาติกา", "บาลี", "วาระ", "ภาณวาระ", "นิทเทส", "กถา", "ข้อบาลี", "ข้อธรรม"]);

export function buildSections(book, override = null) {
  const majors = buildToc(book, override)
    .filter((entry) => entry.major && (entry.added || SECTION_TYPES.has(entry.type)));

  // หัวข้อหลักซ้อนหน้าเดียวกันหลายตัว → เก็บตัวแรกของหน้า
  const starts = [];
  for (const entry of majors) {
    if (!starts.length || starts[starts.length - 1].page !== entry.page) starts.push(entry);
  }

  if (!starts.length || starts[0].page > 1) {
    starts.unshift({ page: 1, title: "ตอนต้นของเล่ม", type: "หน้า" });
  }

  return starts.map((entry, index) => ({
    index,
    title: entry.title,
    type: entry.type,
    startPage: entry.page,
    endPage: index + 1 < starts.length ? starts[index + 1].page - 1 : book.pages,
  }));
}

/* ───────────── diagnostics สำหรับ extraction ───────────── */

export const LONG_SECTION_PAGES = 30;

/* รูปแบบช่องว่างแทรกกลางคำที่ normalize แล้วแต่ยังบ่งชี้คุณภาพ extraction:
   พยัญชนะ + ช่องว่าง + สระบน/ล่าง/วรรณยุกต์ เช่น "ป ิ ด", "นั ้น" */
const SPLIT_ISSUE_RE = /[ก-ฮ]\s+[ัิ-ฺ็-๎]/g;

export function diagnoseBook(book, override = null) {
  const toc = buildToc(book, override);
  const sections = buildSections(book, override);
  const majors = toc.filter((e) => e.major);

  let totalHeadings = 0;
  const shortPages = [];
  let splitIssues = 0;
  const splitPages = [];
  for (const page of book.pageData) {
    totalHeadings += Array.isArray(page.headings) ? page.headings.length : 0;
    const text = page.text || "";
    if (text.trim().length < 80) shortPages.push(page.number);
    const found = text.match(SPLIT_ISSUE_RE);
    if (found) {
      splitIssues += found.length;
      if (splitPages.length < 8) splitPages.push(page.number);
    }
  }

  const typeDist = {};
  for (const entry of majors) typeDist[entry.type] = (typeDist[entry.type] || 0) + 1;

  const sized = sections.map((s) => ({ ...s, length: s.endPage - s.startPage + 1 }));
  const byLength = [...sized].sort((a, b) => b.length - a.length);

  return {
    pages: book.pages,
    totalHeadings,
    majorCount: majors.length,
    sectionCount: sections.length,
    typeDist,
    longest: byLength[0] || null,
    shortest: byLength[byLength.length - 1] || null,
    longSections: sized.filter((s) => s.length > LONG_SECTION_PAGES),
    shortPages,
    splitIssues,
    splitPages,
  };
}

/* ───────────── ดัชนีธรรม ───────────── */

export const KNOWLEDGE_INDEX = [
  {
    category: "ญาณ",
    terms: ["ญาณ", "สุตมยญาณ", "สีลมยญาณ", "สมาธิภาวนามยญาณ", "ธรรมฐิติญาณ", "สัมมสนญาณ",
      "อุทยัพพยานุปัสนาญาณ", "วิปัสสนาญาณ", "โคตรภูญาณ", "มรรคญาณ", "ผลญาณ", "ปฏิสัมภิทาญาณ"],
  },
  {
    category: "หมวดนิทเทส",
    terms: ["อภิญเญยยะ", "ปริญเญยยะ", "ปหาตัพพะ", "ภาเวตัพพะ", "สัจฉิกาตัพพะ"],
  },
  {
    category: "อริยสัจและมรรคผล",
    terms: ["อริยสัจ", "ทุกข์", "สมุทัย", "นิโรธ", "มรรค", "อริยมรรค", "ผล", "นิพพาน", "วิมุตติ"],
  },
  {
    category: "กิเลสที่ควรละ",
    terms: ["อวิชชา", "ตัณหา", "ภวตัณหา", "อนุสัย", "นิวรณ์", "อาสวะ", "มิจฉาทิฏฐิ"],
  },
  {
    category: "ขันธ์ อายตนะ ธาตุ",
    terms: ["ขันธ์", "อายตนะ", "ธาตุ", "รูป", "เวทนา", "สัญญา", "สังขาร", "วิญญาณ"],
  },
  {
    category: "ภาวนาและอินทรีย์",
    terms: ["สมาธิ", "วิปัสสนา", "สติปัฏฐาน", "อินทรีย์", "พละ", "โพชฌงค์", "อิทธิบาท",
      "ฉันทะ", "วิริยะ", "จิตตะ", "วิมังสา", "ปัญญา", "ศรัทธา", "สติ"],
  },
];

export const TERM_INDEX_VERSION = "v2";

/* รวมคำจาก KNOWLEDGE_INDEX กับ extraTerms ใน override → [{category, term, variants}] */
export function resolveTerms(termConfig = {}) {
  const aliases = termConfig.aliases || {};
  const extra = termConfig.extraTerms || {};
  const out = [];
  for (const group of KNOWLEDGE_INDEX) {
    const terms = [...group.terms, ...(Array.isArray(extra[group.category]) ? extra[group.category] : [])];
    for (const term of terms) {
      out.push({
        category: group.category,
        term,
        variants: [term, ...(Array.isArray(aliases[term]) ? aliases[term] : [])],
      });
    }
  }
  return out;
}

/* นับจำนวนหน้าที่พบแต่ละคำ แยกตามเล่ม ทั้งแบบกว้าง (substring) และเฉพาะคำโดด (exact)
   + snippet ตัวอย่างแรก | loadBook: (slug) => Promise<book> */
export async function buildTermIndex(catalog, loadBook, onProgress, termConfig = {}) {
  const resolved = resolveTerms(termConfig);
  const normVariants = resolved.map((r) => r.variants.map((v) => normalizeQuery(v)));
  const index = Object.fromEntries(resolved.map((r) => [r.term, {
    total: 0, perBook: {}, totalExact: 0, perBookExact: {}, snippet: "", snippetRef: null,
  }]));

  for (let b = 0; b < catalog.books.length; b += 1) {
    const meta = catalog.books[b];
    const book = await loadBook(meta.slug);
    for (const page of book.pageData) {
      const { norm } = getNorm(page);
      for (let t = 0; t < resolved.length; t += 1) {
        const hitVariant = resolved[t].variants.find((v, i) => norm.includes(normVariants[t][i]));
        if (hitVariant === undefined) continue;
        const entry = index[resolved[t].term];
        entry.total += 1;
        entry.perBook[meta.slug] = (entry.perBook[meta.slug] || 0) + 1;
        const exactHit = resolved[t].variants.some((v) => findMatches(page, v, 4, true).length > 0);
        if (exactHit) {
          entry.totalExact += 1;
          entry.perBookExact[meta.slug] = (entry.perBookExact[meta.slug] || 0) + 1;
        }
        if (!entry.snippet) {
          entry.snippet = makeSnippet(page, hitVariant, 40, 90).replace(/\s+/g, " ");
          entry.snippetRef = { slug: meta.slug, page: page.number };
        }
      }
    }
    if (onProgress) onProgress(b + 1, catalog.books.length);
    await new Promise((resolve) => setTimeout(resolve, 0)); // คืน main thread ให้ UI
  }
  return index;
}
