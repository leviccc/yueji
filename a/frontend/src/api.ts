export type Statement = 'fact' | 'plan' | 'claim' | 'inference'
export type Relation = 'before' | 'after' | 'simultaneous' | 'unknown'
export interface Evidence {
  id: string
  paragraph_id: string
  chapter: number
  paragraph_number: number
  start: number
  end: number
  quote: string
}
export interface Character { id: string; name: string }
export interface Event {
  id: string
  title: string
  participants: Character[]
  action: string
  location: string | null
  time_expression: string | null
  time_bounds: { earliest: string | null; latest: string | null; anchor: string | null } | null
  result: string | null
  statement: Statement
  speaker: string | null
  importance: 'key' | 'supporting'
  retrospective: boolean
  known_from: number
  last_mentioned: number
  evidence: Evidence[]
}
export interface Constraint {
  id: string
  source: string
  target: string
  relation: Relation
  evidence_type: 'explicit' | 'anchored' | 'inferred'
  evidence: Evidence[]
  known_from: number
  reason: string
}
export interface Timeline {
  events: Event[]
  constraints: Constraint[]
  accepted_ids: string[]
  pending_ids: string[]
  simultaneous_groups: string[][]
  layers: string[][]
  unplaced_ids: string[]
  predecessors: Record<string, string[]>
  conflicts: { constraint_ids: string[]; pending_ids: string[]; reason: string }[]
}
export interface SummaryItem {
  text: string
  event_ids: string[]
  statement: Statement
  evidence: Evidence[]
}
export interface Summary { items: SummaryItem[]; unresolved_questions: SummaryItem[] }
export interface Scope {
  book_id: string
  cutoff_chapter: number
  chapter_range: number[]
  knowledge_version: string
}
export interface Book { id: string; title: string; chapter_count: number; progress: number }
export interface NovelPreview { boundaries: { line: number; title: string }[]; lines: { line: number; text: string }[] }
export interface Task {
  id: string
  book_id: string
  cutoff: number
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'paused'
  stage: string
  completed: number
  total: number
  error: string | null
}
export interface ChapterInfo { id: string; number: number; title: string | null }
export interface Paragraph { id: string; number: number; text: string }
export interface Source { chapter: { number: number; title: string; paragraphs: Paragraph[] }; scope: Scope }
export const statementLabel: Record<Statement, string> = {
  fact: '已发生', plan: '计划', claim: '角色陈述', inference: '推断',
}

/** Send a same-origin API request and normalize HTTP or response-format errors. */
export async function request<T>(path: string, init?: RequestInit, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api${path}`, { ...init, signal })
  const contentType = response.headers.get('content-type') ?? ''
  const responseText = await response.text()
  let body: unknown
  if (contentType.includes('application/json')) {
    try {
      body = JSON.parse(responseText)
    } catch {
      body = undefined
    }
  }
  if (!response.ok) {
    const detail = body && typeof body === 'object' && 'detail' in body
      ? body.detail
      : undefined
    const message = typeof detail === 'string'
      ? detail
      : `请求失败（HTTP ${response.status}）`
    throw new Error(message)
  }
  if (!contentType.includes('application/json') || body === undefined) {
    throw new Error('服务返回了无效响应')
  }
  return body as T
}

export function jsonBody(value: unknown): RequestInit {
  return { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value) }
}

/** Create requests that share one book, reading cutoff, and cancellation signal. */
export function plotClient(bookId: string, cutoff: number, signal?: AbortSignal) {
  const root = `/books/${encodeURIComponent(bookId)}`
  const query = `cutoff=${cutoff}`
  return {
    timeline: () => request<{ scope: Scope; timeline: Timeline }>(`${root}/timeline?${query}`, undefined, signal),
    summary: (chapter: number) => request<{ scope: Scope; summary: Summary }>(`${root}/summaries/${chapter}?${query}`, undefined, signal),
    recap: () => request<{ scope: Scope; recap: Summary }>(`${root}/recap?${query}`, { method: 'POST' }, signal),
    source: (chapter: number) => request<Source>(`${root}/chapters/${chapter}/source?${query}`, undefined, signal),
    chapters: () => request<{ chapters: ChapterInfo[]; scope: Scope }>(`${root}/chapters?${query}`, undefined, signal),
  }
}
