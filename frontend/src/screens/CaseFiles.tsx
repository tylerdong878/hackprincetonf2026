import { useEffect } from 'react'
import { SiteHeader } from '../components/Header'
import { IconFolder, IconLens } from '../components/Icon'
import { Button, ErrorState, Loading } from '../components/ui'
import { api, ApiError, caseCache } from '../lib/api'
import { caseNo } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { href, navigate } from '../lib/router'
import { NextCaseError, useNextCase } from './common'

/** Case Files: the v1 four-post feed, now an archive of extra cases (CONTRACT §8.7). */
export function CaseFiles() {
  const featured = useAsync(() => api.todayCase(), [])
  const list = useAsync(() => api.listCases(), [])
  const next = useNextCase()
  // No approved Case Files yet (every one waits for a human editor): say so instead of an error.
  const noCases =
    (list.status === 'ok' && list.data.length === 0) ||
    (featured.status === 'error' && featured.error instanceof ApiError && featured.error.status === 404)

  useEffect(() => {
    if (featured.status === 'ok') caseCache.set(featured.data.id, featured.data)
  }, [featured.status, featured.data])

  return (
    <>
      <SiteHeader active="casefiles" />
      <main className="flex-1 pb-16">
        {/* Masthead on the black paper: red kicker, Iosevka caps title over the double rule, the two ways in. */}
        <section className="torn-hero">
          <div className="page-wrap pt-8 md:pt-[30px]">
            <div className="on-night max-w-[830px]">
              <p className="kicker">Learn more</p>
              <h1 className="hero-title mt-1">Case Files</h1>
              <div className="double-rule mt-1 max-w-[780px]" aria-hidden="true" />
              <p className="mt-3 text-[17px] leading-[1.5] italic">
                Four posts to investigate one at a time: spend clue tokens on real evidence, mark every post, then walk through the
                side-by-side reveal. You can replay how the AI built each case in the Workshop.
              </p>
            </div>
            {!noCases && (
            <div className="mt-6 flex flex-wrap items-center gap-5">
              <Button
                variant="primary"
                size="lg"
                className="w-full sm:w-auto sm:min-w-[400px]"
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
              <Button size="lg" className="w-full sm:w-auto sm:min-w-[300px]" onClick={next.open} disabled={next.loading}>
                <IconLens size={20} />
                {next.loading ? 'Finding…' : 'A case picked for me'}
              </Button>
            </div>
            )}
            {featured.status === 'error' && !noCases && <ErrorState error={featured.error} onRetry={featured.reload} className="mt-6" />}
          </div>
        </section>

        <div className="page-wrap">
          <NextCaseError error={next.error} onRetry={next.open} />

          {noCases && (
            <div className="paper-card mb-10 max-w-[860px] bg-white/90 px-6 py-6">
              <p className="text-2xl font-bold">No Case Files on the shelf yet.</p>
              <p className="mt-2 text-[16px] leading-relaxed">
                The Con’s agents build every case, and a human editor approves each one before it goes live. The next one is waiting on
                the Editor’s Desk.
              </p>
            </div>
          )}
          <section aria-labelledby="all-h">
            <div className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
              <h2 id="all-h" className="text-[34px] leading-tight font-bold">
                All approved cases
              </h2>
              <a href={href('/editor')} className="caps inline-flex items-center gap-1.5 pb-1 text-[13px] font-bold hover:underline">
                Editor’s Desk
              </a>
              <div className="double-rule-thin w-full" aria-hidden="true" />
            </div>
            {list.status === 'loading' && <Loading label="Opening the filing cabinet…" />}
            {list.status === 'error' && <ErrorState error={list.error} onRetry={list.reload} />}
            {list.status === 'ok' && !noCases && (
              <ul className="grid gap-6 md:grid-cols-2 md:gap-x-8">
                {list.data.map((c) => (
                  <li key={c.id}>
                    <a href={href(`/case/${c.id}`)} className="press paper-card group flex h-full min-h-[140px] items-center gap-4 px-6 py-5 hover:bg-white/90">
                      <span className="flex min-w-0 flex-1 flex-col">
                        <span className="text-[28px] leading-tight font-bold sm:text-[32px]">{c.title}</span>
                        <span className="mt-1.5 text-[16px] text-muted italic">{c.topic}</span>
                        <span className="caps mt-2 text-[11.5px] font-bold tracking-[0.06em] text-muted">
                          {caseNo(c.number)}{c.difficulty ? `, ${c.difficulty}` : ''}
                        </span>
                      </span>
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <footer className="mt-9">
            <div className="double-rule" aria-hidden="true" />
            <p className="mt-6 text-[19px] italic">
              All solved? “You’ve solved every case file on record. The Con is preparing new ones.”
            </p>
          </footer>
        </div>
      </main>
    </>
  )
}
