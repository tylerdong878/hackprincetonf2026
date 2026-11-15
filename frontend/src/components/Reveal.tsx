import { useState, type ReactNode } from 'react'
import { formatNumber, outcomeStyle, withUnit } from '../lib/format'
import { useReducedMotion, useTween } from '../lib/hooks'
import type { ChartDiff, ChartSpec, Diff, Post } from '../lib/types'
import { IconPlay, IconReplay, OutcomeGlyph } from './Icon'
import { FeedCard } from './PostCard'
import { chartDomain, PostChart } from './PostChart'
import { SectionLabel } from './ui'

/** The outcome stamp (Figma "Outcomes": ink Trusted, paper Caught with a salt crystal, ochre False alarm, red Fooled). */
export function OutcomeBadge({ outcome, animate = true, size = 'md' }: { outcome: string; animate?: boolean; size?: 'sm' | 'md' | 'lg' }) {
  const s = outcomeStyle(outcome)
  const sizes = { sm: 'text-[13px] px-2 py-0.5', md: 'text-[15px] md:text-base px-2.5 py-1', lg: 'text-lg sm:text-xl px-3 py-1' }
  const glyph = { sm: 14, md: 17, lg: 20 }[size]
  return (
    <span
      className={`caps inline-flex items-center gap-1.5 border-2 border-ink font-bold leading-none whitespace-nowrap ${animate ? 'stamp-thunk' : ''} ${sizes[size]}`}
      style={{
        background: s.fill,
        color: s.ink,
        ['--stamp-rot' as string]: '0deg',
        ['--stamp-rot-from' as string]: '-9deg',
      }}
    >
      <OutcomeGlyph outcome={outcome} size={glyph} />
      {s.word}
    </span>
  )
}

// ---- charts: "What you saw" next to "The honest view" -------------------------------------------

interface ChartPair {
  shown: ChartSpec
  honest: ChartSpec
  /** Where the posted axis starts, and its top. */
  from: number
  top: number
  /** The honest chart's top: the posted top when the honest values fit under it, so heights compare. */
  sharedTop: number
  /** Months the post picked that the honest view doesn't use (and vice versa). */
  picked: string[]
  honestPicked: string[]
}

/** The honest chart starts at 0 on the same top as the posted one (when its values fit), so heights compare. */
function chartPair(diff: ChartDiff, post?: Post): ChartPair | null {
  const shown = diff.shown ?? post?.chart ?? null
  const original = diff.original
  if (!shown || !original?.points?.length) return null
  const [from, top] = chartDomain(shown)
  const honestMax = Math.max(...original.points.map((p) => p.value))
  const sharedTop = honestMax <= top ? top : chartDomain({ ...original, y_min: 0, y_max: null })[1]
  const honest: ChartSpec = { ...original, y_min: 0, y_max: sharedTop }
  const sLabels = shown.points.map((p) => p.label)
  const hLabels = original.points.map((p) => p.label)
  const few = shown.points.length <= 6 && original.points.length <= 6
  return {
    shown,
    honest,
    from,
    top,
    sharedTop,
    picked: few ? sLabels.filter((l) => !hLabels.includes(l)) : [],
    honestPicked: few ? hLabels.filter((l) => !sLabels.includes(l)) : [],
  }
}

/**
 * "Drop the axis to 0": the posted chart's floor tweens to 0 and its top to the honest chart's top,
 * so once dropped both charts share one scale.
 */
function useAxisDrop(pair: ChartPair | null) {
  const reduced = useReducedMotion()
  const [playKey, setPlayKey] = useState(0)
  const p = useTween(0, 1, playKey, 800, reduced)
  const from = pair?.from ?? 0
  const top = pair?.top ?? 1
  const shared = pair?.sharedTop ?? top
  return {
    dropped: playKey > 0,
    yMin: playKey ? from * (1 - p) : undefined,
    yMax: playKey ? top + (shared - top) * p : undefined,
    animating: playKey > 0 && p < 1 - 1e-6,
    drop: () => setPlayKey((k) => k + 1),
  }
}

