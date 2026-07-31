import { Hotspot } from './Hotspot'
import type { Audience, Slide } from '../types'

interface Props {
  slide: Slide
  /** width / height, e.g. 1.7778 for 16:9 */
  aspectRatio: number
  persona: Audience
  highlightAll: boolean
  pinnedId: string | null
  onPin: (id: string | null) => void
  onChatOpen?: (componentId: string) => void
  onCloseChat?: () => void
  chatComponentId?: string | null
}

/**
 * The only component that knows about geometry.
 *
 * Hotspot boxes arrive as fractions of slide width/height, never pixels, so
 * they are positioned in percentages: the overlay then stays aligned at any
 * window size with no scaling maths and no drift on resize.
 */
export function SlideCanvas({
  slide,
  aspectRatio,
  persona,
  highlightAll,
  pinnedId,
  onPin,
  onChatOpen,
  onCloseChat,
  chatComponentId,
}: Props) {
  return (
    <div
      className="relative mx-auto overflow-hidden rounded-lg border border-white/10
                 shadow-2xl shadow-black/50"
      style={{
        aspectRatio: String(aspectRatio),
        // Fit the viewport height by narrowing the box, NOT by capping its
        // height: a max-height would break the aspect ratio, the image would
        // letterbox inside the box, and every hotspot percentage would then be
        // measured against the wrong rectangle.
        width: `min(100%, calc((100vh - 13rem) * ${aspectRatio}))`,
      }}
    >
      {/* object-fill, not object-contain: the box already has the deck's aspect
          ratio, so filling it guarantees image and overlay share one rectangle.
          If the two ever disagree this shows as a slight stretch rather than as
          silently misaligned hotspots. */}
      <img
        src={slide.imageUrl}
        alt={`Slide ${slide.index + 1}`}
        className="h-full w-full object-fill"
        draggable={false}
      />

      {slide.components.map((h) => (
        <Hotspot
          key={h.id}
          hotspot={h}
          style={{
            left: `${h.bbox.left * 100}%`,
            top: `${h.bbox.top * 100}%`,
            width: `${h.bbox.width * 100}%`,
            height: `${h.bbox.height * 100}%`,
          }}
          persona={persona}
          highlighted={highlightAll}
          pinned={pinnedId === h.id}
          onPin={onPin}
          onChatOpen={onChatOpen}
          onClose={onCloseChat}
          isChatOpen={chatComponentId === h.id}
        />
      ))}
    </div>
  )
}
