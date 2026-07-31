import { useState, useEffect, type CSSProperties } from 'react'
import {
  FloatingPortal,
  autoUpdate,
  flip,
  offset,
  safePolygon,
  shift,
  useDismiss,
  useFloating,
  useHover,
  useInteractions,
  useRole,
} from '@floating-ui/react'
import { DetailPopover } from './DetailPopover'
import type { Component as HotspotData, Audience } from '../types'

interface Props {
  hotspot: HotspotData
  /** Absolute percentage box, computed by SlideCanvas — the only geometry owner. */
  style: CSSProperties
  persona: Audience
  highlighted: boolean
  pinned: boolean
  onPin: (id: string | null) => void
  onChatOpen?: (componentId: string) => void
  onClose?: () => void
  isChatOpen?: boolean
}

/**
 * A transparent target laid over the rendered slide.
 *
 * Rendered as a <button> rather than a <div> so it is reachable by Tab and
 * announced to screen readers for free.
 */
export function Hotspot({ hotspot, style, persona, highlighted, pinned, onPin, onChatOpen, onClose, isChatOpen = false }: Props) {
  const [hovered, setHovered] = useState(false)
  const open = pinned || hovered || isChatOpen

  const { refs, floatingStyles, context } = useFloating({
    open,
    onOpenChange: (next) => {
      if (next) {
        setHovered(true)
        return
      }
      setHovered(false)
      // Esc or an outside click while pinned should also release the pin.
      if (pinned) onPin(null)
    },
    placement: 'bottom-start',
    strategy: 'fixed',
    middleware: [
      offset(10),
      // Cards near the slide edges would otherwise be clipped or run off-screen.
      // Use generous padding to account for the 26rem (416px) popover width.
      // flip: try opposite side if current placement would go off-screen
      // shift: prevent going off-screen by shifting back
      // The padding values are in pixels and define the minimum distance from viewport edges
      flip({ padding: 64 }),
      shift({ padding: 64 }),
    ],
    whileElementsMounted: autoUpdate,
  })

  const hover = useHover(context, {
    // A pinned card stays put; mouseleave must not close it.
    enabled: !pinned,
    // Without a delay, cards flicker as the cursor scans across the slide.
    delay: { open: 150, close: 100 },
    // The single most important line here: keeps the card alive while the
    // cursor travels diagonally across dead space from hotspot to card.
    handleClose: safePolygon({ blockPointerEvents: false }),
  })
  const dismiss = useDismiss(context, {
    enabled: pinned || isChatOpen,
    outsidePress: (event) => {
      // Don't treat clicks on persona/highlight controls as a dismiss —
      // switching view level shouldn't collapse a pinned card.
      const target = event.target as HTMLElement
      return !target.closest('[data-persona-control]')
    },
  })

  // When popover is dismissed and chat is open, close the chat
  useEffect(() => {
    if (!open && isChatOpen && onClose) {
      onClose()
    }
  }, [open, isChatOpen, onClose])
  const role = useRole(context, { role: 'tooltip' })

  const { getReferenceProps, getFloatingProps } = useInteractions([hover, dismiss, role])

  const isText = (hotspot.type ?? 'text_box') === 'text_box'

  return (
    <>
      <button
        ref={refs.setReference}
        {...getReferenceProps({
          onClick: (e) => {
            e.stopPropagation()
            // If chat is enabled, open chat on click
            if (onChatOpen) {
              setHovered(false)
              if (isChatOpen && onClose) {
                // Clicking the hotspot with chat open closes it
                onClose()
              } else {
                onChatOpen(hotspot.id)
              }
            } else {
              // Otherwise, toggle pin (old behavior)
              setHovered(false)
              onPin(pinned ? null : hotspot.id)
            }
          },
        })}
        style={style}
        aria-label={`Explain: ${hotspot.text}`}
        className={[
          'absolute cursor-help transition-colors duration-150',
          isText
            ? 'rounded-sm border-b border-dotted border-sky-400/30'
            : 'rounded-md border border-dashed border-sky-400/40',
          // A persistent affordance: nobody hovers text they don't know is live.
          open ? 'bg-sky-400/[0.15]' : 'bg-sky-400/[0.06] hover:bg-sky-400/[0.15]',
          highlighted ? 'ring-2 ring-sky-400/70' : '',
          pinned ? 'ring-2 ring-sky-400' : '',
          isChatOpen ? 'ring-2 ring-sky-300 bg-sky-400/[0.2]' : '',
        ].join(' ')}
      />

      {open && (
        // Portalled so the card is never clipped by the slide's bounding box.
        // pointerEvents: none allows mouse-through to slide content below
        <FloatingPortal>
          <div
            ref={refs.setFloating}
            style={{ ...floatingStyles, zIndex: 50, pointerEvents: 'none' }}
            {...getFloatingProps()}
          >
            <div style={{ pointerEvents: 'auto' }}>
              <DetailPopover
                hotspot={hotspot}
                persona={persona}
                pinned={pinned}
                onUnpin={() => onPin(null)}
              />
            </div>
          </div>
        </FloatingPortal>
      )}
    </>
  )
}
