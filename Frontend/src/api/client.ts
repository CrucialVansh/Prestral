import type {
  Deck,
  Session,
  QueryRequest,
  QueryResponse,
  CreateSessionRequest,
  SendMessageRequest,
  DriveFileList,
  DriveImportRequest,
  ComponentType,
} from '../types'
 
/**
 * Mock is ON unless explicitly disabled, so a fresh clone runs with no backend.
 * Flip VITE_USE_MOCK=false in .env.local once pointed at a real server.
 */
export const USE_MOCK = (import.meta.env.VITE_USE_MOCK ?? 'true') !== 'false'
 
const API_BASE = import.meta.env.VITE_API_TARGET ?? 'http://localhost:8000'
 
const DEMO_ID = 'demo'
const MOCK_PROCESSING_MS = 6000
 
async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(detail || `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}
 
/** First TITLE component's text, if any — the backend doesn't return a slide title directly. */
function deriveSlideTitle(deck: Deck): Deck {
  return {
    ...deck,
    slides: deck.slides.map((slide) => ({
      ...slide,
      title: slide.components.find((c) => c.type === ('title' as ComponentType))?.text,
    })),
    aspectRatio: deck.aspectRatio ?? 16 / 9,
  }
}
 
// ---------- Decks ----------
 
export async function uploadDeck(deckFile: File, contextFiles: File[]): Promise<{ id: string }> {
  if (USE_MOCK) {
    const id = `mock_${Math.random().toString(36).slice(2, 8)}`
    mockUploads.set(id, Date.now())
    return { id }
  }
 
  const form = new FormData()
  form.append('slides', deckFile)
  // Backend accepts a single `doc` file currently — send the first context file.
  // If multiple context files are selected, only the first is sent until the
  // backend supports multiple `doc` parts.
  if (contextFiles[0]) form.append('doc', contextFiles[0])
 
  return json<{ id: string }>(
    await fetch(`${API_BASE}/api/decks/upload`, { method: 'POST', body: form }),
  )
}
 
export async function getDeck(deckId: string): Promise<Deck> {
  if (USE_MOCK) {
    const raw = await mockDeck()
    return deriveSlideTitle({ ...raw, id: deckId })
  }
  const raw = await json<Deck>(await fetch(`${API_BASE}/api/decks/${deckId}`))
  return deriveSlideTitle(raw)
}
 
export async function listDecks(): Promise<Deck[]> {
  if (USE_MOCK) return [deriveSlideTitle(await mockDeck())]
  const raw = await json<Deck[]>(await fetch(`${API_BASE}/api/decks`))
  return raw.map(deriveSlideTitle)
}
 
// ---------- Single-shot query ----------
 
export async function queryDeck(deckId: string, req: QueryRequest): Promise<QueryResponse> {
  if (USE_MOCK) {
    return { answer: `Mock answer for mode="${req.mode}"`, sources: [] }
  }
  return json<QueryResponse>(
    await fetch(`${API_BASE}/api/decks/${deckId}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    }),
  )
}
 
// ---------- Sessions ----------
 
export async function createSession(deckId: string, req: CreateSessionRequest): Promise<Session> {
  if (USE_MOCK) return mockSession(req.component_id, req.audience ?? 'general')
  return json<Session>(
    await fetch(`${API_BASE}/api/decks/${deckId}/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    }),
  )
}
 
export async function listSessions(deckId: string): Promise<Session[]> {
  if (USE_MOCK) return Array.from(mockSessions.values())
  return json<Session[]>(await fetch(`${API_BASE}/api/decks/${deckId}/sessions`))
}
 
export async function getSession(deckId: string, sessionId: string): Promise<Session> {
  if (USE_MOCK) {
    const s = mockSessions.get(sessionId)
    if (!s) throw new Error('Session not found')
    return s
  }
  return json<Session>(await fetch(`${API_BASE}/api/decks/${deckId}/sessions/${sessionId}`))
}
 
export async function updateSessionAudience(
  deckId: string,
  sessionId: string,
  audience: string,
): Promise<Session> {
  if (USE_MOCK) {
    const s = mockSessions.get(sessionId)
    if (!s) throw new Error('Session not found')
    s.audience = audience
    return s
  }
  return json<Session>(
    await fetch(`${API_BASE}/api/decks/${deckId}/sessions/${sessionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ audience }),
    }),
  )
}
 
export async function sendMessage(
  deckId: string,
  sessionId: string,
  req: SendMessageRequest,
): Promise<Session> {
  if (USE_MOCK) {
    const s = mockSessions.get(sessionId)
    if (!s) throw new Error('Session not found')
    if (req.content) s.messages.push({ role: 'user', content: req.content, created_at: new Date().toISOString() })
    s.messages.push({
      role: 'assistant',
      content: `Mock reply (${req.mode}) for audience="${s.audience}".`,
      sources: [],
      created_at: new Date().toISOString(),
    })
    return s
  }
  return json<Session>(
    await fetch(`${API_BASE}/api/decks/${deckId}/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    }),
  )
}
 
export async function deleteSession(deckId: string, sessionId: string): Promise<void> {
  if (USE_MOCK) {
    mockSessions.delete(sessionId)
    return
  }
  await fetch(`${API_BASE}/api/decks/${deckId}/sessions/${sessionId}`, { method: 'DELETE' })
}
 
// ---------- Google Drive (only wire up if the Drive UI is actually built) ----------
 
export async function getDriveAuthUrl(): Promise<{ auth_url: string; state: string }> {
  return json(await fetch(`${API_BASE}/api/storage/google/auth-url`))
}
 
export async function listDriveFiles(connectionId: string): Promise<DriveFileList> {
  return json(await fetch(`${API_BASE}/api/storage/files?connection_id=${connectionId}`))
}
 
export async function importFromDrive(req: DriveImportRequest): Promise<Deck> {
  const raw = await json<Deck>(
    await fetch(`${API_BASE}/api/storage/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    }),
  )
  return deriveSlideTitle(raw)
}
 
// ---------- Mock internals ----------
 
const mockUploads = new Map<string, number>()
const mockSessions = new Map<string, Session>()
 
let _mockDeckCache: Deck | null = null
async function mockDeck(): Promise<Deck> {
  if (!_mockDeckCache) {
    const mod = await import('../mock/deck.json')
    _mockDeckCache = mod.default as unknown as Deck
  }
  return _mockDeckCache
}
 
function mockSession(componentId: string, audience: string): Session {
  const existing = Array.from(mockSessions.values()).find((s) => s.component_id === componentId)
  if (existing) return existing
 
  const session: Session = {
    id: `sess_${Math.random().toString(36).slice(2, 8)}`,
    deck_id: DEMO_ID,
    component_id: componentId,
    audience,
    messages: [],
  }
  mockSessions.set(session.id, session)
  return session
}
 
/** Retained for Processing.tsx's fake progress bar until a real status endpoint exists. */
export function mockProgress(deckId: string): number {
  const started = mockUploads.get(deckId)
  if (!started || deckId === DEMO_ID) return 1
  return Math.min(1, (Date.now() - started) / MOCK_PROCESSING_MS)
}