import { useEffect, useState } from 'react'
import { ConMascot } from '../components/Art'
import { ConBubble } from '../components/ConBubble'
import { IconArrow, IconCheck, IconChevron, IconFlame, IconMask, IconShare, IconSparkles, OutcomeSquare, SaltCrystal } from '../components/Icon'
import { LeanMeter } from '../components/LeanMeter'
import { btnClass, LinkButton } from '../components/ui'
import { computeLean, gridFor, GRID_LEGEND, hms, leanLabel, msUntilMidnightET, outcomeStyle, shortDate, trickLabel } from '../lib/format'
import { copyText, useReducedMotion, useTween } from '../lib/hooks'
import { play } from '../lib/sound'
import type { DailyResponse, Post, PostResult, VerdictResponse } from '../lib/types'
import { useNow } from './common'

export function Countdown({ className = '' }: { className?: string }) {
  const now = useNow(1000)
  return (
    <p className={`flex flex-wrap items-end justify-between gap-x-3 bg-ink px-4 py-3 text-sheet ${className}`}>
      <span className="flex flex-col">
        <span className="caps text-[12.5px] font-semibold tracking-[0.08em] text-[#C9C2B5]">Next Grain in</span>
        <span className="num text-[34px] leading-none font-bold">{hms(msUntilMidnightET(now))}</span>
      </span>
      <span className="caps text-[12.5px] font-semibold tracking-[0.08em] text-[#C9C2B5]"> (midnight ET)</span>
    </p>
  )
}

const TILE_MS = 230

/** The outcome legend: the same four words as GRID_LEGEND, with the squares instead of the share emoji. */
const LEGEND: [string, string][] = [
  ['trusted', 'trusted'],
  ['caught', 'caught'],
  ['false_alarm', 'false alarm'],
  ['fooled', 'fooled'],
]

