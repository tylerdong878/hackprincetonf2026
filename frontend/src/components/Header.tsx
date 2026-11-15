import type { ReactNode } from 'react'
import { href } from '../lib/router'
import { play, useMuted } from '../lib/sound'
import { RatingBadge, usePlayerProfile } from '../screens/common'
import { Logotype } from './Art'
import { IconSoundOff, IconSoundOn } from './Icon'

/** Sound on / off in the header. Sound starts after the first tap; the choice is remembered. */
export function SoundToggle({ className = '' }: { className?: string }) {
  const [muted, setMuted] = useMuted()
  return (
    <button
      type="button"
      aria-pressed={!muted}
      aria-label={muted ? 'Sound off. Turn sound on' : 'Sound on. Turn sound off'}
      title={muted ? 'Sound off' : 'Sound on'}
      onClick={() => {
        setMuted(!muted)
        if (muted) window.setTimeout(() => play('tile'), 30)
      }}
      className={`inline-flex h-9 w-9 shrink-0 items-center justify-center text-muted hover:bg-ink hover:text-sheet ${className}`}
    >
      {muted ? <IconSoundOff size={18} /> : <IconSoundOn size={18} />}
    </button>
  )
}

/** The corner logo: "Grain of Salt" in Gloock, linking home. */
export function Brand({ compact = false, size = 34 }: { compact?: boolean; size?: number }) {
  return (
    <a href={href('/')} className="flex shrink-0 items-center" aria-label="Grain of Salt, home">
      <Logotype size={compact ? Math.round(size * 0.8) : size} className="leading-none" />
    </a>
  )
}

// `short` is used below md; `wide` items only appear from lg (they're also on Home).
const NAV = [
  { to: '/daily', label: 'Daily', short: 'Daily', key: 'daily' },
  { to: '/con', label: 'Con the Con', short: 'Con', key: 'con' },
  { to: '/casefiles', label: 'Case Files', short: 'Files', key: 'casefiles' },
  { to: '/casebook', label: 'Tricks', short: 'Tricks', key: 'casebook', wide: true },
  { to: '/dossier', label: 'Stats', short: 'Stats', key: 'dossier' },
  { to: '/editor', label: 'Editor’s Desk', short: 'Desk', key: 'editor', wide: true },
]

/**
 * One header system (Figma "Site header"): Gloock nameplate | Oswald caps nav, the streak + rating
 * badge on the right, and the double rule underneath.
 */
export function SiteHeader({ active, right }: { active?: string; right?: ReactNode }) {
  const profile = usePlayerProfile()
  return (
    <header className="sticky top-0 z-30 bg-sheet">
      <div className="mx-auto flex h-16 max-w-[1360px] items-center gap-2 px-4 sm:gap-4 sm:px-6">
        <span className="sm:hidden">
          <Brand size={24} />
        </span>
        <span className="hidden sm:inline-flex">
          <Brand size={32} />
        </span>
        <span aria-hidden="true" className="hidden h-10 w-px bg-ink sm:block" />
        <nav aria-label="Main" className="ml-auto flex min-w-0 items-center gap-0.5 sm:ml-0 sm:gap-1">
          {NAV.map((n) => (
            <a
              key={n.key}
              href={href(n.to)}
              aria-current={active === n.key ? 'page' : undefined}
              className={`caps px-1.5 py-1.5 text-[12.5px] whitespace-nowrap sm:px-2.5 sm:text-[13px] ${
                active === n.key ? 'bg-ink text-sheet' : 'text-ink hover:underline hover:decoration-2 hover:underline-offset-4'
              } ${n.wide ? 'hidden lg:inline-block' : ''}`}
            >
              <span className="md:hidden">{n.short}</span>
              <span className="hidden md:inline">{n.label}</span>
            </a>
          ))}
        </nav>
        <div className="flex shrink-0 items-center gap-1 sm:ml-auto">
          {right}
          <RatingBadge profile={profile} />
          <SoundToggle className="-mr-1.5" />
        </div>
      </div>
      <div className="double-rule" aria-hidden="true" />
    </header>
  )
}

/** The case bar / mobile bar variant: nameplate on the left, anything on the right, same double rule. */
export function BarHeader({ children, right, className = '' }: { children?: ReactNode; right?: ReactNode; className?: string }) {
  return (
    <header className={`sticky top-0 z-30 bg-sheet ${className}`}>
      <div className="mx-auto flex min-h-14 max-w-[1360px] items-center gap-3 px-4 py-2 sm:px-6">
        <Brand size={26} />
        {children && (
          <>
            <span aria-hidden="true" className="hidden h-9 w-px bg-ink sm:block" />
            <div className="min-w-0 flex-1">{children}</div>
          </>
        )}
        <div className="ml-auto flex shrink-0 items-center gap-2">{right}</div>
      </div>
      <div className="double-rule" aria-hidden="true" />
    </header>
  )
}
