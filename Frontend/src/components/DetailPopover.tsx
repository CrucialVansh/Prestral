import { useEffect, useState } from 'react'
import { AUDIENCE_PRESETS, type Component, type Audience } from '../types'

const FADE_MS = 180

interface Props {
  hotspot: Component
  persona: Audience
  pinned: boolean
  onUnpin: () => void
}

/**
 * The payoff card. Everything shown here is pre-computed and already in memory,
 * so a persona change is a pure re-render — but an instant text swap is
 * invisible to an audience, so the body crossfades to make the change legible.
 */
export function DetailPopover({ hotspot, persona, pinned, onUnpin }: Props) {
  const [shownPersona, setShownPersona] = useState(persona)
  const [fading, setFading] = useState(false)

  useEffect(() => {
    if (persona === shownPersona) return
    setFading(true)
    const t = setTimeout(() => {
      setShownPersona(persona)
      setFading(false)
    }, FADE_MS)
    return () => clearTimeout(t)
  }, [persona, shownPersona])

  // Get the display label for the audience
  const getAudienceLabel = (aud: Audience): string => {
    if (AUDIENCE_PRESETS.includes(aud as any)) {
      return aud
    }
    // For free-text audiences, capitalize and use as-is
    return aud.toString().charAt(0).toUpperCase() + aud.toString().slice(1)
  }

  // A component without contexts should degrade gracefully
  if (!hotspot.contexts || Object.keys(hotspot.contexts).length === 0) return null

  // Get the context for the currently selected audience, fall back to general
  const context = hotspot.contexts[shownPersona] || hotspot.contexts['general'] || ''
  if (!context) return null

  return (
    <div
      className="animate-fadeUp w-[26rem] max-w-[calc(100vw-2rem)] rounded-xl border
                 border-white/10 bg-[#161b24]/95 p-4 shadow-2xl shadow-black/60
                 backdrop-blur-sm"
    >
      <div className="mb-2 flex items-center gap-2">
        <span className="rounded-full bg-sky-400/15 px-2 py-0.5 text-[11px] font-medium text-sky-300">
          {getAudienceLabel(shownPersona)}
        </span>

        {pinned && (
          <button
            onClick={onUnpin}
            aria-label="Close"
            className="ml-auto rounded p-1 text-white/40 transition hover:bg-white/10 hover:text-white/80"
          >
            <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M3 3l10 10M13 3L3 13" strokeLinecap="round" />
            </svg>
          </button>
        )}
      </div>

      <div
        className="transition-opacity duration-[180ms]"
        style={{ opacity: fading ? 0 : 1 }}
      >
        <p className="text-[13.5px] leading-relaxed text-white/85">{context}</p>

        {/* Provenance is the difference between "the AI paraphrased this slide"
            and "the AI grounded this in our documents". Always show it if present. */}
        {hotspot.sources && hotspot.sources.length > 0 && (
          <p className="mt-3 border-t border-white/10 pt-2 text-[11px] text-white/40">
            <span className="text-white/30">Grounded in: </span>
            {hotspot.sources.join(' · ')}
          </p>
        )}
      </div>

      {!pinned && (
        <p className="mt-3 text-[10.5px] text-white/25">Click to keep this open</p>
      )}
    </div>
  )
}
