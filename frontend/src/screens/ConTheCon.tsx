import { useEffect, useMemo, useRef, useState } from 'react'
import { ConMascot } from '../components/Art'
import { ConBubble } from '../components/ConBubble'
import { TOOLS } from '../components/EvidenceKit'
import { SiteHeader } from '../components/Header'
import { FeedCard } from '../components/PostCard'
import { PostChart } from '../components/PostChart'
import { DiffView, change } from '../components/Reveal'
import { Button, ErrorState, Loading, SectionLabel } from '../components/ui'
import { api, ApiError, errorCode } from '../lib/api'
import { formatMonth, formatNumber, trickLabel } from '../lib/format'
import { useAsync, useReducedMotion } from '../lib/hooks'
import { withPlayer } from '../lib/player'
import type { ChartSpec, FoolDeckItem, FoolEdit, FoolJudgeResponse, FoolOutcome, FoolTool, Post } from '../lib/types'

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

const OUTCOME: Record<FoolOutcome, { title: string; sub: string; color: string; win: boolean | null }> = {
  fooled_the_con: { title: 'You fooled the Con!', sub: 'Your edit got past the AI.', color: 'var(--real)', win: true },
  caught: { title: 'Caught!', sub: 'The Con saw through your edit.', color: 'var(--doctored)', win: false },
  con_false_alarm: { title: 'False alarm: the Con doubted the truth.', sub: 'You bluffed with a real post and it took the bait. You win.', color: 'var(--alarm)', win: true },
  con_trusted: { title: 'The Con trusted the truth.', sub: 'A real post, called real. A draw.', color: 'var(--con)', win: null },
}

// A made-up account for previews: doctored posts never stay under a real outlet's name.
const SOCK_PUPPET = { name: 'Garden State Truth', handle: '@gstruth_daily', kind: 'person', verified: false, avatar_color: '#8B5CF6' }

