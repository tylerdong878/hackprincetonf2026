import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ConBubble } from '../components/ConBubble'
import { AccountView, DataView, normalizeEvidence, SourceView, ToolRow, TOOLS } from '../components/EvidenceKit'
import { BarHeader, SiteHeader, SoundToggle } from '../components/Header'
import {
  ClueToken,
  IconArrow,
  IconArrowLeft,
  IconCheck,
  IconGlasses,
  IconLens,
  IconMask,
  IconSparkles,
  IconX,
  OutcomeSquare,
  SaltCrystal,
} from '../components/Icon'
import { FeedCard, PostThumb } from '../components/PostCard'
import { MiniDiff, OutcomeBadge } from '../components/Reveal'
import { TrickPicker } from '../components/TrickPicker'
import { btnClass, Button, ErrorState, Loading } from '../components/ui'
import { api, ApiError, BACKEND_START_CMD } from '../lib/api'
import { CON_QUIPS, pick } from '../lib/content'
import { outcomeStyle, shortDate, trickLabel } from '../lib/format'
import { useAsync, useElementHeight, useReducedMotion, useTween } from '../lib/hooks'
import { withPlayer } from '../lib/player'
import { navigate } from '../lib/router'
import { play } from '../lib/sound'
import type {
  AccountEvidence,
  AnswerResponse,
  AnyEvidence,
  DailyResponse,
  DataEvidence,
  Post,
  RarityBonus,
  SourceEvidence,
  ToolId,
  VerdictResponse,
} from '../lib/types'
import { loadJSON, saveJSON } from './common'
import { DailyEnd } from './DailyEnd'
import tornV from '../assets/figma/torn-v.webp'

export const DAILY_RANGE = '0–3 doctored today'

interface CardRecord {
  doctored: boolean
  trick: string | null
  reveal: AnswerResponse | null
  /** The server already had an answer for this card (another tab / device). */
  skipped?: boolean
  /** Rebuilt from GET /daily's `answered` after a reload (no crowd stats then). */
  restored?: boolean
}

interface Progress {
  started: boolean
  cards: Record<string, CardRecord>
  cluesLeft: number
  evidence: Record<string, Partial<Record<ToolId, AnyEvidence>>>
}

function trickChoices(options: string[]): string[] {
  const list = [...options]
  if (!list.includes('edited-detail')) list.push('edited-detail')
  return list
}

// ---------------------------------------------------------------------------------------------

function SaltBurst() {
  const grains = useMemo(
    () =>
      Array.from({ length: 12 }, (_, i) => {
        const angle = (i / 12) * Math.PI * 2 + Math.random() * 0.4
        const dist = 60 + Math.random() * 50
        return { dx: Math.cos(angle) * dist, dy: Math.sin(angle) * dist - 20, rot: Math.random() * 360 - 180, size: 6 + Math.random() * 6 }
      }),
    [],
  )
  return (
    <span className="pointer-events-none absolute top-8 left-16 z-10" aria-hidden="true">
      {grains.map((g, i) => (
        <span
          key={i}
          className="burst-grain absolute border border-ink bg-white"
          style={{
            width: g.size,
            height: g.size,
            ['--dx' as string]: `${g.dx}px`,
            ['--dy' as string]: `${g.dy}px`,
            ['--rot' as string]: `${g.rot}deg`,
          }}
        />
      ))}
    </span>
  )
}

export function ProgressDots({ posts, cards, current }: { posts: Post[]; cards: Record<string, CardRecord>; current: number }) {
  return (
    <ol className="flex items-center justify-center gap-2.5" aria-label="Today’s cards">
      {posts.map((p, i) => {
        const rec = cards[p.id]
        const outcome = rec?.reveal?.result.outcome
        const label = outcome ? outcomeStyle(outcome).word : rec?.skipped ? 'answered earlier' : i === current ? 'current card' : 'not played yet'
        const here = i === current
        return (
          <li key={p.id} aria-label={`Card ${i + 1}: ${label}`} aria-current={here ? 'step' : undefined}>
            {outcome ? (
              <span className={`pop flex ${here ? 'outline-2 outline-offset-2 outline-press' : ''}`}>
                <OutcomeSquare outcome={outcome} size={32} />
              </span>
            ) : (
              <span
                className={`num flex h-8 w-8 items-center justify-center text-[14px] font-semibold ${
                  here
                    ? 'border-2 border-ink bg-sheet text-ink outline-2 outline-offset-2 outline-press'
                    : 'border-[1.5px] border-[#cfcfcf] text-muted'
                }`}
              >
                {rec?.skipped ? '–' : i + 1}
              </span>
            )}
          </li>
        )
      })}
    </ol>
  )
}

