import { useState, type ReactNode } from 'react'
import { FeedCard } from '../components/PostCard'
import { DiffView } from '../components/Reveal'
import { SiteHeader } from '../components/Header'
import { IconArrowLeft, IconCheck, IconGear, IconLock, IconX } from '../components/Icon'
import { Workshop } from '../components/Workshop'
import { Button, Chip, ErrorState, LinkButton, Loading, SectionLabel } from '../components/ui'
import { api, ApiError, getEditorToken, setEditorToken } from '../lib/api'
import { caseNo, shortDate, trickLabel } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { href } from '../lib/router'
import type { CaseMeta, EditorCase, QueueItem } from '../lib/types'

const STATUS: Record<string, { label: string; color: string }> = {
  draft: { label: 'Draft', color: 'var(--muted)' },
  awaiting_approval: { label: 'Awaiting approval', color: 'var(--alarm)' },
  approved: { label: 'Approved', color: 'var(--real)' },
  rejected: { label: 'Rejected', color: 'var(--doctored)' },
  live: { label: 'Live', color: 'var(--real)' },
}

export function StatusBadge({ status }: { status?: string | null }) {
  const s = STATUS[status ?? ''] ?? { label: status ?? 'unknown', color: 'var(--muted)' }
  return <Chip color={s.color}>{s.label}</Chip>
}

/** Section title: Bodoni over the thin double rule (same as "All approved cases" on Case Files). */
function DeskSection({ id, children }: { id: string; children: ReactNode }) {
  return (
    <div className="mb-5">
      <h2 id={id} className="font-display text-3xl font-bold">
        {children}
      </h2>
      <div className="double-rule-thin mt-1.5" aria-hidden="true" />
    </div>
  )
}

const metaOf = (item: QueueItem): CaseMeta => ({ ...item, ...(item.meta ?? {}) }) as CaseMeta

function normalizeQueue(res: QueueItem[] | { cases: QueueItem[] }): QueueItem[] {
  const list = Array.isArray(res) ? res : res?.cases ?? []
  return list.map((it) => {
    const c = (it as { case?: { number?: number; title?: string; topic?: string } }).case
    return c ? { ...it, number: it.number ?? c.number, title: it.title ?? c.title, topic: it.topic ?? c.topic } : it
  })
}

/**
 * Public mode (CONTRACT §8.6): the desk's routes answer 401 without X-Editor-Token. Ask once, keep it in
 * sessionStorage, and retry. A 404 from the queue in public mode means the desk is switched off.
 */
function DeskGate({ error, onToken, children }: { error: unknown; onToken: () => void; children: ReactNode }) {
  const [token, setToken] = useState('')
  const status = error instanceof ApiError ? error.status : 0
  if (status !== 401) return <>{children}</>
  const hadToken = !!getEditorToken()
  return (
    <form
      className="panel mx-auto mt-4 flex w-full max-w-md flex-col gap-3 p-6"
      onSubmit={(e) => {
        e.preventDefault()
        if (!token.trim()) return
        setEditorToken(token.trim())
        onToken()
      }}
    >
      <h2 className="flex items-center gap-2 font-display text-2xl font-bold">
        <IconLock size={22} className="text-press" /> Editor’s Desk is locked
      </h2>
      <p className="text-sm text-muted">Puzzle editors only. Enter the desk token once; it’s kept for this browser tab.</p>
      <label htmlFor="desk-token" className="caps text-[13px] font-semibold tracking-[0.06em]">
        Desk token
      </label>
      <input
        id="desk-token"
        type="password"
        autoComplete="off"
        autoFocus
        value={token}
        onChange={(e) => setToken(e.target.value)}
        className="border-2 border-ink bg-white px-3 py-2 text-[15px] text-ink"
      />
      {hadToken && (
        <p role="alert" className="text-sm font-bold text-press">
          That token didn’t work. Try again.
        </p>
      )}
      <Button type="submit" variant="primary" disabled={!token.trim()}>
        Unlock
      </Button>
    </form>
  )
}

function deskTitle(e: unknown, fallback: string) {
  if (e instanceof ApiError && e.status === 404) return 'The Editor’s Desk is switched off on this server.'
  return fallback
}

