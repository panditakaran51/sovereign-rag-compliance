import type { CorpusDocument, HealthStatus, QueryMetadata, StreamEvent } from '../types'

const BASE = '/api'

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${BASE}/health`)
  return res.json()
}

export async function fetchSources(): Promise<CorpusDocument[]> {
  const res = await fetch(`${BASE}/sources`)
  return res.json()
}

export async function fetchAuditLog(limit = 10): Promise<{ entries: unknown[] }> {
  const res = await fetch(`${BASE}/audit-log?limit=${limit}`)
  return res.json()
}

/**
 * Stream a query to the backend SSE endpoint.
 * Parses the raw SSE byte stream into typed StreamEvent objects and
 * calls onEvent for each. Returns when the stream closes.
 *
 * The browser's native Fetch + ReadableStream is used — no external
 * SSE library needed. This pattern works in every modern browser and
 * allows proper AbortController cancellation.
 */
export async function streamQuery(
  question: string,
  sessionId: string,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/query/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, session_id: sessionId }),
    signal,
  })

  if (!res.ok || !res.body) {
    throw new Error(`Backend returned ${res.status}`)
  }

  const reader  = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer       = ''
  let currentEvent = 'message'

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      if (line.startsWith('event:')) {
        currentEvent = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        const raw = line.slice(5).trim()
        if (!raw) continue

        const parsed = JSON.parse(raw) as unknown

        if (currentEvent === 'token') {
          onEvent({ type: 'token', data: parsed as string })
        } else if (currentEvent === 'rewrite') {
          onEvent({ type: 'rewrite', data: parsed as string })
        } else if (currentEvent === 'metadata') {
          onEvent({ type: 'metadata', data: parsed as QueryMetadata })
        } else if (currentEvent === 'error') {
          onEvent({ type: 'error', data: parsed as string })
        }
      } else if (line === '') {
        currentEvent = 'message'
      }
    }
  }
}

export async function uploadDocument(
  file: File,
): Promise<{ job_id: string; filename: string; message: string }> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/ingest`, { method: 'POST', body: form })
  return res.json()
}

export async function pollJob(
  jobId: string,
): Promise<{ status: string; chunks_written?: number; error?: string }> {
  const res = await fetch(`${BASE}/ingest/${jobId}`)
  return res.json()
}
