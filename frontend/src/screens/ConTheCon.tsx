import { useEffect, useMemo, useRef, useState } from 'react'
import { ConMascot } from '../components/Art'
import { ConBubble } from '../components/ConBubble'
import { TOOLS } from '../components/EvidenceKit'
import { SiteHeader } from '../components/Header'
import { FeedCard } from '../components/PostCard'
import { chartDomain, niceStep, PostChart } from '../components/PostChart'
import { DiffView, change } from '../components/Reveal'
import { Button, ErrorState, Loading, SectionLabel } from '../components/ui'
import { api, ApiError, errorCode } from '../lib/api'
import { formatMonth, formatNumber, trickLabel, withUnit } from '../lib/format'
import { useAsync, useElementHeight, useReducedMotion } from '../lib/hooks'
import { withPlayer } from '../lib/player'
import { play } from '../lib/sound'
import type { Author, ChartSpec, ConLevel, FoolDeckItem, FoolEdit, FoolJudgeResponse, FoolOutcome, FoolTool, LevelRecord, Post } from '../lib/types'
import { loadJSON, saveJSON } from './common'

const WATERMARK = 'CON THE CON · TRAINING MATERIAL'
const MIN_KEEP = 4

type Tool = FoolTool | 'none'

const TOOL_META: Record<Tool, { icon: string; label: string; hint: string }> = {
  crop: { icon: '✂️', label: 'Crop', hint: 'Tap words to cut them. Deletion only: you can’t add words.' },
  axis: { icon: '📉', label: 'Axis', hint: 'Slide where the y-axis starts. Same numbers, steeper story.' },
  window: { icon: '🗓️', label: 'Window', hint: 'Pick which two months to compare.' },
  drop: { icon: '🔢', label: 'Drop context', hint: 'Hide the number that puts the claim in context.' },
  none: { icon: '🙈', label: 'Leave it real', hint: 'The bluff: send it untouched and see if the Con doubts the truth.' },
}

// ---- the three bosses (CONTRACT §8.1) ----------------------------------------------------------
interface Boss {
  level: ConLevel
  name: string
  icon: string
  blurb: string
  checks: boolean
}
const BOSSES: Boss[] = [
  { level: 1, name: 'Rookie Con', icon: '🃏', blurb: 'judges by vibes, no evidence', checks: false },
  { level: 2, name: 'Street Con', icon: '🕶️', blurb: 'one check, fast brain', checks: true },
  { level: 3, name: 'Master Con', icon: '🎩', blurb: 'one check, full brain', checks: true },
]
const bossOf = (l: number | null | undefined) => BOSSES.find((b) => b.level === l) ?? BOSSES[2]

/** CONTRACT §8.2 wording. `win` = the Con got it wrong. */
const OUTCOME: Record<FoolOutcome, { title: string; sub: string; color: string; win: boolean | null; icon: string }> = {
  caught: { title: 'BUSTED', sub: 'The Con caught your edit.', color: 'var(--doctored)', win: false, icon: '🚨' },
  fooled_the_con: { title: 'FOOLED THE CON', sub: 'Your edit got past the AI.', color: 'var(--real)', win: true, icon: '🎉' },
  con_false_alarm: {
    title: 'FALSE ALARM',
    sub: 'You sent the truth, untouched, and the Con called it doctored. You win.',
    color: 'var(--alarm)',
    win: true,
    icon: '🎉',
  },
  con_trusted: { title: 'TRUSTED', sub: 'A real post, called real. A draw.', color: 'var(--real)', win: null, icon: '🤝' },
}
const isWin = (o: FoolOutcome) => OUTCOME[o]?.win === true

// Shown only if the server's deck doesn't name the made-up account yet. Never a realistic persona.
const UNNAMED_ACCOUNT: Author = { name: 'A made-up account', handle: '@made_up_account', kind: 'person', verified: false, avatar_color: '#64748B' }

// ---- persistence (all wrapped; storage may be blocked) ----------------------------------------
interface Round {
  deck_id: string
  outcome: FoolOutcome
  level: ConLevel
  con_line?: string | null
}
interface SavedRound {
  deck_id: string
  edit: FoolEdit
  level: ConLevel
}
type Board = Partial<Record<'1' | '2' | '3', LevelRecord>>

const SESSION_KEY = 'gos.fool.session'
const LEVEL_KEY = 'gos.fool.level'
const SAVED_KEY = 'gos.fool.saved'
const BOARD_KEY = 'gos.fool.board'
let memoryRounds: Round[] = []

function loadRounds(): Round[] {
  try {
    const raw = window.sessionStorage.getItem(SESSION_KEY)
    if (raw) return (JSON.parse(raw) as Round[]).map((r) => ({ ...r, level: (r.level ?? 3) as ConLevel }))
  } catch {
    /* fall back to memory */
  }
  return memoryRounds
}
function saveRounds(r: Round[]) {
  memoryRounds = r
  try {
    window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(r))
  } catch {
    /* memory only */
  }
}
function loadLevel(): ConLevel {
  const v = loadJSON<number>(LEVEL_KEY)
  return v === 1 || v === 2 || v === 3 ? v : 1 // first-timers start against the Rookie
}

/**
 * Rounds already judged on the server are cached there, so replaying them is free and always allowed (§8.5).
 * These match real verdicts in the shipped data/fool_cache (checked against the server's cache key, Master Con);
 * rounds this browser plays are remembered and offered first.
 */