/** Wordle-style: each card's tile flips in one by one, with a small tick per tile. */
function Tiles({ outcomes, animate }: { outcomes: string[]; animate: boolean }) {
  useEffect(() => {
    if (!animate) return
    const ids = outcomes.map((_, i) => window.setTimeout(() => play('tile'), i * TILE_MS + 220))
    return () => ids.forEach((id) => window.clearTimeout(id))
  }, [outcomes, animate])
  return (
    <div className="flex flex-nowrap justify-start gap-2" role="img" aria-label={outcomes.map((o) => outcomeStyle(o).word).join(', ')}>
      {outcomes.map((o, i) => (
        <span
          key={i}
          className={`${animate ? 'tile-flip' : ''} inline-flex shrink-0`}
          style={{ animationDelay: animate ? `${i * TILE_MS}ms` : undefined }}
          aria-hidden="true"
        >
          <OutcomeSquare outcome={o} size={52} />
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
    <main className="mx-auto flex w-full max-w-lg flex-1 flex-col gap-5 px-4 pt-6 pb-16 lg:grid lg:max-w-[1160px] lg:grid-cols-2 lg:items-start lg:gap-x-10 lg:px-6 lg:pt-10">
      {alreadyPlayed && (
        <p className="border-2 border-ink bg-sheet px-4 py-2.5 text-center text-sm lg:col-span-2">
          You’ve played today’s Grain. <b>Come back tomorrow</b> for #{n + 1}.
        </p>
      )}

      {/* Laptop: the result on the left, what to do next on the right. Phones: one column, same order. */}
      <div className="flex flex-col gap-5">
        {/* Lead with the grid and the lean meter. */}
        <section className="panel rise-in relative px-5 pt-5 pb-16 sm:px-6" aria-labelledby="end-h">
          <p className="dateline font-bold">
            {shortDate(`${daily.date}T12:00:00`)} {daily.theme ? `· ${daily.theme}` : ''}
          </p>
          <h1 id="end-h" className="logotype mt-2 text-[40px] text-ink sm:text-[44px]">
            Grain of Salt #{n}
          </h1>
          <div className="mt-4 flex flex-wrap items-end gap-x-4 gap-y-1" aria-label={`${correct} of ${outcomes.length} right, ${result.score} points`}>
            <p className="flex items-baseline gap-1.5">
              <b className="num text-[76px] leading-[0.85] font-bold text-ink">{score}</b>
              <span className="caps text-sm font-semibold text-muted">pts</span>
            </p>
            <div className="pb-1">
              <p className="font-head text-xl font-bold">
                <span className="num">
                  {correct}/{outcomes.length}
                </span>{' '}
                right
              </p>
              {(result.clue_bonus || bonusTotal > 0) && (
                <p className="text-[14px] text-muted">
                  {result.clue_bonus ? <>+{result.clue_bonus} unused checks</> : null}
                  {result.clue_bonus && bonusTotal ? ' · ' : null}
                  {bonusTotal ? <>+{bonusTotal} rarity bonus</> : null}
                </p>
              )}
            </div>
          </div>
          <div className="mt-4">
            <Tiles outcomes={outcomes} animate={animate} />
          </div>
          <ul className="mt-3 flex flex-wrap gap-x-3.5 gap-y-1 text-[13px] text-muted" aria-label={GRID_LEGEND}>
            {LEGEND.map(([o, word]) => (
              <li key={o} className="inline-flex items-center gap-1.5">
                <OutcomeSquare outcome={o} size={15} />
                {word}
              </li>
            ))}
          </ul>
          <span
            className={`stamp ${animate ? 'stamp-thunk' : ''} absolute right-5 bottom-4 bg-sheet text-[18px] text-press`}
            style={{ ['--stamp-rot' as string]: '-6deg', animationDelay: animate ? `${tilesDone}ms` : undefined }}
            aria-hidden="true"
          >
            Closed
          </span>
        </section>

        <section aria-label="Your lean">
          <LeanMeter lean={lean} label={label} />
        </section>

        {/* Rating and streak. */}
        <div className="grid grid-cols-2 gap-3">
          <a href="#/dossier" className="panel press flex flex-col justify-center px-4 py-3 hover:bg-surface-2">
            <span className="flex items-baseline gap-2">
              <span className="num text-[40px] leading-none font-bold">{result.rating}</span>
              <span className="truncate text-lg text-press italic">{result.rank}</span>
            </span>
          </a>
          <div className="panel flex items-center gap-2 px-4 py-3">
            <IconFlame size={30} className={streak > 0 ? 'flame text-press' : 'text-muted opacity-50'} />
            <span className="num leading-none whitespace-nowrap">
              <span className="text-[40px] font-bold">{streak}</span>
              <span className="text-[18px] font-semibold text-muted">-day streak</span>
            </span>
          </div>
        </div>

        {rare && (
          <section className="pop panel flex items-center gap-3 px-4 py-3" aria-label="Your rarest catch today">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center border-2 border-ink bg-highlight text-ink" aria-hidden="true">
              {rare.r.rarity_bonus && rare.r.rarity_bonus.points >= 100 ? <SaltCrystal size={26} /> : <IconSparkles size={22} />}
            </span>
            <div className="min-w-0 flex-1 text-sm">
              <p className="font-head text-lg font-bold">
                Rarest catch: card {rare.index + 1}
                {rare.r.rarity_bonus && (
                  <span className="ml-2 text-press">
                    {rare.r.rarity_bonus.label} <span className="num">+{rare.r.rarity_bonus.points}</span>
                  </span>
                )}
              </p>
              <p className="truncate text-muted">
                {rare.pct != null && (
                  <>
                    Only <b className="num text-ink">{Math.round(rare.pct)}%</b> {rare.r.doctored ? 'caught' : 'trusted'} this ·{' '}
                  </>
                )}
                {rare.post.author.name}
              </p>
            </div>
          </section>
        )}

        {result.adaptation_message && (
          <div className="flex items-start gap-3">
            <ConMascot size={56} shape="circle" className="mt-1 shrink-0" />
            <ConBubble text={result.adaptation_message} size="md" className="min-w-0 flex-1" />
          </div>
        )}

      </div>

      <div className="flex flex-col gap-5">
        <section className="flex flex-col gap-2">
          <button
            type="button"
            onClick={async () => {
              setCopied((await copyText(shareText)) ? 'ok' : 'fail')
              window.setTimeout(() => setCopied('idle'), 2400)
            }}
            className={`${btnClass('primary', 'lg')} w-full py-4 text-xl`}
          >
            {copied === 'ok' ? (
              <>
                <IconCheck size={22} strokeWidth={2.6} /> Copied!
              </>
            ) : (
              <>
                <IconShare size={22} /> Share
              </>
            )}
          </button>
          <p className="text-[13px] text-muted" role="status">
            {copied === 'fail' ? `Copy this instead: ${shareText.replace(/\n/g, ' · ')}` : 'Shares the number, grid and lean. Never the doctored posts.'}
          </p>
          <Countdown className="mt-3" />
        </section>

        <a
          href="#/con"
          className="group press flex w-full items-center gap-3.5 border-2 border-press bg-sheet px-4 py-4 shadow-[var(--hard)] hover:bg-press/[0.04]"
        >
          <IconMask size={34} className="shrink-0 text-press" />
          <span className="min-w-0 flex-1">
            <span className="block font-display text-[21px] leading-tight font-bold">Bonus round: con the Con</span>
            <span className="block text-[14px] text-muted">Doctor a real post. Our AI tries to bust you, live.</span>
          </span>
          <IconArrow size={24} className="shrink-0 text-press transition group-hover:translate-x-1" />
        </a>

        <section className="border-2 border-ink bg-sheet">
          <button
            type="button"
            aria-expanded={showCards}
            onClick={() => setShowCards((s) => !s)}
            className="caps flex w-full items-center justify-between px-4 py-3.5 text-left text-[16px] font-bold"
          >
            Review today’s cards <IconChevron size={20} className={`transition ${showCards ? 'rotate-180' : ''}`} />
          </button>
          {showCards && (
            <ol className="flex flex-col gap-3 border-t-2 border-ink px-4 py-4">
              {ordered.map(({ post, r }, i) => (
                <li key={post.id} className="flex gap-3 text-sm">
                  <OutcomeSquare outcome={r!.outcome} size={26} className="mt-0.5" />
                  <div className="min-w-0">
                    <p className="font-bold">
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
            Stats
          </LinkButton>
          <LinkButton to="/casefiles" variant="ghost" size="sm">
            More cases
          </LinkButton>
          <LinkButton to="/" variant="ghost" size="sm">
            Home
          </LinkButton>
        </div>
      </div>
    </main>
  )
}
