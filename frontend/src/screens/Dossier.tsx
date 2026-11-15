import { useState } from 'react'
import { ConMascot } from '../components/Art'
import { ConBubble } from '../components/ConBubble'
import { LeanMeter } from '../components/LeanMeter'
import { SiteHeader } from '../components/Header'
import { IconArrow, IconFlame, OutcomeSquare } from '../components/Icon'
import { TrickIcon } from '../components/TrickPicker'
import { Button, ErrorState, LinkButton, Loading, SectionLabel } from '../components/ui'
import { api } from '../lib/api'
import { conVerdictOnPlayer } from '../lib/content'
import { caseNo, outcomeStyle, pct, RANKS, shortDate, TRICK_LABELS, trickLabel } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { newDetective, withPlayer } from '../lib/player'
import type { CaseSummary, PerTrick, Profile } from '../lib/types'
import { profileExtras } from './common'

/** Figma "Rate bars": label and percentage above a ruled bar. */
function RateBar({ label, rate, color }: { label: string; rate: number; color: string }) {
  const v = pct(rate)
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2 text-[13px]">
        <span className="font-bold">{label}</span>
        <span className="num text-[14px] font-semibold">{v}%</span>
      </div>
      <div
        className="mt-1 h-3 min-w-0 overflow-hidden border-[1.5px] border-ink bg-[#E6DDCB]"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={v}
        aria-valuetext={`${v}%`}
      >
        <div className="h-full transition-[width] duration-700" style={{ width: `${v}%`, background: color }} />
      </div>
    </div>
  )
}

/** Figma "Mastery pips": three press-red squares. */
function MasteryPips({ value }: { value: number }) {
  const n = Math.max(0, Math.min(3, Math.round(value)))
  return (
    <span className="inline-flex shrink-0 items-center gap-1" role="img" aria-label={`Mastery ${n} of 3`}>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-3.5 w-3.5 border-[1.5px] border-press"
          style={{ background: i < n ? 'var(--press)' : 'transparent' }}
          aria-hidden="true"
        />
      ))}
    </span>
  )
}

