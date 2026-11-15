import { SiteHeader } from '../components/Header'
import { PostChart } from '../components/PostChart'
import { IconArrowLeft, IconBook, IconLens, IconWarn } from '../components/Icon'
import { TrickIcon } from '../components/TrickPicker'
import { LinkButton, SectionLabel } from '../components/ui'
import { CASEBOOK } from '../lib/content'
import { href } from '../lib/router'
import type { ChartSpec } from '../lib/types'

/** The worked example's own numbers, drawn the way the post drew them (Figma "Trick page"). */
const EXAMPLE_CHART: Record<string, ChartSpec> = {
  'misleading-chart': {
    type: 'bar',
    unit: '¢/kWh',
    y_min: 19,
    points: [
      { label: 'Apr 2025', value: 19.91 },
      { label: 'Jul 2026', value: 25.19 },
    ],
  },
}

/** The Casebook copy carries an emoji in front of each tool line; the UI shows icons, so drop it here. */
const noEmoji = (s: string) => s.replace(/^[\p{Extended_Pictographic}️‍]+\s*/u, '')

export function Casebook({ trickId }: { trickId?: string }) {
  const page = trickId ? CASEBOOK.find((t) => t.id === trickId) : undefined

  return (
    <>
      <SiteHeader active="casebook" />
      <main className="flex-1 pb-16">
        {page ? (
          <article className="page-wrap max-w-[1000px] pt-8 sm:pt-10">
            <a
              href={href('/casebook')}
              className="caps -ml-1 inline-flex items-center gap-1.5 px-1 py-1 text-[14px] font-semibold hover:underline hover:decoration-2 hover:underline-offset-4"
            >
              <IconArrowLeft size={16} />
              All tricks
            </a>
            <div className="mt-8 flex items-end gap-4">
              <TrickIcon trick={page.id} size={44} className="mb-2 hidden text-press sm:inline-block" />
              <h1 className="hero-title">{page.name}</h1>
            </div>
            <div className="double-rule mt-2" aria-hidden="true" />
            <p className="mt-4 text-xl leading-relaxed italic sm:text-[22px]">{page.what}</p>

            <div className="mt-10 grid gap-8">
              <section className="panel p-6">
                <SectionLabel className="!text-ink">Worked example (real material)</SectionLabel>
                <div className={EXAMPLE_CHART[page.id] ? 'mt-3 grid items-start gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]' : 'mt-3'}>
                  <p className="max-w-2xl text-[17px] leading-relaxed">{page.example}</p>
                  {EXAMPLE_CHART[page.id] && (
                    <div className="border-[1.5px] border-ink bg-white p-3 text-[#1B1B1F]" aria-hidden="true">
                      <PostChart spec={EXAMPLE_CHART[page.id]} height={220} showTitle={false} marks={{ floor: true, tone: 'trick' }} />
                    </div>
                  )}
                </div>
              </section>
              <section className="relative border-2 border-ink bg-sheet p-6 pr-14">
                <IconWarn size={24} className="absolute top-6 right-6 text-press" />
                <SectionLabel className="!text-press">The tell</SectionLabel>
                <p className="mt-3 max-w-[60ch] text-[19px] leading-[1.6] font-semibold sm:text-[20px]">{page.tell}</p>
              </section>
              <section className="relative border-2 border-ink bg-sheet p-6 pr-14">
                <IconLens size={24} className="absolute top-6 right-6 text-ink" />
                <SectionLabel className="!text-ink">How to check it</SectionLabel>
                <dl className="mt-4 grid max-w-[64ch] gap-5 text-[17px] leading-[1.6]">
                  <div>
                    <dt className="caps text-[12.5px] font-bold tracking-[0.08em] text-muted">In the game</dt>
                    <dd className="mt-1">{noEmoji(page.tool)}</dd>
                  </div>
                  <div className="border-t border-[#cfcfcf] pt-5">
                    <dt className="caps text-[12.5px] font-bold tracking-[0.08em] text-muted">In real life</dt>
                    <dd className="mt-1">{page.realWorld}</dd>
                  </div>
                </dl>
              </section>
            </div>
            <div className="mt-10 flex flex-wrap gap-4">
              <LinkButton to="/casefiles" variant="primary" size="lg">
                Play a case
              </LinkButton>
              <LinkButton to="/casebook" size="lg">
                <IconBook size={20} />
                More tricks
              </LinkButton>
            </div>
          </article>
        ) : (
          <>
            <section className="torn-hero">
              <div className="page-wrap pt-8 md:pt-[30px]">
                <div className="on-night max-w-[830px]">
                  <p className="kicker">The casebook</p>
                  <h1 className="hero-title mt-1">The Con’s Tricks</h1>
                  <div className="double-rule mt-1" aria-hidden="true" />
                  <p className="mt-3 text-[17px] leading-[1.5] italic">
                    Misinformation mostly runs on a handful of repeatable tricks. Learn the tell for each, and which check exposes it.
                  </p>
                </div>
              </div>
            </section>
            <div className="page-wrap">
            {trickId && (
              <p className="mb-6 border-2 border-ink bg-white px-4 py-3 text-[15px] text-muted">
                That trick isn’t on the Con’s list yet. Here are the ones that are.
              </p>
            )}
            <ul className="grid gap-8 md:grid-cols-2">
              {CASEBOOK.map((t, i) => (
                <li key={t.id}>
                  <a
                    href={href(`/casebook/${t.id}`)}
                    className="press group flex h-full min-h-[15rem] border-2 border-ink bg-sheet shadow-[var(--hard)] hover:border-press"
                  >
                    <span className="flex w-24 shrink-0 flex-col items-center justify-between bg-ink py-8 text-sheet transition-colors group-hover:bg-press sm:w-28">
                      <TrickIcon trick={t.id} size={44} />
                      <span className="text-[17px] italic">No. {i + 1}</span>
                    </span>
                    <span className="flex min-w-0 flex-1 flex-col p-6">
                      <span className="caps text-3xl leading-none font-bold sm:text-[38px]">{t.name}</span>
                      <span className="mt-3 flex-1 text-[16px] leading-relaxed">{t.what}</span>
                      <span className="caps mt-5 inline-flex items-center gap-1.5 self-end text-[15px] font-semibold text-press">
                        Read the tell
                      </span>
                    </span>
                  </a>
                </li>
              ))}
            </ul>
            </div>
          </>
        )}
      </main>
    </>
  )
}
