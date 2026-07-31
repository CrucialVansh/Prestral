import { useCallback, useEffect, useRef, useState } from 'react'
import {
  createSession,
  sendMessage as apiSendMessage,
  listSessions,
  getSession,
  updateSessionAudience,
  deleteSession,
} from '../api/client'
import type { Session, ChatMessage, SendMessageRequest, Audience, QueryMode } from '../types'

interface UseSessionResult {
  session: Session | null
  messages: ChatMessage[]
  loading: boolean
  error: string | null
  sendMessage: (mode: QueryMode, content: string) => Promise<void>
  setAudience: (audience: Audience) => Promise<void>
  refresh: () => Promise<void>
  closeSession: () => Promise<void>
}

export function useSession(
  deckId: string | undefined,
  componentId: string | undefined,
  initialAudience: Audience,
): UseSessionResult {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  // Refs to avoid stale closures in async callbacks
  const deckIdRef = useRef(deckId)
  const componentIdRef = useRef(componentId)
  const sessionRef = useRef(session)
  const initialAudienceRef = useRef(initialAudience)
  
  // Update refs on every render
  deckIdRef.current = deckId
  componentIdRef.current = componentId
  sessionRef.current = session
  initialAudienceRef.current = initialAudience

  // Scroll to bottom of chat when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [session && session.messages ? session.messages.length : 0])

  const refresh = useCallback(async () => {
    // Use refs for latest values
    const currentDeckId = deckIdRef.current
    const currentComponentId = componentIdRef.current
    const currentAudience = initialAudienceRef.current
    
    if (!currentDeckId || !currentComponentId) {
      setSession(null)
      return
    }

    setLoading(true)
    setError(null)

    try {
      // Try to find existing session for this component
      const sessions = await listSessions(currentDeckId)
      const existing = sessions.find((s) => s.component_id === currentComponentId)

      if (existing) {
        // Get full session with messages
        const fullSession = await getSession(currentDeckId, existing.id)
        setSession(fullSession)
      } else {
        // Create new session
        const newSession = await createSession(currentDeckId, {
          component_id: currentComponentId,
          audience: currentAudience,
        })
        setSession(newSession)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load session')
      setSession(null)
    } finally {
      setLoading(false)
    }
  }, [])

  // Auto-refresh when deckId or componentId changes
  useEffect(() => {
    refresh()
  }, [deckId, componentId, initialAudience])

  const sendMessage = useCallback(
    async (mode: QueryMode, content: string) => {
      // Use refs for latest values
      const currentDeckId = deckIdRef.current
      const currentSession = sessionRef.current
      
      if (!currentDeckId || !currentSession) return

      setLoading(true)
      setError(null)

      try {
        const request: SendMessageRequest = {
          mode,
          content,
        }

        const updatedSession = await apiSendMessage(currentDeckId, currentSession.id, request)
        setSession(updatedSession)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to send message')
      } finally {
        setLoading(false)
      }
    },
    [],
  )

  const setAudience = useCallback(
    async (audience: Audience) => {
      // Use refs for latest values
      const currentDeckId = deckIdRef.current
      const currentSession = sessionRef.current
      
      if (!currentDeckId || !currentSession) return

      setLoading(true)
      setError(null)

      try {
        const updatedSession = await updateSessionAudience(currentDeckId, currentSession.id, audience)
        setSession(updatedSession)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update audience')
      } finally {
        setLoading(false)
      }
    },
    [],
  )

  const closeSession = useCallback(async () => {
    // Use refs for latest values
    const currentDeckId = deckIdRef.current
    const currentSession = sessionRef.current
    
    if (!currentDeckId || !currentSession) return

    setLoading(true)
    try {
      await deleteSession(currentDeckId, currentSession.id)
      setSession(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to close session')
    } finally {
      setLoading(false)
    }
  }, [])

  return {
    session,
    messages: session?.messages ?? [],
    loading,
    error,
    sendMessage,
    setAudience,
    refresh,
    closeSession,
  }
}
