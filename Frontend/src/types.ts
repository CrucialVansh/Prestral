/**
 * The contract between frontend and backend.
 * Keep in sync with the Pydantic models in Backend/schemas.py.
 */

export type PersonaId = 'marketing' | 'product' | 'engineering'

export const PERSONAS: { id: PersonaId; label: string; blurb: string }[] = [
  { id: 'marketing', label: 'Marketing', blurb: 'Plain language, outcomes and positioning' },
  { id: 'product', label: 'Product', blurb: 'Scope, tradeoffs and user impact' },
  { id: 'engineering', label: 'Engineering', blurb: 'Systems, constraints and implementation' },
]

/** Normalised 0..1 fractions of slide width/height — never pixels. */
export interface BBox {
  x: number
  y: number
  w: number
  h: number
}

export interface Variant {
  body: string
  /** Whether the LLM expanded the source text or condensed it for this reader. */
  mode: 'simplified' | 'expanded'
  /** Context files this elaboration was grounded in, e.g. "roadmap.pdf p.4". */
  sources?: string[]
}

export interface Hotspot {
  id: string
  bbox: BBox
  originalText: string
  kind?: 'text' | 'chart' | 'image'
  variants: Record<PersonaId, Variant>
}

export interface Slide {
  index: number
  imageUrl: string
  title?: string
  hotspots: Hotspot[]
}

export interface Deck {
  deckId: string
  title: string
  /** width / height, e.g. 1.7778 for 16:9 */
  aspectRatio: number
  personas: PersonaId[]
  contextFiles?: string[]
  slides: Slide[]
}

export type DeckState = 'queued' | 'rendering' | 'analysing' | 'ready' | 'error'

export interface DeckStatus {
  deckId: string
  state: DeckState
  /** 0..1 */
  progress: number
  message: string
  slidesDone: number
  slidesTotal: number
  /** Thumbnails stream in as slides finish rendering. */
  readyThumbnails: string[]
  error?: string
}