/** Laptop: one tab per card with its status (Figma "Case — Investigation" jump strip). Phones use ProgressDots. */
function CardTabs({ posts, cards, current, className = '' }: { posts: Post[]; cards: Record<string, CardRecord>; current: number; className?: string }) {
  return (
    <ol className={`grid-cols-5 gap-2 ${className}`} aria-label="Today’s cards">
      {posts.map((p, i) => {
        const rec = cards[p.id]
        const outcome = rec?.reveal?.result.outcome
        const on = i === current
        const word = outcome ? outcomeStyle(outcome).word : rec?.skipped ? 'answered' : on ? 'inspecting' : 'not played'
        const bad = outcome === 'fooled' || outcome === 'false_alarm'
        return (
          <li
            key={p.id}
            aria-current={on ? 'step' : undefined}
            className={`caps flex flex-col items-center border-2 px-2 py-1.5 leading-tight ${
              on ? 'border-ink bg-ink text-sheet' : outcome ? 'border-ink bg-sheet text-ink' : 'border-[#a8a8a8] bg-sheet text-ink'
            }`}
          >
            <span className="text-[15px] font-bold">Card {i + 1}</span>
            <span className={`text-[11px] font-semibold tracking-[0.06em] ${on ? 'text-press-soft' : bad ? 'text-press' : 'text-muted'}`}>{word}</span>
          </li>
        )
      })}
    </ol>
  )
}

function Magnifiers({ left, total }: { left: number; total: number }) {
  return (
    <span className="inline-flex items-center gap-1" role="img" aria-label={`${left} of ${total} checks left`}>
      {Array.from({ length: total }, (_, i) => (
        <ClueToken key={i} spent={i >= left} size={24} />
      ))}
    </span>
  )
}

/** CONTRACT §8.7 rarity bonus: "One in a shaker" (+100) or "Rare catch" (+50). */
export function rarityBonusOf(reveal: AnswerResponse | null | undefined): RarityBonus | null {
  const b = reveal?.result.rarity_bonus ?? reveal?.rarity_bonus ?? null
  return b && typeof b.points === 'number' && b.points > 0 ? b : null
}

export function RarityBadge({ bonus, className = '' }: { bonus: RarityBonus; className?: string }) {
  const shaker = /shaker/i.test(bonus.label) || bonus.points >= 100
  return (
    <span
      className={`pop caps inline-flex items-center gap-1.5 border-2 border-ink px-2.5 py-1 text-[13px] font-bold whitespace-nowrap shadow-[var(--hard-sm)] ${
        shaker ? 'bg-highlight text-ink' : 'bg-sheet text-press'
      } ${className}`}
    >
      {shaker ? <SaltCrystal size={16} /> : <IconSparkles size={15} />}
      {bonus.label}
      {/[!.]$/.test(bonus.label) ? '' : shaker ? '!' : ''} <span className="num">+{bonus.points}</span>
    </span>
  )
}

function CrowdLine({ reveal }: { reveal: AnswerResponse }) {
  const crowd = reveal.crowd
  const rarity = reveal.rarity ?? reveal.result.rarity ?? null
  const bonus = rarityBonusOf(reveal)
  if (!crowd) {
    return (
      <p className="flex items-start gap-2 border-[1.5px] border-[#cfcfcf] px-3 py-2 text-sm text-muted">
        <IconGlasses size={18} className="mt-0.5 text-ink" />
        <span>Be one of the first 10 detectives to answer this one. Crowd stats unlock at 10.</span>
      </p>
    )
  }
  const doctoredPct = Math.round(crowd.said_doctored_pct)
  const realPct = 100 - doctoredPct
  const correct = Math.round(rarity?.correct_pct ?? crowd.correct_pct)
  const verb = reveal.result.doctored ? 'caught this' : 'trusted this'
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex h-3.5 overflow-hidden border-2 border-ink bg-sheet" aria-hidden="true">
        <span className="h-full bg-ink" style={{ width: `${realPct}%` }} />
        <span className="h-full bg-press" style={{ width: `${doctoredPct}%` }} />
      </div>
      <p className="text-[15px] font-bold">
        <b className="num">{realPct}%</b> said Real, <b className="num">{doctoredPct}%</b> said Doctored
        <span className="font-normal text-muted">
          {' '}
          (<span className="num">{crowd.n}</span> detectives)
        </span>
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-[15px] font-bold" style={{ color: correct < 50 ? 'var(--press)' : 'var(--muted)' }}>
          {correct < 50 ? (
            <>
              Only <span className="num">{correct}%</span> {verb}.
            </>
          ) : (
            <>
              <span className="num">{correct}%</span> {verb}.
            </>
          )}
        </p>
        {bonus && <RarityBadge bonus={bonus} />}
      </div>
    </div>
  )
}

function Points({ value, delay = 120 }: { value: number; delay?: number }) {
  const reduced = useReducedMotion()
  const [go, setGo] = useState(reduced ? 1 : 0)
  useEffect(() => {
    if (reduced) return
    const id = window.setTimeout(() => setGo(1), delay)
    return () => window.clearTimeout(id)
  }, [reduced, delay])
  const v = Math.round(useTween(0, value, go, 520, reduced))
  return (
    <span
      className="pop num ml-auto text-4xl leading-none font-bold"
      style={{ color: value > 0 ? 'var(--ink)' : value < 0 ? 'var(--press)' : 'var(--muted)' }}
      aria-label={`${value} points`}
    >
      {v > 0 ? `+${v}` : v < 0 ? `−${Math.abs(v)}` : '0'}
    </span>
  )
}

