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

  // Scroll to bottom of chat when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [session?.messages?.length])

  const refresh = useCallback(async () => {
    if (!deckId || !componentId) {
      setSession(null)
      return
    }

    setLoading(true)
    setError(null)

    try {
      // Try to find existing session for this component
      const sessions = await listSessions(deckId)
      const existing = sessions.find((s) => s.component_id === componentId)

      if (existing) {
        // Get full session with messages
        const fullSession = await getSession(deckId, existing.id)
        setSession(fullSession)
      } else {
        // Create new session
        const newSession = await createSession(deckId, {
          component_id: componentId,
          audience: initialAudience,
        })
        setSession(newSession)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load session')
      setSession(null)
    } finally {
      setLoading(false)
    }
    // initialAudience only used when creating a new session
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deckId, componentId])

  // Auto-refresh when deckId or componentId changes
  useEffect(() => {
    void refresh()
  }, [refresh])

  const sendMessage = useCallback(
    async (mode: QueryMode, content: string) => {
      if (!deckId || !session) return

      setLoading(true)
      setError(null)

      try {
        const request: SendMessageRequest = {
          mode,
          content,
        }

        const res = await apiSendMessage(deckId, session.id, request)
        setSession((prev) => {
          if (!prev) return prev
          return {
            ...prev,
            audience: (res.audience as Audience) || prev.audience,
            messages: [...prev.messages, res.user_message, res.assistant_message],
          }
        })
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to send message')
      } finally {
        setLoading(false)
      }
    },
    [deckId, session],
  )

  const setAudience = useCallback(
    async (audience: Audience) => {
      if (!deckId || !session) return

      setLoading(true)
      setError(null)

      try {
        const updatedSession = await updateSessionAudience(deckId, session.id, audience)
        setSession(updatedSession)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update audience')
      } finally {
        setLoading(false)
      }
    },
    [deckId, session],
  )

  const closeSession = useCallback(async () => {
    if (!deckId || !session) return

    setLoading(true)
    try {
      await deleteSession(deckId, session.id)
      setSession(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to close session')
    } finally {
      setLoading(false)
    }
  }, [deckId, session])

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
