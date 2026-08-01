# Prestral Backend

FastAPI service that turns a **PPTX + supporting document** into hoverable/
clickable slide components with doc-grounded context and audience-aware chat.

| | |
|-|-|
| Base URL (local) | `http://localhost:8000` |
| Swagger | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |

Root [README](../README.md) covers install. This doc is **architecture + endpoints**.

---

## Architecture

```
PPTX + DOCX/PDF
       │
       ▼
┌──────────────────┐
│  slide_parser    │  shapes → components (id, type, bbox 0–1, text)
│  slide_rasterizer│  per-slide PNG (LibreOffice or Pillow fallback)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  doc_parser      │  chunk document
│  embeddings      │  mistral-embed + cosine top-k
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  llm             │  per-slide: attach context/sources to each component
│  analysis        │  orchestrates pipeline → Deck in memory
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  store           │  DeckStore / SessionStore / ConnectionStore (RAM only)
└────────┬─────────┘
         │
    ┌────┴────┬──────────┐
    ▼         ▼          ▼
  decks    sessions    storage/query
  routers  (chat)      (Drive + one-shot QA)
```

### Layout

```
Backend/
  app/
    main.py              # FastAPI app, CORS, optional SPA static mount
    config.py            # pydantic-settings from .env
    store.py             # in-memory decks / sessions / Drive connections
    models/schemas.py    # request/response contracts (OpenAPI source of truth)
    routers/
      decks.py           # upload, list, get
      query.py           # single-shot ask/summarize/explain
      sessions.py        # multi-turn chat per component
      storage.py         # Google Drive OAuth + import
    services/
      slide_parser.py    # PPTX → components (+ rasterize)
      slide_rasterizer.py
      doc_parser.py
      embeddings.py
      llm.py
      analysis.py        # full ingest pipeline
      chat.py / qa.py
      google_drive.py / drive_import.py / doc_select.py
  samples/               # demo pptx + docx
  tests/
```

### Data model (frontend-facing)

- **Deck** — `id` (6-char code), filenames, `slides[]`, `aspect_ratio`, `source`
- **Slide** — `index`, `notes`, `components[]`, `image_url` (often a data-URI PNG)
- **Component** — hotspot: `id`, `type`, `bbox` `{left,top,width,height}` in **0–1**,
  `text`, precomputed `context` + `sources`, optional `has_image`
- **Session** — chat thread for one `component_id`, with `audience` and `messages[]`
- **SendMessageResponse** — `{ session_id, user_message, assistant_message, audience }`  
  (not a full session — the UI must append those turns)

### Design notes

| Topic | Behaviour |
|-------|-----------|
| Storage | **In-memory** — process restart wipes everything |
| Hover | Use `components[].context` — no extra API call |
| Chat | Create/resume session by `component_id`; RAG per turn |
| Audience | Presets (`swe`, `marketing`, …) or free text |
| Images | Embedded PPTX pictures kept server-side for multimodal LLM; client sees `has_image` |
| Slide PNG | LibreOffice preferred; Pillow compositor if missing |

---

## Setup (local)

```bash
cd Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set MISTRAL_API_KEY
uvicorn app.main:app --reload --port 8000
```

| Env | Required | Purpose |
|-----|----------|---------|
| `MISTRAL_API_KEY` | yes | Embeddings + chat |
| `MISTRAL_CHAT_MODEL` | no | Default `mistral-large-latest` |
| `MISTRAL_EMBED_MODEL` | no | Default `mistral-embed` |
| `LIBREOFFICE_PATH` | no | Path to `soffice` if not on PATH |
| `GOOGLE_CLIENT_ID` / `SECRET` | no | Drive import only |
| `STATIC_DIR` | no | Serve Vite `dist` (production Docker) |

---

## Endpoints

All JSON unless noted. Interactive schemas: **/docs**.

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness `{ "status": "ok" }` |

### Decks

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/decks/upload` | Multipart: `slides` (.pptx) + `doc` (.docx/.pdf). Returns full `DeckAnalysisResponse` (sync analysis). |
| `GET` | `/api/decks` | List in-memory decks (`DeckSummary[]`) |
| `GET` | `/api/decks/{deck_id}` | Re-fetch analyzed deck |

**Upload response (high level):**

```jsonc
{
  "id": "A1B2C3",
  "slides_filename": "deck.pptx",
  "doc_filename": "notes.docx",
  "aspect_ratio": 1.777,
  "source": "upload",
  "slides": [
    {
      "index": 0,
      "image_url": "data:image/png;base64,...",
      "components": [
        {
          "id": "slide0-shape1",
          "type": "title",
          "bbox": { "left": 0.1, "top": 0.05, "width": 0.8, "height": 0.12 },
          "text": "...",
          "context": "Doc-grounded explanation...",
          "sources": ["notes.docx:..."],
          "has_image": false
        }
      ]
    }
  ]
}
```

### One-shot query (no chat history)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/decks/{deck_id}/query` | Body: `{ mode, question?, component_id?, slide_index?, audience? }` → `{ answer, sources, ... }` |

`mode`: `ask` | `summarize` | `explain`

### Sessions (multi-turn chat)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/decks/{deck_id}/sessions` | Get-or-create by `component_id` (+ optional `audience`, `force_new`) |
| `GET` | `/api/decks/{deck_id}/sessions` | List session summaries |
| `GET` | `/api/decks/{deck_id}/sessions/{session_id}` | Full session + messages |
| `PATCH` | `/api/decks/{deck_id}/sessions/{session_id}` | Update `{ audience }` |
| `POST` | `/api/decks/{deck_id}/sessions/{session_id}/messages` | Send turn → **`SendMessageResponse`** |
| `DELETE` | `/api/decks/{deck_id}/sessions/{session_id}` | Delete session |

**Typical chat sequence:**

```
POST /api/decks/upload
POST /api/decks/{id}/sessions          { "component_id": "slide0-shape2", "audience": "swe" }
POST /api/decks/{id}/sessions/{sid}/messages
     { "mode": "ask", "content": "Why did margin expand?" }
→ { "user_message": {...}, "assistant_message": {...}, "audience": "swe", "session_id": "..." }
```

### Google Drive (optional)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/storage/google/auth-url` | Start OAuth |
| `GET` | `/api/storage/google/callback` | OAuth callback |
| `GET` | `/api/storage/connections` | List connections |
| `DELETE` | `/api/storage/connections/{id}` | Disconnect |
| `GET` | `/api/storage/files?connection_id=` | List slides/docs |
| `POST` | `/api/storage/import` | Import PPTX (+ auto-select docs) → same deck shape as upload |

Requires `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` in `.env`.

---

## Tests

```bash
cd Backend
source .venv/bin/activate
pytest -m "not integration"   # unit / API (no live Mistral)
pytest -m integration         # live Mistral — slow, needs key
```

---

## Samples

- `samples/infographic_deck.pptx`
- `samples/infographic_notes.docx`