function CardBack({ post, rec, caseNumber }: { post: Post; rec: CardRecord; caseNumber: number }) {
  const reveal = rec.reveal
  const quip = useMemo(() => {
    if (!reveal) return ''
    return reveal.result.con_line || pick(CON_QUIPS[reveal.result.outcome] ?? CON_QUIPS.trusted)
  }, [reveal])

  if (!reveal) {
    return (
      <div className="panel p-5 text-center">
        <p className="font-display text-xl font-bold">You answered this card earlier.</p>
        <p className="mt-1 text-sm text-muted">Its reveal is waiting on your end card.</p>
        <div className="mt-4 opacity-80">
          <FeedCard post={post} caseNumber={caseNumber} compact />
        </div>
      </div>
    )
  }
  const r = reveal.result
  const s = outcomeStyle(r.outcome)
  const win = r.outcome === 'caught' || r.outcome === 'trusted'
  const pts = r.points ?? 0
  const you = rec.doctored ? `Doctored${rec.trick ? ` (${trickLabel(rec.trick)})` : ''}` : 'Real'

  return (
    <div
      className={`relative overflow-hidden border-2 bg-sheet p-4 shadow-[var(--hard)] sm:p-5 ${win ? 'thud' : 'shake'}`}
      style={{ borderColor: r.outcome === 'trusted' || r.outcome === 'caught' ? 'var(--ink)' : s.color }}
      aria-live="polite"
    >
      {win && <SaltBurst />}
      {/* the post you just judged, shrunk to a thumbnail */}
      <PostThumb post={post} className="mb-3 opacity-95" />
      <div className="flex items-center gap-3 px-1 py-1">
        <OutcomeBadge outcome={r.outcome} size="lg" />
        <Points value={pts} />
      </div>
      <p className="mt-3 font-head text-2xl leading-tight font-bold">
        {r.doctored ? <>Doctored: {trickLabel(r.trick)}</> : r.suspicious_real ? <>Real, just sounds fake</> : <>Real</>}
      </p>
      <p className="text-[15px] text-muted">
        You said <span className="font-bold text-ink">{you}</span>
        {r.trick_named_correctly && <span className="font-bold text-ink">, named the trick (+50)</span>}
      </p>

      {(r.tell || r.explanation) && (
        <p className={`mt-3 text-[16px] leading-snug font-bold`}>
          {r.doctored ? (
            <b>The tell: </b>
          ) : (
            <b className="inline-flex items-baseline gap-1">
              <IconCheck size={15} strokeWidth={2.6} className="self-center" /> Checks out:
            </b>
          )}{' '}
          <span className="font-normal">{r.tell || r.explanation}</span>
        </p>
      )}

      {r.doctored && r.diff && (
        <div className="mt-3">
          <MiniDiff diff={r.diff} post={post} />
        </div>
      )}

      <div className="mt-5 flex items-start gap-3">
        <ConBubble text={quip} size="md" speed={14} className="min-w-0 flex-1" />
      </div>

      {!rec.restored && (
        <div className="mt-5 border-t border-[#a8a8a8] pt-4">
          <CrowdLine reveal={reveal} />
        </div>
      )}
    </div>
  )
}

function EvidenceInline({ tool, ev }: { tool: ToolId; ev: AnyEvidence }) {
  const t = TOOLS.find((x) => x.id === tool)
  return (
    <section className="fade-in border-2 border-ink bg-sheet p-3 shadow-[var(--hard)]" aria-label={`${t?.label} evidence`}>
      <p className="caps mb-2 text-[12.5px] font-semibold tracking-[0.08em] text-press">{t?.label}</p>
      {tool === 'source' && <SourceView ev={ev as SourceEvidence} />}
      {tool === 'data' && <DataView ev={ev as DataEvidence} />}
      {tool === 'account' && <AccountView ev={ev as AccountEvidence} />}
    </section>
  )
}

// ---------------------------------------------------------------------------------------------

