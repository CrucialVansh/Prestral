# Prestral Frontend

Vite + React + TypeScript + Tailwind SPA for hosting/joining decks, hovering
hotspots, and chatting about components.

Root [README](../README.md) covers install. Backend contracts:
[Backend/README.md](../Backend/README.md).

| | |
|-|-|
| Dev URL | http://localhost:5173 |
| API (dev) | Proxied `/api` → `http://localhost:8000` (see `vite.config.ts`) |

---

## Architecture

```
Landing (Host / Join)
    │
    ├─ Host: upload PPTX + doc → POST /api/decks/upload
    │         → /present/{deckId}/0   (presenter)
    │
    └─ Join: 6-char code → /deck/{deckId}/0   (viewer)

Deck view
    │
    ├─ useDeck          GET /api/decks/{id}  (or cache after upload)
    ├─ SlideCanvas      slide image_url + absolute % hotspots
    ├─ Hotspot          hover → DetailPopover (precomputed context)
    │                   click → open ChatPanel + useSession
    ├─ useSession       create/list/get session; POST messages
    └─ AudienceSelector role for LLM tone (PATCH session when chatting)
```

### Layout

```
Frontend/
  src/
    main.tsx / App.tsx       # routes
    api/client.ts            # fetch wrappers (+ optional mock)
    types.ts                 # mirrors backend schemas
    hooks/
      useDeck.ts
      useSession.ts          # append SendMessageResponse turns (do not replace Session)
      usePersona.ts          # audience in localStorage
      useKeyboardNav.ts
    routes/
      Landing.tsx            # host upload / join code
      Deck.tsx               # viewer + presenter modes
      Upload.tsx / Processing.tsx   # legacy paths
    components/
      SlideCanvas.tsx
      Hotspot.tsx
      DetailPopover.tsx
      ChatPanel.tsx
      AudienceSelector.tsx
      SlideNav.tsx
  public/mock/               # demo slide PNGs for mock mode
```

### Routes

| Path | Mode | Purpose |
|------|------|---------|
| `/` | — | Landing: Host or Join |
| `/present/:deckId/:slideIndex` | presenter | Host after upload |
| `/deck/:deckId/:slideIndex` | viewer | Join via code |
| `/deck/:deckId/processing` | — | Legacy mock progress screen |

### Key UX rules

1. **Hover** uses `component.context` only — no network
2. **Click** opens chat: get-or-create session for that `component_id`
3. **BBoxes** are 0–1 fractions; `SlideCanvas` is the only geometry owner
4. **Send message** returns `{ user_message, assistant_message }` — the hook
   **appends** them; never `setSession(response)` as if it were a full session
5. **Presenter vs viewer** — same `Deck` component; `mode="presenter"` from the present route

---

## Local setup

```bash
cd Frontend
cp .env.example .env.local
npm install
npm run dev
```

### `.env.local`

```bash
# Talk to the real FastAPI backend
VITE_USE_MOCK=false

# Absolute origin for API calls (optional if you only use the Vite /api proxy)
VITE_API_TARGET=http://localhost:8000
```

| Value | Effect |
|-------|--------|
| `VITE_USE_MOCK=true` | Bundled mock deck; no backend needed |
| `VITE_USE_MOCK=false` | Real upload / sessions / chat |
| Empty `VITE_API_TARGET` | Same-origin `/api` (production Docker) |
| `VITE_API_TARGET=http://localhost:8000` | Direct calls to local API |

Start the backend first (see root README). Without it, uploads and chat fail when mock is off.

---

## Scripts

```bash
npm run dev         # Vite on :5173
npm run build       # production bundle → dist/
npm run typecheck   # tsc --noEmit
npm run preview     # serve dist locally
```

---

## API client notes

`src/api/client.ts` wraps:

- `uploadDeck` → full deck JSON (cached in memory for navigation)
- `getDeck` / `listDecks`
- `createSession` / `listSessions` / `getSession` / `updateSessionAudience`
- `sendMessage` → **`SendMessageResponse`**
- Drive helpers (if UI wires them)

Types live in `src/types.ts` and should stay aligned with
`Backend/app/models/schemas.py`.

---

## Keyboard (deck view)

| Key | Action |
|-----|--------|
| ← / → | Previous / next slide |
| `h` | Toggle highlight-all hotspots |
| Esc | Close pin / chat |

---

## Related

- Backend endpoints & pipeline: [Backend/README.md](../Backend/README.md)
- Deploy (optional): [DEPLOY.md](../DEPLOY.md)
- Older API gap notes: [API-RECONCILIATION.md](./API-RECONCILIATION.md)