// ---- session scoreboard -----------------------------------------------------------------------
interface Round {
  deck_id: string
  outcome: FoolOutcome
  con_line?: string | null
}
const SESSION_KEY = 'gos.fool.session'
let memoryRounds: Round[] = []
function loadRounds(): Round[] {
  try {
    const raw = window.sessionStorage.getItem(SESSION_KEY)
    if (raw) return JSON.parse(raw) as Round[]
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

function Scoreboard({ rounds, allTime }: { rounds: Round[]; allTime: { fooled: number; played: number } | null }) {
  const wins = rounds.filter((r) => OUTCOME[r.outcome]?.win).length
  return (
    <div className="flex flex-col items-end gap-1">
      <div
        className="inline-flex items-center gap-2 rounded-full border border-con/60 bg-con/10 px-3.5 py-1.5 text-sm font-semibold"
        aria-label={`Fooled the Con ${wins} of ${rounds.length} rounds this session`}
      >
        🎭 Fooled the Con <span className="font-mono">{wins}/{rounds.length}</span>
        <span className="font-normal text-muted">this session</span>
      </div>
      {allTime && allTime.played > 0 && (
        <span className="text-xs text-muted">
          All-time: <span className="font-mono">{allTime.fooled}/{allTime.played}</span>
        </span>
      )}
    </div>
  )
}

// ---- edit helpers -----------------------------------------------------------------------------
function seriesOf(item: FoolDeckItem) {
  return item.editable.chart_series ?? item.post.chart?.points ?? []
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

/** A local approximation of the edited post, for the live preview (the server's apply_edit is the source of truth). */
function previewPost(item: FoolDeckItem, edit: FoolEdit): Post {
  const p: Post = { ...item.post, quote: item.post.quote ? { ...item.post.quote } : item.post.quote }
  if (edit.type === 'none') return p
  if (edit.type === 'crop') {
    const words = item.editable.quote_words ?? []
    const text = edit.keep_word_indices.map((i) => words[i]).join(' ')
    if (p.quote) p.quote = { ...p.quote, text }
    else p.body = text
  } else if (edit.type === 'axis' && p.chart) {
    p.chart = { ...p.chart, y_min: edit.y_min }
  } else if (edit.type === 'window') {
    const s = seriesOf(item)
    const pts = edit.window.map((l) => s.find((x) => x.label === l)).filter(Boolean) as { label: string; value: number }[]
    const base: ChartSpec = p.chart ?? { type: 'bar', title: '', unit: '', points: [], y_min: 0, y_max: null }
    p.chart = { ...base, type: 'bar', points: pts.map((x) => ({ label: formatMonth(x.label), value: x.value })), y_max: null }
  } else if (edit.type === 'drop') {
    const d = item.editable.stat?.droppable.find((x) => x.id === edit.drop)
    const full = item.editable.stat?.full
    if (d) p.body = full && p.body.includes(full) ? p.body.replace(full, d.shown_without) : d.shown_without
  }
  p.author = { ...SOCK_PUPPET }
  p.source_label = null
  return p
}

// ---- editor tools -----------------------------------------------------------------------------
function CropTool({ words, removed, onChange }: { words: string[]; removed: number[]; onChange: (r: number[]) => void }) {
  const kept = words.length - removed.length
  return (
    <div>
      <p className="mb-2 text-sm text-muted" aria-live="polite">
        Keeping <b className="font-mono text-text">{kept}</b> of {words.length} words · minimum {MIN_KEEP}
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
              className={`rounded-md px-1.5 py-0.5 transition ${
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
  const values = seriesOf(item).map((p) => p.value)
  const seriesMin = values.length ? Math.min(...values) : 1
  const step = 0.5
  let max = Math.floor((seriesMin - 1e-9) / step) * step
  if (max >= seriesMin) max -= step
  max = Math.max(0, max)
  const spec = item.post.chart
  return (
    <div className="flex flex-col gap-3">
      <label className="flex flex-col gap-1.5 text-sm">
        <span>
          Y-axis starts at <b className="font-mono text-base">{formatNumber(yMin, Number.isInteger(yMin) ? 0 : 1)}</b>
          {spec?.unit && <span className="text-muted"> {spec.unit}</span>}
        </span>
        <input
          type="range"
          min={0}
          max={max}
          step={step}
          value={Math.min(yMin, max)}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full accent-[var(--con)]"
        />
        <span className="flex justify-between font-mono text-[11px] text-muted">
          <span>0 (honest)</span>
          <span>{formatNumber(max, Number.isInteger(max) ? 0 : 1)} (max)</span>
        </span>
      </label>
      {spec && (
        <p className="text-xs text-muted">
          The axis can start anywhere below the lowest value ({formatNumber(seriesMin)}). Watch the preview steepen.
        </p>
      )}
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
        className="rounded-xl border border-line bg-bg px-3 py-2 font-mono text-sm text-text"
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
          The post will compare {c.from === c.to ? 'a month with itself' : `${formatMonth(value[0])} with ${formatMonth(value[1])}`}:{' '}
          <b className="font-mono">{c.text}</b>
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

// ---- the inspection scene ---------------------------------------------------------------------
function Inspecting({ post }: { post: Post }) {
  return (
    <div className="flex flex-col items-center gap-5 py-6 text-center" role="status" aria-live="polite">
      <div className="relative">
        <ConMascot size={150} shape="door" />
        <span className="magnify absolute top-10 -left-2 text-5xl" aria-hidden="true">
          🔍
        </span>
      </div>
      <p className="font-con text-xl tracking-wide">The Con is inspecting…</p>
      <div className="flex gap-2" aria-hidden="true">
        {TOOLS.map((t) => (
          <span key={t.id} className="pulse-dot rounded-full border border-line px-3 py-1 text-xs text-muted">
            {t.icon} {t.label}
          </span>
        ))}
      </div>
      <div className="w-full max-w-md text-left opacity-90">
        <FeedCard post={post} caseNumber={0} compact watermarkText={WATERMARK} />
      </div>
    </div>
  )
}

function Verdict({ res, onAgain, onDeck }: { res: FoolJudgeResponse; onAgain: () => void; onDeck: () => void }) {
  const reduced = useReducedMotion()
  const lines = res.con.reasoning?.length ? res.con.reasoning : ['…']
  // stage: 0 = tool chosen, 1..n = reasoning lines, n+1 = verdict stamp, n+2 = outcome
  const [stage, setStage] = useState(reduced ? lines.length + 2 : 0)
  const n = lines.length
  const done = stage >= n + 2
  const o = OUTCOME[res.outcome] ?? OUTCOME.con_trusted
  const checked = res.con.checked?.[0]
  const tool = TOOLS.find((t) => t.id === checked)
  const resultRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (stage === 0) {
      const id = window.setTimeout(() => setStage(1), 1100)
      return () => window.clearTimeout(id)
    }
    if (stage === n + 1) {
      const id = window.setTimeout(() => setStage(n + 2), 900)
      return () => window.clearTimeout(id)
    }
  }, [stage, n])

  useEffect(() => {
    if (done) resultRef.current?.focus({ preventScroll: false })
  }, [done])

  const conf = res.con.confidence != null ? Math.round(res.con.confidence * 100) : null

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted">The Con opened ONE tool:</span>
        {TOOLS.map((t) => (
          <span
            key={t.id}
            className={`rounded-full border px-3 py-1 text-sm font-semibold transition ${
              stage >= 1 && t.id === checked ? 'pop border-con bg-con text-on-accent' : 'border-line text-muted opacity-60'
            }`}
          >
            {t.icon} {t.label}
          </span>
        ))}
        {!res.con.checked?.length && stage >= 1 && <span className="text-sm text-muted">none: it judged on sight</span>}
        {!done && (
          <button type="button" className="ml-auto text-xs font-semibold text-muted hover:text-text" onClick={() => setStage(n + 2)}>
            Skip ⏭
          </button>
        )}
      </div>

      <div className="flex items-start gap-3">
        <ConMascot size={72} className="shrink-0" />
        <div className="flex min-w-0 flex-1 flex-col gap-2" aria-live="polite">
          {stage >= 1 && tool && (
            <p className="text-xs text-muted">
              Opened {tool.icon} {tool.label}…
            </p>
          )}
          {lines.slice(0, Math.max(0, Math.min(stage, n))).map((line, i) => (
            <ConBubble
              key={i}
              text={line}
              size="sm"
              speed={18}
              typewriter={i === stage - 1 && stage <= n}
              onDone={i === stage - 1 && stage <= n ? () => window.setTimeout(() => setStage((s) => (s === i + 1 ? s + 1 : s)), 450) : undefined}
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
          {conf != null && <span className="font-mono text-sm text-muted">{conf}% sure</span>}
        </div>
      )}

      {done && (
        <div ref={resultRef} tabIndex={-1} className="rise-in flex flex-col gap-4 focus-visible:outline-none">
          <section
            className="rounded-2xl border-2 p-5 text-center"
            style={{ borderColor: o.color, background: `color-mix(in srgb, ${o.color} 14%, transparent)` }}
            aria-label="Outcome"
          >
            <p className="font-display text-2xl font-bold sm:text-3xl" style={{ color: o.color }}>
              {o.win === true ? '🎉 ' : o.win === false ? '🚨 ' : '🤝 '}
              {o.title}
            </p>
            <p className="mt-1 text-sm text-muted">{o.sub}</p>
          </section>
          {res.con_line && (
            <div className="flex items-end gap-2.5">
              <ConMascot size={44} className="shrink-0" />
              <ConBubble text={res.con_line} size="md" className="min-w-0 flex-1" />
            </div>
          )}
          {res.diff ? (
            <DiffView post={res.edited_post} caseNumber={0} diff={res.diff} autoplay shownLabel="What the Con saw" watermarkText={WATERMARK} />
          ) : (
            <p className="rounded-xl border border-line bg-surface p-4 text-sm">
              {res.changed ? 'Your edit changed the post.' : 'You left it untouched: the post was real, word for word.'}
              {res.trick && <> Trick: {trickLabel(res.trick)}.</>}
            </p>
          )}
          <p className="text-xs text-muted">
            Judged {res.con.cached ? 'from the cache (a real earlier AI verdict for this exact edit)' : 'live'}
            {res.con.model ? ` by ${res.con.model}` : ''}. It’s the same blind solver that checks every Daily is fair.
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

// ---- screen -----------------------------------------------------------------------------------
function normalizeDeck(res: FoolDeckItem[] | { items: FoolDeckItem[] }): FoolDeckItem[] {
  const list = Array.isArray(res) ? res : res?.items ?? []
  return list.filter((x) => x && x.id && x.post)
}

export function ConTheCon() {
  const deck = useAsync(() => api.foolDeck().then(normalizeDeck), [])
  const [item, setItem] = useState<FoolDeckItem | null>(null)
  const [st, setSt] = useState<EditorState | null>(null)
  const [phase, setPhase] = useState<'pick' | 'edit' | 'judging' | 'result' | 'asleep'>('pick')
  const [res, setRes] = useState<FoolJudgeResponse | null>(null)
  const [editErr, setEditErr] = useState<string | null>(null)
  const [err, setErr] = useState<unknown>(null)
  const [rounds, setRounds] = useState<Round[]>(loadRounds)
  const [allTime, setAllTime] = useState<{ fooled: number; played: number } | null>(null)
  const top = useRef<HTMLDivElement>(null)

  const edit = useMemo(() => (item && st ? buildEdit(item, st) : null), [item, st])
  const preview = useMemo(() => (item && edit ? previewPost(item, edit) : null), [item, edit])

  const scrollTop = () => window.setTimeout(() => top.current?.scrollIntoView({ block: 'start', behavior: 'smooth' }), 0)

  const choose = (it: FoolDeckItem) => {
    setItem(it)
    setSt(initialState(it))
    setEditErr(null)
    setErr(null)
    setPhase('edit')
    scrollTop()
  }

  const submit = async () => {
    if (!item || !edit) return
    setPhase('judging')
    setEditErr(null)
    setErr(null)
    scrollTop()
    try {
      const r = await withPlayer((pid) => api.foolJudge(pid, item.id, edit))
      setRes(r)
      if (r.scoreboard) setAllTime(r.scoreboard)
      const next = [...rounds, { deck_id: item.id, outcome: r.outcome, con_line: r.con_line }]
      setRounds(next)
      saveRounds(next)
      setPhase('result')
    } catch (e) {
      if (e instanceof ApiError && (e.status === 503 || errorCode(e) === 'con_asleep')) setPhase('asleep')
      else if (e instanceof ApiError && e.status === 422) {
        setEditErr(e.message || 'That edit isn’t allowed.')
        setPhase('edit')
      } else {
        setErr(e)
        setPhase('edit')
      }
    }
  }

  const bestLines = rounds.filter((r) => r.con_line).slice(-3).reverse()

  return (
    <>
      <SiteHeader active="con" />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6" ref={top}>
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-3xl font-bold sm:text-4xl">Con the Con 🎭</h1>
            <p className="mt-1 max-w-xl text-sm text-muted">
              Doctor a real post with the same tricks the Con uses on you. Our AI, the blind solver that checks every Daily, gets one
              look at the evidence and rules. Can you fool it?
            </p>
          </div>
          <Scoreboard rounds={rounds} allTime={allTime} />
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
                  <SectionLabel className="mb-3">Pick a real post to doctor</SectionLabel>
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
                    <li key={i} className="con-bubble rounded-r-xl rounded-l-sm px-4 py-2 text-sm">
                      “{r.con_line}”
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </>
        )}

        {phase === 'edit' && item && st && edit && preview && (
          <div className="grid gap-6 pb-28 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] md:pb-0">
            <section aria-label="Live preview" className="min-w-0">
              <div className="md:sticky md:top-[72px]">
                <SectionLabel className="mb-2">{edit.type === 'none' ? 'The real post' : 'Your doctored post (live preview)'}</SectionLabel>
                <FeedCard
                  post={preview}
                  caseNumber={0}
                  watermarkText={WATERMARK}
                  renderChart={(spec) => <PostChart spec={spec} height={210} />}
                />
                {edit.type !== 'none' && (
                  <p className="mt-2 text-xs text-muted">
                    Doctored posts move to a made-up account. We never put edited words under a real outlet’s name.
                  </p>
                )}
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
                    Send the real post, untouched. If the Con calls it doctored, it doubted the truth and you win. That’s the over-doubt
                    we train against.
                  </p>
                )}
                {st.tool !== 'none' && edit.type === 'none' && (
                  <p className="mt-3 text-xs text-alarm">No change yet, so this would go in as a bluff.</p>
                )}
              </div>
              {editErr && (
                <p role="alert" className="mt-3 rounded-xl border border-doctored/50 bg-doctored/10 px-3 py-2 text-sm">
                  {editErr}
                </p>
              )}
              {err != null && <ErrorState error={err} className="mt-3" title="Couldn’t reach the Con." />}
              <div className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-bg/95 px-4 py-3 backdrop-blur md:static md:mt-4 md:border-0 md:bg-transparent md:p-0">
                <button
                  type="button"
                  onClick={submit}
                  className="flex w-full items-center justify-center gap-2 rounded-2xl bg-con py-4 font-display text-xl font-semibold text-on-accent shadow-[0_10px_30px_-12px_var(--con)] transition hover:brightness-110 active:scale-[0.98]"
                >
                  {edit.type === 'none' ? '🙈 Bluff: send it untouched' : 'Send it to the Con'} <span aria-hidden="true">→</span>
                </button>
              </div>
            </section>
          </div>
        )}

        {phase === 'judging' && preview && <Inspecting post={preview} />}

        {phase === 'result' && res && (
          <div className="mx-auto max-w-4xl">
            <Verdict
              res={res}
              onAgain={() => {
                setRes(null)
                setPhase('edit')
                scrollTop()
              }}
              onDeck={() => {
                setRes(null)
                setItem(null)
                setPhase('pick')
                scrollTop()
              }}
            />
          </div>
        )}

        {phase === 'asleep' && (
          <div role="alert" className="mx-auto max-w-md rounded-2xl border border-line bg-surface p-6 text-center">
            <ConMascot size={120} className="mx-auto opacity-70" />
            <p className="mt-3 font-display text-2xl font-semibold">The Con is asleep. 💤</p>
            <p className="mt-2 text-sm text-muted">
              No AI available right now, and there’s no earlier verdict cached for this exact edit. We won’t invent one.
            </p>
            <div className="mt-4 flex justify-center gap-2">
              <Button variant="primary" onClick={submit}>
                Try again
              </Button>
              <Button onClick={() => setPhase('edit')}>Change the edit</Button>
            </div>
          </div>
        )}
      </main>
    </>
  )
}