function DailyBriefing({ daily, onStart }: { daily: DailyResponse; onStart: () => void }) {
  const c = daily.case
  const startRef = useRef<HTMLButtonElement>(null)
  return (
    <>
      <SiteHeader active="daily" />
      <main className="flex-1 pb-16">
        {/* Masthead on the black paper: red kicker, Iosevka caps title over the double rule (as on every page). */}
        <section className="torn-hero">
          <div className="page-wrap pt-8 md:pt-[30px]">
            <div className="on-night max-w-[830px]">
              <p className="kicker">{shortDate(`${daily.date}T12:00:00`)}</p>
              <h1 id="grain-h" className="hero-title mt-1">
                Grain #{daily.daily_number}
              </h1>
              <div className="double-rule mt-1 max-w-[780px]" aria-hidden="true" />
              <p className="mt-3 text-[20px] leading-snug font-bold">{c.title}</p>
              {daily.theme && <p className="mt-1 text-[17px] leading-[1.5] italic">{daily.theme}</p>}
            </div>
          </div>
        </section>

        {/* Below the tear: the Con’s line on the left, the rules card on the right (Figma "Case — Briefing"). */}
        <div className="page-wrap -mt-10 grid gap-8 md:-mt-16 lg:grid-cols-[minmax(0,1fr)_minmax(0,560px)] lg:items-start lg:gap-14">
          <div className="lg:pt-20">
            <ConBubble
              text={c.briefing}
              size="lg"
              className="w-full"
              onDone={() => startRef.current?.focus({ preventScroll: true })}
            />
          </div>
          <section className="folder-open paper-card relative bg-white/90 p-5 sm:p-7" aria-labelledby="grain-h">
            <p className="caps text-[13px] font-bold tracking-[0.06em]">Today’s rules</p>
            <div className="double-rule-thin mt-1.5" aria-hidden="true" />
            <ul className="mt-5 grid grid-cols-3 gap-2 border-y border-[#cfcfcf] py-4 text-center">
              <li className="flex flex-col items-center gap-1">
                <span className="caps text-[12px] font-semibold tracking-[0.08em] text-muted">cards</span>
                <span className="num block text-4xl leading-none font-bold">{c.posts.length}</span>
              </li>
              <li className="flex flex-col items-center gap-1">
                <span className="caps text-[12px] font-semibold tracking-[0.08em] text-muted">{c.clue_budget} checks</span>
                <span className="flex items-center gap-0.5" aria-hidden="true">
                  {Array.from({ length: Math.min(5, c.clue_budget) }, (_, i) => (
                    <ClueToken key={i} size={26} />
                  ))}
                </span>
              </li>
              <li className="flex flex-col items-center gap-1">
                <span className="caps text-[12px] font-semibold tracking-[0.08em] text-muted">doctored</span>
                <span className="num block text-4xl leading-none font-bold">0–3</span>
              </li>
            </ul>
            <p className="mt-5 border-2 border-press bg-press-wash px-4 py-3 text-center text-[18px] text-press italic">{DAILY_RANGE}. Maybe none.</p>
            <ul className="mt-4 flex flex-col gap-1.5 text-[15px]" aria-label="Scoring">
              <li className="flex items-baseline gap-3">
                <span className="num w-12 text-lg font-bold">+100</span> per right call
              </li>
              <li className="flex items-baseline gap-3">
                <span className="num w-12 text-lg font-bold text-press">−50</span> for accusing the truth
              </li>
              <li className="flex items-center gap-3">
                <span className="flex w-12 justify-start">
                  <SaltCrystal size={20} />
                </span>{' '}
                bonus for rare catches
              </li>
            </ul>
            <button ref={startRef} type="button" onClick={onStart} className={`${btnClass('primary', 'lg')} mt-6 min-h-16 w-full py-4 text-[22px]`}>
              <IconArrow size={22} /> Start
            </button>
          </section>
        </div>
      </main>
    </>
  )
}

