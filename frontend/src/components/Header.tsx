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
      className={`inline-flex h-9 w-9 shrink-0 items-center justify-center text-muted hover:bg-ink hover:text-white ${className}`}
    >
      {muted ? <IconSoundOff size={18} /> : <IconSoundOn size={18} />}
    </button>
  )
}

/** The corner logo: the blackletter "Grain of Salt", linking home. */
export function Brand({ compact = false, size = 34 }: { compact?: boolean; size?: number }) {
  return (
    <a
      href={href('/')}
      className="group -mx-2 flex shrink-0 items-center px-2 py-1 transition-colors hover:bg-ink focus-visible:bg-ink"
      aria-label="Grain of Salt, home"
    >
      <Logotype size={compact ? Math.round(size * 0.8) : size} className="transition-[filter] group-hover:invert group-focus-visible:invert" />
    </a>
  )
}

// The five sections in the Figma header. `short` is used below md. (The Editor's Desk is linked from Case Files.)
const NAV = [
  { to: '/daily', label: 'Daily', short: 'Daily', key: 'daily' },
  { to: '/con', label: 'Con the Con', short: 'Con', key: 'con' },
  { to: '/casefiles', label: 'Case Files', short: 'Files', key: 'casefiles' },
  { to: '/casebook', label: 'Casebook', short: 'Tricks', key: 'casebook' },
  { to: '/dossier', label: 'Dossier', short: 'Stats', key: 'dossier' },
]

/**
 * One header system (Figma "site-header"): blackletter logo | caps nav (the current page is a black
 * tab), the streak flame and the rating box on the right, and the double rule underneath.
 */
export function SiteHeader({ active, right }: { active?: string; right?: ReactNode }) {
  const profile = usePlayerProfile()
  return (
    <header className="sticky top-0 z-30 bg-newsprint">
      <div className="mx-auto flex h-16 max-w-[1440px] items-center gap-2 px-4 sm:gap-4 sm:px-6 md:h-[82px] lg:pl-[21px]">
        <span className="sm:hidden">
          <Brand size={20} />
        </span>
        <span className="hidden sm:inline-flex">
          <Brand size={34} />
        </span>
        <nav aria-label="Main" className="ml-auto flex min-w-0 items-center gap-0.5 sm:ml-4 sm:gap-1 lg:ml-12 lg:gap-6 xl:gap-9">
          {NAV.map((n) => (
            <a
              key={n.key}
              href={href(n.to)}
              aria-current={active === n.key ? 'page' : undefined}
              className={`caps px-1.5 py-1 text-[12px] font-medium whitespace-nowrap sm:px-2 sm:text-[13px] ${
                active === n.key ? 'bg-ink text-white' : 'text-ink hover:underline hover:decoration-2 hover:underline-offset-4'
              } ${n.key === 'casebook' || n.key === 'dossier' ? 'hidden sm:inline-block' : ''}`}
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

/** The case bar / mobile bar variant: logo on the left, anything on the right, same double rule. */
export function BarHeader({ children, right, className = '' }: { children?: ReactNode; right?: ReactNode; className?: string }) {
  return (
    <header className={`sticky top-0 z-30 bg-newsprint ${className}`}>
      <div className="mx-auto flex min-h-14 max-w-[1440px] items-center gap-3 px-4 py-2 sm:px-6">
        <Brand size={24} />
        {children && (
          <>
            <div className="min-w-0 flex-1">{children}</div>
          </>
        )}
        <div className="ml-auto flex shrink-0 items-center gap-2">{right}</div>
      </div>
      <div className="double-rule" aria-hidden="true" />
    </header>
  )
}
