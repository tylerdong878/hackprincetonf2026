import { useEffect, useState } from 'react'
import { ConMascot } from '../components/Art'
import { ConBubble } from '../components/ConBubble'
import { LeanMeter } from '../components/LeanMeter'
import { LinkButton } from '../components/ui'
import { computeLean, gridFor, GRID_LEGEND, hms, leanLabel, msUntilMidnightET, outcomeStyle, shortDate, trickLabel } from '../lib/format'
import { copyText, useReducedMotion, useTween } from '../lib/hooks'
import { play } from '../lib/sound'
import type { DailyResponse, Post, PostResult, VerdictResponse } from '../lib/types'
import { useNow } from './common'

export function Countdown({ className = '' }: { className?: string }) {
  const now = useNow(1000)
  return (
    <p className={className}>
      Next Grain in <span className="num font-semibold">{hms(msUntilMidnightET(now))}</span>
      <span className="text-muted"> (midnight ET)</span>
    </p>
  )
}

const TILE_MS = 230

/** Wordle-style: each card's tile flips in one by one, with a small tick per tile. */
function Tiles({ outcomes, animate }: { outcomes: string[]; animate: boolean }) {
  useEffect(() => {
    if (!animate) return
    const ids = outcomes.map((_, i) => window.setTimeout(() => play('tile'), i * TILE_MS + 220))
    return () => ids.forEach((id) => window.clearTimeout(id))
  }, [outcomes, animate])
  return (
    <div className="flex flex-nowrap justify-center gap-1.5" role="img" aria-label={outcomes.map((o) => outcomeStyle(o).word).join(', ')}>
      {outcomes.map((o, i) => (
        <span
          key={i}
          className={`${animate ? 'tile-flip' : ''} inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border-2 bg-white/55 text-[26px] leading-none sm:h-12 sm:w-12 sm:text-[28px]`}
          style={{ borderColor: 'rgba(42,36,24,0.18)', animationDelay: animate ? `${i * TILE_MS}ms` : undefined }}
          aria-hidden="true"
        >
          {outcomeStyle(o).emoji}
        </span>
      ))}
    </div>
  )
}

interface Rarest {
  index: number
  post: Post
  r: PostResult
  pct: number | null
}

/** The rarest correct call today: the biggest rarity bonus, else the lowest "% got it right". */
function rarestCatch(ordered: { post: Post; r?: PostResult }[]): Rarest | null {
  let best: Rarest | null = null
  ordered.forEach(({ post, r }, index) => {
    if (!r || (r.outcome !== 'caught' && r.outcome !== 'trusted')) return
    const pct = r.rarity?.correct_pct ?? null
    const bonus = r.rarity_bonus?.points ?? 0
    if (!bonus && (pct == null || pct > 40)) return
    const cand = { index, post, r, pct }
    if (!best) best = cand
    else {
      const b: Rarest = best
      const bb = b.r.rarity_bonus?.points ?? 0
      if (bonus > bb || (bonus === bb && (pct ?? 101) < (b.pct ?? 101))) best = cand
    }
  })
  return best
}

