import { useCallback, useEffect, useState } from 'react'
import { AUDIENCE_PRESETS, type Audience } from '../types'

const KEY = 'prestral.audience'

function initial(): Audience {
  const saved = localStorage.getItem(KEY) as Audience | null
  return saved && AUDIENCE_PRESETS.includes(saved as any) ? saved : 'swe'
}

/** Audience survives a reload, so a mid-demo refresh doesn't reset the view level. */
export function usePersona() {
  const [persona, setPersona] = useState<Audience>(initial)

  useEffect(() => {
    localStorage.setItem(KEY, persona)
  }, [persona])

  const setByIndex = useCallback((i: number) => {
    const next = AUDIENCE_PRESETS[Math.max(0, Math.min(AUDIENCE_PRESETS.length - 1, i))]
    if (next) setPersona(next)
  }, [])

  const index = AUDIENCE_PRESETS.findIndex((p) => p === persona)

  return { persona, setPersona, index, setByIndex }
}