/** Section heading: Bodoni title over a thin double rule. */
function SectionTitle({ id, children }: { id: string; children: string }) {
  return (
    <div className="mb-4">
      <h2 id={id} className="font-display text-3xl font-bold">
        {children}
      </h2>
      <div className="double-rule-thin mt-1.5" aria-hidden="true" />
    </div>
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
  const trickCount = Object.keys(perTrick).length

  return (
    <>
      <section className="grid gap-8 lg:grid-cols-[1.25fr_1fr] lg:items-center">
        <div className="panel p-6 sm:p-7">
          <SectionLabel className="!text-ink">Detective rating</SectionLabel>
          <div className="mt-1 flex flex-wrap items-end gap-x-5 gap-y-1">
            <span className="num text-[96px] leading-[0.95] font-bold sm:text-[112px]">{rating}</span>
            <span className="mb-3 font-display text-4xl font-semibold text-press italic sm:text-5xl">{profile.rank}</span>
          </div>
          <div className="mt-2 h-3.5 overflow-hidden border-[1.5px] border-ink bg-[#E6DDCB]" aria-hidden="true">
            <div className="h-full bg-press" style={{ width: `${rating}%` }} />
          </div>
          <p className="mt-3 text-[15px] italic">
            Discernment, not suspicion: catching fakes raises it, accusing real posts lowers it. Marking everything “doctored” lands
            near 50.
          </p>
          <dl className="mt-5 grid grid-cols-3 gap-4">
            <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
              <dt className="caps text-[12px] font-semibold tracking-[0.08em] text-muted">Cases solved</dt>
              <dd className="num text-2xl font-bold">{history.length}</dd>
            </div>
            <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
              <dt className="caps text-[12px] font-semibold tracking-[0.08em] text-muted">Posts judged</dt>
              <dd className="num text-2xl font-bold">{profile.recent?.length ?? 0}</dd>
            </div>
            <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
              <dt className="caps text-[12px] font-semibold tracking-[0.08em] text-muted">Daily streak</dt>
              <dd className="num flex items-center gap-2 text-2xl font-bold">
                {extras.streak}
                <IconFlame size={22} className={extras.streak > 0 ? 'flame text-press' : 'text-muted opacity-50'} />
              </dd>
            </div>
          </dl>
        </div>
        <div className="flex flex-col gap-3">
          <SectionLabel>What the Con thinks of you</SectionLabel>
          <div className="flex flex-col items-center gap-5 sm:flex-row">
            <ConMascot size={176} shape="circle" className="shrink-0" />
            <ConBubble text={conVerdictOnPlayer(profile.per_trick, history.length)} className="w-full min-w-0 flex-1" />
          </div>
        </div>
      </section>

      <section className="mt-10 grid gap-6 lg:grid-cols-[1fr_auto] lg:items-center" aria-label="How your guesses lean">
        <LeanMeter lean={extras.lean} label={extras.leanLabel} />
        {(profile.daily_played?.length ?? 0) > 0 && (
          <p className="text-[17px] font-bold lg:pl-6">Daily Grains played: {profile.daily_played!.length}</p>
        )}
      </section>

      <section className="mt-12" aria-labelledby="tricks-h">
        <SectionTitle id="tricks-h">By trick</SectionTitle>
        <div className={`grid gap-5 sm:grid-cols-2 ${trickCount >= 4 ? 'lg:grid-cols-4' : 'lg:grid-cols-3'}`}>
          {Object.entries(perTrick).map(([id, t]) => {
            const counts = profile.tricks?.[id]
            return (
              <div key={id} className="panel flex flex-col p-4">
                <div className="mb-4 flex items-start justify-between gap-2">
                  <a href={`#/casebook/${id}`} className="flex min-w-0 items-center gap-2 hover:underline hover:decoration-2 hover:underline-offset-4">
                    <TrickIcon trick={id} size={20} className="text-press" />
                    <span className="font-head text-[21px] leading-tight font-semibold">{trickLabel(id)}</span>
                  </a>
                  <span className="mt-1.5">
                    <MasteryPips value={t.mastery} />
                  </span>
                </div>
                <div className="flex flex-col gap-3">
                  <RateBar label="Fooled rate" rate={t.miss_rate} color="var(--press)" />
                  <RateBar label="False alarms" rate={t.false_alarm_rate} color="var(--ochre)" />
                </div>
                {counts && (
                  <p className="mt-4 text-[12.5px] text-muted">
                    seen {counts.shown ?? 0} fake · caught {counts.caught ?? 0} · honest {counts.honest_shown ?? 0} · false alarms{' '}
                    {counts.false_alarms ?? 0}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      </section>

      <section className="mt-12" aria-labelledby="history-h">
        <SectionTitle id="history-h">Case history</SectionTitle>
        {history.length === 0 ? (
          <div className="border-[1.5px] border-dashed border-[#B9AE99] p-6 text-center text-[15px] text-muted">
            No cases closed yet.{' '}
            <a href="#/daily" className="font-bold text-ink underline decoration-2 underline-offset-4 hover:text-press">
              Open today’s case
            </a>
            .
          </div>
        ) : (
          <div className="overflow-x-auto border-2 border-ink bg-sheet thin-scroll">
            <table className="w-full min-w-[560px] border-collapse text-[15px]">
              <thead className="caps bg-ink text-left text-[12.5px] tracking-[0.08em] text-sheet">
                <tr>
                  <th scope="col" className="px-4 py-3 font-semibold">Date</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Case</th>
                  <th scope="col" className="px-4 py-3 text-right font-semibold">Score</th>
                  <th scope="col" className="px-4 py-3 font-semibold">Outcomes</th>
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
                      <tr key={`${h.case_id}-${i}`} className={`border-t border-[#CFC6B4] ${i % 2 ? 'bg-[#F4ECDB]' : 'bg-sheet'}`}>
                        <td className="px-4 py-3 whitespace-nowrap">{shortDate(h.at)}</td>
                        <td className="px-4 py-3 font-bold">
                          {c ? (
                            <>
                              <span className="num mr-1 text-[13px] font-semibold text-muted">{caseNo(c.number)}</span> {c.title}
                            </>
                          ) : (
                            <span className="text-[13px]">{h.case_id}</span>
                          )}
                        </td>
                        <td className="num px-4 py-3 text-right text-[17px] font-semibold">{h.score ?? '—'}</td>
                        <td className="px-4 py-3">
                          <span
                            className="inline-flex items-center gap-1"
                            role="img"
                            aria-label={outs.map(([pid, o]) => `${pid} ${outcomeStyle(o).word}`).join(', ')}
                          >
                            {outs.map(([pid, o]) => (
                              <OutcomeSquare key={pid} outcome={o} size={24} />
                            ))}
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

      <section className="mt-8 flex flex-wrap items-center gap-x-4 gap-y-2" aria-labelledby="ranks-h">
        <SectionLabel className="mr-2">
          <span id="ranks-h">Ranks</span>
        </SectionLabel>
        <ol className="flex flex-wrap gap-2 text-[15px]">
          {RANKS.slice()
            .reverse()
            .map((r, i, arr) => (
              <li
                key={r.title}
                className={`border-[1.5px] px-3 py-1 font-bold ${profile.rank === r.title ? 'border-press bg-press text-white' : 'border-ink text-ink'}`}
              >
                {r.title}{' '}
                <span className="num text-[14px] font-medium">
                  {r.min}–{i < arr.length - 1 ? arr[i + 1].min - 1 : 100}
                </span>
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
  const fileNo = data.status === 'ok' ? data.data.profile.player_id?.replace(/[^a-zA-Z0-9]/g, '').slice(-4).toUpperCase() : ''

  return (
    <>
      <SiteHeader active="dossier" />
      <main className="mx-auto w-full max-w-[1368px] flex-1 px-4 pt-8 pb-16 sm:px-6 sm:pt-10">
        <div className="mb-10 flex flex-wrap items-end justify-between gap-6">
          <div className="min-w-0">
            {fileNo && (
              <p className="caps mb-4 inline-block bg-press px-3 py-1 text-[12.5px] font-semibold tracking-[0.08em] text-white">
                File: Detective #{fileNo}
              </p>
            )}
            <h1 className="caps text-5xl leading-[0.95] font-bold sm:text-7xl">Your Stats</h1>
            <div className="double-rule mt-2 w-full max-w-[44rem]" aria-hidden="true" />
            <p className="mt-3 text-[17px] italic">What the Con has learned about you, trick by trick.</p>
          </div>
          <div className="flex items-center gap-4">
            <LinkButton to="/" variant="primary" size="lg">
              <IconArrow size={20} />
              Play a case
            </LinkButton>
            <Button
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
        {data.status === 'loading' && <Loading label="Pulling up your stats…" />}
        {data.status === 'error' && <ErrorState error={data.error} onRetry={data.reload} title="Couldn’t load your stats." />}
        {data.status === 'ok' && <DossierBody profile={data.data.profile} cases={data.data.cases} />}
      </main>
    </>
  )
}