const NET_CROP = Array.from({ length: 29 }, (_, i) => i).filter((i) => i !== 17) // delete only "net"
const DEMO_ROUNDS: SavedRound[] = [
  // Seeded Nov 14 with real live verdicts: two wins against the Con first, then busts at each level.
  { deck_id: 'dino-blood-headline', edit: { type: 'crop', keep_word_indices: [0, 3, 4, 5, 6, 7, 8] }, level: 1 },
  { deck_id: 'candy-two-years', edit: { type: 'drop', drop: 'one_year' }, level: 2 },
  { deck_id: 'eia-nj-power', edit: { type: 'axis', y_min: 19.5 }, level: 3 },
  { deck_id: 'hs-net-increase', edit: { type: 'crop', keep_word_indices: NET_CROP }, level: 3 },
  { deck_id: 'eia-nj-power', edit: { type: 'window', window: ['2025-04', '2026-07'] }, level: 2 },
  { deck_id: 'robinson-100-percent', edit: { type: 'crop', keep_word_indices: [1, 2, 3, 4, 5, 6, 7] }, level: 1 },
  { deck_id: 'eia-nj-power', edit: { type: 'none' }, level: 3 },
  { deck_id: 'rebhorn-peak-hours', edit: { type: 'none' }, level: 3 },
  { deck_id: 'falkner-watching-sports', edit: { type: 'none' }, level: 3 },
]
function loadSaved(): SavedRound[] {
  return loadJSON<SavedRound[]>(SAVED_KEY) ?? []
}
function rememberSaved(r: SavedRound) {
  const key = JSON.stringify(r)
  const list = [r, ...loadSaved().filter((x) => JSON.stringify(x) !== key)].slice(0, 12)
  saveJSON(SAVED_KEY, list)
}

function editLabel(item: FoolDeckItem | undefined, e: FoolEdit): string {
  switch (e.type) {
    case 'axis':
      return `📉 Axis from ${withUnit(e.y_min, item?.post.chart?.unit)}`
    case 'window':
      return `🗓️ ${formatMonth(e.window[0])} vs ${formatMonth(e.window[1])}`
    case 'crop': {
      const words = item?.editable.quote_words ?? []
      const cut = words.filter((_, i) => !e.keep_word_indices.includes(i))
      return `✂️ Cut “${cut.slice(0, 4).join(' ')}${cut.length > 4 ? '…' : ''}”`
    }
    case 'drop': {
      const d = item?.editable.stat?.droppable.find((x) => x.id === e.drop)
      return `🔢 Hide ${d ? `“${d.text.slice(0, 40)}${d.text.length > 40 ? '…' : ''}”` : e.drop}`
    }
    default:
      return '🙈 Bluff: untouched'
  }
}

// ---- edit helpers -----------------------------------------------------------------------------
function seriesOf(item: FoolDeckItem) {
  return item.editable.chart_series ?? item.post.chart?.points ?? []
}

/** The values the post actually displays: the axis rule is y_min < their minimum (apply_edit). */
function displayedValues(item: FoolDeckItem): number[] {
  return (item.post.chart?.points ?? []).map((p) => p.value)
}

/** Mirrors pipeline.fool._axis_top: the top a truncated axis gets. */
function axisTop(values: number[], yMin: number): number | null {
  if (yMin <= 0 || !values.length) return null
  const hi = Math.max(...values)
  const top = Math.ceil(hi)
  return top <= hi ? top + 1 : top
}

/** The slider's range: from 0 up to just below the lowest displayed value, in steps fine enough to matter. */
function axisRange(item: FoolDeckItem): { max: number; step: number; lowest: number } {
  const values = displayedValues(item)
  const lowest = values.length ? Math.min(...values) : 1
  const step = niceStep(lowest, 50)
  let max = Number((Math.floor((lowest - 1e-9) / step) * step).toFixed(6))
  if (max >= lowest) max = Number((max - step).toFixed(6))
  return { max: Math.max(0, max), step, lowest }
}

function defaultWindow(item: FoolDeckItem): [string, string] {
  const s = seriesOf(item)
  if (!s.length) return ['', '']
  const pts = item.post.chart?.points ?? []
  const find = (label?: string) => s.find((p) => p.label === label || formatMonth(p.label) === label)?.label
  const a = find(pts[0]?.label) ?? s[0].label
  const b = find(pts[pts.length - 1]?.label) ?? s[s.length - 1].label
  return [a, b]
}

interface EditorState {
  tool: Tool
  removed: number[]
  yMin: number
  window: [string, string]
  drop: string | null
}

function initialState(item: FoolDeckItem): EditorState {
  return {
    tool: item.tools[0] ?? 'none',
    removed: [],
    yMin: item.post.chart?.y_min ?? 0,
    window: defaultWindow(item),
    drop: null,
  }
}

function stateFromEdit(item: FoolDeckItem, e: FoolEdit): EditorState {
  const st = initialState(item)
  const words = item.editable.quote_words ?? []
  switch (e.type) {
    case 'crop':
      return { ...st, tool: 'crop', removed: words.map((_, i) => i).filter((i) => !e.keep_word_indices.includes(i)) }
    case 'axis':
      return { ...st, tool: 'axis', yMin: e.y_min }
    case 'window':
      return { ...st, tool: 'window', window: e.window }
    case 'drop':
      return { ...st, tool: 'drop', drop: e.drop }
    default:
      return { ...st, tool: 'none' }
  }
}

function buildEdit(item: FoolDeckItem, st: EditorState): FoolEdit {
  const words = item.editable.quote_words ?? []
  switch (st.tool) {
    case 'crop':
      return st.removed.length ? { type: 'crop', keep_word_indices: words.map((_, i) => i).filter((i) => !st.removed.includes(i)) } : { type: 'none' }
    case 'axis':
      return st.yMin !== (item.post.chart?.y_min ?? 0) ? { type: 'axis', y_min: st.yMin } : { type: 'none' }
    case 'window': {
      const [a, b] = defaultWindow(item)
      return st.window[0] !== a || st.window[1] !== b ? { type: 'window', window: st.window } : { type: 'none' }
    }
    case 'drop':
      return st.drop ? { type: 'drop', drop: st.drop } : { type: 'none' }
    default:
      return { type: 'none' }
  }
}

const g = (v: number) => String(Number(v.toPrecision(6)))

