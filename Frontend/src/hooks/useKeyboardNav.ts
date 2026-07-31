import { useEffect, useRef } from 'react'

interface Handlers {
  onPrev: () => void
  onNext: () => void
  onPersona: (index: number) => void
  onEscape: () => void
  onToggleHighlight: () => void
}

function isTyping() {
  const el = document.activeElement as HTMLElement | null
  if (!el) return false
  return (
    el.tagName === 'INPUT' ||
    el.tagName === 'TEXTAREA' ||
    el.tagName === 'SELECT' ||
    el.isContentEditable
  )
}

/**
 * Space is the presenter's "next slide", but it is also how you activate a
 * focused button — and hotspots are buttons. Only claim it when focus is
 * resting on the page itself, or Tab-then-Space could never open a card.
 */
function canClaimSpace() {
  const el = document.activeElement
  return !el || el === document.body
}

/**
 * Presenting with a mouse is fiddly; every demo action has a key.
 * Handlers live in a ref so the listener is bound once and never churns.
 */
export function useKeyboardNav(handlers: Handlers) {
  const ref = useRef(handlers)
  ref.current = handlers

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      // Never hijack keys while the user is filling in a field.
      if (isTyping() || e.metaKey || e.ctrlKey || e.altKey) return
      const h = ref.current

      switch (e.key) {
        case 'ArrowLeft':
          h.onPrev()
          break
        case ' ':
          if (!canClaimSpace()) return
          e.preventDefault()
          h.onNext()
          break
        case 'ArrowRight':
          h.onNext()
          break
        case '1':
        case '2':
        case '3':
          h.onPersona(Number(e.key) - 1)
          break
        case 'Escape':
          h.onEscape()
          break
        case 'h':
        case 'H':
          h.onToggleHighlight()
          break
        default:
          return
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])
}
