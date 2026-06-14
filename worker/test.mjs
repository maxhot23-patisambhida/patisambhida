/**
 * worker/test.mjs — unit tests for publish payload validation
 * รัน: node worker/test.mjs
 *
 * ทดสอบ normalizePayload (ตัวที่เคย reject "align-center" ด้วย 400)
 * โดยไม่ต้องเรียก GitHub API
 */
import { normalizePayload, EDITORIAL_TYPES } from "./worker.js";

let pass = 0, fail = 0;
const ok = (name, cond) => { cond ? pass++ : (fail++, console.log("FAIL:", name)); };
const expectThrow = (name, fn) => {
  try { fn(); fail++; console.log("FAIL(no throw):", name); }
  catch (e) { ok(name, e && e.status === 400); }
};

// ── เป้าหมายหลัก: publish entry type "align-center" ต้องผ่าน ──────────
const r = normalizePayload({
  "book-01": { entries: [{ id: "layout-1", type: "align-center", page: 3, start: 10, end: 40 }] },
});
ok("align-center accepted", r.count === 1);
ok("align-center kept type", r.books["book-01"].entries[0].type === "align-center");

// ── layout types ทั้ง 6 + heading-lg/md/sm ต้องอยู่ในชุดที่อนุญาต ────
for (const t of ["align-center", "align-left", "align-right", "indent", "spacing-top", "spacing-bottom",
                 "heading-lg", "heading-md", "heading-sm"]) {
  ok(`type allowed: ${t}`, EDITORIAL_TYPES.has(t));
}

// ── flat form ก็ต้องรับ align-center ได้ ─────────────────────────────
const rf = normalizePayload({ entries: [{ slug: "book-02", id: "x", type: "align-right", page: 1, start: 0, end: 5 }] });
ok("flat align-right accepted", rf.count === 1 && rf.books["book-02"].entries[0].type === "align-right");

// ── validation เดิมต้องยังทำงาน (regression) ────────────────────────
expectThrow("still rejects bogus type", () =>
  normalizePayload({ "book-01": { entries: [{ id: "bad", type: "rainbow", page: 1, start: 0, end: 1 }] } }));
expectThrow("still rejects non-numeric", () =>
  normalizePayload({ "book-01": { entries: [{ id: "bad", type: "bold", page: 1, start: "a", end: 1 }] } }));
expectThrow("still rejects entries:string", () => normalizePayload({ entries: "nope" }));

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
