import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ConMascot } from '../components/Art'
import { ConBubble } from '../components/ConBubble'
import { AccountView, DataView, normalizeEvidence, SourceView, TOOLS } from '../components/EvidenceKit'
import { Brand } from '../components/Header'
import { FeedCard } from '../components/PostCard'
import { MiniDiff, OutcomeBadge } from '../components/Reveal'
import { Button, ErrorState, Loading } from '../components/ui'
import { api, ApiError, BACKEND_START_CMD } from '../lib/api'
import { CON_QUIPS, pick } from '../lib/content'
import { outcomeStyle, shortDate, trickLabel } from '../lib/format'
import { useAsync, useReducedMotion } from '../lib/hooks'
import { withPlayer } from '../lib/player'
import { navigate } from '../lib/router'
import type {
  AccountEvidence,
  AnswerResponse,
  AnyEvidence,
  DailyResponse,
  DataEvidence,
  Post,
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
          className="burst-grain absolute rounded-[2px] border border-[#12141C]/40 bg-white"
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
    <ol className="flex items-center justify-center gap-2" aria-label="Today’s cards">
      {posts.map((p, i) => {
        const rec = cards[p.id]
        const outcome = rec?.reveal?.result.outcome
        const label = outcome ? outcomeStyle(outcome).word : rec?.skipped ? 'answered earlier' : i === current ? 'current card' : 'not played yet'
        return (
          <li key={p.id} aria-label={`Card ${i + 1}: ${label}`} aria-current={i === current ? 'step' : undefined}>
            {outcome ? (
              <span className="pop flex h-8 w-8 items-center justify-center text-xl leading-none">{outcomeStyle(outcome).emoji}</span>
            ) : (
              <span
                className={`flex h-8 w-8 items-center justify-center rounded-full border-2 font-mono text-xs font-semibold ${
                  i === current ? 'border-con bg-con/15 text-text' : 'border-line text-muted'
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
    <span className="inline-flex items-center gap-0.5" role="img" aria-label={`${left} of ${total} checks left`}>
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={i < left ? '' : 'opacity-25 grayscale'} aria-hidden="true">
          🔍
        </span>
      ))}
    </span>
  )
}

function CrowdLine({ reveal }: { reveal: AnswerResponse }) {
  const crowd = reveal.crowd
  const rarity = reveal.rarity ?? reveal.result.rarity ?? null
  if (!crowd) {
    return (
      <p className="rounded-xl border border-dashed border-line px-3 py-2 text-sm text-muted">
        🕵️ Be one of the first 10 detectives to answer this one. Crowd stats unlock at 10.
      </p>
    )
  }
  const doctoredPct = Math.round(crowd.said_doctored_pct)
  const realPct = 100 - doctoredPct
  const correct = Math.round(rarity?.correct_pct ?? crowd.correct_pct)
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex h-3 overflow-hidden rounded-full bg-surface-2" aria-hidden="true">
        <span className="h-full bg-real" style={{ width: `${realPct}%` }} />
        <span className="h-full bg-doctored" style={{ width: `${doctoredPct}%` }} />
      </div>
      <p className="text-sm">
        <b className="font-mono">{realPct}%</b> said Real · <b className="font-mono">{doctoredPct}%</b> said Doctored
        <span className="text-muted"> · {crowd.n} detectives</span>
      </p>
      <p className="text-sm font-semibold" style={{ color: correct < 50 ? 'var(--con)' : 'var(--muted)' }}>
        {correct < 50 ? `Only ${correct}% got this right.` : `${correct}% got this right.`}
      </p>
    </div>
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
      <div className="rounded-2xl border-2 border-line bg-surface p-5 text-center">
        <p className="font-display text-lg font-semibold">You answered this card earlier.</p>
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
      className={`relative overflow-hidden rounded-2xl border-2 bg-surface p-4 sm:p-5 ${!win ? 'shake' : ''}`}
      style={{ borderColor: s.color }}
      aria-live="polite"
    >
      {win && <SaltBurst />}
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xl sm:text-2xl">
          <OutcomeBadge outcome={r.outcome} />
        </span>
        <span
          className="pop ml-auto font-mono text-2xl font-semibold tabular-nums"
          style={{ color: pts > 0 ? 'var(--real)' : pts < 0 ? 'var(--doctored)' : 'var(--muted)' }}
        >
          {pts > 0 ? `+${pts}` : pts < 0 ? `−${Math.abs(pts)}` : '0'}
        </span>
      </div>
      <p className="mt-2 font-display text-lg font-semibold">
        {r.doctored ? <>Doctored · {trickLabel(r.trick)}</> : r.suspicious_real ? <>Real · sounds fake, isn’t</> : <>Real</>}
      </p>
      <p className="text-sm text-muted">
        You said <span className="font-semibold text-text">{you}</span>
        {r.trick_named_correctly && <span className="font-semibold text-real"> · named the trick (+50)</span>}
      </p>

      {(r.tell || r.explanation) && (
        <p className="mt-3 text-[15px]">
          {r.doctored ? <b className="font-display">The tell: </b> : <b className="font-display text-real">✓ Checks out: </b>}
          {r.tell || r.explanation}
        </p>
      )}

      {r.doctored && r.diff && (
        <div className="mt-3">
          <MiniDiff diff={r.diff} post={post} />
        </div>
      )}

      <div className="mt-4 flex items-end gap-2.5">
        <ConMascot size={40} className="shrink-0" />
        <ConBubble text={quip} size="sm" speed={14} className="min-w-0 flex-1" />
      </div>

      {!rec.restored && (
        <div className="mt-4">
          <CrowdLine reveal={reveal} />
        </div>
      )}
    </div>
  )
}

function EvidenceInline({ tool, ev }: { tool: ToolId; ev: AnyEvidence }) {
  const t = TOOLS.find((x) => x.id === tool)
  return (
    <section className="fade-in" aria-label={`${t?.label} evidence`}>
      <p className="mb-1.5 text-[11px] font-bold tracking-[0.16em] text-muted uppercase">
        {t?.icon} {t?.label}
      </p>
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
    <main className="mx-auto flex w-full max-w-lg flex-1 flex-col gap-5 px-4 py-6">
      <div className="flex items-end gap-3">
        <ConMascot size={96} shape="door" className="shrink-0" />
        <ConBubble text={c.briefing} size="md" className="min-w-0 flex-1" onDone={() => startRef.current?.focus({ preventScroll: true })} />
      </div>
      <section className="folder-open paper-texture rounded-2xl p-6 shadow-[0_24px_60px_-20px_rgba(0,0,0,0.6)]" aria-labelledby="grain-h">
        <p className="font-mono text-xs font-semibold tracking-[0.18em] text-[#6B5E45] uppercase">{shortDate(`${daily.date}T12:00:00`)}</p>
        <h1 id="grain-h" className="mt-1 font-display text-4xl font-bold">
          Grain of Salt #{daily.daily_number}
        </h1>
        {daily.theme && (
          <p className="mt-1 inline-flex rounded-full bg-[#12141C] px-3 py-1 text-sm font-semibold text-[#EFE4CC]">{daily.theme}</p>
        )}
        <p className="mt-3 text-[15px] text-[#4B4232]">{c.title}</p>
        <ul className="mt-5 grid grid-cols-3 gap-2 border-y border-dashed border-[#B9A985] py-4 text-center">
          <li>
            <span className="block font-mono text-2xl font-semibold">{c.posts.length}</span>
            <span className="text-xs text-[#6B5E45]">cards</span>
          </li>
          <li>
            <span className="block text-xl" aria-hidden="true">
              {'🔍'.repeat(Math.min(5, c.clue_budget))}
            </span>
            <span className="text-xs text-[#6B5E45]">{c.clue_budget} checks</span>
          </li>
          <li>
            <span className="block font-mono text-2xl font-semibold">0–3</span>
            <span className="text-xs text-[#6B5E45]">doctored</span>
          </li>
        </ul>
        <p className="mt-4 rounded-xl border-2 border-[#2A2418] px-4 py-2.5 text-center font-con text-lg">{DAILY_RANGE}. Maybe none.</p>
        <p className="mt-3 text-center text-[13px] text-[#4B4232]">
          +100 per right call · −50 for accusing the truth · +20 per unused check
        </p>
        <button
          ref={startRef}
          type="button"
          onClick={onStart}
          className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[#12141C] px-6 py-4 font-display text-xl font-semibold text-[#EFE4CC] transition hover:bg-black active:scale-[0.98]"
        >
          Start <span aria-hidden="true">→</span>
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
        try {
          if (!reduced) navigator.vibrate?.(res.result.outcome === 'caught' || res.result.outcome === 'trusted' ? 12 : [20, 40, 20])
        } catch {
          /* no vibration API */
        }
        if (!reduced) {
          setFlip('out')
          await new Promise((r) => window.setTimeout(r, 160))
        }
        setProg((p) => ({
          ...p,
          cards: { ...p.cards, [post.id]: { doctored, trick, reveal: res } },
          cluesLeft: typeof res.clues_left === 'number' ? res.clues_left : p.cluesLeft,
        }))
        if (!reduced) {
          setFlip('in')
          window.setTimeout(() => setFlip(null), 300)
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
    <main className="mx-auto flex w-full max-w-lg flex-1 flex-col px-4 pt-3 pb-40">
      <ProgressDots posts={posts} cards={prog.cards} current={idx} />
      <p className="mt-1 text-center text-xs text-muted">
        Card {idx + 1} of {posts.length} · {DAILY_RANGE}
      </p>

      <div key={post.id} className="card-in mt-3">
        <div className={flipClass} style={{ transformOrigin: 'center' }}>
          {answered ? (
            <CardBack post={post} rec={rec} caseNumber={game.number} />
          ) : (
            <div className="flex flex-col gap-3">
              <FeedCard post={post} caseNumber={game.number} size="daily" />

              {/* 🔍 Check: one evidence view, inline */}
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  aria-expanded={checkOpen}
                  onClick={() => setCheckOpen((o) => !o)}
                  className={`inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-sm font-semibold transition ${
                    checkOpen ? 'border-focus bg-focus/10' : 'border-line bg-surface hover:border-muted'
                  }`}
                >
                  🔍 Check <span className="font-mono text-xs text-muted">{prog.cluesLeft} left</span>
                </button>
                <Magnifiers left={prog.cluesLeft} total={game.clue_budget} />
              </div>
              {checkOpen && (
                <div className="rise-in grid gap-2 sm:grid-cols-3" role="group" aria-label="Pick one evidence tool">
                  {TOOLS.map((t) => {
                    const has = post.tools?.includes(t.id)
                    const isOpen = !!opened[t.id]
                    const out = prog.cluesLeft <= 0 && !isOpen
                    return (
                      <button
                        key={t.id}
                        type="button"
                        disabled={!has || out || busyTool != null}
                        onClick={() => check(t.id)}
                        title={!has ? 'Nothing to check with this tool here' : out ? 'Out of magnifiers today' : isOpen ? 'Already open (free)' : 'Costs one magnifier'}
                        className="flex items-center gap-2 rounded-xl border border-line bg-surface-2 px-3 py-2.5 text-left text-sm font-semibold transition hover:border-muted disabled:opacity-45"
                      >
                        <span aria-hidden="true">{t.icon}</span>
                        <span className="min-w-0 flex-1">{t.label}</span>
                        <span className="font-mono text-[11px] text-muted">{busyTool === t.id ? '…' : isOpen ? 'open' : has ? '−1🔍' : '—'}</span>
                      </button>
                    )
                  })}
                </div>
              )}
              {notice && (
                <p role="alert" className="rounded-xl border border-alarm/50 bg-alarm/10 px-3 py-2 text-sm">
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

      {/* Sticky action bar */}
      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-bg/95 px-4 pt-3 pb-[max(12px,env(safe-area-inset-bottom))] backdrop-blur">
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
                className="flex w-full items-center justify-center gap-2 rounded-2xl bg-con py-4 font-display text-xl font-semibold text-on-accent shadow-[0_10px_30px_-12px_var(--con)] transition hover:brightness-110 active:scale-[0.98] disabled:opacity-60"
              >
                {finishing ? 'Tallying…' : isLast ? 'See your results' : 'Next card'} <span aria-hidden="true">→</span>
              </button>
            </>
          ) : picker ? (
            <div className="rise-in" role="group" aria-label="What’s the trick?">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-sm font-semibold">What’s the trick? <span className="text-muted">(+50 if right)</span></p>
                <button type="button" className="text-sm font-semibold text-muted hover:text-text" onClick={() => setPicker(false)}>
                  ← Back
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {choices.map((t, i) => (
                  <button
                    key={t}
                    type="button"
                    disabled={pending}
                    onClick={() => answer(true, t)}
                    className="flex items-center gap-2 rounded-xl border border-doctored/60 bg-doctored/10 px-3 py-3 text-left text-sm font-semibold transition hover:bg-doctored/20 active:scale-[0.98] disabled:opacity-50"
                  >
                    <kbd className="font-mono text-[11px] text-muted">{i + 1}</kbd>
                    {trickLabel(t)}
                  </button>
                ))}
                <button
                  type="button"
                  disabled={pending}
                  onClick={() => answer(true, null)}
                  className="col-span-2 rounded-xl border border-line px-3 py-2.5 text-sm font-semibold text-muted transition hover:text-text disabled:opacity-50"
                >
                  Just doctored, not sure how
                </button>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                disabled={pending}
                onClick={() => answer(false, null)}
                className="flex items-center justify-center gap-2 rounded-2xl bg-real py-4 font-display text-xl font-semibold text-on-accent shadow-[0_10px_24px_-12px_var(--real)] transition hover:brightness-110 active:scale-[0.97] disabled:opacity-60"
              >
                <span aria-hidden="true">✓</span> Real
              </button>
              <button
                type="button"
                disabled={pending}
                onClick={() => setPicker(true)}
                className="flex items-center justify-center gap-2 rounded-2xl bg-doctored py-4 font-display text-xl font-semibold text-on-accent shadow-[0_10px_24px_-12px_var(--doctored)] transition hover:brightness-110 active:scale-[0.97] disabled:opacity-60"
              >
                <span aria-hidden="true">✗</span> Doctored
              </button>
              <p className="col-span-2 -mt-1 text-center text-[11px] text-muted" aria-live="polite">
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
    <header className="sticky top-0 z-30 border-b border-line/70 bg-bg/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-3xl items-center gap-3 px-4">
        <Brand compact />
        <div className="min-w-0 flex-1 truncate text-sm">
          <span className="font-display text-base font-semibold">Grain of Salt{daily ? ` #${daily.daily_number}` : ''}</span>
          {daily?.theme && <span className="text-muted"> · {daily.theme}</span>}
        </div>
        <a href="#/" className="rounded-lg px-2 py-1 text-sm font-semibold text-muted hover:text-text">
          Home
        </a>
      </div>
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
            <div className="mx-auto max-w-md rounded-2xl border border-line bg-surface p-6 text-center">
              <h1 className="font-display text-2xl font-semibold">No Grain today yet.</h1>
              <p className="mt-2 text-sm text-muted">The Con is still preparing today’s puzzle. Try a Case File or Con the Con meanwhile.</p>
              <div className="mt-4 flex justify-center gap-2">
                <a href="#/con" className="rounded-xl bg-con px-4 py-2.5 font-semibold text-on-accent">
                  Con the Con 🎭
                </a>
                <a href="#/casefiles" className="rounded-xl border border-line px-4 py-2.5 font-semibold">
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
            <p className="font-display text-xl font-semibold">You’ve already played today’s Grain.</p>
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
