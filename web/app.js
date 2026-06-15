/* ปฏิสัมภิทามรรค — ห้องสมุดธรรมดิจิทัล (static SPA)
   ชั้นความรู้ (สารบัญ/หัวข้อ/ดัชนี/ค้นหา normalized) อยู่ใน knowledge.js */

import {
  escapeHtml,
  findMatches,
  normalizeQuery,
  pageHasMatch,
  highlightText,
  makeSnippet,
  buildToc,
  buildSections,
  KNOWLEDGE_INDEX,
  TERM_INDEX_VERSION,
  buildTermIndex,
  resolveTerms,
  headingConfidence,
  diagnoseBook,
  LONG_SECTION_PAGES,
} from "./knowledge.js?v=editorial-v2";

const LS = {
  theme: "psm.theme",
  fontSize: "psm.fontSize",
  progress: "psm.progress",
  bookmarks: "psm.bookmarks",
  annotations: "psm.annotations",
  recentSearches: "psm.recentSearches",
  recentSections: "psm.recentSections",
  termIndex: "psm.termIndex",
  admin: "psm_admin",
  editorial: "psm.editorial",
  edPopup: "psm.edPopup",
  edLastExport: "psm.edLastExport",
  edLastPublish: "psm.edLastPublish",
};

/* รหัสผ่านโหมดแอดมิน — เว็บ static เปิดเผยซอร์สได้ จึงเป็น "ประตูเบา" กันผู้อ่านทั่วไป
   ไม่ใช่ระบบความปลอดภัยจริง เจ้าของเว็บแก้ค่านี้ได้ตามต้องการ */
const ADMIN_PASSCODE = "patisambhida-2569";
/* ปลายทาง publish (Cloudflare Worker) — แก้ค่านี้ค่าเดียวเพื่อย้าย endpoint
   ต้องลงท้ายด้วย /api/publish (worker route ตามนั้น) */
const PUBLISH_ENDPOINT = "https://patisambhida-publish.maxhot23.workers.dev/api/publish";

const state = {
  catalog: null,
  cache: new Map(),
  view: "library",
  slug: null,
  page: 1,
  book: null,
  highlightQuery: "",
  fontSize: clampFont(Number(localStorage.getItem(LS.fontSize)) || 20),

  paletteOpen: false,
  paletteScope: "all", // all | current | bookmarks
  paletteFilters: new Set(),
  paletteActive: 0,
  searchToken: 0,

  tocOpen: false,
  tocMode: "major", // major | all | review
  tocCache: new Map(),

  sectionsCache: new Map(),
  section: null,

  termIndex: null,
  indexMode: "broad", // broad | exact

  // override จาก /web/overrides (โหลดตอน init ถ้ามี)
  overrides: { toc: {}, tocRaw: {}, terms: {} },
  // หัวข้อที่ผู้ตรวจ "ตัดออก" ชั่วคราวในโหมดตรวจสารบัญ (ยังไม่บันทึกเป็นไฟล์)
  reviewRemovals: new Map(),

  qualityCache: null,
  pendingSelection: null,
  pendingRemoveIds: [], // id ของ editorial ที่ selection ปัจจุบันทับ (ใช้ปุ่มลบรูปแบบ)
  pendingRemoveAnnIds: [], // id ของไฮไลท์ผู้อ่านที่ selection ปัจจุบันทับ
  _selChangeTimer: null, // debounce สำหรับ selectionchange บน touch device

  // โหมดแอดมิน + ชั้นแก้ไข editorial (global, แสดงต่อผู้อ่านทุกคน)
  admin: false,
  editorialFile: {}, // เนื้อหาจาก editorial-overrides.json (baseline)
};

const $ = (sel) => document.querySelector(sel);

const els = {
  appnavLinks: document.querySelectorAll("[data-nav]"),
  views: {
    library: $("#viewLibrary"),
    reader: $("#viewReader"),
    bookmarks: $("#viewBookmarks"),
    notes: $("#viewNotes"),
    map: $("#viewMap"),
    section: $("#viewSection"),
    quality: $("#viewQuality"),
  },
  qualityBody: $("#qualityBody"),
  libraryStats: $("#libraryStats"),
  continueStrip: $("#continueStrip"),
  shelf: $("#shelf"),
  heroStart: $("#heroStart"),
  heroContinue: $("#heroContinue"),
  heroStatBooks: $("#heroStatBooks"),
  heroStatPages: $("#heroStatPages"),
  heroStatChars: $("#heroStatChars"),

  readerKicker: $("#readerKicker"),
  readerTitle: $("#readerTitle"),
  pageHeading: $("#pageHeading"),
  pagePct: $("#pagePct"),
  pageText: $("#pageText"),
  pageSource: $("#pageSource"),
  pageInput: $("#pageInput"),
  pageTotal: $("#pageTotal"),
  pageSlider: $("#pageSlider"),
  prevPage: $("#prevPage"),
  nextPage: $("#nextPage"),
  pdfLink: $("#pdfLink"),
  bookmarkBtn: $("#bookmarkBtn"),
  notesBtn: $("#notesBtn"),
  citeBtn: $("#citeBtn"),
  focusBtn: $("#focusBtn"),
  focusExit: $("#focusExit"),
  fontUp: $("#fontUp"),
  fontDown: $("#fontDown"),

  tocBtn: $("#tocBtn"),
  tocBackdrop: $("#tocBackdrop"),
  tocClose: $("#tocClose"),
  tocBookTitle: $("#tocBookTitle"),
  tocFilter: $("#tocFilter"),
  tocModeMajor: $("#tocModeMajor"),
  tocModeAll: $("#tocModeAll"),
  tocModeReview: $("#tocModeReview"),
  tocList: $("#tocList"),

  sectionBack: $("#sectionBack"),
  sectionKicker: $("#sectionKicker"),
  sectionBookTitle: $("#sectionBookTitle"),
  sectionType: $("#sectionType"),
  sectionTitle: $("#sectionTitle"),
  sectionRange: $("#sectionRange"),
  sectionBody: $("#sectionBody"),
  sectionPrev: $("#sectionPrev"),
  sectionNext: $("#sectionNext"),
  sectionCiteBtn: $("#sectionCiteBtn"),
  sectionPdfLink: $("#sectionPdfLink"),
  sectionFontUp: $("#sectionFontUp"),
  sectionFontDown: $("#sectionFontDown"),

  bookmarkStats: $("#bookmarkStats"),
  bookmarkList: $("#bookmarkList"),
  notesStats: $("#notesStats"),
  notesList: $("#notesList"),
  exportNotesBtn: $("#exportNotesBtn"),
  importNotesInput: $("#importNotesInput"),
  deleteAllHighlightsBtn: $("#deleteAllHighlightsBtn"),
  mapBody: $("#mapBody"),

  themeToggle: $("#themeToggle"),
  searchTrigger: $("#searchTrigger"),
  paletteBackdrop: $("#paletteBackdrop"),
  paletteInput: $("#paletteInput"),
  paletteClose: $("#paletteClose"),
  paletteFilters: $("#paletteFilters"),
  paletteResults: $("#paletteResults"),

  selectionPopover: $("#selectionPopover"),
  selHeader: $("#selHeader"),
  selTitle: $("#selTitle"),
  selMinBtn: $("#selMinBtn"),
  selResize: $("#selResize"),
  selRestoreBtn: $("#selRestoreBtn"),
  highlightSelectionBtn: $("#highlightSelectionBtn"),
  removeHighlightBtn: $("#removeHighlightBtn"),
  noteSelectionBtn: $("#noteSelectionBtn"),
  cancelSelectionBtn: $("#cancelSelectionBtn"),
  selectionNoteBox: $("#selectionNoteBox"),
  selectionNoteInput: $("#selectionNoteInput"),
  saveNoteSelectionBtn: $("#saveNoteSelectionBtn"),

  adminSelectionActions: $("#adminSelectionActions"),
  edBoldBtn: $("#edBoldBtn"),
  edItalicBtn: $("#edItalicBtn"),
  edReplaceBtn: $("#edReplaceBtn"),
  edPresets: $(".ed-presets"),
  edHeadings: $(".ed-headings"),
  edLayouts: $(".ed-layouts"),
  edRemoveRow: $("#edRemoveRow"),
  edRemoveBtn: $("#edRemoveBtn"),
  edReplaceBox: $("#edReplaceBox"),
  edReplaceInput: $("#edReplaceInput"),
  edReplaceSaveBtn: $("#edReplaceSaveBtn"),
  edImageBtn: $("#edImageBtn"),

  edImageBackdrop: $("#edImageBackdrop"),
  edImageUrl: $("#edImageUrl"),
  edImageCaption: $("#edImageCaption"),
  edImagePreviewWrap: $("#edImagePreviewWrap"),
  edImagePreview: $("#edImagePreview"),
  edImageSave: $("#edImageSave"),
  edImageCancel: $("#edImageCancel"),

  adminBar: $("#adminBar"),
  adminStatus: $("#adminStatus"),
  adminEntriesBtn: $("#adminEntriesBtn"),
  adminExportBtn: $("#adminExportBtn"),
  adminPublishBtn: $("#adminPublishBtn"),
  adminImportInput: $("#adminImportInput"),
  adminExitBtn: $("#adminExitBtn"),

  adminLoginBackdrop: $("#adminLoginBackdrop"),
  adminLoginInput: $("#adminLoginInput"),
  adminLoginCancel: $("#adminLoginCancel"),
  adminLoginSubmit: $("#adminLoginSubmit"),

  editorialBackdrop: $("#editorialBackdrop"),
  editorialClose: $("#editorialClose"),
  editorialStats: $("#editorialStats"),
  editorialStatsBox: $("#editorialStatsBox"),
  edClearPageBtn: $("#edClearPageBtn"),
  editorialList: $("#editorialList"),

  toast: $("#toast"),
};

/* ───────────── utilities ───────────── */

const thaiNum = new Intl.NumberFormat("th-TH-u-nu-thai");
const arabicNum = new Intl.NumberFormat("th-TH");

function clampFont(size) {
  return Math.min(30, Math.max(16, size || 20));
}

function readStore(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
}

function writeStore(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage เต็ม — ข้ามไป ไม่ให้แอปพัง */
  }
}

let toastTimer;
function toast(message, hint = "") {
  if (hint) {
    els.toast.innerHTML = `<span class="toast-main"></span><span class="toast-hint"></span>`;
    els.toast.querySelector(".toast-main").textContent = message;
    els.toast.querySelector(".toast-hint").textContent = hint;
    els.toast.classList.add("has-hint");
  } else {
    els.toast.textContent = message;
    els.toast.classList.remove("has-hint");
  }
  els.toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => els.toast.classList.remove("show"), hint ? 3800 : 2200);
}

async function loadJson(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`โหลดไม่สำเร็จ: ${path}`);
  return response.json();
}

async function loadBook(slug) {
  if (!state.cache.has(slug)) {
    state.cache.set(slug, loadJson(`./data/${slug}.json`, { cache: "no-cache" }));
  }
  return state.cache.get(slug);
}

function bookMeta(slug) {
  return state.catalog.books.find((book) => book.slug === slug);
}

function shortTitle(book) {
  return `เล่ม ${thaiNum.format(book.number)}`;
}

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
}

async function copyText(text, message) {
  await copyToClipboard(text);
  toast(message);
}

/* ───────────── citations ───────────── */

function pageUrl(slug, page) {
  return `${location.origin}${location.pathname}#/book/${slug}/${page}`;
}

function pageCitation(book, page) {
  return `ปฏิสัมภิทามรรค เล่ม ${thaiNum.format(book.number)}, “${book.title}”, หน้า ${thaiNum.format(page)}, ไฟล์ PDF: ${book.file}, ลิงก์: ${pageUrl(book.slug, page)}`;
}

function sectionCitation(book, section) {
  const range = section.startPage === section.endPage
    ? `หน้า ${thaiNum.format(section.startPage)}`
    : `หน้า ${thaiNum.format(section.startPage)}-${thaiNum.format(section.endPage)}`;
  return `ปฏิสัมภิทามรรค เล่ม ${thaiNum.format(book.number)}, “${book.title}”, หัวข้อ “${section.title}”, ${range}, ไฟล์ PDF: ${book.file}, ลิงก์: ${pageUrl(book.slug, section.startPage)}`;
}

/* ───────────── persistent reading state ───────────── */

function getProgress() {
  return readStore(LS.progress, {});
}

function saveProgress(slug, page, pages) {
  const progress = getProgress();
  progress[slug] = { page, pages, ts: Date.now() };
  writeStore(LS.progress, progress);
}

function getBookmarks() {
  return readStore(LS.bookmarks, []);
}

function isBookmarked(slug, page) {
  return getBookmarks().some((bm) => bm.slug === slug && bm.page === page);
}

function toggleBookmark(slug, page, snippet) {
  let bookmarks = getBookmarks();
  const exists = bookmarks.some((bm) => bm.slug === slug && bm.page === page);
  if (exists) {
    bookmarks = bookmarks.filter((bm) => !(bm.slug === slug && bm.page === page));
  } else {
    bookmarks.push({ slug, page, snippet, ts: Date.now() });
  }
  writeStore(LS.bookmarks, bookmarks);
  return !exists;
}

function getAnnotations() {
  return readStore(LS.annotations, []);
}

function writeAnnotations(items) {
  writeStore(LS.annotations, items);
}

function pageAnnotations(slug, page) {
  return getAnnotations()
    .filter((ann) => ann.slug === slug && ann.page === page)
    .sort((a, b) => a.start - b.start || a.end - b.end);
}