function DailyPlay({ daily, playerId, onFinished }: { daily: DailyResponse; playerId: string; onFinished: (r: VerdictResponse) => void }) {
  const game = daily.case
  const posts = game.posts
  const reduced = useReducedMotion()
  const storeKey = `gos.daily.${playerId}.${game.id}`
  const [prog, setProg] = useState<Progress>(() => {
    const base = loadJSON<Progress>(storeKey) ?? { started: false, cards: {}, cluesLeft: game.clue_budget, evidence: {} }
    // The server is the source of truth for which cards are answered; local storage only adds crowd stats.
    if (daily.answered) {
      const cards: Record<string, CardRecord> = {}
      for (const [pid, r] of Object.entries(daily.answered)) {
        const local = base.cards[pid]
        cards[pid] = local?.reveal
          ? local
          : {
              doctored: r.outcome === 'caught' || r.outcome === 'false_alarm',
              trick: r.trick_named_correctly ? r.trick ?? null : null,
              reveal: { result: r, crowd: null },
              restored: true,
            }
      }
      base.cards = cards
      if (Object.keys(cards).length) base.started = true
    }
    if (typeof daily.clues_left === 'number') base.cluesLeft = daily.clues_left
    return base
  })
  const firstOpen = posts.findIndex((p) => !prog.cards[p.id])
  const [idx, setIdx] = useState(firstOpen === -1 ? posts.length - 1 : firstOpen)
  const [picker, setPicker] = useState(false)
  const [checkOpen, setCheckOpen] = useState(false)
  const [pending, setPending] = useState(false)
  const [busyTool, setBusyTool] = useState<ToolId | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [err, setErr] = useState<unknown>(null)
  const [flip, setFlip] = useState<'out' | 'in' | null>(null)
  const [finishing, setFinishing] = useState(false)
  const [finishErr, setFinishErr] = useState<unknown>(null)
  const nextBtn = useRef<HTMLButtonElement>(null)
  const nextBtnDesk = useRef<HTMLButtonElement>(null)
  // The sticky action bar changes height (Next / Real+Doctored / trick picker): pad the page by exactly that much.
  const [barRef, barH] = useElementHeight<HTMLDivElement>()

  useEffect(() => saveJSON(storeKey, prog), [storeKey, prog])

  const post = posts[idx]
  const rec = prog.cards[post.id]
  const answered = !!rec
  // First-time tip above card 1 ("How to spot the Con"), remembered per browser once dismissed or card 1 is answered.
  const [tipSeen, setTipSeen] = useState(() => loadJSON<boolean>('gos.tip.spot_the_con') === true)
  const dismissTip = () => {
    setTipSeen(true)
    saveJSON('gos.tip.spot_the_con', true)
  }
  useEffect(() => {
    if (idx === 0 && answered && !tipSeen) dismissTip()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idx, answered, tipSeen])
  const isLast = idx === posts.length - 1
  const opened = prog.evidence[post.id] ?? {}

  useEffect(() => {
    setPicker(false)
    setCheckOpen(false)
    setNotice(null)
    setErr(null)
  }, [idx])

  useEffect(() => {
    if (!answered || flip) return
    const desk = nextBtnDesk.current
    if (desk && desk.offsetParent !== null) {
      // Laptop: the button sits under the revealed card; bring it above the Con dock.
      desk.focus({ preventScroll: true })
      desk.scrollIntoView({ block: 'nearest', behavior: reduced ? 'auto' : 'smooth' })
    } else nextBtn.current?.focus({ preventScroll: true })
  }, [answered, flip, reduced])

  const answer = useCallback(
    async (doctored: boolean, trick: string | null) => {
      if (pending || answered) return
      setPending(true)
      setErr(null)
      setPicker(false)
      try {
        const res = await withPlayer((pid) => api.answer(game.id, pid, post.id, doctored, trick))
        const won = res.result.outcome === 'caught' || res.result.outcome === 'trusted'
        try {
          if (!reduced) navigator.vibrate?.(won ? 12 : [20, 40, 20])
        } catch {
          /* no vibration API */
        }
        // ~300ms flip: out 140ms, swap to the back, in 180ms. Sounds: paper flip, stamp thunk, then ding / bwomp.
        play('flip')
        if (!reduced) {
          setFlip('out')
          await new Promise((r) => window.setTimeout(r, 140))
        }
        setProg((p) => ({
          ...p,
          cards: { ...p.cards, [post.id]: { doctored, trick, reveal: res } },
          cluesLeft: typeof res.clues_left === 'number' ? res.clues_left : p.cluesLeft,
        }))
        play('thunk')
        window.setTimeout(() => play(won ? 'ding' : 'bwomp'), 140)
        if (!reduced) {
          setFlip('in')
          window.setTimeout(() => setFlip(null), 200)
        }
      } catch (e) {
        setFlip(null)
        if (e instanceof ApiError && e.status === 409) {
          setProg((p) => ({ ...p, cards: { ...p.cards, [post.id]: { doctored, trick, reveal: null, skipped: true } } }))
        } else setErr(e)
      } finally {
        setPending(false)
      }
    },
    [pending, answered, game.id, post.id, reduced],
  )

  const check = async (tool: ToolId) => {
    if (opened[tool] || busyTool) return
    setBusyTool(tool)
    setNotice(null)
    try {
      const res = await withPlayer((pid) => api.evidence(game.id, pid, post.id, tool))
      setProg((p) => ({
        ...p,
        evidence: { ...p.evidence, [post.id]: { ...p.evidence[post.id], [tool]: normalizeEvidence(tool, res.evidence) } },
        cluesLeft: typeof res.clues_left === 'number' ? res.clues_left : p.cluesLeft,
      }))
      setCheckOpen(false)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setProg((p) => ({ ...p, cluesLeft: 0 }))
        setNotice('Out of magnifiers for today. Trust your eye, or your doubt.')
      } else if (e instanceof ApiError && e.backendDown) setNotice(`The game server isn’t answering. Start it with: ${BACKEND_START_CMD}`)
      else setNotice(e instanceof Error ? e.message : 'Couldn’t open that evidence.')
    } finally {
      setBusyTool(null)
    }
  }

  const finish = async () => {
    setFinishing(true)
    setFinishErr(null)
    try {
      const res = await withPlayer((pid) => api.finishDaily(game.id, pid))
      onFinished(res)
    } catch (e) {
      setFinishErr(e)
    } finally {
      setFinishing(false)
    }
  }

  const next = () => {
    if (isLast) finish()
    else setIdx((i) => Math.min(posts.length - 1, i + 1))
  }

  // Keyboard: R real · D doctored · 1–4 trick · C check · Enter/→ next · Esc closes the picker.
  const choices = trickChoices(game.trick_options)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || !prog.started) return
      const t = e.target as HTMLElement | null
      if (t?.closest('input, textarea, select')) return
      const k = e.key.toLowerCase()
      if (answered) {
        if ((k === 'enter' && t?.tagName !== 'BUTTON') || k === 'arrowright') {
          e.preventDefault()
          next()
        }
        return
      }
      if (k === 'r') answer(false, null)
      else if (k === 'd') setPicker(true)
      else if (k === 'escape') setPicker(false)
      else if (k === 'c') setCheckOpen((o) => !o)
      else if (picker && /^[1-9]$/.test(k)) {
        const trick = choices[Number(k) - 1]
        if (trick) answer(true, trick)
      } else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (!prog.started) return <DailyBriefing daily={daily} onStart={() => setProg((p) => ({ ...p, started: true }))} />

  const flipClass = flip === 'out' ? 'flip-out' : flip === 'in' ? 'flip-in' : ''

  const nextLabel = finishing ? 'Tallying…' : isLast ? 'See your results' : 'Next card'

  return (
    <>
    <DailyBar daily={daily} cluesLeft={prog.cluesLeft} />
    <main
      className="mx-auto flex w-full max-w-lg flex-1 flex-col px-4 pt-3 lg:grid lg:max-w-[1360px] lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] lg:items-start lg:gap-8 lg:px-6 lg:pt-6"
      style={{ paddingBottom: Math.max(barH, 96) + 20 }}
    >
      {/* Laptop (Figma "Case — Investigation"): tabs, the card and its answer buttons on the left, the Evidence Kit
          on the right, the Con on an ink dock. Phones: dots, the card, inline Check and the sticky bar. */}
      <section className="min-w-0" aria-label="Today’s card">
        <div className="lg:mx-auto lg:max-w-[680px]">
          <div className="lg:hidden">
            <ProgressDots posts={posts} cards={prog.cards} current={idx} />
            <p className="dateline mt-2 text-center">
              Card {idx + 1} of {posts.length}
            </p>
          </div>
          <CardTabs posts={posts} cards={prog.cards} current={idx} className="hidden lg:grid" />
          <p className="mt-3 hidden bg-press-wash px-3 py-2.5 text-center text-[17px] text-press italic lg:block">
            {DAILY_RANGE}. Maybe none.
          </p>

          {idx === 0 && !answered && !tipSeen && (
            <aside
              className="mt-3 border-2 border-ink bg-sheet px-4 py-3 text-[14.5px] leading-relaxed shadow-[var(--hard)]"
              aria-label="How to spot the Con"
            >
              <div className="flex items-start justify-between gap-3">
                <p>
                  <span className="caps mr-1 text-[12.5px] font-semibold tracking-[0.08em] text-press">How to spot the Con:</span>
                  who posted it? Does a real outlet back it up? Does it sound too neat?
                </p>
                <button type="button" onClick={dismissTip} aria-label="Dismiss tip" className="shrink-0 px-1 text-xl leading-none text-muted hover:text-ink">
                  ×
                </button>
              </div>
            </aside>
          )}

          <div key={post.id} className="card-in mt-4">
            <div className={flipClass} style={{ transformOrigin: 'center' }}>
              {answered ? (
                <CardBack post={post} rec={rec} caseNumber={game.number} />
              ) : (
                <div className="flex flex-col gap-3">
                  <FeedCard post={post} caseNumber={game.number} size="daily" />

                  {/* Check: one evidence view, inline (phones; laptops use the Evidence Kit panel) */}
                  <div className="flex flex-col gap-3 lg:hidden">
                    <div className="mt-1 flex flex-wrap items-center gap-3">
                      <button
                        type="button"
                        aria-expanded={checkOpen}
                        onClick={() => setCheckOpen((o) => !o)}
                        className={`press inline-flex items-center gap-2.5 border-2 border-ink px-3.5 py-2 shadow-[var(--hard)] ${
                          checkOpen ? 'bg-sheet text-ink' : 'bg-ink text-sheet hover:bg-[#2a2a2a]'
                        }`}
                      >
                        <IconLens size={18} />
                        <span className="caps text-[16px] font-bold">Check</span>
                        <span className={`num caps text-[12.5px] font-semibold ${checkOpen ? 'text-press' : 'text-press-soft'}`}>{prog.cluesLeft} left</span>
                      </button>
                      <Magnifiers left={prog.cluesLeft} total={game.clue_budget} />
                    </div>
                    {checkOpen && (
                      <div className="rise-in flex flex-col gap-2.5" role="group" aria-label="Pick one evidence tool">
                        {TOOLS.map((t) => {
                          const has = post.tools?.includes(t.id)
                          const isOpen = !!opened[t.id]
                          const out = prog.cluesLeft <= 0 && !isOpen
                          return (
                            <ToolRow
                              key={t.id}
                              icon={t.icon}
                              label={t.label}
                              sub={!has ? 'Nothing to check here' : out ? 'Out of magnifiers today' : t.blurb}
                              state={isOpen ? 'open' : !has ? 'na' : out ? 'out' : 'ready'}
                              busy={busyTool === t.id}
                              disabled={!has || out || busyTool != null}
                              onClick={() => check(t.id)}
                              title={!has ? 'Nothing to check with this tool here' : out ? 'Out of magnifiers today' : isOpen ? 'Already open (free)' : 'Costs one magnifier'}
                              compact
                            />
                          )
                        })}
                      </div>
                    )}
                    {notice && (
                      <p role="alert" className="border-2 border-ochre bg-press-wash px-3 py-2 text-sm">
                        {notice}
                      </p>
                    )}
                    {TOOLS.filter((t) => opened[t.id]).map((t) => (
                      <EvidenceInline key={t.id} tool={t.id} ev={opened[t.id]!} />
                    ))}
                  </div>
                  {err != null && <ErrorState error={err} onRetry={() => setErr(null)} title="That answer didn’t go through." />}
                </div>
              )}
            </div>
          </div>

          {/* Laptop: answer right under the card (phones use the sticky bar below) */}
          <div className="mt-5 hidden lg:block">
            {answered ? (
              <>
                {finishErr != null && (
                  <div className="mb-2">
                    <ErrorState error={finishErr} onRetry={finish} title="Couldn’t close today’s Grain." />
                  </div>
                )}
                <button
                  ref={nextBtnDesk}
                  type="button"
                  onClick={next}
                  disabled={finishing}
                  className={`${btnClass('primary', 'lg')} w-full py-4 text-xl`}
                >
                  {!finishing && <IconArrow size={22} />}
                  {nextLabel}
                </button>
              </>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    disabled={pending}
                    onClick={() => answer(false, null)}
                    className="press caps flex items-center justify-center gap-2 border-2 border-ink bg-sheet py-3.5 text-[22px] font-bold text-ink shadow-[var(--hard)] hover:bg-surface-2 disabled:opacity-60"
                  >
                    <IconCheck size={24} strokeWidth={2.6} /> Real
                  </button>
                  <button
                    type="button"
                    disabled={pending}
                    aria-pressed={picker}
                    onClick={() => setPicker((o) => !o)}
                    className={`press caps flex items-center justify-center gap-2 border-2 border-press py-3.5 text-[22px] font-bold shadow-[var(--hard)] disabled:opacity-60 ${
                      picker ? 'bg-press text-white' : 'bg-sheet text-press hover:bg-press/[0.06]'
                    }`}
                  >
                    <IconX size={24} strokeWidth={2.6} /> Doctored
                  </button>
                </div>
                {picker && (
                  <TrickPicker
                    options={choices}
                    onPick={(t) => answer(true, t)}
                    disabled={pending}
                    columns={2}
                    notSureLabel="Just doctored, not sure how"
                    className="rise-in mt-4"
                  />
                )}
              </>
            )}
            {pending && (
              <p className="dateline mt-3 text-center !text-[11px]" aria-live="polite">
                Checking…
              </p>
            )}
          </div>
          {game.notice && <p className="dateline mt-5 text-center normal-case">{game.notice}</p>}
        </div>
      </section>

      <aside className="hidden min-w-0 pl-6 lg:block" aria-label="Evidence Kit">
        {/* The rip: the kit's column sits on torn black paper, the tear running down the gap between the columns.
            Fixed, but left at its static spot (the kit's edge). Only the near-vertical top half of the tear is used. */}
        <div aria-hidden="true" className="pointer-events-none fixed inset-y-0 -z-[5] -ml-[80px] hidden w-[100vw] overflow-hidden lg:flex">
          <img src={tornV} alt="" draggable={false} className="h-[200vh] w-[400px] max-w-none shrink-0 -scale-x-100 select-none" />
          <div className="-ml-px flex-1 bg-night" />
        </div>
        <div className="panel thin-scroll sticky top-[88px] flex max-h-[calc(100vh-88px-24px)] flex-col gap-4 overflow-y-auto p-5">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-head text-[30px] leading-none font-bold">Evidence Kit</h2>
            <span className="flex items-center gap-2">
              <Magnifiers left={prog.cluesLeft} total={game.clue_budget} />
              <span className="num caps text-[12.5px] font-semibold text-press">{prog.cluesLeft} left</span>
            </span>
          </div>
          <p className="caps -mt-1 text-[12.5px] font-semibold tracking-[0.06em] text-press">
            Card {idx + 1} {answered ? 'answered' : 'selected'}
          </p>
          {answered ? (
            <p className="text-[14px] leading-snug text-muted">Answered.</p>
          ) : (
            <div className="flex flex-col gap-2.5" role="group" aria-label="Pick one evidence tool">
              {TOOLS.map((t) => {
                const has = post.tools?.includes(t.id)
                const isOpen = !!opened[t.id]
                const out = prog.cluesLeft <= 0 && !isOpen
                return (
                  <ToolRow
                    key={t.id}
                    icon={t.icon}
                    label={t.label}
                    sub={!has ? 'Nothing to check here' : out ? 'Out of magnifiers today' : t.blurb}
                    state={isOpen ? 'open' : !has ? 'na' : out ? 'out' : 'ready'}
                    busy={busyTool === t.id}
                    disabled={!has || out || busyTool != null}
                    onClick={() => check(t.id)}
                    title={!has ? 'Nothing to check with this tool here' : out ? 'Out of magnifiers today' : isOpen ? 'Already open (free)' : 'Costs one magnifier'}
                  />
                )
              })}
            </div>
          )}
          {notice && (
            <p role="alert" className="border-2 border-ochre bg-press-wash px-3 py-2 text-sm">
              {notice}
            </p>
          )}
          {TOOLS.filter((t) => opened[t.id]).map((t) => (
            <EvidenceInline key={t.id} tool={t.id} ev={opened[t.id]!} />
          ))}
        </div>
      </aside>

      {/* Phones: the trick picker opens as a bottom sheet over the card. */}
      {picker && !answered && (
        <button type="button" aria-label="Close the trick picker" className="fade-in fixed inset-0 z-10 bg-ink/45 lg:hidden" onClick={() => setPicker(false)} />
      )}

      {/* Phones: sticky action bar */}
      <div
        ref={barRef}
        className={`fixed inset-x-0 bottom-0 z-20 bg-sheet px-4 pb-[max(12px,env(safe-area-inset-bottom))] lg:hidden ${
          picker && !answered ? 'border-t-[3px] border-press pt-2' : 'border-t-[3px] border-ink pt-3'
        }`}
      >
        <div className="mx-auto max-w-lg">
          {answered ? (
            <>
              {finishErr != null && (
                <div className="mb-2">
                  <ErrorState error={finishErr} onRetry={finish} title="Couldn’t close today’s Grain." />
                </div>
              )}
              <button ref={nextBtn} type="button" onClick={next} disabled={finishing} className={`${btnClass('primary', 'lg')} w-full py-4 text-xl`}>
                {!finishing && <IconArrow size={22} />}
                {nextLabel}
              </button>
            </>
          ) : picker ? (
            <div className="sheet-up">
              <div className="flex justify-center pb-2" aria-hidden="true">
                <span className="h-1.5 w-12 bg-[#a8a8a8]" />
              </div>
              <button type="button" className="caps mb-2 inline-flex items-center gap-1 text-[13px] font-bold text-ink hover:underline" onClick={() => setPicker(false)}>
                <IconArrowLeft size={15} /> Back
              </button>
              <TrickPicker options={choices} onPick={(t) => answer(true, t)} disabled={pending} notSureLabel="Just doctored, not sure how" className="pb-2" />
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                disabled={pending}
                onClick={() => answer(false, null)}
                className="press caps flex items-center justify-center gap-2 border-2 border-ink bg-sheet py-4 text-[22px] font-bold text-ink shadow-[var(--hard)] hover:bg-surface-2 disabled:opacity-60"
              >
                <IconCheck size={24} strokeWidth={2.6} /> Real
              </button>
              <button
                type="button"
                disabled={pending}
                onClick={() => setPicker(true)}
                className="press caps flex items-center justify-center gap-2 border-2 border-press bg-sheet py-4 text-[22px] font-bold text-press shadow-[var(--hard)] hover:bg-press/[0.06] disabled:opacity-60"
              >
                <IconX size={24} strokeWidth={2.6} /> Doctored
              </button>
              <p className="dateline col-span-2 -mt-0.5 text-center !text-[11px]" aria-live="polite">
                {pending ? 'Checking…' : null}
              </p>
            </div>
          )}
        </div>
      </div>

    </main>
    </>
  )
}

