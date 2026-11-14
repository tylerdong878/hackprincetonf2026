import { useState } from 'react'
import { ConMascot, Logo } from '../components/Art'
import { ConBubble } from '../components/ConBubble'
import { SiteHeader } from '../components/Header'
import { ErrorState } from '../components/ui'
import { api, ApiError } from '../lib/api'
import { hms, msUntilMidnightET } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { newDetective, withPlayer } from '../lib/player'
import { navigate } from '../lib/router'
import { profileExtras, RatingBadge, useNow, usePlayerProfile } from './common'

function Flame({ streak }: { streak: number }) {
  if (streak <= 0) return null
  return (
    <span
      className="num inline-flex items-center gap-1 rounded-full bg-black/25 px-2.5 py-1 text-sm font-semibold"
      aria-label={`${streak}-day streak`}
    >
      <span className="flame" aria-hidden="true">
        🔥
      </span>
      {streak}
    </span>
  )
}

function ConCta({ primary = false }: { primary?: boolean }) {
  if (primary) {
    return (
      <a
        href="#/con"
        className="group relative flex w-full flex-col items-center overflow-hidden rounded-3xl bg-con px-6 py-5 text-on-accent shadow-[0_14px_40px_-12px_var(--con)] transition hover:brightness-110 active:scale-[0.99] md:items-start"
      >
        <span className="flex w-full items-center justify-center gap-3 font-display text-2xl font-bold sm:text-3xl md:justify-start">
          <span aria-hidden="true">🎭</span> Con the Con
          <span aria-hidden="true" className="transition group-hover:translate-x-1 md:ml-auto">
            →
          </span>
        </span>
        <span className="mt-1 text-sm opacity-90">Bonus round: doctor a real post and beat three AI bosses.</span>
      </a>
    )
  }
  return (
    <a
      href="#/con"
      className="group flex w-full items-center gap-4 rounded-3xl border-2 border-con bg-surface px-5 py-4 text-left transition hover:bg-con/15 active:scale-[0.99]"
    >
      <span className="text-3xl" aria-hidden="true">
        🎭
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-display text-xl font-semibold">Con the Con</span>
        <span className="block text-sm text-muted">Doctor a real post. Three AI bosses try to bust you, live.</span>
      </span>
      <span aria-hidden="true" className="text-xl transition group-hover:translate-x-1">
        →
      </span>
    </a>
  )
}