function addAnnotation({ slug, page, start, end, quote, note = "" }) {
  const annotations = getAnnotations();
  const id = `ann-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
  annotations.push({
    id,
    slug,
    page,
    start,
    end,
    quote,
    note: note.trim(),
    color: "gold",
    ts: Date.now(),
    updated: Date.now(),
  });
  writeAnnotations(annotations);
  return id;
}

function removeAnnotation(id) {
  writeAnnotations(getAnnotations().filter((ann) => ann.id !== id));
}

function removeAnnotationsMany(ids) {
  const set = new Set(ids);
  writeAnnotations(getAnnotations().filter((ann) => !set.has(ann.id)));
}

/* ───────────── editorial layer (admin, global) ─────────────
   เก็บแบบเดียวกับ TOC override: ไฟล์ editorial-overrides.json = baseline ที่ผู้อ่านทุกคนเห็น
   แอดมินแก้ใน localStorage (psm.editorial) เป็น overlay: entries ทับ/เพิ่ม + removed = tombstone
   แล้ว "ส่งออก Editorial" รวมเป็น JSON ไปวางในไฟล์ | offset อิง text ต้นฉบับเหมือนระบบไฮไลท์ */

/* layout overrides (Phase 1.4) — block-level จัดวาง/ระยะ ตาม preset เชิงความหมาย (ไม่มีค่าตัวเลขอิสระ) */
const LAYOUT_TYPES = new Set(["align-center", "align-left", "align-right", "indent", "spacing-top", "spacing-bottom"]);

const EDITORIAL_TYPES = new Set(["bold", "italic", "color", "replace", "heading-lg", "heading-md", "heading-sm", "image-block", ...LAYOUT_TYPES]);

/* ประวัติ undo/redo — เก็บ snapshot ของ local editorial (ในหน่วยความจำเท่านั้น) */
const editorialUndo = [];
const editorialRedo = [];
const EDITORIAL_HISTORY_CAP = 100;

/* เรียกก่อนทุก action ที่แก้ editorial — เก็บสถานะปัจจุบันไว้ย้อนกลับได้ */
function pushEditorialHistory() {
  editorialUndo.push(JSON.stringify(getEditorialLocal()));
  if (editorialUndo.length > EDITORIAL_HISTORY_CAP) editorialUndo.shift();
  editorialRedo.length = 0;
}

function getEditorialLocal() {
  const raw = readStore(LS.editorial, null);
  if (!raw || typeof raw !== "object") return { entries: [], removed: [] };
  return {
    entries: Array.isArray(raw.entries) ? raw.entries : [],
    removed: Array.isArray(raw.removed) ? raw.removed : [],
  };
}

function writeEditorialLocal(local) {
  writeStore(LS.editorial, local);
}

/* รวม baseline (ไฟล์) + overlay (local) เป็นชุดที่มีผลจริง — keyed by id */
function effectiveEditorial(slug) {
  const fileEntries = (state.editorialFile[slug] && state.editorialFile[slug].entries) || [];
  const local = getEditorialLocal();
  const removed = new Set(local.removed);
  const byId = new Map();
  for (const entry of fileEntries) {
    if (entry && entry.id && !removed.has(entry.id)) byId.set(entry.id, entry);
  }
  for (const entry of local.entries) {
    if (entry && entry.slug === slug && entry.id) byId.set(entry.id, entry);
  }
  return [...byId.values()];
}

function pageEditorial(slug, page) {
  return effectiveEditorial(slug)
    .filter((e) => Number(e.page) === page && EDITORIAL_TYPES.has(e.type))
    .sort((a, b) => a.start - b.start || a.end - b.end);
}

/* รวมทุกเล่มสำหรับแผงรายการ/ส่งออก */
function allEffectiveEditorial() {
  const out = [];
  for (const book of state.catalog.books) {
    for (const entry of effectiveEditorial(book.slug)) out.push(entry);
  }
  return out;
}

function addEditorial(entry) {
  const local = getEditorialLocal();
  const id = `ed-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
  local.entries.push({ id, ts: Date.now(), ...entry });
  writeEditorialLocal(local);
  return id;
}

function updateEditorial(id, patch) {
  const local = getEditorialLocal();
  const existing = local.entries.find((e) => e.id === id);
  if (existing) {
    Object.assign(existing, patch, { updated: Date.now() });
  } else {
    // entry มาจากไฟล์ — คัดลอกมาเป็น local แล้วแก้
    const fromFile = allEffectiveEditorial().find((e) => e.id === id);
    if (!fromFile) return;
    local.entries.push({ ...fromFile, ...patch, updated: Date.now() });
  }
  writeEditorialLocal(local);
}

function removeEditorial(id) {
  const local = getEditorialLocal();
  local.entries = local.entries.filter((e) => e.id !== id);
  // ถ้า id นี้มาจากไฟล์ baseline ต้องทำ tombstone
  const inFile = Object.values(state.editorialFile).some(
    (book) => Array.isArray(book.entries) && book.entries.some((e) => e.id === id),
  );
  if (inFile && !local.removed.includes(id)) local.removed.push(id);
  writeEditorialLocal(local);
}

/* JSON สำหรับวางในไฟล์ editorial-overrides.json (โครงสร้าง { "book-XX": { entries: [] } }) */
function editorialExportJson() {
  const grouped = {};
  for (const entry of allEffectiveEditorial()) {
    const slug = entry.slug;
    if (!grouped[slug]) grouped[slug] = { entries: [] };
    // เก็บเฉพาะฟิลด์ที่จำเป็น เรียงให้คงที่
    const clean = { id: entry.id, type: entry.type, page: entry.page, start: entry.start, end: entry.end };
    if (entry.type === "color") clean.color = entry.color;
    if (entry.type === "replace") clean.replacement = entry.replacement;
    if (entry.type === "image-block") { clean.image = entry.image; clean.caption = entry.caption || ""; }
    grouped[slug].entries.push(clean);
  }
  for (const slug of Object.keys(grouped)) {
    grouped[slug].entries.sort((a, b) => a.page - b.page || a.start - b.start);
  }
  return JSON.stringify(grouped, null, 2);
}

/* เผยแพร่ editorial ไป /api/publish (Cloudflare Worker) — แยกจาก export เพื่อให้ backup ยังใช้ได้ */
async function publishEditorial() {
  const btn = els.adminPublishBtn;
  if (btn.disabled) return;

  const icon = btn.querySelector(".publish-icon");
  const spinner = btn.querySelector(".publish-spinner");
  const label = btn.querySelector(".publish-label");

  btn.disabled = true;
  btn.classList.remove("publish-success", "publish-error");
  icon.hidden = true;
  spinner.hidden = false;
  label.textContent = "กำลังเผยแพร่…";

  const payload = editorialExportJson();
  try {
    const res = await fetch(PUBLISH_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload,
    });
    const bodyText = await res.text();
    let data = null;
    try { data = JSON.parse(bodyText); } catch { /* response ไม่ใช่ JSON */ }

    if (!res.ok || !(data && data.success)) {
      // diagnostics: HTTP status + response body + full payload
      console.error("[publish] ล้มเหลว", { status: res.status, response: bodyText, payload });
      const detail = (data && data.error) || bodyText.slice(0, 200) || "ไม่มีรายละเอียด";
      throw new Error(`HTTP ${res.status} — ${detail}`);
    }

    // สำเร็จ — ใช้เวลา commit จาก worker ถ้ามี, ไม่งั้นใช้เวลาเครื่อง
    const committedAt = data.updatedAt ? new Date(data.updatedAt).getTime() : Date.now();
    setLastPublish(committedAt);
    updateAdminStatus();
    btn.classList.add("publish-success");
    label.textContent = "เผยแพร่สำเร็จ ✓";
    const stamp = thaiDateTime.format(new Date(committedAt));
    const commitShort = data.commitSha ? ` · commit ${String(data.commitSha).slice(0, 7)}` : "";
    toast("เผยแพร่สำเร็จ", `${stamp}${commitShort}`);
    setTimeout(() => resetPublishBtn(btn), 3000);
  } catch (err) {
    console.error("[publish] error", err, { payload });
    btn.classList.add("publish-error");
    label.textContent = "เผยแพร่ล้มเหลว";
    toast("เผยแพร่ล้มเหลว", err.message);
    setTimeout(() => resetPublishBtn(btn), 4000);
  }
}

function resetPublishBtn(btn) {
  btn.disabled = false;
  btn.classList.remove("publish-success", "publish-error");
  btn.querySelector(".publish-icon").hidden = false;
  btn.querySelector(".publish-spinner").hidden = true;
  btn.querySelector(".publish-label").textContent = "เผยแพร่";
}

/* ลบหลาย entry ในครั้งเดียว (caller จัดการ history เอง) */
function removeEditorialMany(ids) {
  const set = new Set(ids);
  const local = getEditorialLocal();
  local.entries = local.entries.filter((e) => !set.has(e.id));
  for (const id of ids) {
    const inFile = Object.values(state.editorialFile).some(
      (book) => Array.isArray(book.entries) && book.entries.some((e) => e.id === id),
    );
    if (inFile && !local.removed.includes(id)) local.removed.push(id);
  }
  writeEditorialLocal(local);
}

/* editorial entry บนหน้านี้ที่ทับช่วง [start,end) ของ selection */
function overlappingEditorial(slug, page, start, end) {
  return pageEditorial(slug, page).filter((e) => e.start < end && e.end > start);
}

/* ย้อน/ทำซ้ำ — สลับ snapshot ของ local editorial */
function undoEditorial() {
  if (!editorialUndo.length) {
    toast("ไม่มีอะไรให้ย้อนกลับ");
    return;
  }
  editorialRedo.push(JSON.stringify(getEditorialLocal()));
  writeEditorialLocal(JSON.parse(editorialUndo.pop()));
  afterEditorialChange();
  toast("ย้อนกลับแล้ว");
}

function redoEditorial() {
  if (!editorialRedo.length) {
    toast("ไม่มีอะไรให้ทำซ้ำ");
    return;
  }
  editorialUndo.push(JSON.stringify(getEditorialLocal()));
  writeEditorialLocal(JSON.parse(editorialRedo.pop()));
  afterEditorialChange();
  toast("ทำซ้ำแล้ว");
}

/* re-render หน้าอ่าน + แผง หลัง editorial เปลี่ยน */
function afterEditorialChange() {
  if (state.view === "reader" && state.book) renderPage();
  if (!els.editorialBackdrop.hidden) renderEditorialPanel();
  if (state.admin) updateAdminStatus();
}

/* นับสถิติ editorial แยกตามชนิด/ความหมาย */
function editorialStats() {
  const counts = {
    bold: 0, italic: 0, replace: 0, important: 0, pali: 0, commentary: 0, review: 0, other: 0,
    "heading-lg": 0, "heading-md": 0, "heading-sm": 0, "image-block": 0,
    "align-center": 0, "align-left": 0, "align-right": 0, indent: 0, "spacing-top": 0, "spacing-bottom": 0,
  };
  for (const entry of allEffectiveEditorial()) {
    if (entry.type === "color") {
      const preset = COLOR_PRESETS[String(entry.color || "").toLowerCase()];
      if (preset) counts[preset.badge.toLowerCase()] += 1;
      else counts.other += 1;
    } else if (counts[entry.type] != null) {
      counts[entry.type] += 1;
    }
  }
  counts.total = allEffectiveEditorial().length;
  return counts;
}

function getRecentSearches() {
  return readStore(LS.recentSearches, []);
}

function saveRecentSearch(query) {
  if (!query || query.length < 2) return;
  const recent = getRecentSearches().filter((q) => q !== query);
  recent.unshift(query);
  writeStore(LS.recentSearches, recent.slice(0, 8));
}

function getRecentSections() {
  return readStore(LS.recentSections, []);
}

function saveRecentSection(slug, section) {
  const recent = getRecentSections()
    .filter((s) => !(s.slug === slug && s.index === section.index));
  recent.unshift({
    slug,
    index: section.index,
    title: section.title,
    startPage: section.startPage,
    endPage: section.endPage,
    ts: Date.now(),
  });
  writeStore(LS.recentSections, recent.slice(0, 6));
}

/* ───────────── routing ───────────── */

