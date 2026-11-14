import { useState } from 'react'
import { ConMascot } from '../components/Art'
import { ConBubble } from '../components/ConBubble'
import { LeanMeter } from '../components/LeanMeter'
import { SiteHeader } from '../components/Header'
import { Button, ErrorState, LinkButton, Loading, SectionLabel } from '../components/ui'
import { api } from '../lib/api'
import { conVerdictOnPlayer } from '../lib/content'
import { caseNo, outcomeStyle, pct, RANKS, shortDate, TRICK_LABELS, trickLabel } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { newDetective, withPlayer } from '../lib/player'
import type { CaseSummary, PerTrick, Profile } from '../lib/types'
import { profileExtras } from './common'

function RateBar({ label, rate, color }: { label: string; rate: number; color: string }) {
  const v = pct(rate)
  return (
    <div className="flex items-center gap-3">
      <span className="w-24 shrink-0 text-xs text-muted">{label}</span>
      <div
        className="h-2.5 min-w-0 flex-1 overflow-hidden rounded-full bg-surface-2"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={v}
        aria-valuetext={`${v}%`}
      >
        <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${v}%`, background: color }} />
      </div>
      <span className="num w-10 shrink-0 text-right text-sm">{v}%</span>
    </div>
  )
}

function MasteryPips({ value }: { value: number }) {
  const n = Math.max(0, Math.min(3, Math.round(value)))
  return (
    <span className="inline-flex items-center gap-1" role="img" aria-label={`Mastery ${n} of 3`}>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-3 w-3 rounded-full border-2"
          style={{ borderColor: 'var(--con)', background: i < n ? 'var(--con)' : 'transparent' }}
          aria-hidden="true"
        />
      ))}
    </span>
  )
}

function DossierBody({ profile, cases }: { profile: Profile; cases: CaseSummary[] }) {
  const history = profile.history ?? []
  const perTrick: Record<string, PerTrick> = { ...profile.per_trick }
  for (const id of Object.keys(TRICK_LABELS)) perTrick[id] ??= { miss_rate: 0, false_alarm_rate: 0, mastery: 0 }
  // edited-detail only shows once the player has met it
  if (!profile.per_trick?.['edited-detail'] && !profile.tricks?.['edited-detail']) delete perTrick['edited-detail']
  const caseById = new Map(cases.map((c) => [c.id, c]))
  const rating = Math.max(0, Math.min(100, profile.rating ?? 0))
  const extras = profileExtras(profile)

  return (
    <>
      <section className="grid gap-4 md:grid-cols-[1.2fr_1fr]">
        <div className="paper-texture rounded-2xl p-6">
          <p className="text-xs font-semibold tracking-[0.18em] text-[#6B5E45] uppercase">Detective rating</p>
          <div className="mt-1 flex items-end gap-3">
            <span className="num text-6xl font-bold">{rating}</span>
            <span className="mb-2 font-display text-2xl font-semibold text-[#6D3FD8]">{profile.rank}</span>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#D9CCAE]" aria-hidden="true">
            <div className="h-full rounded-full bg-[#6D3FD8]" style={{ width: `${rating}%` }} />
          </div>
          <p className="mt-2 text-xs text-[#4B4232]">
            Discernment, not suspicion: catching fakes raises it, accusing real posts lowers it. Marking everything “doctored” lands
            near 50.
          </p>
          <dl className="mt-4 flex gap-8 text-sm">
            <div>
              <dt className="text-xs text-[#6B5E45]">Cases solved</dt>
              <dd className="num text-xl font-bold">{history.length}</dd>
            </div>
            <div>
              <dt className="text-xs text-[#6B5E45]">Posts judged</dt>
              <dd className="num text-xl font-bold">{profile.recent?.length ?? 0}</dd>
            </div>
            <div>
              <dt className="text-xs text-[#6B5E45]">Daily streak</dt>
              <dd className="num text-xl font-bold">
                <span className={extras.streak > 0 ? 'flame' : 'opacity-40 grayscale'} aria-hidden="true">
                  🔥
                </span>{' '}
                {extras.streak}
              </dd>
            </div>
          </dl>
        </div>
        <div className="flex flex-col justify-end gap-3 rounded-2xl border border-line bg-surface p-5">
          <SectionLabel>What the Con thinks of you</SectionLabel>
          <div className="flex items-end gap-3">
            <ConMascot size={64} className="shrink-0" />
            <ConBubble text={conVerdictOnPlayer(profile.per_trick, history.length)} className="min-w-0 flex-1" />
          </div>
        </div>
      </section>

      <section className="mt-4 rounded-2xl border border-line bg-surface p-5" aria-label="How your guesses lean">
        <LeanMeter lean={extras.lean} label={extras.leanLabel} />
        {(profile.daily_played?.length ?? 0) > 0 && (
          <p className="mt-3 text-xs text-muted">Daily Grains played: {profile.daily_played!.length}</p>
        )}
      </section>

      <section className="mt-8" aria-labelledby="tricks-h">
        <SectionLabel className="mb-3">
          <span id="tricks-h">By trick</span>
        </SectionLabel>
        <div className="grid gap-3 md:grid-cols-3">
          {Object.entries(perTrick).map(([id, t]) => {
            const counts = profile.tricks?.[id]
            return (
              <div key={id} className="rounded-2xl border border-line bg-surface p-4">
                <div className="mb-3 flex items-center justify-between gap-2">
                  <a href={`#/casebook/${id}`} className="font-display text-lg font-semibold hover:underline">
                    {trickLabel(id)}
                  </a>
                  <MasteryPips value={t.mastery} />
                </div>
                <div className="flex flex-col gap-2">
                  <RateBar label="Fooled rate" rate={t.miss_rate} color="var(--doctored)" />
                  <RateBar label="False alarms" rate={t.false_alarm_rate} color="var(--alarm)" />
                </div>
                {counts && (
                  <p className="mt-3 font-mono text-[11px] text-muted">
                    seen {counts.shown ?? 0} fake · caught {counts.caught ?? 0} · honest {counts.honest_shown ?? 0} · false alarms{' '}
                    {counts.false_alarms ?? 0}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      </section>

      <section className="mt-8" aria-labelledby="history-h">
        <SectionLabel className="mb-3">
          <span id="history-h">Case history</span>
        </SectionLabel>
        {history.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted">
            No cases closed yet. <a href="#/" className="font-semibold text-text underline underline-offset-2">Open today’s case</a>.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-2xl border border-line thin-scroll">
            <table className="w-full min-w-[480px] border-collapse text-sm">
              <thead className="bg-surface-2 text-left text-xs text-muted">
                <tr>
                  <th scope="col" className="px-4 py-2.5 font-semibold">Date</th>
                  <th scope="col" className="px-4 py-2.5 font-semibold">Case</th>
                  <th scope="col" className="px-4 py-2.5 text-right font-semibold">Score</th>
                  <th scope="col" className="px-4 py-2.5 font-semibold">Outcomes</th>
                </tr>
              </thead>
              <tbody>
                {history
                  .slice()
                  .reverse()
                  .map((h, i) => {
                    const c = caseById.get(h.case_id)
                    const outs = Object.entries(h.outcomes ?? {}).sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }))
                    return (
                      <tr key={`${h.case_id}-${i}`} className="border-t border-line bg-surface">
                        <td className="px-4 py-2.5 whitespace-nowrap text-muted">{shortDate(h.at)}</td>
                        <td className="px-4 py-2.5">
                          {c ? (
                            <>
                              <span className="font-mono text-xs text-muted">{caseNo(c.number)}</span> {c.title}
                            </>
                          ) : (
                            <span className="font-mono text-xs">{h.case_id}</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono tabular-nums">{h.score ?? '—'}</td>
                        <td className="px-4 py-2.5">
                          <span
                            className="tracking-[0.15em]"
                            role="img"
                            aria-label={outs.map(([pid, o]) => `${pid} ${outcomeStyle(o).word}`).join(', ')}
                          >
                            {outs.map(([, o]) => outcomeStyle(o).emoji).join('')}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="mt-8 rounded-2xl border border-line bg-surface p-5" aria-labelledby="ranks-h">
        <SectionLabel className="mb-2">
          <span id="ranks-h">Ranks</span>
        </SectionLabel>
        <ol className="flex flex-wrap gap-2 text-sm">
          {RANKS.slice()
            .reverse()
            .map((r, i, arr) => (
              <li
                key={r.title}
                className={`rounded-full border px-3 py-1 ${profile.rank === r.title ? 'border-con bg-con/15 font-semibold' : 'border-line text-muted'}`}
              >
                {r.title} <span className="font-mono text-xs">{r.min}–{i < arr.length - 1 ? arr[i + 1].min - 1 : 100}</span>
              </li>
            ))}
        </ol>
      </section>
    </>
  )
}

export function Dossier() {
  const [nonce, setNonce] = useState(0)
  const data = useAsync(async () => {
    const profile = await withPlayer((id) => api.getPlayer(id))
    const cases = await api.listCases().catch(() => [] as CaseSummary[])
    return { profile, cases }
  }, [nonce])
  const [resetting, setResetting] = useState(false)

  return (
    <>
      <SiteHeader active="dossier" />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="font-display text-3xl font-bold">Dossier</h1>
            <p className="text-sm text-muted">What the Con has learned about you, trick by trick.</p>
          </div>
          <div className="flex gap-2">
            <LinkButton to="/" size="sm">
              Play a case
            </LinkButton>
            <Button
              size="sm"
              variant="ghost"
              disabled={resetting}
              onClick={async () => {
                setResetting(true)
                try {
                  await newDetective()
                } catch {
                  /* shown by the reload below */
                } finally {
                  setResetting(false)
                  setNonce((n) => n + 1)
                }
              }}
            >
              {resetting ? 'Resetting…' : 'New detective'}
            </Button>
          </div>
        </div>
        {data.status === 'loading' && <Loading label="Opening your dossier…" />}
        {data.status === 'error' && <ErrorState error={data.error} onRetry={data.reload} title="Couldn’t open your dossier." />}
        {data.status === 'ok' && <DossierBody profile={data.data.profile} cases={data.data.cases} />}
      </main>
    </>
  )
}
