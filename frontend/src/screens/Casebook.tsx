import { SiteHeader } from '../components/Header'
import { IconArrow, IconArrowLeft, IconBook, IconLens, IconWarn } from '../components/Icon'
import { TrickIcon } from '../components/TrickPicker'
import { LinkButton, SectionLabel } from '../components/ui'
import { CASEBOOK } from '../lib/content'
import { href } from '../lib/router'

/** The Casebook copy carries an emoji in front of each tool line; the UI shows icons, so drop it here. */
const noEmoji = (s: string) => s.replace(/^[\p{Extended_Pictographic}️‍]+\s*/u, '')

export function Casebook({ trickId }: { trickId?: string }) {
  const page = trickId ? CASEBOOK.find((t) => t.id === trickId) : undefined

  return (
    <>
      <SiteHeader active="casebook" />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pt-8 pb-16 sm:pt-10">
        {page ? (
          <article className="mx-auto max-w-4xl">
            <a
              href={href('/casebook')}
              className="caps -ml-1 inline-flex items-center gap-1.5 px-1 py-1 text-[14px] font-semibold hover:underline hover:decoration-2 hover:underline-offset-4"
            >
              <IconArrowLeft size={16} />
              All tricks
            </a>
            <div className="mt-8 flex items-end gap-4">
              <TrickIcon trick={page.id} size={44} className="mb-2 hidden text-press sm:inline-block" />
              <h1 className="caps text-5xl leading-[0.95] font-bold sm:text-7xl">{page.name}</h1>
            </div>
            <div className="double-rule mt-2" aria-hidden="true" />
            <p className="mt-4 text-xl leading-relaxed italic sm:text-[22px]">{page.what}</p>

            <div className="mt-10 grid gap-8">
              <section className="panel p-6">
                <SectionLabel className="!text-ink">Worked example (real material)</SectionLabel>
                <p className="mt-3 max-w-2xl text-[17px] leading-relaxed">{page.example}</p>
              </section>
              <section className="relative border-l-[6px] border-press py-2 pr-10 pl-6">
                <IconWarn size={24} className="absolute top-2 right-2 text-press" />
                <SectionLabel className="!text-press">The tell</SectionLabel>
                <p className="mt-2 text-xl leading-snug font-bold sm:text-[22px]">{page.tell}</p>
              </section>
              <section className="relative border-l-[6px] border-ink py-2 pr-10 pl-6">
                <IconLens size={24} className="absolute top-2 right-2 text-ink" />
                <SectionLabel className="!text-ink">How to check it</SectionLabel>
                <dl className="mt-3 grid gap-x-5 gap-y-3 text-[17px] sm:grid-cols-[auto_1fr]">
                  <dt className="font-bold">In the game:</dt>
                  <dd>{noEmoji(page.tool)}</dd>
                  <dt className="font-bold">In real life:</dt>
                  <dd>{page.realWorld}</dd>
                </dl>
              </section>
            </div>
            <div className="mt-10 flex flex-wrap gap-4">
              <LinkButton to="/" variant="primary" size="lg">
                <IconArrow size={20} />
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
            <p className="caps mb-4 inline-block bg-press px-3 py-1 text-[12.5px] font-semibold tracking-[0.08em] text-white">
              The trick library
            </p>
            <h1 className="caps text-5xl leading-[0.95] font-bold sm:text-7xl">The Con’s Tricks</h1>
            <div className="double-rule mt-2 max-w-3xl" aria-hidden="true" />
            <p className="mt-3 max-w-3xl text-[17px] italic">
              Misinformation mostly runs on a handful of repeatable tricks. Learn the tell for each, and which check exposes it.
            </p>
            {trickId && (
              <p className="mt-6 border-2 border-ink bg-sheet px-4 py-3 text-[15px] text-muted">
                That trick isn’t on the Con’s list yet. Here are the ones that are.
              </p>
            )}
            <ul className="mt-10 grid gap-8 md:grid-cols-2">
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
                        <IconArrow size={16} className="transition-transform group-hover:translate-x-0.5" />
                      </span>
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          </>
        )}
      </main>
    </>
  )
}
