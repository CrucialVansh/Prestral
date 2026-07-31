import { useCallback, useState } from 'react'
import { useDropzone, type Accept } from 'react-dropzone'
import { Link, useNavigate } from 'react-router-dom'
import { uploadDeck } from '../api/client'

const DECK_ACCEPT: Accept = {
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
}

const CONTEXT_ACCEPT: Accept = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/markdown': ['.md'],
  'text/plain': ['.txt'],
}

export default function Upload() {
  const navigate = useNavigate()
  const [deckFile, setDeckFile] = useState<File | null>(null)
  const [contextFiles, setContextFiles] = useState<File[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const deckZone = useDropzone({
    accept: DECK_ACCEPT,
    maxFiles: 1,
    multiple: false,
    onDrop: (accepted, rejected) => {
      // Silence on rejection would look like the drop simply didn't register.
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

  const submit = useCallback(async () => {
    if (!deckFile) return
    setBusy(true)
    setError(null)
    try {
      const { deckId } = await uploadDeck(deckFile, contextFiles)
      navigate(`/deck/${deckId}/processing`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
      setBusy(false)
    }
  }, [deckFile, contextFiles, navigate])

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col justify-center gap-8 px-6 py-10">
      <div>
        <h1 className="text-2xl font-semibold">Prestral</h1>
        <p className="mt-1 text-sm text-white/45">
          One deck, read three ways. Hover any text and it rewrites itself for your discipline.
        </p>
      </div>

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
          onClick={submit}
          disabled={!deckFile || busy}
          className="rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-medium text-white transition
                     hover:bg-sky-400 disabled:cursor-not-allowed disabled:bg-white/10 disabled:text-white/30"
        >
          {busy ? 'Uploading…' : 'Analyse deck'}
        </button>

        <Link to="/deck/demo/0" className="text-xs text-white/35 underline-offset-4 hover:text-white/70 hover:underline">
          or open the demo deck
        </Link>
      </div>
    </div>
  )
}

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
