import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { PersonaSlider } from '../components/PersonaSlider'
import { SlideCanvas } from '../components/SlideCanvas'
import { SlideNav } from '../components/SlideNav'
import { useDeck } from '../hooks/useDeck'
import { useKeyboardNav } from '../hooks/useKeyboardNav'
import { usePersona } from '../hooks/usePersona'

export default function Deck() {
  const { deckId, slideIndex } = useParams<{ deckId: string; slideIndex: string }>()
  const navigate = useNavigate()

  const { deck, loading, error } = useDeck(deckId)
  const { persona, index: personaIndex, setByIndex } = usePersona()
  const [highlightAll, setHighlightAll] = useState(false)
  const [pinnedId, setPinnedId] = useState<string | null>(null)

  const total = deck?.slides.length ?? 0
  const requested = Number(slideIndex)
  const current =
    total > 0 && Number.isInteger(requested)
      ? Math.min(Math.max(requested, 0), total - 1)
      : 0

  // A hand-typed or stale index shouldn't 404 mid-demo — clamp it into the URL.
  useEffect(() => {
    if (deck && String(current) !== slideIndex) {
      navigate(`/deck/${deckId}/${current}`, { replace: true })
    }
  }, [deck, current, slideIndex, deckId, navigate])

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
      navigate(`/deck/${deckId}/${next}`)
    },
    [deckId, navigate, total],
  )

  const step = useCallback((delta: number) => goTo(indexRef.current + delta), [goTo])

  // Warm the neighbouring slides so arrow-key navigation never flashes white.
  useEffect(() => {
    if (!deck) return
    for (const i of [current - 1, current + 1]) {
      const s = deck.slides[i]
      if (s) new Image().src = s.imageUrl
    }
  }, [deck, current])

  useKeyboardNav({
    onPrev: () => step(-1),
    onNext: () => step(1),
    onPersona: setByIndex,
    onEscape: () => setPinnedId(null),
    onToggleHighlight: () => setHighlightAll((v) => !v),
  })

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
        <h1 className="mr-auto min-w-0 truncate text-sm font-medium text-white/80">{deck.title}</h1>

        <PersonaSlider index={personaIndex} onChange={setByIndex} />

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
      </header>

      <main className="flex flex-1 items-center justify-center px-6 py-5">
        {slide ? (
          <SlideCanvas
            slide={slide}
            aspectRatio={deck.aspectRatio}
            persona={persona}
            highlightAll={highlightAll}
            pinnedId={pinnedId}
            onPin={setPinnedId}
          />
        ) : (
          <p className="text-sm text-white/40">This deck has no slides.</p>
        )}
      </main>

      <footer className="flex items-center justify-between px-6 pb-5">
        <p className="hidden text-[11px] text-white/25 md:block">
          Hover any highlighted text · click to pin · 1/2/3 to change view · ←/→ to move
        </p>
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