function parseHash() {
  const hash = location.hash.replace(/^#\/?/, "");
  const parts = hash.split("/").filter(Boolean);
  if (parts[0] === "book" && parts[1]) {
    return { view: "reader", slug: parts[1], page: Math.max(1, Number(parts[2]) || 1) };
  }
  if (parts[0] === "section" && parts[1]) {
    return { view: "section", slug: parts[1], index: Math.max(0, Number(parts[2]) || 0) };
  }
  if (parts[0] === "bookmarks") return { view: "bookmarks" };
  if (parts[0] === "notes") return { view: "notes" };
  if (parts[0] === "map") return { view: "map" };
  if (parts[0] === "quality") return { view: "quality" };
  return { view: "library" };
}

function goTo(slug, page, query = "") {
  state.highlightQuery = query;
  const target = `#/book/${slug}/${page}`;
  if (location.hash === target) {
    router();
  } else {
    location.hash = target;
  }
}

async function router() {
  const route = parseHash();
  state.view = route.view;

  for (const [name, el] of Object.entries(els.views)) {
    el.hidden = name !== route.view;
  }
  els.appnavLinks.forEach((link) => {
    link.classList.toggle("active", link.dataset.nav === route.view);
  });

  if (route.view !== "reader") {
    document.body.classList.remove("focus-mode");
    closeToc();
  }

  try {
    if (route.view === "library") renderLibrary();
    if (route.view === "bookmarks") renderBookmarks();
    if (route.view === "notes") renderNotes();
    if (route.view === "map") await renderKnowledgeIndex();
    if (route.view === "reader") await openBook(route.slug, route.page);
    if (route.view === "section") await openSection(route.slug, route.index);
    if (route.view === "quality") await renderQuality();
  } catch (error) {
    toast(`เกิดข้อผิดพลาด: ${error.message}`);
  }

  if (route.view !== "reader") {
    window.scrollTo({ top: 0, behavior: "instant" });
  }
}

/* ───────────── library view ───────────── */

function renderLibrary() {
  const { books, totalPages, totalChars } = state.catalog;
  els.libraryStats.textContent =
    `${thaiNum.format(books.length)} เล่ม · ${thaiNum.format(totalPages)} หน้า · ` +
    `${arabicNum.format(Math.round(totalChars / 1000) / 1000)} ล้านตัวอักษร · อ้างอิงกลับ PDF ต้นฉบับได้ทุกหน้า`;

  const progress = getProgress();
  const pieces = [];

  // แถบ "อ่านต่อ" — เล่มที่แตะล่าสุด
  const recent = Object.entries(progress)
    .map(([slug, p]) => ({ slug, ...p }))
    .filter((p) => bookMeta(p.slug))
    .sort((a, b) => b.ts - a.ts)[0];

  // hero — สถิติ + ปุ่มเริ่มอ่าน/อ่านต่อ (เหนือชั้นหนังสือ ไม่แตะส่วนอ่าน)
  els.heroStatBooks.textContent = thaiNum.format(books.length);
  els.heroStatPages.textContent = thaiNum.format(totalPages);
  els.heroStatChars.textContent = thaiNum.format(totalChars);
  const firstBook = books[0];
  els.heroStart.href = firstBook ? `#/book/${firstBook.slug}/1` : "#/";
  if (recent && recent.page > 1 && bookMeta(recent.slug)) {
    els.heroContinue.href = `#/book/${recent.slug}/${recent.page}`;
    els.heroContinue.hidden = false;
  } else {
    els.heroContinue.hidden = true;
  }

  if (recent && recent.page > 1) {
    const book = bookMeta(recent.slug);
    pieces.push(`
      <a class="continue-strip" href="#/book/${book.slug}/${recent.page}">
        <span class="c-icon">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5.5C10 4 7.5 3.5 4.5 3.5v15c3 0 5.5.5 7.5 2 2-1.5 4.5-2 7.5-2v-15c-3 0-5.5.5-7.5 2Zm0 0V20"/></svg>
        </span>
        <span class="c-meta">
          <small>อ่านต่อจากครั้งก่อน</small>
          <strong>${escapeHtml(book.title)}</strong>
          <span>หน้า ${thaiNum.format(recent.page)} จาก ${thaiNum.format(book.pages)} · ${Math.round((recent.page / book.pages) * 100)}%</span>
        </span>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg>
      </a>
    `);
  }

  // หัวข้อที่ดูล่าสุด
  const recentSections = getRecentSections().filter((s) => bookMeta(s.slug));
  if (recentSections.length) {
    pieces.push(`
      <div class="recent-sections">
        <span class="rs-label">หัวข้อที่ดูล่าสุด</span>
        ${recentSections.map((s) => `
          <a class="chip" href="#/section/${s.slug}/${s.index}" title="${escapeHtml(s.title)}">
            ${escapeHtml(s.title.length > 36 ? `${s.title.slice(0, 36)}…` : s.title)}
          </a>
        `).join("")}
      </div>
    `);
  }

  els.continueStrip.innerHTML = pieces.join("");

  els.shelf.innerHTML = state.catalog.books.map((book) => {
    const saved = progress[book.slug];
    const pct = saved ? Math.round((saved.page / book.pages) * 100) : 0;
    return `
      <button class="tome" type="button" data-slug="${book.slug}" data-page="${saved ? saved.page : 1}">
        <span class="tome-spine"><b>${thaiNum.format(book.number)}</b></span>
        <span class="tome-body">
          <h3>${escapeHtml(book.title)}</h3>
          <p class="tome-note">${escapeHtml(book.note || "")}</p>
          <span class="tome-foot">
            <span>${thaiNum.format(book.pages)} หน้า</span>
            <span class="tome-progress"><i style="width:${pct}%"></i></span>
            <span class="tome-pct">${pct > 0 ? `${pct}%` : "—"}</span>
          </span>
        </span>
      </button>
    `;
  }).join("");
}

/* ───────────── reader view ───────────── */

async function openBook(slug, page) {
  state.book = await loadBook(slug);
  state.slug = slug;
  state.page = Math.min(Math.max(1, page), state.book.pages);
  renderPage();
}

function renderPage() {
  const book = state.book;
  const page = book.pageData[state.page - 1];
  const pct = Math.round((state.page / book.pages) * 100);

  els.readerKicker.textContent = `เล่ม ${thaiNum.format(book.number)} จาก ${thaiNum.format(state.catalog.books.length)}`;
  els.readerTitle.textContent = book.title;

  const heading = Array.isArray(page.headings) && page.headings.length
    ? page.headings[0]
    : `หน้า ${thaiNum.format(page.number)}`;
  els.pageHeading.textContent = heading.length > 80 ? `${heading.slice(0, 80)}…` : heading;
  els.pagePct.textContent = `หน้า ${thaiNum.format(state.page)} / ${thaiNum.format(book.pages)} · ${pct}%`;

  els.pageText.innerHTML = renderAnnotatedText(
    page.text || "(ไม่มีข้อความในหน้านี้)",
    pageAnnotations(book.slug, state.page),
    state.highlightQuery,
    pageEditorial(book.slug, state.page),
  );

  const pdfHref = `../pdf/${encodeURIComponent(book.file)}#page=${page.number}`;
  els.pdfLink.href = pdfHref;
  els.pageSource.href = pdfHref;
  els.pageSource.textContent = `เปิด PDF ต้นฉบับ · หน้า ${thaiNum.format(page.number)}`;

  els.pageInput.max = book.pages;
  els.pageInput.value = state.page;
  els.pageTotal.textContent = `/ ${thaiNum.format(book.pages)}`;
  els.pageSlider.max = book.pages;
  els.pageSlider.value = state.page;
  els.pageSlider.style.setProperty("--slider-pct", `${(state.page / book.pages) * 100}%`);
  els.prevPage.disabled = state.page <= 1;
  els.nextPage.disabled = state.page >= book.pages;

  els.bookmarkBtn.classList.toggle("on", isBookmarked(book.slug, state.page));

  saveProgress(book.slug, state.page, book.pages);
  window.scrollTo({ top: 0, behavior: "instant" });

  // ไฮไลต์คำค้นเฉพาะหน้าที่กระโดดมาจากผลค้นหา — เปลี่ยนหน้าแล้วล้างทิ้ง
  state.highlightQuery = "";
}

/* สีที่ปลอดภัยสำหรับ inline style — กัน injection ใน style attribute */
function safeColor(value) {
  return /^#[0-9a-fA-F]{3,8}$/.test(String(value || "")) ? value : "";
}

/* ที่อยู่รูปภาพที่ปลอดภัย — อนุญาต http(s), data:image, path สัมพัทธ์/สัมบูรณ์ และชื่อไฟล์ภาพ
   ปฏิเสธ scheme อันตราย (javascript:, vbscript: ฯลฯ) */
function safeImageSrc(value) {
  const s = String(value || "").trim();
  if (!s) return "";
  if (/^https?:\/\//i.test(s)) return s;
  if (/^data:image\/(png|jpe?g|webp|gif|svg\+xml|avif);/i.test(s)) return s;
  if (/^(\.{0,2}\/|\/)[^\s]*$/.test(s)) return s; // /foo, ./foo, ../foo
  if (/^[\w.\-]+\.(png|jpe?g|webp|gif|svg|avif)$/i.test(s)) return s; // ชื่อไฟล์ล้วน
  return "";
}

/* HTML ของบล็อกรูปภาพ editorial — render กลางเนื้อหา (figure + caption) */
function imageBlockHtml(im) {
  const cap = im.caption
    ? `<figcaption>${escapeHtml(im.caption)}</figcaption>`
    : "";
  return `<figure class="ed-image-block" data-ed-id="${escapeHtml(im.id)}">`
    + `<img src="${escapeHtml(im.image)}" alt="${escapeHtml(im.caption || "ภาพประกอบ")}" loading="lazy" />`
    + `${cap}</figure>`;
}

/* ห่อ chunk เดียวด้วย overlay ที่มีผล: mark (ค้น) → bold/italic/color → ไฮไลท์ผู้อ่าน → block ชั้นนอกสุด (heading + layout) */
function wrapChunk(chunk, { ann, matched, bold, italic, color, heading, layouts }) {
  let part = escapeHtml(chunk);
  if (matched) part = `<mark>${part}</mark>`;
  if (bold) part = `<strong class="ed-bold">${part}</strong>`;
  if (italic) part = `<em class="ed-italic">${part}</em>`;
  if (color) part = `<span class="ed-color" style="color:${color}">${part}</span>`;
  if (ann) {
    const noteClass = ann.note ? " has-note" : "";
    const title = ann.note ? ` title="${escapeHtml(ann.note)}"` : "";
    part = `<span class="user-highlight${noteClass}" data-ann-id="${escapeHtml(ann.id)}"${title}>${part}</span>`;
  }
  // ชั้น block นอกสุด — รวม heading + layout (จัดวาง/ระยะ) เป็น class เดียวกัน
  const blockClasses = [];
  if (heading) blockClasses.push("ed-heading", `ed-h-${heading.replace("heading-", "")}`);
  if (layouts && layouts.length) for (const t of layouts) blockClasses.push(`ed-${t}`);
  if (blockClasses.length) part = `<span class="${blockClasses.join(" ")}">${part}</span>`;
  return part;
}

function renderAnnotatedText(text, annotations, query = "", editorial = []) {
  const len = text.length;
  const clamp = (n) => Math.max(0, Math.min(len, n));

  const noteRanges = annotations
    .filter((ann) => Number.isFinite(ann.start) && Number.isFinite(ann.end) && ann.end > ann.start)
    .map((ann) => ({ start: clamp(ann.start), end: clamp(ann.end), ann }))
    .filter((range) => range.end > range.start);

  const searchRanges = query
    ? findMatches({ text }, query, 500).map(([start, end]) => ({ start, end }))
    : [];

  const formats = editorial
    .filter((e) => e.type === "bold" || e.type === "italic" || e.type === "color" || e.type.startsWith("heading-") || LAYOUT_TYPES.has(e.type))
    .map((e) => ({ type: e.type, start: clamp(e.start), end: clamp(e.end), color: safeColor(e.color) }))
    .filter((e) => e.end > e.start);

  // replace = แทนข้อความช่วงนั้น (ไม่ซอยภายใน) เรียงและตัดช่วงซ้อน
  const replaceRanges = editorial
    .filter((e) => e.type === "replace")
    .map((e) => ({ start: clamp(e.start), end: clamp(e.end), replacement: String(e.replacement || ""), id: e.id }))
    .filter((e) => e.end > e.start)
    .sort((a, b) => a.start - b.start)
    .reduce((acc, r) => {
      if (!acc.length || r.start >= acc[acc.length - 1].end) acc.push(r);
      return acc;
    }, []);

  // render ช่วงปกติ [from,to) โดยซอยตามขอบของ noteRanges/searchRanges/formats
  const emitNormal = (from, to) => {
    if (to <= from) return "";
    const points = new Set([from, to]);
    for (const r of [...noteRanges, ...searchRanges, ...formats]) {
      if (r.start > from && r.start < to) points.add(r.start);
      if (r.end > from && r.end < to) points.add(r.end);
    }
    const sorted = [...points].sort((a, b) => a - b);
    let out = "";
    for (let i = 0; i < sorted.length - 1; i += 1) {
      const s = sorted[i];
      const e = sorted[i + 1];
      if (s === e) continue;
      const ann = noteRanges.find((r) => s >= r.start && e <= r.end)?.ann;
      const matched = searchRanges.some((r) => s >= r.start && e <= r.end);
      let bold = false;
      let italic = false;
      let color = "";
      let heading = "";
      const layouts = [];
      for (const f of formats) {
        if (s >= f.start && e <= f.end) {
          if (f.type === "bold") bold = true;
          else if (f.type === "italic") italic = true;
          else if (f.type === "color" && f.color) color = f.color;
          else if (f.type.startsWith("heading-")) heading = f.type;
          else if (LAYOUT_TYPES.has(f.type)) layouts.push(f.type);
        }
      }
      out += wrapChunk(text.slice(s, e), { ann, matched, bold, italic, color, heading, layouts });
    }
    return out;
  };

  // image-block = บล็อกรูปภาพ ผูกกับจุด start (start==end) แทรกคั่นกลางเนื้อหา
  const imageBlocks = editorial
    .filter((e) => e.type === "image-block")
    .map((e) => ({ kind: "image", at: clamp(e.start), image: safeImageSrc(e.image), caption: String(e.caption || ""), id: e.id }))
    .filter((e) => e.image);

  // รวม replace (กินช่วง) + image (จุดแทรก) เรียงตามตำแหน่ง — image มาก่อนถ้าอยู่จุดเดียวกัน
  const ops = [
    ...replaceRanges.map((r) => ({ kind: "replace", at: r.start, ...r })),
    ...imageBlocks,
  ].sort((a, b) => a.at - b.at || (a.kind === "image" ? -1 : 1));

  let html = "";
  let cursor = 0;
  for (const op of ops) {
    if (op.at < cursor) continue; // อยู่ในช่วง replace ที่กินไปแล้ว — ข้าม
    html += emitNormal(cursor, op.at);
    if (op.kind === "replace") {
      const original = text.slice(op.start, op.end);
      html += `<span class="ed-replace" data-ed-id="${escapeHtml(op.id)}" title="ข้อความเดิม: ${escapeHtml(original)}">${escapeHtml(op.replacement)}</span>`;
      cursor = op.end;
    } else {
      html += imageBlockHtml(op);
      cursor = op.at;
    }
  }
  html += emitNormal(cursor, len);
  return html;
}

function selectionOffsetsInPage() {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return null;
  const range = selection.getRangeAt(0);
  if (!els.pageText.contains(range.commonAncestorContainer)) return null;

  const textRange = document.createRange();
  textRange.selectNodeContents(els.pageText);
  textRange.setEnd(range.startContainer, range.startOffset);
  const start = textRange.toString().length;
  const quote = selection.toString();
  const end = start + quote.length;
  if (!quote.trim() || end <= start) return null;
  return { start, end, quote };
}

/* ตำแหน่ง/ขนาด/สถานะย่อ ของป๊อปอัป — จำไว้ใน localStorage */
const edPopup = (() => {
  const saved = readStore(LS.edPopup, {}) || {};
  return {
    x: Number.isFinite(saved.x) ? saved.x : null,
    y: Number.isFinite(saved.y) ? saved.y : null,
    w: Number.isFinite(saved.w) ? saved.w : null,
    h: Number.isFinite(saved.h) ? saved.h : null,
    minimized: !!saved.minimized,
  };
})();

function persistEdPopup() {
  writeStore(LS.edPopup, edPopup);
}

/* กันไม่ให้ออกนอกจอ */
function clampToViewport(x, y, w, h) {
  const maxX = Math.max(8, window.innerWidth - w - 8);
  const maxY = Math.max(8, window.innerHeight - h - 8);
  return [Math.min(Math.max(8, x), maxX), Math.min(Math.max(8, y), maxY)];
}

/* วางตำแหน่ง+ขนาดป๊อปอัป: ใช้ค่าที่จำไว้ ถ้าไม่มีก็วางใกล้ selection แล้ว clamp */
function applyPopupGeometry(rect) {
  const pop = els.selectionPopover;
  pop.style.width = edPopup.w ? `${edPopup.w}px` : "";
  pop.style.height = edPopup.h ? `${edPopup.h}px` : "";

  let x;
  let y;
  if (edPopup.x != null && edPopup.y != null) {
    x = edPopup.x;
    y = edPopup.y;
  } else if (rect) {
    x = rect.left + rect.width / 2 - pop.offsetWidth / 2;
    y = rect.top - pop.offsetHeight - 8;
    if (y < 8) y = rect.bottom + 8; // ไม่มีที่ด้านบน → ไปด้านล่าง
  } else {
    x = window.innerWidth - pop.offsetWidth - 24;
    y = 84;
  }
  [x, y] = clampToViewport(x, y, pop.offsetWidth, pop.offsetHeight);
  pop.style.left = `${x}px`;
  pop.style.top = `${y}px`;
}

function showFab() {
  els.selRestoreBtn.hidden = false;
}

function showSelectionPopover(selectionData) {
  const sel = window.getSelection();
  const rect = sel && sel.rangeCount ? sel.getRangeAt(0).getBoundingClientRect() : null;
  state.pendingSelection = selectionData;

  // reset โหมดย่อย (note/replace ซ่อนไว้ก่อน — split mode)
  els.selectionNoteBox.hidden = true;
  els.selectionNoteInput.value = "";
  els.adminSelectionActions.hidden = !state.admin;
  els.edReplaceBox.hidden = true;
  els.edReplaceInput.value = "";
  els.selTitle.textContent = state.admin ? "เครื่องมือแก้ไข" : "เครื่องมือ";

  // ปุ่ม "ลบรูปแบบ" — แสดงเมื่อ selection ทับ editorial entry ที่มีอยู่
  if (state.admin && state.book && selectionData) {
    const overlap = overlappingEditorial(state.book.slug, state.page, selectionData.start, selectionData.end);
    state.pendingRemoveIds = overlap.map((e) => e.id);
    els.edRemoveRow.hidden = overlap.length === 0;
  } else {
    state.pendingRemoveIds = [];
    els.edRemoveRow.hidden = true;
  }

  // ไฮไลท์ผู้อ่าน: สลับปุ่ม "ไฮไลท์" ↔ "เอาไฮไลท์ออก" ตามว่าช่วงที่เลือกถูกไฮไลท์แล้วหรือยัง
  let annOverlap = [];
  if (state.book && selectionData) {
    annOverlap = pageAnnotations(state.book.slug, state.page)
      .filter((a) => a.start < selectionData.end && a.end > selectionData.start);
  }
  state.pendingRemoveAnnIds = annOverlap.map((a) => a.id);
  els.highlightSelectionBtn.hidden = annOverlap.length > 0;
  els.removeHighlightBtn.hidden = annOverlap.length === 0;

  // ถ้าย่ออยู่ → ไม่กางป๊อปอัป แค่คง FAB ไว้ (selection ถูกจดจำใน pendingSelection แล้ว)
  if (edPopup.minimized) {
    showFab();
    return;
  }
  els.selRestoreBtn.hidden = true;
  els.selectionPopover.hidden = false;
  applyPopupGeometry(rect);
}

function hideSelectionPopover(clearSelection = false) {
  clearTimeout(state._selChangeTimer);
  els.selectionPopover.hidden = true;
  els.edReplaceBox.hidden = true;
  els.selectionNoteBox.hidden = true;
  state.pendingSelection = null;
  if (clearSelection) window.getSelection()?.removeAllRanges();
}

function savePendingAnnotation(note = "") {
  if (!state.book || !state.pendingSelection) return;
  const { start, end, quote } = state.pendingSelection;
  addAnnotation({ slug: state.book.slug, page: state.page, start, end, quote, note });
  hideSelectionPopover(true);
  renderPage();
  toast(note.trim() ? "บันทึกโน้ตแล้ว" : "ไฮไลท์ข้อความแล้ว");
}

/* เอาไฮไลท์ผู้อ่านออกจากช่วงที่เลือก (คลิกเดียว — ถ้าช่วงนั้นมีโน้ตด้วย ถามยืนยันก่อน) */
function removePendingHighlight() {
  if (!state.pendingRemoveAnnIds.length) return;
  const ids = state.pendingRemoveAnnIds.slice();
  const hasNote = getAnnotations().some((a) => ids.includes(a.id) && a.note);
  if (hasNote && !window.confirm("ช่วงนี้มีโน้ตอยู่ด้วย — เอาไฮไลท์และโน้ตออกทั้งหมด?")) return;
  removeAnnotationsMany(ids);
  hideSelectionPopover(true);
  renderPage();
  toast("เอาไฮไลท์ออกแล้ว");
}

/* บันทึก editorial entry จาก selection ปัจจุบัน (เฉพาะแอดมิน)
   เก็บ quote ไว้สำหรับแสดงในแผงรายการ (ไม่ส่งออกลงไฟล์) */
function savePendingEditorial(type, extra = {}) {
  if (!state.admin || !state.book || !state.pendingSelection) return;
  const { start, end, quote } = state.pendingSelection;
  pushEditorialHistory();
  addEditorial({ slug: state.book.slug, page: state.page, type, start, end, quote, ...extra });
  hideSelectionPopover(true);
  renderPage();
  const labels = {
    bold: "ทำตัวหนาแล้ว", italic: "ทำตัวเอียงแล้ว", color: "ใส่สีแล้ว", replace: "แก้ไขข้อความแล้ว",
    "heading-lg": "ทำหัวข้อใหญ่แล้ว", "heading-md": "ทำหัวข้อกลางแล้ว", "heading-sm": "ทำหัวข้อเล็กแล้ว",
    "align-center": "จัดกึ่งกลางแล้ว", "align-left": "ชิดซ้ายแล้ว", "align-right": "ชิดขวาแล้ว",
    indent: "ย่อหน้าแล้ว", "spacing-top": "เพิ่มระยะบนแล้ว", "spacing-bottom": "เพิ่มระยะล่างแล้ว",
  };
  toast(labels[type] || "บันทึกการแก้ไขแล้ว");
}

/* ───────────── image-block (แทรกรูปภาพประกอบในเนื้อหา) ─────────────
   target: { mode:"insert", slug, page, start } | { mode:"edit", id } */
let imageDialogTarget = null;

function updateImagePreview() {
  const src = safeImageSrc(els.edImageUrl.value);
  if (src) {
    els.edImagePreview.src = src;
    els.edImagePreviewWrap.hidden = false;
  } else {
    els.edImagePreview.removeAttribute("src");
    els.edImagePreviewWrap.hidden = true;
  }
}

function openImageDialog(target, prefill = {}) {
  imageDialogTarget = target;
  els.edImageUrl.value = prefill.image || "";
  els.edImageCaption.value = prefill.caption || "";
  updateImagePreview();
  els.edImageBackdrop.hidden = false;
  els.edImageUrl.focus();
}

function closeImageDialog() {
  els.edImageBackdrop.hidden = true;
  imageDialogTarget = null;
}

function saveImageDialog() {
  if (!imageDialogTarget) return;
  const image = safeImageSrc(els.edImageUrl.value);
  const caption = els.edImageCaption.value.trim();
  if (!image) {
    toast("กรอกที่อยู่รูปภาพที่ถูกต้อง (http(s):// หรือ path ของไฟล์ภาพ)");
    els.edImageUrl.focus();
    return;
  }
  pushEditorialHistory();
  if (imageDialogTarget.mode === "edit") {
    updateEditorial(imageDialogTarget.id, { image, caption });
    toast("แก้ไขรูปภาพแล้ว");
  } else {
    const { slug, page, start } = imageDialogTarget;
    addEditorial({ slug, page, type: "image-block", start, end: start, image, caption });
    toast("แทรกรูปภาพแล้ว");
  }
  closeImageDialog();
  afterEditorialChange();
}

/* เปิดไดอะล็อกแทรกรูปจากป๊อปอัป — ผูกรูปที่จุดเริ่มของ selection ปัจจุบัน */
function openImageInsertFromSelection() {
  if (!state.admin || !state.book || !state.pendingSelection) {
    toast("เลือกตำแหน่งในข้อความก่อนแทรกรูป");
    return;
  }
  const target = { mode: "insert", slug: state.book.slug, page: state.page, start: state.pendingSelection.start };
  hideSelectionPopover(true);
  openImageDialog(target);
}

/* ลบรูปแบบ editorial ที่ทับ selection ปัจจุบัน (ปุ่ม 🗑 ในป๊อปอัป) */
function removePendingFormatting() {
  if (!state.admin || !state.pendingRemoveIds.length) return;
  const ids = state.pendingRemoveIds.slice();
  const hasReplace = allEffectiveEditorial().some((e) => ids.includes(e.id) && e.type === "replace");
  if (hasReplace && !window.confirm("ลบการแก้ไขข้อความ (replace) ในช่วงที่เลือก?")) return;
  pushEditorialHistory();
  removeEditorialMany(ids);
  hideSelectionPopover(true);
  afterEditorialChange();
  toast(`ลบรูปแบบแล้ว ${thaiNum.format(ids.length)} รายการ`);
}

/* ล้าง editorial ทั้งหมดของหน้าปัจจุบัน */
function clearCurrentPageEditorial() {
  if (!state.admin || !state.slug || !state.page) return;
  const ids = pageEditorial(state.slug, state.page).map((e) => e.id);
  if (!ids.length) {
    toast("หน้านี้ไม่มีรายการแก้ไข");
    return;
  }
  if (!window.confirm(`ลบคำอธิบาย editorial ทั้งหมดบนหน้านี้? (${thaiNum.format(ids.length)} รายการ)`)) return;
  pushEditorialHistory();
  removeEditorialMany(ids);
  afterEditorialChange();
  toast(`ล้างหน้านี้แล้ว ${thaiNum.format(ids.length)} รายการ`);
}

function setPage(page) {
  if (!state.book) return;
  const next = Math.min(Math.max(1, page), state.book.pages);
  if (next === state.page) return;
  state.page = next;
  history.replaceState(null, "", `#/book/${state.slug}/${next}`);
  renderPage();
}

function applyFontSize() {
  document.documentElement.style.setProperty("--reader-size", `${state.fontSize}px`);
  localStorage.setItem(LS.fontSize, state.fontSize);
}

function bumpFont(delta) {
  state.fontSize = clampFont(state.fontSize + delta);
  applyFontSize();
}

/* ───────────── สารบัญ (TOC drawer) ───────────── */

/* override ที่มีผลจริง = ไฟล์ overrides + รายการที่ตัดออกในโหมดตรวจ (ยังไม่บันทึก) */
function tocOverrideFor(slug) {
  const file = state.overrides.toc[slug] || null;
  const ui = state.reviewRemovals.get(slug) || [];
  if (!ui.length) return file;
  return {
    add: (file && file.add) || [],
    remove: [...((file && file.remove) || []), ...ui],
  };
}

function invalidateTocCaches(slug) {
  state.tocCache.delete(slug);
  state.sectionsCache.delete(slug);
}

function getToc(slug, book) {
  if (!state.tocCache.has(slug)) state.tocCache.set(slug, buildToc(book, tocOverrideFor(slug)));
  return state.tocCache.get(slug);
}

function getSections(slug, book) {
  if (!state.sectionsCache.has(slug)) state.sectionsCache.set(slug, buildSections(book, tocOverrideFor(slug)));
  return state.sectionsCache.get(slug);
}

function openToc() {
  if (!state.book) return;
  state.tocOpen = true;
  els.tocBackdrop.hidden = false;
  els.tocBookTitle.textContent = state.book.title;
  els.tocFilter.value = "";
  renderTocList();
  if (window.matchMedia("(min-width: 881px)").matches) els.tocFilter.focus();
}

function closeToc() {
  if (!state.tocOpen) return;
  state.tocOpen = false;
  els.tocBackdrop.hidden = true;
}

function renderTocList() {
  const book = state.book;
  const entries = getToc(state.slug, book);
  const sections = getSections(state.slug, book);
  const sectionByPage = new Map(sections.map((s) => [s.startPage, s.index]));

  const filterQuery = normalizeQuery(els.tocFilter.value.trim());
  const majorCount = entries.filter((e) => e.major).length;

  els.tocModeMajor.classList.toggle("on", state.tocMode === "major");
  els.tocModeAll.classList.toggle("on", state.tocMode === "all");
  els.tocModeReview.classList.toggle("on", state.tocMode === "review");
  els.tocModeMajor.textContent = `หัวข้อหลัก (${thaiNum.format(majorCount)})`;
  els.tocModeAll.textContent = `ทุกหน้า (${thaiNum.format(entries.length)})`;

  if (state.tocMode === "review") {
    renderTocReview(book, entries, sections);
    return;
  }

  let shown = state.tocMode === "major" ? entries.filter((e) => e.major) : entries;
  if (filterQuery) {
    shown = shown.filter((e) => normalizeQuery(e.title).includes(filterQuery));
  }

  if (!shown.length) {
    els.tocList.innerHTML = `<p class="toc-empty">ไม่พบหัวข้อที่ตรงกับคำกรอง</p>`;
    return;
  }

  els.tocList.innerHTML = shown.map((entry) => {
    const sectionIndex = entry.major ? sectionByPage.get(entry.page) : undefined;
    return `
      <div class="toc-item ${entry.major ? "is-major" : ""}" data-page="${entry.page}">
        <span class="toc-badge">${escapeHtml(entry.type)}</span>
        <span class="toc-title">${escapeHtml(entry.title)}</span>
        <span class="toc-page">${thaiNum.format(entry.page)}</span>
        ${sectionIndex !== undefined ? `
          <button class="toc-sec" type="button" data-sec="${sectionIndex}" title="อ่านทั้งหัวข้อ" aria-label="อ่านทั้งหัวข้อ">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5h14M5 10h14M5 15h9M5 20h6"/></svg>
          </button>` : ""}
      </div>
    `;
  }).join("");
}

/* ───────────── โหมดตรวจสารบัญ (review) ───────────── */

function renderTocReview(book, entries, sections) {
  const diag = diagnoseBook(book, tocOverrideFor(state.slug));
  const removals = state.reviewRemovals.get(state.slug) || [];
  const majorByPage = new Map();
  for (const entry of entries) {
    if (entry.major && !majorByPage.has(entry.page)) majorByPage.set(entry.page, entry);
  }

  const typeDist = Object.entries(diag.typeDist)
    .sort((a, b) => b[1] - a[1])
    .map(([type, count]) => `<span class="ti-cell">${escapeHtml(type)}<b>${thaiNum.format(count)}</b></span>`)
    .join("");

  const rows = sections.map((section) => {
    const length = section.endPage - section.startPage + 1;
    const entry = majorByPage.get(section.startPage);
    const confidence = entry ? headingConfidence(entry) : "—";
    const isLong = length > LONG_SECTION_PAGES;
    return `
      <div class="rv-item ${isLong ? "rv-long" : ""}">
        <div class="rv-main">
          <span class="toc-badge">${escapeHtml(section.type)}</span>
          <span class="rv-title">${escapeHtml(section.title)}</span>
        </div>
        <div class="rv-meta">
          <span>หน้า ${thaiNum.format(section.startPage)}–${thaiNum.format(section.endPage)}</span>
          <span class="${isLong ? "rv-warn" : ""}">${thaiNum.format(length)} หน้า${isLong ? " ⚠ ยาวผิดปกติ" : ""}</span>
          <span>ความเชื่อมั่น: ${confidence}</span>
          ${entry ? `
            <button class="rv-remove" type="button" data-page="${entry.page}" data-title="${escapeHtml(entry.title)}">ตัดออก</button>
          ` : `<span class="rv-auto">เพิ่มอัตโนมัติ</span>`}
        </div>
      </div>
    `;
  }).join("");

  els.tocList.innerHTML = `
    <div class="rv-diag">
      <p class="rv-diag-line">headings ทั้งหมด <b>${thaiNum.format(diag.totalHeadings)}</b> · หัวข้อหลัก <b>${thaiNum.format(diag.majorCount)}</b> · หัวข้อ <b>${thaiNum.format(diag.sectionCount)}</b></p>
      ${diag.longest ? `<p class="rv-diag-line">ยาวสุด: ${escapeHtml(diag.longest.title.slice(0, 40))} (${thaiNum.format(diag.longest.length)} หน้า) · สั้นสุด: ${thaiNum.format(diag.shortest.length)} หน้า</p>` : ""}
      <div class="rv-dist">${typeDist}</div>
      <div class="rv-actions">
        <button class="pf-chip" id="rvCopy" type="button">คัดลอก override JSON${removals.length ? ` (ตัดออก ${thaiNum.format(removals.length)})` : ""}</button>
        ${removals.length ? `<button class="pf-chip" id="rvRestore" type="button">คืนค่าที่ตัดออก</button>` : ""}
      </div>
    </div>
    ${rows}
  `;
}

function reviewOverrideJson() {
  const out = JSON.parse(JSON.stringify(state.overrides.tocRaw || {}));
  for (const [slug, removals] of state.reviewRemovals) {
    if (!removals.length) continue;
    const fileOv = out[slug] || {};
    const merged = [...(fileOv.remove || [])];
    for (const r of removals) {
      if (!merged.some((m) => m.page === r.page && m.title === r.title)) merged.push(r);
    }
    out[slug] = { add: fileOv.add || [], remove: merged };
  }
  return JSON.stringify(out, null, 2);
}

/* ───────────── อ่านตามหัวข้อ (section view) ───────────── */

const SECTION_RENDER_CAP = 30; // หน้าต่อหัวข้อที่ render ครั้งเดียว

async function openSection(slug, index) {
  const book = await loadBook(slug);
  const sections = getSections(slug, book);
  const section = sections[Math.min(index, sections.length - 1)];
  state.slug = slug;
  state.book = book;
  state.section = section;

  els.sectionKicker.textContent = `เล่ม ${thaiNum.format(book.number)} · หัวข้อ ${thaiNum.format(section.index + 1)} จาก ${thaiNum.format(sections.length)}`;
  els.sectionBookTitle.textContent = book.title;
  els.sectionBack.href = `#/book/${slug}/${section.startPage}`;
  els.sectionType.textContent = section.type;
  els.sectionTitle.textContent = section.title;

  const range = section.startPage === section.endPage
    ? `หน้า ${thaiNum.format(section.startPage)}`
    : `หน้า ${thaiNum.format(section.startPage)}–${thaiNum.format(section.endPage)}`;
  const pageCount = section.endPage - section.startPage + 1;
  els.sectionRange.textContent = `${range} · ${thaiNum.format(pageCount)} หน้า`;

  els.sectionPdfLink.href = `../pdf/${encodeURIComponent(book.file)}#page=${section.startPage}`;

  const renderEnd = Math.min(section.endPage, section.startPage + SECTION_RENDER_CAP - 1);
  const chunks = [];
  for (let p = section.startPage; p <= renderEnd; p += 1) {
    const page = book.pageData[p - 1];
    chunks.push(`
      <div class="sec-page">
        <a class="sec-page-no" href="#/book/${slug}/${p}" title="เปิดหน้านี้แบบรายหน้า">หน้า ${thaiNum.format(p)}</a>
        <div class="sec-page-text">${renderAnnotatedText(page.text || "(ไม่มีข้อความในหน้านี้)", [], "", pageEditorial(slug, p))}</div>
      </div>
    `);
  }
  if (renderEnd < section.endPage) {
    chunks.push(`
      <div class="sec-more">
        หัวข้อนี้ยาว ${thaiNum.format(pageCount)} หน้า — แสดง ${thaiNum.format(SECTION_RENDER_CAP)} หน้าแรก
        <a href="#/book/${slug}/${renderEnd + 1}">อ่านต่อแบบรายหน้า ตั้งแต่หน้า ${thaiNum.format(renderEnd + 1)}</a>
      </div>
    `);
  }
  els.sectionBody.innerHTML = chunks.join("");

  els.sectionPrev.disabled = section.index <= 0;
  els.sectionNext.disabled = section.index >= sections.length - 1;
  els.sectionPrev.dataset.target = section.index - 1;
  els.sectionNext.dataset.target = section.index + 1;

  saveRecentSection(slug, section);
  window.scrollTo({ top: 0, behavior: "instant" });
}

/* ───────────── bookmarks view ───────────── */

function renderBookmarks() {
  const bookmarks = getBookmarks().sort((a, b) => b.ts - a.ts);
  els.bookmarkStats.textContent = bookmarks.length
    ? `${thaiNum.format(bookmarks.length)} ตำแหน่งที่คั่นไว้ — บันทึกไว้ในเครื่องนี้`
    : "ยังไม่มีหน้าที่คั่นไว้";

  if (!bookmarks.length) {
    els.bookmarkList.innerHTML = `
      <div class="empty">
        <b>ยังไม่มีที่คั่นหน้า</b>
        ระหว่างอ่าน กดปุ่มรูปที่คั่นหนังสือเพื่อบันทึกหน้าสำคัญไว้กลับมาอ่านภายหลัง
      </div>
    `;
    return;
  }

  const groups = new Map();
  for (const bm of bookmarks) {
    if (!bookMeta(bm.slug)) continue;
    if (!groups.has(bm.slug)) groups.set(bm.slug, []);
    groups.get(bm.slug).push(bm);
  }

  els.bookmarkList.innerHTML = [...groups.entries()].map(([slug, items]) => {
    const book = bookMeta(slug);
    return `
      <div class="bm-group">
        <h3>${escapeHtml(book.title)}</h3>
        ${items.sort((a, b) => a.page - b.page).map((bm) => `
          <div class="bm-item">
            <span class="bm-page">หน้า<br>${thaiNum.format(bm.page)}</span>
            <span class="bm-text">
              <a href="#/book/${slug}/${bm.page}">${escapeHtml(bm.snippet || "")}…</a>
              <small>${new Date(bm.ts).toLocaleDateString("th-TH", { day: "numeric", month: "short", year: "numeric" })}</small>
            </span>
            <button class="bm-cite" type="button" data-slug="${slug}" data-page="${bm.page}" title="คัดลอกการอ้างอิง" aria-label="คัดลอกการอ้างอิง">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9.5 8.5c-2.5.7-4 2.6-4 5.5v1.5h4v-4h-2c.2-1.4 1-2.3 2-2.7Zm9 0c-2.5.7-4 2.6-4 5.5v1.5h4v-4h-2c.2-1.4 1-2.3 2-2.7Z"/></svg>
            </button>
            <button class="bm-remove" type="button" data-slug="${slug}" data-page="${bm.page}" aria-label="ลบที่คั่นหน้า">✕</button>
          </div>
        `).join("")}
      </div>
    `;
  }).join("");
}

/* ───────────── notes/highlights view ───────────── */

function renderNotes() {
  const annotations = getAnnotations().sort((a, b) => b.updated - a.updated);
  const noteCount = annotations.filter((ann) => ann.note).length;
  els.notesStats.textContent = annotations.length
    ? `${thaiNum.format(annotations.length)} ไฮไลท์ · ${thaiNum.format(noteCount)} โน้ต — บันทึกไว้ในเครื่องนี้`
    : "ยังไม่มีไฮไลท์หรือโน้ต";

  // ปุ่ม "ลบไฮไลท์ทั้งหมด" — แสดงเมื่อมีไฮไลท์ที่ไม่มีโน้ต (โน้ตจะถูกเก็บไว้)
  const highlightOnly = annotations.filter((ann) => !ann.note);
  els.deleteAllHighlightsBtn.hidden = highlightOnly.length === 0;

  if (!annotations.length) {
    els.notesList.innerHTML = `
      <div class="empty">
        <b>ยังไม่มีโน้ต</b>
        ลากเลือกข้อความในหน้าอ่าน แล้วกด “ไฮไลท์” หรือ “เพิ่มโน้ต” เพื่อเก็บไว้กลับมาอ่านภายหลัง
      </div>
    `;
    return;
  }

  const groups = new Map();
  for (const ann of annotations) {
    if (!bookMeta(ann.slug)) continue;
    if (!groups.has(ann.slug)) groups.set(ann.slug, []);
    groups.get(ann.slug).push(ann);
  }

  els.notesList.innerHTML = [...groups.entries()].map(([slug, items]) => {
    const book = bookMeta(slug);
    return `
      <div class="note-group">
        <h3>${escapeHtml(book.title)}</h3>
        ${items.sort((a, b) => a.page - b.page || a.start - b.start).map((ann) => `
          <article class="note-card" data-ann-id="${escapeHtml(ann.id)}">
            <a class="note-page" href="#/book/${slug}/${ann.page}">หน้า ${thaiNum.format(ann.page)}</a>
            <blockquote>${escapeHtml(ann.quote)}</blockquote>
            ${ann.note ? `<p class="note-body">${escapeHtml(ann.note)}</p>` : ""}
            <footer>
              <span>${new Date(ann.updated).toLocaleDateString("th-TH", { day: "numeric", month: "short", year: "numeric" })}</span>
              <button type="button" class="note-copy" data-ann-id="${escapeHtml(ann.id)}">คัดลอก</button>
              <button type="button" class="note-remove" data-ann-id="${escapeHtml(ann.id)}">ลบ</button>
            </footer>
          </article>
        `).join("")}
      </div>
    `;
  }).join("");
}

function annotationExportJson() {
  return JSON.stringify({
    type: "patisambhida-annotations",
    version: 1,
    exportedAt: new Date().toISOString(),
    annotations: getAnnotations(),
  }, null, 2);
}

function downloadTextFile(name, text) {
  const blob = new Blob([text], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/* ───────────── โหมดแอดมิน (editorial) ───────────── */

function setAdminMode(on) {
  state.admin = on;
  document.documentElement.classList.toggle("admin-on", on);
  els.adminBar.hidden = !on;
  if (!on) {
    els.editorialBackdrop.hidden = true;
    els.selRestoreBtn.hidden = true;
    hideSelectionPopover(true);
  } else {
    updateAdminStatus();
  }
  // re-render หน้าปัจจุบันให้ตัวเลือก editorial ใน popover อัปเดต (ตัว entry แสดงทุกคนอยู่แล้ว)
  if (state.view === "reader" && state.book) renderPage();
}

/* วันที่/เวลาแบบไทย (พ.ศ.) เช่น "14 มิ.ย. 2569 22:14" */
const thaiDateTime = new Intl.DateTimeFormat("th-TH-u-ca-buddhist-nu-latn", {
  day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});
function getLastExport() {
  const ts = Number(localStorage.getItem(LS.edLastExport));
  return Number.isFinite(ts) && ts > 0 ? ts : null;
}
function setLastExport(ts) {
  localStorage.setItem(LS.edLastExport, String(ts));
}

/* สรุปสถานะแอดมิน (เฉพาะโหมดแอดมิน) — จำนวน editorial + เวลาส่งออก/เผยแพร่ล่าสุด */
function getLastPublish() {
  const ts = Number(localStorage.getItem(LS.edLastPublish));
  return Number.isFinite(ts) && ts > 0 ? ts : null;
}
function setLastPublish(ts) {
  localStorage.setItem(LS.edLastPublish, String(ts));
}
function updateAdminStatus() {
  if (!state.admin) return;
  const count = allEffectiveEditorial().length;
  const lastExport = getLastExport();
  const lastPublish = getLastPublish();
  const exportPart = lastExport
    ? `ส่งออกล่าสุด <b>${escapeHtml(thaiDateTime.format(new Date(lastExport)))}</b>`
    : `ยังไม่เคยส่งออก`;
  const publishPart = lastPublish
    ? ` · เผยแพร่ล่าสุด <b>${escapeHtml(thaiDateTime.format(new Date(lastPublish)))}</b>`
    : "";
  els.adminStatus.innerHTML =
    `แก้ไข Editorial: <b>${arabicNum.format(count)}</b> · ${exportPart}${publishPart}`;
}

function openAdminLogin() {
  if (state.admin) {
    toast("อยู่ในโหมดแอดมินแล้ว");
    return;
  }
  els.adminLoginBackdrop.hidden = false;
  els.adminLoginInput.value = "";
  els.adminLoginInput.focus();
}

function submitAdminLogin() {
  if (els.adminLoginInput.value === ADMIN_PASSCODE) {
    localStorage.setItem(LS.admin, "true");
    els.adminLoginBackdrop.hidden = true;
    setAdminMode(true);
    toast("เข้าสู่โหมดแอดมินแล้ว");
  } else {
    toast("รหัสผ่านไม่ถูกต้อง");
    els.adminLoginInput.select();
  }
}

function exitAdminMode() {
  localStorage.removeItem(LS.admin);
  setAdminMode(false);
  toast("ออกจากโหมดแอดมินแล้ว");
}

/* preview ใช้ quote ที่เก็บไว้ตอนสร้าง (entry จากไฟล์อาจไม่มี → แสดงช่วง offset แทน) */
function editorialPreviewHtml(entry) {
  const slice = entry.quote || `(หน้า ${thaiNum.format(entry.page)} · อักษรที่ ${entry.start}–${entry.end})`;
  if (entry.type === "replace") {
    const original = entry.quote ? `<del>${escapeHtml(entry.quote)}</del> ` : "";
    return `${original}<ins>${escapeHtml(entry.replacement || "")}</ins>`;
  }
  if (entry.type === "color") {
    return `<span style="color:${safeColor(entry.color)}">${escapeHtml(slice)}</span>`;
  }
  if (entry.type === "image-block") {
    const src = safeImageSrc(entry.image);
    const cap = escapeHtml(entry.caption || "(ไม่มีคำบรรยาย)");
    if (src) return `<span class="ed-img-prev"><img src="${escapeHtml(src)}" alt="" loading="lazy" /><span>${cap}</span></span>`;
    return `🖼 ${cap}`;
  }
  if (entry.type === "bold") return `<strong>${escapeHtml(slice)}</strong>`;
  if (entry.type === "italic") return `<em>${escapeHtml(slice)}</em>`;
  if (entry.type.startsWith("heading-")) return `<span class="ed-heading ed-h-${entry.type.replace("heading-", "")}" style="font-size:1.2em">${escapeHtml(slice)}</span>`;
  return escapeHtml(slice);
}

/* สี preset เชิงความหมาย — เก็บเป็น color entry ปกติ (id/type/page/start/end/color)
   แล้ว map สีกลับเป็นป้ายความหมายในแผงรายการ (ไม่มี logic การ render พิเศษ) */
const COLOR_PRESETS = {
  "#0d6efd": { label: "คำสำคัญ", badge: "IMPORTANT" },
  "#8e44ad": { label: "คำบาลี", badge: "PALI" },
  "#1e8449": { label: "คำอธิบาย", badge: "COMMENTARY" },
  "#c0392b": { label: "ตรวจสอบ", badge: "REVIEW" },
};

function editorialBadge(entry) {
  if (entry.type === "bold") return { text: "BOLD", cls: "b-bold" };
  if (entry.type === "italic") return { text: "ITALIC", cls: "b-italic" };
  if (entry.type === "replace") return { text: "REPLACE", cls: "b-replace" };
  if (entry.type === "image-block") return { text: "IMAGE", cls: "b-image" };
  if (entry.type === "align-center") return { text: "CENTER", cls: "b-layout" };
  if (entry.type === "align-left") return { text: "LEFT", cls: "b-layout" };
  if (entry.type === "align-right") return { text: "RIGHT", cls: "b-layout" };
  if (entry.type === "indent") return { text: "INDENT", cls: "b-layout" };
  if (entry.type === "spacing-top") return { text: "SPACE-TOP", cls: "b-layout" };
  if (entry.type === "spacing-bottom") return { text: "SPACE-BOTTOM", cls: "b-layout" };
  if (entry.type.startsWith("heading-")) return { text: entry.type.toUpperCase(), cls: "b-heading" };
  if (entry.type === "color") {
    const preset = COLOR_PRESETS[String(entry.color || "").toLowerCase()];
    if (preset) return { text: preset.badge, cls: `b-${preset.badge.toLowerCase()}`, color: entry.color };
    return { text: "COLOR", cls: "b-color", color: entry.color };
  }
  return { text: String(entry.type).toUpperCase(), cls: "" };
}

function renderEditorialStats() {
  const s = editorialStats();
  els.editorialStatsBox.innerHTML = [
    `<span class="ed-stat total">รวม <b>${thaiNum.format(s.total)}</b></span>`,
    `<span class="ed-stat"><i class="dot" style="--sc:#0d6efd"></i>คำสำคัญ <b>${thaiNum.format(s.important)}</b></span>`,
    `<span class="ed-stat"><i class="dot" style="--sc:#8e44ad"></i>คำบาลี <b>${thaiNum.format(s.pali)}</b></span>`,
    `<span class="ed-stat"><i class="dot" style="--sc:#1e8449"></i>คำอธิบาย <b>${thaiNum.format(s.commentary)}</b></span>`,
    `<span class="ed-stat"><i class="dot" style="--sc:#c0392b"></i>ตรวจสอบ <b>${thaiNum.format(s.review)}</b></span>`,
    `<span class="ed-stat">ตัวหนา <b>${thaiNum.format(s.bold)}</b></span>`,
    `<span class="ed-stat">ตัวเอียง <b>${thaiNum.format(s.italic)}</b></span>`,
    `<span class="ed-stat">แก้ข้อความ <b>${thaiNum.format(s.replace)}</b></span>`,
    `<span class="ed-stat">หัวข้อใหญ่ <b>${thaiNum.format(s["heading-lg"])}</b></span>`,
    `<span class="ed-stat">หัวข้อกลาง <b>${thaiNum.format(s["heading-md"])}</b></span>`,
    `<span class="ed-stat">หัวข้อเล็ก <b>${thaiNum.format(s["heading-sm"])}</b></span>`,
    `<span class="ed-stat">ภาพประกอบ <b>${thaiNum.format(s["image-block"])}</b></span>`,
    `<span class="ed-stat">จัดกึ่งกลาง <b>${thaiNum.format(s["align-center"])}</b></span>`,
    `<span class="ed-stat">ชิดซ้าย <b>${thaiNum.format(s["align-left"])}</b></span>`,
    `<span class="ed-stat">ชิดขวา <b>${thaiNum.format(s["align-right"])}</b></span>`,
    `<span class="ed-stat">ย่อหน้า <b>${thaiNum.format(s.indent)}</b></span>`,
    `<span class="ed-stat">ระยะบน <b>${thaiNum.format(s["spacing-top"])}</b></span>`,
    `<span class="ed-stat">ระยะล่าง <b>${thaiNum.format(s["spacing-bottom"])}</b></span>`,
  ].join("");

  // ปุ่มล้างหน้านี้ — ใช้ได้เมื่อมีหน้าปัจจุบันและมีรายการบนหน้านั้น
  const pageIds = state.slug && state.page ? pageEditorial(state.slug, state.page) : [];
  els.edClearPageBtn.disabled = !pageIds.length;
  els.edClearPageBtn.textContent = state.page
    ? `🗑 ล้างหน้านี้ (หน้า ${thaiNum.format(state.page)} · ${thaiNum.format(pageIds.length)})`
    : "🗑 ล้างหน้านี้";
}

function renderEditorialPanel() {
  const entries = allEffectiveEditorial();
  els.editorialStats.textContent = entries.length
    ? `แก้ใน localStorage แล้วกด “ส่งออก Editorial” ไปวางในไฟล์`
    : "ยังไม่มีรายการแก้ไข — ลากเลือกข้อความในหน้าอ่านเพื่อเริ่ม";
  renderEditorialStats();

  if (!entries.length) {
    els.editorialList.innerHTML = `
      <div class="empty"><b>ยังไม่มีรายการแก้ไข</b>ลากเลือกข้อความในหน้าอ่าน แล้วเลือกตัวหนา/ตัวเอียง/สี/แก้ข้อความ</div>`;
    return;
  }

  const groups = new Map();
  for (const entry of entries) {
    if (!bookMeta(entry.slug)) continue;
    if (!groups.has(entry.slug)) groups.set(entry.slug, []);
    groups.get(entry.slug).push(entry);
  }

  els.editorialList.innerHTML = [...groups.entries()].map(([slug, items]) => {
    const book = bookMeta(slug);
    return items
      .sort((a, b) => a.page - b.page || a.start - b.start)
      .map((entry) => {
        const badge = editorialBadge(entry);
        const badgeStyle = badge.color ? ` style="--bdg:${safeColor(badge.color)}"` : "";
        return `
        <div class="ed-entry" data-ed-id="${escapeHtml(entry.id)}">
          <div class="ed-entry-main">
            <div class="ed-entry-meta">
              <span class="ed-badge ${badge.cls}"${badgeStyle}>${badge.text}</span>
              <span>${escapeHtml(book.title)}</span>
              <a href="#/book/${slug}/${entry.page}" data-ed-jump="${escapeHtml(entry.id)}">หน้า ${thaiNum.format(entry.page)} →</a>
            </div>
            <div class="ed-preview">${editorialPreviewHtml(entry)}</div>
          </div>
          <div class="ed-entry-actions">
            ${entry.type === "replace" || entry.type === "color" || entry.type === "image-block" ? `<button type="button" class="ed-edit" data-ed-id="${escapeHtml(entry.id)}">แก้ไข</button>` : ""}
            <button type="button" class="ed-del" data-ed-id="${escapeHtml(entry.id)}">ลบ</button>
          </div>
        </div>
      `;
      }).join("");
  }).join("");
}

function openEditorialPanel() {
  renderEditorialPanel();
  els.editorialBackdrop.hidden = false;
}

/* ───────────── ดัชนีธรรม (knowledge index) ───────────── */

/* fingerprint รวม override ของ term — แก้ aliases/extraTerms แล้วดัชนีสแกนใหม่เอง */
function termIndexFingerprint() {
  return `${state.catalog.totalChars}|${JSON.stringify(state.overrides.terms || {})}`;
}

function loadStoredTermIndex() {
  const stored = readStore(LS.termIndex, null);
  if (stored && stored.version === TERM_INDEX_VERSION && stored.fingerprint === termIndexFingerprint()) {
    return stored.index;
  }
  return null;
}

async function ensureTermIndex() {
  if (state.termIndex) return state.termIndex;
  const stored = loadStoredTermIndex();
  if (stored) {
    state.termIndex = stored;
    return stored;
  }

  const progressEl = $("#indexProgress");
  const index = await buildTermIndex(state.catalog, loadBook, (done, total) => {
    if (progressEl) progressEl.textContent = `กำลังสแกนเล่ม ${thaiNum.format(done)} / ${thaiNum.format(total)}…`;
  }, state.overrides.terms);
  state.termIndex = index;
  writeStore(LS.termIndex, {
    version: TERM_INDEX_VERSION,
    fingerprint: termIndexFingerprint(),
    index,
  });
  return index;
}

function termRow(term, entry) {
  const exact = state.indexMode === "exact";
  const total = entry ? (exact ? entry.totalExact : entry.total) : 0;
  const per = entry ? (exact ? entry.perBookExact : entry.perBook) || {} : {};

  const perBook = state.catalog.books.map((book) => {
    const count = per[book.slug] || 0;
    return `<span class="ti-cell ${count ? "" : "dim"}" title="${escapeHtml(book.title)}">${thaiNum.format(book.number)}<b>${count ? thaiNum.format(count) : "·"}</b></span>`;
  }).join("");

  return `
    <div class="term-row" data-term="${escapeHtml(term)}" role="button" tabindex="0">
      <div class="term-main">
        <span class="term-name">${escapeHtml(term)}</span>
        <span class="term-total">${entry ? `${thaiNum.format(total)} หน้า` : "…"}</span>
      </div>
      <div class="term-books">${perBook}</div>
      ${entry && entry.snippet ? `<p class="term-snippet">${highlightText(entry.snippet, term)}</p>` : ""}
    </div>
  `;
}

/* หมวด → รายชื่อคำ (รวม extraTerms จาก override) */
function indexGroups() {
  const resolved = resolveTerms(state.overrides.terms);
  const groups = new Map();
  for (const r of resolved) {
    if (!groups.has(r.category)) groups.set(r.category, []);
    groups.get(r.category).push(r.term);
  }
  return [...groups.entries()].map(([category, terms]) => ({ category, terms }));
}

async function renderKnowledgeIndex() {
  const haveIndex = state.termIndex || loadStoredTermIndex();
  const groups = indexGroups();

  els.mapBody.innerHTML = `
    <div class="index-controls">
      <button class="pf-chip ${state.indexMode === "broad" ? "on" : ""}" type="button" data-imode="broad">แบบกว้าง — รวมคำประสม</button>
      <button class="pf-chip ${state.indexMode === "exact" ? "on" : ""}" type="button" data-imode="exact">เฉพาะคำโดด — “มรรค” ไม่นับ “อริยมรรค”</button>
    </div>
    ${haveIndex ? "" : `<p class="index-progress" id="indexProgress">กำลังเปิดคลังคัมภีร์เพื่อสร้างดัชนี…</p>`}
    <div id="indexGroups">
      ${groups.map((group) => `
        <div class="index-group">
          <h3>${escapeHtml(group.category)}</h3>
          <div class="index-terms" data-category="${escapeHtml(group.category)}">
            ${group.terms.map((term) => termRow(term, haveIndex ? haveIndex[term] : null)).join("")}
          </div>
        </div>
      `).join("")}
    </div>
    <p class="map-note">
      ดัชนีนับจากข้อความที่สกัดจาก PDF (ปรับเลขไทย/อารบิก สระอำ และช่องว่างแทรกให้แล้ว)
      จำนวนคือ "หน้าที่พบคำ" ไม่ใช่จำนวนครั้ง — กดคำเพื่อเปิดผลค้นหาเต็ม ·
      กำหนดคำพ้องได้ใน <code>overrides/term-overrides.json</code> ·
      <a href="#/quality">รายงานคุณภาพข้อมูล →</a>
    </p>
  `;

  if (!haveIndex) {
    const index = await ensureTermIndex();
    // ผู้ใช้อาจสลับ view ระหว่างสแกน — render เฉพาะเมื่อยังอยู่หน้าดัชนี
    if (state.view === "map") {
      const progressEl = $("#indexProgress");
      if (progressEl) progressEl.remove();
      for (const group of groups) {
        const container = els.mapBody.querySelector(`[data-category="${CSS.escape(group.category)}"]`);
        if (container) container.innerHTML = group.terms.map((term) => termRow(term, index[term])).join("");
      }
    }
  } else if (!state.termIndex) {
    state.termIndex = haveIndex;
  }
}

/* ───────────── รายงานคุณภาพข้อมูล (#/quality) ───────────── */

async function renderQuality() {
  els.qualityBody.innerHTML = `<p class="index-progress" id="qualityProgress">กำลังวิเคราะห์ทั้ง ${thaiNum.format(state.catalog.books.length)} เล่ม…</p><div id="qualityList"></div>`;
  const listEl = $("#qualityList");

  if (!state.qualityCache) state.qualityCache = new Map();

  for (const meta of state.catalog.books) {
    if (state.view !== "quality") return; // ผู้ใช้สลับหน้าไปแล้ว
    let diag = state.qualityCache.get(meta.slug);
    if (!diag) {
      const book = await loadBook(meta.slug);
      diag = diagnoseBook(book, tocOverrideFor(meta.slug));
      state.qualityCache.set(meta.slug, diag);
    }
    listEl.insertAdjacentHTML("beforeend", qualityCard(meta, diag));
    await new Promise((resolve) => setTimeout(resolve, 0));
  }

  const progressEl = $("#qualityProgress");
  if (progressEl) progressEl.textContent = "กำลังตรวจดัชนีธรรม…";

  const index = await ensureTermIndex();
  if (state.view !== "quality") return;
  if (progressEl) progressEl.remove();

  // คำที่พบ "มากผิดปกติ" = พบเกิน 60% ของหน้าในเล่มใดเล่มหนึ่ง (กว้างเกินกว่าจะใช้เป็นดัชนี)
  const noisy = [];
  for (const [term, entry] of Object.entries(index)) {
    for (const meta of state.catalog.books) {
      const count = entry.perBook[meta.slug] || 0;
      if (count > meta.pages * 0.6) {
        noisy.push(`${term} (เล่ม ${thaiNum.format(meta.number)}: ${thaiNum.format(count)}/${thaiNum.format(meta.pages)} หน้า)`);
      }
    }
  }

  listEl.insertAdjacentHTML("beforeend", `
    <div class="q-card">
      <h3>ดัชนีธรรม — คำที่กว้างเกินไป</h3>
      <p class="q-line">${noisy.length
        ? `คำต่อไปนี้พบเกิน 60% ของหน้าในบางเล่ม ควรใช้โหมด "เฉพาะคำโดด" หรือพิจารณาตัดออก: ${escapeHtml(noisy.join(" · "))}`
        : "ไม่พบคำที่กว้างผิดปกติ"}</p>
    </div>
  `);
}

function qualityCard(meta, diag) {
  const tocQuality = diag.majorCount >= 10 ? "ดี" : diag.majorCount >= 4 ? "พอใช้" : "ควรตรวจมือ";
  const typeDist = Object.entries(diag.typeDist)
    .sort((a, b) => b[1] - a[1])
    .map(([type, count]) => `<span class="ti-cell">${escapeHtml(type)}<b>${thaiNum.format(count)}</b></span>`)
    .join("") || "<span class='ti-cell dim'>ไม่มีหัวข้อหลัก</span>";

  const longList = diag.longSections.length
    ? diag.longSections.map((s) =>
      `<a href="#/section/${meta.slug}/${s.index}">${escapeHtml(s.title.slice(0, 38))} (${thaiNum.format(s.length)} หน้า)</a>`
    ).join(" · ")
    : "ไม่มี";

  return `
    <div class="q-card">
      <div class="q-head">
        <h3>เล่ม ${thaiNum.format(meta.number)} — ${escapeHtml(meta.title)}</h3>
        <span class="q-badge ${tocQuality === "ดี" ? "ok" : tocQuality === "พอใช้" ? "mid" : "bad"}">TOC: ${tocQuality}</span>
      </div>
      <p class="q-line">headings ${thaiNum.format(diag.totalHeadings)} · หัวข้อหลัก ${thaiNum.format(diag.majorCount)} · หัวข้อ ${thaiNum.format(diag.sectionCount)} จาก ${thaiNum.format(diag.pages)} หน้า</p>
      <div class="q-dist">${typeDist}</div>
      <p class="q-line"><b>หัวข้อยาวเกิน ${thaiNum.format(LONG_SECTION_PAGES)} หน้า:</b> ${longList}</p>
      <p class="q-line"><b>หน้าว่าง/สั้นกว่า ๘๐ ตัวอักษร:</b> ${diag.shortPages.length
        ? `${thaiNum.format(diag.shortPages.length)} หน้า (${diag.shortPages.slice(0, 8).map((p) => `<a href="#/book/${meta.slug}/${p}">${thaiNum.format(p)}</a>`).join(", ")}${diag.shortPages.length > 8 ? "…" : ""})`
        : "ไม่มี"}</p>
      <p class="q-line"><b>ช่องว่างแทรกกลางคำ (เช่น "ป ิ ด"):</b> ${diag.splitIssues
        ? `${thaiNum.format(diag.splitIssues)} จุด — ตัวอย่างหน้า ${diag.splitPages.map((p) => `<a href="#/book/${meta.slug}/${p}">${thaiNum.format(p)}</a>`).join(", ")} (ระบบค้นหา normalize ให้แล้ว แต่การแสดงผลยังคงตามต้นฉบับ)`
        : "ไม่พบ"}</p>
    </div>
  `;
}

/* ───────────── command palette ───────────── */

function openPalette(prefill = "") {
  state.paletteOpen = true;
  els.paletteBackdrop.hidden = false;
  els.paletteInput.value = prefill;
  renderPaletteFilters();
  els.paletteInput.focus();
  if (prefill) {
    schedulePaletteSearch();
  } else {
    renderPaletteHint();
  }
}

function closePalette() {
  state.paletteOpen = false;
  els.paletteBackdrop.hidden = true;
}

function renderPaletteFilters() {
  const scopes = [["all", "ทุกเล่ม"]];
  if (state.slug) scopes.push(["current", "เล่มนี้"]);
  scopes.push(["bookmarks", "ที่คั่นไว้"]);

  const scopeChips = scopes.map(([key, label]) =>
    `<button class="pf-chip pf-scope ${state.paletteScope === key ? "on" : ""}" type="button" data-scope="${key}">${label}</button>`
  ).join("");

  const bookChips = state.paletteScope === "all"
    ? `<span class="pf-sep"></span>` + state.catalog.books.map((book) =>
      `<button class="pf-chip ${state.paletteFilters.has(book.slug) ? "on" : ""}" type="button" data-filter="${book.slug}">${shortTitle(book)}</button>`
    ).join("")
    : "";

  els.paletteFilters.innerHTML = scopeChips + bookChips;
}

function renderPaletteHint() {
  const recent = getRecentSearches();
  els.paletteResults.innerHTML = `
    <div class="palette-hint">
      <b>ค้นหาทั้ง ${thaiNum.format(state.catalog.books.length)} เล่ม</b>
      พิมพ์คำที่ต้องการ เช่น “ญาณ” “อริยมรรค” “ปหาตัพพะ”<br>
      รองรับเลขไทย/อารบิก และช่องว่างแทรกจาก PDF เช่น “ท า” = “ทำ”
      ${recent.length ? `
        <div class="recent-queries">
          ${recent.map((q) => `<button class="chip" type="button" data-recent="${escapeHtml(q)}">${escapeHtml(q)}</button>`).join("")}
        </div>` : ""}
    </div>
  `;
}

let paletteTimer;
function schedulePaletteSearch() {
  clearTimeout(paletteTimer);
  paletteTimer = setTimeout(runPaletteSearch, 200);
}

/* คืนรายการ {slug, pages:Set|null} ตาม scope ที่เลือก */
function searchTargets() {
  if (state.paletteScope === "current" && state.slug) {
    return [{ slug: state.slug, pages: null }];
  }
  if (state.paletteScope === "bookmarks") {
    const groups = new Map();
    for (const bm of getBookmarks()) {
      if (!bookMeta(bm.slug)) continue;
      if (!groups.has(bm.slug)) groups.set(bm.slug, new Set());
      groups.get(bm.slug).add(bm.page);
    }
    return [...groups.entries()].map(([slug, pages]) => ({ slug, pages }));
  }
  const slugs = state.paletteFilters.size
    ? state.catalog.books.filter((b) => state.paletteFilters.has(b.slug)).map((b) => b.slug)
    : state.catalog.books.map((b) => b.slug);
  return slugs.map((slug) => ({ slug, pages: null }));
}

async function runPaletteSearch() {
  const query = els.paletteInput.value.trim();
  const token = ++state.searchToken;
  const normQuery = normalizeQuery(query);

  if (normQuery.length < 2) {
    renderPaletteHint();
    return;
  }

  const targets = searchTargets();
  if (!targets.length) {
    els.paletteResults.innerHTML = `<div class="palette-hint"><b>ยังไม่มีที่คั่นหน้า</b>คั่นหน้าก่อน แล้วจึงค้นเฉพาะหน้าที่คั่นไว้ได้</div>`;
    return;
  }

  const needsLoad = targets.some(({ slug }) => !state.cache.has(slug));
  if (needsLoad) {
    els.paletteResults.innerHTML = `<div class="palette-hint">กำลังเปิดคลังคัมภีร์…</div>`;
  }

  const MAX_RESULTS = 60;
  const results = [];
  let total = 0;

  for (const { slug, pages } of targets) {
    const book = await loadBook(slug);
    if (token !== state.searchToken) return; // มีการพิมพ์ใหม่ระหว่างโหลด
    for (const page of book.pageData) {
      if (pages && !pages.has(page.number)) continue;
      if (!page.text || !pageHasMatch(page, normQuery)) continue;
      total += 1;
      if (results.length < MAX_RESULTS) {
        results.push({ book, page, snippet: makeSnippet(page, query) });
      }
    }
  }

  if (token !== state.searchToken) return;
  state.paletteActive = 0;

  if (!results.length) {
    els.paletteResults.innerHTML = `
      <div class="palette-hint"><b>ไม่พบ “${escapeHtml(query)}”</b>ลองคำสั้นลง หรือสะกดแบบอื่น</div>
    `;
    return;
  }

  const scopeLabel = { all: "", current: " ในเล่มนี้", bookmarks: " ในหน้าที่คั่นไว้" }[state.paletteScope];
  els.paletteResults.innerHTML = `
    <p class="p-summary">พบ ${thaiNum.format(total)} หน้า${scopeLabel}${total > MAX_RESULTS ? ` · แสดง ${thaiNum.format(MAX_RESULTS)} รายการแรก` : ""}</p>
    ${results.map((result, index) => `
      <div class="p-result ${index === 0 ? "active" : ""}" role="option" data-index="${index}" data-slug="${result.book.slug}" data-page="${result.page.number}">
        <span class="p-result-meta">
          <span class="badge">${shortTitle(result.book)}</span>
          <span>หน้า ${thaiNum.format(result.page.number)}</span>
          <button class="p-copy" type="button" title="คัดลอกการอ้างอิง" aria-label="คัดลอกการอ้างอิง">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9.5 8.5c-2.5.7-4 2.6-4 5.5v1.5h4v-4h-2c.2-1.4 1-2.3 2-2.7Zm9 0c-2.5.7-4 2.6-4 5.5v1.5h4v-4h-2c.2-1.4 1-2.3 2-2.7Z"/></svg>
          </button>
        </span>
        <span class="p-result-snippet">${highlightText(result.snippet, query)}</span>
      </div>
    `).join("")}
  `;
}

function movePaletteActive(delta) {
  const items = els.paletteResults.querySelectorAll(".p-result");
  if (!items.length) return;
  state.paletteActive = (state.paletteActive + delta + items.length) % items.length;
  items.forEach((item, index) => item.classList.toggle("active", index === state.paletteActive));
  items[state.paletteActive].scrollIntoView({ block: "nearest" });
}

function openPaletteActive() {
  const item = els.paletteResults.querySelector(`.p-result[data-index="${state.paletteActive}"]`);
  if (!item) return;
  const query = els.paletteInput.value.trim();
  saveRecentSearch(query);
  closePalette();
  goTo(item.dataset.slug, Number(item.dataset.page), query);
}

/* ───────────── events ───────────── */

// ห้องสมุด: เปิดเล่ม
els.shelf.addEventListener("click", (event) => {
  const tome = event.target.closest(".tome");
  if (tome) location.hash = `#/book/${tome.dataset.slug}/${tome.dataset.page}`;
});

// เปลี่ยนหน้า
els.prevPage.addEventListener("click", () => setPage(state.page - 1));
els.nextPage.addEventListener("click", () => setPage(state.page + 1));
els.pageInput.addEventListener("change", () => setPage(Number(els.pageInput.value) || 1));
els.pageSlider.addEventListener("input", () => setPage(Number(els.pageSlider.value)));

// เครื่องมืออ่าน
els.fontUp.addEventListener("click", () => bumpFont(1));
els.fontDown.addEventListener("click", () => bumpFont(-1));
els.sectionFontUp.addEventListener("click", () => bumpFont(1));
els.sectionFontDown.addEventListener("click", () => bumpFont(-1));

els.bookmarkBtn.addEventListener("click", () => {
  if (!state.book) return;
  const page = state.book.pageData[state.page - 1];
  const snippet = (page.text || "").replace(/\s+/g, " ").trim().slice(0, 130);
  const added = toggleBookmark(state.slug, state.page, snippet);
  els.bookmarkBtn.classList.toggle("on", added);
  toast(added ? "คั่นหน้านี้แล้ว" : "เอาที่คั่นออกแล้ว");
});

els.notesBtn.addEventListener("click", () => {
  location.hash = "#/notes";
});

els.citeBtn.addEventListener("click", () => {
  if (state.book) copyText(pageCitation(state.book, state.page), "คัดลอกการอ้างอิงแล้ว");
});

els.focusBtn.addEventListener("click", () => {
  document.body.classList.add("focus-mode");
  window.scrollTo({ top: 0, behavior: "instant" });
});
els.focusExit.addEventListener("click", () => document.body.classList.remove("focus-mode"));

// สารบัญ
els.tocBtn.addEventListener("click", openToc);
els.tocClose.addEventListener("click", closeToc);
els.tocBackdrop.addEventListener("click", (event) => {
  if (event.target === els.tocBackdrop) closeToc();
});
els.tocFilter.addEventListener("input", renderTocList);
els.tocModeMajor.addEventListener("click", () => {
  state.tocMode = "major";
  renderTocList();
});
els.tocModeAll.addEventListener("click", () => {
  state.tocMode = "all";
  renderTocList();
});
els.tocModeReview.addEventListener("click", () => {
  state.tocMode = "review";
  renderTocList();
});
els.tocList.addEventListener("click", (event) => {
  // โหมดตรวจสารบัญ
  if (event.target.closest("#rvCopy")) {
    copyText(reviewOverrideJson(), "คัดลอก override JSON แล้ว — วางใน overrides/toc-overrides.json");
    return;
  }
  if (event.target.closest("#rvRestore")) {
    state.reviewRemovals.delete(state.slug);
    invalidateTocCaches(state.slug);
    renderTocList();
    toast("คืนค่าหัวข้อที่ตัดออกแล้ว");
    return;
  }
  const removeBtn = event.target.closest(".rv-remove");
  if (removeBtn) {
    const removals = state.reviewRemovals.get(state.slug) || [];
    removals.push({ page: Number(removeBtn.dataset.page), title: removeBtn.dataset.title });
    state.reviewRemovals.set(state.slug, removals);
    invalidateTocCaches(state.slug);
    renderTocList();
    return;
  }

  const secBtn = event.target.closest(".toc-sec");
  if (secBtn) {
    closeToc();
    location.hash = `#/section/${state.slug}/${secBtn.dataset.sec}`;
    return;
  }
  const item = event.target.closest(".toc-item");
  if (item) {
    setPage(Number(item.dataset.page));
    closeToc();
  }
});

// หัวข้อ
els.sectionPrev.addEventListener("click", () => {
  location.hash = `#/section/${state.slug}/${els.sectionPrev.dataset.target}`;
});
els.sectionNext.addEventListener("click", () => {
  location.hash = `#/section/${state.slug}/${els.sectionNext.dataset.target}`;
});
els.sectionCiteBtn.addEventListener("click", () => {
  if (state.book && state.section) {
    copyText(sectionCitation(state.book, state.section), "คัดลอกการอ้างอิงหัวข้อแล้ว");
  }
});

// ที่คั่นหน้า: ลบ / อ้างอิง
els.bookmarkList.addEventListener("click", async (event) => {
  const cite = event.target.closest(".bm-cite");
  if (cite) {
    const book = await loadBook(cite.dataset.slug);
    copyText(pageCitation(book, Number(cite.dataset.page)), "คัดลอกการอ้างอิงแล้ว");
    return;
  }
  const remove = event.target.closest(".bm-remove");
  if (remove) {
    toggleBookmark(remove.dataset.slug, Number(remove.dataset.page), "");
    renderBookmarks();
    toast("ลบที่คั่นหน้าแล้ว");
  }
});

// โน้ตและไฮไลท์: คัดลอก / ลบ / ส่งออก / นำเข้า
els.notesList.addEventListener("click", (event) => {
  const copy = event.target.closest(".note-copy");
  if (copy) {
    const ann = getAnnotations().find((item) => item.id === copy.dataset.annId);
    if (!ann) return;
    const book = bookMeta(ann.slug);
    copyText(`${ann.quote}\n\n${ann.note ? `โน้ต: ${ann.note}\n` : ""}${pageCitation(book, ann.page)}`, "คัดลอกโน้ตแล้ว");
    return;
  }
  const remove = event.target.closest(".note-remove");
  if (remove) {
    removeAnnotation(remove.dataset.annId);
    renderNotes();
    toast("ลบโน้ตแล้ว");
  }
});

els.exportNotesBtn.addEventListener("click", () => {
  downloadTextFile(`patisambhida-notes-${new Date().toISOString().slice(0, 10)}.json`, annotationExportJson());
  toast("สำรองโน้ตแล้ว");
});

// ลบไฮไลท์ทั้งหมด (เฉพาะที่ไม่มีโน้ต — โน้ตยังอยู่ครบ)
els.deleteAllHighlightsBtn.addEventListener("click", () => {
  const ids = getAnnotations().filter((ann) => !ann.note).map((ann) => ann.id);
  if (!ids.length) return;
  if (!window.confirm(`ลบไฮไลท์ทั้งหมด ${thaiNum.format(ids.length)} รายการ? (โน้ตจะยังอยู่)`)) return;
  removeAnnotationsMany(ids);
  renderNotes();
  if (state.view === "reader" && state.book) renderPage();
  toast("ลบไฮไลท์ทั้งหมดแล้ว");
});

els.importNotesInput.addEventListener("change", async () => {
  const file = els.importNotesInput.files && els.importNotesInput.files[0];
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text());
    const incoming = Array.isArray(payload) ? payload : payload.annotations;
    if (!Array.isArray(incoming)) throw new Error("ไฟล์นี้ไม่มีข้อมูลโน้ต");
    const byId = new Map(getAnnotations().map((ann) => [ann.id, ann]));
    for (const ann of incoming) {
      if (ann && ann.id && ann.slug && Number.isFinite(ann.page)) byId.set(ann.id, ann);
    }
    writeAnnotations([...byId.values()]);
    renderNotes();
    toast("กู้คืนโน้ตแล้ว");
  } catch (error) {
    toast(`กู้คืนไม่สำเร็จ: ${error.message}`);
  } finally {
    els.importNotesInput.value = "";
  }
});

els.pageText.addEventListener("mouseup", () => {
  setTimeout(() => {
    if (state.view !== "reader") return;
    const data = selectionOffsetsInPage();
    if (data) showSelectionPopover(data);
  }, 0);
});

// Mobile (touch device) — mouseup ไม่ fire เมื่อลากหัว selection handle บน Android/iOS
// ใช้ selectionchange แทน พร้อม debounce 300ms เพื่อรอให้ handle หยุดลากก่อนแสดง toolbar
if (window.matchMedia("(pointer: coarse)").matches) {
  document.addEventListener("selectionchange", () => {
    if (state.view !== "reader") return;
    clearTimeout(state._selChangeTimer);
    state._selChangeTimer = setTimeout(() => {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed) {
        // ถ้า focus อยู่ในป๊อปอัป (เช่น textarea โน้ต หรือช่องแก้ไขข้อความ) การ collapse
        // มาจากการเปิดคีย์บอร์ด ไม่ใช่ผู้ใช้ยกเลิก selection — ห้ามปิดป๊อปอัป
        if (els.selectionPopover.contains(document.activeElement)) return;
        if (!els.selectionPopover.hidden) hideSelectionPopover(false);
        return;
      }
      const data = selectionOffsetsInPage();
      if (data) showSelectionPopover(data);
    }, 300);
  });
}

els.pageText.addEventListener("keyup", (event) => {
  if (!["Shift", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
  const data = selectionOffsetsInPage();
  if (data) showSelectionPopover(data);
});

els.highlightSelectionBtn.addEventListener("click", () => savePendingAnnotation(""));
els.removeHighlightBtn.addEventListener("click", removePendingHighlight);
els.noteSelectionBtn.addEventListener("click", () => {
  els.selectionNoteBox.hidden = false;
  els.selectionNoteInput.focus();
});
els.saveNoteSelectionBtn.addEventListener("click", () => savePendingAnnotation(els.selectionNoteInput.value));
els.cancelSelectionBtn.addEventListener("click", () => hideSelectionPopover(true));

// ย่อ / เปิดใหม่ ป๊อปอัป
els.selMinBtn.addEventListener("click", () => {
  edPopup.minimized = true;
  persistEdPopup();
  els.selectionPopover.hidden = true;
  els.edReplaceBox.hidden = true;
  els.selectionNoteBox.hidden = true;
  showFab();
});
els.selRestoreBtn.addEventListener("click", () => {
  edPopup.minimized = false;
  persistEdPopup();
  els.selRestoreBtn.hidden = true;
  els.selectionPopover.hidden = false;
  applyPopupGeometry(null);
});

// ลากป๊อปอัปด้วย header (ฟัง pointermove/up บน window เพื่อความนิ่ง ไม่หลุดเมื่อเมาส์ออกนอก header)
els.selHeader.addEventListener("pointerdown", (event) => {
  if (event.target.closest("button")) return; // ปุ่มย่อ/ปิดไม่เริ่มลาก
  event.preventDefault();
  const pop = els.selectionPopover;
  const startX = event.clientX;
  const startY = event.clientY;
  const box = pop.getBoundingClientRect();
  const ox = box.left;
  const oy = box.top;
  const onMove = (ev) => {
    const [nx, ny] = clampToViewport(ox + (ev.clientX - startX), oy + (ev.clientY - startY), pop.offsetWidth, pop.offsetHeight);
    pop.style.left = `${nx}px`;
    pop.style.top = `${ny}px`;
    edPopup.x = nx;
    edPopup.y = ny;
  };
  const onUp = () => {
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", onUp);
    persistEdPopup();
  };
  window.addEventListener("pointermove", onMove);
  window.addEventListener("pointerup", onUp);
});

// ปรับขนาดจากมุมขวาล่าง
els.selResize.addEventListener("pointerdown", (event) => {
  event.preventDefault();
  const pop = els.selectionPopover;
  const startX = event.clientX;
  const startY = event.clientY;
  const startW = pop.offsetWidth;
  const startH = pop.offsetHeight;
  const left = pop.getBoundingClientRect().left;
  const top = pop.getBoundingClientRect().top;
  const onMove = (ev) => {
    const w = Math.max(200, Math.min(startW + (ev.clientX - startX), window.innerWidth - left - 8));
    const h = Math.max(120, Math.min(startH + (ev.clientY - startY), window.innerHeight - top - 8));
    pop.style.width = `${w}px`;
    pop.style.height = `${h}px`;
    edPopup.w = w;
    edPopup.h = h;
  };
  const onUp = () => {
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", onUp);
    persistEdPopup();
  };
  window.addEventListener("pointermove", onMove);
  window.addEventListener("pointerup", onUp);
});

// resize หน้าต่าง → ดึงป๊อปอัปกลับเข้าจอ
window.addEventListener("resize", () => {
  if (els.selectionPopover.hidden) return;
  const pop = els.selectionPopover;
  const box = pop.getBoundingClientRect();
  const [nx, ny] = clampToViewport(box.left, box.top, pop.offsetWidth, pop.offsetHeight);
  pop.style.left = `${nx}px`;
  pop.style.top = `${ny}px`;
  if (edPopup.x != null) { edPopup.x = nx; edPopup.y = ny; persistEdPopup(); }
});

// editorial (แอดมิน): ปุ่มในป๊อปอัปเลือกข้อความ
els.edBoldBtn.addEventListener("click", () => savePendingEditorial("bold"));
els.edItalicBtn.addEventListener("click", () => savePendingEditorial("italic"));
// preset สี: คลิกเดียวลงสีทันที (ไม่ต้องเลือก swatch อีกขั้น)
els.edPresets.addEventListener("click", (event) => {
  const preset = event.target.closest(".ed-preset");
  if (preset) savePendingEditorial("color", { color: preset.dataset.color });
});
// หัวข้อ: คลิกเดียวใช้ขนาดหัวข้อตาม preset (เหมือน color preset)
els.edHeadings.addEventListener("click", (event) => {
  const btn = event.target.closest(".ed-heading-btn");
  if (btn) savePendingEditorial(btn.dataset.heading);
});
// จัดวาง/ระยะ (layout overrides): คลิกเดียวใช้ preset เชิงความหมาย
els.edLayouts.addEventListener("click", (event) => {
  const btn = event.target.closest(".ed-layout-btn");
  if (btn) savePendingEditorial(btn.dataset.layout);
});
els.edReplaceBtn.addEventListener("click", () => {
  els.edReplaceBox.hidden = false;
  if (state.pendingSelection) els.edReplaceInput.value = state.pendingSelection.quote;
  els.edReplaceInput.focus();
});
els.edReplaceSaveBtn.addEventListener("click", () => {
  const replacement = els.edReplaceInput.value.trim();
  if (!replacement) {
    toast("กรอกข้อความที่ถูกต้องก่อน");
    return;
  }
  savePendingEditorial("replace", { replacement });
});
els.edImageBtn.addEventListener("click", openImageInsertFromSelection);
els.edRemoveBtn.addEventListener("click", removePendingFormatting);

// ไดอะล็อกแทรก/แก้ไขรูปภาพ
els.edImageSave.addEventListener("click", saveImageDialog);
els.edImageCancel.addEventListener("click", closeImageDialog);
els.edImageBackdrop.addEventListener("click", (event) => {
  if (event.target === els.edImageBackdrop) closeImageDialog();
});
els.edImageUrl.addEventListener("input", updateImagePreview);
els.edImageUrl.addEventListener("keydown", (event) => {
  if (event.key === "Enter") { event.preventDefault(); els.edImageCaption.focus(); }
});
els.edImageCaption.addEventListener("keydown", (event) => {
  if (event.key === "Enter") { event.preventDefault(); saveImageDialog(); }
});

// แถบเครื่องมือแอดมิน
els.adminEntriesBtn.addEventListener("click", openEditorialPanel);
els.adminExitBtn.addEventListener("click", exitAdminMode);
els.adminPublishBtn.addEventListener("click", publishEditorial);
els.adminExportBtn.addEventListener("click", async () => {
  const json = editorialExportJson();
  downloadTextFile(`patisambhida-editorial-${new Date().toISOString().slice(0, 10)}.json`, json);
  await copyToClipboard(json);
  setLastExport(Date.now());
  updateAdminStatus();
  toast("คัดลอก Editorial JSON แล้ว", "วางลงใน overrides/editorial-overrides.json แล้ว deploy");
});
els.adminImportInput.addEventListener("change", async () => {
  const file = els.adminImportInput.files && els.adminImportInput.files[0];
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text());
    const entries = [];
    for (const [slug, book] of Object.entries(payload)) {
      if (slug === "_doc" || !book || !Array.isArray(book.entries)) continue;
      for (const e of book.entries) {
        if (e && e.id && EDITORIAL_TYPES.has(e.type) && Number.isFinite(e.start) && Number.isFinite(e.end)) {
          entries.push({ ...e, slug });
        }
      }
    }
    pushEditorialHistory();
    writeEditorialLocal({ entries, removed: [] });
    afterEditorialChange();
    toast(`นำเข้า Editorial แล้ว: ${thaiNum.format(entries.length)} รายการ`);
  } catch (error) {
    toast(`นำเข้าไม่สำเร็จ: ${error.message}`);
  } finally {
    els.adminImportInput.value = "";
  }
});

// ไดอะล็อกล็อกอินแอดมิน
els.adminLoginSubmit.addEventListener("click", submitAdminLogin);
els.adminLoginCancel.addEventListener("click", () => { els.adminLoginBackdrop.hidden = true; });
els.adminLoginInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") submitAdminLogin();
});
els.adminLoginBackdrop.addEventListener("click", (event) => {
  if (event.target === els.adminLoginBackdrop) els.adminLoginBackdrop.hidden = true;
});

