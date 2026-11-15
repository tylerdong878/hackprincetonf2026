import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import halftone from '../assets/figma/halftone.svg'
import { ConMascot } from '../components/Art'
import { ConBubble } from '../components/ConBubble'
import { TOOLS } from '../components/EvidenceKit'
import {
  IconArrow,
  IconArrowLeft,
  IconAxis,
  IconCalendar,
  IconCheck,
  IconEye,
  IconEyeOff,
  IconGlasses,
  IconHash,
  IconLens,
  IconMask,
  IconPen,
  IconReplay,
  IconScissors,
  IconSkip,
  IconTrophy,
  IconX,
  IconZap,
  IconZzz,
} from '../components/Icon'
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

const TOOL_META: Record<Tool, { icon: ReactNode; label: string; hint: string }> = {
  crop: { icon: <IconScissors size={18} />, label: 'Crop', hint: 'Tap words to cut them. Deletion only: you can’t add words.' },
  axis: { icon: <IconAxis size={18} />, label: 'Axis', hint: 'Slide where the y-axis starts. Same numbers, steeper story.' },
  window: { icon: <IconCalendar size={18} />, label: 'Window', hint: 'Pick which two months to compare.' },
  drop: { icon: <IconHash size={18} />, label: 'Drop context', hint: 'Hide the number that puts the claim in context.' },
  none: { icon: <IconEyeOff size={18} />, label: 'Leave it real', hint: 'The bluff: send it untouched and see if the Con doubts the truth.' },
}

// ---- the three bosses (CONTRACT §8.1) ----------------------------------------------------------
interface Boss {
  level: ConLevel
  name: string
  blurb: string
  checks: boolean
}
const BOSSES: Boss[] = [
  { level: 1, name: 'Rookie Con', blurb: 'judges by vibes, no evidence', checks: false },
  { level: 2, name: 'Street Con', blurb: 'one check, fast brain', checks: true },
  { level: 3, name: 'Master Con', blurb: 'one check, full brain', checks: true },
]

/** Each boss's mark: the Rookie wears the mask, the Street Con shades, the Master Con is the noir silhouette. */
function BossIcon({ level, size = 20, className = '' }: { level: ConLevel; size?: number; className?: string }) {
  if (level === 1) return <IconMask size={size} className={className} />
  if (level === 2) return <IconGlasses size={size} className={className} />
  return <ConMascot size={size + 2} className={className} />
}
const bossOf = (l: number | null | undefined) => BOSSES.find((b) => b.level === l) ?? BOSSES[2]

