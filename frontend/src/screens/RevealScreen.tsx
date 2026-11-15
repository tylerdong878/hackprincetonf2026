import { useEffect, useMemo, useState } from 'react'
import { ConMascot } from '../components/Art'
import { ConBubble } from '../components/ConBubble'
import { IconArrow, IconBook, IconCheck, IconShare, OutcomeSquare } from '../components/Icon'
import { FeedCard } from '../components/PostCard'
import { DiffView, OutcomeBadge } from '../components/Reveal'
import { Button, LinkButton } from '../components/ui'
import { caseNo, outcomeStyle, trickLabel } from '../lib/format'
import { copyText, useReducedMotion, useTween } from '../lib/hooks'
import type { GameCase, Post, PostResult, VerdictChoice, VerdictResponse } from '../lib/types'
import { NextCaseError, useNextCase } from './common'

const REVEAL_GAP_MS = 600

const LABEL = 'caps text-[12px] font-semibold tracking-[0.1em] text-muted'

function ConSays({ text, typewriter = true }: { text: string; typewriter?: boolean }) {
  return <ConBubble text={text} size="md" typewriter={typewriter} speed={16} className="w-full" />
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
  const tell = result.doctored && (result.tell || result.explanation)

  return (
    <article className="rise-in border-t-[1.5px] border-ink pt-4 pb-8" aria-labelledby={`reveal-${post.id}`}>
      <h3 id={`reveal-${post.id}`} className={`${LABEL} !text-ink`}>
        Post {index + 1}
      </h3>
      <header className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-2">
        <OutcomeBadge outcome={result.outcome} size="lg" />
        <span className="font-head text-[22px] leading-tight sm:text-[26px]">
          {result.doctored ? (
            <>Doctored · {trickLabel(result.trick)}</>
          ) : result.suspicious_real ? (
            <>Real · built to look fake</>
          ) : (
            <>Real</>
          )}
        </span>
        <span
          className="num ml-auto text-[30px] leading-none font-bold sm:text-[34px]"
          style={{ color: pts > 0 ? 'var(--ink)' : pts < 0 ? 'var(--ochre)' : 'var(--muted)' }}
        >
          {pts > 0 ? `+${pts}` : pts < 0 ? `−${Math.abs(pts)}` : '0'}
        </span>
      </header>
      <p className="mt-2 text-[15.5px]">
        {s.blurb} You said: <span className="font-bold">{you}</span>
        {result.trick_named_correctly && <span className="font-bold"> · named the trick (+50)</span>}
      </p>

      {result.doctored && result.diff ? (
        <div className="mt-5">
          <DiffView post={post} caseNumber={caseNumber} diff={result.diff} />
        </div>
      ) : (
        <div className={`mt-5 ${result.doctored ? '' : 'grid items-start gap-6 md:grid-cols-2'}`}>
          <FeedCard post={post} caseNumber={caseNumber} compact doctoredStamp={result.doctored} />
          {!result.doctored && (result.explanation || result.con_line) && (
            <div className="flex flex-col gap-4">
              {result.explanation && (
                <div className="border-2 border-ink bg-sheet p-5 text-[16px] leading-relaxed">
                  <p className="caps mb-1.5 inline-flex items-center gap-1.5 text-[14px] font-bold tracking-[0.06em]">
                    <IconCheck size={16} strokeWidth={2.6} /> Checks out
                  </p>
                  <p>{result.explanation}</p>
                </div>
              )}
              {result.con_line && <ConSays text={result.con_line} />}
            </div>
          )}
        </div>
      )}

      {result.doctored && (tell || result.con_line) && (
        <div className="mt-6 grid items-start gap-6 md:grid-cols-2">
          {tell ? (
            <div className="border-l-[6px] border-press py-1 pl-5 text-[16.5px] leading-snug">
              {result.tell && (
                <p className="font-bold">
                  <span className="font-head font-semibold tracking-wide">The tell:</span> {result.tell}
                </p>
              )}
              {result.explanation && <p className="mt-2 text-[15px] text-muted">{result.explanation}</p>}
            </div>
          ) : (
            <span aria-hidden="true" />
          )}
          {result.con_line && <ConSays text={result.con_line} />}
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
    <main className="mx-auto w-full max-w-[1368px] flex-1 px-4 pt-8 pb-20 sm:px-6">
      {/* Case closed: the extra-edition masthead with the score box */}
      <section aria-labelledby="closed-title">
        <div className="grid items-end gap-x-10 gap-y-6 lg:grid-cols-[minmax(0,1fr)_auto]">
          <div className="min-w-0">
            <h1
              id="closed-title"
              className="caps stamp-thunk text-[64px] leading-[0.9] font-bold sm:text-[104px] lg:text-[120px]"
              style={{ ['--stamp-rot' as string]: '0deg', ['--stamp-rot-from' as string]: '-4deg' }}
            >
              Case closed
            </h1>
            <p className="mt-2 text-[18px] italic sm:text-[19px]">
              {(['caught', 'trusted', 'fooled', 'false_alarm'] as const)
                .filter((o) => counts[o])
                .map((o) => `${counts[o]} ${outcomeStyle(o).word.toLowerCase()}`)
                .join(' · ')}
              <span className="sr-only">. Share grid: {grid}</span>
            </p>
          </div>
          <dl className="panel grid auto-cols-fr grid-flow-col self-start text-center lg:mb-3 lg:min-w-[420px]">
            <div className="flex flex-col items-center px-5 py-5">
              <dt className={LABEL}>Score</dt>
              <dd className="num mt-2 text-[44px] leading-none font-bold sm:text-[52px]">{score}</dd>
            </div>
            {result.clue_bonus != null && (
              <div className="flex flex-col items-center border-l-[1.5px] border-ink px-5 py-5">
                <dt className={LABEL}>Clue bonus</dt>
                <dd className="num mt-2 text-[44px] leading-none font-bold sm:text-[52px]">+{result.clue_bonus}</dd>
              </div>
            )}
            <div className="flex flex-col items-center border-l-[1.5px] border-ink px-5 py-5">
              <dt className={LABEL}>Detective rating</dt>
              <dd className="mt-2 flex flex-col items-center">
                <span className="num text-[44px] leading-none font-bold text-press sm:text-[52px]">{result.rating}</span>
                <span className="mt-1 text-[17px] italic">{result.rank}</span>
              </dd>
            </div>
          </dl>
        </div>
        <div className="double-rule mt-5" aria-hidden="true" />
      </section>

      {result.clean_case && (
        <section className="rise-in mt-8 border-2 border-press bg-sheet p-5 shadow-[var(--hard)] sm:p-6" aria-label="Clean case">
          <div className="flex flex-col items-center gap-5 sm:flex-row">
            <ConMascot size={120} shape="circle" className="shrink-0" />
            <div className="min-w-0 flex-1 text-center sm:text-left">
              <p className="caps text-2xl font-bold tracking-[0.04em] text-press sm:text-3xl">A clean case</p>
              <p className="mt-1 text-[15px] text-muted italic">Every post in this case was real. Nothing was doctored.</p>
              <ConBubble
                className="mt-3"
                text={result.con_line_clean || 'Nothing to catch today. Getting you to doubt everything is my favorite trick of all.'}
              />
            </div>
          </div>
        </section>
      )}

      <ol className="mt-6 flex flex-col" aria-label="Post by post">
        {ordered.map((p, i) => (
          <li key={p.id}>
            {i < shown ? (
              <PostReveal post={p} index={i} result={byId.get(p.id)!} verdict={verdicts[p.id]} caseNumber={game.number} />
            ) : (
              <div className="mb-6 border-[1.5px] border-dashed border-ink px-5 py-5 text-[15px] text-muted italic" aria-hidden="true">
                Post {i + 1} · opening the file…
              </div>
            )}
          </li>
        ))}
      </ol>

      {shown >= total && (
        <section className="rise-in flex flex-col gap-6" aria-label="What's next">
          <div className="double-rule" aria-hidden="true" />
          {result.adaptation_message && (
            <div className="flex items-center gap-5 bg-press px-5 py-5 text-white sm:px-6">
              <ConMascot size={92} shape="circle" className="hidden shrink-0 sm:inline-block" />
              <div className="min-w-0 flex-1">
                <ConBubble
                  text={result.adaptation_message}
                  size="lg"
                  speed={16}
                  className="!border-l-0 !bg-transparent !p-0 !text-white !shadow-none [&_span.caps]:!text-white/85 [&>p]:text-[22px] sm:[&>p]:text-[26px]"
                />
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-4">
            <Button variant="primary" size="lg" onClick={next.open} disabled={next.loading}>
              <IconArrow size={18} />
              {next.loading ? 'Finding the next case…' : 'Next case'}
            </Button>
            <LinkButton to={learnTrick ? `/casebook/${learnTrick}` : '/casebook'} size="lg">
              <IconBook size={18} />
              Learn: {learnTrick ? trickLabel(learnTrick) : 'the tricks'}
            </LinkButton>
            <Button
              size="lg"
              onClick={async () => {
                setCopied((await copyText(shareText)) ? 'ok' : 'fail')
                window.setTimeout(() => setCopied('idle'), 2400)
              }}
              aria-describedby="share-note"
            >
              <IconShare size={18} />
              Share
            </Button>
            <LinkButton to="/dossier" variant="ghost" size="lg">
              Stats
            </LinkButton>
            <LinkButton to="/" variant="ghost" size="lg">
              Home
            </LinkButton>
            <span className="ml-auto flex gap-1.5" role="img" aria-label={`Share grid: ${ordered.map((p) => outcomeStyle(byId.get(p.id)!.outcome).word).join(', ')}`}>
              {ordered.map((p) => (
                <OutcomeSquare key={p.id} outcome={byId.get(p.id)!.outcome} size={30} />
              ))}
            </span>
          </div>
          <p id="share-note" className="-mt-2 text-[14px] text-muted italic" role="status">
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
