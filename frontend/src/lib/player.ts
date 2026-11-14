import { api, ApiError } from './api'

const KEY = 'gos.player_id'
let memoryId: string | null = null
let pending: Promise<string> | null = null
const listeners = new Set<(id: string | null) => void>()

function readStored(): string | null {
  try {
    return window.localStorage.getItem(KEY)
  } catch {
    return null
  }
}

function store(id: string | null) {
  memoryId = id
  try {
    if (id) window.localStorage.setItem(KEY, id)
    else window.localStorage.removeItem(KEY)
  } catch {
    /* storage blocked: the id lives in memory for this tab */
  }
  listeners.forEach((fn) => fn(id))
}

export function getPlayerId(): string | null {
  if (!memoryId) memoryId = readStored()
  return memoryId
}

/** Returns the stored player id, creating a player on the server the first time. */
export function ensurePlayer(): Promise<string> {
  const id = getPlayerId()
  if (id) return Promise.resolve(id)
  if (!pending) {
    pending = api
      .createPlayer()
      .then((r) => {
        store(r.player_id)
        return r.player_id
      })
      .finally(() => {
        pending = null
      })
  }
  return pending
}

/** Forget this detective and start fresh (new clue budget, empty dossier). */
export async function newDetective(): Promise<string> {
  store(null)
  return ensurePlayer()
}

export function onPlayerChange(fn: (id: string | null) => void): () => void {
  listeners.add(fn)
  return () => {
    listeners.delete(fn)
  }
}

function isUnknownPlayer(e: unknown): boolean {
  return e instanceof ApiError && e.status === 404 && /player/i.test(e.message)
}

/** Runs fn with the player id; if the server forgot the player, re-creates it once and retries. */
export async function withPlayer<T>(fn: (playerId: string) => Promise<T>): Promise<T> {
  const id = await ensurePlayer()
  try {
    return await fn(id)
  } catch (e) {
    if (!isUnknownPlayer(e)) throw e
    store(null)
    return fn(await ensurePlayer())
  }
}
