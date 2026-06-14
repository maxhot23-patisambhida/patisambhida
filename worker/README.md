# Patisambhida — Editorial Publish Worker

Cloudflare Worker ที่อยู่เบื้องหลังปุ่ม **🚀 เผยแพร่** ในโหมดแอดมิน
รับ editorial payload → commit ลง GitHub → Cloudflare Pages auto-deploy → ผู้อ่านทุกคนเห็นการแก้ไข

```
Admin browser
  → POST /api/publish
  → Cloudflare Worker (this)
  → GitHub Contents API  (GET sha → PUT file → commit)
  → web/overrides/editorial-overrides.json updated on `main`
  → Cloudflare Pages auto deploy
```

> ผู้เผยแพร่ → 🚀 → GitHub commit → Cloudflare deploy → ทุกคนเห็นการแก้ไข **ในคลิกเดียว**

---

## API contract

### Request — `POST /api/publish`

รองรับ **2 รูปแบบ** (worker normalize ให้เป็น storage format เดียวกันก่อน commit):

**(a) flat** — ตามสเปก Phase 3.1:
```json
{ "entries": [ { "slug": "book-01", "id": "...", "type": "bold", "page": 8, "start": 100, "end": 120 } ] }
```

**(b) grouped** — รูปแบบที่หน้าเว็บส่งจริง (`editorialExportJson()`), ตรงกับไฟล์ปลายทาง:
```json
{ "book-01": { "entries": [ { "id": "...", "type": "bold", "page": 8, "start": 100, "end": 120 } ] } }
```

> หน้าเว็บปัจจุบันส่งแบบ (b) — ไม่ต้องแก้ client ใด ๆ. แบบ (a) มีไว้รองรับสเปก/ผู้เรียกอื่น.

### Response — `200`
```json
{ "success": true, "commitSha": "abc123…", "updatedAt": "2026-06-14T08:30:00.000Z" }
```

### Errors
| Status | เมื่อไหร่ |
|--------|----------|
| `400`  | payload ไม่ถูกต้อง (ไม่ใช่ JSON, ไม่มี entries, type ผิด, page/start/end ไม่ใช่ตัวเลข, > 5MB) |
| `404`  | path ไม่ใช่ `/api/publish` |
| `405`  | method ไม่ใช่ `POST` |
| `500`  | worker ตั้งค่าไม่ครบ หรือ GitHub API ล้มเหลว |

ไฟล์ปลายทาง: **`web/overrides/editorial-overrides.json`** (คง `_doc` header เดิมไว้อัตโนมัติ)
Commit message: `Editorial publish YYYY-MM-DD HH:mm` (UTC)

---

## Configuration

| Key | ชนิด | ค่า/ตัวอย่าง |
|-----|------|--------------|
| `GITHUB_TOKEN` | **secret** | GitHub token (ดูสิทธิ์ด้านล่าง) |
| `GITHUB_OWNER` | **secret** | `maxhot23-patisambhida` |
| `GITHUB_REPO`  | **secret** | `patisambhida` |
| `GITHUB_BRANCH`| var | `main` (default) |
| `TARGET_PATH`  | var | `web/overrides/editorial-overrides.json` (default) |
| `ALLOWED_ORIGIN`| var | origin ของ Pages เช่น `https://patisambhida.pages.dev` |

**GitHub token** — ใช้อย่างใดอย่างหนึ่ง:
- Fine-grained PAT: เข้าถึงเฉพาะ repo `patisambhida` + permission **Contents: Read and write**
- Classic PAT: scope **`repo`**

---

## Deploy

### 1) ติดตั้ง wrangler และ login
```bash
npm install -g wrangler
wrangler login
```

### 2) ตั้ง secrets (รันใน `worker/`)
```bash
wrangler secret put GITHUB_TOKEN
# วาง token แล้ว Enter

wrangler secret put GITHUB_OWNER
# พิมพ์: maxhot23-patisambhida

wrangler secret put GITHUB_REPO
# พิมพ์: patisambhida
```

### 3) ตั้งค่า CORS origin
แก้ `ALLOWED_ORIGIN` ใน `wrangler.jsonc` ให้เป็น origin จริงของหน้าเว็บ (เช่น `https://patisambhida.pages.dev`).
ถ้าใช้ Worker Route แบบ same-origin (ทางเลือก A ด้านล่าง) ไม่จำเป็นต้องใช้ CORS แต่ตั้งไว้ก็ไม่เสียหาย.

### 4) deploy
```bash
wrangler deploy
```

### 5) เชื่อม `/api/publish` เข้ากับหน้าเว็บ

**ทางเลือก A — Worker Route (แนะนำ, same-origin, ไม่ต้องพึ่ง CORS):**
มี custom domain บน Cloudflare แล้วเพิ่มใน `wrangler.jsonc`:
```jsonc
"routes": [
  { "pattern": "yourdomain.com/api/publish", "zone_name": "yourdomain.com" }
]
```
แล้ว `wrangler deploy` อีกครั้ง. หน้าเว็บเรียก `fetch("/api/publish")` ได้ทันที (ค่า `PUBLISH_ENDPOINT` เดิมในโค้ดใช้ได้เลย).

**ทางเลือก B — workers.dev (cross-origin):**
ใช้ URL `https://patisambhida-publish.<subdomain>.workers.dev/api/publish`
แล้วแก้ค่า `PUBLISH_ENDPOINT` ใน `web/app.js` ให้ชี้มาที่ URL นี้ + ตั้ง `ALLOWED_ORIGIN` ให้ตรงกับ origin ของ Pages.

---

## ทดสอบ

```bash
# ควรได้ 200 + commit จริงบน main (ระวัง: เขียนไฟล์จริง)
curl -X POST https://<worker-url>/api/publish \
  -H "Content-Type: application/json" \
  -d '{"book-01":{"entries":[{"id":"t1","type":"bold","page":8,"start":100,"end":120}]}}'

# ควรได้ 400
curl -X POST https://<worker-url>/api/publish \
  -H "Content-Type: application/json" -d '{"entries":"not-an-array"}'

# preflight — ควรได้ 204 + Access-Control-Allow-Origin
curl -X OPTIONS https://<worker-url>/api/publish -i
```

ดู log แบบ realtime:
```bash
wrangler tail
```
(`[publish] ok — entries: N …` เมื่อสำเร็จ, `[publish] failed: …` เมื่อพลาด)

---

## หมายเหตุ

- Worker นี้อยู่นอก `web/` จึง **ไม่ถูก deploy ไปกับ Pages** (Pages เสิร์ฟเฉพาะ `web/`) — ดู `DEPLOYMENT_GUIDE.md`
- Token อยู่ใน Cloudflare Secrets เท่านั้น — **ไม่มีใน browser, ไม่มีใน source**
- ไม่แตะ reader / notes / highlights / editorial rendering / storage format
- เนื่องจากแอดมินคือ "ประตูเบา" ฝั่ง client การกด publish จึงเปิดให้ทุกคนที่เข้าถึง endpoint ได้
  หากต้องการกันเพิ่ม ควรใส่ shared-secret header แล้วตรวจใน worker (นอกสโคป Phase 3.1)
```