function DropButton({ dropped, onClick, className = '' }: { dropped: boolean; onClick: () => void; className?: string }) {
  return (
    <button
      type="button"
      className={`press caps inline-flex items-center gap-1.5 self-start border-2 border-ink bg-sheet px-2.5 py-1 text-[13px] font-semibold text-ink shadow-[var(--hard-sm)] hover:bg-surface-2 ${className}`}
      onClick={onClick}
    >
      {dropped ? <IconReplay size={15} /> : <IconPlay size={15} />}
      {dropped ? 'Replay the axis drop' : 'Drop the axis to 0'}
    </button>
  )
}

function ShownCaption({ pair }: { pair: ChartPair }) {
  const a = change(pair.shown)
  return (
    <p className="text-[13px] leading-snug text-muted">
      {pair.from > 0 ? (
        <>
          Axis starts at <b className="num text-doctored">{withUnit(pair.from, pair.shown.unit)}</b>, not 0
        </>
      ) : (
        <>Axis starts at 0</>
      )}
      {a && (
        <>
          {' '}
          · shows <b className="num text-text">{a.text}</b> ({a.from} → {a.to})
        </>
      )}
      {pair.picked.length > 0 && (
        <span className="block">
          Picked months: <b className="text-doctored">{pair.picked.join(' and ')}</b>
        </span>
      )}
    </p>
  )
}

function HonestCaption({ pair, onLight = false }: { pair: ChartPair; onLight?: boolean }) {
  const b = change(pair.honest)
  return (
    <p className={`text-[13px] leading-snug ${onLight ? 'text-[#4A4A55]' : 'text-muted'}`}>
      Axis from 0
      {b && (
        <>
          {' '}
          · {b.from} → {b.to}: <b className={`num ${onLight ? 'text-[#1B1B1F]' : 'text-text'}`}>{b.text}</b>
        </>
      )}
    </p>
  )
}

const dot = (color: string) => <span className="mr-1.5 inline-block h-2.5 w-2.5 align-middle" style={{ background: color }} aria-hidden="true" />

export function change(spec: ChartSpec): { text: string; from: string; to: string } | null {
  const pts = spec.points
  if (pts.length < 2) return null
  const a = pts[0]
  const b = pts[pts.length - 1]
  if (!a.value) return null
  const pctChange = ((b.value - a.value) / Math.abs(a.value)) * 100
  const sign = pctChange >= 0 ? '+' : '−'
  return { text: `${sign}${formatNumber(Math.abs(pctChange), 1)}%`, from: a.label, to: b.label }
}

/** Splits `text` into plain and highlighted runs for each phrase in `marks`. */
export function highlightRuns(text: string, marks: string[]): { s: string; hit: boolean }[] {
  const phrases = marks.map((m) => m.trim()).filter(Boolean)
  if (!phrases.length) return [{ s: text, hit: false }]
  const lower = text.toLowerCase()
  const ranges: [number, number][] = []
  for (const p of phrases) {
    let from = 0
    const lp = p.toLowerCase()
    for (;;) {
      const i = lower.indexOf(lp, from)
      if (i < 0) break
      ranges.push([i, i + p.length])
      from = i + p.length
    }
  }
  ranges.sort((x, y) => x[0] - y[0])
  const runs: { s: string; hit: boolean }[] = []
  let pos = 0
  for (const [a, b] of ranges) {
    if (a < pos) continue
    if (a > pos) runs.push({ s: text.slice(pos, a), hit: false })
    runs.push({ s: text.slice(a, b), hit: true })
    pos = b
  }
  if (pos < text.length) runs.push({ s: text.slice(pos), hit: false })
  return runs
}

