import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api, ApiError } from '../lib/api'
import type { PipelineEvent, Todo } from '../lib/types'
import { Spinner } from './Art'
import { Button, ErrorState, SectionLabel } from './ui'

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
      <span aria-hidden="true" className="redacted inline-block align-middle text-muted" style={{ width: `${width}ch`, height: '0.9em' }} />
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
      return 'Paused for teacher approval'
    case 'case_status':
      return `Case status: ${ev.status}`
    default:
      return ev.type
  }
}

const TODO_ICON: Record<string, { icon: string; color: string; label: string }> = {
  completed: { icon: '✓', color: 'var(--real)', label: 'done' },
  in_progress: { icon: '◐', color: 'var(--con)', label: 'in progress' },
  pending: { icon: '○', color: 'var(--muted)', label: 'pending' },
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
    <aside
      aria-label="The Con's Workshop"
      aria-hidden={!open}
      inert={!open}
      className={`fixed top-0 right-0 bottom-0 z-50 flex flex-col border-l border-line bg-surface shadow-2xl transition-transform duration-300 ease-out motion-reduce:transition-none ${
        full ? 'w-full' : 'w-full sm:w-[460px]'
      } ${open ? 'translate-x-0' : 'translate-x-full'}`}
    >
      <header className="flex shrink-0 items-center gap-2 border-b border-line px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full bg-con" aria-hidden="true" />
        <h2 className="font-con text-base tracking-wider text-text uppercase">The Con’s Workshop</h2>
        {load.status === 'ok' && (
          <span className="ml-1 truncate font-mono text-[11px] text-muted">⟲ replay of run {mmss(end)}</span>
        )}
        <div className="ml-auto flex items-center gap-1">
          <button
            type="button"
            onClick={() => setFull((f) => !f)}
            className="hidden rounded-lg px-2 py-1 text-sm text-muted hover:bg-surface-2 hover:text-text sm:inline-flex"
            aria-label={full ? 'Exit full screen' : 'Full screen'}
            title={full ? 'Exit full screen' : 'Full screen'}
          >
            {full ? '⤡' : '⤢'}
          </button>
          <button
            ref={closeBtn}
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-sm font-semibold text-muted hover:bg-surface-2 hover:text-text"
            aria-label="Close the workshop"
          >
            ✕
          </button>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 thin-scroll">
        {(load.status === 'idle' || load.status === 'loading') && (
          <div className="flex flex-col items-center gap-3 py-16 text-sm text-muted">
            <Spinner size={32} label="Loading the run log" />
            Loading the run log…
          </div>
        )}

        {load.status === 'error' && <ErrorState error={load.error} onRetry={fetchLog} title="Couldn’t load the run log." />}

        {load.status === 'none' && (
          <div className="mx-auto max-w-sm py-10 text-center">
            <p className="text-3xl" aria-hidden="true">
              🗂️
            </p>
            <h3 className="mt-3 font-display text-lg font-semibold">No agent run for this case</h3>
            <p className="mt-2 text-sm text-muted">This case was hand-built by the team — no agent run to replay.</p>
            <p className="mt-3 text-xs text-muted">
              Cases built by the Deep Agents pipeline log every step (plan, sub-agents, files, blind solver), and that log plays
              back here.
            </p>
          </div>
        )}

        {load.status === 'ok' && (
          <div className={`flex flex-col gap-6 ${full ? 'mx-auto max-w-5xl lg:grid lg:grid-cols-2 lg:items-start' : ''}`}>
            {/* replay controls */}
            <div className={`flex flex-wrap items-center gap-2 rounded-xl border border-line bg-surface-2 p-2 ${full ? 'lg:col-span-2' : ''}`}>
              <Button
                size="sm"
                variant="con"
                onClick={() => {
                  if (clock >= end) setClock(0)
                  setPlaying((p) => !p)
                }}
                aria-label={playing ? 'Pause replay' : 'Play replay'}
              >
                {playing ? '❚❚ Pause' : clock >= end ? '⟲ Replay' : '▶ Play'}
              </Button>
              <div role="group" aria-label="Replay speed" className="inline-flex overflow-hidden rounded-lg border border-line">
                {([2, 4] as const).map((s) => (
                  <button
                    key={s}
                    type="button"
                    aria-pressed={speed === s}
                    onClick={() => setSpeed(s)}
                    className={`px-2.5 py-1 font-mono text-xs font-semibold ${speed === s ? 'bg-con text-on-accent' : 'text-muted hover:text-text'}`}
                  >
                    {s}×
                  </button>
                ))}
              </div>
              <button
                type="button"
                className="rounded-lg px-2 py-1 text-xs font-semibold text-muted hover:text-text"
                onClick={() => {
                  setPlaying(false)
                  setClock(end)
                }}
              >
                Skip to end
              </button>
              <span className="ml-auto font-mono text-[11px] text-muted tabular-nums" aria-live="off">
                {mmss(clock)} / {mmss(end)}
              </span>
              <div className="h-1 w-full overflow-hidden rounded-full bg-line" aria-hidden="true">
                <div className="h-full bg-con" style={{ width: `${end ? (clock / end) * 100 : 100}%` }} />
              </div>
            </div>

            <section>
              <SectionLabel className="mb-2">Plan</SectionLabel>
              {state.plan ? (
                <ul className="flex flex-col gap-1.5">
                  {state.plan.todos.map((todo, i) => {
                    const s = TODO_ICON[todo.status] ?? TODO_ICON.pending
                    return (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <span key={todo.status} className="tick-in mt-px w-4 shrink-0 text-center font-bold" style={{ color: s.color }}>
                          {s.icon}
                          <span className="sr-only">{s.label}</span>
                        </span>
                        <span className={todo.status === 'completed' ? 'text-muted' : ''}>{txt(todo.content, state.plan?.spoiler, 18)}</span>
                      </li>
                    )
                  })}
                </ul>
              ) : (
                <p className="text-sm text-muted">Waiting for the orchestrator’s plan…</p>
              )}
            </section>

            <section>
              <SectionLabel className="mb-2">Sub-agents</SectionLabel>
              {state.lanes.length === 0 ? (
                <p className="text-sm text-muted">No sub-agents yet.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {state.lanes.map((l) => (
                    <div key={l.name} className="rounded-xl border border-line bg-surface-2 p-3">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold capitalize">{l.name.replace(/[-_]/g, ' ')}</span>
                        {l.status === 'done' ? (
                          <span className="text-xs font-semibold text-real">✓ done</span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs font-semibold text-con">
                            <span className="pulse-dot h-2 w-2 rounded-full bg-con" aria-hidden="true" /> working
                          </span>
                        )}
                      </div>
                      {l.task && <p className="mt-1 text-xs text-muted">{txt(l.task, l.taskSpoiler, 16)}</p>}
                      {l.calls.length > 0 && (
                        <ul className="mt-2 flex flex-col gap-1 border-l-2 border-line pl-2.5">
                          {l.calls.slice(-6).map((c, i) => (
                            <li key={`${c.t}-${i}`} className="fade-in text-xs">
                              <span className="font-mono text-con">{c.tool}</span>
                              {c.summary && <span className="text-muted"> · {txt(c.summary, c.spoiler, 12)}</span>}
                            </li>
                          ))}
                          {l.calls.length > 6 && <li className="text-[11px] text-muted">+{l.calls.length - 6} earlier calls</li>}
                        </ul>
                      )}
                      {l.summary && <p className="mt-2 text-xs">{txt(l.summary, l.summarySpoiler, 14)}</p>}
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section>
              <SectionLabel className="mb-2">Files</SectionLabel>
              {state.files.length === 0 ? (
                <p className="text-sm text-muted">No files written yet.</p>
              ) : (
                <ul className="flex flex-col gap-1">
                  {state.files.map((f) => (
                    <li key={f.path} className="fade-in flex items-baseline gap-2 font-mono text-xs">
                      <span className="min-w-0 flex-1 break-all">{hide(f.spoiler) ? <Redacted width={20} /> : f.path}</span>
                      <span className="shrink-0 text-muted">{f.count > 1 ? `updated ×${f.count}` : 'new'}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section>
              <SectionLabel className="mb-2">Blind solver</SectionLabel>
              {state.solver.length === 0 ? (
                <p className="text-sm text-muted">Not run yet.</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {state.solver.map((s, i) => (
                    <li key={i} className="fade-in rounded-xl border border-line bg-surface-2 p-3 text-sm">
                      {hide(s.spoiler) ? (
                        <Redacted width={24} />
                      ) : (
                        <>
                          <span className="font-semibold" style={{ color: s.pass ? 'var(--real)' : 'var(--doctored)' }}>
                            {s.pass ? '✓ Pass' : '✗ Fail'}
                          </span>
                          {s.attempt != null && <span className="text-muted"> · attempt {s.attempt}</span>}
                          {s.difficulty && <span className="text-muted"> · {s.difficulty}</span>}
                          {s.tools_used && (
                            <div className="mt-1 text-xs text-muted">
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
                <p className="mt-2 text-xs text-muted">
                  Status: <span className="font-semibold text-text">{state.status.replace(/_/g, ' ')}</span>
                </p>
              )}
            </section>

            <section className={full ? 'lg:col-span-2' : ''}>
              <SectionLabel className="mb-2">Event log</SectionLabel>
              <ol className="flex flex-col gap-1 font-mono text-[11px]">
                {visible
                  .slice()
                  .reverse()
                  .slice(0, 40)
                  .map((ev, i) => (
                    <li key={`${ev.t}-${visible.length - i}`} className="flex gap-2">
                      <span className="w-12 shrink-0 text-right text-muted tabular-nums">{ev.t.toFixed(1)}s</span>
                      <span className="min-w-0 break-words">{hide(ev.spoiler) ? <Redacted width={22} /> : describe(ev)}</span>
                    </li>
                  ))}
              </ol>
              {!unmasked && events.some((e) => e.spoiler) && (
                <p className="mt-3 text-xs text-muted">Redacted lines would give away the answers. They unlock after you submit.</p>
              )}
            </section>
          </div>
        )}
      </div>
    </aside>
  )
}
