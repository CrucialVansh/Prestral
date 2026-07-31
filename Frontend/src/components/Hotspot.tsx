import { useState, type CSSProperties } from 'react'
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
import type { Hotspot as HotspotData, PersonaId } from '../types'

interface Props {
  hotspot: HotspotData
  /** Absolute percentage box, computed by SlideCanvas — the only geometry owner. */
  style: CSSProperties
  persona: PersonaId
  highlighted: boolean
  pinned: boolean
  onPin: (id: string | null) => void
}

/**
 * A transparent target laid over the rendered slide.
 *
 * Rendered as a <button> rather than a <div> so it is reachable by Tab and
 * announced to screen readers for free.
 */
export function Hotspot({ hotspot, style, persona, highlighted, pinned, onPin }: Props) {
  const [hovered, setHovered] = useState(false)
  const open = pinned || hovered

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
    middleware: [
      offset(10),
      // Cards near the slide edges would otherwise be clipped or run off-screen.
      flip({ padding: 8 }),
      shift({ padding: 8 }),
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
  const dismiss = useDismiss(context, { enabled: pinned })
  const role = useRole(context, { role: 'tooltip' })

  const { getReferenceProps, getFloatingProps } = useInteractions([hover, dismiss, role])

  const isText = (hotspot.kind ?? 'text') === 'text'

  return (
    <>
      <button
        ref={refs.setReference}
        {...getReferenceProps({
          onClick: () => {
            // Clear the hover flag as we pin, otherwise it stays latched true
            // (useHover is disabled while pinned, so no mouseleave arrives) and
            // the card would linger after unpinning.
            setHovered(false)
            onPin(pinned ? null : hotspot.id)
          },
        })}
        style={style}
        aria-label={`Explain: ${hotspot.originalText}`}
        className={[
          'absolute cursor-help transition-colors duration-150',
          isText
            ? 'rounded-sm border-b border-dotted border-sky-400/30'
            : 'rounded-md border border-dashed border-sky-400/40',
          // A persistent affordance: nobody hovers text they don't know is live.
          open ? 'bg-sky-400/[0.15]' : 'bg-sky-400/[0.06] hover:bg-sky-400/[0.15]',
          highlighted ? 'ring-2 ring-sky-400/70' : '',
          pinned ? 'ring-2 ring-sky-400' : '',
        ].join(' ')}
      />

      {open && (
        // Portalled so the card is never clipped by the slide's bounding box.
        <FloatingPortal>
          <div
            ref={refs.setFloating}
            style={{ ...floatingStyles, zIndex: 50 }}
            {...getFloatingProps()}
          >
            <DetailPopover
              hotspot={hotspot}
              persona={persona}
              pinned={pinned}
              onUnpin={() => onPin(null)}
            />
          </div>
        </FloatingPortal>
      )}
    </>
  )
}
