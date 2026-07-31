interface Props {
  index: number
  total: number
  onGo: (index: number) => void
}

function Arrow({ dir }: { dir: 'left' | 'right' }) {
  return (
    <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path
        d={dir === 'left' ? 'M10 3L5 8l5 5' : 'M6 3l5 5-5 5'}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function SlideNav({ index, total, onGo }: Props) {
  const btn =
    'rounded-lg border border-white/10 bg-white/[0.04] p-2 text-white/70 transition ' +
    'hover:bg-white/[0.1] hover:text-white disabled:opacity-25 disabled:hover:bg-white/[0.04]'

  return (
    <div className="flex items-center gap-3">
      <button className={btn} onClick={() => onGo(index - 1)} disabled={index <= 0} aria-label="Previous slide">
        <Arrow dir="left" />
      </button>

      <span className="tabular-nums text-sm text-white/45">
        <span className="text-white/80">{index + 1}</span> / {total}
      </span>

      <button
        className={btn}
        onClick={() => onGo(index + 1)}
        disabled={index >= total - 1}
        aria-label="Next slide"
      >
        <Arrow dir="right" />
      </button>
    </div>
  )
}
