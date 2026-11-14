import { useState, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { ApiError, BACKEND_START_CMD } from '../lib/api'
import { copyText } from '../lib/hooks'
import { href } from '../lib/router'
import { BrandIcon, Spinner } from './Art'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'real' | 'con'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-con text-on-accent hover:brightness-110 shadow-[0_6px_20px_-8px_var(--con)]',
  secondary: 'bg-surface-2 text-text border border-line hover:border-muted',
  ghost: 'text-text hover:bg-surface-2',
  danger: 'bg-doctored text-on-accent hover:brightness-110',
  real: 'bg-real text-on-accent hover:brightness-110',
  con: 'border border-con/60 text-text hover:bg-con/15',
}

export function btnClass(variant: Variant = 'secondary', size: 'sm' | 'md' | 'lg' = 'md') {
  const sizes = { sm: 'px-3 py-1.5 text-sm', md: 'px-4 py-2.5 text-[15px]', lg: 'px-6 py-3.5 text-lg' }
  return `inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition disabled:opacity-45 disabled:hover:brightness-100 ${VARIANTS[variant]} ${sizes[size]}`
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
    <div className="flex max-w-full items-stretch overflow-hidden rounded-lg border border-line bg-bg text-left">
      <code className="min-w-0 flex-1 overflow-x-auto px-3 py-2 font-mono text-[13px] whitespace-nowrap text-text thin-scroll">
        {cmd}
      </code>
      <button
        type="button"
        className="shrink-0 border-l border-line px-3 text-xs font-semibold text-muted hover:text-text"
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
    <div role="alert" className={`mx-auto w-full max-w-lg rounded-2xl border border-line bg-surface p-6 text-center ${className}`}>
      <BrandIcon size={56} className="mx-auto mb-3" />
      {down ? (
        <>
          <h2 className="font-display text-xl font-semibold">The case room is dark.</h2>
          <p className="mt-2 text-sm text-muted">
            The game server isn’t answering. Start it from the repo root, then try again:
          </p>
          <div className="mt-4">
            <CommandLine cmd={BACKEND_START_CMD} />
          </div>
        </>
      ) : (
        <>
          <h2 className="font-display text-xl font-semibold">{title ?? 'Something went sideways.'}</h2>
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
  return <h2 className={`text-[11px] font-bold tracking-[0.18em] text-muted uppercase ${className}`}>{children}</h2>
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
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${className}`}
      style={{ borderColor: `color-mix(in srgb, ${color} 55%, transparent)`, color, background: `color-mix(in srgb, ${color} 12%, transparent)` }}
    >
      {children}
    </span>
  )
}

export function VisuallyHidden({ children }: { children: ReactNode }) {
  return <span className="sr-only">{children}</span>
}
