import type { Outcome, TrickId } from './types'

export const TRICK_LABELS: Record<string, string> = {
  'out-of-context-quote': 'Out of context',
  'misleading-chart': 'Misleading chart',
  'cherry-picked-stat': 'Cherry-picked stat',
  'edited-detail': 'Edited detail',
}

export function trickLabel(id: TrickId | null | undefined): string {
  if (!id) return 'Not sure'
  return TRICK_LABELS[id] ?? id.replace(/[-_]+/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

/** The kind of post each trick disguises itself as (CONTRACT §3). */
export const TRICK_FORMAT: Record<string, string> = {
  'out-of-context-quote': 'quotes',
  'misleading-chart': 'charts',
  'cherry-picked-stat': 'statistics',
  'edited-detail': 'headlines',
}

export const caseNo = (n: number | undefined | null) => `#${String(n ?? 0).padStart(4, '0')}`

export const watermark = (n: number | undefined | null) => `CASE ${caseNo(n)} · TRAINING MATERIAL`

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function shortDate(iso: string | null | undefined, withYear = true): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const base = `${MONTHS[d.getMonth()]} ${d.getDate()}`
  return withYear ? `${base}, ${d.getFullYear()}` : base
}

/** Social-app style: 5m, 3h, 2d, then "Sep 24". */
export function relativeTime(iso: string, now = Date.now()): string {
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return ''
  const s = Math.max(0, (now - t) / 1000)
  if (s < 60) return 'now'
  if (s < 3600) return `${Math.floor(s / 60)}m`
  if (s < 86400) return `${Math.floor(s / 3600)}h`
  if (s < 7 * 86400) return `${Math.floor(s / 86400)}d`
  return shortDate(iso, new Date(t).getFullYear() !== new Date(now).getFullYear())
}

export function dateRange(isos: string[]): string {
  const ts = isos.map((i) => new Date(i).getTime()).filter((n) => !Number.isNaN(n))
  if (!ts.length) return ''
  const a = new Date(Math.min(...ts))
  const b = new Date(Math.max(...ts))
  const right = `${MONTHS[b.getMonth()]} ${b.getDate()}, ${b.getFullYear()}`
  if (a.toDateString() === b.toDateString()) return right
  const sameYear = a.getFullYear() === b.getFullYear()
  const left = `${MONTHS[a.getMonth()]} ${a.getDate()}${sameYear ? '' : `, ${a.getFullYear()}`}`
  return `${left} – ${right}`
}

export function initials(name: string): string {
  const words = name
    .replace(/[^\p{L}\p{N} ]/gu, ' ')
    .split(/\s+/)
    .filter(Boolean)
  return (words.slice(0, 2).map((w) => w[0]).join('') || '?').toUpperCase()
}

export function formatNumber(v: number, digits?: number): string {
  if (!Number.isFinite(v)) return String(v)
  const d = digits ?? (Math.abs(v) < 1000 && !Number.isInteger(v) ? 2 : 0)
  return v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })
}

export const RANKS: { min: number; title: string }[] = [
  { min: 90, title: 'Untouchable' },
  { min: 80, title: 'Chief' },
  { min: 60, title: 'Inspector' },
  { min: 40, title: 'Gumshoe' },
  { min: 0, title: 'Rookie' },
]

export const rankFor = (rating: number) => RANKS.find((r) => rating >= r.min)?.title ?? 'Rookie'

export interface OutcomeStyle {
  word: string
  icon: string
  /** Accent for borders, rings and text on the page (CSS var). */
  color: string
  /** Stamp / tile fill and the ink on it (CONTRACT §8.2: green, salt/white, amber, red). */
  fill: string
  ink: string
  blurb: string
  emoji: string
}

/** One mapping for every stamp, tile and grid (CONTRACT §8.2). */
export const OUTCOMES: Record<Outcome, OutcomeStyle> = {
  trusted: {
    word: 'Trusted',
    icon: '✓',
    color: 'var(--real)',
    fill: 'var(--real)',
    ink: '#FFFFFF',
    blurb: 'It was real, and you trusted it.',
    emoji: '🟩',
  },
  caught: {
    word: 'Caught',
    icon: '✓',
    color: 'var(--salt-edge)',
    fill: 'var(--salt)',
    ink: 'var(--salt-ink)',
    blurb: 'Doctored, and you caught it.',
    emoji: '🧂',
  },
  false_alarm: {
    word: 'False alarm',
    icon: '⚠',
    color: 'var(--alarm)',
    fill: 'var(--alarm)',
    ink: '#1B1B1F',
    blurb: 'It was real. Surprising, but true.',
    emoji: '🟨',
  },
  fooled: {
    word: 'Fooled',
    icon: '✗',
    color: 'var(--doctored)',
    fill: 'var(--doctored)',
    ink: '#FFFFFF',
    blurb: 'Doctored, and it got past you.',
    emoji: '🟥',
  },
}

