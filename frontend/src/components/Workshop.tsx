import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api, ApiError } from '../lib/api'
import type { PipelineEvent, Todo } from '../lib/types'
import { Spinner } from './Art'
import { IconCheck, IconClose, IconExpand, IconFolder, IconPause, IconPlay, IconReplay } from './Icon'
import { ErrorState } from './ui'

type LoadState =
  | { status: 'idle' | 'loading' }
  | { status: 'none' }
  | { status: 'ok'; events: PipelineEvent[] }
  | { status: 'error'; error: unknown }

const mmss = (s: number) => {
  const total = Math.max(0, Math.round(s))
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

function Redacted({ width = 8 }: { width?: number }) {
  return (
    <span>
      <span aria-hidden="true" className="redacted inline-block align-middle text-ink" style={{ width: `${width}ch`, height: '0.95em' }} />
      <span className="sr-only">hidden until you submit your verdicts</span>
    </span>
  )
}

interface Lane {
  name: string
  status: 'working' | 'done'
  task?: string
  taskSpoiler?: boolean
  summary?: string
  summarySpoiler?: boolean
  calls: { tool: string; summary?: string; spoiler?: boolean; t: number }[]
}

function derive(events: PipelineEvent[]) {
  let plan: { todos: Todo[]; spoiler?: boolean } | null = null
  const lanes = new Map<string, Lane>()
  const files = new Map<string, { path: string; agent?: string; spoiler?: boolean; count: number }>()
  const solver: PipelineEvent[] = []
  let status: string | null = null
  const lane = (name: string) => {
    let l = lanes.get(name)
    if (!l) {
      l = { name, status: 'working', calls: [] }
      lanes.set(name, l)
    }
    return l
  }
  for (const ev of events) {
    switch (ev.type) {
      case 'plan_updated':
        if (Array.isArray(ev.todos)) plan = { todos: ev.todos, spoiler: ev.spoiler }
        break
      case 'subagent_started': {
        const l = lane(ev.name ?? 'agent')
        l.status = 'working'
        l.task = ev.task
        l.taskSpoiler = ev.spoiler
        break
      }
      case 'subagent_finished': {
        const l = lane(ev.name ?? 'agent')
        l.status = 'done'
        l.summary = ev.summary
        l.summarySpoiler = ev.spoiler
        break
      }
      case 'tool_called':
        lane(ev.agent ?? 'orchestrator').calls.push({ tool: ev.tool ?? ev.name ?? 'tool', summary: ev.summary, spoiler: ev.spoiler, t: ev.t })
        break
      case 'file_written': {
        const p = ev.path ?? '?'
        const prev = files.get(p)
        files.set(p, { path: p, agent: ev.agent, spoiler: ev.spoiler || prev?.spoiler, count: (prev?.count ?? 0) + 1 })
        break
      }
      case 'solver_result':
        solver.push(ev)
        break
      case 'awaiting_approval':
        status = 'awaiting_approval'
        break
      case 'case_status':
        status = ev.status ?? status
        break
    }
  }
  return { plan, lanes: [...lanes.values()], files: [...files.values()], solver, status }
}

function describe(ev: PipelineEvent): string {
  switch (ev.type) {
    case 'plan_updated':
      return `Plan updated (${ev.todos?.length ?? 0} steps)`
    case 'subagent_started':
      return `${ev.name} started: ${ev.task ?? ''}`
    case 'subagent_finished':
      return `${ev.name} finished${ev.summary ? `: ${ev.summary}` : ''}`
    case 'tool_called':
      return `${ev.agent ?? 'orchestrator'} → ${ev.tool}${ev.summary ? `: ${ev.summary}` : ''}`
    case 'file_written':
      return `${ev.agent ?? 'agent'} wrote ${ev.path}`
    case 'solver_result':
      return `Blind solver: ${ev.pass ? 'pass' : 'fail'}${ev.difficulty ? ` (${ev.difficulty})` : ''}`
    case 'awaiting_approval':
      return 'Paused for the puzzle editor’s approval'
    case 'case_status':
      return `Case status: ${ev.status}`
    default:
      return ev.type
  }
}

const TODO_LABEL: Record<string, string> = { completed: 'done', in_progress: 'in progress', pending: 'pending' }

/** Plan step markers (Figma "Workshop"): filled ink check = done, half press-red = in progress, ring = pending. */
function TodoMark({ status }: { status: string }) {
  if (status === 'completed')
    return (
      <span className="flex h-[22px] w-[22px] items-center justify-center rounded-full bg-ink text-sheet" aria-hidden="true">
        <IconCheck size={14} strokeWidth={3} />
      </span>
    )
  if (status === 'in_progress')
    return (
      <svg viewBox="0 0 22 22" width={22} height={22} aria-hidden="true" className="block shrink-0">
        <circle cx="11" cy="11" r="9.6" fill="#FBF7EE" stroke="var(--press)" strokeWidth="2" />
        <path d="M11 1.4a9.6 9.6 0 0 0 0 19.2Z" fill="var(--press)" />
      </svg>
    )
  return <span className="block h-[22px] w-[22px] rounded-full border-2 border-[#8C8270]" aria-hidden="true" />
}

/** Workshop section heading: Bodoni over the thin double rule. */
function WsHead({ children }: { children: ReactNode }) {
  return (
    <div className="mb-3">
      <h3 className="font-display text-[24px] leading-tight font-bold">{children}</h3>
      <div className="double-rule-thin mt-1" aria-hidden="true" />
    </div>
  )
}

/**
 * The Con's Workshop (SPEC §3.10): replays this case's pipeline_log.jsonl.
 * Events marked "spoiler" stay redacted until the verdict is in. Never shows fabricated events.
 */
export function Workshop({
  caseId,
  open,
  onClose,
  unmasked,
}: {
  caseId: string
  open: boolean
  onClose: () => void
  unmasked: boolean
}) {
  const [load, setLoad] = useState<LoadState>({ status: 'idle' })
  const [clock, setClockState] = useState(0)
  const clockRef = useRef(0)
  const setClock = (v: number) => {
    clockRef.current = v
    setClockState(v)
  }
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState<2 | 4>(2)
  const [full, setFull] = useState(false)
  const closeBtn = useRef<HTMLButtonElement>(null)

  const fetchLog = () => {
    setLoad({ status: 'loading' })
    api
      .pipelineLog(caseId)
      .then((res) => {
        const events = (Array.isArray(res) ? res : res?.events ?? [])
          .filter((e) => e && typeof e === 'object' && typeof e.type === 'string')
          .map((e) => ({ ...e, t: Number(e.t) || 0 }))
          .sort((a, b) => a.t - b.t)
        if (!events.length) {
          setLoad({ status: 'none' })
          return
        }
        setLoad({ status: 'ok', events })
        setClock(0)
        setPlaying(true)
      })
      .catch((error) => {
        if (error instanceof ApiError && error.status === 404) setLoad({ status: 'none' })
        else setLoad({ status: 'error', error })
      })
  }

  // Load lazily the first time the panel opens (and again for a new case).
  useEffect(() => {
    setLoad({ status: 'idle' })
    setClock(0)
    setPlaying(false)
  }, [caseId])
  useEffect(() => {
    if (open && load.status === 'idle') fetchLog()
    if (open) window.setTimeout(() => closeBtn.current?.focus({ preventScroll: true }), 50)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, load.status])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const events = load.status === 'ok' ? load.events : []
  const end = events.length ? events[events.length - 1].t : 0

  // Replay clock
  useEffect(() => {
    if (!playing || !open || !events.length) return
    let raf = 0
    let last = performance.now()
    const step = (now: number) => {
      const dt = Math.min(0.25, (now - last) / 1000)
      last = now
      const next = Math.min(end, clockRef.current + dt * speed)
      setClock(next)
      if (next >= end) setPlaying(false)
      else raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, open, speed, end, events.length])

  const visible = useMemo(() => events.filter((e) => e.t <= clock + 1e-6), [events, clock])
  const state = useMemo(() => derive(visible), [visible])
  const hide = (spoiler?: boolean) => !!spoiler && !unmasked
  const txt = (s: string | undefined, spoiler?: boolean, w = 10): ReactNode => (hide(spoiler) ? <Redacted width={w} /> : s)

  return (
    <>
      {/* Full screen: the page dims behind the sheet; the case bar stays visible above it. */}
      {open && full && <div aria-hidden="true" className="fade-in fixed inset-0 z-40 bg-[#87806F]/80" onClick={onClose} />}
      <aside
        aria-label="The Con's Workshop"
        aria-hidden={!open}
        inert={!open}
        className={`fixed z-50 flex flex-col bg-sheet transition-transform duration-300 ease-out motion-reduce:transition-none ${
          full
            ? 'inset-0 border-2 border-ink sm:inset-x-6 sm:top-[84px] sm:bottom-6 sm:mx-auto sm:max-w-[1320px] sm:shadow-[var(--hard)]'
            : 'top-0 right-0 bottom-0 w-full border-l-2 border-ink shadow-[var(--hard)] sm:w-[480px]'
        } ${open ? 'translate-x-0' : 'translate-x-[calc(100%+3rem)]'}`}
      >
        <header className={`shrink-0 px-5 pt-4 ${full ? 'sm:px-7 sm:pt-6' : ''}`}>
          <div className="flex items-center gap-3">
            <span className="h-3 w-3 shrink-0 rounded-full bg-press" aria-hidden="true" />
            <h2 className={`truncate leading-tight uppercase italic ${full ? 'text-[22px] sm:text-[26px]' : 'text-[20px]'}`}>
              The Con’s Workshop
            </h2>
            {load.status === 'ok' && (
              <span className={`ml-1 hidden shrink-0 items-center gap-1 text-[13px] text-muted italic ${full ? 'sm:inline-flex' : ''}`}>
                <IconReplay size={13} /> replay of run {mmss(end)}
              </span>
            )}
            <div className="ml-auto flex shrink-0 items-center gap-1">
              <button
                type="button"
                onClick={() => setFull((f) => !f)}
                className="hidden h-9 w-9 items-center justify-center text-ink hover:bg-ink hover:text-sheet sm:inline-flex"
                aria-label={full ? 'Exit full screen' : 'Full screen'}
                title={full ? 'Exit full screen' : 'Full screen'}
              >
                <IconExpand size={18} />
              </button>
              <button
                ref={closeBtn}
                type="button"
                onClick={onClose}
                className="inline-flex h-9 w-9 items-center justify-center text-ink hover:bg-ink hover:text-sheet"
                aria-label="Close the workshop"
              >
                <IconClose size={20} />
              </button>
            </div>
          </div>
          <div className="double-rule-thin mt-3" aria-hidden="true" />
        </header>

        <div className={`min-h-0 flex-1 overflow-y-auto px-5 py-5 thin-scroll ${full ? 'sm:px-7' : ''}`}>
          {(load.status === 'idle' || load.status === 'loading') && (
            <div className="flex flex-col items-center gap-3 py-16 text-[15px] text-muted italic">
              <Spinner size={32} label="Loading the run log" />
              Loading the run log…
            </div>
          )}

          {load.status === 'error' && <ErrorState error={load.error} onRetry={fetchLog} title="Couldn’t load the run log." />}

          {load.status === 'none' && (
            <div className="mx-auto max-w-sm py-10 text-center">
              <IconFolder size={40} className="mx-auto text-ink" />
              <h3 className="mt-3 font-display text-2xl font-bold">No agent run for this case</h3>
              <p className="mt-2 text-[15px] text-muted">This case was hand-built by the team — no agent run to replay.</p>
              <p className="mt-3 text-[13.5px] text-muted italic">
                Cases built by the Deep Agents pipeline log every step (plan, sub-agents, files, blind solver), and that log plays
                back here.
              </p>
            </div>
          )}

          {load.status === 'ok' && (
            <div className={`flex flex-col gap-7 ${full ? 'lg:grid lg:grid-cols-2 lg:items-start lg:gap-x-10' : ''}`}>
              {/* replay controls */}
              <div className={`flex flex-wrap items-center gap-2 ${full ? 'lg:col-span-2' : ''}`}>
                <button
                  type="button"
                  className="press caps inline-flex h-10 items-center gap-2 border-2 border-ink bg-ink px-4 text-[15px] font-semibold text-sheet hover:bg-[#2a2a2a]"
                  onClick={() => {
                    if (clock >= end) setClock(0)
                    setPlaying((p) => !p)
                  }}
                  aria-label={playing ? 'Pause replay' : 'Play replay'}
                >
                  {playing ? <IconPause size={16} /> : clock >= end ? <IconReplay size={16} /> : <IconPlay size={16} />}
                  {playing ? 'Pause' : clock >= end ? 'Replay' : 'Play'}
                </button>
                <div role="group" aria-label="Replay speed" className="inline-flex gap-2">
                  {([2, 4] as const).map((s) => (
                    <button
                      key={s}
                      type="button"
                      aria-pressed={speed === s}
                      onClick={() => setSpeed(s)}
                      className={`num h-10 w-14 border-2 border-ink text-[15px] font-semibold ${
                        speed === s ? 'bg-ink text-sheet' : 'bg-sheet text-ink hover:bg-surface-2'
                      }`}
                    >
                      {s}×
                    </button>
                  ))}
                </div>
                <button
                  type="button"
                  className="caps px-3 py-2 text-[15px] font-semibold text-ink hover:underline hover:decoration-2 hover:underline-offset-4"
                  onClick={() => {
                    setPlaying(false)
                    setClock(end)
                  }}
                >
                  Skip to end
                </button>
                <span className="num ml-auto text-[15px] font-semibold text-ink tabular-nums" aria-live="off">
                  {mmss(clock)} / {mmss(end)}
                </span>
                <div className="mt-2 h-1 w-full overflow-hidden bg-[#DDD3BF]" aria-hidden="true">
                  <div className="h-full bg-press" style={{ width: `${end ? (clock / end) * 100 : 100}%` }} />
                </div>
              </div>

              <section>
                <WsHead>Plan</WsHead>
                {state.plan ? (
                  <ul className="flex flex-col gap-2.5">
                    {state.plan.todos.map((todo, i) => {
                      const pending = todo.status !== 'completed' && todo.status !== 'in_progress'
                      return (
                        <li key={i} className="flex items-start gap-3 text-[16px] leading-snug">
                          <span key={todo.status} className="tick-in shrink-0">
                            <TodoMark status={todo.status} />
                            <span className="sr-only">{TODO_LABEL[todo.status] ?? TODO_LABEL.pending}</span>
                          </span>
                          <span className={pending ? 'text-muted' : 'font-bold'}>{txt(todo.content, state.plan?.spoiler, 18)}</span>
                        </li>
                      )
                    })}
                  </ul>
                ) : (
                  <p className="text-[15px] text-muted italic">Waiting for the orchestrator’s plan…</p>
                )}
              </section>

              <section>
                <WsHead>Sub-agents</WsHead>
                {state.lanes.length === 0 ? (
                  <p className="text-[15px] text-muted italic">No sub-agents yet.</p>
                ) : (
                  <div className="flex flex-col gap-3">
                    {state.lanes.map((l) => (
                      <div key={l.name} className="border-[1.5px] border-ink bg-sheet px-4 py-3">
                        <div className="flex items-baseline gap-2">
                          <span className="font-head text-[18px] font-semibold capitalize">{l.name.replace(/[-_]/g, ' ')}</span>
                          {l.status === 'done' ? (
                            <span className="caps ml-auto inline-flex items-center gap-1 text-[12px] font-semibold text-ink">
                              <IconCheck size={12} strokeWidth={3} /> done
                            </span>
                          ) : (
                            <span className="caps ml-auto inline-flex items-center gap-1.5 text-[12px] font-semibold text-press">
                              <span className="pulse-dot h-2 w-2 rounded-full bg-press" aria-hidden="true" /> working
                            </span>
                          )}
                        </div>
                        {l.task && <p className="mt-0.5 text-[14px] text-muted">{txt(l.task, l.taskSpoiler, 16)}</p>}
                        {l.calls.length > 0 && (
                          <ul className="mt-2.5 flex flex-col gap-1">
                            {l.calls.slice(-6).map((c, i) => (
                              <li key={`${c.t}-${i}`} className="fade-in text-[13.5px] break-words">
                                <span className="font-bold">{c.tool}</span>
                                {c.summary && <span> · {txt(c.summary, c.spoiler, 12)}</span>}
                              </li>
                            ))}
                            {l.calls.length > 6 && <li className="text-[12px] text-muted italic">+{l.calls.length - 6} earlier calls</li>}
                          </ul>
                        )}
                        {l.summary && <p className="mt-2 text-[14px] italic">{txt(l.summary, l.summarySpoiler, 14)}</p>}
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section>
                <WsHead>Files</WsHead>
                {state.files.length === 0 ? (
                  <p className="text-[15px] text-muted italic">No files written yet.</p>
                ) : (
                  <ul className="flex flex-col gap-1.5">
                    {state.files.map((f) => (
                      <li key={f.path} className="fade-in flex items-baseline gap-3 text-[14px]">
                        <span className="min-w-0 flex-1 break-all">{hide(f.spoiler) ? <Redacted width={20} /> : f.path}</span>
                        <span className={`shrink-0 text-[13px] font-bold ${f.count > 1 ? 'text-muted' : 'text-press'}`}>
                          {f.count > 1 ? `updated ×${f.count}` : 'new'}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section>
                <WsHead>Blind solver</WsHead>
                {state.solver.length === 0 ? (
                  <p className="border-[1.5px] border-dashed border-ink px-4 py-5 text-[15px] text-muted italic">Not run yet.</p>
                ) : (
                  <ul className="flex flex-col gap-2">
                    {state.solver.map((s, i) => (
                      <li key={i} className="fade-in border-[1.5px] border-ink bg-sheet px-4 py-3 text-[15px]">
                        {hide(s.spoiler) ? (
                          <Redacted width={24} />
                        ) : (
                          <>
                            <span className="caps font-semibold" style={{ color: s.pass ? 'var(--ink)' : 'var(--press)' }}>
                              {s.pass ? '✓ Pass' : '✗ Fail'}
                            </span>
                            {s.attempt != null && <span className="text-muted"> · attempt {s.attempt}</span>}
                            {s.difficulty && <span className="text-muted"> · {s.difficulty}</span>}
                            {s.tools_used && (
                              <div className="mt-1 text-[13.5px] text-muted">
                                Tools used: {s.tools_used.length ? s.tools_used.join(', ') : 'none'}
                              </div>
                            )}
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                {state.status && (
                  <p className="mt-2 text-[14px] text-muted">
                    Status: <span className="font-bold text-ink">{state.status.replace(/_/g, ' ')}</span>
                  </p>
                )}
              </section>

              <section className={full ? 'lg:col-span-2' : ''}>
                <WsHead>Event log</WsHead>
                <ol className="flex flex-col gap-1 text-[13.5px]">
                  {visible
                    .slice()
                    .reverse()
                    .slice(0, 40)
                    .map((ev, i) => (
                      <li key={`${ev.t}-${visible.length - i}`} className="flex gap-4">
                        <span className="num w-12 shrink-0 text-muted tabular-nums">{ev.t.toFixed(1)}s</span>
                        <span className="min-w-0 break-words">{hide(ev.spoiler) ? <Redacted width={22} /> : describe(ev)}</span>
                      </li>
                    ))}
                </ol>
                {!unmasked && events.some((e) => e.spoiler) && (
                  <p className="mt-4 border-[1.5px] border-press bg-[#F8E1DC] px-4 py-3 text-[14.5px]">
                    Redacted lines would give away the answers. They unlock after you submit.
                  </p>
                )}
              </section>
            </div>
          )}
        </div>
      </aside>
    </>
  )
}
