// Shared hooks and small pieces used across screens.
import { useEffect, useState } from 'react'
import { ErrorState } from '../components/ui'
import { api, ApiError, caseCache } from '../lib/api'
import { computeLean, computeStreak, leanLabel } from '../lib/format'
import { ensurePlayer, onPlayerChange, withPlayer } from '../lib/player'
import { navigate } from '../lib/router'
import type { Profile } from '../lib/types'

/** Fires once at app start so the player exists before they need it. */
export function bootstrapPlayer() {
  ensurePlayer().catch(() => {
    /* backend down; retried on demand */
  })
}

export function usePlayerProfile() {
  const [profile, setProfile] = useState<Profile | null>(null)
  useEffect(() => {
    let alive = true
    const load = () =>
      withPlayer((id) => api.getPlayer(id))
        .then((p) => {
          if (alive) setProfile(p)
        })
        .catch(() => {
          if (alive) setProfile(null)
        })
    load()
    const off = onPlayerChange(() => load())
    return () => {
      alive = false
      off()
    }
  }, [])
  return profile
}

/** Streak and lean from the profile, computed locally when the server doesn't send them. */
export function profileExtras(p: Profile | null) {
  if (!p) return { streak: 0, lean: null as number | null, leanLabel: null as string | null }
  const streak = p.streak ?? computeStreak(p.daily_played)
  const lean = p.lean ?? computeLean(p.recent)
  return { streak, lean, leanLabel: p.lean_label ?? (lean == null ? null : leanLabel(lean)) }
}

export function RatingBadge({ profile }: { profile: Profile | null }) {
  if (!profile || !((profile.history?.length ?? 0) || (profile.daily_played?.length ?? 0))) return null
  const { streak } = profileExtras(profile)
  return (
    <a
      href="#/dossier"
      className="ml-1 hidden items-center gap-1.5 rounded-full border border-con/50 bg-con/10 px-3 py-1 text-sm font-semibold sm:inline-flex"
      aria-label={`Detective rating ${profile.rating}, ${profile.rank}${streak ? `, ${streak}-day streak` : ''}. Open your stats.`}
    >
      {streak > 0 && (
        <span aria-hidden="true">
          <span className="flame">🔥</span>
          <span className="num">{streak}</span>
        </span>
      )}
      <span className="num">{profile.rating}</span>
      <span className="text-muted">{profile.rank}</span>
    </a>
  )
}

export function useNextCase() {
  const [state, setState] = useState<{ loading: boolean; error: unknown }>({ loading: false, error: null })
  const open = async () => {
    setState({ loading: true, error: null })
    try {
      const c = await withPlayer((id) => api.nextCase(id))
      caseCache.set(c.id, c)
      setState({ loading: false, error: null })
      navigate(`/case/${c.id}`)
    } catch (error) {
      setState({ loading: false, error })
    }
  }
  return { ...state, open }
}

export function NextCaseError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  if (!error) return null
  if (error instanceof ApiError && error.status === 404) {
    return (
      <p role="status" className="mt-3 rounded-xl border border-line bg-surface px-4 py-3 text-sm text-muted">
        You’ve solved every case file on record. The Con is preparing new ones. Try the featured case again, or start as a new
        detective.
      </p>
    )
  }
  return <ErrorState error={error} onRetry={onRetry} className="mt-4" />
}

/** Ticks every `ms` so countdowns re-render. */
export function useNow(ms = 1000) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), ms)
    return () => window.clearInterval(id)
  }, [ms])
  return now
}

/** localStorage JSON helpers that never throw (private mode, blocked storage). */
export function loadJSON<T>(key: string): T | null {
  try {
    const raw = window.localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}
export function saveJSON(key: string, value: unknown) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* storage unavailable: progress lives in memory only */
  }
}
