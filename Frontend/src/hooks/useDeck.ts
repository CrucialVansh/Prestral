import { useEffect, useState } from 'react'
import { getDeck } from '../api/client'
import type { Deck } from '../types'

interface State {
  deck: Deck | null
  loading: boolean
  error: string | null
}

/**
 * Fetches the deck JSON once per deckId. Every persona variant ships inside it,
 * so this is the only network call the viewer ever makes — switching persona or
 * slide never touches the network.
 */
export function useDeck(deckId: string | undefined): State {
  const [state, setState] = useState<State>({ deck: null, loading: true, error: null })

  useEffect(() => {
    if (!deckId) {
      setState({ deck: null, loading: false, error: 'No deck specified' })
      return
    }

    let cancelled = false
    setState({ deck: null, loading: true, error: null })

    getDeck(deckId)
      .then((deck) => {
        if (!cancelled) setState({ deck, loading: false, error: null })
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({
            deck: null,
            loading: false,
            error: err instanceof Error ? err.message : 'Could not load deck',
          })
        }
      })

    return () => {
      cancelled = true
    }
  }, [deckId])

  return state
}
