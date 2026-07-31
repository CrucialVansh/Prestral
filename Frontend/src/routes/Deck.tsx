import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AudienceSelector } from '../components/AudienceSelector'
import { ChatPanel } from '../components/ChatPanel'
import { SlideCanvas } from '../components/SlideCanvas'
import { SlideNav } from '../components/SlideNav'
import { useDeck } from '../hooks/useDeck'
import { useKeyboardNav } from '../hooks/useKeyboardNav'
import { usePersona } from '../hooks/usePersona'
import { useSession } from '../hooks/useSession'
import type { Audience } from '../types'

interface DeckProps {
  mode?: 'presenter' | 'viewer'
}

export default function Deck({ mode = 'viewer' }: DeckProps) {
  const { deckId, slideIndex } = useParams<{ deckId: string; slideIndex: string }>()
  const navigate = useNavigate()
  const isPresenter = mode === 'presenter'

  const { deck, loading, error } = useDeck(deckId)
  const { persona: globalAudience, setPersona: setGlobalPersona } = usePersona()
  const [highlightAll, setHighlightAll] = useState(false)
  const [pinnedId, setPinnedId] = useState<string | null>(null)
  
  // Chat state - not used in presenter mode
  const [chatComponentId, setChatComponentId] = useState<string | null>(null)
  const [sessionAudience, setSessionAudience] = useState<Audience>(globalAudience)
  
  // Initialize session audience from global audience
  useEffect(() => {
    setSessionAudience(globalAudience)
  }, [globalAudience])
  
  // Session management for the currently selected component
  const { 
    messages, 
    loading: sessionLoading, 
    error: sessionError, 
    sendMessage,
  } = useSession(deckId, chatComponentId ?? undefined, sessionAudience)
  
  // Update global audience when session audience changes
  const handleSessionAudienceChange = useCallback(async (aud: Audience) => {
    setSessionAudience(aud)
    setGlobalPersona(aud)
  }, [setGlobalPersona])

  const total = deck?.slides.length ?? 0
  const requested = Number(slideIndex)
  const current =
    total > 0 && Number.isInteger(requested)
      ? Math.min(Math.max(requested, 0), total - 1)
      : 0

  const basePath = isPresenter ? `/present/${deckId}` : `/deck/${deckId}`

  // A hand-typed or stale index shouldn't 404 mid-demo — clamp it into the URL.
  useEffect(() => {
    if (deck && String(current) !== slideIndex) {
      navigate(`${basePath}/${current}`, { replace: true })
    }
  }, [deck, current, slideIndex, deckId, navigate, basePath])

  // A pin belongs to one hotspot on one slide.
  useEffect(() => setPinnedId(null), [current])

  // Two arrow presses inside one frame would both read the same rendered
  // `current` and collapse into a single move. The ref advances immediately on
  // navigate, so a fast presser never loses a slide.
  const indexRef = useRef(current)
  indexRef.current = current

  const goTo = useCallback(
    (i: number) => {
      if (total === 0) return
      const next = Math.min(Math.max(i, 0), total - 1)
      indexRef.current = next
      navigate(`${basePath}/${next}`)
    },
    [basePath, deckId, navigate, total],
  )

  const step = useCallback((delta: number) => goTo(indexRef.current + delta), [goTo])

  // Warm the neighbouring slides so arrow-key navigation never flashes white.
  useEffect(() => {
    if (!deck) return
    for (const i of [current - 1, current + 1]) {
      const s = deck.slides[i]
      if (s && s.imageUrl) new Image().src = s.imageUrl
    }
  }, [deck, current])

  // Disable keyboard shortcuts for presenters (h, Escape for pins/chats)
  const keyboardHandlers = isPresenter ? {
    onPrev: () => step(-1),
    onNext: () => step(1),
    onPersona: () => {},
    onEscape: () => {},
    onToggleHighlight: () => {},
  } : {
    onPrev: () => step(-1),
    onNext: () => step(1),
    onPersona: () => {},
    onEscape: () => {
      setPinnedId(null)
      setChatComponentId(null)
    },
    onToggleHighlight: () => setHighlightAll((v) => !v),
  }

  // Cast to satisfy TypeScript
  useKeyboardNav(keyboardHandlers as Parameters<typeof useKeyboardNav>[0])

  if (loading) {
    return (
      <Centred>
        <div className="h-64 w-[56rem] max-w-[90vw] animate-pulse rounded-lg bg-white/[0.04]" />
      </Centred>
    )
  }

  if (error || !deck) {
    return (
      <Centred>
        <p className="text-sm text-red-300/80">{error ?? 'Deck not found'}</p>
      </Centred>
    )
  }

  const slide = deck.slides[current]

  return (
    <div className="flex h-full flex-col">
      {/* Deliberately nowrap: the slide is sized against a fixed chrome height,
          so a header that wrapped to two lines would push the slide off-screen.
          The title truncates instead. */}
      <header className="flex flex-nowrap items-center gap-4 border-b border-white/[0.07] px-6 py-3">
        {/* Session code for presenter, deck name for viewer */}
        {isPresenter ? (
          <div className="flex items-center gap-4">
            <span className="text-xs font-mono font-medium text-sky-300 tracking-wider">
              CODE: {deckId}
            </span>
            <span className="text-white/30">|</span>
            <h1 className="min-w-0 truncate text-sm font-medium text-white/80">{deck.slides_filename ?? 'Untitled'}</h1>
          </div>
        ) : (
          <h1 className="mr-auto min-w-0 truncate text-sm font-medium text-white/80">{deck.slides_filename ?? 'Untitled'}</h1>
        )}

        {/* Hide audience selector and highlight for presenters */}
        {!isPresenter && (
          <>
            {chatComponentId ? (
              <AudienceSelector
                audience={sessionAudience}
                onChange={handleSessionAudienceChange}
                disabled={sessionLoading}
              />
            ) : (
              <AudienceSelector
                audience={globalAudience}
                onChange={setGlobalPersona}
              />
            )}

            <button
              onClick={() => setHighlightAll((v) => !v)}
              title="Outline every hotspot  (press h)"
              data-persona-control
              className={[
                'rounded-lg border px-3 py-1.5 text-xs font-medium transition',
                highlightAll
                  ? 'border-sky-400/50 bg-sky-400/15 text-sky-200'
                  : 'border-white/10 bg-white/[0.04] text-white/50 hover:text-white/80',
              ].join(' ')}
            >
              Highlight all
            </button>
          </>
        )}
      </header>

      <main className="flex flex-1 items-center justify-center px-6 py-5">
        {slide ? (
          <div className="flex flex-1 items-center justify-center gap-4">
            <SlideCanvas
              slide={slide}
              aspectRatio={deck.aspectRatio ?? 16 / 9}
              persona={globalAudience}
              highlightAll={!isPresenter && highlightAll}
              pinnedId={!isPresenter ? pinnedId : null}
              onPin={!isPresenter ? (id: string | null) => setPinnedId(id) : undefined}
              onChatOpen={!isPresenter ? setChatComponentId : undefined}
              onCloseChat={!isPresenter ? () => setChatComponentId(null) : undefined}
              chatComponentId={!isPresenter ? chatComponentId : null}
            />
            {!isPresenter && chatComponentId && (
              <ChatPanel
                messages={messages}
                audience={sessionAudience}
                loading={sessionLoading}
                error={sessionError}
                onSend={sendMessage}
                onAudienceChange={handleSessionAudienceChange}
                onClose={() => setChatComponentId(null)}
              />
            )}
          </div>
        ) : (
          <p className="text-sm text-white/40">This deck has no slides.</p>
        )}
      </main>

      <footer className="flex items-center justify-between px-6 pb-5">
        {!isPresenter && (
          <p className="hidden text-[11px] text-white/25 md:block">
            Click any highlighted text to chat · use audience selector to change tone · h to highlight all · ←/→ to move · Esc to close
          </p>
        )}
        <div className="ml-auto">
          <SlideNav index={current} total={total} onGo={goTo} />
        </div>
      </footer>
    </div>
  )
}

function Centred({ children }: { children: ReactNode }) {
  return <div className="flex h-full items-center justify-center">{children}</div>
}
