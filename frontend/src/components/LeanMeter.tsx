import { leanLabel as labelFor } from '../lib/format'
import { LEAN_EXPLAINER } from '../lib/content'

const BANDS = ['Gullible', 'Trusting', 'Balanced', 'Suspicious', 'Paranoid']

/**
 * Gullible ↔ Paranoid meter (PLAN_V2 §1A). `lean` runs from −1 (gullible: fakes slip past)
 * to +1 (paranoid: accusing the truth). Both ends lose points; the middle is the goal.
 */
export function LeanMeter({
  lean,
  label,
  explain = true,
  onPaper = false,
}: {
  lean: number | null | undefined
  label?: string | null
  explain?: boolean
  onPaper?: boolean
}) {
  const has = lean != null && Number.isFinite(lean)
  const v = has ? Math.max(-1, Math.min(1, lean as number)) : 0
  const name = label ?? (has ? labelFor(v) : null)
  const pos = ((v + 1) / 2) * 100
  const muted = onPaper ? 'text-[#5B5140]' : 'text-muted'

  return (
    <div className="w-full">
      <div className="flex items-baseline justify-between gap-2">
        <span className={`text-xs font-bold tracking-[0.16em] uppercase ${muted}`}>Gullible ↔ Paranoid</span>
        {name && <span className="font-display text-lg font-semibold">{name}</span>}
      </div>
      <div
        className="relative mt-2 h-4 rounded-full"
        role="meter"
        aria-label="How your guesses leaned, from gullible to paranoid"
        aria-valuemin={-1}
        aria-valuemax={1}
        aria-valuenow={has ? Number(v.toFixed(2)) : undefined}
        aria-valuetext={name ? `${name}${has ? ` (${v.toFixed(2)})` : ''}` : 'Not enough answers yet'}
        style={{
          background:
            'linear-gradient(90deg, var(--doctored) 0%, color-mix(in srgb, var(--doctored) 35%, var(--real)) 28%, var(--real) 50%, color-mix(in srgb, var(--alarm) 45%, var(--real)) 72%, var(--alarm) 100%)',
        }}
      >
        {/* the sweet spot */}
        <span className="absolute inset-y-0 left-[42.5%] w-[15%] rounded-full border-2 border-white/70" aria-hidden="true" />
        {has && (
          <span
            className="meter-slide absolute top-1/2 h-7 w-7 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-white bg-[#12141C] shadow-lg"
            style={{ left: `${pos}%` }}
            aria-hidden="true"
          />
        )}
      </div>
      <div className={`mt-1.5 flex justify-between text-[11px] ${muted}`} aria-hidden="true">
        {BANDS.map((b) => (
          <span key={b} className={b === name ? 'font-bold text-current' : ''} style={b === name ? { color: 'inherit' } : undefined}>
            {b}
          </span>
        ))}
      </div>
      {!has && <p className={`mt-2 text-xs ${muted}`}>Play a few cards and the meter finds your lean.</p>}
      {explain && <p className={`mt-2 text-[13px] ${muted}`}>{LEAN_EXPLAINER}</p>}
    </div>
  )
}
