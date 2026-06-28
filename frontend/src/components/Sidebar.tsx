import { useEffect, useState } from 'react'
import { CheckCircle2, XCircle, Database, Clock } from 'lucide-react'
import { fetchHealth, fetchSources } from '../lib/api'
import type { CorpusDocument, HealthStatus, HistoryEntry } from '../types'
import { DemoQuestions } from './DemoQuestions'

interface Props {
  history: HistoryEntry[]
  onSelectQuestion: (q: string) => void
  isStreaming: boolean
}

function StatusDot({ ok }: { ok: boolean }) {
  return ok
    ? <CheckCircle2 size={13} className="text-brand-green shrink-0" />
    : <XCircle    size={13} className="text-red-400 shrink-0" />
}

export function Sidebar({ history, onSelectQuestion, isStreaming }: Props) {
  const [health,  setHealth]  = useState<HealthStatus | null>(null)
  const [sources, setSources] = useState<CorpusDocument[]>([])

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => null)
    fetchSources().then(setSources).catch(() => null)
    const id = setInterval(() => {
      fetchHealth().then(setHealth).catch(() => null)
    }, 30_000)
    return () => clearInterval(id)
  }, [])

  return (
    <aside className="w-72 shrink-0 h-screen sticky top-0 flex flex-col bg-brand-card border-r border-brand-border overflow-y-auto">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-brand-border">
        <div className="text-brand-green font-bold text-lg tracking-tight">⚖ Sovereign RAG</div>
        <div className="text-brand-muted text-xs mt-0.5">EU Financial Compliance · Local AI</div>
      </div>

      {/* System status */}
      {health && (
        <div className="px-5 py-4 border-b border-brand-border">
          <div className="text-xs font-semibold text-brand-muted uppercase tracking-wider mb-2">
            System
          </div>
          <div className="flex flex-col gap-1.5 text-xs">
            <div className="flex items-center gap-2">
              <StatusDot ok={health.ollama === 'ok'} />
              <span className="text-white">Ollama</span>
              {health.ollama !== 'ok' && (
                <span className="text-red-400 truncate">{health.ollama}</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <StatusDot ok={health.qdrant === 'ok'} />
              <span className="text-white">Qdrant</span>
            </div>
            <div className="flex items-center gap-2 text-brand-muted">
              <Database size={13} className="shrink-0" />
              <span>BM25: {health.bm25_corpus_size.toLocaleString()} chunks</span>
            </div>
          </div>
        </div>
      )}

      {/* Corpus */}
      {sources.length > 0 && (
        <div className="px-5 py-4 border-b border-brand-border">
          <div className="text-xs font-semibold text-brand-muted uppercase tracking-wider mb-2">
            Corpus
          </div>
          {sources.map((doc) => (
            <div key={doc.filename} className="text-xs">
              <span className="text-white font-medium">{doc.filename}</span>
              <span className="text-brand-muted ml-1.5">
                {doc.chunk_count.toLocaleString()} chunks ·{' '}
                {doc.articles_found.length} articles
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Demo questions */}
      <div className="px-5 py-4 border-b border-brand-border">
        <DemoQuestions onSelect={onSelectQuestion} disabled={isStreaming} />
      </div>

      {/* Session history */}
      {history.length > 0 && (
        <div className="px-5 py-4">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-brand-muted uppercase tracking-wider mb-2">
            <Clock size={11} />
            History
          </div>
          <div className="flex flex-col gap-1">
            {history.slice(0, 8).map((entry) => (
              <button
                key={entry.query_id}
                onClick={() => onSelectQuestion(entry.question)}
                disabled={isStreaming}
                className="text-left group"
              >
                <p className="text-xs text-brand-muted group-hover:text-white transition-colors truncate">
                  {entry.question}
                </p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span
                    className={`text-[10px] font-semibold ${
                      entry.confidence >= 4 ? 'text-brand-green' :
                      entry.confidence === 3 ? 'text-yellow-400' : 'text-red-400'
                    }`}
                  >
                    {entry.confidence}/5
                  </span>
                  {entry.flagged && (
                    <span className="text-[10px] text-yellow-400">⚠ flagged</span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="mt-auto px-5 py-4 border-t border-brand-border">
        <p className="text-[10px] text-brand-muted leading-relaxed">
          qwen3.6:27b · nomic-embed-text<br />
          Hybrid BM25 + dense retrieval · RRF fusion<br />
          <span className="text-brand-green font-medium">Zero egress · All inference local</span>
        </p>
      </div>
    </aside>
  )
}
