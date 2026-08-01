# Prestral — Frontend Implementation Plan

Hover over any text on a slide, get it rewritten for *your* discipline.

## Decisions locked

| Area | Decision |
|---|---|
| Slide rendering | Backend renders slide → PNG; frontend overlays invisible hotspot divs |
| View levels | 3 discrete personas (Marketing / Product / Engineering) |
| LLM timing | Pre-compute everything at upload, cache in the deck JSON |
| In scope | Context file upload, shareable per-slide links, keyboard nav |
| Cut | Google Drive OAuth, mobile |

---

## 1. The data contract (build this first, hour 0)

Everything else depends on this. Agree it with the backend dev before either side writes a component.

```jsonc
{
  "deckId": "d_a1b2c3",
  "title": "Q3 Platform Review",
  "aspectRatio": 1.7778,
  "personas": ["marketing", "product", "engineering"],
  "slides": [
    {
      "index": 0,
      "imageUrl": "/api/decks/d_a1b2c3/slides/0.png",
      "hotspots": [
        {
          "id": "s0h2",
          // NORMALISED 0..1 fractions of slide width/height — NOT pixels
          "bbox": { "x": 0.078, "y": 0.305, "w": 0.375, "h": 0.125 },
          "originalText": "Migrate ingest to event-driven architecture",
          "variants": {
            "marketing":   { "body": "...", "mode": "simplified" },
            "product":     { "body": "...", "mode": "expanded" },
            "engineering": { "body": "...", "mode": "expanded" }
          }
        }
      ]
    }
  ]
}
```

**Why normalised coordinates matter.** python-pptx returns EMU (914400 per inch). If the backend converts to pixels, the frontend is locked to one render size and breaks on resize. Instead:

```python
x = shape.left / prs.slide_width      # 0..1
y = shape.top  / prs.slide_height
```

Frontend then positions with percentages and is responsive for free — no scaling maths, no drift when the window resizes:

```tsx
style={{ left: `${x*100}%`, top: `${y*100}%`,
         width: `${w*100}%`, height: `${h*100}%` }}
```

This is the single highest-leverage detail in the whole build. Push for it.

**On `mode`:** one `body` string per persona, not separate summary/detail fields. The prompt tells Mistral: *"rewrite for this reader — expand what they lack context on, compress what they don't need."* The `mode` flag is just so the UI can show a small "Simplified"/"Expanded" chip.

## 2. Mock-first — the key de-risking move

Within the first 30 minutes, hand-write `src/mock/deck.json` with 2–3 slides and ~5 hotspots, plus 3 exported slide PNGs in `public/mock/`. Put a `VITE_USE_MOCK=true` flag behind the API client.

The frontend is then **never blocked on the backend**. In a 24h build, backend integration always slips; this makes that slip cost nothing. It also gives you a guaranteed-working demo path if the pipeline breaks at hour 22.

## 3. Stack

Vite + React 18 + TypeScript + Tailwind, plus:

- **`@floating-ui/react`** — non-negotiable, see §5
- **`react-router-dom`** — shareable slide links
- **`react-dropzone`** — upload

**Delete `Frontend/server.js`.** A Node server earns its place only if it does SSR, auth, or secret-holding. This app is a static SPA talking to FastAPI. Use the Vite dev proxy (`/api` → `localhost:8000`) and ship the production build as static files served by FastAPI or Vercel. One less thing to deploy at 4am.

## 4. File layout

```
Frontend/
├── src/
│   ├── types.ts                  # mirror of the contract above
│   ├── api/client.ts             # uploadDeck, getDeck, pollStatus (+ mock switch)
│   ├── mock/deck.json
│   ├── routes/
│   │   ├── Upload.tsx            # /
│   │   ├── Processing.tsx        # /deck/:id/processing
│   │   └── Deck.tsx              # /deck/:id/:slideIndex
│   ├── components/
│   │   ├── SlideCanvas.tsx       # <img> + overlay layer, owns aspect ratio
│   │   ├── Hotspot.tsx           # transparent div + floating-ui trigger
│   │   ├── DetailPopover.tsx     # the payoff card
│   │   ├── PersonaSlider.tsx     # 3-stop slider
│   │   └── SlideNav.tsx          # arrows + "3 / 12"
│   ├── hooks/
│   │   ├── useDeck.ts            # fetch + cache deck JSON
│   │   ├── usePersona.ts         # persona state, persisted to localStorage
│   │   └── useKeyboardNav.ts
│   └── App.tsx
```

`SlideCanvas` is the only component that knows about geometry. It renders a relatively-positioned box with `aspect-ratio: 16/9`, the slide `<img>` filling it, and hotspots absolutely positioned in percentages. Everything else is dumb.

## 5. The hover interaction (where this demo is won or lost)

Naive `onMouseEnter`/`onMouseLeave` will feel broken. Five specific problems and their fixes:

1. **Diagonal travel gap** — user moves the cursor from hotspot toward the popover, passes over dead space, popover vanishes. Fix: `useHover(ctx, { handleClose: safePolygon() })` from Floating UI. It computes a triangular safe zone between trigger and popover. This alone justifies the dependency.
2. **Flicker while scanning** — popovers firing as the cursor crosses the slide. Fix: `delay: { open: 150, close: 100 }`.
3. **Off-screen popovers** — hotspots near slide edges. Fix: `flip()` + `shift({ padding: 8 })` middleware.
4. **Undiscoverable hotspots** — judges won't know where to hover. Fix: persistent low-opacity affordance on every hotspot (`bg-sky-400/[0.06]` + `border-b border-dotted border-sky-400/30`), lifting to `/15` on hover. Plus a "Highlight all" toggle in the toolbar for the demo.
5. **Can't read long text while holding a hover** — Fix: **click to pin**. Pinned popover gets a close button and ignores mouseleave. Cheap to build, and it's what you'll actually use when presenting.

Bonus: when the persona changes while a popover is open, crossfade the body text (~180ms). Makes the slider's effect legible instead of an instant swap the audience misses.

## 6. Persona slider

Three stops, not a continuum. Render as a segmented control *and* a slider track — snapping to 3 labelled positions. Persist to `localStorage` so a reload doesn't reset the demo. Keyboard: `1`/`2`/`3`.

Because all variants ship in the deck JSON, switching personas is a pure client-side re-render — instant, no network. Demo that explicitly: pin a popover, drag the slider, watch the text rewrite itself with zero latency.

## 7. Upload & processing

Two dropzones on `/`:

- **Deck** (required, `.pptx` only) — reject others with a clear message
- **Context files** (optional, multiple) — pdf/docx/md/txt

POST multipart → `{ deckId }` → navigate to `/deck/:id/processing`, poll `GET /api/decks/:id/status` every 1.5s for `{ state, progress, message }`.

Pre-computation takes 30–60s, so the processing screen is real UI, not a throwaway spinner: show slide-by-slide progress ("Analysing slide 4 of 12"), and stream in slide thumbnails as they render. Turns dead time into something that looks intentional.

## 8. Routing & keyboard

- `/` upload
- `/deck/:deckId/processing`
- `/deck/:deckId/:slideIndex` — slide index in the URL, so every slide is linkable

`useKeyboardNav`: `←`/`→` slides, `1`/`2`/`3` persona, `Esc` unpin, `h` highlight-all. Guard against firing while an input is focused.

## 9. Timeline (24h, frontend track)

| Hours | Work | Milestone |
|---|---|---|
| 0–1 | Contract agreed, Vite scaffold, mock fixture + PNGs | Backend unblocked to work in parallel |
| 1–4 | SlideCanvas, Hotspot overlay, SlideNav, routing — all on mock | **Slides navigable, hotspots visible** |
| 4–7 | DetailPopover, Floating UI wiring, pinning, PersonaSlider | **Core demo works end-to-end on mock** |
| 7–9 | Upload + Processing screens, API client against real endpoints | |
| 9–12 | Real backend integration, fix bbox drift | **Real deck working** |
| 12–16 | Polish: affordances, crossfade, empty/error states, loading skeletons | |
| 16–20 | Buffer — this *will* be consumed | |
| 20–22 | Deploy, run demo 3× on the actual presentation machine | |
| 22–24 | Freeze. Script the demo. Sleep. | |

**Hour 12 is the go/no-go.** If real backend data isn't rendering by then, ship the mock path and pre-generate one deck's JSON by hand. A flawless demo on canned data beats a broken one on live data.

## 10. Open questions for the team

1. **Hotspot granularity.** A bulleted list is *one* pptx shape with many paragraphs. python-pptx gives geometry for the shape, **not** per-paragraph — you'd have to estimate line heights from font size, which drifts badly with wrapping. Recommendation: **one hotspot per shape for v1.** Hovering a whole bullet block is fine. Only chase per-bullet if you're ahead at hour 14.
2. **Non-text hotspots.** Charts and diagrams are the things people *most* need explained cross-discipline. Backend already has the bounding boxes — an "explain this chart" hotspot is nearly free and would be the strongest single addition if time allows.
3. **Do elaborations cite the context files?** If a variant returns `sources: ["roadmap.pdf p.4"]`, the popover can show a provenance line. Big credibility win with judges — it's the difference between "AI paraphrased the slide" and "AI grounded this in our docs." Needs a field in the contract, so decide now, not later.
4. **Persona names.** "Marketing / Product / Engineering" — or does your demo deck suit different roles? The slider labels should match the story you tell on stage.
5. **Demo deck.** Who's making it, and is it deliberately jargon-heavy? The whole value prop is invisible unless the source slides contain terms one discipline wouldn't know. Assign this to someone early — it's usually forgotten until hour 23.
6. **Font fidelity.** LibreOffice substitutes missing fonts, which shifts text and misaligns hotspots against the rendered PNG. Test with your actual demo deck by hour 10, and stick to Arial/Calibri if it's a problem.
