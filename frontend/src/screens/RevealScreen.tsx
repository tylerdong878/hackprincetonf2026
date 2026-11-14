import { useEffect, useMemo, useState } from 'react'
import { ConMascot } from '../components/Art'
import { ConBubble } from '../components/ConBubble'
import { FeedCard } from '../components/PostCard'
import { DiffView, OutcomeBadge } from '../components/Reveal'
import { Button, LinkButton } from '../components/ui'
import { caseNo, outcomeStyle, trickLabel } from '../lib/format'
import { copyText, useReducedMotion, useTween } from '../lib/hooks'
import type { GameCase, Post, PostResult, VerdictChoice, VerdictResponse } from '../lib/types'
import { NextCaseError, useNextCase } from './common'

const REVEAL_GAP_MS = 600

function ConSays({ text, typewriter = true }: { text: string; typewriter?: boolean }) {
  return (
    <div className="flex items-end gap-2.5">
      <ConMascot size={40} className="shrink-0" />
      <ConBubble text={text} size="sm" typewriter={typewriter} speed={16} className="min-w-0 flex-1" />
    </div>
  )
}

function PostReveal({
  post,
  index,
  result,
  verdict,
  caseNumber,
}: {
  post: Post
  index: number
  result: PostResult
  verdict?: VerdictChoice
  caseNumber: number
}) {
  const s = outcomeStyle(result.outcome)
  const you = verdict ? (verdict.doctored ? `Doctored${verdict.trick ? ` (${trickLabel(verdict.trick)})` : ''}` : 'Real') : '—'
  const pts = result.points ?? 0

  return (
    <article
      className="rise-in rounded-2xl border-2 bg-surface p-4 sm:p-5"
      style={{ borderColor: `color-mix(in srgb, ${s.color} 45%, transparent)` }}
      aria-labelledby={`reveal-${post.id}`}
    >
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h3 id={`reveal-${post.id}`} className="text-[11px] font-bold tracking-[0.16em] text-muted uppercase">
          Post {index + 1}
        </h3>
        <OutcomeBadge outcome={result.outcome} />
        <span className="text-sm font-semibold">
          {result.doctored ? (
            <>Doctored · {trickLabel(result.trick)}</>
          ) : result.suspicious_real ? (
            <>Real · built to look fake</>
          ) : (
            <>Real</>
          )}
        </span>
        <span
          className="num ml-auto text-lg font-bold"
          style={{ color: pts > 0 ? 'var(--real)' : pts < 0 ? 'var(--doctored)' : 'var(--muted)' }}
        >
          {pts > 0 ? `+${pts}` : pts < 0 ? `−${Math.abs(pts)}` : '0'}
        </span>
      </header>
      <p className="mt-1 text-sm text-muted">
        {s.blurb} You said: <span className="font-semibold text-text">{you}</span>
        {result.trick_named_correctly && <span className="font-semibold text-real"> · named the trick (+50)</span>}
      </p>

      {result.doctored && result.diff ? (
        <div className="mt-4">
          <DiffView post={post} caseNumber={caseNumber} diff={result.diff} />
        </div>
      ) : (
        <div className={`mt-4 ${result.doctored ? '' : 'grid gap-4 md:grid-cols-2'}`}>
          <FeedCard post={post} caseNumber={caseNumber} compact doctoredStamp={result.doctored} />
          {!result.doctored && result.explanation && (
            <div className="flex flex-col justify-center gap-2 rounded-xl border border-line bg-surface-2 p-4 text-[15px]">
              <p className="text-[11px] font-bold tracking-[0.16em] text-real uppercase">✓ Checks out</p>
              <p>{result.explanation}</p>
            </div>
          )}
        </div>
      )}

      {result.doctored && (result.tell || result.explanation) && (
        <div className="mt-4 rounded-xl border-l-4 border-doctored bg-surface-2 px-4 py-3 text-[15px]">
          {result.tell && (
            <p>
              <b className="font-display tracking-wide">The tell:</b> {result.tell}
            </p>
          )}
          {result.explanation && <p className="mt-1.5 text-sm text-muted">{result.explanation}</p>}
        </div>
      )}

      {result.con_line && (
        <div className="mt-4">
          <ConSays text={result.con_line} />
        </div>
      )}
    </article>
  )
}