/** In play: the slim case bar (logo | Grain No. and title | checks, Home, sound), same as a Case File. */
function DailyBar({ daily, cluesLeft }: { daily: DailyResponse; cluesLeft: number }) {
  return (
    <BarHeader
      right={
        <>
          <span className="hidden flex-col items-start gap-0.5 md:flex">
            <span className="caps text-[11px] font-semibold tracking-[0.1em] text-muted">Checks</span>
            <Magnifiers left={cluesLeft} total={daily.case.clue_budget} />
          </span>
          <a href="#/" className="caps ml-2 px-1.5 py-1 text-[13px] font-bold text-ink hover:underline">
            Home
          </a>
          <SoundToggle className="-mr-1.5" />
        </>
      }
    >
      <div className="min-w-0 leading-tight">
        <p className="caps truncate text-[11.5px] font-semibold tracking-[0.08em] text-muted">
          Grain #{daily.daily_number}
          {daily.theme && <>, {daily.theme}</>}
        </p>
        <p className="truncate text-[17px] italic sm:text-[19px]">{daily.case.title}</p>
      </div>
    </BarHeader>
  )
}

export function DailyScreen() {
  const data = useAsync(async () => withPlayer(async (pid) => ({ daily: await api.daily(pid), pid })), [])
  const [result, setResult] = useState<VerdictResponse | null>(null)

  const daily = data.status === 'ok' ? data.data.daily : null
  const finalResult = result ?? (daily?.already_played ? daily.result ?? null : null)

  useEffect(() => {
    if (result) window.scrollTo({ top: 0 })
  }, [result])

  return (
    <>
      {/* The site header everywhere but mid-game (the briefing and the play view bring their own). */}
      {!(data.status === 'ok' && daily && !finalResult && !daily.already_played) && <SiteHeader active="daily" />}
      {data.status === 'loading' && <Loading label="Shaking out today’s Grain…" className="flex-1" />}
      {data.status === 'error' && (
        <main className="flex flex-1 items-center px-4 py-16">
          {data.error instanceof ApiError && data.error.status === 404 ? (
            <div className="paper-card mx-auto max-w-md bg-white/90 p-6 text-center">
              <h1 className="font-display text-3xl font-bold">No Grain today yet.</h1>
              <p className="mt-2 text-sm text-muted">The Con is still preparing today’s puzzle. Try a Case File or Con the Con meanwhile.</p>
              <div className="mt-5 flex justify-center gap-3">
                <a href="#/con" className={btnClass('primary')}>
                  <IconMask size={20} /> Con the Con
                </a>
                <a href="#/casefiles" className={btnClass('secondary')}>
                  Case Files
                </a>
              </div>
            </div>
          ) : (
            <ErrorState error={data.error} onRetry={data.reload} title="Couldn’t open today’s Grain." />
          )}
        </main>
      )}
      {data.status === 'ok' &&
        daily &&
        (finalResult ? (
          <DailyEnd daily={daily} result={finalResult} alreadyPlayed={!result} />
        ) : daily.already_played ? (
          <main className="mx-auto max-w-md px-4 py-16 text-center">
            <p className="font-display text-2xl font-bold">You’ve already played today’s Grain.</p>
            <p className="mt-1 text-muted">Come back tomorrow for #{daily.daily_number + 1}.</p>
            <Button className="mt-4" variant="primary" onClick={() => navigate('/con')}>
              Con the Con meanwhile →
            </Button>
          </main>
        ) : (
          <DailyPlay daily={daily} playerId={data.data.pid} onFinished={setResult} />
        ))}
    </>
  )
}
