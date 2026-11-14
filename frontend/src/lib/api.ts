import type {
  AnswerResponse,
  CaseMeta,
  ConLevel,
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
  EditorCase,
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

const json = (body: unknown, headers?: Record<string, string>): RequestInit => ({ method: 'POST', body: JSON.stringify(body), headers })
const enc = encodeURIComponent

// ---- Tokens (CONTRACT §8.5, §8.6) ------------------------------------------------------------
const DEMO_KEY = 'gos.demo_token'
const EDITOR_KEY = 'gos.editor_token'
const OLD_EDITOR_KEY = 'gos.teacher_token' // the key's old name; read once and moved to EDITOR_KEY
let memDemo: string | null = null
let memEditor: string | null = null

/** Reads `?demo=TOKEN` (before or inside the hash) once, stores it, and strips it from the address bar. */
export function captureDemoToken() {
  try {
    const search = new URLSearchParams(window.location.search)
    const hash = window.location.hash
    const qi = hash.indexOf('?')
    const hashParams = qi >= 0 ? new URLSearchParams(hash.slice(qi + 1)) : null
    const token = search.get('demo') ?? hashParams?.get('demo') ?? null
    if (!token) return
    memDemo = token
    try {
      window.localStorage.setItem(DEMO_KEY, token)
    } catch {
      /* memory only */
    }
    search.delete('demo')
    hashParams?.delete('demo')
    const rest = hashParams?.toString()
    const newHash = qi >= 0 ? hash.slice(0, qi) + (rest ? `?${rest}` : '') : hash
    const qs = search.toString()
    window.history.replaceState(null, '', `${window.location.pathname}${qs ? `?${qs}` : ''}${newHash}`)
  } catch {
    /* no URL API: nothing to capture */
  }
}

export function getDemoToken(): string | null {
  if (memDemo) return memDemo
  try {
    memDemo = window.localStorage.getItem(DEMO_KEY)
  } catch {
    /* ignore */
  }
  return memDemo
}

export function getEditorToken(): string | null {
  if (memEditor) return memEditor
  try {
    memEditor = window.sessionStorage.getItem(EDITOR_KEY)
    const old = window.sessionStorage.getItem(OLD_EDITOR_KEY)
    if (old != null) {
      // One-time move from the old key name (a tab that unlocked the desk before the rename).
      window.sessionStorage.removeItem(OLD_EDITOR_KEY)
      if (!memEditor && old) {
        memEditor = old
        window.sessionStorage.setItem(EDITOR_KEY, old)
      }
    }
  } catch {
    /* ignore */
  }
  return memEditor
}

export function setEditorToken(token: string | null) {
  memEditor = token
  try {
    if (token) window.sessionStorage.setItem(EDITOR_KEY, token)
    else window.sessionStorage.removeItem(EDITOR_KEY)
  } catch {
    /* memory only */
  }
}

const demoHeaders = (): Record<string, string> => {
  const t = getDemoToken()
  return t ? { 'X-Demo-Token': t } : {}
}
const editorHeaders = (): Record<string, string> => {
  const t = getEditorToken()
  return t ? { 'X-Editor-Token': t } : {}
}

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
  /** `level` is the Con's level (CONTRACT §8.1). Sends the demo token, if any, to skip the live caps (§8.5). */
  foolJudge: (playerId: string, deckId: string, edit: FoolEdit, level: ConLevel) =>
    request<FoolJudgeResponse>('/fool/judge', json({ player_id: playerId, deck_id: deckId, edit, level }, demoHeaders())),

  pipelineLog: (caseId: string) => request<PipelineEvent[] | { events: PipelineEvent[] }>(`/cases/${enc(caseId)}/pipeline-log`),

  // Editor's Desk routes send X-Editor-Token when one is stored (public mode, CONTRACT §8.6).
  editorQueue: () => request<QueueItem[] | { cases: QueueItem[] }>('/editor/queue', { headers: editorHeaders() }),
  editorCase: (id: string) => request<EditorCase>(`/editor/cases/${enc(id)}`, { headers: editorHeaders() }),
  approve: (id: string) => request<CaseMeta>(`/editor/cases/${enc(id)}/approve`, json({}, editorHeaders())),
  reject: (id: string, reason: string) => request<CaseMeta>(`/editor/cases/${enc(id)}/reject`, json({ reason }, editorHeaders())),
}

/** Case objects fetched once are kept so navigation doesn't refetch them. */
export const caseCache = new Map<string, GameCase>()
