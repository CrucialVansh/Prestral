import { PERSONAS } from '../types'

interface Props {
  index: number
  onChange: (index: number) => void
}

/**
 * Three discrete stops, not a continuum — the value is "read this as an
 * engineer", not "read this 62% technically". Rendered as a segmented control
 * with a sliding pill so the change reads as movement along an axis.
 */
export function PersonaSlider({ index, onChange }: Props) {
  return (
    <div className="flex items-center gap-3">
      <span className="hidden text-[11px] uppercase tracking-wider text-white/35 sm:block">
        View as
      </span>

      <div
        role="radiogroup"
        aria-label="View level"
        className="relative flex rounded-full border border-white/10 bg-white/[0.04] p-1"
      >
        <div
          aria-hidden
          className="absolute inset-y-1 left-1 rounded-full bg-sky-500/90 transition-transform duration-200 ease-out"
          style={{
            width: `calc((100% - 0.5rem) / ${PERSONAS.length})`,
            transform: `translateX(${index * 100}%)`,
          }}
        />

        {PERSONAS.map((p, i) => (
          <button
            key={p.id}
            role="radio"
            aria-checked={i === index}
            title={`${p.blurb}  (press ${i + 1})`}
            onClick={() => onChange(i)}
            className={[
              'relative z-10 flex-1 whitespace-nowrap rounded-full px-4 py-1.5 text-xs font-medium transition-colors',
              i === index ? 'text-white' : 'text-white/50 hover:text-white/80',
            ].join(' ')}
          >
            {p.label}
          </button>
        ))}
      </div>
    </div>
  )
}
