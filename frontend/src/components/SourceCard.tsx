import { FileText } from 'lucide-react'
import type { Source } from '../types'

interface Props {
  source: Source
  rank: number
}

export function SourceCard({ source, rank }: Props) {
  return (
    <div className="bg-brand-card border border-brand-border rounded-lg p-4">
      <div className="flex items-start gap-3">
        <span className="shrink-0 flex items-center justify-center w-6 h-6 rounded-full bg-brand-green/20 text-brand-green text-xs font-bold mt-0.5">
          {rank}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-2">
            <div className="flex items-center gap-1.5 text-sm font-medium text-white">
              <FileText size={13} className="text-brand-muted" />
              {source.document}
            </div>
            <span className="text-brand-muted text-xs">p.{source.page}</span>
            {source.articles.map((a) => (
              <span
                key={a}
                className="px-1.5 py-0.5 rounded text-xs font-semibold bg-brand-green text-brand-navy"
              >
                Art. {a}
              </span>
            ))}
          </div>
          <p className="text-brand-muted text-sm leading-relaxed font-mono line-clamp-4">
            {source.excerpt}
          </p>
        </div>
      </div>
    </div>
  )
}
