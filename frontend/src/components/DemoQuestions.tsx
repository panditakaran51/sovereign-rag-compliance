import { Zap } from 'lucide-react'

const QUESTIONS = [
  'What are the general principles of ICT third-party risk management under DORA Article 28?',
  'What logging and incident reporting requirements does DORA impose on financial entities?',
  'What contractual obligations must be included when outsourcing critical functions to an ICT provider?',
  'What does DORA require for digital operational resilience testing (TLPT)?',
  'Can a German bank use a US-based cloud provider for its core banking system?',
]

interface Props {
  onSelect: (question: string) => void
  disabled: boolean
}

export function DemoQuestions({ onSelect, disabled }: Props) {
  return (
    <div>
      <div className="flex items-center gap-1.5 text-xs font-semibold text-brand-muted uppercase tracking-wider mb-2">
        <Zap size={11} />
        Demo questions
      </div>
      <div className="flex flex-col gap-1">
        {QUESTIONS.map((q) => (
          <button
            key={q}
            onClick={() => onSelect(q)}
            disabled={disabled}
            className="text-left text-xs text-brand-muted hover:text-white hover:bg-brand-card transition-colors rounded-md px-2 py-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {q.length > 78 ? q.slice(0, 78) + '…' : q}
          </button>
        ))}
      </div>
    </div>
  )
}
