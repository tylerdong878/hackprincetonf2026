import { useMemo } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { decimalsFor, formatNumber, withUnit } from '../lib/format'
import type { ChartSpec } from '../lib/types'

// Charts live on light "feed" surfaces in every theme, so they use the light-mode steps.
const INK = '#0F1419'
const MUTED = '#536471'
const GRID = '#E7E9EC'
const AXIS = '#B8BEC6'
const SERIES = '#2a78d6'
const TRICK = '#C62F24' // the trick marker (red on white: 5.6:1)
const TRICK_BG = '#FDE7E4'
const HONEST = '#1E7A4C'
const HONEST_BG = '#E3F4EA'

export function niceStep(range: number, target = 5): number {
  if (!(range > 0)) return 1
  const raw = range / target
  const mag = Math.pow(10, Math.floor(Math.log10(raw)))
  const norm = raw / mag
  const mult = norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10
  return mult * mag
}

/** The exact axis the post uses: y_min as given (default 0), y_max as given or rounded up from the data. */
export function chartDomain(spec: ChartSpec): [number, number] {
  const values = spec.points.map((p) => p.value)
  const dataMax = values.length ? Math.max(...values) : 1
  const min = spec.y_min ?? 0
  if (spec.y_max != null && spec.y_max > min) return [min, spec.y_max]
  const step = niceStep(dataMax - min)
  return [min, Math.ceil((dataMax * 1.04) / step) * step]
}

function ticksFor(min: number, max: number, settled: boolean): { ticks: number[]; step: number } {
  const step = niceStep(max - min)
  const first = Math.ceil(min / step - 1e-9) * step
  const ticks: number[] = []
  for (let v = first; v <= max + 1e-9; v += step) ticks.push(Number(v.toFixed(6)) || 0)
  // Always label where the axis starts (0 included), so a truncated floor is visible to a careful reader.
  if (settled && (ticks.length === 0 || Math.abs(ticks[0] - min) > 1e-6)) ticks.unshift(Number(min.toFixed(6)) || 0)
  return { ticks, step }
}

export function chartSummary(spec: ChartSpec, yMin?: number): string {
  const [min, max] = chartDomain(spec)
  const lo = yMin ?? min
  const pts = spec.points
  const unit = spec.unit ? ` ${spec.unit}` : ''
  const range =
    pts.length > 4
      ? `${pts.length} points from ${pts[0].label} (${formatNumber(pts[0].value)}${unit}) to ${pts[pts.length - 1].label} (${formatNumber(pts[pts.length - 1].value)}${unit})`
      : pts.map((p) => `${p.label}: ${formatNumber(p.value)}${unit}`).join('; ')
  return `${spec.type === 'line' ? 'Line' : 'Bar'} chart${spec.title ? `, “${spec.title}”` : ''}. ${range}. The y-axis runs from ${formatNumber(lo, Number.isInteger(lo) ? 0 : 2)} to ${formatNumber(max, Number.isInteger(max) ? 0 : 2)}.`
}

function TooltipBox({ active, payload, label, unit }: { active?: boolean; payload?: { value?: number }[]; label?: string; unit?: string | null }) {
  if (!active || !payload?.length) return null
  const v = payload[0].value
  return (
    <div className="rounded-md border border-[#E1E4E8] bg-white px-2.5 py-1.5 text-xs shadow-md feed-font" style={{ color: INK }}>
      <div style={{ color: MUTED }}>{label}</div>
      <div className="font-semibold">
        {typeof v === 'number' ? formatNumber(v) : v} {unit}
      </div>
    </div>
  )
}

/** Annotations that point at the trick (reveal only, never on a card the player is judging). */
export interface ChartMarks {
  /** Mark where the axis starts: a red bracket on the axis and a "$2.10, not 0" tag. */
  floor?: boolean
  /** X labels to highlight (e.g. the cherry-picked months). */
  labels?: string[]
  /** 'trick' = red (what the post did), 'honest' = green (what the honest view uses). */
  tone?: 'trick' | 'honest'
}

interface TickProps {
  x?: number
  y?: number
  payload?: { value?: string | number }
}

const X_AXIS_H = 30
const FLOOR_TAG_SPACE = 24

/**
 * A truncated axis, marked: the classic "//" axis break and a bracket at the floor, plus a "$2.10, not 0"
 * callout under the axis corner (below the month labels, so it never covers a bar).
 */
