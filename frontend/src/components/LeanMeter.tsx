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
  const muted = onPaper ? 'text-[#4A4234]' : 'text-muted'

  return (
    <div className="w-full">
      <div className="flex items-baseline justify-between gap-2">
        <span className={`caps text-[12px] font-semibold tracking-[0.1em] ${muted}`}>Gullible ↔ Paranoid</span>
        {name && <span className="caps text-xl font-bold text-ink">{name}</span>}
      </div>
      <div
        className="relative mt-2 flex h-4 border-2 border-ink"
        role="meter"
        aria-label="How your guesses leaned, from gullible to paranoid"
        aria-valuemin={-1}
        aria-valuemax={1}
        aria-valuenow={has ? Number(v.toFixed(2)) : undefined}
        aria-valuetext={name ? `${name}${has ? ` (${v.toFixed(2)})` : ''}` : 'Not enough answers yet'}
      >
        {/* five bands: press red, pink, paper (the sweet spot), tan, ochre */}
        <span className="h-full flex-1 bg-press" aria-hidden="true" />
        <span className="h-full flex-1 bg-[#D98A84]" aria-hidden="true" />
        <span className="h-full flex-1 bg-sheet outline-[1.5px] outline-offset-[-3px] outline-ink outline-solid" aria-hidden="true" />
        <span className="h-full flex-1 bg-[#D9B77A]" aria-hidden="true" />
        <span className="h-full flex-1 bg-ochre" aria-hidden="true" />
        {has && (
          <span
            className="meter-slide absolute top-1/2 h-7 w-7 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-sheet bg-ink"
            style={{ left: `${pos}%` }}
            aria-hidden="true"
          />
        )}
      </div>
      <div className={`mt-1.5 grid grid-cols-5 text-center text-[12px] ${muted}`} aria-hidden="true">
        {BANDS.map((b) => (
          <span key={b} className={b === name ? 'font-bold text-ink' : ''}>
            {b}
          </span>
        ))}
      </div>
      {!has && <p className={`mt-2 text-xs ${muted}`}>Play a few cards and the meter finds your lean.</p>}
      {explain && <p className={`mt-2 text-[13px] ${muted}`}>{LEAN_EXPLAINER}</p>}
    </div>
  )
}
