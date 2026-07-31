import { useCallback, useEffect, useState } from 'react'
import { PERSONAS, type PersonaId } from '../types'

const KEY = 'prestral.persona'

function initial(): PersonaId {
  const saved = localStorage.getItem(KEY) as PersonaId | null
  return saved && PERSONAS.some((p) => p.id === saved) ? saved : 'product'
}

/** Persona survives a reload, so a mid-demo refresh doesn't reset the view level. */
export function usePersona() {
  const [persona, setPersona] = useState<PersonaId>(initial)

  useEffect(() => {
    localStorage.setItem(KEY, persona)
  }, [persona])

  const setByIndex = useCallback((i: number) => {
    const next = PERSONAS[Math.max(0, Math.min(PERSONAS.length - 1, i))]
    if (next) setPersona(next.id)
  }, [])

  const index = PERSONAS.findIndex((p) => p.id === persona)

  return { persona, setPersona, index, setByIndex }
}