export function EditorQueue() {
  const q = useAsync(() => api.editorQueue().then(normalizeQueue), [])
  return (
    <>
      <SiteHeader active="editor" />
      <main className="mx-auto w-full max-w-[1368px] flex-1 px-4 pt-8 pb-16 sm:px-6 sm:pt-10">
        <h1 className="caps text-5xl leading-[0.95] font-bold sm:text-7xl">Editor’s Desk</h1>
        <div className="double-rule mt-2 max-w-[860px]" aria-hidden="true" />
        <p className="mt-3 max-w-[860px] text-[17px] leading-relaxed italic">
          A human puzzle editor approves every puzzle before it goes live. Open one to play-test it, check the answer key, the diffs
          and the blind-solver log, then approve or reject it.
        </p>
        <div className="mt-10">
          {q.status === 'loading' && <Loading label="Loading the puzzle queue…" />}
          {q.status === 'error' && (
            <DeskGate error={q.error} onToken={q.reload}>
              <ErrorState error={q.error} onRetry={q.reload} title={deskTitle(q.error, 'Couldn’t load the puzzle queue.')} />
            </DeskGate>
          )}
          {q.status === 'ok' &&
            (q.data.length === 0 ? (
              <p className="border-[1.5px] border-dashed border-[#B9AE99] p-6 text-center text-[15px] text-muted">No cases on file yet.</p>
            ) : (
              <div className="overflow-x-auto border-2 border-ink bg-sheet shadow-[var(--hard)] thin-scroll">
                <table className="w-full min-w-[900px] border-collapse text-[15px]">
                  <thead className="caps bg-ink text-left text-[12.5px] tracking-[0.08em] text-sheet">
                    <tr>
                      <th scope="col" className="px-4 py-3 font-semibold whitespace-nowrap">Case</th>
                      <th scope="col" className="px-4 py-3 font-semibold whitespace-nowrap">Topic</th>
                      <th scope="col" className="px-4 py-3 font-semibold whitespace-nowrap">Date</th>
                      <th scope="col" className="px-4 py-3 font-semibold whitespace-nowrap">Tricks used</th>
                      <th scope="col" className="px-4 py-3 font-semibold whitespace-nowrap">Blind solver</th>
                      <th scope="col" className="px-4 py-3 font-semibold whitespace-nowrap">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {q.data.map((item) => {
                      const m = metaOf(item)
                      const solver = item.solver
                      return (
                        <tr key={item.id} className="border-t border-[#CFC6B4] bg-sheet even:bg-[#F4ECDB] hover:bg-[#EFE5CF]">
                          <td className="px-4 py-3">
                            <a href={href(`/editor/${item.id}`)} className="text-[16px] font-bold underline-offset-4 hover:underline hover:decoration-2">
                              {item.number != null && <span className="num mr-1.5 text-[13px] font-semibold text-muted">{caseNo(item.number)}</span>}
                              {item.title ?? item.id}
                            </a>
                            {m.daily && <span className="caps ml-2 bg-press px-1.5 py-0.5 text-[11px] font-semibold tracking-[0.06em] text-white">daily</span>}
                          </td>
                          <td className="px-4 py-3 text-muted">{item.topic ?? '—'}</td>
                          <td className="px-4 py-3 whitespace-nowrap text-muted">{shortDate(m.created_at ?? undefined) || '—'}</td>
                          <td className="px-4 py-3">
                            <div className="flex flex-wrap gap-1">
                              {(m.tricks ?? []).length ? (
                                (m.tricks ?? []).map((t) => <Chip key={t}>{trickLabel(t)}</Chip>)
                              ) : (
                                <span className="text-xs text-muted">none (clean)</span>
                              )}
                            </div>
                          </td>
                          <td className="min-w-[160px] px-4 py-3 text-[13.5px]">
                            {solver?.pass != null ? (
                              <span
                                style={{ color: solver.pass ? 'var(--real)' : 'var(--doctored)' }}
                                className="inline-flex items-center gap-1 font-bold"
                              >
                                {solver.pass ? <IconCheck size={14} strokeWidth={2.6} /> : <IconX size={14} strokeWidth={2.6} />}
                                {solver.pass ? 'pass' : 'fail'}
                              </span>
                            ) : item.has_solver_log ? (
                              <span className="font-bold text-ink not-italic">log on file</span>
                            ) : m.origin === 'seed' ? (
                              <span className="text-muted">hand-built</span>
                            ) : (
                              <span className="text-muted">—</span>
                            )}
                            {(solver?.difficulty ?? m.difficulty) && (
                              <span className="text-muted"> · {solver?.difficulty ?? m.difficulty}</span>
                            )}
                            {item.has_pipeline_log && <span className="block font-bold text-press">agent run logged</span>}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <StatusBadge status={m.status} />
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ))}
        </div>
      </main>
    </>
  )
}

function safetyChecks(d: EditorCase): { ok: boolean; label: string }[] {
  const posts = d.case.posts
  const key = d.answer_key.posts ?? {}
  const doctored = posts.filter((p) => key[p.id]?.doctored)
  const real = posts.filter((p) => key[p.id] && !key[p.id].doctored)
  return [
    {
      ok: doctored.every((p) => p.author.kind === 'person'),
      label: 'Every doctored post comes from a made-up “person” account, never an outlet or official',
    },
    {
      ok: real.every((p) => !!p.source_label || !!d.evidence?.[p.id]?.source),
      label: 'Every real post names its source',
    },
    {
      ok: d.answer_key.clean_case === (doctored.length === 0),
      label: d.answer_key.clean_case ? 'Marked as a clean case, and no post is doctored' : 'Clean-case flag matches the answer key',
    },
    {
      ok: doctored.every((p) => !!key[p.id]?.tell && !!key[p.id]?.diff),
      label: 'Every doctored post has a tell and a side-by-side diff',
    },
    {
      ok: posts.every((p) => !!key[p.id]),
      label: 'Every post is in the answer key',
    },
  ]
}

function CaseReview({ data, onMeta }: { data: EditorCase; onMeta: (m: CaseMeta) => void }) {
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState<'approve' | 'reject' | null>(null)
  const [err, setErr] = useState<unknown>(null)
  const [rejectOpen, setRejectOpen] = useState(false)
  const [workshop, setWorkshop] = useState(false)
  const game = data.case
  const meta = data.meta ?? {}
  const checks = safetyChecks(data)

  const act = async (kind: 'approve' | 'reject') => {
    setBusy(kind)
    setErr(null)
    try {
      const m = kind === 'approve' ? await api.approve(game.id) : await api.reject(game.id, reason.trim())
      onMeta({ ...meta, ...m })
      setRejectOpen(false)
    } catch (e) {
      setErr(e)
    } finally {
      setBusy(null)
    }
  }

  return (
    <>
      <div className="relative pt-8">
        <div
          aria-hidden="true"
          className="absolute top-0 left-6 flex h-9 w-56 items-center justify-center border-[1.5px] border-b-0 border-[#C9AE73] bg-manila text-[15px] italic sm:left-10"
          style={{ clipPath: 'polygon(9% 0, 91% 0, 100% 100%, 0 100%)' }}
        >
          Case file
        </div>
        <div className="border-[1.5px] border-[#C9AE73] bg-manila p-3 sm:p-6">
      <div className="flex flex-wrap items-start gap-x-6 gap-y-4 border-2 border-ink bg-sheet p-5 shadow-[var(--hard)] sm:p-7">
        <div className="min-w-0 flex-1">
          <p className="caps text-[12px] font-semibold tracking-[0.08em] text-ink">
            Case {caseNo(game.number)} · {game.id}
          </p>
          <div className="double-rule-thin mt-1.5" aria-hidden="true" />
          <h1 className="mt-3 font-display text-4xl leading-[1.05] font-bold sm:text-5xl">{game.title}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[15px] text-muted">
            <StatusBadge status={meta.status} />
            <span>{meta.origin === 'pipeline' ? 'Built by the pipeline' : meta.origin === 'seed' ? 'Hand-built by the team' : meta.origin}</span>
            {meta.difficulty && <span>· {meta.difficulty}</span>}
            {meta.daily && <span className="font-bold text-press">· daily case</span>}
          </div>
          {meta.status === 'rejected' && meta.rejection_reason && (
            <p className="mt-2 text-sm">
              <b>Rejected:</b> {meta.rejection_reason}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-3">
          <Button onClick={() => setWorkshop(true)}>
            <IconGear size={17} />
            Agent run
          </Button>
          <Button variant="real" onClick={() => act('approve')} disabled={busy != null || meta.status === 'approved'}>
            {busy !== 'approve' && <IconCheck size={18} strokeWidth={2.6} />}
            {busy === 'approve' ? 'Approving…' : meta.status === 'approved' ? 'Approved' : 'Approve'}
          </Button>
          <Button variant="danger" onClick={() => setRejectOpen((o) => !o)} disabled={busy != null} aria-expanded={rejectOpen}>
            <IconX size={18} strokeWidth={2.6} />
            Reject…
          </Button>
        </div>
      </div>
        </div>
      </div>

      {rejectOpen && (
        <form
          className="rise-in mt-5 flex flex-col gap-2 border-2 border-press bg-sheet p-4 shadow-[var(--hard)]"
          onSubmit={(e) => {
            e.preventDefault()
            if (reason.trim()) act('reject')
          }}
        >
          <label htmlFor="reject-reason" className="text-[15px] font-bold">
            Why reject this case? (The pipeline uses this to revise it.)
          </label>
          <textarea
            id="reject-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            required
            className="border-2 border-ink bg-white px-3 py-2 text-[15px] text-ink"
            placeholder="e.g. Post 3’s quote is too long for a fair-use excerpt."
          />
          <div className="flex gap-2">
            <Button type="submit" variant="danger" size="sm" disabled={!reason.trim() || busy != null}>
              {busy === 'reject' ? 'Rejecting…' : 'Reject case'}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setRejectOpen(false)}>
              Cancel
            </Button>
          </div>
        </form>
      )}
      {err != null && <ErrorState error={err} className="mt-4" title="That didn’t go through." />}

      <div className="mt-12 grid gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <section aria-labelledby="preview-h" className="min-w-0">
          <DeskSection id="preview-h">Player preview</DeskSection>
          <div className="con-bubble mb-5 px-4 py-3">
            <p className="text-[17px] leading-snug">{game.briefing}</p>
            <p className="mt-2 text-[12.5px] text-[#C9C2B5] not-italic">
              {game.posts.length} posts · {game.clue_budget} clues · topic: {game.topic}
            </p>
          </div>
          <div className="flex flex-col gap-4">
            {game.posts.map((p, i) => (
              <div key={p.id}>
                <p className="caps mb-1.5 text-[12px] font-semibold tracking-[0.1em] text-muted">Post {i + 1}</p>
                <FeedCard post={p} caseNumber={game.number} compact />
              </div>
            ))}
          </div>
        </section>

        <section aria-labelledby="key-h" className="min-w-0">
          <DeskSection id="key-h">Answer key</DeskSection>
          <div className="flex flex-col gap-4">
            {data.answer_key.clean_case && (
              <div className="border-2 border-press bg-sheet p-4 text-[15px] shadow-[var(--hard)]">
                <b>Clean case:</b> no post is doctored.
                {data.answer_key.con_line_clean && <p className="mt-1 italic">“{data.answer_key.con_line_clean}”</p>}
              </div>
            )}
            {game.posts.map((p, i) => {
              const k = data.answer_key.posts?.[p.id]
              if (!k) return null
              return (
                <article key={p.id} className="panel p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="caps text-[12px] font-semibold tracking-[0.1em] text-muted">Post {i + 1}</span>
                    {k.doctored ? (
                      <Chip color="var(--doctored)">
                        <IconX size={13} strokeWidth={2.6} /> Doctored · {trickLabel(k.trick)}
                      </Chip>
                    ) : (
                      <Chip color="var(--real)">
                        <IconCheck size={13} strokeWidth={2.6} /> Real{k.suspicious_real ? ' · built to look fake' : ''}
                      </Chip>
                    )}
                  </div>
                  {k.tell && (
                    <p className="mt-2 text-[15px]">
                      <b>The tell:</b> {k.tell}
                    </p>
                  )}
                  {k.explanation && <p className="mt-1.5 text-[15px] text-muted">{k.explanation}</p>}
                  {k.doctored && k.diff && (
                    <div className="mt-3">
                      <DiffView post={p} caseNumber={game.number} diff={k.diff} />
                    </div>
                  )}
                  <ul className="mt-3 flex flex-col gap-1 border-t border-[#CFC6B4] pt-2 text-[13px] text-muted italic">
                    {k.con_line_fooled && (
                      <li>
                        <span className="font-bold text-ink not-italic">Con, if fooled:</span> “{k.con_line_fooled}”
                      </li>
                    )}
                    {k.con_line_caught && (
                      <li>
                        <span className="font-bold text-ink not-italic">Con, if caught:</span> “{k.con_line_caught}”
                      </li>
                    )}
                    {k.con_line_false_alarm && (
                      <li>
                        <span className="font-bold text-ink not-italic">Con, on a false alarm:</span> “{k.con_line_false_alarm}”
                      </li>
                    )}
                  </ul>
                </article>
              )
            })}

            <section className="panel p-4" aria-labelledby="safety-h">
              <SectionLabel className="mb-2">
                <span id="safety-h">Safety checks</span>
              </SectionLabel>
              <ul className="flex flex-col gap-1.5 text-[15px]">
                {checks.map((c) => (
                  <li key={c.label} className="flex items-start gap-2">
                    <span
                      className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center border-[1.5px] border-ink"
                      style={{ background: c.ok ? 'var(--ink)' : 'var(--press)', color: c.ok ? 'var(--sheet)' : '#fff' }}
                      aria-hidden="true"
                    >
                      {c.ok ? <IconCheck size={13} strokeWidth={3} /> : <IconX size={13} strokeWidth={3} />}
                    </span>
                    <span>
                      <span className="sr-only">{c.ok ? 'Pass: ' : 'Fail: '}</span>
                      {c.label}
                    </span>
                  </li>
                ))}
              </ul>
              {(meta.sources ?? []).length > 0 && (
                <>
                  <p className="caps mt-4 text-[12px] font-semibold tracking-[0.1em] text-muted">Sources</p>
                  <ul className="mt-1 flex flex-col gap-0.5 text-[13px]">
                    {(meta.sources ?? []).map((s) => (
                      <li key={s} className="break-all">
                        <a href={s} target="_blank" rel="noopener noreferrer" className="text-focus underline underline-offset-2">
                          {s}
                        </a>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </section>

            <section className="panel p-4" aria-labelledby="solver-h">
              <SectionLabel className="mb-2">
                <span id="solver-h">Blind-solver log</span>
              </SectionLabel>
              {data.solver_log ? (
                <pre className="max-h-96 overflow-auto border-[1.5px] border-[#CFC6B4] bg-white p-3 font-code text-xs leading-relaxed whitespace-pre-wrap thin-scroll">{data.solver_log}</pre>
              ) : (
                <p className="text-[15px] text-muted">
                  {meta.origin === 'pipeline'
                    ? 'No solver log: the blind solver never ran on this build, so its fairness was not checked.'
                    : 'No solver log: this case was hand-built by the team, not run through the pipeline.'}
                </p>
              )}
            </section>
          </div>
        </section>
      </div>

      <Workshop caseId={game.id} open={workshop} onClose={() => setWorkshop(false)} unmasked />
    </>
  )
}

export function EditorCaseScreen({ caseId }: { caseId: string }) {
  const d = useAsync(() => api.editorCase(caseId), [caseId])
  const [meta, setMeta] = useState<CaseMeta | null>(null)
  return (
    <>
      <SiteHeader active="editor" />
      <main className="mx-auto w-full max-w-[1368px] flex-1 px-4 pt-6 pb-16 sm:px-6">
        <LinkButton to="/editor" size="sm" variant="ghost" className="mb-6 -ml-3">
          <IconArrowLeft size={16} />
          Puzzle queue
        </LinkButton>
        {d.status === 'loading' && <Loading label="Opening the puzzle for review…" />}
        {d.status === 'error' && (
          <DeskGate error={d.error} onToken={d.reload}>
            <ErrorState
              error={d.error}
              onRetry={d.reload}
              title={d.error instanceof ApiError && d.error.status === 404 ? 'No such puzzle (or the desk is switched off).' : 'Couldn’t open the puzzle.'}
            />
          </DeskGate>
        )}
        {d.status === 'ok' && <CaseReview data={{ ...d.data, meta: meta ?? d.data.meta }} onMeta={setMeta} />}
      </main>
    </>
  )
}