/** CONTRACT §8.2 wording. `win` = the Con got it wrong. */
const OUTCOME: Record<FoolOutcome, { title: string; sub: string; color: string; win: boolean | null; icon: ReactNode }> = {
  caught: { title: 'BUSTED', sub: 'The Con caught your edit.', color: 'var(--doctored)', win: false, icon: <IconX size={34} strokeWidth={2.4} /> },
  fooled_the_con: { title: 'FOOLED THE CON', sub: 'Your edit got past the AI.', color: 'var(--press)', win: true, icon: <IconTrophy size={34} /> },
  con_false_alarm: {
    title: 'FALSE ALARM',
    sub: 'You sent the truth, untouched, and the Con called it doctored. You win.',
    color: 'var(--alarm)',
    win: true,
    icon: <IconTrophy size={34} />,
  },
  con_trusted: { title: 'TRUSTED', sub: 'A real post, called real. A draw.', color: 'var(--ink)', win: null, icon: <IconCheck size={34} strokeWidth={2.4} /> },
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
      return `Axis from ${withUnit(e.y_min, item?.post.chart?.unit)}`
    case 'window':
      return `${formatMonth(e.window[0])} vs ${formatMonth(e.window[1])}`
    case 'crop': {
      const words = item?.editable.quote_words ?? []
      const cut = words.filter((_, i) => !e.keep_word_indices.includes(i))
      return `Cut “${cut.slice(0, 4).join(' ')}${cut.length > 4 ? '…' : ''}”`
    }
    case 'drop': {
      const d = item?.editable.stat?.droppable.find((x) => x.id === e.drop)
      return `Hide ${d ? `“${d.text.slice(0, 40)}${d.text.length > 40 ? '…' : ''}”` : e.drop}`
    }
    default:
      return 'Bluff: untouched'
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
            className={`flex flex-col items-center border-2 border-ink px-1.5 py-1.5 text-center ${
              level === b.level ? 'bg-ink text-sheet' : 'bg-sheet text-ink hover:bg-surface-2'
            }`}
          >
            <span className="caps flex items-center gap-1.5 text-[13px] font-semibold whitespace-nowrap">
              <BossIcon level={b.level} size={16} /> {b.name}
            </span>
            <span className={`text-[11.5px] leading-tight ${level === b.level ? 'text-[#C9C2B5]' : 'text-muted'}`}>{b.blurb}</span>
          </button>
        ))}
      </div>
    )
  }
  return (
    <section className="panel overflow-hidden" aria-labelledby="busters-h">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b-2 border-ink px-4 py-2.5">
        <h2 id="busters-h" className="caps flex items-center gap-2 text-[15px] font-bold tracking-[0.12em] whitespace-nowrap">
          <IconMask size={22} className="text-press" />
          ★ Con Busters ★
        </h2>
        <span className="text-[13px] whitespace-nowrap text-muted">
          This session: <b className="num text-[17px] text-ink">{sessionWins}</b> fooled / <span className="num">{rounds.length}</span>
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
              className={`flex items-center gap-3 border-t border-[#CFC6B4] px-4 py-2.5 text-left first:border-t-0 ${
                on ? 'bg-ink text-sheet' : 'hover:bg-surface-2'
              }`}
            >
              <span className={`caps w-12 shrink-0 text-[11.5px] font-semibold tracking-[0.1em] ${on ? 'text-press-soft' : 'text-press'}`}>
                Boss <span className="num">{b.level}</span>
              </span>
              <span className="flex w-7 justify-center" aria-hidden="true">
                <BossIcon level={b.level} size={22} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-display text-[17px] leading-tight font-bold">
                  {b.name}
                  {beaten && (
                    <span className="caps ml-2 border-[1.5px] border-current px-1.5 py-px align-middle text-[10.5px] font-semibold tracking-[0.1em] text-press">
                      BEATEN
                    </span>
                  )}
                </span>
                <span className={`block text-[12.5px] ${on ? 'text-[#C9C2B5]' : 'text-muted'}`}>{b.blurb}</span>
              </span>
              <span className="shrink-0 text-right">
                <span className="num block text-2xl leading-none font-bold">
                  {rec.fooled}
                  <span className={`text-sm ${on ? 'text-[#C9C2B5]' : 'text-muted'}`}>/{rec.played}</span>
                </span>
                <span className={`caps text-[10.5px] tracking-[0.1em] ${on ? 'text-[#C9C2B5]' : 'text-muted'}`}>fooled</span>
              </span>
              <span
                className={`ml-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2 ${on ? 'border-sheet' : 'border-ink'}`}
                aria-hidden="true"
              >
                {on && <span className="h-1.5 w-1.5 rounded-full bg-press-soft" />}
              </span>
            </button>
          )
        })}
      </div>
      {masterBeaten && (
        <p className="pop caps flex items-center justify-center gap-2 border-t-2 border-ink bg-ochre px-4 py-2 text-center text-[14px] font-semibold tracking-[0.06em] text-ink">
          <IconTrophy size={17} /> Fooled the Master Con
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
      <p className="mb-3 text-sm text-muted" aria-live="polite">
        Keeping <b className="num text-text">{kept}</b> of <span className="num">{words.length}</span> words · minimum {MIN_KEEP}
      </p>
      <div className="feed-font flex flex-wrap gap-1.5 text-[15px] text-[#1B1B1F]">
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
              className={`min-h-[34px] border px-2 py-0.5 transition ${
                isOut
                  ? 'border-press bg-[#F6D5D1] text-press line-through decoration-[1.5px]'
                  : 'border-[#CFC6B4] bg-white hover:border-ink'
              } disabled:cursor-not-allowed`}
            >
              {w}
            </button>
          )
        })}
      </div>
      {removed.length > 0 && (
        <button type="button" className="mt-3 inline-flex items-center gap-1.5 text-[14px] font-bold text-ink hover:underline" onClick={() => onChange([])}>
          <IconReplay size={16} /> Restore all words
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
            className="caps border-[1.5px] px-2 py-0.5 text-[13px] font-semibold"
            style={{
              background: factor >= 1.5 ? 'var(--press)' : 'var(--sheet)',
              borderColor: factor >= 1.5 ? 'var(--press)' : 'var(--ink)',
              color: factor >= 1.5 ? '#FFFFFF' : 'var(--muted)',
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
          className="w-full accent-[var(--press)]"
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
          <IconAxis size={16} /> Max drama
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
        className="num border-2 border-ink bg-white px-3 py-2 text-sm text-text"
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
      <p className="feed-font rounded-[10px] border border-[#CFD4DA] bg-white p-3 text-[15px] leading-relaxed text-[#1B1B1F]">{stat.full}</p>
      {stat.droppable.map((d) => (
        <button
          key={d.id}
          type="button"
          aria-pressed={drop === d.id}
          onClick={() => onChange(drop === d.id ? null : d.id)}
          className={`flex items-start gap-2 border-2 px-3 py-2.5 text-left text-sm ${
            drop === d.id ? 'border-press bg-[#F6D5D1]' : 'border-ink bg-sheet hover:bg-surface-2'
          }`}
        >
          <span className={`mt-px ${drop === d.id ? 'text-press' : 'text-ink'}`}>{drop === d.id ? <IconEyeOff size={16} /> : <IconEye size={16} />}</span>
          <span className="font-semibold">{drop === d.id ? 'Hidden: ' : 'Showing: '}</span>
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
      {/* the Con as a newspaper photo, a red lens sweeping the post */}
      <div className="panel relative w-full max-w-[420px] p-2.5">
        <div className="relative overflow-hidden bg-[#E6DDCB]" style={{ aspectRatio: '476 / 470' }}>
          <img src={halftone} alt="" aria-hidden="true" draggable={false} className="absolute inset-x-0 bottom-0 h-[48%] w-full select-none" />
          <span className="absolute bottom-0 left-1/2 h-[86%] -translate-x-1/2">
            <ConMascot size={340} shape="door" className="!h-full !w-auto" />
          </span>
        </div>
        <span className="magnify absolute top-[22%] right-[14%] text-press" aria-hidden="true">
          <IconLens size={96} strokeWidth={2.2} />
        </span>
      </div>
      <p key={step} className="ack-in font-con text-3xl italic sm:text-4xl">
        {step}
      </p>
      <p className="caps flex items-center gap-1.5 text-[13px] tracking-[0.08em] text-muted">
        <BossIcon level={boss.level} size={16} /> {boss.name} · live AI · <span className="num">{t.toFixed(1)} s</span>
      </p>
      <div className="flex flex-wrap justify-center gap-3" aria-hidden="true">
        {TOOLS.map((tool, i) => (
          <span
            key={tool.id}
            className={`flex items-center gap-2.5 border-2 border-dashed border-ink bg-sheet px-3.5 py-2 text-[15px] font-bold ${boss.checks ? '' : 'line-through opacity-40'}`}
          >
            {tool.icon} {tool.label}
            {boss.checks && <span className="pulse-dot ml-1 h-2 w-2 rounded-full bg-press" style={{ animationDelay: `${i * 0.3}s` }} />}
          </span>
        ))}
      </div>
      <div className="w-full max-w-xl text-left">
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
      <div>
        <p className="caps mb-2.5 flex items-center gap-1.5 text-[13px] font-semibold tracking-[0.08em] text-ink">
          <BossIcon level={boss.level} size={16} /> {boss.name} {boss.checks ? 'opened ONE tool:' : 'opened no evidence:'}
        </p>
        <div className="flex flex-wrap items-center gap-2.5">
          {TOOLS.map((t) => (
            <span
              key={t.id}
              className={`flex min-w-[180px] items-center gap-2.5 px-3.5 py-2.5 text-[15px] font-bold ${
                t.id === checked
                  ? 'pop border-2 border-ink bg-press text-white shadow-[var(--hard)]'
                  : 'border-2 border-[#CFC6B4] text-muted'
              } ${!boss.checks ? 'line-through' : ''}`}
            >
              {t.icon} {t.label}
            </span>
          ))}
          {!res.con.checked?.length && <span className="text-sm text-muted italic">it judged on sight</span>}
          {!done && (
            <button
              type="button"
              className="caps ml-auto inline-flex items-center gap-1 text-[13px] font-semibold tracking-[0.06em] text-ink hover:underline"
              onClick={() => setStage(n + 2)}
            >
              Skip <IconSkip size={15} />
            </button>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="flex items-start gap-4">
        <ConMascot size={76} className="shrink-0" />
        <div className="flex min-w-0 flex-1 flex-col gap-3" aria-live="polite">
          {lines.slice(0, Math.max(0, Math.min(stage, n))).map((line, i) => (
            <ConBubble
              key={i}
              text={line}
              size="md"
              speed={16}
              typewriter={!cached && i === stage - 1 && stage <= n}
              onDone={!cached && i === stage - 1 && stage <= n ? () => window.setTimeout(() => setStage((s) => (s === i + 1 ? s + 1 : s)), 350) : undefined}
            />
          ))}
        </div>
      </div>

      {stage >= n + 1 && (
        <div className="flex flex-col items-start gap-3 lg:pt-2">
          <span className="caps text-[13px] font-semibold tracking-[0.08em] text-ink">Verdict:</span>
          <span
            className="stamp stamp-thunk mx-2 bg-sheet text-5xl sm:text-6xl"
            style={{
              color: res.con.verdict === 'doctored' ? 'var(--doctored)' : 'var(--ink)',
              ['--stamp-rot' as string]: '-5deg',
            }}
          >
            {res.con.verdict === 'doctored' ? 'Doctored' : 'Real'}
          </span>
          <span className="mt-1 flex flex-wrap items-baseline gap-x-3 text-[17px]">
            {res.con.trick_guess && res.con.verdict === 'doctored' && <span>guess: {trickLabel(res.con.trick_guess)}</span>}
            {conf != null && <span className="text-muted"><span className="num text-ink">{conf}%</span> sure</span>}
          </span>
        </div>
      )}
      </div>

      {done && (
        <div ref={resultRef} tabIndex={-1} className="rise-in flex flex-col gap-4 focus-visible:outline-none">
          <div className="double-rule" aria-hidden="true" />
          <section
            className="flex flex-col gap-4 border-2 border-l-[10px] border-ink bg-sheet px-6 py-5 shadow-[var(--hard)] sm:flex-row sm:items-center"
            aria-label="Outcome"
          >
            <span className="shrink-0" style={{ color: o.color }} aria-hidden="true">
              {o.icon}
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-display text-[28px] leading-tight font-bold sm:text-[38px]">{o.sub}</p>
              {level === 3 && o.win === true && (
                <p className="pop caps mt-2 inline-flex items-center gap-1.5 bg-ochre px-2 py-0.5 text-[14px] font-semibold tracking-[0.06em] text-ink">
                  <IconTrophy size={16} /> You fooled the Master Con
                </p>
              )}
            </div>
            <span
              className="stamp stamp-thunk shrink-0 self-start bg-sheet text-3xl sm:mr-4 sm:self-center sm:text-4xl"
              style={{ color: o.color, ['--stamp-rot' as string]: '-4deg' }}
            >
              {o.title}
            </span>
          </section>

          {o.win === true && next && (
            <div className="pop flex flex-wrap items-center gap-4 border-2 border-press bg-sheet px-4 py-3 shadow-[var(--hard)]">
              <span className="text-press" aria-hidden="true">
                <BossIcon level={next.level} size={30} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-display text-xl font-bold">
                  {boss.name} beaten. Next boss: {next.name}
                </p>
                <p className="text-sm text-muted">{next.blurb}</p>
              </div>
              <Button variant="primary" onClick={() => onLevelUp(next.level)}>
                Take on the {next.name} <IconArrow size={17} />
              </Button>
            </div>
          )}

          {res.con_line && (
            <div className="flex items-start gap-4 lg:pr-[324px]">
              <ConMascot size={76} className="shrink-0" />
              <ConBubble text={res.con_line} size="md" className="min-w-0 flex-1" typewriter={!cached} />
            </div>
          )}
          {res.diff ? (
            <DiffView post={res.edited_post} caseNumber={0} diff={res.diff} shownLabel="What the Con saw" watermarkText={WATERMARK} />
          ) : (
            <p className="panel p-4 text-[15px]">
              {res.changed ? 'Your edit changed the post.' : 'You left it untouched: the post was real, word for word.'}
              {res.trick && <> Trick: {trickLabel(res.trick)}.</>}
            </p>
          )}
          <p className="text-[13px] text-muted">
            {cached ? (
              <>
                <IconZap size={13} className="-mt-0.5 text-press" /> Replay of a real verdict
              </>
            ) : (
              <>
                Judged live by the blind solver · <span className="num">{elapsed.toFixed(1)} s</span>
              </>
            )}{' '}
            · {boss.name}. The same blind solver checks every Daily is fair.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" size="lg" onClick={onDeck}>
              <IconArrow size={18} /> Doctor another post
            </Button>
            <Button size="lg" onClick={onAgain}>
              <IconReplay size={18} /> Try this post again
            </Button>
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
              className="press flex w-full items-center gap-3 border-2 border-ink bg-sheet px-3 py-2.5 text-left text-sm hover:bg-surface-2 disabled:opacity-50"
            >
              <IconZap size={18} className="text-press" />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-bold">{title}</span>
                <span className="flex items-center gap-1.5 truncate text-[12.5px] text-muted">
                  <span className="shrink-0 text-ink">{TOOL_META[r.edit.type]?.icon}</span>
                  <span className="truncate">
                    {editLabel(it, r.edit)} · {bossOf(r.level).name}
                  </span>
                </span>
              </span>
              <span className="caps text-[12.5px] font-semibold tracking-[0.06em] text-press">Replay →</span>
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
        className="mx-auto w-full max-w-6xl flex-1 px-4 py-8"
        ref={top}
        style={editing ? { paddingBottom: Math.max(barH, 0) + 24 } : undefined}
      >
        <div className="mb-8 grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,400px)] md:items-start">
          <div className="min-w-0">
            <p className="caps inline-block bg-press px-2.5 py-1 text-[12px] font-semibold tracking-[0.1em] text-white">Bonus round · challenge mode</p>
            <h1 className="caps mt-4 text-[52px] leading-[0.95] font-bold tracking-[0.01em] normal-case sm:text-[76px]">Con the Con</h1>
            <div className="double-rule mt-2 max-w-3xl" aria-hidden="true" />
            <p className="mt-3 max-w-2xl text-[17px] leading-relaxed text-ink italic">
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
                <p className="border-[1.5px] border-dashed border-[#B9AE99] p-6 text-center text-sm text-muted">The Fool Deck is empty right now.</p>
              ) : (
                <>
                  <div className="mb-5">
                    <SectionLabel className="!text-[13px] !text-ink">
                      Pick a real post to doctor · facing <BossIcon level={boss.level} size={16} className="align-[-3px]" /> {boss.name}
                    </SectionLabel>
                    <div className="double-rule-thin mt-2" aria-hidden="true" />
                  </div>
                  <ul className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                    {deck.data.map((it) => (
                      <li key={it.id}>
                        <button
                          type="button"
                          onClick={() => choose(it)}
                          className="press group flex h-full w-full flex-col gap-3 border-2 border-ink bg-sheet p-3.5 text-left shadow-[var(--hard)] hover:border-press"
                        >
                          <span className="caps text-[12.5px] font-semibold tracking-[0.1em] text-muted">{it.kind}</span>
                          <FeedCard post={it.post} caseNumber={0} compact watermarkText={WATERMARK} />
                          <span className="mt-auto flex flex-wrap items-center gap-2 pt-2">
                            {it.tools.map((t) => (
                              <span key={t} className="flex items-center gap-1.5 border-[1.5px] border-ink bg-white px-2 py-1 text-[14px] font-bold">
                                {TOOL_META[t]?.icon} {TOOL_META[t]?.label ?? t}
                              </span>
                            ))}
                            <span className="caps ml-auto text-[15px] font-semibold tracking-[0.04em] text-press group-hover:underline">Doctor it →</span>
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              ))}
            {bestLines.length > 0 && (
              <section className="mt-12">
                <h2 className="font-display text-3xl font-bold">The Con’s best lines this session</h2>
                <div className="double-rule-thin mt-2 mb-5" aria-hidden="true" />
                <ul className="grid gap-5 md:grid-cols-3">
                  {bestLines.map((r, i) => (
                    <li key={i} className="con-bubble px-5 py-4 text-[16px] leading-snug">
                      <span aria-hidden="true" className="caps mb-1 block text-[11.5px] font-semibold tracking-[0.1em] text-press-soft not-italic">
                        The Con
                      </span>
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
                <SectionLabel className="mb-2 !text-press">{edit.type === 'none' ? 'The real post' : 'Your doctored post (live preview)'}</SectionLabel>
                <FeedCard post={preview} caseNumber={0} watermarkText={WATERMARK} renderChart={(spec) => <PostChart spec={spec} height={230} />} />
                <p className="mt-4 border-l-4 border-press py-1 pl-3 text-[14px] text-ink">
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
                <button
                  type="button"
                  className="caps inline-flex items-center gap-1 text-[13px] font-semibold tracking-[0.06em] text-ink hover:underline"
                  onClick={() => setPhase('pick')}
                >
                  <IconArrowLeft size={15} /> Back to the deck
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
                    className={`flex items-center gap-2 border-2 border-ink px-3.5 py-2 text-[15px] font-bold ${
                      st.tool === t ? 'bg-ink text-sheet' : 'bg-sheet text-ink hover:bg-surface-2'
                    }`}
                  >
                    {TOOL_META[t].icon} {TOOL_META[t].label}
                    {t === 'none' && <span className="font-normal opacity-80"> (bluff)</span>}
                  </button>
                ))}
              </div>
              <div role="tabpanel" className="mt-4 border-2 border-ink bg-sheet p-5">
                <p className="mb-2 text-[16px] font-bold">{TOOL_META[st.tool].hint}</p>
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
                {st.tool !== 'none' && edit.type === 'none' && (
                  <p className="mt-4 border-[1.5px] border-ochre bg-ochre/10 px-3 py-2 text-[13.5px] text-ink">No change yet, so this would go in as a bluff.</p>
                )}
              </div>
              {editErr && (
                <p role="alert" className="mt-3 border-2 border-press bg-[#F6D5D1] px-3 py-2 text-sm">
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
                className="fixed inset-x-0 bottom-0 z-20 flex flex-col gap-2 border-t-2 border-ink bg-bg px-4 pt-2.5 pb-[max(10px,env(safe-area-inset-bottom))] md:static md:mt-6 md:border-0 md:bg-transparent md:p-0"
              >
                <div className="md:hidden">
                  <BossBoard level={level} onLevel={setLevel} board={board} rounds={rounds} compact />
                </div>
                <button
                  type="button"
                  onClick={submit}
                  disabled={phase === 'judging'}
                  className="press caps flex w-full items-center justify-center gap-2.5 border-2 border-ink bg-press py-3.5 text-xl font-bold tracking-[0.04em] text-white shadow-[var(--hard)] hover:bg-press-dark disabled:opacity-70 sm:text-2xl"
                >
                  {edit.type === 'none' && phase !== 'judging' && <IconEyeOff size={22} />}
                  {phase === 'judging'
                    ? 'Sending…'
                    : edit.type === 'none'
                      ? `Bluff the ${boss.name}`
                      : `Send it to the ${boss.name}`}{' '}
                  <IconArrow size={22} />
                </button>
              </div>
            </section>
          </div>
        )}

        {phase === 'judging' && ack && preview && <Inspecting post={preview} level={level} since={judgeStart.current} />}

        {phase === 'result' && judged && (
          <div className="mx-auto max-w-6xl">
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
          <div role="alert" className="panel mx-auto max-w-2xl px-6 py-8 text-center sm:px-12">
            <div className="relative mx-auto w-fit">
              <ConMascot size={150} className="opacity-60 grayscale" />
              <span className="absolute -top-2 -right-16 text-muted" aria-hidden="true">
                <IconZzz size={64} strokeWidth={2.2} />
              </span>
            </div>
            {phase === 'resting' ? (
              <>
                <p className="mt-4 font-display text-4xl font-bold">The Con is resting.</p>
                <p className="mx-auto mt-3 max-w-md text-[16px] text-ink">
                  {restMsg ?? 'Live rounds are capped so everyone gets a turn.'} Saved rounds replay real verdicts and are always free.
                </p>
                {savedMiss && (
                  <p className="mt-2 text-sm font-bold text-press">That replay isn’t saved on this server any more. Try another one.</p>
                )}
              </>
            ) : (
              <>
                <p className="mt-4 font-display text-4xl font-bold">The Con is asleep.</p>
                <p className="mx-auto mt-3 max-w-md text-[16px] text-ink">
                  No AI available right now, and there’s no earlier verdict saved for this exact edit. We won’t invent one.
                </p>
              </>
            )}
            <SavedRounds deck={deckList} onPlay={playSaved} busy={false} />
            <div className="mt-7 flex flex-wrap justify-center gap-4">
              {phase === 'asleep' && (
                <Button variant="primary" size="lg" onClick={submit}>
                  <IconReplay size={18} /> Try again
                </Button>
              )}
              <Button size="lg" onClick={() => setPhase(item ? 'edit' : 'pick')}>
                {item ? <IconPen size={17} /> : <IconArrowLeft size={17} />} {item ? 'Change the edit' : 'Back to the deck'}
              </Button>
            </div>
          </div>
        )}
      </main>
    </>
  )
}
