import type { Deck, DeckStatus } from '../types'
import mockDeck from '../mock/deck.json'

/**
 * Mock is ON unless explicitly disabled, so a fresh clone runs with no backend.
 * Flip VITE_USE_MOCK=false in .env.local once the pipeline returns real JSON.
 */
export const USE_MOCK = (import.meta.env.VITE_USE_MOCK ?? 'true') !== 'false'

const DEMO_ID = 'demo'
const MOCK_PROCESSING_MS = 6000

/** Fake upload timestamps, so the mock processing screen behaves like the real one. */
const mockUploads = new Map<string, number>()

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(detail || `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export async function uploadDeck(
  deckFile: File,
  contextFiles: File[],
): Promise<{ deckId: string }> {
  if (USE_MOCK) {
    const id = `mock_${Math.random().toString(36).slice(2, 8)}`
    mockUploads.set(id, Date.now())
    return { deckId: id }
  }

  const form = new FormData()
  form.append('deck', deckFile)
  contextFiles.forEach((f) => form.append('context', f))

  return json<{ deckId: string }>(
    await fetch('/api/decks', { method: 'POST', body: form }),
  )
}

export async function getDeckStatus(deckId: string): Promise<DeckStatus> {
  if (USE_MOCK) return mockStatus(deckId)
  return json<DeckStatus>(await fetch(`/api/decks/${deckId}/status`))
}

export async function getDeck(deckId: string): Promise<Deck> {
  if (USE_MOCK) {
    // Every mock id resolves to the same bundled demo deck.
    return { ...(mockDeck as unknown as Deck), deckId }
  }
  return json<Deck>(await fetch(`/api/decks/${deckId}`))
}

function mockStatus(deckId: string): DeckStatus {
  const total = (mockDeck as unknown as Deck).slides.length
  const started = mockUploads.get(deckId)

  // Deep-linked demo deck: already done.
  if (!started || deckId === DEMO_ID) {
    return {
      deckId,
      state: 'ready',
      progress: 1,
      message: 'Ready',
      slidesDone: total,
      slidesTotal: total,
      readyThumbnails: (mockDeck as unknown as Deck).slides.map((s) => s.imageUrl),
    }
  }

  const p = Math.min(1, (Date.now() - started) / MOCK_PROCESSING_MS)
  const done = Math.floor(p * total)

  let state: DeckStatus['state'] = 'rendering'
  let message = 'Rendering slides'
  if (p >= 1) {
    state = 'ready'
    message = 'Ready'
  } else if (p > 0.35) {
    state = 'analysing'
    message = `Analysing slide ${Math.min(done + 1, total)} of ${total}`
  }

  return {
    deckId,
    state,
    progress: p,
    message,
    slidesDone: done,
    slidesTotal: total,
    readyThumbnails: (mockDeck as unknown as Deck).slides
      .slice(0, done)
      .map((s) => s.imageUrl),
  }
}