/** When the diff doesn't list removed words, highlight whatever surrounds the shown crop. */
export function restoredRuns(shown: string, original: string): { s: string; hit: boolean }[] {
  const core = shown.replace(/^[\s“"'….]+|[\s”"'….]+$/g, '')
  const i = core ? original.indexOf(core) : -1
  if (i < 0) return [{ s: original, hit: false }]
  const runs = [
    { s: original.slice(0, i), hit: true },
    { s: original.slice(i, i + core.length), hit: false },
    { s: original.slice(i + core.length), hit: true },
  ]
  return runs.filter((r) => r.s.trim().length > 0 || !r.hit)
}

export function Restored({ runs }: { runs: { s: string; hit: boolean }[] }) {
  return (
    <>
      {runs.map((r, i) =>
        r.hit ? (
          <mark
            key={i}
            className="rounded-sm px-0.5 text-inherit underline decoration-2 underline-offset-[3px]"
            style={{ background: 'var(--highlight)', textDecorationColor: '#141414' }}
          >
            <span className="sr-only">[restored: </span>
            {r.s}
            <span className="sr-only">]</span>
          </mark>
        ) : (
          <span key={i}>{r.s}</span>
        ),
      )}
    </>
  )
}

function OriginalPanel({ children, note }: { children: ReactNode; note?: ReactNode }) {
  return (
    <div className="flex h-full flex-col overflow-hidden border-2 border-ink bg-white text-[#1B1B1F]">
      <div className="flex-1 p-4">{children}</div>
      {note && <div className="border-t border-dashed border-[#CFC6B4] bg-sheet px-4 py-2 text-[13px] text-[#4A4A55]">{note}</div>}
    </div>
  )
}

/**
 * "What you saw" next to "The honest view" (SPEC §3.7), side by side on desktop, stacked on mobile.
 * For charts the posted chart keeps its trick, marked in red; "Drop the axis to 0" animates it honest.
 */
export function DiffView({
  post,
  caseNumber,
  diff,
  shownLabel = 'What you saw',
  watermarkText,
}: {
  post: Post
  caseNumber: number
  diff: Diff
  shownLabel?: string
  watermarkText?: string
}) {
  const pair = diff.type === 'chart' ? chartPair(diff, post) : null
  const axis = useAxisDrop(pair)
  const shownPost: Post = pair ? { ...post, chart: pair.shown } : post

  let right: ReactNode = null
  if (pair) {
    right = (
      <OriginalPanel note={<HonestCaption pair={pair} onLight />}>
        <PostChart spec={pair.honest} height={200} marks={{ labels: pair.honestPicked, tone: 'honest' }} />
      </OriginalPanel>
    )
  } else if (diff.type === 'quote') {
    const runs = diff.removed?.length ? highlightRuns(diff.original, diff.removed) : restoredRuns(diff.shown, diff.original)
    right = (
      <OriginalPanel note={<>Highlighted: the words the post cut.</>}>
        <p className="text-[15px] leading-relaxed">
          “<Restored runs={runs} />”
        </p>
      </OriginalPanel>
    )
  } else if (diff.type === 'stat') {
    const runs = diff.missing ? highlightRuns(diff.original, [diff.missing]) : [{ s: diff.original, hit: false }]
    const found = runs.some((r) => r.hit)
    right = (
      <OriginalPanel note={diff.missing && !found ? <>Left out: <b>{diff.missing}</b></> : <>Highlighted: what the post left out.</>}>
        <p className="text-[15px] leading-relaxed">
          <Restored runs={runs} />
        </p>
      </OriginalPanel>
    )
  } else if (diff.type === 'detail') {
    const changed = diff.changed ?? []
    right = (
      <OriginalPanel note={<DetailChanges changed={changed} />}>
        <p className="text-[15px] leading-relaxed">
          <Restored runs={highlightRuns(diff.original, changed.map((c) => c.from))} />
        </p>
      </OriginalPanel>
    )
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="flex min-w-0 flex-col gap-2">
        <SectionLabel>
          {dot('var(--doctored)')}
          {shownLabel}
        </SectionLabel>
        <FeedCard
          post={shownPost}
          caseNumber={caseNumber}
          watermarkText={watermarkText}
          doctoredStamp
          stampCorner={!!pair}
          renderChart={
            pair
              ? (spec) => (
                  <PostChart
                    spec={spec}
                    height={200}
                    yMinOverride={axis.yMin}
                    yMaxOverride={axis.yMax}
                    animating={axis.animating}
                    marks={{ floor: true, labels: pair.picked, tone: 'trick' }}
                  />
                )
              : undefined
          }
        />
        {pair && (
          <div className="flex flex-col gap-1">
            <ShownCaption pair={pair} />
            {pair.from > 0 && <DropButton dropped={axis.dropped} onClick={axis.drop} />}
          </div>
        )}
      </div>
      <div className="flex min-w-0 flex-col gap-2">
        <SectionLabel>
          {dot('var(--real)')}
          {pair ? 'The honest view' : 'The original'}
        </SectionLabel>
        {right}
      </div>
    </div>
  )
}

export function DetailChanges({ changed }: { changed: { from: string; to: string }[] }) {
  if (!changed.length) return <>Highlighted: the detail that was changed.</>
  return (
    <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {changed.map((c, i) => (
        <span key={i}>
          Really <b className="font-mono">{c.from}</b>, posted as{' '}
          <s className="font-mono decoration-[#C8231B] decoration-2">{c.to}</s>
        </span>
      ))}
    </span>
  )
}

/**
 * The compact before-and-after on a Daily card's back (PLAN_V2 §1A): the chart's axis animates
 * to its honest start, cut words come back highlighted, a missing number reappears, a swapped detail is shown.
 */
export function MiniDiff({ diff, post }: { diff: Diff; post?: Post }) {
  const pair = diff.type === 'chart' ? chartPair(diff, post) : null
  const axis = useAxisDrop(pair)

  // No auto-play: the player first sees the chart exactly as posted (the trick marked in red),
  // then chooses to drop the axis. The honest view sits beside it (below it on a phone).
  const box = 'border-[1.5px] border-ink bg-white p-2.5 text-[14.5px] leading-relaxed text-[#1B1B1F]'
  const label = 'caps text-[12px] font-semibold tracking-[0.1em] text-muted'

  if (pair) {
    return (
      <div className="@container">
        <div className="grid gap-3 @sm:grid-cols-2">
          <div className="flex min-w-0 flex-col gap-1.5">
            <p className={label}>
              {dot('var(--doctored)')}
              What you saw
            </p>
            <div className={box}>
              <PostChart
                spec={pair.shown}
                height={150}
                compact
                yMinOverride={axis.yMin}
                yMaxOverride={axis.yMax}
                animating={axis.animating}
                marks={{ floor: true, labels: pair.picked, tone: 'trick' }}
              />
            </div>
            <ShownCaption pair={pair} />
            {pair.from > 0 && <DropButton dropped={axis.dropped} onClick={axis.drop} />}
          </div>
          <div className="flex min-w-0 flex-col gap-1.5">
            <p className={label}>
              {dot('var(--real)')}
              The honest view
            </p>
            <div className={box}>
              <PostChart spec={pair.honest} height={150} compact marks={{ labels: pair.honestPicked, tone: 'honest' }} />
            </div>
            <HonestCaption pair={pair} />
          </div>
        </div>
      </div>
    )
  }
  if (diff.type === 'quote') {
    const runs = diff.removed?.length ? highlightRuns(diff.original, diff.removed) : restoredRuns(diff.shown, diff.original)
    return (
      <div className={box}>
        <p className="caps mb-1 text-[12px] font-semibold tracking-[0.1em] text-[#5A544B]">The full quote</p>
        <p>
          “<Restored runs={runs} />”
        </p>
      </div>
    )
  }
  if (diff.type === 'stat') {
    const runs = diff.missing ? highlightRuns(diff.original, [diff.missing]) : [{ s: diff.original, hit: false }]
    return (
      <div className={box}>
        <p className="caps mb-1 text-[12px] font-semibold tracking-[0.1em] text-[#5A544B]">The full numbers</p>
        <p>
          <Restored runs={runs} />
        </p>
        {diff.missing && !runs.some((r) => r.hit) && (
          <p className="mt-1 text-[13px] text-[#4A4A55]">
            Left out: <b>{diff.missing}</b>
          </p>
        )}
      </div>
    )
  }
  if (diff.type === 'detail') {
    const changed = diff.changed ?? []
    return (
      <div className={box}>
        <p className="caps mb-1 text-[12px] font-semibold tracking-[0.1em] text-[#5A544B]">The original</p>
        <p>
          <Restored runs={highlightRuns(diff.original, changed.map((c) => c.from))} />
        </p>
        <p className="mt-1.5 text-[13px] text-[#4A4A55]">
          <DetailChanges changed={changed} />
        </p>
      </div>
    )
  }
  return null
}
