import { useRef, useState, useId } from 'react'
import { Send, RotateCcw, Upload } from 'lucide-react'
import { clsx } from 'clsx'
import { useStreamQuery } from './hooks/useStreamQuery'
import { Sidebar } from './components/Sidebar'
import { ConfidenceBadge } from './components/ConfidenceBadge'
import { SourceCard } from './components/SourceCard'
import { uploadDocument, pollJob } from './lib/api'

// Stable session ID for the lifetime of the browser tab
const SESSION_ID = crypto.randomUUID()

export default function App() {
  const inputId = useId()
  const [question, setQuestion]     = useState('')
  const [uploadStatus, setUpload]   = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const {
    answer, metadata, rewrittenQuery,
    isStreaming, error, history,
    submit, reset,
  } = useStreamQuery(SESSION_ID)

  function handleSubmit(e?: React.FormEvent) {
    e?.preventDefault()
    const q = question.trim()
    if (!q || isStreaming) return
    submit(q)
  }

  function handleDemoSelect(q: string) {
    setQuestion(q)
    reset()
    // slight delay so the question appears in the input before submitting
    setTimeout(() => submit(q), 50)
  }

  async function handleUpload(file: File) {
    setUpload('Uploading…')
    const result = await uploadDocument(file)
    if (!result.job_id) { setUpload('Upload failed'); return }
    setUpload(`Ingesting ${result.filename}…`)
    const poll = setInterval(async () => {
      const status = await pollJob(result.job_id)
      if (status.status === 'done') {
        setUpload(`✓ Ingested ${status.chunks_written} chunks`)
        clearInterval(poll)
        setTimeout(() => setUpload(null), 4000)
      } else if (status.status === 'failed') {
        setUpload(`✗ ${status.error}`)
        clearInterval(poll)
      }
    }, 2000)
  }

  return (
    <div className="flex h-screen bg-brand-navy font-sans text-white overflow-hidden">
      <Sidebar
        history={history}
        onSelectQuestion={handleDemoSelect}
        isStreaming={isStreaming}
      />

      {/* Main panel */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="px-8 py-5 border-b border-brand-border flex items-center justify-between shrink-0">
          <div>
            <h1 className="text-xl font-bold">EU Compliance Assistant</h1>
            <p className="text-brand-muted text-sm mt-0.5">
              Query DORA · EU AI Act · BaFin circulars — all inference runs locally
            </p>
          </div>
          {/* Upload */}
          <div className="flex items-center gap-3">
            {uploadStatus && (
              <span className="text-xs text-brand-muted">{uploadStatus}</span>
            )}
            <button
              onClick={() => fileRef.current?.click()}
              className="flex items-center gap-1.5 text-xs text-brand-muted hover:text-white border border-brand-border hover:border-brand-green rounded-md px-3 py-1.5 transition-colors"
            >
              <Upload size={12} />
              Add regulation
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) handleUpload(f)
                e.target.value = ''
              }}
            />
          </div>
        </header>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto px-8 py-6">
          {/* Empty state */}
          {!answer && !isStreaming && !error && (
            <div className="flex flex-col items-center justify-center h-full text-center gap-4 pb-16">
              <div className="text-5xl">⚖</div>
              <h2 className="text-2xl font-semibold">Ask a compliance question</h2>
              <p className="text-brand-muted max-w-lg text-sm leading-relaxed">
                Query EU financial regulations with cited answers. Select a demo question
                from the sidebar or type your own below.
              </p>
              <div className="flex flex-wrap justify-center gap-2 mt-2">
                {['DORA', 'EU AI Act', 'BaFin BAIT', 'GDPR'].map((tag) => (
                  <span key={tag} className="px-3 py-1 rounded-full text-xs border border-brand-border text-brand-muted">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Rewrite notice */}
          {rewrittenQuery && (
            <div className="mb-4 text-xs text-brand-muted italic">
              Query expanded → <span className="text-white">{rewrittenQuery}</span>
            </div>
          )}

          {/* Answer — streams in token by token */}
          {(answer || isStreaming) && (
            <div className="mb-6">
              <div className="bg-brand-card border-l-2 border-brand-green rounded-r-lg rounded-bl-lg px-6 py-5 text-[0.94rem] leading-7 whitespace-pre-wrap">
                {answer}
                {isStreaming && (
                  <span className="inline-block w-0.5 h-4 bg-brand-green ml-0.5 animate-pulse" />
                )}
              </div>

              {metadata && (
                <ConfidenceBadge
                  score={metadata.confidence}
                  flagged={metadata.flagged}
                />
              )}
            </div>
          )}

          {/* Error state */}
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-5 py-4 text-red-400 text-sm mb-6">
              <strong>Error:</strong> {error}
              <p className="text-xs mt-1 text-red-400/70">
                Make sure both the FastAPI backend (port 8000) and Qdrant are running.
              </p>
            </div>
          )}

          {/* Sources */}
          {metadata?.sources && metadata.sources.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-brand-muted uppercase tracking-wider mb-3">
                Sources — {metadata.sources.length} passages retrieved
              </h3>
              <div className="flex flex-col gap-3">
                {metadata.sources.map((src, i) => (
                  <SourceCard key={i} source={src} rank={i + 1} />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Query input — pinned to bottom */}
        <div className="shrink-0 border-t border-brand-border px-8 py-4 bg-brand-navy">
          <form onSubmit={handleSubmit} className="flex gap-3">
            <div className="flex-1 relative">
              <label htmlFor={inputId} className="sr-only">Compliance question</label>
              <textarea
                id={inputId}
                rows={2}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit() }
                }}
                placeholder="e.g. What are the ICT third-party risk requirements under DORA Article 28?"
                className={clsx(
                  'w-full bg-brand-card border border-brand-border rounded-xl px-4 py-3',
                  'text-sm text-white placeholder-brand-muted resize-none',
                  'focus:outline-none focus:border-brand-green transition-colors',
                  'disabled:opacity-50',
                )}
                disabled={isStreaming}
              />
            </div>
            <div className="flex flex-col gap-2">
              <button
                type="submit"
                disabled={!question.trim() || isStreaming}
                className={clsx(
                  'flex items-center justify-center gap-1.5 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all',
                  'bg-brand-green text-brand-navy hover:bg-brand-green/90',
                  'disabled:opacity-40 disabled:cursor-not-allowed',
                )}
              >
                <Send size={14} />
                Ask
              </button>
              {(answer || error) && (
                <button
                  type="button"
                  onClick={() => { reset(); setQuestion('') }}
                  className="flex items-center justify-center gap-1 px-5 py-2 rounded-xl text-xs text-brand-muted hover:text-white border border-brand-border hover:border-brand-green transition-colors"
                >
                  <RotateCcw size={11} />
                  Clear
                </button>
              )}
            </div>
          </form>
          <p className="text-[10px] text-brand-muted mt-2">
            Enter to submit · Shift+Enter for new line · Answers cite article and page numbers
          </p>
        </div>
      </main>
    </div>
  )
}