function FloorTag({ viewBox, text, compact, yWidth }: { viewBox?: { x?: number; y?: number }; text: string; compact: boolean; yWidth: number }) {
  const x = viewBox?.x ?? 0
  const y = viewBox?.y ?? 0
  const fs = compact ? 10.5 : 12
  const tw = text.length * fs * 0.57 + 22
  const left = Math.max(2, x - yWidth + 2)
  const top = y + X_AXIS_H + 2
  return (
    <g aria-hidden="true">
      {/* axis break on the y axis, just above the floor */}
      <path d={`M ${x - 6} ${y - 10} l 12 -5 M ${x - 6} ${y - 5} l 12 -5`} stroke={TRICK} strokeWidth={2.2} strokeLinecap="round" />
      {/* bracket at the floor the post chose */}
      <path d={`M ${x + 1} ${y - 16} L ${x + 1} ${y} L ${x + 10} ${y}`} fill="none" stroke={TRICK} strokeWidth={2.6} />
      {/* callout from the axis corner down to the tag */}
      <path d={`M ${x} ${y + 3} L ${x} ${top}`} stroke={TRICK} strokeWidth={1.4} strokeDasharray="2 2" />
      <rect x={left} y={top} width={tw} height={fs + 8} rx={4} fill={TRICK_BG} stroke={TRICK} strokeWidth={1.2} />
      <text x={left + 8} y={top + fs + 2.5} fontSize={fs} fontWeight={700} fill={TRICK}>
        ▲ {text}
      </text>
    </g>
  )
}

/**
 * Renders a post's chart with exactly the axis it declares (the misleading-chart trick is a truncated axis).
 * `yMinOverride` lets the reveal morph the floor down to the honest value; `marks` annotate the trick.
 */