export function Home() {
  const daily = useAsync(() => withPlayer((pid) => api.daily(pid)), [])
  const profile = usePlayerProfile()
  const [resetting, setResetting] = useState(false)
  const now = useNow(1000)

  const d = daily.status === 'ok' ? daily.data : null
  const played = !!d?.already_played
  const streak = Math.max(d?.result?.streak ?? 0, profileExtras(profile).streak)
  const noDaily = daily.status === 'error' && daily.error instanceof ApiError && daily.error.status === 404

  return (
    <>
      <SiteHeader right={<RatingBadge profile={profile} />} />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pt-6 pb-16 md:pt-12">
        <section className="grid items-center gap-8 md:grid-cols-[1.2fr_1fr] md:gap-10">
          <div className="rise-in flex flex-col items-center text-center md:items-start md:text-left">
            {/* The main logo already carries the name, so it is the page heading. */}
            <h1 className="-ml-2">
              <Logo size={200} />
            </h1>
            <p className="mt-1 max-w-md font-display text-xl font-medium text-muted sm:text-2xl">
              Spot the doctored post. <span className="text-text">Don’t doubt the true ones.</span>{' '}
              <span className="whitespace-nowrap">2 minutes a day.</span>
            </p>

            <div className="mt-7 flex w-full max-w-md flex-col gap-3">
              {played ? (
                <>
                  {/* Played today: the bonus round leads. */}
                  <ConCta primary />
                  <button
                    type="button"
                    onClick={() => navigate('/daily')}
                    className="group flex w-full items-center gap-4 rounded-3xl border-2 border-line bg-surface px-5 py-4 text-left transition hover:border-muted active:scale-[0.99]"
                  >
                    <span className="text-3xl" aria-hidden="true">
                      🧂
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-2 font-display text-xl font-semibold">
                        Grain #{d!.daily_number} done <Flame streak={streak} />
                      </span>
                      <span className="block text-sm text-muted">
                        {d?.result?.share_grid || d?.result?.results?.length ? 'See your grid · ' : ''}next in{' '}
                        <span className="num font-semibold text-text">{hms(msUntilMidnightET(now))}</span>
                      </span>
                    </span>
                    <span aria-hidden="true" className="text-xl transition group-hover:translate-x-1">
                      →
                    </span>
                  </button>
                </>
              ) : (
                <>
                  {/* 1. The Daily Grain */}
                  <button
                    type="button"
                    onClick={() => (noDaily || daily.status === 'ok' ? navigate('/daily') : daily.reload())}
                    disabled={daily.status === 'loading'}
                    className="group relative flex w-full flex-col items-center overflow-hidden rounded-3xl bg-con px-6 py-5 text-on-accent shadow-[0_14px_40px_-12px_var(--con)] transition hover:brightness-110 active:scale-[0.99] disabled:opacity-70 md:items-start"
                  >
                    <span className="flex w-full items-center justify-center gap-3 md:justify-start">
                      <span className="font-display text-2xl font-bold sm:text-3xl">
                        {daily.status === 'loading'
                          ? 'Shaking out today’s Grain…'
                          : d
                            ? `Play today’s Grain #${d.daily_number}`
                            : noDaily
                              ? 'Today’s Grain'
                              : 'Retry: today’s Grain'}
                      </span>
                      <span className="md:ml-auto">
                        <Flame streak={streak} />
                      </span>
                    </span>
                    {d && (
                      <span className="mt-1 text-sm opacity-90">
                        {d.theme ? `${d.theme} · ` : ''}5 cards · about 2 minutes
                      </span>
                    )}
                    {noDaily && <span className="mt-1 text-sm opacity-90">The Con is still cooking today’s puzzle.</span>}
                  </button>
                  {/* 2. Con the Con */}
                  <ConCta />
                </>
              )}
            </div>
            {daily.status === 'error' && !noDaily && (
              <div className="mt-6 w-full max-w-md">
                <ErrorState error={daily.error} onRetry={daily.reload} />
              </div>
            )}
          </div>

          <div className="relative mx-auto flex w-full max-w-sm flex-col items-center">
            <ConBubble
              size="md"
              className="mb-4 w-full max-w-xs self-end"
              text={
                played
                  ? 'Back already? Today’s Grain is done. Fancy a rematch? Try to con me.'
                  : 'Five posts. Some real, a few of mine, maybe none. Two minutes. Care to test your eye, detective?'
              }
            />
            <ConMascot size={240} shape="door" className="relative" />
          </div>
        </section>

        <section aria-labelledby="how" className="mt-14">
          <h2 id="how" className="sr-only">
            How it works
          </h2>
          <ol className="grid gap-3 sm:grid-cols-3">
            {[
              ['🧂', 'One Grain a day', 'Five posts, the same for everyone. Real or doctored? Some days nothing is fake. Rare catches score big.'],
              ['🔍', 'Peek, then call it', 'Three magnifiers a day to peek at the receipts. Cry wolf on a true post and you lose points.'],
              ['🎭', 'Then con the Con', 'Your turn to doctor a real post. Three boss levels of AI try to bust you, live.'],
            ].map(([icon, title, body], i) => (
              <li key={title} className="relative rounded-2xl border border-line bg-surface p-5">
                <span className="text-2xl" aria-hidden="true">
                  {icon}
                </span>
                <h3 className="mt-2 font-display text-lg font-semibold">
                  <span className="mr-1.5 font-mono text-sm text-muted">{i + 1}.</span>
                  {title}
                </h3>
                <p className="mt-1 text-sm text-muted">{body}</p>
              </li>
            ))}
          </ol>
        </section>

        <footer className="mt-12 flex flex-col items-center gap-3 text-center text-xs text-muted">
          <nav aria-label="More" className="flex flex-wrap justify-center gap-x-4 gap-y-1 text-sm font-semibold">
            <a href="#/casefiles" className="hover:text-text">
              Case Files <span className="font-normal">(extra cases)</span>
            </a>
            <a href="#/casebook" className="hover:text-text">
              Casebook
            </a>
            <a href="#/teacher" className="hover:text-text">
              Editor’s Desk
            </a>
          </nav>
          <p className="max-w-xl">
            Real posts are verbatim, with sources. Doctored posts only ever come from made-up accounts, and every card is watermarked. A
            human puzzle editor approves every puzzle before it goes live.
          </p>
          <button
            type="button"
            disabled={resetting}
            className="rounded-lg px-2 py-1 font-semibold underline underline-offset-2 hover:text-text"
            onClick={async () => {
              setResetting(true)
              try {
                await newDetective()
                daily.reload()
              } catch {
                /* backend down: the next action will retry */
              } finally {
                setResetting(false)
              }
            }}
          >
            {resetting ? 'Issuing a new badge…' : 'Start as a new detective (fresh streak, clues and dossier)'}
          </button>
        </footer>
      </main>
    </>
  )
}