// แผงรายการ editorial: แก้ไข / ลบ / กระโดด
els.editorialClose.addEventListener("click", () => { els.editorialBackdrop.hidden = true; });
els.editorialBackdrop.addEventListener("click", (event) => {
  if (event.target === els.editorialBackdrop) els.editorialBackdrop.hidden = true;
});
els.editorialList.addEventListener("click", (event) => {
  const jump = event.target.closest("[data-ed-jump]");
  if (jump) {
    els.editorialBackdrop.hidden = true;
    return; // ปล่อยให้ลิงก์ href ทำงานเปลี่ยนหน้า
  }
  const del = event.target.closest(".ed-del");
  if (del) {
    const entry = allEffectiveEditorial().find((e) => e.id === del.dataset.edId);
    if (entry && entry.type === "replace" && !window.confirm("ลบการแก้ไขข้อความ (replace) นี้?")) return;
    pushEditorialHistory();
    removeEditorial(del.dataset.edId);
    afterEditorialChange();
    toast("ลบรายการแก้ไขแล้ว");
    return;
  }
  const edit = event.target.closest(".ed-edit");
  if (edit) {
    const entry = allEffectiveEditorial().find((e) => e.id === edit.dataset.edId);
    if (!entry) return;
    if (entry.type === "replace") {
      const next = window.prompt("แก้ไขข้อความที่ถูกต้อง:", entry.replacement || "");
      if (next === null) return;
      const replacement = next.trim();
      if (!replacement) {
        toast("ข้อความว่าง — ไม่บันทึก");
        return;
      }
      pushEditorialHistory();
      updateEditorial(entry.id, { replacement });
      afterEditorialChange();
      toast("แก้ไขข้อความแล้ว");
    } else if (entry.type === "color") {
      const choice = window.prompt("เลือกสี: 1=คำสำคัญ (น้ำเงิน), 2=คำบาลี (ม่วง), 3=คำอธิบาย (เขียว), 4=ตรวจสอบ (แดง)", "");
      if (choice === null) return;
      const map = { 1: "#0d6efd", 2: "#8e44ad", 3: "#1e8449", 4: "#c0392b" };
      const color = map[choice.trim()];
      if (!color) {
        toast("กรุณาเลือก 1–4");
        return;
      }
      pushEditorialHistory();
      updateEditorial(entry.id, { color });
      afterEditorialChange();
      toast("เปลี่ยนสีแล้ว");
    } else if (entry.type === "image-block") {
      openImageDialog({ mode: "edit", id: entry.id }, { image: entry.image, caption: entry.caption });
    }
  }
});

