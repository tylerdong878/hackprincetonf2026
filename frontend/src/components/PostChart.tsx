import { useMemo } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatNumber } from '../lib/format'
import type { ChartSpec } from '../lib/types'

// Charts live on light "feed" surfaces in every theme, so they use the light-mode steps.
const INK = '#0F1419'
const MUTED = '#536471'
const GRID = '#E7E9EC'
const AXIS = '#B8BEC6'
const SERIES = '#2a78d6'

function niceStep(range: number, target = 5): number {
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
  if (spec.y_max != null) return [min, spec.y_max]
  const step = niceStep(dataMax - min)
  return [min, Math.ceil((dataMax * 1.04) / step) * step]
}

function ticksFor(min: number, max: number, settled: boolean): number[] {
  const step = niceStep(max - min)
  const first = Math.ceil(min / step - 1e-9) * step
  const ticks: number[] = []
  for (let v = first; v <= max + 1e-9; v += step) ticks.push(Number(v.toFixed(6)))
  // Always label where the axis starts, so a truncated floor is visible to a careful reader.
  if (settled && (ticks.length === 0 || Math.abs(ticks[0] - min) > 1e-6)) ticks.unshift(min)
  return ticks
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
  return `${spec.type === 'line' ? 'Line' : 'Bar'} chart${spec.title ? `, “${spec.title}”` : ''}. ${range}. The y-axis runs from ${formatNumber(lo, Number.isInteger(lo) ? 0 : 1)} to ${formatNumber(max, Number.isInteger(max) ? 0 : 1)}.`
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

/**
 * Renders a post's chart with exactly the axis it declares (the misleading-chart trick is a truncated axis).
 * `yMinOverride` lets the reveal morph the floor down to the honest value.
 */
export function PostChart({
  spec,
  height = 200,
  yMinOverride,
  showTitle = true,
  compact = false,
  animating = false,
}: {
  spec: ChartSpec
  height?: number
  yMinOverride?: number
  showTitle?: boolean
  compact?: boolean
  /** True while the axis is morphing: skip the floor label so ticks don't jitter. */
  animating?: boolean
}) {
  const [baseMin, max] = chartDomain(spec)
  const min = yMinOverride ?? baseMin
  const settled = !animating
  const ticks = useMemo(() => ticksFor(min, max, settled), [min, max, settled])
  const data = spec.points
  const many = data.length > 8
  const tickStyle = { fontSize: compact ? 11 : 12, fill: MUTED }
  const yWidth = Math.max(30, String(formatNumber(max, 0)).length * 8 + 14)

  const axes = (
    <>
      <CartesianGrid vertical={false} stroke={GRID} />
      <XAxis
        dataKey="label"
        tick={tickStyle}
        tickLine={false}
        axisLine={{ stroke: AXIS }}
        interval={many ? 'preserveStartEnd' : 0}
        minTickGap={many ? 18 : 4}
      />
      <YAxis
        domain={[min, max]}
        allowDataOverflow
        ticks={ticks}
        interval={0}
        tick={tickStyle}
        tickLine={false}
        axisLine={{ stroke: AXIS }}
        width={yWidth}
        tickFormatter={(v: number) => formatNumber(v, Number.isInteger(v) ? 0 : 1)}
      />
      <Tooltip
        cursor={spec.type === 'line' ? { stroke: AXIS, strokeWidth: 1 } : { fill: 'rgba(15,20,25,0.05)' }}
        content={<TooltipBox unit={spec.unit} />}
        isAnimationActive={false}
      />
    </>
  )

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
            <LineChart data={data} margin={{ top: 10, right: 12, bottom: 0, left: 0 }}>
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
            </LineChart>
          ) : (
            <BarChart data={data} margin={{ top: 22, right: 8, bottom: 0, left: 0 }} barCategoryGap="28%">
              {axes}
              <Bar dataKey="value" fill={SERIES} radius={[4, 4, 0, 0]} maxBarSize={56} isAnimationActive={false}>
                {data.length <= 6 && (
                  <LabelList
                    dataKey="value"
                    position="top"
                    style={{ fontSize: 12, fontWeight: 600, fill: INK }}
                    formatter={(v: unknown) => (typeof v === 'number' ? formatNumber(v) : String(v ?? ''))}
                  />
                )}
              </Bar>
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
