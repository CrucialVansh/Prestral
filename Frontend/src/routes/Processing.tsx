import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { getDeckStatus } from '../api/client'
import type { DeckStatus } from '../types'

const POLL_MS = 1500

/**
 * Pre-computing every persona variant takes 30–60s, so this is real UI rather
 * than a spinner: per-slide progress plus thumbnails streaming in as they
 * render. Dead time the audience can watch is dead time that looks intentional.
 */
export default function Processing() {
  const { deckId } = useParams<{ deckId: string }>()
  const navigate = useNavigate()
  const [status, setStatus] = useState<DeckStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!deckId) return
    let stopped = false
    let timer: ReturnType<typeof setTimeout>

    async function poll() {
      try {
        const next = await getDeckStatus(deckId!)
        if (stopped) return
        setStatus(next)

        if (next.state === 'ready') {
          navigate(`/deck/${deckId}/0`, { replace: true })
          return
        }
        if (next.state === 'error') {
          setError(next.error ?? 'Processing failed')
          return
        }
      } catch (err) {
        if (stopped) return
        setError(err instanceof Error ? err.message : 'Lost contact with the server')
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

  const pct = Math.round((status?.progress ?? 0) * 100)

  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col justify-center gap-6 px-6">
      <div>
        <h1 className="text-lg font-medium">
          {error ? 'Something went wrong' : (status?.message ?? 'Starting up')}
        </h1>
        {!error && (
          <p className="mt-1 text-sm text-white/40">
            Writing a Marketing, Product and Engineering reading of every slide.
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

          {status && status.slidesTotal > 0 && (
            <p className="text-xs tabular-nums text-white/35">
              {status.slidesDone} of {status.slidesTotal} slides · {pct}%
            </p>
          )}

          {status && status.readyThumbnails.length > 0 && (
            <div className="grid grid-cols-4 gap-3">
              {status.readyThumbnails.map((src) => (
                <img
                  key={src}
                  src={src}
                  alt=""
                  className="animate-fadeUp aspect-video w-full rounded border border-white/10 object-cover"
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