export const GRID_LEGEND = '🟩 trusted · 🧂 caught · 🟨 false alarm · 🟥 fooled'

export function outcomeStyle(o: string): OutcomeStyle {
  return (
    OUTCOMES[o as Outcome] ?? { word: o, icon: '•', color: 'var(--muted)', fill: 'var(--surface-2)', ink: 'var(--text)', blurb: '', emoji: '⬜' }
  )
}

export function pct(rate: number | undefined | null): number {
  if (rate == null || !Number.isFinite(rate)) return 0
  return Math.round(Math.max(0, Math.min(1, rate)) * 100)
}

// ---- v2 helpers ---------------------------------------------------------------

/** CONTRACT §7.2 lean bands: negative = gullible, positive = paranoid. */
export function leanLabel(lean: number): string {
  if (lean <= -0.5) return 'Gullible'
  if (lean <= -0.15) return 'Trusting'
  if (lean < 0.15) return 'Balanced'
  if (lean < 0.5) return 'Suspicious'
  return 'Paranoid'
}

/** lean = false_alarm_rate − miss_rate over the recent posts (used when the server doesn't send it). */
export function computeLean(recent: { doctored: boolean; outcome: string }[] | undefined): number | null {
  if (!recent?.length) return null
  const fakes = recent.filter((r) => r.doctored)
  const reals = recent.filter((r) => !r.doctored)
  const miss = fakes.length ? fakes.filter((r) => r.outcome === 'fooled').length / fakes.length : 0
  const fa = reals.length ? reals.filter((r) => r.outcome === 'false_alarm').length / reals.length : 0
  return Math.max(-1, Math.min(1, fa - miss))
}

/** "2025-04" -> "Apr 2025"; anything else is returned unchanged. */
export function formatMonth(label: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(label)
  if (!m) return label
  return `${MONTHS[Number(m[2]) - 1] ?? m[2]} ${m[1]}`
}

const ET = 'America/New_York'

/** Today's date in Eastern Time as YYYY-MM-DD (the Daily resets at midnight ET). */
export function etDate(d = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: ET, year: 'numeric', month: '2-digit', day: '2-digit' }).format(d)
}

export function msUntilMidnightET(d = new Date()): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: ET,
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).formatToParts(d)
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value ?? 0)
  const elapsed = ((get('hour') % 24) * 3600 + get('minute') * 60 + get('second')) * 1000 + d.getMilliseconds()
  return Math.max(0, 24 * 3600 * 1000 - elapsed)
}

export function hms(ms: number): string {
  const s = Math.floor(ms / 1000)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(Math.floor(s / 3600))}:${p(Math.floor((s % 3600) / 60))}:${p(s % 60)}`
}

/** Consecutive days played, ending today or yesterday (ET). Streaks count days played, not perfect days. */
export function computeStreak(dates: string[] | undefined, today = etDate()): number {
  if (!dates?.length) return 0
  const set = new Set(dates)
  const day = (iso: string, delta: number) => {
    const t = new Date(`${iso}T12:00:00Z`)
    t.setUTCDate(t.getUTCDate() + delta)
    return t.toISOString().slice(0, 10)
  }
  let cur = set.has(today) ? today : set.has(day(today, -1)) ? day(today, -1) : null
  let n = 0
  while (cur && set.has(cur)) {
    n += 1
    cur = day(cur, -1)
  }
  return n
}

/** The share grid in v2.1 emoji (CONTRACT §8.2) for a list of outcomes. */
export const gridFor = (outcomes: string[]) => outcomes.map((o) => outcomeStyle(o).emoji).join('')

/** A value with its unit, for chart annotations: "$2.10", "19¢", "4.5%". */
export function withUnit(v: number, unit: string | null | undefined): string {
  const u = (unit ?? '').trim()
  if (u.startsWith('$')) return `$${formatNumber(v, Number.isInteger(v) && Math.abs(v) >= 10 ? 0 : 2)}`
  const d = Number.isInteger(v) ? 0 : Math.abs(v - Math.round(v * 10) / 10) < 1e-9 ? 1 : 2
  if (u.startsWith('¢')) return `${formatNumber(v, d)}¢`
  if (u.startsWith('%')) return `${formatNumber(v, d)}%`
  return formatNumber(v, d)
}

/** Decimal places that keep ticks spaced `step` apart distinct (0.05 -> 2, 0.5 -> 1, 5 -> 0). */
export function decimalsFor(step: number): number {
  if (!(step > 0) || !Number.isFinite(step)) return 0
  return Math.max(0, Math.min(4, Math.ceil(-Math.log10(step) - 1e-9)))
}
