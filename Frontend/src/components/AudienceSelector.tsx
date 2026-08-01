import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import { AUDIENCE_PRESETS, type Audience } from '../types'

interface Props {
  audience: Audience
  onChange: (audience: Audience) => void
  disabled?: boolean
}

const PRESET_LABELS: Record<Audience, string> = {
  general: 'General',
  swe: 'Software Engineer',
  marketing: 'Marketing',
  executive: 'Executive',
  sales: 'Sales',
  student: 'Student',
  designer: 'Designer',
  finance: 'Finance',
}

function getLabel(aud: Audience): string {
  if (PRESET_LABELS[aud as Audience]) {
    return PRESET_LABELS[aud as Audience]
  }
  // For free-text audiences, capitalize first letter
  const str = aud.toString()
  return str.charAt(0).toUpperCase() + str.slice(1)
}

export function AudienceSelector({ audience, onChange, disabled = false }: Props) {
  const [isOpen, setIsOpen] = useState(false)
  const [inputValue, setInputValue] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(() =>
    AUDIENCE_PRESETS.findIndex((p) => p === audience),
  )
  const containerRef = useRef<HTMLDivElement>(null)

  // Update selectedIndex when audience prop changes
  useEffect(() => {
    const idx = AUDIENCE_PRESETS.findIndex((p) => p === audience)
    setSelectedIndex(idx >= 0 ? idx : -1)
  }, [audience])

  // Handle click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
        setInputValue('')
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Handle keyboard navigation
  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (!isOpen) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault()
        setIsOpen(true)
      }
      return
    }

    switch (e.key) {
      case 'Escape':
        setIsOpen(false)
        setInputValue('')
        e.preventDefault()
        break
      case 'ArrowDown':
        e.preventDefault()
        setSelectedIndex((prev) =>
          prev < AUDIENCE_PRESETS.length - 1 ? prev + 1 : prev,
        )
        break
      case 'ArrowUp':
        e.preventDefault()
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : 0))
        break
      case 'Enter':
        e.preventDefault()
        if (selectedIndex >= 0) {
          onChange(AUDIENCE_PRESETS[selectedIndex])
          setIsOpen(false)
          setInputValue('')
        }
        break
      case 'Tab':
        setIsOpen(false)
        setInputValue('')
        break
    }
  }

  const handleSelect = (preset: Audience) => {
    onChange(preset)
    setIsOpen(false)
    setInputValue('')
  }

  const filteredPresets = inputValue
    ? AUDIENCE_PRESETS.filter((p) =>
        p.toLowerCase().includes(inputValue.toLowerCase()),
      )
    : AUDIENCE_PRESETS

  const displayValue = audience ? getLabel(audience) : 'Select audience...'

  return (
    <div
      ref={containerRef}
      className="relative"
      onKeyDown={handleKeyDown}
      tabIndex={0}
    >
      <button
        type="button"
        onClick={() => {
          if (!disabled) {
            setIsOpen(!isOpen)
            if (isOpen) setInputValue('')
          }
        }}
        disabled={disabled}
        className={[
          'flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium transition',
          'min-w-[100px] justify-between',
          disabled
            ? 'cursor-not-allowed border-white/20 bg-white/[0.04] text-white/40'
            : 'border-white/15 bg-white/[0.04] text-white/80 hover:border-white/30 hover:bg-white/[0.08]',
        ].join(' ')}
        data-persona-control
      >
        <span className="truncate">{displayValue}</span>
        <svg
          viewBox="0 0 16 16"
          className={`h-3 w-3 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
        >
          <path d="M3 6l5 5 5-5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute left-0 top-full mt-1 w-48 rounded-lg border border-white/10 bg-[#161b24] p-1 shadow-2xl shadow-black/60 z-50">
          <div className="relative">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Filter audiences..."
              className="w-full rounded-md border border-white/10 bg-white/[0.04] px-2 py-1.5 text-xs text-white/80 placeholder:text-white/35 focus:outline-none focus:ring-1 focus:ring-sky-400/50"
              autoFocus
            />
          </div>
          <div className="mt-1 max-h-60 overflow-y-auto">
            {filteredPresets.length > 0 ? (
              filteredPresets.map((preset, index) => (
                <button
                  key={preset}
                  onClick={() => handleSelect(preset)}
                  className={[
                    'w-full text-left rounded-md px-2 py-1.5 text-xs transition',
                    'hover:bg-white/[0.06] text-white/70 hover:text-white',
                    selectedIndex === index ? 'bg-sky-400/15 text-white' : '',
                  ].join(' ')}
                >
                  <span className="flex items-center gap-2">
                    {getLabel(preset)}
                    {audience === preset && (
                      <svg
                        viewBox="0 0 16 16"
                        className="h-3 w-3 text-sky-400"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.8"
                      >
                        <path
                          d="M12.5 5L5 12.5 3.5 11"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    )}
                  </span>
                </button>
              ))
            ) : (
              <p className="px-2 py-1.5 text-xs text-white/40">No audiences found</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
