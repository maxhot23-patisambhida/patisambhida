/**
 * Patisambhida — Editorial Publish Worker
 *
 * รับ editorial payload จากปุ่ม 🚀 เผยแพร่ (โหมดแอดมิน) แล้ว commit ลง GitHub
 * ผ่าน Contents API → Cloudflare Pages auto-deploy → ผู้อ่านทุกคนเห็นการแก้ไข
 *
 *   Admin browser → POST /api/publish → (this worker) → GitHub Contents API
 *                 → web/overrides/editorial-overrides.json → commit/push → Pages deploy
 *
 * Secrets (wrangler secret put): GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO
 * Vars (wrangler.jsonc):         TARGET_PATH, GITHUB_BRANCH, ALLOWED_ORIGIN
 *
 * ไม่ยุ่งกับ reader / notes / highlights / editorial rendering / storage format
 */

const DEFAULT_TARGET_PATH = "web/overrides/editorial-overrides.json";
const DEFAULT_BRANCH = "main";
const MAX_BODY_BYTES = 5 * 1024 * 1024; // 5MB
const ROUTE = "/api/publish";

const EDITORIAL_TYPES = new Set(["bold", "italic", "color", "replace", "image-block", "heading"]);

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // ── CORS preflight ───────────────────────────────────────────────
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(env, request) });
    }

    // เฉพาะ POST /api/publish เท่านั้น
    if (url.pathname !== ROUTE) {
      return json({ success: false, error: "not found" }, 404, env, request);
    }
    if (request.method !== "POST") {
      return json({ success: false, error: "method not allowed" }, 405, env, request);
    }

    try {
      return await handlePublish(request, env, request);
    } catch (err) {
      // ValidationError → 400, อื่น ๆ → 500
      const status = err && err.status === 400 ? 400 : 500;
      if (status === 400) {
        console.error("[publish] invalid payload:", err.message);
      } else {
        console.error("[publish] failed:", err && err.stack ? err.stack : err);
      }
      return json({ success: false, error: err.message || "internal error" }, status, env, request);
    }
  },
};

async function handlePublish(request, env, reqForCors) {
  // ── 1) ตรวจ config (secrets) ─────────────────────────────────────
  const token = env.GITHUB_TOKEN;
  const owner = env.GITHUB_OWNER;
  const repo = env.GITHUB_REPO;
  if (!token || !owner || !repo) {
    // misconfiguration ฝั่งเซิร์ฟเวอร์ → 500 (ไม่เผยรายละเอียด secret)
    throw new Error("worker not configured: missing GITHUB_TOKEN/OWNER/REPO");
  }
  const branch = env.GITHUB_BRANCH || DEFAULT_BRANCH;
  const targetPath = env.TARGET_PATH || DEFAULT_TARGET_PATH;

  // ── 2) อ่าน + ตรวจขนาด body ──────────────────────────────────────
  const raw = await request.text();
  const byteLen = new TextEncoder().encode(raw).length;
  if (byteLen > MAX_BODY_BYTES) {
    throw validationError(`payload too large: ${byteLen} bytes (max ${MAX_BODY_BYTES})`);
  }

  // ── 3) parse JSON ────────────────────────────────────────────────
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    throw validationError("invalid payload: body is not valid JSON");
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    throw validationError("invalid payload: expected a JSON object");
  }

  // ── 4) normalize → storage format { "book-XX": { entries: [] } } ──
  // รับได้สองรูปแบบ:
  //   (a) flat   : { entries: [ { slug, id, type, ... }, ... ] }   (ตาม Phase 3.1 spec)
  //   (b) grouped: { "book-XX": { entries: [...] }, _doc? }         (ที่ client ส่งจริง)
  const { books, count } = normalizePayload(body);

  // ── 5) GET ไฟล์ปัจจุบันเพื่ออ่าน sha + คง _doc header ───────────
  const ghHeaders = githubHeaders(token);
  const contentsUrl = `https://api.github.com/repos/${owner}/${repo}/contents/${encodeURIComponent(
    targetPath
  ).replace(/%2F/g, "/")}`;

  let sha;
  let existingDoc;
  const getRes = await fetch(`${contentsUrl}?ref=${encodeURIComponent(branch)}`, { headers: ghHeaders });
  if (getRes.status === 200) {
    const cur = await getRes.json();
    sha = cur.sha;
    try {
      const parsed = JSON.parse(base64ToUtf8(cur.content || ""));
      if (parsed && typeof parsed._doc === "string") existingDoc = parsed._doc;
    } catch {
      /* ไฟล์เดิม parse ไม่ได้ก็ข้าม — เราจะเขียนทับด้วยของใหม่ */
    }
  } else if (getRes.status !== 404) {
    const detail = await safeText(getRes);
    throw new Error(`github GET failed: ${getRes.status} ${detail}`);
  }
  // 404 = ไฟล์ยังไม่มี → สร้างใหม่ (sha undefined)

  // ── 6) ประกอบไฟล์ใหม่ (คง _doc ไว้ด้านบนถ้ามี) ──────────────────
  const fileObject = {};
  if (existingDoc) fileObject._doc = existingDoc;
  for (const slug of Object.keys(books).sort()) fileObject[slug] = books[slug];
  const newContent = JSON.stringify(fileObject, null, 2) + "\n";

  // ── 7) PUT (commit) ──────────────────────────────────────────────
  const message = `Editorial publish ${commitTimestamp()}`;
  const putBody = {
    message,
    content: utf8ToBase64(newContent),
    branch,
  };
  if (sha) putBody.sha = sha; // มี sha = update, ไม่มี = create

  const putRes = await fetch(contentsUrl, {
    method: "PUT",
    headers: { ...ghHeaders, "Content-Type": "application/json" },
    body: JSON.stringify(putBody),
  });
  if (!putRes.ok) {
    const detail = await safeText(putRes);
    throw new Error(`github PUT failed: ${putRes.status} ${detail}`);
  }
  const putJson = await putRes.json();
  const commitSha = putJson.commit && putJson.commit.sha;
  const updatedAt = new Date().toISOString();

  console.log(
    `[publish] ok — entries: ${count}, books: ${Object.keys(books).length}, commit: ${commitSha}`
  );

  return json({ success: true, commitSha, updatedAt }, 200, env, reqForCors);
}

