import { useState, type ReactNode } from 'react'
import { FeedCard } from '../components/PostCard'
import { DiffView } from '../components/Reveal'
import { SiteHeader } from '../components/Header'
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
      className="mx-auto mt-4 flex w-full max-w-md flex-col gap-3 rounded-2xl border border-line bg-surface p-6"
      onSubmit={(e) => {
        e.preventDefault()
        if (!token.trim()) return
        setEditorToken(token.trim())
        onToken()
      }}
    >
      <h2 className="font-display text-xl font-semibold">🔐 Editor’s Desk is locked</h2>
      <p className="text-sm text-muted">Puzzle editors only. Enter the desk token once; it’s kept for this browser tab.</p>
      <label htmlFor="desk-token" className="text-sm font-semibold">
        Desk token
      </label>
      <input
        id="desk-token"
        type="password"
        autoComplete="off"
        autoFocus
        value={token}
        onChange={(e) => setToken(e.target.value)}
        className="rounded-xl border border-line bg-bg px-3 py-2 text-sm text-text"
      />
      {hadToken && (
        <p role="alert" className="text-sm text-doctored">
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
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <h1 className="font-display text-3xl font-bold">Editor’s Desk</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          A human puzzle editor approves every puzzle before it goes live. Open one to play-test it, check the answer key, the diffs
          and the blind-solver log, then approve or reject it.
        </p>
        <div className="mt-6">
          {q.status === 'loading' && <Loading label="Loading the puzzle queue…" />}
          {q.status === 'error' && (
            <DeskGate error={q.error} onToken={q.reload}>
              <ErrorState error={q.error} onRetry={q.reload} title={deskTitle(q.error, 'Couldn’t load the puzzle queue.')} />
            </DeskGate>
          )}
          {q.status === 'ok' &&
            (q.data.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted">No cases on file yet.</p>
            ) : (
              <div className="overflow-x-auto rounded-2xl border border-line thin-scroll">
                <table className="w-full min-w-[720px] border-collapse text-sm">
                  <thead className="bg-surface-2 text-left text-xs text-muted">
                    <tr>
                      <th scope="col" className="px-4 py-2.5 font-semibold">Case</th>
                      <th scope="col" className="px-4 py-2.5 font-semibold">Topic</th>
                      <th scope="col" className="px-4 py-2.5 font-semibold">Date</th>
                      <th scope="col" className="px-4 py-2.5 font-semibold">Tricks used</th>
                      <th scope="col" className="px-4 py-2.5 font-semibold">Blind solver</th>
                      <th scope="col" className="px-4 py-2.5 font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {q.data.map((item) => {
                      const m = metaOf(item)
                      const solver = item.solver
                      return (
                        <tr key={item.id} className="border-t border-line bg-surface hover:bg-surface-2">
                          <td className="px-4 py-3">
                            <a href={href(`/editor/${item.id}`)} className="font-semibold underline-offset-2 hover:underline">
                              {item.number != null && <span className="mr-1.5 font-mono text-xs text-muted">{caseNo(item.number)}</span>}
                              {item.title ?? item.id}
                            </a>
                            {m.daily && <span className="ml-2 text-xs text-con">daily</span>}
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
                          <td className="px-4 py-3 text-xs">
                            {solver?.pass != null ? (
                              <span style={{ color: solver.pass ? 'var(--real)' : 'var(--doctored)' }} className="font-semibold">
                                {solver.pass ? '✓ pass' : '✗ fail'}
                              </span>
                            ) : item.has_solver_log ? (
                              <span className="font-semibold text-text">log on file</span>
                            ) : m.origin === 'seed' ? (
                              <span className="text-muted">hand-built</span>
                            ) : (
                              <span className="text-muted">—</span>
                            )}
                            {(solver?.difficulty ?? m.difficulty) && (
                              <span className="text-muted"> · {solver?.difficulty ?? m.difficulty}</span>
                            )}
                            {item.has_pipeline_log && <span className="block text-con">agent run logged</span>}
                          </td>
                          <td className="px-4 py-3">
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
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-mono text-xs text-muted">
            Case {caseNo(game.number)} · {game.id}
          </p>
          <h1 className="mt-1 font-display text-3xl font-bold">{game.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted">
            <StatusBadge status={meta.status} />
            <span>{meta.origin === 'pipeline' ? 'Built by the pipeline' : meta.origin === 'seed' ? 'Hand-built by the team' : meta.origin}</span>
            {meta.difficulty && <span>· {meta.difficulty}</span>}
            {meta.daily && <span className="text-con">· daily case</span>}
          </div>
          {meta.status === 'rejected' && meta.rejection_reason && (
            <p className="mt-2 text-sm">
              <b>Rejected:</b> {meta.rejection_reason}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="con" size="sm" onClick={() => setWorkshop(true)}>
            Agent run ▸
          </Button>
          <Button variant="real" onClick={() => act('approve')} disabled={busy != null || meta.status === 'approved'}>
            {busy === 'approve' ? 'Approving…' : meta.status === 'approved' ? '✓ Approved' : '✓ Approve'}
          </Button>
          <Button variant="danger" onClick={() => setRejectOpen((o) => !o)} disabled={busy != null} aria-expanded={rejectOpen}>
            ✗ Reject…
          </Button>
        </div>
      </div>

      {rejectOpen && (
        <form
          className="rise-in mt-4 flex flex-col gap-2 rounded-2xl border border-doctored/50 bg-surface p-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (reason.trim()) act('reject')
          }}
        >
          <label htmlFor="reject-reason" className="text-sm font-semibold">
            Why reject this case? (The pipeline uses this to revise it.)
          </label>
          <textarea
            id="reject-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            required
            className="rounded-xl border border-line bg-bg px-3 py-2 text-sm text-text"
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

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <section aria-labelledby="preview-h" className="min-w-0">
          <SectionLabel className="mb-3">
            <span id="preview-h">Player preview</span>
          </SectionLabel>
          <div className="mb-4 rounded-2xl border border-line bg-surface p-4 text-sm">
            <p className="font-con text-base">{game.briefing}</p>
            <p className="mt-2 text-xs text-muted">
              {game.posts.length} posts · {game.clue_budget} clues · topic: {game.topic}
            </p>
          </div>
          <div className="flex flex-col gap-4">
            {game.posts.map((p, i) => (
              <div key={p.id}>
                <p className="mb-1 text-[11px] font-bold tracking-[0.16em] text-muted uppercase">Post {i + 1}</p>
                <FeedCard post={p} caseNumber={game.number} compact />
              </div>
            ))}
          </div>
        </section>

        <section aria-labelledby="key-h" className="min-w-0">
          <SectionLabel className="mb-3">
            <span id="key-h">Answer key</span>
          </SectionLabel>
          <div className="flex flex-col gap-4">
            {data.answer_key.clean_case && (
              <div className="rounded-2xl border-2 border-con bg-con/10 p-4 text-sm">
                <b>Clean case:</b> no post is doctored.
                {data.answer_key.con_line_clean && <p className="mt-1 font-con">“{data.answer_key.con_line_clean}”</p>}
              </div>
            )}
            {game.posts.map((p, i) => {
              const k = data.answer_key.posts?.[p.id]
              if (!k) return null
              return (
                <article key={p.id} className="rounded-2xl border border-line bg-surface p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[11px] font-bold tracking-[0.16em] text-muted uppercase">Post {i + 1}</span>
                    {k.doctored ? (
                      <Chip color="var(--doctored)">✗ Doctored · {trickLabel(k.trick)}</Chip>
                    ) : (
                      <Chip color="var(--real)">✓ Real{k.suspicious_real ? ' · built to look fake' : ''}</Chip>
                    )}
                  </div>
                  {k.tell && (
                    <p className="mt-2 text-sm">
                      <b>The tell:</b> {k.tell}
                    </p>
                  )}
                  {k.explanation && <p className="mt-1.5 text-sm text-muted">{k.explanation}</p>}
                  {k.doctored && k.diff && (
                    <div className="mt-3">
                      <DiffView post={p} caseNumber={game.number} diff={k.diff} />
                    </div>
                  )}
                  <ul className="mt-3 flex flex-col gap-1 text-xs text-muted">
                    {k.con_line_fooled && (
                      <li>
                        <span className="font-semibold text-text">Con, if fooled:</span> “{k.con_line_fooled}”
                      </li>
                    )}
                    {k.con_line_caught && (
                      <li>
                        <span className="font-semibold text-text">Con, if caught:</span> “{k.con_line_caught}”
                      </li>
                    )}
                    {k.con_line_false_alarm && (
                      <li>
                        <span className="font-semibold text-text">Con, on a false alarm:</span> “{k.con_line_false_alarm}”
                      </li>
                    )}
                  </ul>
                </article>
              )
            })}

            <section className="rounded-2xl border border-line bg-surface p-4" aria-labelledby="safety-h">
              <SectionLabel className="mb-2">
                <span id="safety-h">Safety checks</span>
              </SectionLabel>
              <ul className="flex flex-col gap-1.5 text-sm">
                {checks.map((c) => (
                  <li key={c.label} className="flex items-start gap-2">
                    <span className="font-bold" style={{ color: c.ok ? 'var(--real)' : 'var(--doctored)' }}>
                      {c.ok ? '✓' : '✗'}
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
                  <p className="mt-3 text-xs font-semibold text-muted">Sources</p>
                  <ul className="mt-1 flex flex-col gap-0.5 text-xs">
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

            <section className="rounded-2xl border border-line bg-surface p-4" aria-labelledby="solver-h">
              <SectionLabel className="mb-2">
                <span id="solver-h">Blind-solver log</span>
              </SectionLabel>
              {data.solver_log ? (
                <pre className="max-h-96 overflow-auto font-mono text-xs leading-relaxed whitespace-pre-wrap thin-scroll">{data.solver_log}</pre>
              ) : (
                <p className="text-sm text-muted">No solver log: this case was hand-built by the team, not run through the pipeline.</p>
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
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
        <LinkButton to="/editor" size="sm" variant="ghost" className="mb-4 -ml-2">
          ← Puzzle queue
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
