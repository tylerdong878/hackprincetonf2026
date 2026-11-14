import { useState } from 'react'
import { ConMascot } from '../components/Art'
import { ConBubble } from '../components/ConBubble'
import { LeanMeter } from '../components/LeanMeter'
import { LinkButton } from '../components/ui'
import { computeLean, gridFor, hms, leanLabel, msUntilMidnightET, outcomeStyle, shortDate, trickLabel } from '../lib/format'
import { copyText, useReducedMotion, useTween } from '../lib/hooks'
import type { DailyResponse, VerdictResponse } from '../lib/types'
import { useNow } from './common'

export function Countdown({ className = '' }: { className?: string }) {
  const now = useNow(1000)
  return (
    <p className={className}>
      Next Grain in <span className="font-mono font-semibold tabular-nums">{hms(msUntilMidnightET(now))}</span>
      <span className="text-muted"> (midnight ET)</span>
    </p>
  )
}

export function DailyEnd({ daily, result, alreadyPlayed }: { daily: DailyResponse; result: VerdictResponse; alreadyPlayed: boolean }) {
  const reduced = useReducedMotion()
  const score = Math.round(useTween(0, result.score ?? 0, 1, 1000, reduced))
  const [copied, setCopied] = useState<'idle' | 'ok' | 'fail'>('idle')
  const [showCards, setShowCards] = useState(false)

  const posts = daily.case.posts
  const byId = new Map(result.results.map((r) => [r.post_id, r]))
  const ordered = posts.map((p) => ({ post: p, r: byId.get(p.id) })).filter((x) => x.r)
  const outcomes = ordered.map((x) => x.r!.outcome)
  const grid = result.share_grid || gridFor(outcomes)
  const correct = outcomes.filter((o) => o === 'caught' || o === 'trusted').length
  const n = result.daily_number ?? daily.daily_number
  const streak = result.streak ?? 0
  const lean =
    result.lean ??
    computeLean(ordered.map((x) => ({ doctored: x.r!.doctored, outcome: x.r!.outcome })))
  const label = result.lean_label ?? (lean == null ? null : leanLabel(lean))
  const shareText =
    result.share_text ||
    `Grain of Salt #${n} 🧂 ${correct}/${outcomes.length}${streak ? ` 🔥${streak}` : ''}\n${grid}${label ? `\n${label} detective` : ''}`

  return (
    <main className="mx-auto flex w-full max-w-lg flex-1 flex-col gap-4 px-4 pt-5 pb-16">
      {alreadyPlayed && (
        <p className="rounded-xl border border-con/50 bg-con/10 px-4 py-2.5 text-center text-sm">
          You’ve played today’s Grain. <b>Come back tomorrow</b> for #{n + 1}.
        </p>
      )}

      <section className="paper-texture rise-in relative overflow-hidden rounded-2xl p-6 text-center" aria-labelledby="end-h">
        <p className="font-mono text-xs font-semibold tracking-[0.18em] text-[#6B5E45] uppercase">
          {shortDate(`${daily.date}T12:00:00`)} {daily.theme ? `· ${daily.theme}` : ''}
        </p>
        <h1 id="end-h" className="mt-1 font-display text-3xl font-bold">
          Grain of Salt #{n}
        </h1>
        <p className="mt-3 font-mono text-6xl font-semibold tabular-nums" aria-label={`Score ${result.score}`}>
          {score}
        </p>
        <p className="text-sm text-[#4B4232]">
          <b>{correct}/{outcomes.length}</b> right
          {result.clue_bonus ? <> · +{result.clue_bonus} for unused checks</> : null}
        </p>
        <p className="pop mt-4 text-4xl tracking-[0.2em]" role="img" aria-label={outcomes.map((o) => outcomeStyle(o).word).join(', ')}>
          {grid}
        </p>
        <p className="mt-1 text-[11px] text-[#6B5E45]">🟩 trusted · 🧂 caught · 🟥 false alarm · ⬛ fooled</p>
        <span
          className="stamp stamp-thunk absolute top-4 right-4 text-sm text-[#B8322A] opacity-80"
          style={{ ['--stamp-rot' as string]: '12deg' }}
          aria-hidden="true"
        >
          Closed
        </span>
      </section>

      <section className="rounded-2xl border border-line bg-surface p-5">
        <LeanMeter lean={lean} label={label} />
      </section>

      <section className="grid grid-cols-2 gap-3">
        <div className="rounded-2xl border border-line bg-surface p-4">
          <p className="text-[11px] font-bold tracking-[0.16em] text-muted uppercase">Detective rating</p>
          <p className="mt-1 font-mono text-3xl font-semibold">{result.rating}</p>
          <p className="font-display font-semibold text-con">{result.rank}</p>
        </div>
        <div className="rounded-2xl border border-line bg-surface p-4">
          <p className="text-[11px] font-bold tracking-[0.16em] text-muted uppercase">Streak</p>
          <p className="mt-1 font-mono text-3xl font-semibold">
            <span className={streak > 0 ? 'flame' : 'opacity-40 grayscale'} aria-hidden="true">
              🔥
            </span>{' '}
            {streak}
          </p>
          <p className="text-sm text-muted">{streak === 1 ? 'day played' : 'days in a row'}</p>
        </div>
      </section>

      {result.adaptation_message && (
        <div className="flex items-end gap-2.5">
          <ConMascot size={44} className="shrink-0" />
          <ConBubble text={result.adaptation_message} size="sm" className="min-w-0 flex-1" />
        </div>
      )}

      <section className="flex flex-col gap-2">
        <button
          type="button"
          onClick={async () => {
            setCopied((await copyText(shareText)) ? 'ok' : 'fail')
            window.setTimeout(() => setCopied('idle'), 2400)
          }}
          className="flex w-full items-center justify-center gap-2 rounded-2xl bg-real py-3.5 font-display text-lg font-semibold text-on-accent transition hover:brightness-110 active:scale-[0.98]"
        >
          {copied === 'ok' ? '✓ Copied!' : 'Share'} <span className="tracking-[0.1em]">{grid}</span>
        </button>
        <p className="text-center text-xs text-muted" role="status">
          {copied === 'fail'
            ? `Copy this instead: ${shareText.replace(/\n/g, ' · ')}`
            : 'Shares the number, grid and lean. Never the doctored posts.'}
        </p>
        <Countdown className="text-center text-sm" />
      </section>

      <a
        href="#/con"
        className="group flex w-full flex-col items-center rounded-2xl border-2 border-con bg-con/15 px-5 py-4 text-center transition hover:bg-con/25"
      >
        <span className="font-display text-xl font-semibold">
          Now try to con the Con <span className="inline-block transition group-hover:translate-x-1">→</span>
        </span>
        <span className="text-sm text-muted">Doctor a real post. Our AI tries to catch you, live.</span>
      </a>

      <section className="rounded-2xl border border-line bg-surface">
        <button
          type="button"
          aria-expanded={showCards}
          onClick={() => setShowCards((s) => !s)}
          className="flex w-full items-center justify-between px-5 py-3.5 text-left font-semibold"
        >
          Review today’s cards <span aria-hidden="true">{showCards ? '▴' : '▾'}</span>
        </button>
        {showCards && (
          <ol className="flex flex-col gap-3 border-t border-line px-5 py-4">
            {ordered.map(({ post, r }, i) => (
              <li key={post.id} className="flex gap-3 text-sm">
                <span className="text-xl leading-none" aria-hidden="true">
                  {outcomeStyle(r!.outcome).emoji}
                </span>
                <div className="min-w-0">
                  <p className="font-semibold">
                    {i + 1}. {post.author.name} · {outcomeStyle(r!.outcome).word}
                    {r!.doctored && <span className="text-muted"> · {trickLabel(r!.trick)}</span>}
                  </p>
                  <p className="text-muted">{r!.tell || r!.explanation}</p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>

      <div className="flex flex-wrap justify-center gap-2">
        <LinkButton to="/dossier" variant="ghost" size="sm">
          Dossier
        </LinkButton>
        <LinkButton to="/casefiles" variant="ghost" size="sm">
          Case Files
        </LinkButton>
        <LinkButton to="/" variant="ghost" size="sm">
          Home
        </LinkButton>
      </div>
    </main>
  )
}
