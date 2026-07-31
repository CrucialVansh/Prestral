# Prestral FastAPI backend

Upload a PowerPoint deck (`.pptx`) plus a supporting document (`.docx` or `.pdf`).
The API parses slide components (with normalized bounding boxes), embeds the document,
and uses Mistral to attach deeper context to each component. A separate query endpoint
supports ask / summarize / explain over the deck using the document as grounding.

## Setup

```bash
cd Backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set MISTRAL_API_KEY=...
```

## Run

```bash
cd Backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `POST` | `/api/decks/upload` | Upload slides + doc; returns full analysis |
| `GET` | `/api/decks` | List processed decks (in-memory) |
| `GET` | `/api/decks/{deck_id}` | Re-fetch a processed deck |
| `POST` | `/api/decks/{deck_id}/query` | Single-shot ask / summarize / explain |
| `POST` | `/api/decks/{deck_id}/sessions` | Get-or-create chat session for a `component_id` (optional `audience`) |
| `GET` | `/api/decks/{deck_id}/sessions` | List sessions (switch between component chats) |
| `GET` | `/api/decks/{deck_id}/sessions/{session_id}` | Fetch session + full message history |
| `PATCH` | `/api/decks/{deck_id}/sessions/{session_id}` | Update session `audience` / role |
| `POST` | `/api/decks/{deck_id}/sessions/{session_id}/messages` | Send a multi-turn chat message |
| `DELETE` | `/api/decks/{deck_id}/sessions/{session_id}` | Delete a session |

### Upload

```bash
curl -X POST http://localhost:8000/api/decks/upload \
  -F "slides=@/path/to/deck.pptx" \
  -F "doc=@/path/to/notes.docx"
```

Response shape (simplified):

```json
{
  "id": "uuid",
  "slides_filename": "deck.pptx",
  "doc_filename": "notes.docx",
  "slides": [
    {
      "index": 0,
      "notes": "",
      "components": [
        {
          "id": "slide0-shape0",
          "type": "title",
          "bbox": {"left": 0.1, "top": 0.05, "width": 0.8, "height": 0.12},
          "text": "Quarterly Results",
          "context": "Q3 revenue grew 12% YoY driven by ...",
          "sources": ["paragraph:3"]
        }
      ]
    }
  ]
}
```

`bbox` values are fractions of slide width/height (0–1) so the frontend can overlay
hoverable/clickable regions regardless of render scale.

### Query

```bash
# Ask a question about a specific component
curl -X POST http://localhost:8000/api/decks/<deck_id>/query \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "ask",
    "question": "What drove the revenue growth?",
    "component_id": "slide0-shape1"
  }'

# Summarize a slide
curl -X POST http://localhost:8000/api/decks/<deck_id>/query \
  -H "Content-Type: application/json" \
  -d '{"mode": "summarize", "slide_index": 0}'

# Deeper explanation of a component
curl -X POST http://localhost:8000/api/decks/<deck_id>/query \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "explain",
    "component_id": "slide0-shape1"
  }'
```

### Component chat sessions

Each session is linked to one `component_id`. Opening the same hotspot again returns the
same session (unless you pass `"force_new": true`), so the UI can switch between sessions
and resume history.

Pass `audience` so explanations match the reader's role. Presets: `general`, `swe`,
`marketing`, `executive`, `sales`, `student`, `designer`, `finance` — or any free-text
role string (e.g. `"junior PM"`).

```bash
# Open (get-or-create) a session for a hotspot as a marketer
curl -s -X POST http://localhost:8000/api/decks/<deck_id>/sessions \
  -H "Content-Type: application/json" \
  -d '{"component_id":"slide0-shape1","audience":"marketing"}'

# Change role mid-session
curl -s -X PATCH http://localhost:8000/api/decks/<deck_id>/sessions/<session_id> \
  -H "Content-Type: application/json" \
  -d '{"audience":"swe"}'

# List all sessions for the deck (for a session switcher UI)
curl -s http://localhost:8000/api/decks/<deck_id>/sessions

# Multi-turn message (history is kept server-side)
curl -s -X POST http://localhost:8000/api/decks/<deck_id>/sessions/<session_id>/messages \
  -H "Content-Type: application/json" \
  -d '{"mode":"explain","content":""}'

curl -s -X POST http://localhost:8000/api/decks/<deck_id>/sessions/<session_id>/messages \
  -H "Content-Type: application/json" \
  -d '{"mode":"ask","content":"Can you expand on the enterprise upsell part?"}'
```

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `MISTRAL_API_KEY` | *(required)* | Mistral API key |
| `MISTRAL_CHAT_MODEL` | `mistral-large-latest` | Chat model for analysis / Q&A |
| `MISTRAL_EMBED_MODEL` | `mistral-embed` | Embedding model for retrieval |
| `CHUNK_MAX_CHARS` | `1000` | Max characters per doc chunk |
| `CHUNK_OVERLAP` | `150` | Overlap between consecutive chunks |
| `TOP_K` | `4` | Chunks retrieved per similarity search |

## Tests

```bash
cd Backend
source .venv/bin/activate
pip install -r requirements.txt

# Unit tests (no API calls)
pytest -m "not integration" -q

# Full live roundtrip against Mistral (needs MISTRAL_API_KEY in .env)
pytest -m integration -q
```

## Notes

- Storage is **in-memory only** — processed decks are lost when the server restarts.
- Q&A uses the uploaded document + Mistral's own knowledge; there is no external web search.
- No frontend changes are included in this backend.
