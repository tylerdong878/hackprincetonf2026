import { useEffect } from 'react'
import { ConMascot } from '../components/Art'
import { SiteHeader } from '../components/Header'
import { IconArrow, IconFolder, IconLens } from '../components/Icon'
import { Button, ErrorState, LinkButton, Loading } from '../components/ui'
import { api, caseCache } from '../lib/api'
import { caseNo } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { href, navigate } from '../lib/router'
import { NextCaseError, useNextCase } from './common'

/** Case Files: the v1 four-post feed, now an archive of extra cases (CONTRACT §8.7). */
export function CaseFiles() {
  const featured = useAsync(() => api.todayCase(), [])
  const list = useAsync(() => api.listCases(), [])
  const next = useNextCase()

  useEffect(() => {
    if (featured.status === 'ok') caseCache.set(featured.data.id, featured.data)
  }, [featured.status, featured.data])

  return (
    <>
      <SiteHeader active="casefiles" />
      <main className="mx-auto w-full max-w-[1368px] flex-1 px-4 pt-8 pb-16 sm:px-6 sm:pt-10">
        {/* Masthead: red tag, Oswald caps title over the double rule, the Con's round portrait on the right */}
        <div className="flex items-start justify-between gap-8">
          <div className="min-w-0 max-w-[860px] flex-1">
            <p className="caps mb-4 inline-block bg-press px-3 py-1 text-[12.5px] font-semibold tracking-[0.08em] text-white">
              Extra cases
            </p>
            <h1 className="caps text-5xl leading-[0.95] font-bold sm:text-7xl">Case Files</h1>
            <div className="double-rule mt-2" aria-hidden="true" />
            <p className="mt-3 text-[17px] leading-relaxed italic">
              Done with today’s Grain? Crack a whole feed: four posts, a few clue tokens, one verdict. Then watch how the AI forged the
              case in the Workshop replay.
            </p>
          </div>
          <div className="hidden shrink-0 md:block">
            <ConMascot size={200} shape="circle" />
          </div>
        </div>

        <div className="mt-8 flex flex-wrap items-center gap-4">
          <Button
            variant="primary"
            size="lg"
            disabled={featured.status !== 'ok'}
            onClick={() => featured.status === 'ok' && navigate(`/case/${featured.data.id}`)}
          >
            <IconFolder size={20} />
            {featured.status === 'ok' ? (
              <>
                Open the featured case <span className="num">{caseNo(featured.data.number)}</span>
              </>
            ) : (
              'Loading the featured case…'
            )}
          </Button>
          <Button size="lg" onClick={next.open} disabled={next.loading}>
            <IconLens size={18} />
            {next.loading ? 'Finding…' : 'A case picked for me'}
          </Button>
          <LinkButton to="/editor" size="lg" variant="ghost">
            Editor’s Desk <IconArrow size={18} />
          </LinkButton>
        </div>
        {featured.status === 'error' && <ErrorState error={featured.error} onRetry={featured.reload} className="mt-6" />}
        <NextCaseError error={next.error} onRetry={next.open} />

        <section className="mt-12" aria-labelledby="all-h">
          <div className="mb-6">
            <h2 id="all-h" className="font-display text-3xl font-bold sm:text-[34px]">
              All approved cases
            </h2>
            <div className="double-rule-thin mt-1.5" aria-hidden="true" />
          </div>
          {list.status === 'loading' && <Loading label="Opening the filing cabinet…" />}
          {list.status === 'error' && <ErrorState error={list.error} onRetry={list.reload} />}
          {list.status === 'ok' && (
            <ul className="grid gap-6 sm:grid-cols-2 sm:gap-7">
              {list.data.map((c) => (
                <li key={c.id}>
                  <a
                    href={href(`/case/${c.id}`)}
                    className="press group flex h-full items-center gap-4 border-2 border-ink bg-sheet px-6 py-5 shadow-[var(--hard)] hover:bg-surface-2"
                  >
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="caps text-[12px] font-semibold tracking-[0.08em] text-muted">
                        {caseNo(c.number)} {c.difficulty ? `· ${c.difficulty}` : ''} {c.origin === 'pipeline' ? '· built by the AI pipeline' : ''}
                      </span>
                      <span className="mt-1.5 font-display text-2xl leading-tight font-bold sm:text-[30px]">{c.title}</span>
                      <span className="mt-1.5 text-[15px] text-muted italic">{c.topic}</span>
                    </span>
                    <IconArrow size={24} className="shrink-0 text-press transition-transform group-hover:translate-x-1" />
                  </a>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </>
  )
}