/** Mirrors pipeline.fool.apply_edit for the live preview (the server stays the source of truth). */
function previewPost(item: FoolDeckItem, edit: FoolEdit, author: Author): Post {
  const p: Post = { ...item.post, quote: item.post.quote ? { ...item.post.quote } : item.post.quote }
  if (edit.type === 'none') return p
  if (edit.type === 'crop') {
    const words = item.editable.quote_words ?? []
    let shown = edit.keep_word_indices
      .map((i) => words[i])
      .join(' ')
      .replace(/^["'“”‘’ ]+|["'“”‘’ ]+$/g, '')
      .replace(/[,;:]+$/, '')
    if (shown && shown[0] !== shown[0].toUpperCase()) shown = shown[0].toUpperCase() + shown.slice(1)
    shown = `${shown.replace(/[.!?…]+$/, '')}.`
    if (p.quote) p.quote = { ...p.quote, text: shown }
    p.body = ''
  } else if (edit.type === 'axis' && p.chart) {
    const values = p.chart.points.map((x) => x.value)
    p.chart = { ...p.chart, y_min: edit.y_min, y_max: axisTop(values, edit.y_min) }
  } else if (edit.type === 'window') {
    const s = seriesOf(item)
    const idx = (l: string) => s.findIndex((x) => x.label === l)
    const picked = [...edit.window].sort((a, b) => idx(a) - idx(b))
    const pts = picked.map((l) => s.find((x) => x.label === l)).filter(Boolean) as { label: string; value: number }[]
    const base: ChartSpec = p.chart ?? { type: 'bar', title: '', unit: '', points: [], y_min: 0, y_max: null }
    const values = pts.map((x) => x.value)
    let yMin = base.y_min ?? 0
    if (values.length && yMin >= Math.min(...values)) yMin = 0
    p.chart = { ...base, type: 'bar', points: pts.map((x) => ({ label: formatMonth(x.label), value: x.value })), y_min: yMin, y_max: axisTop(values, yMin) }
    if (pts.length === 2) {
      const [a, b] = p.chart.points
      const pct = a.value ? (b.value / a.value - 1) * 100 : 0
      p.body = `${a.label}: ${g(a.value)} → ${b.label}: ${g(b.value)} ${base.unit ?? ''} (${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%).`
    }
  } else if (edit.type === 'drop') {
    const d = item.editable.stat?.droppable.find((x) => x.id === edit.drop)
    if (d) p.body = d.shown_without
  }
  p.author = { ...author }
  p.source_label = null
  return p
}

// ---- the boss board (level picker + "Con Busters" scoreboard) -----------------------------------
function recordFor(level: ConLevel, board: Board | null, rounds: Round[]): LevelRecord {
  const s = board?.[String(level) as '1' | '2' | '3']
  if (s) return s
  const mine = rounds.filter((r) => r.level === level)
  return { fooled: mine.filter((r) => isWin(r.outcome)).length, played: mine.length }
}

function BossBoard({
  level,
  onLevel,
  board,
  rounds,
  compact = false,
}: {
  level: ConLevel
  onLevel: (l: ConLevel) => void
  board: Board | null
  rounds: Round[]
  compact?: boolean
}) {
  const masterBeaten = rounds.some((r) => r.level === 3 && isWin(r.outcome))
  const sessionWins = rounds.filter((r) => isWin(r.outcome)).length
  if (compact) {
    return (
      <div role="radiogroup" aria-label="Which Con do you take on?" className="grid grid-cols-3 gap-1.5">
        {BOSSES.map((b) => (
          <button
            key={b.level}
            type="button"
            role="radio"
            aria-checked={level === b.level}
            onClick={() => onLevel(b.level)}
            className={`flex flex-col items-center rounded-xl border px-1.5 py-1.5 text-center transition ${
              level === b.level ? 'border-con bg-con/20' : 'border-line bg-surface hover:border-muted'
            }`}
          >
            <span className="text-sm font-semibold whitespace-nowrap">
              <span aria-hidden="true">{b.icon}</span> {b.name}
            </span>
            <span className="text-[11px] leading-tight text-muted">{b.blurb}</span>
          </button>
        ))}
      </div>
    )
  }
  return (
    <section className="overflow-hidden rounded-2xl border-2 border-con/60 bg-[#0E0F16] text-[#ECEAE4]" aria-labelledby="busters-h">
      <div className="flex items-center justify-between gap-2 border-b border-con/40 bg-con/20 px-4 py-2">
        <h2 id="busters-h" className="font-con text-base tracking-[0.2em] uppercase">
          ★ Con Busters ★
        </h2>
        <span className="text-xs text-[#B9B6C8]">
          This session: <b className="num text-white">{sessionWins}</b> fooled / <span className="num">{rounds.length}</span>
        </span>
      </div>
      <div role="radiogroup" aria-label="Pick your boss" className="flex flex-col">
        {BOSSES.map((b) => {
          const rec = recordFor(b.level, board, rounds)
          const beaten = rec.fooled > 0
          const on = level === b.level
          return (
            <button
              key={b.level}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => onLevel(b.level)}
              className={`flex items-center gap-3 border-t border-white/5 px-4 py-2.5 text-left transition first:border-t-0 ${
                on ? 'bg-con/25' : 'hover:bg-white/5'
              }`}
            >
              <span className="num w-12 shrink-0 text-[11px] font-bold tracking-widest text-[#B9B6C8] uppercase">Boss {b.level}</span>
              <span className="text-2xl" aria-hidden="true">
                {b.icon}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-display text-base leading-tight font-semibold">
                  {b.name}
                  {beaten && <span className="ml-2 rounded bg-[#2F9E6A] px-1.5 py-0.5 align-middle text-[10px] font-bold tracking-wider">BEATEN</span>}
                </span>
                <span className="block text-xs text-[#B9B6C8]">{b.blurb}</span>
              </span>
              <span className="shrink-0 text-right">
                <span className="num block text-lg leading-none font-bold">
                  {rec.fooled}
                  <span className="text-sm text-[#B9B6C8]">/{rec.played}</span>
                </span>
                <span className="text-[10px] tracking-wider text-[#B9B6C8] uppercase">fooled</span>
              </span>
              <span
                className={`ml-1 h-4 w-4 shrink-0 rounded-full border-2 ${on ? 'border-[#C9B8FF] bg-[#8B5CF6]' : 'border-[#5A5870]'}`}
                aria-hidden="true"
              />
            </button>
          )
        })}
      </div>
      {masterBeaten && (
        <p className="pop border-t border-[#E3A42B]/50 bg-[#E3A42B]/15 px-4 py-2 text-center text-sm font-bold text-[#F5C563]">
          🏅 Fooled the Master Con
        </p>
      )}
    </section>
  )
}

// ---- editor tools -----------------------------------------------------------------------------
function CropTool({ words, removed, onChange }: { words: string[]; removed: number[]; onChange: (r: number[]) => void }) {
  const kept = words.length - removed.length
  return (
    <div>
      <p className="mb-2 text-sm text-muted" aria-live="polite">
        Keeping <b className="num text-text">{kept}</b> of <span className="num">{words.length}</span> words · minimum {MIN_KEEP}
      </p>
      <div className="flex flex-wrap gap-1.5 rounded-xl bg-white p-3 text-[15px] text-[#1B1B1F] feed-font">
        {words.map((w, i) => {
          const isOut = removed.includes(i)
          const locked = !isOut && kept <= MIN_KEEP
          return (
            <button
              key={i}
              type="button"
              aria-pressed={isOut}
              aria-label={`${w}${isOut ? ' (cut)' : ''}`}
              disabled={locked}
              title={locked ? `Keep at least ${MIN_KEEP} words` : isOut ? 'Tap to restore' : 'Tap to cut'}
              onClick={() => onChange(isOut ? removed.filter((x) => x !== i) : [...removed, i])}
              className={`min-h-[34px] rounded-md px-1.5 py-0.5 transition ${
                isOut ? 'bg-[#FDE2DF] text-[#B8322A] line-through decoration-2 opacity-70' : 'hover:bg-[#EEF2F6]'
              } disabled:cursor-not-allowed`}
            >
              {w}
            </button>
          )
        })}
      </div>
      {removed.length > 0 && (
        <button type="button" className="mt-2 text-xs font-semibold text-muted hover:text-text" onClick={() => onChange([])}>
          ↺ Restore all words
        </button>
      )}
    </div>
  )
}

function AxisTool({ item, yMin, onChange }: { item: FoolDeckItem; yMin: number; onChange: (v: number) => void }) {
  const { max, step, lowest } = axisRange(item)
  const spec = item.post.chart
  const values = displayedValues(item)
  const v = Math.min(yMin, max)
  const top = axisTop(values, v) ?? (spec ? chartDomain(spec)[1] : 1)
  const honestTop = spec ? chartDomain({ ...spec, y_min: 0 })[1] : top
  // How much taller the same differences look on the truncated axis.
  const factor = v > 0 ? honestTop / Math.max(1e-9, top - v) : 1
  const digits = step < 0.1 ? 2 : step < 1 ? 1 : 0
  return (
    <div className="flex flex-col gap-3">
      <label className="flex flex-col gap-1.5 text-sm">
        <span className="flex flex-wrap items-baseline justify-between gap-2">
          <span>
            Y-axis starts at <b className="num text-lg">{formatNumber(v, Number.isInteger(v) ? 0 : digits)}</b>
            {spec?.unit && <span className="text-muted"> {spec.unit}</span>}
          </span>
          <span
            className="num rounded-full px-2.5 py-0.5 text-sm font-bold"
            style={{
              background: factor >= 1.5 ? 'color-mix(in srgb, var(--doctored) 20%, transparent)' : 'var(--surface-2)',
              color: factor >= 1.5 ? 'var(--doctored)' : 'var(--muted)',
            }}
            aria-live="polite"
          >
            {factor >= 1.05 ? `Looks ${formatNumber(factor, factor < 10 ? 1 : 0)}× steeper` : 'Honest scale'}
          </span>
        </span>
        <input
          type="range"
          min={0}
          max={max}
          step={step}
          value={v}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full accent-[var(--con)]"
          aria-valuetext={`${formatNumber(v, digits)}${spec?.unit ? ` ${spec.unit}` : ''}`}
        />
        <span className="flex justify-between text-[11px] text-muted">
          <span className="num">0 (honest)</span>
          <span className="num">{formatNumber(max, Number.isInteger(max) ? 0 : digits)} (max)</span>
        </span>
      </label>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={() => onChange(0)} disabled={v === 0}>
          Honest (0)
        </Button>
        <Button size="sm" variant="con" onClick={() => onChange(max)} disabled={v === max}>
          📈 Max drama
        </Button>
      </div>
      <p className="text-xs text-muted">
        The axis can start anywhere below the lowest value shown (<span className="num">{formatNumber(lowest)}</span>). Watch the preview
        steepen.
      </p>
    </div>
  )
}

function WindowTool({ item, value, onChange }: { item: FoolDeckItem; value: [string, string]; onChange: (v: [string, string]) => void }) {
  const s = seriesOf(item)
  const a = s.find((p) => p.label === value[0])
  const b = s.find((p) => p.label === value[1])
  const c = a && b ? change({ type: 'bar', points: [a, b] }) : null
  const select = (i: 0 | 1) => (
    <label className="flex min-w-0 flex-1 flex-col gap-1 text-sm">
      <span className="text-muted">{i === 0 ? 'From' : 'To'}</span>
      <select
        value={value[i]}
        onChange={(e) => onChange(i === 0 ? [e.target.value, value[1]] : [value[0], e.target.value])}
        className="num rounded-xl border border-line bg-bg px-3 py-2 text-sm text-text"
      >
        {s.map((p) => (
          <option key={p.label} value={p.label}>
            {formatMonth(p.label)} · {formatNumber(p.value)}
          </option>
        ))}
      </select>
    </label>
  )
  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-3">
        {select(0)}
        {select(1)}
      </div>
      {c && (
        <p className="text-sm">
          The post will compare {value[0] === value[1] ? 'a month with itself' : `${formatMonth(value[0])} with ${formatMonth(value[1])}`}:{' '}
          <b className="num">{c.text}</b>
        </p>
      )}
    </div>
  )
}

