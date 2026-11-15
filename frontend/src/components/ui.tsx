import { useState, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { ApiError, BACKEND_START_CMD } from '../lib/api'
import { copyText } from '../lib/hooks'
import { href } from '../lib/router'
import { BrandIcon, Spinner } from './Art'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'real' | 'con' | 'ink'

// One button system (Figma "Controls"): Oswald caps, 2px ink rule, the one hard shadow.
const VARIANTS: Record<Variant, string> = {
  primary: 'press border-2 border-ink bg-press text-white shadow-[var(--hard)] hover:bg-press-dark',
  secondary: 'press border-2 border-ink bg-sheet text-ink shadow-[var(--hard)] hover:bg-surface-2',
  ghost: 'text-ink hover:bg-ink/[0.06]',
  danger: 'press border-2 border-ink bg-press text-white shadow-[var(--hard)] hover:bg-press-dark',
  real: 'press border-2 border-ink bg-ink text-sheet shadow-[var(--hard)] hover:bg-[#2a2a2a]',
  con: 'press border-2 border-press bg-sheet text-press shadow-[var(--hard)] hover:bg-press/[0.06]',
  ink: 'press border-2 border-ink bg-ink text-sheet shadow-[var(--hard)] hover:bg-[#2a2a2a]',
}

export function btnClass(variant: Variant = 'secondary', size: 'sm' | 'md' | 'lg' = 'md') {
  const sizes = { sm: 'px-3 py-1.5 text-[13px]', md: 'px-4 py-2.5 text-[15px]', lg: 'px-6 py-3.5 text-lg' }
  return `caps inline-flex items-center justify-center gap-2 font-semibold disabled:opacity-45 disabled:shadow-none ${VARIANTS[variant]} ${sizes[size]}`
}

export function Button({
  variant = 'secondary',
  size = 'md',
  className = '',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'md' | 'lg' }) {
  return <button type="button" className={`${btnClass(variant, size)} ${className}`} {...rest} />
}

export function LinkButton({
  to,
  variant = 'secondary',
  size = 'md',
  className = '',
  children,
}: {
  to: string
  variant?: Variant
  size?: 'sm' | 'md' | 'lg'
  className?: string
  children: ReactNode
}) {
  return (
    <a href={href(to)} className={`${btnClass(variant, size)} ${className}`}>
      {children}
    </a>
  )
}

export function Loading({ label = 'Loading…', className = '' }: { label?: string; className?: string }) {
  return (
    <div className={`flex flex-col items-center justify-center gap-3 py-16 text-muted ${className}`}>
      <Spinner size={36} label={label} />
      <p className="text-sm">{label}</p>
    </div>
  )
}

export function CommandLine({ cmd }: { cmd: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="flex max-w-full items-stretch overflow-hidden border-2 border-ink bg-sheet text-left">
      <code className="min-w-0 flex-1 overflow-x-auto px-3 py-2 font-code text-[13px] whitespace-nowrap text-text thin-scroll">
        {cmd}
      </code>
      <button
        type="button"
        className="caps shrink-0 border-l-2 border-ink px-3 text-xs font-semibold text-ink hover:bg-ink hover:text-sheet"
        onClick={async () => {
          setCopied(await copyText(cmd))
          window.setTimeout(() => setCopied(false), 1600)
        }}
      >
        {copied ? 'Copied' : 'Copy'}
      </button>
    </div>
  )
}

/** Friendly error. When the backend isn't running, says how to start it. */
export function ErrorState({
  error,
  onRetry,
  title,
  className = '',
}: {
  error: unknown
  onRetry?: () => void
  title?: string
  className?: string
}) {
  const down = error instanceof ApiError ? error.backendDown : error instanceof TypeError
  const message = error instanceof Error ? error.message : String(error)
  return (
    <div role="alert" className={`panel mx-auto w-full max-w-lg p-6 text-center ${className}`}>
      <BrandIcon size={56} className="mx-auto mb-3" />
      {down ? (
        <>
          <h2 className="font-display text-2xl font-bold">The case room is dark.</h2>
          <p className="mt-2 text-sm text-muted">
            The game server isn’t answering. Start it from the repo root, then try again:
          </p>
          <div className="mt-4">
            <CommandLine cmd={BACKEND_START_CMD} />
          </div>
        </>
      ) : (
        <>
          <h2 className="font-display text-2xl font-bold">{title ?? 'Something went sideways.'}</h2>
          <p className="mt-2 text-sm text-muted">{message}</p>
        </>
      )}
      {onRetry && (
        <Button variant="primary" className="mt-5" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}

export function SectionLabel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <h2 className={`caps text-[12px] font-semibold tracking-[0.12em] text-muted ${className}`}>{children}</h2>
}

export function Chip({
  children,
  color = 'var(--muted)',
  className = '',
}: {
  children: ReactNode
  color?: string
  className?: string
}) {
  return (
    <span
      className={`caps inline-flex items-center gap-1 border-[1.5px] px-2 py-0.5 text-[12px] font-semibold ${className}`}
      style={{ borderColor: color, color, background: `color-mix(in srgb, ${color} 8%, var(--sheet))` }}
    >
      {children}
    </span>
  )
}

export function VisuallyHidden({ children }: { children: ReactNode }) {
  return <span className="sr-only">{children}</span>
}