export function DailyEnd({ daily, result, alreadyPlayed }: { daily: DailyResponse; result: VerdictResponse; alreadyPlayed: boolean }) {
  const reduced = useReducedMotion()
  const posts = daily.case.posts
  const byId = new Map(result.results.map((r) => [r.post_id, r]))
  const ordered = posts.map((p) => ({ post: p, r: byId.get(p.id) })).filter((x) => x.r)
  const outcomes = ordered.map((x) => x.r!.outcome)
  const animate = !reduced && !alreadyPlayed
  const tilesDone = outcomes.length * TILE_MS + 300
  const [scoreGo, setScoreGo] = useState(animate ? 0 : 1)
  useEffect(() => {
    if (!animate) return
    const id = window.setTimeout(() => setScoreGo(1), tilesDone)
    return () => window.clearTimeout(id)
  }, [animate, tilesDone])
  const score = Math.round(useTween(0, result.score ?? 0, scoreGo, 900, reduced || !animate))
  const [copied, setCopied] = useState<'idle' | 'ok' | 'fail'>('idle')
  const [showCards, setShowCards] = useState(false)

  // The grid always uses the v2.1 emoji (CONTRACT §8.2), whatever an older server sends.
  const grid = gridFor(outcomes)
  const correct = outcomes.filter((o) => o === 'caught' || o === 'trusted').length
  const n = result.daily_number ?? daily.daily_number
  const streak = result.streak ?? 0
  const lean = result.lean ?? computeLean(ordered.map((x) => ({ doctored: x.r!.doctored, outcome: x.r!.outcome })))
  const label = result.lean_label ?? (lean == null ? null : leanLabel(lean))
  const fallbackShare = `Grain of Salt #${n} 🧂 ${correct}/${outcomes.length}${streak ? ` 🔥${streak}` : ''}\n${grid}${label ? `\n${label} detective` : ''}`
  const shareText = result.share_text
    ? result.share_grid && result.share_grid !== grid
      ? result.share_text.replace(result.share_grid, grid)
      : result.share_text
    : fallbackShare
  const rare = rarestCatch(ordered)
  const bonusTotal = ordered.reduce((s, x) => s + (x.r?.rarity_bonus?.points ?? 0), 0)

  return (
    <main className="mx-auto flex w-full max-w-lg flex-1 flex-col gap-4 px-4 pt-5 pb-16">
      {alreadyPlayed && (
        <p className="rounded-xl border border-con/50 bg-con/10 px-4 py-2.5 text-center text-sm">
          You’ve played today’s Grain. <b>Come back tomorrow</b> for #{n + 1}.
        </p>
      )}

      {/* Lead with the grid and the lean meter. */}
      <section className="paper-texture rise-in rounded-2xl px-5 pt-5 pb-5 text-center sm:px-6" aria-labelledby="end-h">
        <p className="font-mono text-xs font-semibold tracking-[0.18em] text-[#6B5E45] uppercase">
          {shortDate(`${daily.date}T12:00:00`)} {daily.theme ? `· ${daily.theme}` : ''}
        </p>
        <h1 id="end-h" className="mt-1 font-display text-3xl font-bold">
          Grain of Salt #{n}
        </h1>
        <div className="mt-4">
          <Tiles outcomes={outcomes} animate={animate} />
        </div>
        <p className="mt-1.5 text-[11px] text-[#6B5E45]">{GRID_LEGEND}</p>
        <div className="mt-3 flex flex-wrap items-center justify-center gap-x-3 gap-y-1">
          <p className="text-[15px] text-[#4B4232]" aria-label={`${correct} of ${outcomes.length} right, ${result.score} points`}>
            <b className="num text-[#2A2418]">
              {correct}/{outcomes.length}
            </b>{' '}
            right · <b className="num text-2xl text-[#2A2418]">{score}</b> pts
          </p>
          <span
            className={`stamp ${animate ? 'stamp-thunk' : ''} text-xs text-[#B8322A]`}
            style={{ ['--stamp-rot' as string]: '-6deg', animationDelay: animate ? `${tilesDone}ms` : undefined }}
            aria-hidden="true"
          >
            Closed
          </span>
        </div>
        {(result.clue_bonus || bonusTotal > 0) && (
          <p className="mt-0.5 text-xs text-[#6B5E45]">
            {result.clue_bonus ? <>+{result.clue_bonus} unused checks</> : null}
            {result.clue_bonus && bonusTotal ? ' · ' : null}
            {bonusTotal ? <>+{bonusTotal} rarity bonus</> : null}
          </p>
        )}
        <div className="mt-4 border-t border-dashed border-[#B9A985] pt-4 text-left text-[#2A2418]">
          <LeanMeter lean={lean} label={label} onPaper />
        </div>
      </section>

      {/* Small chips: streak, rating, the rarest catch. */}
      <div className="flex flex-wrap items-center justify-center gap-2 text-sm">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 font-semibold">
          <span className={streak > 0 ? 'flame' : 'opacity-40 grayscale'} aria-hidden="true">
            🔥
          </span>
          <span>
            <span className="num">{streak}</span>-day streak
          </span>
        </span>
        <a
          href="#/dossier"
          className="inline-flex items-center gap-1.5 rounded-full border border-con/50 bg-con/10 px-3 py-1.5 font-semibold hover:bg-con/20"
        >
          <span aria-hidden="true">🕵️</span> {result.rank} <span className="num text-muted">{result.rating}</span>
        </a>
      </div>

      {rare && (
        <section className="pop flex items-center gap-3 rounded-2xl border-2 border-con/60 bg-con/10 px-4 py-3" aria-label="Your rarest catch today">
          <span className="text-3xl" aria-hidden="true">
            {rare.r.rarity_bonus && rare.r.rarity_bonus.points >= 100 ? '🧂' : '💎'}
          </span>
          <div className="min-w-0 flex-1 text-sm">
            <p className="font-display text-base font-semibold">
              Rarest catch: card {rare.index + 1}
              {rare.r.rarity_bonus && (
                <span className="ml-2 text-con">
                  {rare.r.rarity_bonus.label} <span className="num">+{rare.r.rarity_bonus.points}</span>
                </span>
              )}
            </p>
            <p className="truncate text-muted">
              {rare.pct != null && (
                <>
                  Only <b className="num text-text">{Math.round(rare.pct)}%</b> {rare.r.doctored ? 'caught' : 'trusted'} this ·{' '}
                </>
              )}
              {rare.post.author.name}
            </p>
          </div>
        </section>
      )}

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
          {copied === 'fail' ? `Copy this instead: ${shareText.replace(/\n/g, ' · ')}` : 'Shares the number, grid and lean. Never the doctored posts.'}
        </p>
        <Countdown className="text-center text-sm" />
      </section>

      <a
        href="#/con"
        className="group flex w-full flex-col items-center rounded-2xl border-2 border-con bg-con/15 px-5 py-4 text-center transition hover:bg-con/25"
      >
        <span className="font-display text-xl font-semibold">
          Bonus round: con the Con <span className="inline-block transition group-hover:translate-x-1">→</span>
        </span>
        <span className="text-sm text-muted">Doctor a real post. Our AI tries to bust you, live.</span>
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
          More cases
        </LinkButton>
        <LinkButton to="/" variant="ghost" size="sm">
          Home
        </LinkButton>
      </div>
    </main>
  )
}
