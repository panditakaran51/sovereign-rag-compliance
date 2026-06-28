export interface Source {
  document: string
  page: number
  articles: string[]
  excerpt: string
}

export interface QueryMetadata {
  query_id: string
  confidence: number     // 1–5
  flagged: boolean
  duration_ms: number
  sources: Source[]
}

export interface HistoryEntry {
  query_id: string
  question: string
  confidence: number
  flagged: boolean
  timestamp: string
}

export interface CorpusDocument {
  filename: string
  chunk_count: number
  articles_found: string[]
}

export interface HealthStatus {
  status: 'ok' | 'degraded' | 'unreachable'
  ollama: string
  qdrant: string
  bm25_corpus_size: number
}

export type StreamEvent =
  | { type: 'token';    data: string }
  | { type: 'rewrite';  data: string }
  | { type: 'metadata'; data: QueryMetadata }
  | { type: 'error';    data: string }
