# Prestral Backend — Frontend Guide

Base URL (local): `http://localhost:8000`  
Interactive API docs: **[http://localhost:8000/docs](http://localhost:8000/docs)** (Swagger)  
Alternate docs: [http://localhost:8000/redoc](http://localhost:8000/redoc)

This backend turns a **PowerPoint deck + deeper documents** into hotspot data the UI can hover/click, plus audience-aware chat about each hotspot.

---

## What you build on the frontend

| UX | Data source |
|----|-------------|
| Slide-by-slide viewer | `slides[]` from upload/import |
| Hover tooltip | `components[].context` (already filled — no extra call) |
| Clickable hotspot | Position with `components[].bbox` (0–1 fractions) |
| Chat about a shape | Create/resume a **session** with that `component_id` |
| Role-aware answers | Pass `audience` (`swe`, `marketing`, … or free text) |
| Cloud files | Google Drive connect → list → import |

---

## Setup & API keys

### 1. Install and run the backend

```bash
cd Backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — at minimum set MISTRAL_API_KEY (see below)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open:

- API: http://localhost:8000  
- Swagger: http://localhost:8000/docs  

CORS is open (`*`) for local frontend work.

**Note:** Everything is **in-memory**. Restarting the server clears decks, chat sessions, and Drive connections.

### 2. Which keys do you need?

| Feature | Required keys |
|---------|----------------|
| Local upload, analysis, hover context, chat, query | **`MISTRAL_API_KEY` only** |
| Google Drive connect / list / import | **`MISTRAL_API_KEY`** + **`GOOGLE_CLIENT_ID`** + **`GOOGLE_CLIENT_SECRET`** |

There is no frontend API key. The browser talks to this backend; the backend holds secrets in `Backend/.env` (never commit `.env`).

### 3. Mistral API key (required)

Used for embeddings (`mistral-embed`) and chat (`mistral-large-latest` by default). Without it the server will not start.

1. Create / sign in at [https://console.mistral.ai](https://console.mistral.ai)
2. Open **API Keys** and create a key
3. Put it in `Backend/.env`:

```bash
MISTRAL_API_KEY=sk-...your_key_here...
```

Optional overrides (defaults are fine for most teams):

```bash
MISTRAL_CHAT_MODEL=mistral-large-latest
MISTRAL_EMBED_MODEL=mistral-embed
```

### 4. Google Drive OAuth (optional — only for cloud import)

Skip this if the frontend only uses `POST /api/decks/upload` with local files.

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable **Google Drive API** (APIs & Services → Library → search “Google Drive API” → Enable)
4. Configure the **OAuth consent screen** (External is fine for hackathon/dev):
   - Add your Google account as a test user if the app is in Testing mode
   - Scopes used by the backend: Drive readonly + basic profile/email
5. Create credentials: **APIs & Services → Credentials → Create credentials → OAuth client ID**
   - Application type: **Web application**
   - Authorized redirect URIs — add exactly:
     - `http://localhost:8000/api/storage/google/callback`
   - If the frontend later hosts its own OAuth, you can also add that redirect; for the built-in backend flow, the URI above is required
6. Copy the **Client ID** and **Client secret** into `Backend/.env`:

```bash
GOOGLE_CLIENT_ID=........apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-........
GOOGLE_REDIRECT_URI=http://localhost:8000/api/storage/google/callback
```

7. Restart uvicorn after saving `.env`
8. Call `GET /api/storage/google/auth-url`, open `auth_url` in a browser, approve access, then copy the `connection_id` from the callback page

If `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` are empty, Drive endpoints return **503** with a clear message; local upload still works.

**Alternative:** the frontend can run Google Sign-In itself and pass `access_token` to `/api/storage/files` and `/api/storage/import` instead of using `connection_id`. You still need a Google OAuth client (often the same project); the backend then does not need the user to hit `/google/callback`.

### 5. Full `.env` example

Copy from `.env.example`, then fill secrets:

```bash
# --- Required ---
MISTRAL_API_KEY=your_mistral_api_key_here

# --- Optional Mistral tuning ---
MISTRAL_CHAT_MODEL=mistral-large-latest
MISTRAL_EMBED_MODEL=mistral-embed
CHUNK_MAX_CHARS=1000
CHUNK_OVERLAP=150
TOP_K=4

# --- Optional Google Drive ---
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/api/storage/google/callback
DRIVE_MAX_AUTO_DOCS=3
DRIVE_PREVIEW_CHARS=2500
```

### 6. Env reference

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `MISTRAL_API_KEY` | **Yes** | — | Mistral API key for LLM + embeddings |
| `MISTRAL_CHAT_MODEL` | No | `mistral-large-latest` | Chat model for analysis / Q&A / sessions |
| `MISTRAL_EMBED_MODEL` | No | `mistral-embed` | Embedding model for RAG |
| `CHUNK_MAX_CHARS` | No | `1000` | Max characters per doc chunk |
| `CHUNK_OVERLAP` | No | `150` | Overlap between consecutive chunks |
| `TOP_K` | No | `4` | Chunks retrieved per similarity search |
| `GOOGLE_CLIENT_ID` | Drive only | empty | Google OAuth client id |
| `GOOGLE_CLIENT_SECRET` | Drive only | empty | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | Drive only | `http://localhost:8000/api/storage/google/callback` | Must match Google Cloud console |
| `DRIVE_MAX_AUTO_DOCS` | No | `3` | Max docs auto-selected on Drive import |
| `DRIVE_PREVIEW_CHARS` | No | `2500` | Chars used when ranking Drive docs |

---

## End-to-end flows

### A) Local files (simplest)

```
1. POST /api/decks/upload          (multipart: slides=.pptx, doc=.docx|.pdf)
2. Save response.id
3. For each slide, overlay components using bbox
4. On click → POST /api/decks/{id}/sessions  { component_id, audience }
5. Chat    → POST /api/decks/{id}/sessions/{sessionId}/messages
```

### B) Google Drive

```
1. GET  /api/storage/google/auth-url   → open auth_url
2. User approves → callback page shows connection_id
3. GET  /api/storage/files?connection_id=...
4. User picks a PPTX from files.slides
5. POST /api/storage/import
      { connection_id, slides_file_id, auto_select_docs: true }
6. Same as local from step 2 (use returned deck id + components)
```

You can skip backend OAuth and pass a frontend Google `access_token` instead of `connection_id` on files/import.

---

## Core concepts

### Deck id
Returned by upload/import. Use it for get, query, and sessions.

### Component
One shape on a slide:

```json
{
  "id": "slide0-shape1",
  "type": "body",
  "bbox": { "left": 0.05, "top": 0.23, "width": 0.9, "height": 0.66 },
  "text": "Revenue grew 12% YoY",
  "context": "Doc says enterprise drove +18% …",
  "sources": ["notes.docx:paragraph:1"]
}
```

**Overlay math** (slide drawn in a box of size `W × H`):

- `x = bbox.left * W`
- `y = bbox.top * H`
- `w = bbox.width * W`
- `h = bbox.height * H`

Keep the slide aspect ratio matching the PPTX so hotspots line up.

### Pictures / infographics
Embedded **images** (not native charts or decorative shapes) are extracted server-side as base64 data URIs, keyed by `component_id`. The API exposes `has_image: true` on those components so the UI can badge them; the base64 itself stays on the server and is sent only to `mistral-large-latest` during analysis/chat.

### Session
One multi-turn chat tied to `(deck_id, component_id)`.

- Reopening the same component **resumes** the same session (unless `force_new: true`).
- List sessions for a **session switcher** UI.
- History lives on the server for that process lifetime.

### Audience
Controls how complex / jargon-heavy answers are.

Presets: `general`, `swe`, `marketing`, `executive`, `sales`, `student`, `designer`, `finance`  
Or free text: `"junior PM at a B2B SaaS startup"`.

Set on session create, PATCH session, per message, or on single-shot `/query`.

---

## API reference (frontend-oriented)

### Health

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness `{ "status": "ok" }` |

### Decks

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/decks/upload` | Multipart upload PPTX + DOCX/PDF → full analysis |
| `GET` | `/api/decks` | List decks in memory |
| `GET` | `/api/decks/{deck_id}` | Refetch analysis JSON |

**Upload example**

```bash
curl -X POST http://localhost:8000/api/decks/upload \
  -F "slides=@deck.pptx" \
  -F "doc=@notes.docx"
```

Response highlights: `id`, `slides[].components[]` (`id`, `type`, `bbox`, `text`, `context`, `sources`), `doc_filenames`, `source`.

### Single-shot query (no history)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/decks/{deck_id}/query` | One-off ask / summarize / explain |

```json
{
  "mode": "ask",
  "question": "What drove growth?",
  "component_id": "slide0-shape1",
  "audience": "marketing"
}
```

Prefer **sessions** when the user will follow up.

### Sessions (multi-turn chat)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/decks/{deck_id}/sessions` | Open/resume chat for a component |
| `GET` | `/api/decks/{deck_id}/sessions` | List sessions (switcher) |
| `GET` | `/api/decks/{deck_id}/sessions/{session_id}` | Full history |
| `PATCH` | `/api/decks/{deck_id}/sessions/{session_id}` | Change `audience` |
| `POST` | `/api/decks/{deck_id}/sessions/{session_id}/messages` | Send turn |
| `DELETE` | `/api/decks/{deck_id}/sessions/{session_id}` | Delete session |

**Open session**

```json
{ "component_id": "slide0-shape1", "audience": "swe" }
```

**Send message**

```json
{ "mode": "ask", "content": "Why did margin expand?" }
```

Modes: `ask` | `summarize` | `explain`  
For `ask`, `content` is required. For summarize/explain, `content` may be empty.

### Google Drive storage

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/storage/google/auth-url` | Start OAuth → `{ auth_url, state }` |
| `GET` | `/api/storage/google/callback` | Browser redirect (HTML with `connection_id`) |
| `GET` | `/api/storage/connections` | List connections |
| `DELETE` | `/api/storage/connections/{id}` | Disconnect |
| `GET` | `/api/storage/files` | List PPTX + docs (`connection_id` or `access_token`) |
| `POST` | `/api/storage/import` | Import PPTX; auto-pick relevant docs via RAG |

**Import body**

```json
{
  "connection_id": "<uuid>",
  "slides_file_id": "<drive file id>",
  "auto_select_docs": true,
  "max_docs": 3,
  "folder_id": null
}
```

Or set `auto_select_docs: false` and pass `doc_file_ids: ["...", "..."]`.

Response = same as upload, plus `selected_docs` (which Drive files were used) and `source: "google_drive"`.

**Drive env (backend)**

```bash
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/api/storage/google/callback
```

Redirect URI must match the Google Cloud OAuth client.

---

## Suggested UI wiring

1. **Upload screen** — file inputs or “Connect Google Drive”
2. **Deck viewer** — current slide image/renderer + absolute/relative overlays from `bbox`
3. **Hover card** — `component.text` + `component.context`
4. **Side chat** — on click, `POST .../sessions`, then message thread; show `assistant_message.sources`
5. **Role picker** — sets `audience` on create/PATCH (and optionally globally for new sessions)
6. **Session switcher** — `GET .../sessions` filtered/grouped by `component_id` / `title`

---

## Errors you’ll see

| Status | Typical cause |
|--------|----------------|
| `400` | Wrong file extension, empty upload, missing `question`/`content` for ask, missing Drive auth |
| `404` | Unknown `deck_id`, `session_id`, or `component_id` |
| `503` | Google OAuth not configured (`GOOGLE_CLIENT_*` missing) |
| `500` | Mistral/network/parse failure during analysis or chat |

Error body shape: `{ "detail": "..." }` (FastAPI default).

---

## Running tests

```bash
cd Backend
source .venv/bin/activate
pytest -m "not integration" -q    # fast, no live Mistral/Drive
pytest -m integration -q          # live Mistral (needs MISTRAL_API_KEY)
```

---

## OpenAPI

All routes include summaries and descriptions for Swagger. When in doubt, open `/docs` and try a request from there.

For keys and install steps, see **[Setup & API keys](#setup--api-keys)** above.