/* ───────────── normalize / validate ───────────── */

function normalizePayload(body) {
  const books = {};
  let count = 0;

  if (Array.isArray(body.entries)) {
    // (a) flat form: { entries: [ { slug, ... } ] }
    for (const entry of body.entries) {
      const clean = validateEntry(entry, /*needSlug*/ true);
      (books[clean.slug] ||= { entries: [] }).entries.push(stripEntry(clean));
      count++;
    }
  } else {
    // (b) grouped form: { "book-XX": { entries: [...] }, _doc? }
    const slugKeys = Object.keys(body).filter((k) => k !== "_doc");
    if (slugKeys.length === 0) {
      throw validationError("invalid payload: no editorial entries found");
    }
    for (const slug of slugKeys) {
      const book = body[slug];
      if (!book || typeof book !== "object" || !Array.isArray(book.entries)) {
        throw validationError(`invalid payload: "${slug}".entries must be an array`);
      }
      books[slug] = { entries: [] };
      for (const entry of book.entries) {
        const clean = validateEntry({ ...entry, slug }, /*needSlug*/ false);
        books[slug].entries.push(stripEntry(clean));
        count++;
      }
    }
  }

  // sort ภายในเล่มให้ diff คงที่ (page → start)
  for (const slug of Object.keys(books)) {
    books[slug].entries.sort((a, b) => (a.page - b.page) || (a.start - b.start));
  }
  return { books, count };
}

function validateEntry(entry, needSlug) {
  if (!entry || typeof entry !== "object") {
    throw validationError("invalid payload: entry is not an object");
  }
  if (needSlug && typeof entry.slug !== "string") {
    throw validationError(`invalid payload: entry "${entry.id || "?"}" missing slug`);
  }
  if (typeof entry.id !== "string" || !entry.id) {
    throw validationError("invalid payload: entry missing id");
  }
  if (!EDITORIAL_TYPES.has(entry.type)) {
    throw validationError(`invalid payload: entry "${entry.id}" has bad type "${entry.type}"`);
  }
  if (!Number.isFinite(entry.start) || !Number.isFinite(entry.end) || !Number.isFinite(entry.page)) {
    throw validationError(`invalid payload: entry "${entry.id}" has non-numeric page/start/end`);
  }
  return entry;
}

// เก็บเฉพาะฟิลด์ที่จำเป็น (mirror ของ editorialExportJson ฝั่ง client)
function stripEntry(e) {
  const clean = { id: e.id, type: e.type, page: e.page, start: e.start, end: e.end };
  if (e.type === "color") clean.color = e.color;
  if (e.type === "replace") clean.replacement = e.replacement;
  if (e.type === "image-block") {
    clean.image = e.image;
    clean.caption = e.caption || "";
  }
  return clean;
}

function validationError(message) {
  const err = new Error(message);
  err.status = 400;
  return err;
}

/* ───────────── GitHub helpers ───────────── */

function githubHeaders(token) {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "patisambhida-publish-worker",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

function commitTimestamp() {
  // YYYY-MM-DD HH:mm (UTC)
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())} ${p(
    d.getUTCHours()
  )}:${p(d.getUTCMinutes())}`;
}

async function safeText(res) {
  try {
    const t = await res.text();
    return t.slice(0, 300);
  } catch {
    return "";
  }
}

/* ───────────── base64 (UTF-8 safe — รองรับภาษาไทย) ───────────── */

function utf8ToBase64(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = "";
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return btoa(bin);
}

function base64ToUtf8(b64) {
  const bin = atob(String(b64).replace(/\s/g, ""));
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}

/* ───────────── CORS / JSON response ───────────── */

function corsHeaders(env, request) {
  const allowed = env.ALLOWED_ORIGIN || "*";
  const origin = request.headers.get("Origin") || "";
  let allowOrigin = allowed;
  if (allowed !== "*") {
    // รองรับหลาย origin คั่นด้วย comma → echo เฉพาะตัวที่ตรง
    const list = allowed.split(",").map((s) => s.trim());
    allowOrigin = list.includes(origin) ? origin : list[0];
  }
  return {
    "Access-Control-Allow-Origin": allowOrigin,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

function json(obj, status, env, request) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...corsHeaders(env, request),
    },
  });
}