export function PostChart({
  spec,
  height = 200,
  yMinOverride,
  yMaxOverride,
  showTitle = true,
  compact = false,
  animating = false,
  marks,
}: {
  spec: ChartSpec
  height?: number
  yMinOverride?: number
  /** Lets "Drop the axis to 0" move the top too, onto the honest chart's scale. */
  yMaxOverride?: number
  showTitle?: boolean
  compact?: boolean
  /** True while the axis is morphing: skip the floor label so ticks don't jitter. */
  animating?: boolean
  marks?: ChartMarks
}) {
  const [baseMin, baseMax] = chartDomain(spec)
  const min = yMinOverride ?? baseMin
  const max = yMaxOverride ?? baseMax
  const settled = !animating
  const { ticks, step } = useMemo(() => ticksFor(min, max, settled), [min, max, settled])
  const digits = decimalsFor(step)
  // A floor like 19.5 on a step-1 axis still needs its decimal ("19.5", not "20").
  const fmtTick = (v: number) => {
    if (Number.isInteger(v)) return formatNumber(v, 0)
    const own = Math.abs(v * 10 - Math.round(v * 10)) < 1e-6 ? 1 : 2
    return formatNumber(v, Math.max(digits, own))
  }
  const data = spec.points
  const many = data.length > 8
  const tickStyle = { fontSize: compact ? 11 : 12, fill: MUTED }
  const longest = Math.max(...ticks.map((t) => fmtTick(t).length), 1)
  const yWidth = Math.max(30, longest * 7 + 14)
  const floorMark = !!marks?.floor && settled && min > 1e-9
  // Keep the space reserved while the axis drops, so the chart does not jump.
  const floorSpace = !!marks?.floor && baseMin > 1e-9
  const hot = new Set(marks?.labels ?? [])
  const hotColor = marks?.tone === 'honest' ? HONEST : TRICK
  const hotBg = marks?.tone === 'honest' ? HONEST_BG : TRICK_BG

  const XTick = ({ x = 0, y = 0, payload }: TickProps) => {
    const label = String(payload?.value ?? '')
    const on = hot.has(label)
    const fs = tickStyle.fontSize
    const tw = label.length * fs * 0.58 + 8
    return (
      <g transform={`translate(${x},${y})`}>
        {on && <rect x={-tw / 2} y={2} width={tw} height={fs + 6} rx={4} fill={hotBg} stroke={hotColor} strokeWidth={1} />}
        <text x={0} y={fs + 3} textAnchor="middle" fontSize={fs} fontWeight={on ? 700 : 400} fill={on ? hotColor : MUTED}>
          {label}
        </text>
      </g>
    )
  }

  const YTick = ({ x = 0, y = 0, payload }: TickProps) => {
    const v = Number(payload?.value ?? 0)
    const isFloor = floorMark && Math.abs(v - min) < 1e-6
    return (
      <text x={x} y={y} dy={4} textAnchor="end" fontSize={tickStyle.fontSize} fontWeight={isFloor ? 700 : 400} fill={isFloor ? TRICK : MUTED}>
        {fmtTick(v)}
      </text>
    )
  }

  const axes = (
    <>
      <CartesianGrid vertical={false} stroke={GRID} />
      <XAxis
        dataKey="label"
        tick={hot.size ? <XTick /> : tickStyle}
        tickLine={false}
        axisLine={{ stroke: AXIS }}
        interval={many ? 'preserveStartEnd' : 0}
        minTickGap={many ? 18 : 4}
        height={X_AXIS_H}
      />
      <YAxis
        domain={[min, max]}
        allowDataOverflow
        ticks={ticks}
        interval={0}
        tick={<YTick />}
        tickLine={false}
        axisLine={{ stroke: floorMark ? TRICK : AXIS, strokeWidth: floorMark ? 1.5 : 1 }}
        width={yWidth}
      />
      <Tooltip
        cursor={spec.type === 'line' ? { stroke: AXIS, strokeWidth: 1 } : { fill: 'rgba(15,20,25,0.05)' }}
        content={<TooltipBox unit={spec.unit} />}
        isAnimationActive={false}
      />
    </>
  )

  const floor = floorMark ? (
    <ReferenceLine
      y={min}
      stroke={TRICK}
      strokeWidth={2}
      strokeDasharray="5 3"
      ifOverflow="extendDomain"
      label={(p: { viewBox?: { x?: number; y?: number } }) => (
        <FloorTag viewBox={p.viewBox} text={`${withUnit(min, spec.unit)}, not 0`} compact={compact} yWidth={yWidth} />
      )}
    />
  ) : null

  return (
    <figure className="m-0 feed-font" aria-label={chartSummary(spec, min)} role="group">
      {showTitle && (spec.title || spec.unit) && (
        <figcaption className="mb-1.5 text-[13px] font-semibold" style={{ color: INK }}>
          {spec.title}
          {spec.unit && <span className="font-normal" style={{ color: MUTED }}> ({spec.unit})</span>}
        </figcaption>
      )}
      <div style={{ height }} aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 320, height }}>
          {spec.type === 'line' ? (
            <LineChart data={data} margin={{ top: 10, right: 12, bottom: floorSpace ? FLOOR_TAG_SPACE : 0, left: floorSpace ? 6 : 0 }}>
              {axes}
              <Line
                type="linear"
                dataKey="value"
                stroke={SERIES}
                strokeWidth={2}
                dot={data.length <= 12 ? { r: 3, fill: SERIES, strokeWidth: 0 } : false}
                activeDot={{ r: 5, stroke: '#fff', strokeWidth: 2 }}
                isAnimationActive={false}
              />
              {floor}
            </LineChart>
          ) : (
            <BarChart data={data} margin={{ top: 22, right: 8, bottom: floorSpace ? FLOOR_TAG_SPACE : 0, left: floorSpace ? 6 : 0 }} barCategoryGap="28%">
              {axes}
              <Bar dataKey="value" fill={SERIES} radius={[4, 4, 0, 0]} maxBarSize={56} isAnimationActive={false}>
                {data.length <= 6 && (
                  <LabelList
                    dataKey="value"
                    position="top"
                    style={{ fontSize: compact ? 11 : 12, fontWeight: 600, fill: INK }}
                    formatter={(v: unknown) => (typeof v === 'number' ? formatNumber(v) : String(v ?? ''))}
                  />
                )}
              </Bar>
              {floor}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
      {/* Accessible data table (SPEC §3.12) */}
      <table className="sr-only">
        <caption>{spec.title ?? 'Chart data'}</caption>
        <thead>
          <tr>
            <th scope="col">Label</th>
            <th scope="col">Value{spec.unit ? ` (${spec.unit})` : ''}</th>
          </tr>
        </thead>
        <tbody>
          {data.map((p) => (
            <tr key={p.label}>
              <td>{p.label}</td>
              <td>{p.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  )
}
