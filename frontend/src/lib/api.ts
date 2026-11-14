import type {
  AnswerResponse,
  CaseMeta,
  DailyArchiveItem,
  DailyResponse,
  FoolDeckItem,
  FoolEdit,
  FoolJudgeResponse,
  CaseSummary,
  EvidenceResponse,
  GameCase,
  PipelineEvent,
  Profile,
  QueueItem,
  TeacherCase,
  ToolId,
  VerdictChoice,
  VerdictResponse,
} from './types'

export const BACKEND_START_CMD = 'uv run uvicorn backend.app.main:app --reload --port 8000'

export class ApiError extends Error {
  status: number
  /** True when the game server looks unreachable (not running, or the proxy failed). */
  backendDown: boolean
  detail: unknown

  constructor(status: number, message: string, backendDown = false, detail: unknown = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.backendDown = backendDown
    this.detail = detail
  }
}

/** The machine-readable error code, from `{error}` or `{detail: {error}}` or `{detail: "code"}`. */
export function errorCode(e: unknown): string | null {
  if (!(e instanceof ApiError) || !e.detail || typeof e.detail !== 'object') return null
  const d = e.detail as Record<string, unknown>
  if (typeof d.error === 'string') return d.error
  if (d.detail && typeof d.detail === 'object' && typeof (d.detail as Record<string, unknown>).error === 'string') {
    return (d.detail as Record<string, unknown>).error as string
  }
  if (typeof d.detail === 'string' && /^[a-z_]+$/.test(d.detail)) return d.detail
  return null
}

function messageFrom(detail: unknown, fallback: string): string {
  if (detail && typeof detail === 'object') {
    const inner = (detail as Record<string, unknown>).detail
    if (inner && typeof inner === 'object' && !Array.isArray(inner)) {
      const m = (inner as Record<string, unknown>).message ?? (inner as Record<string, unknown>).error
      if (typeof m === 'string') return m
    }
    const d = (detail as Record<string, unknown>).detail ?? (detail as Record<string, unknown>).message ?? (detail as Record<string, unknown>).error
    if (typeof d === 'string') return d
    if (Array.isArray(d) && d.length && typeof d[0] === 'object' && d[0] && 'msg' in d[0]) {
      return String((d[0] as Record<string, unknown>).msg)
    }
  }
  if (typeof detail === 'string' && detail.trim()) return detail.trim().slice(0, 200)
  return fallback
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}), ...init?.headers },
    })
  } catch {
    throw new ApiError(0, 'Could not reach the game server.', true)
  }

  const contentType = res.headers.get('content-type') ?? ''
  const isJson = contentType.includes('json')

  if (!res.ok) {
    let detail: unknown = null
    let text = ''
    try {
      if (isJson) detail = await res.json()
      else text = await res.text()
    } catch {
      /* ignore body errors */
    }
    // Vite's dev proxy answers an empty 500 when the backend isn't listening; a JSON 503 is the
    // server itself talking (e.g. Con the Con's "con_asleep"), so it is not "down".
    const down =
      res.status === 502 ||
      res.status === 504 ||
      (res.status === 503 && !isJson) ||
      (res.status === 500 && !isJson && text.trim() === '')
    throw new ApiError(
      res.status,
      down ? 'Could not reach the game server.' : messageFrom(detail ?? text, `Request failed (${res.status}).`),
      down,
      detail ?? text,
    )
  }

  if (res.status === 204) return undefined as T
  if (!isJson) {
    // e.g. a static host answering index.html for /api/* — there is no backend behind it.
    throw new ApiError(res.status, 'The game server did not answer with JSON.', true)
  }
  return (await res.json()) as T
}

const json = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) })
const enc = encodeURIComponent

export const api = {
  health: () => request<{ ok: boolean }>('/health'),

  createPlayer: () => request<{ player_id: string }>('/players', json({})),
  getPlayer: (id: string) => request<Profile>(`/players/${enc(id)}`),

  listCases: () => request<CaseSummary[]>('/cases'),
  todayCase: () => request<GameCase>('/cases/today'),
  nextCase: (playerId: string) => request<GameCase>(`/cases/next?player_id=${enc(playerId)}`),
  getCase: (id: string) => request<GameCase>(`/cases/${enc(id)}`),

  evidence: (caseId: string, playerId: string, postId: string, tool: ToolId) =>
    request<EvidenceResponse>(`/cases/${enc(caseId)}/evidence`, json({ player_id: playerId, post_id: postId, tool })),

  verdict: (caseId: string, playerId: string, verdicts: Record<string, VerdictChoice>) =>
    request<VerdictResponse>(`/cases/${enc(caseId)}/verdict`, json({ player_id: playerId, verdicts })),

  // ---- v2: the Daily Grain (CONTRACT §7.2)
  daily: (playerId: string) => request<DailyResponse>(`/daily?player_id=${enc(playerId)}`),
  dailyArchive: () => request<DailyArchiveItem[]>('/daily/archive'),
  answer: (caseId: string, playerId: string, postId: string, doctored: boolean, trick: string | null) =>
    request<AnswerResponse>(`/cases/${enc(caseId)}/answer`, json({ player_id: playerId, post_id: postId, doctored, trick })),
  /** Closes a Daily using the answers already recorded card by card. */
  finishDaily: (caseId: string, playerId: string) =>
    request<VerdictResponse>(`/cases/${enc(caseId)}/verdict`, json({ player_id: playerId })),

  // ---- v2: Con the Con (CONTRACT §7.3)
  foolDeck: () => request<FoolDeckItem[] | { items: FoolDeckItem[] }>('/fool/deck'),
  foolJudge: (playerId: string, deckId: string, edit: FoolEdit) =>
    request<FoolJudgeResponse>('/fool/judge', json({ player_id: playerId, deck_id: deckId, edit })),

  pipelineLog: (caseId: string) => request<PipelineEvent[] | { events: PipelineEvent[] }>(`/cases/${enc(caseId)}/pipeline-log`),

  teacherQueue: () => request<QueueItem[] | { cases: QueueItem[] }>('/teacher/queue'),
  teacherCase: (id: string) => request<TeacherCase>(`/teacher/cases/${enc(id)}`),
  approve: (id: string) => request<CaseMeta>(`/teacher/cases/${enc(id)}/approve`, json({})),
  reject: (id: string, reason: string) => request<CaseMeta>(`/teacher/cases/${enc(id)}/reject`, json({ reason })),
}

/** Case objects fetched once are kept so navigation doesn't refetch them. */
export const caseCache = new Map<string, GameCase>()
