import { clsx } from 'clsx'

interface Props {
  score: number   // 1–5
  flagged: boolean
}

const LABELS: Record<number, string> = {
  1: 'Not supported',
  2: 'Weakly supported',
  3: 'Reasonably supported',
  4: 'Well supported',
  5: 'Fully supported',
}

export function ConfidenceBadge({ score, flagged }: Props) {
  const label = LABELS[score] ?? 'Unknown'

  return (
    <div className="flex flex-col gap-2 mt-4">
      <div className="flex items-center gap-2">
        <span className="text-sm text-brand-muted font-medium">Confidence</span>
        <span
          className={clsx(
            'flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-semibold',
            score >= 4 && 'bg-brand-green/15 text-brand-green',
            score === 3 && 'bg-yellow-500/15 text-yellow-400',
            score <= 2 && 'bg-red-500/15 text-red-400',
          )}
        >
          <span className="text-xs">{'▌'.repeat(score)}{'░'.repeat(5 - score)}</span>
          {score}/5 — {label}
        </span>
      </div>

      {flagged && (
        <div className="flex items-start gap-2 bg-yellow-500/10 border border-yellow-500/30 rounded-lg px-4 py-3 text-yellow-400 text-sm">
          <span className="shrink-0 mt-0.5">⚠</span>
          <span>
            This answer scored below the confidence threshold. It should be reviewed
            by a qualified compliance professional before acting on it.
          </span>
        </div>
      )}
    </div>
  )
}