// ล้างหน้านี้
els.edClearPageBtn.addEventListener("click", clearCurrentPageEditorial);

// ดัชนีธรรม: สลับโหมด / คำ → ค้นหา
els.mapBody.addEventListener("click", (event) => {
  const modeChip = event.target.closest("[data-imode]");
  if (modeChip) {
    state.indexMode = modeChip.dataset.imode;
    renderKnowledgeIndex();
    return;
  }
  const row = event.target.closest(".term-row");
  if (row) openPalette(row.dataset.term);
});
els.mapBody.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    const row = event.target.closest(".term-row");
    if (row) openPalette(row.dataset.term);
  }
});

// โหมดกลางคืน
els.themeToggle.addEventListener("click", () => {
  const dark = document.documentElement.classList.toggle("dark");
  localStorage.setItem(LS.theme, dark ? "dark" : "light");
});

// command palette
els.searchTrigger.addEventListener("click", () => openPalette());
els.paletteClose.addEventListener("click", closePalette);
els.paletteBackdrop.addEventListener("click", (event) => {
  if (event.target === els.paletteBackdrop) closePalette();
});
els.paletteInput.addEventListener("input", schedulePaletteSearch);

els.paletteFilters.addEventListener("click", (event) => {
  const chip = event.target.closest(".pf-chip");
  if (!chip) return;
  if (chip.dataset.scope) {
    state.paletteScope = chip.dataset.scope;
  } else if (state.paletteFilters.has(chip.dataset.filter)) {
    state.paletteFilters.delete(chip.dataset.filter);
  } else {
    state.paletteFilters.add(chip.dataset.filter);
  }
  renderPaletteFilters();
  els.paletteInput.focus();
  schedulePaletteSearch();
});

