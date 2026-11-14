import type { ReactNode } from 'react'
import { href } from '../lib/router'
import { play, useMuted } from '../lib/sound'
import { BrandIcon, Wordmark } from './Art'

/** 🔊 / 🔇 in the header. Sound starts after the first tap; the choice is remembered. */
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
      className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-base text-muted hover:bg-surface-2 hover:text-text ${className}`}
    >
      <span aria-hidden="true">{muted ? '🔇' : '🔊'}</span>
    </button>
  )
}

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <a href={href('/')} className="flex shrink-0 items-center rounded-lg" aria-label="Grain of Salt, home">
      {compact ? (
        <BrandIcon size={40} />
      ) : (
        <>
          <span className="inline-flex sm:hidden">
            <BrandIcon size={40} />
          </span>
          <span className="hidden sm:inline-flex">
            <Wordmark height={46} />
          </span>
        </>
      )}
    </a>
  )
}

// `short` is used below md; `wide` items only appear from lg (they're also on Home).
const NAV = [
  { to: '/daily', label: 'Daily', short: 'Daily', key: 'daily' },
  { to: '/con', label: 'Con the Con', short: 'Con', key: 'con' },
  { to: '/casefiles', label: 'Case Files', short: 'Files', key: 'casefiles' },
  { to: '/casebook', label: 'Casebook', short: 'Casebook', key: 'casebook', wide: true },
  { to: '/dossier', label: 'Dossier', short: 'Dossier', key: 'dossier' },
  { to: '/teacher', label: 'Editor’s Desk', short: 'Desk', key: 'teacher', wide: true },
]

export function SiteHeader({ active, right }: { active?: string; right?: ReactNode }) {
  return (
    <header className="sticky top-0 z-30 border-b border-line/70 bg-bg/85 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-2 px-4 sm:gap-3">
        <Brand />
        <nav aria-label="Main" className="ml-auto flex min-w-0 items-center gap-0.5">
          {NAV.map((n) => (
            <a
              key={n.key}
              href={href(n.to)}
              aria-current={active === n.key ? 'page' : undefined}
              className={`rounded-lg px-2 py-1.5 text-sm font-semibold whitespace-nowrap md:px-2.5 ${
                active === n.key ? 'bg-surface-2 text-text' : 'text-muted hover:text-text'
              } ${n.wide ? 'hidden lg:inline-block' : ''}`}
            >
              <span className="md:hidden">{n.short}</span>
              <span className="hidden md:inline">{n.label}</span>
            </a>
          ))}
          {right}
        </nav>
        <SoundToggle className="-mr-1.5" />
      </div>
    </header>
  )
}
