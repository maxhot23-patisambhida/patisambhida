# Cloudflare Pages Deployment Guide — ปฏิสัมภิทามรรค (Patisambhida)

This project is a **plain static single-page app** with **no build step**. The entire
deployable site lives in the `web/` directory. There is no `package.json`, no bundler,
and no server/backend — Cloudflare Pages just serves the files as-is.

---

## 1. Build command

**None.** Leave the build command **empty**.

- There is no `package.json`, no Vite, no npm scripts — nothing to compile.
- `scripts/build_content.py` regenerates `web/data/*.json` from the source PDFs, but that
  is an **offline authoring step** run locally by the maintainer. It must **not** run on
  Cloudflare's build infrastructure (it needs the PDFs and Python, and the generated JSON
  is already committed under `web/data/`).

| Setting | Value |
|---|---|
| Build command | *(leave blank)* |
| Build output directory | `web` |
| Root directory | *(repository root — default)* |

---

## 2. Output directory

```
web
```

Everything served to the browser is inside `web/`:

```
web/
├── index.html          ← entry point
├── app.js              ← main application
├── knowledge.js        ← term/knowledge index
├── styles.css
├── assets/             ← hero images (jpg/png) + README
├── data/               ← book-01..08.json, catalog.json (~9 MB, generated)
├── overrides/          ← editorial / term / toc override JSON (read at runtime)
├── editorial-images/   ← inline SVG/image assets
└── README.md           ← (optional to deploy; harmless)
```

All references are **relative** (`./styles.css`, `./data/<slug>.json`,
`./overrides/*.json`), so the site works from any path root without extra configuration.

---

## 3. Framework

**Plain static site — not Vite, not a framework.**

- No build tooling, no `node_modules`, no transpilation.
- Vanilla HTML + CSS + ES modules loaded directly by the browser.
- External CDN dependency: Google Fonts (`Noto Sans Thai` / `Noto Serif Thai`) loaded via
  `<link>` — no bundling required.
- Client-side state (bookmarks, notes, editorial admin layer) is stored in the browser
  (`localStorage`). There is **no backend, database, or auth service**.

On the Cloudflare Pages "Framework preset" dropdown, choose **None**.

---

## 4. Files that should be ignored (do NOT deploy)

These exist in the repository but must **not** be uploaded to Pages. The simplest way to
exclude them is to set the **build output directory to `web`** — Pages then publishes only
`web/` and ignores everything else automatically. The items below are listed for awareness
and in case you deploy from a different root.

| Path | Why exclude |
|---|---|
| `pdf/` | ~8 source PDFs — large, not part of the website |
| `scripts/` | Python content-generation tooling (incl. `__pycache__/`) |
| `scripts/__pycache__/` | Python bytecode cache |
| `*.json` at repo root (`patisambhida-editorial-2026-*.json`) | Local editorial export/backups, not site content |
| `.claude/` | Local editor/session config |
| `web/README.md`, `web/assets/README.md`, `web/editorial-images/README.md` | Docs only — harmless if deployed, but not needed |

If you deploy via Wrangler/CLI **or** want belt-and-suspenders exclusion, add a
`.gitignore` / `.cfignore` (this guide does not create one — file creation is limited to
this document). Recommended entries:

```gitignore
# not part of the deployed site
pdf/
scripts/
__pycache__/
patisambhida-editorial-*.json
.claude/
```

> Note: `web/data/` is large (~9 MB) but **must be deployed** — it is the book content the
> app fetches at runtime. Do not exclude it.

---

## 5. Cloudflare Pages settings required

### Routing — no SPA fallback needed
The app uses **hash-based routing** (`#/book/...`, `#/section/...`, `#/bookmarks`, etc.).
Hash fragments never reach the server, so **you do NOT need a `_redirects` SPA catch-all**
(`/* /index.html 200`). The only server-served path is `/` → `index.html`, which Pages
handles by default. Deep links work because the part after `#` is resolved client-side.

### Recommended dashboard configuration

| Field | Value |
|---|---|
| Framework preset | None |
| Build command | *(empty)* |
| Build output directory | `web` |
| Root directory | *(repo root)* |
| Environment variables | *(none required)* |
| Node version | *(irrelevant — no build)* |

### Two ways to deploy

**A. Git integration (dashboard)**
1. Connect the repository.
2. Build command: empty. Output directory: `web`.
3. Save & Deploy. Pages publishes the contents of `web/`.

**B. Direct upload (Wrangler — no build server)**
Because there's nothing to build, you can upload `web/` directly:

```bash
# one-time
npm install -g wrangler
wrangler login

# deploy the static folder as the site root
wrangler pages deploy web --project-name patisambhida
```

This uploads only `web/`, sidestepping all the ignore concerns in section 4.

### Optional hardening (not required to work)
- **Caching:** `web/data/*.json` and `web/overrides/*.json` are fetched with
  `cache: "no-cache"` in code so editors always see fresh content. Pages' default static
  caching is fine; no custom `_headers` file is required.
- **Custom headers:** if you later want security headers (CSP, etc.), add a `web/_headers`
  file — but note the app loads Google Fonts from `fonts.googleapis.com` /
  `fonts.gstatic.com`, so any CSP must allow those origins.

---

## Summary

| Question | Answer |
|---|---|
| Build command | none (leave empty) |
| Output directory | `web` |
| Framework | plain static (not Vite / not a framework) |
| Ignore | `pdf/`, `scripts/`, root `*.json` exports, `.claude/` |
| SPA `_redirects` | not needed (hash routing) |
| Env vars / backend | none |

Fastest path: `wrangler pages deploy web --project-name patisambhida`.