els.paletteResults.addEventListener("click", (event) => {
  const recent = event.target.closest("[data-recent]");
  if (recent) {
    els.paletteInput.value = recent.dataset.recent;
    els.paletteInput.focus();
    schedulePaletteSearch();
    return;
  }
  const copy = event.target.closest(".p-copy");
  if (copy) {
    const item = copy.closest(".p-result");
    const book = bookMeta(item.dataset.slug);
    copyText(pageCitation(book, Number(item.dataset.page)), "คัดลอกการอ้างอิงแล้ว");
    return;
  }
  const item = event.target.closest(".p-result");
  if (item) {
    state.paletteActive = Number(item.dataset.index);
    openPaletteActive();
  }
});

// keyboard
document.addEventListener("keydown", (event) => {
  // เข้า/เปิดไดอะล็อกโหมดแอดมิน
  if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "e") {
    event.preventDefault();
    openAdminLogin();
    return;
  }

  // undo/redo editorial (เฉพาะแอดมิน, ไม่แย่ง undo ของช่องกรอกข้อความ)
  if (state.admin && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
    const inField = event.target instanceof Element && event.target.matches("input, textarea");
    if (!inField) {
      event.preventDefault();
      if (event.shiftKey) redoEditorial();
      else undoEditorial();
      return;
    }
  }

  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    state.paletteOpen ? closePalette() : openPalette();
    return;
  }

  if (state.paletteOpen) {
    if (event.key === "Escape") closePalette();
    if (event.key === "ArrowDown") { event.preventDefault(); movePaletteActive(1); }
    if (event.key === "ArrowUp") { event.preventDefault(); movePaletteActive(-1); }
    if (event.key === "Enter") { event.preventDefault(); openPaletteActive(); }
    return;
  }

  if (event.key === "Escape") {
    if (!els.edImageBackdrop.hidden) {
      closeImageDialog();
      return;
    }
    if (!els.adminLoginBackdrop.hidden) {
      els.adminLoginBackdrop.hidden = true;
      return;
    }
    if (!els.editorialBackdrop.hidden) {
      els.editorialBackdrop.hidden = true;
      return;
    }
    if (!els.selectionPopover.hidden) {
      hideSelectionPopover(true);
      return;
    }
    if (state.tocOpen) {
      closeToc();
      return;
    }
    if (document.body.classList.contains("focus-mode")) {
      document.body.classList.remove("focus-mode");
      return;
    }
  }

  const inField = event.target instanceof Element && event.target.matches("input, textarea");
  if (state.view === "reader" && !inField) {
    if (event.key === "ArrowLeft") setPage(state.page - 1);
    if (event.key === "ArrowRight") setPage(state.page + 1);
  }
});