export function RevealScreen({ game, result, verdicts }: { game: GameCase; result: VerdictResponse; verdicts: Record<string, VerdictChoice> }) {
  const reduced = useReducedMotion()
  const [shown, setShown] = useState(reduced ? game.posts.length : 0)
  const [copied, setCopied] = useState<'idle' | 'ok' | 'fail'>('idle')
  const next = useNextCase()
  const score = Math.round(useTween(0, result.score ?? 0, 1, 900, reduced))

  const byId = useMemo(() => new Map(result.results.map((r) => [r.post_id, r])), [result.results])
  const ordered = game.posts.filter((p) => byId.has(p.id))
  const total = ordered.length

  useEffect(() => {
    if (shown >= total) return
    const id = window.setTimeout(() => setShown((n) => n + 1), shown === 0 ? 350 : REVEAL_GAP_MS)
    return () => window.clearTimeout(id)
  }, [shown, total])

  const grid = ordered.map((p) => outcomeStyle(byId.get(p.id)!.outcome).emoji).join('')
  const shareText = `Grain of Salt · Case ${caseNo(game.number)}\n${grid}\nDetective rating ${result.rating} (${result.rank})`
  const learnTrick =
    result.results.find((r) => r.doctored && r.outcome === 'fooled')?.trick ?? result.results.find((r) => r.doctored)?.trick ?? null
  const counts = result.results.reduce<Record<string, number>>((acc, r) => ({ ...acc, [r.outcome]: (acc[r.outcome] ?? 0) + 1 }), {})

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 pt-6 pb-20">
      {/* Case closed header */}
      <section className="paper-texture relative overflow-hidden rounded-2xl p-5 sm:p-7" aria-labelledby="closed-title">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-4">
          <h1 id="closed-title" className="stamp stamp-thunk text-2xl text-[#B8322A] sm:text-3xl" style={{ ['--stamp-rot' as string]: '-4deg' }}>
            Case closed
          </h1>
          <dl className="flex flex-1 flex-wrap items-end gap-x-8 gap-y-3">
            <div>
              <dt className="text-xs font-semibold tracking-wide text-[#6B5E45] uppercase">Score</dt>
              <dd className="num text-3xl font-bold">{score}</dd>
            </div>
            {result.clue_bonus != null && (
              <div>
                <dt className="text-xs font-semibold tracking-wide text-[#6B5E45] uppercase">Clue bonus</dt>
                <dd className="num text-xl font-bold">+{result.clue_bonus}</dd>
              </div>
            )}
            <div>
              <dt className="text-xs font-semibold tracking-wide text-[#6B5E45] uppercase">Detective rating</dt>
              <dd className="num text-3xl font-bold">
                {result.rating}{' '}
                <span className="font-display text-lg font-semibold text-[#6D3FD8]">{result.rank}</span>
              </dd>
            </div>
          </dl>
        </div>
        <p className="mt-4 text-sm text-[#4B4232]">
          {(['caught', 'trusted', 'fooled', 'false_alarm'] as const)
            .filter((o) => counts[o])
            .map((o) => `${counts[o]} ${outcomeStyle(o).word.toLowerCase()}`)
            .join(' · ')}
          <span className="sr-only">. Share grid: {grid}</span>
        </p>
      </section>

      {result.clean_case && (
        <section className="rise-in mt-6 overflow-hidden rounded-2xl border-2 border-con bg-con/10 p-5 sm:p-6" aria-label="Clean case">
          <div className="flex flex-col items-center gap-5 sm:flex-row">
            <ConMascot size={120} className="shrink-0" />
            <div className="min-w-0 flex-1 text-center sm:text-left">
              <p className="font-con text-xl tracking-wider text-con uppercase sm:text-2xl">A clean case</p>
              <p className="mt-1 text-sm text-muted">Every post in this case was real. Nothing was doctored.</p>
              <ConBubble
                className="mt-3"
                text={result.con_line_clean || 'Nothing to catch today. Getting you to doubt everything is my favorite trick of all.'}
              />
            </div>
          </div>
        </section>
      )}

      <ol className="mt-6 flex flex-col gap-5" aria-label="Post by post">
        {ordered.map((p, i) => (
          <li key={p.id}>
            {i < shown ? (
              <PostReveal post={p} index={i} result={byId.get(p.id)!} verdict={verdicts[p.id]} caseNumber={game.number} />
            ) : (
              <div className="rounded-2xl border-2 border-dashed border-line p-5 text-sm text-muted" aria-hidden="true">
                Post {i + 1} · opening the file…
              </div>
            )}
          </li>
        ))}
      </ol>

      {shown >= total && (
        <section className="rise-in mt-8 flex flex-col gap-5" aria-label="What's next">
          {result.adaptation_message && <ConSays text={result.adaptation_message} />}

          <div className="flex flex-wrap gap-2">
            <Button variant="primary" onClick={next.open} disabled={next.loading}>
              {next.loading ? 'Finding the next case…' : 'Next case →'}
            </Button>
            <LinkButton to={learnTrick ? `/casebook/${learnTrick}` : '/casebook'}>
              Learn: {learnTrick ? trickLabel(learnTrick) : 'the tricks'}
            </LinkButton>
            <Button
              onClick={async () => {
                setCopied((await copyText(shareText)) ? 'ok' : 'fail')
                window.setTimeout(() => setCopied('idle'), 2400)
              }}
              aria-describedby="share-note"
            >
              Share <span className="tracking-[0.15em]">{grid}</span>
            </Button>
            <LinkButton to="/dossier" variant="ghost">
              Dossier
            </LinkButton>
            <LinkButton to="/" variant="ghost">
              Home
            </LinkButton>
          </div>
          <p id="share-note" className="text-xs text-muted" role="status">
            {copied === 'ok'
              ? 'Copied! Only the grid, case number and rating, never the doctored posts.'
              : copied === 'fail'
                ? 'Couldn’t reach the clipboard. Copy this instead: ' + shareText.replace(/\n/g, ' · ')
                : 'Sharing copies only the emoji grid, case number and rating, never the doctored posts.'}
          </p>
          <NextCaseError error={next.error} onRetry={next.open} />
        </section>
      )}
    </main>
  )
}
