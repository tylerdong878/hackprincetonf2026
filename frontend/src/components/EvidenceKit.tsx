import { useEffect, useRef, type ReactNode, type Ref } from 'react'
import { formatNumber } from '../lib/format'
import type { AccountEvidence, AnyEvidence, DataEvidence, GameCase, Post, SourceEvidence, ToolId } from '../lib/types'
import { Spinner } from './Art'
import { ClueToken, IconAccount, IconData, IconLens, IconSource, IconVerified } from './Icon'
import { PostChart } from './PostChart'
import { SectionLabel } from './ui'

export const TOOLS: { id: ToolId; icon: ReactNode; label: string; blurb: string }[] = [
  { id: 'source', icon: <IconSource size={20} />, label: 'Open source', blurb: 'The full article, with the quoted passage in context.' },
  { id: 'data', icon: <IconData size={20} />, label: 'Check the data', blurb: 'The raw numbers, plus an honest chart.' },
  { id: 'account', icon: <IconAccount size={20} />, label: 'Who posted this?', blurb: 'Account age, followers, recent posts.' },
]

export type ToolRowState = 'ready' | 'open' | 'na' | 'out'

/**
 * One evidence component (Figma "Evidence tool"): the same row everywhere.
 * ready = paper row, ink rule, hard shadow, "-1" + a clue token; open = black row tagged OPEN;
 * na (nothing to check) / out (no clues left) = dashed row with a dash.
 */
export function ToolRow({
  icon,
  label,
  sub,
  state,
  busy = false,
  disabled = false,
  title,
  describedById,
  onClick,
  className = '',
  compact = false,
}: {
  icon: ReactNode
  label: ReactNode
  sub?: ReactNode
  state: ToolRowState
  busy?: boolean
  disabled?: boolean
  title?: string
  describedById?: string
  onClick?: () => void
  className?: string
  compact?: boolean
}) {
  const look =
    state === 'open'
      ? 'border-2 border-ink bg-ink text-sheet'
      : state === 'ready'
        ? 'press border-2 border-ink bg-sheet text-ink shadow-[var(--hard)] hover:bg-surface-2'
        : 'border-[1.5px] border-dashed border-[#B9AE99] bg-transparent text-muted'
  return (
    <button
      type="button"
      disabled={disabled}
      title={title}
      aria-describedby={describedById}
      onClick={onClick}
      className={`flex w-full items-center gap-3 text-left ${compact ? 'px-3 py-2' : 'px-3.5 py-2.5'} ${look} disabled:cursor-not-allowed ${className}`}
    >
      <span className={`flex w-6 justify-center ${state === 'open' ? 'text-sheet' : state === 'ready' ? 'text-ink' : 'text-[#8C8270]'}`}>{icon}</span>
      <span className="min-w-0 flex-1">
        <span className="block text-[15.5px] leading-tight font-bold">{label}</span>
        {sub && (
          <span id={describedById} className={`block truncate text-[12.5px] ${state === 'open' ? 'text-[#C9C2B5]' : 'text-muted'}`}>
            {sub}
          </span>
        )}
      </span>
      <span className="flex shrink-0 items-center gap-1.5">
        {busy ? (
          <Spinner size={18} label="Opening evidence" />
        ) : state === 'open' ? (
          <span className="caps text-[12px] font-semibold tracking-[0.08em] text-press-soft">Open</span>
        ) : state === 'ready' ? (
          <>
            <span className="num text-[15px] font-semibold">−1</span>
            <ClueToken size={22} />
          </>
        ) : (
          <span className="text-[15px] font-bold">—</span>
        )}
      </span>
    </button>
  )
}

/** The server may send the tool's object directly or wrapped as { [tool]: {...} }. */
export function normalizeEvidence(tool: ToolId, ev: unknown): AnyEvidence {
  if (ev && typeof ev === 'object' && tool in (ev as object)) {
    const inner = (ev as Record<string, unknown>)[tool]
    if (inner && typeof inner === 'object') return inner as AnyEvidence
  }
  return (ev ?? {}) as AnyEvidence
}

export interface KitNotice {
  postId: string
  tool: ToolId
  kind: 'out' | 'error'
  message: string
}

