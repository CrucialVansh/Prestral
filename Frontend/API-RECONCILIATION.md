# Frontend/Backend API Reconciliation

What the backend actually returns/accepts vs. what the frontend currently models, and what changes on each side to close the gap. Excludes rasterization (`imageUrl`) — tracked separately as the one item the backend genuinely doesn't produce yet.

---

## 1. Deck / Component shape — rename to match backend exactly

Rather than adapting in `client.ts`, align `types.ts` directly to backend field names. Fewer moving parts, and Swagger/`/docs` stays a reliable reference for both sides.

| Backend field | Old frontend field | Action |
|---|---|---|
| `id` | `deckId` | rename frontend to `id` |
| `slides[].components[]` | `slides[].hotspots[]` | rename frontend to `components` |
| `components[].text` | `hotspots[].originalText` | rename frontend to `text` |
| `components[].context` | `hotspots[].variants[persona].body` | **replace** — single string, not per-persona (see §3) |
| `components[].sources` | `hotspots[].variants[persona].sources` | flatten to top-level `sources: string[]` |
| `components[].type` | `hotspots[].kind` | rename + expand enum (see below) |
| `slides[].notes` | *(missing)* | **add** — backend provides speaker notes, frontend doesn't surface them anywhere yet; worth a UI decision (§5) |
| `slides_filename`, `doc_filenames`, `source` | *(missing)* | **add** — useful for a "source: local upload / Google Drive" label in the UI |

`ComponentType` enum must match backend's actual values: `title | body | text_box | picture | table | chart | group | other` (frontend's old `kind: 'text' | 'chart' | 'image'` was a much smaller, non-matching set).

---

## 2. Fields the frontend needs that the backend doesn't produce — still open

| Field | Status |
|---|---|
| `imageUrl` per slide | **Not produced.** Rasterization still not implemented backend-side — this is the one blocking gap, tracked separately, not fixed by this reconciliation. |
| `title` per slide | Not produced. Cheap to add: pull from the first `ComponentType.TITLE` component's `text` if present — can actually be derived **frontend-side** from `components` with no backend change needed. |
| `aspectRatio` (deck-level) | Not produced. Needs `prs.slide_width / prs.slide_height` added to the upload response — genuinely needs a backend change, not derivable from what's already returned. |

---

## 3. Persona variants → replaced by sessions (confirmed direction)

Drop `PersonaId`, `PERSONAS`, `Variant`, and `variants` entirely from `types.ts`. The backend has no precomputed-variant concept — `context`/`sources` is the single default explanation, and persona-specific depth is handled entirely through the session API with a free-text/preset `audience` field. This was the right call made a few messages ago; this reconciliation just removes the now-dead types.

Add instead:

```ts
export type AudiencePreset =
  | 'general' | 'swe' | 'marketing' | 'executive'
  | 'sales' | 'student' | 'designer' | 'finance'

export const AUDIENCE_PRESETS: AudiencePreset[] = [
  'general', 'swe', 'marketing', 'executive', 'sales', 'student', 'designer', 'finance',
]

// audience can be a preset OR any free-text string — not a closed union
export type Audience = AudiencePreset | (string & {})
```

---

## 4. Session + query types — entirely new, frontend currently has zero session concept

```ts
export type QueryMode = 'ask' | 'summarize' | 'explain'

export interface QueryRequest {
  mode: QueryMode
  question?: string          // required when mode === 'ask'
  component_id?: string
  slide_index?: number
  audience?: Audience
}

export interface QueryResponse {
  answer: string
  sources: string[]
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  created_at: string
}

export interface Session {
  id: string
  deck_id: string
  component_id: string
  audience: Audience
  messages: ChatMessage[]
}
```

---

## 5. New backend data the frontend isn't consuming at all yet

| Backend provides | Currently used? | Suggested UI hook |
|---|---|---|
| `slides[].notes` (speaker notes) | No | Optional small "notes" toggle per slide — not required for MVP, flag as a nice-to-have |
| `doc_filenames` / `slides_filename` | No | Show as a small caption ("grounded in: notes.docx") near the deck title — cheap, reinforces trust/provenance at the deck level, not just per-hotspot |
| `source: "local" \| "google_drive"` | No | Small badge on the deck view if imported via Drive — minor polish |
| `GET /api/decks` (list all decks) | No | Not needed for current flow (upload → immediately view), but trivial to wire if you ever want a "recent decks" list |
| Full session history (`GET .../sessions`) | No | Needed for the session-switcher UI once sessions are built into `DetailPopover` |

None of these are blocking — flagging them so nothing already available gets rebuilt from scratch or silently ignored.

---

## 6. Endpoints the frontend has never called

- `POST /api/decks/{id}/query` — single-shot ask/summarize/explain, no session state. Useful for a lightweight "quick question" affordance that doesn't need session tracking.
- All six `/sessions` endpoints — core to the new chat-based hover interaction (§7).
- All Drive endpoints — only relevant if/when the Drive import UI is built.

---

## 7. `client.ts` — full rewrite reflecting the above

See accompanying `client.ts` in this delivery. Key changes: `USE_MOCK` behavior preserved, `getDeck`/`uploadDeck` renamed fields to match backend, new session functions added, mock data updated to match new shape (drop persona variants, add flat `context`).