function DropTool({ item, drop, onChange }: { item: FoolDeckItem; drop: string | null; onChange: (d: string | null) => void }) {
  const stat = item.editable.stat
  if (!stat) return <p className="text-sm text-muted">This post has no droppable context.</p>
  return (
    <div className="flex flex-col gap-2">
      <p className="rounded-xl bg-white p-3 text-[15px] leading-relaxed text-[#1B1B1F] feed-font">{stat.full}</p>
      {stat.droppable.map((d) => (
        <button
          key={d.id}
          type="button"
          aria-pressed={drop === d.id}
          onClick={() => onChange(drop === d.id ? null : d.id)}
          className={`rounded-xl border px-3 py-2.5 text-left text-sm transition ${
            drop === d.id ? 'border-doctored bg-doctored/15' : 'border-line hover:border-muted'
          }`}
        >
          <span className="font-semibold">{drop === d.id ? '🙈 Hidden: ' : '👁 Showing: '}</span>
          <span className={drop === d.id ? 'line-through opacity-70' : ''}>{d.text}</span>
        </button>
      ))}
    </div>
  )
}

// ---- the inspection scene (live calls only) ----------------------------------------------------
function Inspecting({ post, level, since }: { post: Post; level: ConLevel; since: number }) {
  const boss = bossOf(level)
  const [t, setT] = useState(0)
  useEffect(() => {
    const start = since || performance.now()
    const id = window.setInterval(() => setT((performance.now() - start) / 1000), 100)
    return () => window.clearInterval(id)
  }, [])
  // Honest progress: level 1 makes one call (verdict); levels 2-3 make two (choose one tool, then rule).
  const step = !boss.checks
    ? t < 1.2
      ? 'The Con picks up the post…'
      : 'No evidence at this level. Judging by vibes…'
    : t < 1.2
      ? 'The Con picks up the post…'
      : t < 5
        ? 'Choosing ONE piece of evidence to open…'
        : 'Reading it, then ruling…'
  return (
    <div className="flex flex-col items-center gap-5 py-6 text-center" role="status" aria-live="polite">
      <div className="relative">
        <ConMascot size={150} shape="door" />
        <span className="magnify absolute top-10 -left-2 text-5xl" aria-hidden="true">
          🔍
        </span>
      </div>
      <p key={step} className="ack-in font-con text-xl tracking-wide">
        {step}
      </p>
      <p className="text-sm text-muted">
        {boss.icon} {boss.name} · live AI · <span className="num">{t.toFixed(1)} s</span>
      </p>
      <div className="flex flex-wrap justify-center gap-2" aria-hidden="true">
        {TOOLS.map((tool) => (
          <span
            key={tool.id}
            className={`rounded-full border border-line px-3 py-1 text-xs text-muted ${boss.checks ? 'pulse-dot' : 'line-through opacity-40'}`}
          >
            {tool.icon} {tool.label}
          </span>
        ))}
      </div>
      <div className="w-full max-w-md text-left opacity-90">
        <FeedCard post={post} caseNumber={0} compact watermarkText={WATERMARK} />
      </div>
    </div>
  )
}

