import type { ReactNode, Ref } from 'react'
import { trickLabel } from '../lib/format'
import { IconData, IconHash, IconPen, IconSource } from './Icon'

/** The icon for each of the Con's four tricks. */
export function TrickIcon({ trick, size = 18, className = '' }: { trick: string | null | undefined; size?: number; className?: string }) {
  if (trick === 'misleading-chart') return <IconData size={size} className={className} />
  if (trick === 'out-of-context-quote') return <IconSource size={size} className={className} />
  if (trick === 'cherry-picked-stat') return <IconHash size={size} className={className} />
  if (trick === 'edited-detail') return <IconPen size={size} className={className} />
  return null
}

/**
 * One trick picker (Figma "Trick picker"): four tricks plus "Not sure", keys 1-4.
 * Used as the Daily's bottom-sheet body and the Case Files popover. Selected = press-red row.
 */
export function TrickPicker({
  options,
  value,
  notSure = false,
  onPick,
  columns = 1,
  heading = 'What’s the trick?',
  bonus = '+50 if right',
  headingNode,
  className = '',
  groupRef,
  disabled = false,
  notSureLabel = 'Not sure',
}: {
  options: string[]
  /** The trick currently picked (null/undefined = none). */
  value?: string | null
  /** True when "Not sure" is the current pick. */
  notSure?: boolean
  onPick: (trick: string | null) => void
  columns?: 1 | 2
  heading?: string | null
  bonus?: string | null
  headingNode?: ReactNode
  className?: string
  groupRef?: Ref<HTMLDivElement>
  disabled?: boolean
  /** The "Not sure" button's text (the Daily says "Just doctored, not sure how"). */
  notSureLabel?: string
}) {
  return (
    <div ref={groupRef} role="group" aria-label={heading ?? 'Name the trick'} className={className}>
      {headingNode ??
        (heading && (
          <div className="mb-2 flex items-baseline justify-between gap-3">
            <p className="caps text-[12.5px] font-semibold tracking-[0.08em] text-press">{heading}</p>
            {bonus && <p className="caps text-[12px] font-semibold tracking-[0.08em] text-ink">{bonus}</p>}
          </div>
        ))}
      <div className={`grid gap-2 ${columns === 2 ? 'sm:grid-cols-2' : ''}`}>
        {options.map((t, i) => {
          const on = value === t
          return (
            <button
              key={t}
              type="button"
              disabled={disabled}
              aria-pressed={on}
              onClick={() => onPick(t)}
              className={`press flex min-h-[44px] items-center gap-2.5 border-2 px-2.5 py-2 text-left text-[15px] font-bold ${
                on ? 'border-press bg-press text-white' : 'border-press bg-white text-ink hover:bg-press/[0.06]'
              }`}
            >
              {i < 4 && (
                <kbd
                  className={`flex h-6 w-6 shrink-0 items-center justify-center border-[1.5px] text-[11px] font-semibold not-italic ${
                    on ? 'border-white text-white' : 'border-press text-press'
                  }`}
                >
                  {i + 1}
                </kbd>
              )}
              <TrickIcon trick={t} size={18} className={on ? 'text-white' : 'text-press'} />
              <span>{trickLabel(t)}</span>
            </button>
          )
        })}
        <button
          type="button"
          disabled={disabled}
          aria-pressed={notSure}
          onClick={() => onPick(null)}
          className={`flex min-h-[44px] items-center justify-center border-[1.5px] border-dashed px-3 py-2 text-[15px] ${
            notSure ? 'border-ink bg-ink text-sheet' : 'border-ink bg-transparent text-ink hover:bg-ink/[0.05]'
          } ${columns === 2 ? 'sm:col-span-2' : ''}`}
        >
          {notSureLabel}
        </button>
      </div>
    </div>
  )
}
