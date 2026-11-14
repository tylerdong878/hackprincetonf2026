import { useEffect, useRef, type ReactNode, type Ref } from 'react'
import { initials, relativeTime, trickLabel, watermark } from '../lib/format'
import type { ChartSpec, Post, VerdictChoice } from '../lib/types'
import { PostChart } from './PostChart'

// Feed cards are always light, like a real app (SPEC §3.1), so they use light-mode steps.
const CARD_REAL = '#1E7A4C'
const CARD_DOCTORED = '#B8322A'

function VerifiedBadge() {
  return (
    <svg viewBox="0 0 20 20" width="16" height="16" aria-label="Verified account" role="img" className="shrink-0">
      <circle cx="10" cy="10" r="9" fill="#2a78d6" />
      <path d="M6 10.4 8.6 13 14 7.4" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function LinkIcon() {
  return (
    <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true" className="shrink-0">
      <path
        d="M8.5 11.5a3 3 0 0 0 4.2 0l2.6-2.6a3 3 0 0 0-4.2-4.2l-.9.9M11.5 8.5a3 3 0 0 0-4.2 0l-2.6 2.6a3 3 0 0 0 4.2 4.2l.9-.9"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
    </svg>
  )
}

/** The feed post itself: a clean, generic social card with the in-game watermark. */
/** A Daily card's display style: the post's hint, else derived from its contents (CONTRACT §7.1). */
export function cardStyle(post: Post): 'headline' | 'quote' | 'chart' | 'stat' {
  if (post.card_style) return post.card_style
  if (post.chart) return 'chart'
  if (post.quote) return 'quote'
  if (/\d/.test(post.body) && post.body.length < 220) return 'stat'
  return 'headline'
}

export function FeedCard({
  post,
  caseNumber,
  doctoredStamp = false,
  renderChart,
  compact = false,
  size = 'feed',
  watermarkText,
}: {
  post: Post
  caseNumber: number
  doctoredStamp?: boolean
  renderChart?: (spec: ChartSpec) => ReactNode
  compact?: boolean
  /** 'daily' = one big card at a time: larger type for headlines and stats. */
  size?: 'feed' | 'daily'
  watermarkText?: string
}) {
  const a = post.author
  const style = size === 'daily' ? cardStyle(post) : null
  const bodyClass =
    style === 'headline' && post.body.length < 160
      ? 'text-[21px] leading-snug font-semibold tracking-[-0.01em]'
      : style === 'stat' || style === 'headline'
        ? 'text-[18px] leading-snug'
        : 'text-[15px] leading-[1.45]'
  return (
    <div className="feed-font @container relative overflow-hidden rounded-xl bg-feed-card text-[#0F1419] shadow-[0_1px_2px_rgba(0,0,0,0.25)]">
      <div className={compact ? 'p-3' : 'p-4'}>
        <header className="flex items-start gap-3">
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
            style={{ background: a.avatar_color || '#6B7280' }}
            aria-hidden="true"
          >
            {initials(a.name)}
          </div>
          <div className="min-w-0 flex-1 leading-tight">
            <div className="flex min-w-0 items-center gap-1">
              <span className="truncate text-[15px] font-bold">{a.name}</span>
              {a.verified && <VerifiedBadge />}
            </div>
            <div className="truncate text-[14px] text-[#536471]">
              {a.handle} · <time dateTime={post.posted_at}>{relativeTime(post.posted_at)}</time>
            </div>
          </div>
          <span className="text-lg leading-none text-[#8B98A5]" aria-hidden="true">
            ···
          </span>
        </header>

        {post.body && <p className={`mt-2.5 break-words whitespace-pre-line ${bodyClass}`}>{post.body}</p>}

        {post.quote && (
          <blockquote className="mt-3 rounded-lg border border-[#E1E4E8] bg-[#F7F9FA] px-3.5 py-3">
            <p className={size === 'daily' ? 'text-[17px] leading-snug' : 'text-[15px] leading-[1.45]'}>“{post.quote.text}”</p>
            {post.quote.speaker && <footer className="mt-1.5 text-[13px] text-[#536471]">— {post.quote.speaker}</footer>}
          </blockquote>
        )}

        {post.chart && (
          <div className="mt-3 rounded-lg border border-[#E1E4E8] p-3">
            {renderChart ? renderChart(post.chart) : <PostChart spec={post.chart} height={compact ? 170 : 200} compact={compact} />}
          </div>
        )}

        {post.source_label && (
          <div className="mt-2.5 flex items-center gap-1.5 text-[13px] text-[#536471]">
            <LinkIcon />
            <span className="truncate">{post.source_label}</span>
          </div>
        )}
      </div>

      <div className="watermark-strip border-t border-dashed border-[#D9D2C2] bg-[#F7F4EE] px-4 py-1.5 text-[10px] font-medium text-[#7D776A]">
        {watermarkText ?? watermark(caseNumber)}
      </div>

      {doctoredStamp && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center" aria-hidden="true">
          <span
            className="stamp stamp-thunk text-[min(3rem,11cqw)] mix-blend-multiply"
            style={{ color: CARD_DOCTORED, borderWidth: 5, opacity: 0.88, ['--stamp-rot' as string]: '-14deg', ['--stamp-rot-from' as string]: '-24deg' }}
          >
            Doctored
          </span>
        </div>
      )}
    </div>
  )
}

export interface PostCardProps {
  post: Post
  index: number
  caseNumber: number
  trickOptions: string[]
  verdict?: VerdictChoice
  selected?: boolean
  locked?: boolean
  pickerOpen?: boolean
  onPickerOpenChange?: (open: boolean) => void
  /** 'tap' = the card body was clicked/tapped (opens the bottom sheet on mobile). */
  onSelect?: (source: 'focus' | 'tap') => void
  onMark?: (doctored: boolean, trick: string | null) => void
  onInspect?: () => void
  ref?: Ref<HTMLElement>
}

/** A post in the investigation feed: case-file frame + feed card + verdict row. */
export function PostCard({
  post,
  index,
  caseNumber,
  trickOptions,
  verdict,
  selected = false,
  locked = false,
  pickerOpen = false,
  onPickerOpenChange,
  onSelect,
  onMark,
  onInspect,
  ref,
}: PostCardProps) {
  const isReal = verdict && !verdict.doctored
  const isDoctored = verdict?.doctored === true
  const doctoredBtn = useRef<HTMLButtonElement>(null)
  const pickerRef = useRef<HTMLDivElement>(null)
  const openChangeRef = useRef(onPickerOpenChange)
  openChangeRef.current = onPickerOpenChange

  // Close the trick picker on outside click; focus its current (or first) chip when it opens.
  useEffect(() => {
    if (!pickerOpen) return
    const first =
      pickerRef.current?.querySelector<HTMLButtonElement>('button[aria-pressed="true"]') ??
      pickerRef.current?.querySelector<HTMLButtonElement>('button')
    first?.focus({ preventScroll: true })
    const onDown = (e: PointerEvent) => {
      if (!pickerRef.current?.contains(e.target as Node) && !doctoredBtn.current?.contains(e.target as Node)) {
        openChangeRef.current?.(false)
      }
    }
    document.addEventListener('pointerdown', onDown)
    return () => document.removeEventListener('pointerdown', onDown)
  }, [pickerOpen])

  const frameBorder = isReal ? 'var(--real)' : isDoctored ? 'var(--doctored)' : 'color-mix(in srgb, var(--paper) 22%, transparent)'
  const n = index + 1

  return (
    <article
      ref={ref}
      tabIndex={0}
      data-post-id={post.id}
      aria-label={`Post ${n} of the feed, by ${post.author.name}${verdict ? `. Marked ${verdict.doctored ? 'doctored' : 'real'}` : ''}`}
      onFocus={() => onSelect?.('focus')}
      onClick={(e) => {
        const t = e.target as HTMLElement
        if (!t.closest('button, a')) onSelect?.('tap')
      }}
      className={`relative rounded-2xl border-2 p-2 pt-7 transition-[opacity,border-color,box-shadow] duration-200 focus-visible:outline-none ${
        locked ? 'opacity-70' : ''
      }`}
      style={{
        borderColor: frameBorder,
        background: 'color-mix(in srgb, var(--paper) 5%, transparent)',
        boxShadow: selected ? '0 0 0 3px var(--focus)' : undefined,
      }}
    >
      {/* case-file tab */}
      <div className="absolute top-1.5 left-3 flex items-center gap-2 text-[11px] font-bold tracking-[0.16em] text-muted uppercase">
        <span>Post {n}</span>
        {selected && <span className="text-focus normal-case tracking-normal">· inspecting</span>}
      </div>

      {/* verdict stamp, top right */}
      {verdict && (
        <span
          key={`${verdict.doctored}`}
          className="stamp stamp-thunk absolute top-1 right-3 z-10 bg-white text-[13px] shadow-sm"
          style={{ color: isReal ? CARD_REAL : CARD_DOCTORED, ['--stamp-rot' as string]: '4deg', ['--stamp-rot-from' as string]: '14deg' }}
          aria-hidden="true"
        >
          {isReal ? 'Real' : 'Doctored?'}
        </span>
      )}

      <FeedCard post={post} caseNumber={caseNumber} />

      {/* verdict row */}
      <div className="relative mt-2 flex flex-wrap items-center gap-2 px-0.5">
        {onInspect && (
          <button
            type="button"
            disabled={locked}
            onClick={onInspect}
            className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-sm font-semibold text-muted hover:bg-surface-2 hover:text-text"
            aria-label={`Open the evidence kit for post ${n}`}
          >
            <span aria-hidden="true">🔍</span> Evidence
          </button>
        )}

        {isDoctored && (
          <span
            className="rounded-full border px-2.5 py-0.5 text-xs font-semibold"
            style={{
              color: 'var(--doctored)',
              borderColor: 'color-mix(in srgb, var(--doctored) 55%, transparent)',
              background: 'color-mix(in srgb, var(--doctored) 12%, transparent)',
            }}
          >
            {verdict?.trick ? trickLabel(verdict.trick) : 'Trick: not sure'}
          </span>
        )}

        <div role="group" aria-label={`Verdict for post ${n}`} className="ml-auto inline-flex overflow-hidden rounded-xl border border-line bg-surface">
          <button
            type="button"
            disabled={locked}
            aria-pressed={!!isReal}
            onClick={() => {
              onPickerOpenChange?.(false)
              onMark?.(false, null)
            }}
            className={`inline-flex min-h-[40px] items-center gap-1.5 px-3.5 text-sm font-semibold transition ${
              isReal ? 'bg-real text-on-accent' : 'text-text hover:bg-surface-2'
            }`}
          >
            <span aria-hidden="true">✓</span> Real
          </button>
          <button
            ref={doctoredBtn}
            type="button"
            disabled={locked}
            aria-pressed={isDoctored}
            aria-expanded={pickerOpen}
            aria-haspopup="true"
            onClick={() => {
              if (!isDoctored) onMark?.(true, null)
              onPickerOpenChange?.(!pickerOpen)
            }}
            className={`inline-flex min-h-[40px] items-center gap-1.5 border-l border-line px-3.5 text-sm font-semibold transition ${
              isDoctored ? 'bg-doctored text-on-accent' : 'text-text hover:bg-surface-2'
            }`}
          >
            <span aria-hidden="true">✗</span> Doctored <span aria-hidden="true">▾</span>
          </button>
        </div>

        {pickerOpen && (
          <div
            ref={pickerRef}
            role="group"
            aria-label="Name the trick (optional)"
            onKeyDown={(e) => {
              if (e.key === 'Escape') {
                e.stopPropagation()
                onPickerOpenChange?.(false)
                doctoredBtn.current?.focus()
              }
            }}
            className="rise-in absolute top-full right-0 z-30 mt-2 w-[min(100%,320px)] rounded-xl border border-line bg-surface p-3 shadow-2xl"
          >
            <p className="mb-2 text-xs font-semibold text-muted">Which trick? Naming it right earns +50.</p>
            <div className="flex flex-wrap gap-2">
              {trickOptions.map((t, i) => (
                <button
                  key={t}
                  type="button"
                  aria-pressed={verdict?.trick === t}
                  onClick={() => {
                    onMark?.(true, t)
                    onPickerOpenChange?.(false)
                  }}
                  className={`rounded-full border px-3 py-1.5 text-sm font-semibold transition ${
                    verdict?.trick === t ? 'border-doctored bg-doctored text-on-accent' : 'border-line hover:border-doctored'
                  }`}
                >
                  {i < 3 && <kbd className="mr-1.5 font-mono text-[11px] opacity-70">{i + 1}</kbd>}
                  {trickLabel(t)}
                </button>
              ))}
              <button
                type="button"
                aria-pressed={isDoctored && !verdict?.trick}
                onClick={() => {
                  onMark?.(true, null)
                  onPickerOpenChange?.(false)
                }}
                className={`rounded-full border px-3 py-1.5 text-sm font-semibold transition ${
                  isDoctored && !verdict?.trick ? 'border-muted bg-surface-2' : 'border-line hover:border-muted'
                }`}
              >
                Not sure
              </button>
            </div>
          </div>
        )}
      </div>
    </article>
  )
}