interface Judged {
  res: FoolJudgeResponse
  level: ConLevel
  elapsed: number
}

function Verdict({
  judged,
  onAgain,
  onDeck,
  onLevelUp,
}: {
  judged: Judged
  onAgain: () => void
  onDeck: () => void
  onLevelUp: (l: ConLevel) => void
}) {
  const { res, elapsed } = judged
  const level = (res.level ?? judged.level) as ConLevel
  const boss = bossOf(level)
  const reduced = useReducedMotion()
  const cached = !!res.con.cached
  const lines = res.con.reasoning?.length ? res.con.reasoning : ['…']
  const n = lines.length
  // stage: 1..n = reasoning lines, n+1 = verdict stamp, n+2 = outcome. A cached replay renders at once (no fake delays).
  const [stage, setStage] = useState(reduced || cached ? n + 2 : 1)
  const done = stage >= n + 2
  const o = OUTCOME[res.outcome] ?? OUTCOME.con_trusted
  const checked = res.con.checked?.[0]
  const resultRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (stage === n + 1) {
      play('thunk')
      const id = window.setTimeout(() => setStage(n + 2), 600)
      return () => window.clearTimeout(id)
    }
  }, [stage, n])

  useEffect(() => {
    if (!done) return
    if (o.win === true) play('ding')
    else if (o.win === false) play('bwomp')
    resultRef.current?.focus({ preventScroll: false })
  }, [done, o.win])

  const conf = res.con.confidence != null ? Math.round(res.con.confidence * 100) : null
  const next = BOSSES.find((b) => b.level === level + 1)

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted">
          {boss.icon} {boss.name} {boss.checks ? 'opened ONE tool:' : 'opened no evidence:'}
        </span>
        {TOOLS.map((t) => (
          <span
            key={t.id}
            className={`rounded-full border px-3 py-1 text-sm font-semibold transition ${
              t.id === checked ? 'pop border-con bg-con text-on-accent' : 'border-line text-muted opacity-60'
            } ${!boss.checks ? 'line-through' : ''}`}
          >
            {t.icon} {t.label}
          </span>
        ))}
        {!res.con.checked?.length && <span className="text-sm text-muted">it judged on sight</span>}
        {!done && (
          <button type="button" className="ml-auto text-xs font-semibold text-muted hover:text-text" onClick={() => setStage(n + 2)}>
            Skip ⏭
          </button>
        )}
      </div>

      <div className="flex items-start gap-3">
        <ConMascot size={72} className="shrink-0" />
        <div className="flex min-w-0 flex-1 flex-col gap-2" aria-live="polite">
          {lines.slice(0, Math.max(0, Math.min(stage, n))).map((line, i) => (
            <ConBubble
              key={i}
              text={line}
              size="sm"
              speed={16}
              typewriter={!cached && i === stage - 1 && stage <= n}
              onDone={!cached && i === stage - 1 && stage <= n ? () => window.setTimeout(() => setStage((s) => (s === i + 1 ? s + 1 : s)), 350) : undefined}
            />
          ))}
        </div>
      </div>

      {stage >= n + 1 && (
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm text-muted">Verdict:</span>
          <span
            className="stamp stamp-thunk text-2xl"
            style={{
              color: res.con.verdict === 'doctored' ? 'var(--doctored)' : 'var(--real)',
              ['--stamp-rot' as string]: '-5deg',
            }}
          >
            {res.con.verdict === 'doctored' ? 'Doctored' : 'Real'}
          </span>
          {res.con.trick_guess && res.con.verdict === 'doctored' && <span className="text-sm">guess: {trickLabel(res.con.trick_guess)}</span>}
          {conf != null && <span className="num text-sm text-muted">{conf}% sure</span>}
        </div>
      )}

      {done && (
        <div ref={resultRef} tabIndex={-1} className="rise-in flex flex-col gap-4 focus-visible:outline-none">
          <section
            className="rounded-2xl border-2 p-5 text-center"
            style={{ borderColor: o.color, background: `color-mix(in srgb, ${o.color} 14%, transparent)` }}
            aria-label="Outcome"
          >
            <p className="font-display text-3xl font-bold tracking-wide sm:text-4xl" style={{ color: o.color }}>
              <span aria-hidden="true">{o.icon} </span>
              {o.title}
            </p>
            <p className="mt-1 text-sm text-muted">{o.sub}</p>
            {level === 3 && o.win === true && <p className="pop mt-3 text-base font-bold text-alarm">🏅 You fooled the Master Con</p>}
          </section>

          {o.win === true && next && (
            <div className="pop flex flex-wrap items-center gap-3 rounded-2xl border-2 border-con bg-con/15 px-4 py-3">
              <span className="text-3xl" aria-hidden="true">
                {next.icon}
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-display text-lg font-semibold">
                  {boss.name} beaten. Next boss: {next.name}
                </p>
                <p className="text-sm text-muted">{next.blurb}</p>
              </div>
              <Button variant="primary" onClick={() => onLevelUp(next.level)}>
                Take on the {next.name} →
              </Button>
            </div>
          )}

          {res.con_line && (
            <div className="flex items-end gap-2.5">
              <ConMascot size={44} className="shrink-0" />
              <ConBubble text={res.con_line} size="md" className="min-w-0 flex-1" typewriter={!cached} />
            </div>
          )}
          {res.diff ? (
            <DiffView post={res.edited_post} caseNumber={0} diff={res.diff} shownLabel="What the Con saw" watermarkText={WATERMARK} />
          ) : (
            <p className="rounded-xl border border-line bg-surface p-4 text-sm">
              {res.changed ? 'Your edit changed the post.' : 'You left it untouched: the post was real, word for word.'}
              {res.trick && <> Trick: {trickLabel(res.trick)}.</>}
            </p>
          )}
          <p className="text-xs text-muted">
            {cached ? (
              <>⚡ Replay of a real verdict</>
            ) : (
              <>
                Judged live by the blind solver · <span className="num">{elapsed.toFixed(1)} s</span>
              </>
            )}{' '}
            · {boss.name}. The same blind solver checks every Daily is fair.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" onClick={onDeck}>
              Doctor another post →
            </Button>
            <Button onClick={onAgain}>Try this post again</Button>
          </div>
        </div>
      )}
    </div>
  )
}