window.addEventListener("hashchange", () => router());

/* ───────────── init ───────────── */

(function applySavedTheme() {
  const saved = localStorage.getItem(LS.theme) || localStorage.getItem("theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  if (saved === "dark" || (!saved && prefersDark)) {
    document.documentElement.classList.add("dark");
  }
})();

applyFontSize();

/* โหลด override ถ้ามี — ไม่มีหรือพังก็ทำงานต่อด้วย heuristic ล้วน */
async function loadOverrides() {
  // no-cache: ไฟล์ override ถูกแก้บ่อยระหว่างตรวจทาน อย่าให้ browser cache ค้าง
  const [toc, terms, editorial] = await Promise.allSettled([
    loadJson("./overrides/toc-overrides.json", { cache: "no-cache" }),
    loadJson("./overrides/term-overrides.json", { cache: "no-cache" }),
    loadJson("./overrides/editorial-overrides.json", { cache: "no-cache" }),
  ]);
  if (toc.status === "fulfilled" && toc.value && typeof toc.value === "object") {
    state.overrides.tocRaw = toc.value;
    const cleaned = { ...toc.value };
    delete cleaned._doc;
    state.overrides.toc = cleaned;
  }
  if (terms.status === "fulfilled" && terms.value && typeof terms.value === "object") {
    state.overrides.terms = {
      aliases: terms.value.aliases || {},
      extraTerms: terms.value.extraTerms || {},
    };
  }
  if (editorial.status === "fulfilled" && editorial.value && typeof editorial.value === "object") {
    const cleaned = { ...editorial.value };
    delete cleaned._doc;
    state.editorialFile = cleaned;
  }
}

async function init() {
  state.catalog = await loadJson("./data/catalog.json", { cache: "no-cache" });
  await loadOverrides();

  // กู้คืนโหมดแอดมินถ้าเคยเข้าไว้
  if (localStorage.getItem(LS.admin) === "true") setAdminMode(true);

  // รองรับลิงก์เก่ารูปแบบ ?book=&page=
  const params = new URLSearchParams(location.search);
  if (params.get("book")) {
    history.replaceState(null, "", `${location.pathname}#/book/${params.get("book")}/${params.get("page") || 1}`);
  }

  await router();
}

init().catch((error) => {
  document.querySelector("#main").innerHTML =
    `<div class="view"><div class="empty"><b>โหลดข้อมูลไม่สำเร็จ</b>${escapeHtml(error.message)}<br>โปรดเปิดผ่าน local server เช่น <code>python -m http.server</code></div></div>`;
});
