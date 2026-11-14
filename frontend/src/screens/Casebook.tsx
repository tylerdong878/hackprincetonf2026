import { SiteHeader } from '../components/Header'
import { LinkButton, SectionLabel } from '../components/ui'
import { CASEBOOK } from '../lib/content'
import { href } from '../lib/router'

export function Casebook({ trickId }: { trickId?: string }) {
  const page = trickId ? CASEBOOK.find((t) => t.id === trickId) : undefined

  return (
    <>
      <SiteHeader active="casebook" />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        {page ? (
          <article className="mx-auto max-w-3xl">
            <LinkButton to="/casebook" size="sm" variant="ghost" className="-ml-2">
              ← All tricks
            </LinkButton>
            <p className="mt-4 text-4xl" aria-hidden="true">
              {page.icon}
            </p>
            <h1 className="mt-2 font-display text-4xl font-bold">{page.name}</h1>
            <p className="mt-3 text-lg text-muted">{page.what}</p>

            <div className="mt-8 grid gap-4">
              <section className="paper-texture rounded-2xl p-5">
                <h2 className="text-xs font-bold tracking-[0.18em] text-[#6B5E45] uppercase">Worked example (real material)</h2>
                <p className="mt-2 text-[15px]">{page.example}</p>
              </section>
              <section className="rounded-2xl border-l-4 border-doctored bg-surface p-5">
                <SectionLabel>The tell</SectionLabel>
                <p className="mt-2 text-[15px]">{page.tell}</p>
              </section>
              <section className="rounded-2xl border-l-4 border-focus bg-surface p-5">
                <SectionLabel>How to check it</SectionLabel>
                <p className="mt-2 text-[15px]">
                  <b>In the game:</b> {page.tool}
                </p>
                <p className="mt-2 text-[15px]">
                  <b>In real life:</b> {page.realWorld}
                </p>
              </section>
            </div>
            <div className="mt-8 flex flex-wrap gap-2">
              <LinkButton to="/" variant="primary">
                Play a case
              </LinkButton>
              <LinkButton to="/casebook">More tricks</LinkButton>
            </div>
          </article>
        ) : (
          <>
            <h1 className="font-display text-3xl font-bold">The Con’s Tricks</h1>
            <p className="mt-1 max-w-2xl text-sm text-muted">
              Misinformation mostly runs on a handful of repeatable tricks. Learn the tell for each, and which check exposes it.
            </p>
            {trickId && (
              <p className="mt-4 rounded-xl border border-line bg-surface px-4 py-3 text-sm text-muted">
                That trick isn’t on the Con’s list yet. Here are the ones that are.
              </p>
            )}
            <ul className="mt-6 grid gap-4 md:grid-cols-3">
              {CASEBOOK.map((t) => (
                <li key={t.id}>
                  <a
                    href={href(`/casebook/${t.id}`)}
                    className="flex h-full flex-col rounded-2xl border border-line bg-surface p-5 transition hover:-translate-y-0.5 hover:border-con/60"
                  >
                    <span className="text-3xl" aria-hidden="true">
                      {t.icon}
                    </span>
                    <span className="mt-3 font-display text-xl font-semibold">{t.name}</span>
                    <span className="mt-1 flex-1 text-sm text-muted">{t.what}</span>
                    <span className="mt-4 text-sm font-semibold text-con">Read the tell →</span>
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