/** Saved rounds: replays of real cached verdicts, always free (CONTRACT §8.5). */
function SavedRounds({ deck, onPlay, busy }: { deck: FoolDeckItem[]; onPlay: (r: SavedRound) => void; busy: boolean }) {
  const byId = new Map(deck.map((d) => [d.id, d]))
  const seen = new Set<string>()
  const list = [...loadSaved(), ...DEMO_ROUNDS].filter((r) => {
    const k = JSON.stringify(r)
    if (seen.has(k) || !byId.has(r.deck_id)) return false
    seen.add(k)
    return true
  })
  if (!list.length) return null
  return (
    <ul className="mt-4 flex flex-col gap-2 text-left">
      {list.slice(0, 8).map((r, i) => {
        const it = byId.get(r.deck_id)!
        const title = it.post.chart?.title || it.post.quote?.speaker || it.post.author.name
        return (
          <li key={i}>
            <button
              type="button"
              disabled={busy}
              onClick={() => onPlay(r)}
              className="flex w-full items-center gap-3 rounded-xl border border-line bg-surface-2 px-3 py-2.5 text-left text-sm transition hover:border-con disabled:opacity-50"
            >
              <span aria-hidden="true">⚡</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold">{title}</span>
                <span className="block truncate text-xs text-muted">
                  {editLabel(it, r.edit)} · {bossOf(r.level).name}
                </span>
              </span>
              <span className="text-xs font-semibold text-con">Replay →</span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}

// ---- screen -----------------------------------------------------------------------------------
function normalizeDeck(res: FoolDeckItem[] | { items: FoolDeckItem[] }): FoolDeckItem[] {
  const list = Array.isArray(res) ? res : res?.items ?? []
  return list.filter((x) => x && x.id && x.post)
}

type Phase = 'pick' | 'edit' | 'judging' | 'result' | 'asleep' | 'resting'

export function ConTheCon() {
  const deck = useAsync(() => api.foolDeck().then(normalizeDeck), [])
  const [item, setItem] = useState<FoolDeckItem | null>(null)
  const [st, setSt] = useState<EditorState | null>(null)
  const [phase, setPhase] = useState<Phase>('pick')
  const [ack, setAck] = useState(false)
  const [judged, setJudged] = useState<Judged | null>(null)
  const [editErr, setEditErr] = useState<string | null>(null)
  const [err, setErr] = useState<unknown>(null)
  const [restMsg, setRestMsg] = useState<string | null>(null)
  const [savedMiss, setSavedMiss] = useState(false)
  const replaying = useRef(false)
  const judgeStart = useRef(0)
  const [rounds, setRounds] = useState<Round[]>(loadRounds)
  const [board, setBoard] = useState<Board | null>(() => loadJSON<Board>(BOARD_KEY))
  const [level, setLevelState] = useState<ConLevel>(loadLevel)
  const [authors, setAuthors] = useState<Record<string, Author>>({})
  const [barRef, barH] = useElementHeight<HTMLDivElement>()
  const top = useRef<HTMLDivElement>(null)

  const setLevel = (l: ConLevel) => {
    setLevelState(l)
    saveJSON(LEVEL_KEY, l)
  }

  const edit = useMemo(() => (item && st ? buildEdit(item, st) : null), [item, st])
  const author = item ? item.edited_author ?? authors[item.id] ?? UNNAMED_ACCOUNT : UNNAMED_ACCOUNT
  const preview = useMemo(() => (item && edit ? previewPost(item, edit, author) : null), [item, edit, author])

  const scrollTop = () => window.setTimeout(() => top.current?.scrollIntoView({ block: 'start', behavior: 'smooth' }), 0)

  const choose = (it: FoolDeckItem) => {
    setItem(it)
    setSt(initialState(it))
    setEditErr(null)
    setErr(null)
    setPhase('edit')
    play('flip')
    scrollTop()
  }

  const judge = async (it: FoolDeckItem, e: FoolEdit, lvl: ConLevel) => {
    setPhase('judging')
    setAck(false)
    setEditErr(null)
    setErr(null)
    // Acknowledge within 150ms if the answer isn't back (a cached replay usually is, and renders at once).
    const ackId = window.setTimeout(() => {
      setAck(true)
      scrollTop()
    }, 150)
    const t0 = performance.now()
    judgeStart.current = t0
    try {
      const r = await withPlayer((pid) => api.foolJudge(pid, it.id, e, lvl))
      const elapsed = (performance.now() - t0) / 1000
      window.clearTimeout(ackId)
      setJudged({ res: r, level: lvl, elapsed })
      if (r.changed && r.edited_post?.author) setAuthors((a) => ({ ...a, [it.id]: r.edited_post.author }))
      if (r.scoreboard?.by_level) {
        setBoard(r.scoreboard.by_level)
        saveJSON(BOARD_KEY, r.scoreboard.by_level)
      }
      const roundLevel = (r.level ?? lvl) as ConLevel
      const next = [...rounds, { deck_id: it.id, outcome: r.outcome, level: roundLevel, con_line: r.con_line }]
      setRounds(next)
      saveRounds(next)
      rememberSaved({ deck_id: it.id, edit: e, level: roundLevel })
      setPhase('result')
      scrollTop()
    } catch (ex) {
      window.clearTimeout(ackId)
      if (ex instanceof ApiError && (ex.status === 429 || errorCode(ex) === 'con_resting')) {
        setRestMsg(ex.message && ex.message !== `Request failed (429).` ? ex.message : null)
        setSavedMiss(replaying.current)
        setPhase('resting')
      } else if (ex instanceof ApiError && (ex.status === 503 || errorCode(ex) === 'con_asleep')) setPhase('asleep')
      else if (ex instanceof ApiError && ex.status === 422) {
        setEditErr(ex.message || 'That edit isn’t allowed.')
        setPhase('edit')
      } else {
        setErr(ex)
        setPhase('edit')
      }
    }
  }

  const submit = () => {
    replaying.current = false
    if (item && edit) void judge(item, edit, level)
  }

  const playSaved = (r: SavedRound) => {
    const it = deck.status === 'ok' ? deck.data.find((d) => d.id === r.deck_id) : undefined
    if (!it) return
    replaying.current = true
    setItem(it)
    setSt(stateFromEdit(it, r.edit))
    setLevel(r.level)
    void judge(it, r.edit, r.level)
  }

  const bestLines = rounds.filter((r) => r.con_line).slice(-3).reverse()
  const editing = phase === 'edit' || (phase === 'judging' && !ack)
  const boss = bossOf(level)
  const deckList = deck.status === 'ok' ? deck.data : []

  return (
    <>
      <SiteHeader active="con" />
      <main
        className="mx-auto w-full max-w-6xl flex-1 px-4 py-6"
        ref={top}
        style={editing ? { paddingBottom: Math.max(barH, 0) + 24 } : undefined}
      >
        <div className="mb-5 grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,400px)] md:items-start">
          <div>
            <p className="text-xs font-bold tracking-[0.18em] text-con uppercase">Bonus round · challenge mode</p>
            <h1 className="font-display text-3xl font-bold sm:text-4xl">Con the Con 🎭</h1>
            <p className="mt-1 max-w-xl text-sm text-muted">
              Your turn to be the con artist. Doctor a real post with one trick, then send it to a boss. Each boss is our blind-solver AI
              with more to work with. Fool it and you climb the board.
            </p>
          </div>
          {phase === 'pick' && <BossBoard level={level} onLevel={setLevel} board={board} rounds={rounds} />}
        </div>

        {phase === 'pick' && (
          <>
            {deck.status === 'loading' && <Loading label="Shuffling the Fool Deck…" />}
            {deck.status === 'error' && <ErrorState error={deck.error} onRetry={deck.reload} title="Couldn’t load the Fool Deck." />}
            {deck.status === 'ok' &&
              (deck.data.length === 0 ? (
                <p className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted">The Fool Deck is empty right now.</p>
              ) : (
                <>
                  <SectionLabel className="mb-3">
                    Pick a real post to doctor · facing {boss.icon} {boss.name}
                  </SectionLabel>
                  <ul className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {deck.data.map((it) => (
                      <li key={it.id}>
                        <button
                          type="button"
                          onClick={() => choose(it)}
                          className="group flex h-full w-full flex-col gap-3 rounded-2xl border-2 border-line bg-surface p-3 text-left transition hover:-translate-y-0.5 hover:border-con"
                        >
                          <FeedCard post={it.post} caseNumber={0} compact watermarkText={WATERMARK} />
                          <span className="flex flex-wrap items-center gap-1.5 px-1 pb-1">
                            <span className="text-xs font-bold tracking-[0.14em] text-muted uppercase">{it.kind}</span>
                            {it.tools.map((t) => (
                              <span key={t} className="rounded-full border border-line px-2 py-0.5 text-xs">
                                {TOOL_META[t]?.icon} {TOOL_META[t]?.label ?? t}
                              </span>
                            ))}
                            <span className="ml-auto text-sm font-semibold text-con group-hover:underline">Doctor it →</span>
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              ))}
            {bestLines.length > 0 && (
              <section className="mt-8">
                <SectionLabel className="mb-2">The Con’s best lines this session</SectionLabel>
                <ul className="flex flex-col gap-2">
                  {bestLines.map((r, i) => (
                    <li key={i} className="con-bubble rounded-l-sm rounded-r-xl px-4 py-2 text-sm">
                      “{r.con_line}”
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </>
        )}

        {editing && item && st && edit && preview && (
          <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <section aria-label="Live preview" className="min-w-0">
              <div className="md:sticky md:top-[72px]">
                <SectionLabel className="mb-2">{edit.type === 'none' ? 'The real post' : 'Your doctored post (live preview)'}</SectionLabel>
                <FeedCard post={preview} caseNumber={0} watermarkText={WATERMARK} renderChart={(spec) => <PostChart spec={spec} height={230} />} />
                <p className="mt-2 text-xs text-muted">
                  {edit.type === 'none' ? (
                    <>Untouched, it stays under the real outlet’s name.</>
                  ) : (
                    <>
                      Doctored posts go out as <b className="text-text">{author.name}</b> <span className="num">{author.handle}</span>, a made-up
                      account. We never put edited words under a real outlet’s name.
                    </>
                  )}
                </p>
              </div>
            </section>

            <section aria-label="Your tools" className="min-w-0">
              <div className="mb-3 flex items-center justify-between">
                <SectionLabel>Pick one trick</SectionLabel>
                <button type="button" className="text-sm font-semibold text-muted hover:text-text" onClick={() => setPhase('pick')}>
                  ← Back to the deck
                </button>
              </div>
              <div role="tablist" aria-label="Editing tools" className="flex flex-wrap gap-2">
                {([...item.tools, 'none'] as Tool[]).map((t) => (
                  <button
                    key={t}
                    type="button"
                    role="tab"
                    aria-selected={st.tool === t}
                    onClick={() => setSt({ ...st, tool: t })}
                    className={`rounded-xl border px-3.5 py-2 text-sm font-semibold transition ${
                      st.tool === t ? 'border-con bg-con text-on-accent' : 'border-line bg-surface hover:border-muted'
                    }`}
                  >
                    {TOOL_META[t].icon} {TOOL_META[t].label}
                    {t === 'none' && <span className="font-normal opacity-80"> (bluff)</span>}
                  </button>
                ))}
              </div>
              <div role="tabpanel" className="mt-4 rounded-2xl border border-line bg-surface p-4">
                <p className="mb-3 text-sm text-muted">{TOOL_META[st.tool].hint}</p>
                {st.tool === 'crop' && (
                  <CropTool words={item.editable.quote_words ?? []} removed={st.removed} onChange={(removed) => setSt({ ...st, removed })} />
                )}
                {st.tool === 'axis' && <AxisTool item={item} yMin={st.yMin} onChange={(yMin) => setSt({ ...st, yMin })} />}
                {st.tool === 'window' && <WindowTool item={item} value={st.window} onChange={(window) => setSt({ ...st, window })} />}
                {st.tool === 'drop' && <DropTool item={item} drop={st.drop} onChange={(drop) => setSt({ ...st, drop })} />}
                {st.tool === 'none' && (
                  <p className="text-[15px]">
                    Send the real post, untouched. If the Con calls it doctored, it doubted the truth and you win. That’s the over-doubt we
                    score against.
                  </p>
                )}
                {st.tool !== 'none' && edit.type === 'none' && <p className="mt-3 text-xs text-alarm">No change yet, so this would go in as a bluff.</p>}
              </div>
              {editErr && (
                <p role="alert" className="mt-3 rounded-xl border border-doctored/50 bg-doctored/10 px-3 py-2 text-sm">
                  {editErr}
                </p>
              )}
              {err != null && <ErrorState error={err} className="mt-3" title="Couldn’t reach the Con." />}
              <div className="mt-4 hidden md:block">
                <SectionLabel className="mb-2">Your opponent</SectionLabel>
                <BossBoard level={level} onLevel={setLevel} board={board} rounds={rounds} compact />
              </div>
              {/* Mobile: a fixed bar (content pads itself by its measured height). Desktop: inline. */}
              <div
                ref={barRef}
                className="fixed inset-x-0 bottom-0 z-20 flex flex-col gap-2 border-t border-line bg-bg/95 px-4 pt-2.5 pb-[max(10px,env(safe-area-inset-bottom))] backdrop-blur md:static md:mt-4 md:border-0 md:bg-transparent md:p-0"
              >
                <div className="md:hidden">
                  <BossBoard level={level} onLevel={setLevel} board={board} rounds={rounds} compact />
                </div>
                <button
                  type="button"
                  onClick={submit}
                  disabled={phase === 'judging'}
                  className="flex w-full items-center justify-center gap-2 rounded-2xl bg-con py-3.5 font-display text-lg font-semibold text-on-accent shadow-[0_10px_30px_-12px_var(--con)] transition hover:brightness-110 active:scale-[0.98] disabled:opacity-70 sm:text-xl"
                >
                  {phase === 'judging'
                    ? 'Sending…'
                    : edit.type === 'none'
                      ? `🙈 Bluff the ${boss.name}`
                      : `Send it to the ${boss.name}`}{' '}
                  <span aria-hidden="true">→</span>
                </button>
              </div>
            </section>
          </div>
        )}

        {phase === 'judging' && ack && preview && <Inspecting post={preview} level={level} since={judgeStart.current} />}

        {phase === 'result' && judged && (
          <div className="mx-auto max-w-4xl">
            <Verdict
              key={`${judged.res.outcome}-${rounds.length}`}
              judged={judged}
              onAgain={() => {
                setJudged(null)
                setPhase('edit')
                scrollTop()
              }}
              onDeck={() => {
                setJudged(null)
                setItem(null)
                setPhase('pick')
                scrollTop()
              }}
              onLevelUp={(l) => {
                setLevel(l)
                setJudged(null)
                setPhase('edit')
                scrollTop()
              }}
            />
          </div>
        )}

        {(phase === 'asleep' || phase === 'resting') && (
          <div role="alert" className="mx-auto max-w-md rounded-2xl border border-line bg-surface p-6 text-center">
            <ConMascot size={120} className="mx-auto opacity-70" />
            {phase === 'resting' ? (
              <>
                <p className="mt-3 font-display text-2xl font-semibold">The Con is resting. 😴</p>
                <p className="mt-2 text-sm text-muted">
                  {restMsg ?? 'Live rounds are capped so everyone gets a turn.'} Saved rounds replay real verdicts and are always free.
                </p>
                {savedMiss && (
                  <p className="mt-2 text-sm text-alarm">That replay isn’t saved on this server any more. Try another one.</p>
                )}
              </>
            ) : (
              <>
                <p className="mt-3 font-display text-2xl font-semibold">The Con is asleep. 💤</p>
                <p className="mt-2 text-sm text-muted">
                  No AI available right now, and there’s no earlier verdict saved for this exact edit. We won’t invent one.
                </p>
              </>
            )}
            <SavedRounds deck={deckList} onPlay={playSaved} busy={false} />
            <div className="mt-4 flex justify-center gap-2">
              {phase === 'asleep' && (
                <Button variant="primary" onClick={submit}>
                  Try again
                </Button>
              )}
              <Button onClick={() => setPhase(item ? 'edit' : 'pick')}>{item ? 'Change the edit' : 'Back to the deck'}</Button>
            </div>
          </div>
        )}
      </main>
    </>
  )
}
