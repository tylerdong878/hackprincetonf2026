import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ConMascot } from '../components/Art'
import { ConBubble } from '../components/ConBubble'
import { AccountView, DataView, normalizeEvidence, SourceView, ToolRow, TOOLS } from '../components/EvidenceKit'
import { Brand, SoundToggle } from '../components/Header'
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
                    : 'border-[1.5px] border-dashed border-[#B9AE99] text-muted'
                }`}
              >
                {rec?.skipped ? '·' : i + 1}
              </span>
            )}
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
      <p className="flex items-start gap-2 border-[1.5px] border-dashed border-[#B9AE99] px-3 py-2 text-sm text-muted">
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
        <b className="num">{realPct}%</b> said Real · <b className="num">{doctoredPct}%</b> said Doctored
        <span className="font-normal text-muted">
          {' '}
          · <span className="num">{crowd.n}</span> detectives
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
        {r.doctored ? <>Doctored · {trickLabel(r.trick)}</> : r.suspicious_real ? <>Real · sounds fake, isn’t</> : <>Real</>}
      </p>
      <p className="text-[15px] text-muted">
        You said <span className="font-bold text-ink">{you}</span>
        {r.trick_named_correctly && <span className="font-bold text-ink"> · named the trick (+50)</span>}
      </p>

      {(r.tell || r.explanation) && (
        <p className={`mt-3 border-l-4 pl-3 text-[16px] leading-snug font-bold ${r.doctored ? 'border-press' : 'border-ink'}`}>
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
        <ConMascot size={48} shape="circle" className="mt-1 shrink-0" />
        <ConBubble text={quip} size="md" speed={14} className="min-w-0 flex-1" />
      </div>

      {!rec.restored && (
        <div className="mt-5 border-t border-[#CFC6B4] pt-4">
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
    <main className="mx-auto flex w-full max-w-lg flex-1 flex-col gap-6 px-4 py-6">
      <div className="flex items-end gap-4">
        <ConMascot size={150} shape="door" className="shrink-0" />
        <ConBubble text={c.briefing} size="md" className="mb-2 min-w-0 flex-1" onDone={() => startRef.current?.focus({ preventScroll: true })} />
      </div>
      <section className="folder-open panel p-5 sm:p-6" aria-labelledby="grain-h">
        <div className="flex items-baseline justify-between gap-3">
          <p className="dateline font-bold !text-ink">{shortDate(`${daily.date}T12:00:00`)}</p>
        </div>
        <div className="double-rule mt-2" aria-hidden="true" />
        <h1 id="grain-h" className="logotype mt-4 text-[44px] text-ink sm:text-5xl">
          Grain of Salt #{daily.daily_number}
        </h1>
        {daily.theme && <p className="caps mt-3 inline-flex bg-ink px-3 py-1 text-[13px] font-semibold text-sheet">{daily.theme}</p>}
        <p className="mt-3 font-head text-[26px] leading-tight font-bold">{c.title}</p>
        <ul className="mt-5 grid grid-cols-3 gap-2 border-y-2 border-dotted border-[#8C8270] py-4 text-center">
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
        <p className="mt-5 border-2 border-press bg-[#F8E2DC] px-4 py-3 text-center text-[18px] text-press italic">{DAILY_RANGE}. Maybe none.</p>
        <ul className="mt-4 flex flex-col gap-1.5 text-[15px]" aria-label="+100 per right call · −50 for accusing the truth · bonus for rare catches">
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
        <button ref={startRef} type="button" onClick={onStart} className={`${btnClass('ink', 'lg')} mt-6 w-full py-4 text-xl`}>
          <IconArrow size={22} /> Start
        </button>
      </section>
    </main>
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
  // The sticky action bar changes height (Next / Real+Doctored / trick picker): pad the page by exactly that much.
  const [barRef, barH] = useElementHeight<HTMLDivElement>()

  useEffect(() => saveJSON(storeKey, prog), [storeKey, prog])

  const post = posts[idx]
  const rec = prog.cards[post.id]
  const answered = !!rec
  const isLast = idx === posts.length - 1
  const opened = prog.evidence[post.id] ?? {}

  useEffect(() => {
    setPicker(false)
    setCheckOpen(false)
    setNotice(null)
    setErr(null)
  }, [idx])

  useEffect(() => {
    if (answered && !flip) nextBtn.current?.focus({ preventScroll: true })
  }, [answered, flip])

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

  return (
    <main className="mx-auto flex w-full max-w-lg flex-1 flex-col px-4 pt-3" style={{ paddingBottom: Math.max(barH, 96) + 20 }}>
      <ProgressDots posts={posts} cards={prog.cards} current={idx} />
      <p className="dateline mt-2 text-center">
        Card {idx + 1} of {posts.length} · {DAILY_RANGE}
      </p>

      <div key={post.id} className="card-in mt-4">
        <div className={flipClass} style={{ transformOrigin: 'center' }}>
          {answered ? (
            <CardBack post={post} rec={rec} caseNumber={game.number} />
          ) : (
            <div className="flex flex-col gap-3">
              <FeedCard post={post} caseNumber={game.number} size="daily" />

              {/* Check: one evidence view, inline */}
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
                <p role="alert" className="border-2 border-ochre bg-[#F3E3C2] px-3 py-2 text-sm">
                  {notice}
                </p>
              )}
              {TOOLS.filter((t) => opened[t.id]).map((t) => (
                <EvidenceInline key={t.id} tool={t.id} ev={opened[t.id]!} />
              ))}
              {err != null && <ErrorState error={err} onRetry={() => setErr(null)} title="That answer didn’t go through." />}
            </div>
          )}
        </div>
      </div>
      {game.notice && <p className="dateline mt-5 text-center normal-case">{game.notice}</p>}

      {/* The trick picker opens as a bottom sheet over the card. */}
      {picker && !answered && (
        <button type="button" aria-label="Close the trick picker" className="fade-in fixed inset-0 z-10 bg-ink/45" onClick={() => setPicker(false)} />
      )}

      {/* Sticky action bar */}
      <div
        ref={barRef}
        className={`fixed inset-x-0 bottom-0 z-20 bg-sheet px-4 pb-[max(12px,env(safe-area-inset-bottom))] ${
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
              <button
                ref={nextBtn}
                type="button"
                onClick={next}
                disabled={finishing}
                className={`${btnClass('primary', 'lg')} w-full py-4 text-xl`}
              >
                {!finishing && <IconArrow size={22} />}
                {finishing ? 'Tallying…' : isLast ? 'See your results' : 'Next card'}
              </button>
            </>
          ) : picker ? (
            <div className="sheet-up">
              <div className="flex justify-center pb-2" aria-hidden="true">
                <span className="h-1.5 w-12 bg-[#B9AE99]" />
              </div>
              <button
                type="button"
                className="caps mb-2 inline-flex items-center gap-1 text-[13px] font-bold text-ink hover:underline"
                onClick={() => setPicker(false)}
              >
                <IconArrowLeft size={15} /> Back
              </button>
              <TrickPicker
                options={choices}
                onPick={(t) => answer(true, t)}
                disabled={pending}
                notSureLabel="Just doctored, not sure how"
                className="pb-2"
              />
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
                {pending ? 'Checking with the case file…' : <span className="hidden md:inline">Keys: R real · D doctored · C check</span>}
              </p>
            </div>
          )}
        </div>
      </div>
    </main>
  )
}

function DailyTopBar({ daily }: { daily: DailyResponse | null }) {
  return (
    <header className="sticky top-0 z-30 bg-sheet">
      <div className="mx-auto flex min-h-[64px] max-w-lg items-center gap-3 px-4 py-2">
        <div className="min-w-0 flex-1">
          <Brand size={27} />
          <p className="dateline mt-0.5 truncate !text-[12px]">
            {daily ? <>No. {daily.daily_number}</> : 'The Daily Grain'}
            {daily?.theme && <> · {daily.theme}</>}
          </p>
        </div>
        <a href="#/" className="caps px-1.5 py-1 text-[13px] font-bold text-ink hover:underline">
          Home
        </a>
        <SoundToggle className="-mr-1.5" />
      </div>
      <div className="double-rule" aria-hidden="true" />
    </header>
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
      <DailyTopBar daily={daily} />
      {data.status === 'loading' && <Loading label="Shaking out today’s Grain…" className="flex-1" />}
      {data.status === 'error' && (
        <main className="flex flex-1 items-center px-4 py-16">
          {data.error instanceof ApiError && data.error.status === 404 ? (
            <div className="panel mx-auto max-w-md p-6 text-center">
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
          <main className="mx-auto max-w-md px-4 py-10 text-center">
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
