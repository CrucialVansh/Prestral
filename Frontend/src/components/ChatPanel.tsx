import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { AudienceSelector } from './AudienceSelector'
import type { ChatMessage, Audience, QueryMode } from '../types'

interface Props {
  messages: ChatMessage[]
  audience: Audience
  loading: boolean
  error: string | null
  onSend: (mode: QueryMode, content: string) => Promise<void>
  onAudienceChange: (audience: Audience) => Promise<void>
  onClose: () => void
}

export function ChatPanel({
  messages,
  audience,
  loading,
  error,
  onSend,
  onAudienceChange,
  onClose,
}: Props) {
  const [inputValue, setInputValue] = useState('')
  const [mode, setMode] = useState<QueryMode>('ask')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const formRef = useRef<HTMLFormElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  // Auto-focus input when panel opens
  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  // Auto-resize textarea based on content
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
    }
  }, [inputValue])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!inputValue.trim()) return

    await onSend(mode, inputValue.trim())
    setInputValue('')
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e as unknown as FormEvent)
    }
    // Allow Shift+Enter to create a new line (browser default behavior)
  }

  return (
    <div className="flex h-full flex-col border-l border-white/[0.07] bg-[#0e1117]" style={{ width: 320 }}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/[0.07] px-4 py-3">
        <h2 className="text-sm font-medium text-white/80">Chat</h2>
        <div className="flex items-center gap-2">
          <AudienceSelector
            audience={audience}
            onChange={onAudienceChange}
            disabled={loading}
          />
          <button
            onClick={onClose}
            aria-label="Close chat"
            className="rounded p-1.5 text-white/40 transition hover:bg-white/10 hover:text-white/80"
          >
            <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M12 4L4 12M4 4L12 12" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {messages.length === 0 ? (
          <div className="flex h-full items-center justify-center text-xs text-white/40">
            <p>Ask a question about this element</p>
          </div>
        ) : (
          <div className="space-y-3">
            {messages.map((msg, index) => (
              <div
                key={`${msg.role}-${index}`}
                className={[
                  'flex gap-2 rounded-lg p-2 text-xs',
                  msg.role === 'user'
                    ? 'bg-white/[0.04] text-white/80'
                    : 'bg-sky-400/10 text-white',
                ].join(' ')}
              >
                <span
                  className={[
                    'flex-shrink-0 h-5 w-5 rounded-full flex items-center justify-center text-[10px] font-medium',
                    msg.role === 'user' ? 'bg-white/10' : 'bg-sky-400/20 text-sky-300',
                  ].join(' ')}
                >
                  {msg.role === 'user' ? 'U' : 'A'}
                </span>
                <div className="flex-1">
                  <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                  {msg.sources && msg.sources.length > 0 && (
                    <p className="mt-1.5 border-t border-white/[0.1] pt-1.5 text-[10px] text-white/40">
                      <span className="text-white/30">Grounded in: </span>
                      {msg.sources.join(' · ')}
                    </p>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex gap-2 rounded-lg bg-sky-400/10 p-2 text-xs text-white">
                <span className="flex-shrink-0 h-5 w-5 rounded-full flex items-center justify-center bg-sky-400/20 text-sky-300 text-[10px] font-medium">
                  A
                </span>
                <div className="flex-1">
                  <p className="whitespace-pre-wrap leading-relaxed">
                    <span className="animate-pulse">Thinking...</span>
                  </p>
                </div>
              </div>
            )}
            {error && (
              <div className="flex gap-2 rounded-lg bg-red-400/10 p-2 text-xs text-red-300/80">
                <span className="flex-shrink-0 h-5 w-5 rounded-full flex items-center justify-center bg-red-400/20 text-[10px] font-medium">
                  !
                </span>
                <div className="flex-1">
                  <p>{error}</p>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <form ref={formRef} onSubmit={handleSubmit} className="border-t border-white/[0.07] px-4 py-3">
        <div className="flex gap-2">
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as QueryMode)}
            className="rounded-lg border border-white/15 bg-[#0e1117] px-2 py-1.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-sky-400/50 disabled:opacity-50"
            disabled={loading}
          >
            <option value="ask" className="bg-[#161b24] text-white">Ask</option>
            <option value="summarize" className="bg-[#161b24] text-white">Summarize</option>
            <option value="explain" className="bg-[#161b24] text-white">Explain</option>
          </select>
          <textarea
            ref={textareaRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question..."
            disabled={loading}
            className="flex-1 resize-none overflow-hidden rounded-lg border border-white/15 bg-white/[0.04] px-3 py-1.5 text-xs text-white/80 placeholder:text-white/35 focus:outline-none focus:ring-1 focus:ring-sky-400/50 disabled:opacity-50"
            style={{ minHeight: '38px' }}
          />
          <button
            type="submit"
            disabled={loading || !inputValue.trim()}
            className="rounded-lg bg-sky-500 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:bg-white/10 disabled:text-white/30"
          >
            Send
          </button>
        </div>
        <p className="mt-1 text-[10px] text-white/40">Enter to send, Shift+Enter for new line</p>
      </form>
    </div>
  )
}
