import { useEffect } from 'react'
import { SiteHeader } from '../components/Header'
import { Button, ErrorState, LinkButton, Loading, SectionLabel } from '../components/ui'
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
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
        <p className="text-xs font-bold tracking-[0.18em] text-muted uppercase">Extra cases</p>
        <h1 className="mt-1 font-display text-3xl font-bold sm:text-4xl">Case Files 🗂️</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Done with today’s Grain? Crack a whole feed: four posts, a few clue tokens, one verdict. Then watch how the AI forged the
          case in the Workshop replay.
        </p>

        <div className="mt-6 flex flex-wrap gap-2">
          <Button
            variant="primary"
            size="lg"
            disabled={featured.status !== 'ok'}
            onClick={() => featured.status === 'ok' && navigate(`/case/${featured.data.id}`)}
          >
            {featured.status === 'ok' ? (
              <>
                Open the featured case <span className="num text-sm opacity-80">{caseNo(featured.data.number)}</span>
              </>
            ) : (
              'Loading the featured case…'
            )}
          </Button>
          <Button size="lg" onClick={next.open} disabled={next.loading}>
            {next.loading ? 'Finding…' : 'A case picked for me'}
          </Button>
          <LinkButton to="/teacher" size="lg" variant="ghost">
            Editor’s Desk →
          </LinkButton>
        </div>
        {featured.status === 'error' && <ErrorState error={featured.error} onRetry={featured.reload} className="mt-6" />}
        <NextCaseError error={next.error} onRetry={next.open} />

        <section className="mt-10" aria-labelledby="all-h">
          <SectionLabel className="mb-3">
            <span id="all-h">All approved cases</span>
          </SectionLabel>
          {list.status === 'loading' && <Loading label="Opening the filing cabinet…" />}
          {list.status === 'error' && <ErrorState error={list.error} onRetry={list.reload} />}
          {list.status === 'ok' && (
            <ul className="grid gap-3 sm:grid-cols-2">
              {list.data.map((c) => (
                <li key={c.id}>
                  <a
                    href={href(`/case/${c.id}`)}
                    className="flex h-full flex-col rounded-2xl border border-line bg-surface p-4 transition hover:border-con/60"
                  >
                    <span className="font-mono text-xs text-muted">
                      {caseNo(c.number)} {c.difficulty ? `· ${c.difficulty}` : ''} {c.origin === 'pipeline' ? '· built by the AI pipeline' : ''}
                    </span>
                    <span className="mt-1 font-display text-lg font-semibold">{c.title}</span>
                    <span className="text-sm text-muted">{c.topic}</span>
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
