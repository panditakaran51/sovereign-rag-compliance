import { useCallback, useRef, useState } from 'react'
import { streamQuery } from '../lib/api'
import type { HistoryEntry, QueryMetadata } from '../types'

interface StreamState {
  answer: string
  metadata: QueryMetadata | null
  rewrittenQuery: string | null
  isStreaming: boolean
  error: string | null
}

const INITIAL: StreamState = {
  answer:         '',
  metadata:       null,
  rewrittenQuery: null,
  isStreaming:    false,
  error:          null,
}

export function useStreamQuery(sessionId: string) {
  const [state, setState] = useState<StreamState>(INITIAL)
  const [history, setHistory]   = useState<HistoryEntry[]>([])
  const abortRef = useRef<AbortController | null>(null)

  const submit = useCallback(async (question: string) => {
    // Cancel any in-flight request
    abortRef.current?.abort()
    abortRef.current = new AbortController()

    setState({ ...INITIAL, isStreaming: true })

    try {
      await streamQuery(
        question,
        sessionId,
        (event) => {
          switch (event.type) {
            case 'token':
              setState((s) => ({ ...s, answer: s.answer + event.data }))
              break
            case 'rewrite':
              if (event.data.trim() !== question.trim()) {
                setState((s) => ({ ...s, rewrittenQuery: event.data }))
              }
              break
            case 'metadata':
              setState((s) => ({ ...s, metadata: event.data, isStreaming: false }))
              // Add to history
              setHistory((h) => [
                {
                  query_id:   event.data.query_id,
                  question,
                  confidence: event.data.confidence,
                  flagged:    event.data.flagged,
                  timestamp:  new Date().toISOString(),
                },
                ...h,
              ].slice(0, 20)) // keep last 20
              break
            case 'error':
              setState((s) => ({ ...s, error: event.data, isStreaming: false }))
              break
          }
        },
        abortRef.current.signal,
      )
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setState((s) => ({
          ...s,
          isStreaming: false,
          error: (err as Error).message,
        }))
      }
    }
  }, [sessionId])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    setState(INITIAL)
  }, [])

  return { ...state, history, submit, reset }
}
