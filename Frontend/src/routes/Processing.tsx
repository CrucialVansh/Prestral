import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { mockProgress } from '../api/client'

const POLL_MS = 1500
const FAKE_SLIDE_COUNT = 3

/**
 * Fake processing screen while the backend status endpoint is not yet implemented.
 * Shows a progress bar that fills over time, then redirects to the deck.
 */
export default function Processing() {
  const { deckId } = useParams<{ deckId: string }>()
  const navigate = useNavigate()
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!deckId) {
      navigate('/')
      return
    }
    let stopped = false
    let timer: ReturnType<typeof setTimeout>

    async function poll() {
      try {
        const p = mockProgress(deckId!)
        if (stopped) return
        setProgress(p)

        if (p >= 1) {
          navigate(`/deck/${deckId}/0`, { replace: true })
          return
        }
      } catch (err) {
        if (stopped) return
        setError(err instanceof Error ? err.message : 'Processing failed')
        return
      }
      if (!stopped) timer = setTimeout(poll, POLL_MS)
    }

    timer = setTimeout(poll, 0)
    return () => {
      stopped = true
      clearTimeout(timer)
    }
  }, [deckId, navigate])

  const pct = Math.round(progress * 100)
  const done = Math.round(progress * FAKE_SLIDE_COUNT)

  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col justify-center gap-6 px-6">
      <div>
        <h1 className="text-lg font-medium">
          {error ? 'Something went wrong' : 'Processing deck'}
        </h1>
        {!error && (
          <p className="mt-1 text-sm text-white/40">
            Analysing slides and extracting components.
          </p>
        )}
      </div>

      {error ? (
        <div className="space-y-4">
          <p className="text-sm text-red-300/80">{error}</p>
          <Link
            to="/"
            className="inline-block rounded-lg border border-white/15 px-4 py-2 text-sm text-white/70 hover:bg-white/[0.06]"
          >
            Start over
          </Link>
        </div>
      ) : (
        <>
          <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.07]">
            <div
              className="h-full rounded-full bg-sky-500 transition-[width] duration-500 ease-out"
              style={{ width: `${pct}%` }}
            />
          </div>

          <p className="text-xs tabular-nums text-white/35">
            {done} of {FAKE_SLIDE_COUNT} slides · {pct}%
          </p>
        </>
      )}
    </div>
  )
}