export function ClueTokens({ left, total, className = '' }: { left: number; total: number; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 ${className}`} role="img" aria-label={`${left} of ${total} clue tokens left`}>
      {Array.from({ length: total }, (_, i) => (
        <ClueToken key={i} spent={i >= left} size={22} />
      ))}
      <span className="num ml-1.5 text-[14px] font-semibold text-ink" aria-hidden="true">
        {left}/{total}
      </span>
    </span>
  )
}

export function EvidenceKit({
  game,
  post,
  postIndex,
  cluesLeft,
  opened,
  loadingTool,
  notice,
  locked,
  onUse,
  headingRef,
}: {
  game: GameCase
  post: Post | null
  postIndex: number
  cluesLeft: number
  opened: Partial<Record<ToolId, AnyEvidence>>
  loadingTool: ToolId | null
  notice: KitNotice | null
  locked: boolean
  onUse: (tool: ToolId) => void
  headingRef?: Ref<HTMLHeadingElement>
}) {
  const evidenceTop = useRef<HTMLDivElement>(null)
  const openedTools = TOOLS.filter((t) => opened[t.id])

  // When new evidence arrives, bring it into view inside the panel.
  const count = openedTools.length
  useEffect(() => {
    if (count) evidenceTop.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [count])

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <h2 ref={headingRef} tabIndex={-1} className="caps text-xl font-bold focus-visible:outline-none">
          Evidence Kit
        </h2>
        <ClueTokens left={cluesLeft} total={game.clue_budget} />
      </div>

      {!post ? (
        <div className="border-[1.5px] border-dashed border-[#B9AE99] p-6 text-center text-sm text-muted">
          <p className="flex justify-center text-ink" aria-hidden="true">
            <IconLens size={28} />
          </p>
          <p className="mt-2">Select a post, then pick a tool.</p>
          <p className="mt-1 text-xs">Each new check costs one clue token. Unused tokens are worth +20 each.</p>
        </div>
      ) : (
        <>
          <p className="text-sm text-muted">
            <span className="font-semibold text-text">Post {postIndex + 1}</span> selected · {post.author.name}
          </p>
          <ul className="flex flex-col gap-2">
            {TOOLS.map((t) => {
              const has = post.tools?.includes(t.id)
              const isOpen = !!opened[t.id]
              const busy = loadingTool === t.id
              const outOfClues = cluesLeft <= 0 && !isOpen
              const disabled = locked || !has || busy || outOfClues
              const why = !has
                ? 'Nothing to check with this tool for this post.'
                : outOfClues
                  ? 'You’re out of clue tokens. Evidence you already opened stays free to re-read.'
                  : isOpen
                    ? 'Already opened: free to re-read.'
                    : `${t.blurb} Costs one clue token.`
              return (
                <li key={t.id}>
                  <ToolRow
                    icon={t.icon}
                    label={t.label}
                    sub={!has ? 'Nothing to check here' : outOfClues ? 'Out of clues' : t.blurb}
                    state={isOpen ? 'open' : !has ? 'na' : outOfClues ? 'out' : 'ready'}
                    busy={busy}
                    disabled={disabled}
                    title={why}
                    describedById={`tool-why-${t.id}`}
                    onClick={() => onUse(t.id)}
                  />
                </li>
              )
            })}
          </ul>

          {notice && notice.postId === post.id && (
            <div
              role="alert"
              className="border-2 px-3.5 py-2.5 text-sm"
              style={{
                borderColor: notice.kind === 'out' ? 'var(--alarm)' : 'var(--doctored)',
                background: `color-mix(in srgb, ${notice.kind === 'out' ? 'var(--alarm)' : 'var(--doctored)'} 10%, var(--sheet))`,
              }}
            >
              {notice.message}
            </div>
          )}

          <div ref={evidenceTop} />
          {openedTools.length === 0 ? (
            <p className="text-xs text-muted">Opened evidence stays here for this post, free to re-read.</p>
          ) : (
            openedTools.map((t) => (
              <section key={t.id} className="fade-in" aria-label={`${t.label} evidence for post ${postIndex + 1}`}>
                <SectionLabel className="mb-2 flex items-center gap-1.5 !text-press">
                  {t.label}
                </SectionLabel>
                {t.id === 'source' && <SourceView ev={opened.source as SourceEvidence} />}
                {t.id === 'data' && <DataView ev={opened.data as DataEvidence} />}
                {t.id === 'account' && <AccountView ev={opened.account as AccountEvidence} />}
              </section>
            ))
          )}
        </>
      )}
    </div>
  )
}

function ExternalLink({ url, children }: { url?: string; children: ReactNode }) {
  if (!url) return null
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="break-all text-[#1F5FD1] underline underline-offset-2 hover:no-underline">
      {children}
    </a>
  )
}

export function SourceView({ ev }: { ev: SourceEvidence }) {
  return (
    <article className="border-2 border-ink bg-white p-4 text-[15px] leading-relaxed text-[#1B1B1F]">
      <header className="dateline mb-2 flex flex-wrap items-baseline justify-between gap-x-3 !text-[11.5px]">
        <span className="font-semibold text-[#1B1B1F]">{ev.outlet}</span>
        <span>{ev.date}</span>
      </header>
      <p>
        {ev.before && <span className="text-[#4A4A55]">{ev.before} </span>}
        {ev.highlight && <mark className="bg-highlight px-0.5 text-[#1B1B1F]">{ev.highlight}</mark>}
        {ev.after && <span className="text-[#4A4A55]"> {ev.after}</span>}
      </p>
      {ev.url && (
        <p className="mt-3 text-xs">
          <ExternalLink url={ev.url}>Read the original ↗</ExternalLink>
        </p>
      )}
    </article>
  )
}

export function DataView({ ev }: { ev: DataEvidence }) {
  const rows = ev.table ?? []
  return (
    <div className="flex flex-col gap-3">
      {ev.note && <p className="border-l-4 border-ink bg-sheet px-3 py-2 text-sm">{ev.note}</p>}
      {ev.honest_chart && (
        <div className="border-2 border-ink bg-white p-3">
          <PostChart spec={ev.honest_chart} height={180} compact />
          <p className="mt-1 text-[11px] text-[#5E5E68]">Honest view: zero baseline, full date range.</p>
        </div>
      )}
      {rows.length > 0 && (
        <div className="max-h-64 overflow-auto border-2 border-ink bg-sheet thin-scroll">
          <table className="w-full border-collapse text-[14px]">
            <caption className="sr-only">{ev.title}</caption>
            <thead className="caps sticky top-0 border-b-2 border-ink bg-sheet text-left text-[12px] tracking-[0.08em] text-muted">
              <tr>
                <th scope="col" className="px-3 py-2 font-semibold">
                  Period
                </th>
                <th scope="col" className="px-3 py-2 text-right font-semibold">
                  {ev.unit ?? 'Value'}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.label} className="border-t border-[#CFC6B4]">
                  <td className="px-3 py-1.5">{r.label}</td>
                  <td className="px-3 py-1.5 text-right font-bold tabular-nums">{formatNumber(r.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-xs text-muted">
        {ev.title}
        {ev.url && (
          <>
            {' · '}
            <a href={ev.url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-text">
              data source ↗
            </a>
          </>
        )}
      </p>
    </div>
  )
}

export function AccountView({ ev }: { ev: AccountEvidence }) {
  return (
    <div className="feed-font rounded-[10px] border border-[#CFD4DA] bg-white p-4 text-[14px] text-[#1B1B1F]">
      <div className="flex items-baseline gap-1.5">
        <span className="font-bold">{ev.name}</span>
        {ev.verified && (
          <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-[#2a78d6]">
            <IconVerified size={13} /> verified
          </span>
        )}
      </div>
      <div className="text-[13px] text-[#536471]">{ev.handle}</div>
      {ev.bio && <p className="mt-2">{ev.bio}</p>}
      <dl className="mt-3 grid grid-cols-2 gap-2 text-[13px]">
        <div className="rounded-lg bg-[#F4F5F7] px-2.5 py-1.5">
          <dt className="text-[11px] text-[#5E5E68]">Joined</dt>
          <dd className="font-semibold">{ev.created ?? 'Long-standing account'}</dd>
        </div>
        <div className="rounded-lg bg-[#F4F5F7] px-2.5 py-1.5">
          <dt className="text-[11px] text-[#5E5E68]">Followers</dt>
          <dd className="font-mono font-semibold">{ev.followers != null ? formatNumber(ev.followers, 0) : '—'}</dd>
        </div>
      </dl>
      {ev.recent_posts && ev.recent_posts.length > 0 && (
        <div className="mt-3">
          <p className="text-[11px] font-semibold tracking-wide text-[#5E5E68] uppercase">Recent posts</p>
          <ul className="mt-1 flex flex-col gap-1.5">
            {ev.recent_posts.map((p, i) => (
              <li key={i} className="rounded-lg border border-[#E1E4E8] px-2.5 py-1.5 text-[13px]">
                {p}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
