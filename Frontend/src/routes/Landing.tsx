import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadDeck } from '../api/client'
import { useDropzone, type Accept } from 'react-dropzone'

const DECK_ACCEPT: Accept = {
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
}

const CONTEXT_ACCEPT: Accept = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/markdown': ['.md'],
  'text/plain': ['.txt'],
}

type Tab = 'host' | 'join'

export default function Landing() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<Tab>('host')
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)

  // Host state
  const [deckFile, setDeckFile] = useState<File | null>(null)
  const [contextFiles, setContextFiles] = useState<File[]>([])
  const [hostBusy, setHostBusy] = useState(false)

  const deckZone = useDropzone({
    accept: DECK_ACCEPT,
    maxFiles: 1,
    multiple: false,
    onDrop: (accepted, rejected) => {
      if (rejected.length > 0) {
        setError('That file is not a .pptx — Prestral reads PowerPoint decks only.')
        return
      }
      setError(null)
      setDeckFile(accepted[0] ?? null)
    },
  })

  const contextZone = useDropzone({
    accept: CONTEXT_ACCEPT,
    onDrop: (accepted) => setContextFiles((prev) => [...prev, ...accepted]),
  })

  const handleHost = async () => {
    if (!deckFile) return
    setHostBusy(true)
    setError(null)
    try {
      const { id } = await uploadDeck(deckFile, contextFiles)
      // The id is now a 6-character code
      navigate(`/present/${id}/0`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
      setHostBusy(false)
    }
  }

  const handleJoin = () => {
    if (!code || code.length !== 6) {
      setError('Please enter a valid 6-character code')
      return
    }
    setError(null)
    // For now, joining goes to the same view but with viewer mode
    // We'll need to add mode detection to the Deck route
    navigate(`/deck/${code}/0`)
  }

  const handleCodeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.toUpperCase()
    // Only allow letters and numbers
    const filtered = value.replace(/[^A-Z0-9]/g, '').slice(0, 6)
    setCode(filtered)
    setError(null)
  }

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col justify-center gap-8 px-6 py-10">
      <div>
        <h1 className="text-2xl font-semibold">Prestral</h1>
        <p className="mt-1 text-sm text-white/45">
          One deck, read three ways. Hover any text and it rewrites itself for your discipline.
        </p>
      </div>

      {/* Tab Toggle */}
      <div className="flex border-b border-white/10">
        <button
          onClick={() => setActiveTab('host')}
          className={`px-6 py-3 text-sm font-medium transition ${
            activeTab === 'host'
              ? 'border-b-2 border-sky-400 text-white'
              : 'text-white/40 hover:text-white/70'
          }`}
        >
          Host
        </button>
        <button
          onClick={() => setActiveTab('join')}
          className={`px-6 py-3 text-sm font-medium transition ${
            activeTab === 'join'
              ? 'border-b-2 border-sky-400 text-white'
              : 'text-white/40 hover:text-white/70'
          }`}
        >
          Join
        </button>
      </div>

      {activeTab === 'host' ? (
        <div className="flex flex-col gap-6">
          <Zone
            {...deckZone}
            title="Presentation"
            required
            hint=".pptx"
            filled={deckFile ? [deckFile.name] : []}
          />

          <Zone
            {...contextZone}
            title="Context files"
            hint="optional · pdf, docx, md, txt — these are what the elaborations get grounded in"
            filled={contextFiles.map((f) => f.name)}
            onClear={() => setContextFiles([])}
          />

          {error && <p className="text-sm text-red-300/80">{error}</p>}

          <div className="flex items-center gap-4">
            <button
              onClick={handleHost}
              disabled={!deckFile || hostBusy}
              className="rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-medium text-white transition
                         hover:bg-sky-400 disabled:cursor-not-allowed disabled:bg-white/10 disabled:text-white/30"
            >
              {hostBusy ? 'Creating session…' : 'Host session'}
            </button>

            <button
              onClick={() => navigate('/deck/demo/0')}
              className="text-xs text-white/35 underline-offset-4 hover:text-white/70 hover:underline"
            >
              or open the demo deck
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-6">
          <div className="text-center">
            <h2 className="text-lg font-medium text-white/80">Join a session</h2>
            <p className="mt-1 text-sm text-white/40">
              Enter the 6-character code provided by the presenter
            </p>
          </div>

          <div className="w-full max-w-sm">
            <label className="block text-sm font-medium text-white/80 mb-2">Session Code</label>
            <input
              type="text"
              value={code}
              onChange={handleCodeChange}
              placeholder="e.g., ABC123"
              maxLength={6}
              className="w-full rounded-lg border border-white/15 bg-white/[0.03] px-4 py-3 text-lg font-mono tracking-wider text-center text-white placeholder:text-white/30 focus:border-sky-400/50 focus:outline-none focus:ring-2 focus:ring-sky-400/20"
            />
            <p className="mt-2 text-xs text-white/30">6 characters, numbers or capital letters</p>
          </div>

          {error && <p className="text-sm text-red-300/80">{error}</p>}

          <button
            onClick={handleJoin}
            disabled={code.length !== 6}
            className="w-full max-w-sm rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-medium text-white transition
                       hover:bg-sky-400 disabled:cursor-not-allowed disabled:bg-white/10 disabled:text-white/30"
          >
            Join session
          </button>
        </div>
      )}
    </div>
  )
}

// Reuse the Zone component from Upload.tsx
interface ZoneProps {
  title: string
  hint: string
  required?: boolean
  filled: string[]
  onClear?: () => void
  getRootProps: ReturnType<typeof useDropzone>['getRootProps']
  getInputProps: ReturnType<typeof useDropzone>['getInputProps']
  isDragActive: boolean
}

function Zone({ title, hint, required, filled, onClear, getRootProps, getInputProps, isDragActive }: ZoneProps) {
  return (
    <div>
      <div className="mb-2 flex items-baseline gap-2">
        <h2 className="text-sm font-medium text-white/80">{title}</h2>
        {required && <span className="text-[11px] text-sky-300/70">required</span>}
        {onClear && filled.length > 0 && (
          <button onClick={onClear} className="ml-auto text-[11px] text-white/30 hover:text-white/70">
            clear
          </button>
        )}
      </div>

      <div
        {...getRootProps()}
        className={[
          'cursor-pointer rounded-xl border border-dashed p-6 text-center transition',
          isDragActive
            ? 'border-sky-400/70 bg-sky-400/10'
            : 'border-white/15 bg-white/[0.02] hover:border-white/30',
        ].join(' ')}
      >
        <input {...getInputProps()} />
        {filled.length > 0 ? (
          <ul className="space-y-1 text-sm text-white/75">
            {filled.map((name) => (
              <li key={name} className="truncate">
                {name}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-white/40">
            Drop here or click to choose
            <span className="mt-1 block text-[11px] text-white/25">{hint}</span>
          </p>
        )}
      </div>
    </div>
  )
}
