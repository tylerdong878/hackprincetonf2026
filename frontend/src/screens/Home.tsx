import { useState, type ReactNode } from 'react'
import { ConPhoto, Logotype } from '../components/Art'
import { ConBubble } from '../components/ConBubble'
import { SiteHeader } from '../components/Header'
import { IconArrow, IconBook, IconFlame, IconFolder, IconLens, IconMask, ShakerMark } from '../components/Icon'
import { ErrorState } from '../components/ui'
import { api, ApiError } from '../lib/api'
import { hms, msUntilMidnightET } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { newDetective, withPlayer } from '../lib/player'
import { navigate } from '../lib/router'
import { profileExtras, useNow, usePlayerProfile } from './common'

/** The nameplate dateline, in Eastern time (the Daily rolls over at midnight ET). */
function dateline(now: Date) {
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })
    .format(now)
    .toUpperCase()
}

function Flame({ streak, onRed = false }: { streak: number; onRed?: boolean }) {
  if (streak <= 0) return null
  return (
    <span
      className={`caps inline-flex items-center gap-1.5 px-2 py-1 text-[12.5px] font-semibold ${
        onRed ? 'bg-sheet text-ink' : 'border-[1.5px] border-ink bg-sheet text-ink'
      }`}
      aria-label={`${streak}-day streak`}
    >
      <IconFlame size={15} className="flame text-press" />
      <span aria-hidden="true">
        <span className="num">{streak}</span>-day streak
      </span>
    </span>
  )
}

/** The arrow box on the red hero (Figma: paper square, ink rule). */
function ArrowBox({ red = false }: { red?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={`flex h-14 w-16 shrink-0 items-center justify-center border-2 border-ink transition group-hover:translate-x-1 sm:h-16 sm:w-24 md:w-20 xl:w-28 ${
        red ? 'bg-press text-white' : 'bg-sheet text-ink'
      }`}
    >
      <IconArrow size={26} strokeWidth={2.4} />
    </span>
  )
}

/** The red hero panel: kicker, Bodoni title, a line under it, and the arrow box. */
function HeroPanel({ kicker, title, children, aside }: { kicker?: string; title: ReactNode; children?: ReactNode; aside?: ReactNode }) {
  return (
    <span className="flex w-full items-center gap-4 px-5 py-5 sm:px-7 sm:py-7">
      <span className="min-w-0 flex-1">
        {kicker && <span className="caps block text-[12.5px] font-semibold tracking-[0.1em] text-[#FFD9D4]">{kicker}</span>}
        <span className="mt-1 block font-display text-[32px] leading-[1.04] font-bold sm:text-[40px] md:text-[34px] md:whitespace-nowrap lg:text-[40px] xl:text-[50px]">{title}</span>
        {children}
      </span>
      {aside}
    </span>
  )
}

function ConCta({ primary = false }: { primary?: boolean }) {
  if (primary) {
    return (
      <a
        href="#/con"
        className="press group relative flex w-full border-2 border-ink bg-press text-white shadow-[var(--hard)] hover:bg-press-dark"
      >
        <HeroPanel title="Con the Con" aside={<ArrowBox />}>
          <span className="mt-2 block text-[15px] text-[#FFE9E6]">Bonus round: doctor a real post and beat three AI bosses.</span>
        </HeroPanel>
      </a>
    )
  }
  return (
    <a href="#/con" className="press panel group flex w-full items-center gap-4 px-5 py-4 text-left hover:bg-surface-2 sm:px-7 sm:py-5">
      <IconMask size={36} strokeWidth={1.6} className="text-press" />
      <span className="min-w-0 flex-1">
        <span className="block font-display text-[26px] leading-tight font-bold sm:text-[32px]">Con the Con</span>
        <span className="block text-[15.5px] text-ink">Doctor a real post. Three AI bosses try to bust you, live.</span>
      </span>
      <IconArrow size={24} strokeWidth={2.4} className="text-press transition group-hover:translate-x-1" />
    </a>
  )
}

function SmallLink({ to, icon, children }: { to: string; icon: ReactNode; children: ReactNode }) {
  return (
    <a
      href={to}
      className="press caps flex min-h-[56px] items-center justify-center gap-2.5 border-2 border-ink bg-sheet px-3 text-[15px] font-bold text-ink shadow-[var(--hard)] hover:bg-surface-2"
    >
      {icon}
      {children}
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
      <SiteHeader />
      <main className="mx-auto w-full max-w-[1368px] flex-1 px-4 pt-5 pb-12 sm:px-6 md:pt-8">
        {/* Nameplate: dateline, the Gloock logotype, the double rule. The logotype is the page heading. */}
        <header className="rise-in text-center">
          <p className="dateline">{dateline(now)}</p>
          <h1 className="mt-1">
            <Logotype className="block text-[clamp(56px,11.6vw,170px)] leading-[0.95]" />
          </h1>
          <div className="double-rule mt-4" aria-hidden="true" />
          <div className="flex flex-col items-center justify-between gap-1 py-2.5 text-[17px] italic sm:flex-row sm:text-[20px]">
            <span className="text-muted">DON’T BELIEVE EVERYTHING.</span>
            <span className="text-ink">DON’T DOUBT EVERYTHING.</span>
          </div>
          <div className="double-rule-thin" aria-hidden="true" />
        </header>

        <section className="mt-7 grid gap-8 md:grid-cols-[1.2fr_1px_1fr] md:gap-7 lg:gap-9">
          {/* Left column: the Daily, Con the Con, the three sections */}
          <div className="flex min-w-0 flex-col gap-6">
            <p className="text-[17px] leading-snug text-muted italic">
              Spot the doctored post. <span className="text-ink">Don’t doubt the true ones.</span>{' '}
              <span className="whitespace-nowrap">2 minutes a day.</span>
            </p>
            {played ? (
              <>
                {/* Played today: the bonus round leads. */}
                <ConCta primary />
                <button
                  type="button"
                  onClick={() => navigate('/daily')}
                  className="press panel group flex w-full items-center gap-4 px-5 py-4 text-left hover:bg-surface-2 sm:px-7"
                >
                  <ShakerMark size={38} />
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-2 font-display text-[24px] leading-tight font-bold sm:text-[28px]">
                      Grain #{d!.daily_number} done <Flame streak={streak} />
                    </span>
                    <span className="block text-[15px] text-muted">
                      {d?.result?.share_grid || d?.result?.results?.length ? 'See your grid · ' : ''}next in{' '}
                      <span className="num font-semibold text-ink">{hms(msUntilMidnightET(now))}</span>
                    </span>
                  </span>
                  <IconArrow size={24} strokeWidth={2.4} className="transition group-hover:translate-x-1" />
                </button>
              </>
            ) : (
              <>
                {/* 1. The Daily Grain */}
                <button
                  type="button"
                  onClick={() => (noDaily || daily.status === 'ok' ? navigate('/daily') : daily.reload())}
                  disabled={daily.status === 'loading'}
                  className="press group relative flex w-full border-2 border-ink bg-press text-left text-white shadow-[var(--hard)] hover:bg-press-dark disabled:opacity-80"
                >
                  <HeroPanel
                    kicker="The Daily Grain"
                    title={
                      daily.status === 'loading'
                        ? 'Shaking out today’s Grain…'
                        : d
                          ? `Today’s Grain #${d.daily_number}`
                          : noDaily
                            ? 'Today’s Grain'
                            : 'Retry: today’s Grain'
                    }
                    aside={<ArrowBox />}
                  >
                    {d && <span className="mt-2 block text-[15px] text-[#FFE9E6]">{d.theme ? `${d.theme} · ` : ''}5 cards · about 2 minutes</span>}
                    {noDaily && <span className="mt-2 block text-[15px] text-[#FFE9E6]">The Con is still cooking today’s puzzle.</span>}
                    {streak > 0 && (
                      <span className="mt-3 inline-flex">
                        <Flame streak={streak} onRed />
                      </span>
                    )}
                  </HeroPanel>
                </button>
                {/* 2. Con the Con */}
                <ConCta />
              </>
            )}
            {daily.status === 'error' && !noDaily && <ErrorState error={daily.error} onRetry={daily.reload} />}

            <nav aria-label="Sections" className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <SmallLink to="#/casefiles" icon={<IconFolder size={20} />}>
                Case Files
              </SmallLink>
              <SmallLink to="#/dossier" icon={<IconFolder size={20} />}>
                Stats
              </SmallLink>
              <SmallLink to="#/casebook" icon={<IconBook size={20} />}>
                Tricks
              </SmallLink>
            </nav>
          </div>

          <span aria-hidden="true" className="hidden bg-ink md:block" />

          {/* Right column: the Con speaks, and his newspaper photo */}
          <figure className="flex min-w-0 flex-col gap-5">
            <ConBubble
              size="md"
              text={
                played
                  ? 'Back already? Today’s Grain is done. Fancy a rematch? Try to con me.'
                  : 'Five posts. Some real, a few of mine, maybe none. Two minutes. Care to test your eye, detective?'
              }
            />
            <ConPhoto width={560} className="self-stretch" />
            <figcaption className="-mt-2 text-[13.5px] text-muted italic">
              Pictured: the Con. Specialist in cropping, framing and selective arithmetic.
            </figcaption>
          </figure>
        </section>

        <section aria-labelledby="how" className="mt-10">
          <h2 id="how" className="sr-only">
            How it works
          </h2>
          <div className="double-rule" aria-hidden="true" />
          <ol className="grid gap-6 pt-6 sm:grid-cols-3 sm:gap-0">
            {(
              [
                [<ShakerMark key="s" size={38} />, 'One Grain a day', 'Five posts, the same for everyone. Real or doctored? Some days nothing is fake. Rare catches score big.'],
                [<IconLens key="l" size={26} />, 'Peek, then call it', 'Three magnifiers a day to peek at the receipts. Cry wolf on a true post and you lose points.'],
                [<IconMask key="m" size={30} strokeWidth={1.7} />, 'Then con the Con', 'Your turn to doctor a real post. Three boss levels of AI try to bust you, live.'],
              ] as const
            ).map(([icon, title, body], i) => (
              <li key={title} className={`min-w-0 sm:px-6 ${i ? 'sm:border-l sm:border-ink' : 'sm:pl-0'} ${i === 2 ? 'sm:pr-0' : ''}`}>
                <div className="flex items-center gap-3">
                  <span className="num text-[46px] leading-none font-bold text-press">{String(i + 1).padStart(2, '0')}</span>
                  <span className="text-ink">{icon}</span>
                  <h3 className="caps text-[24px] leading-tight font-bold tracking-[0.01em] normal-case lg:text-[26px]">{title}</h3>
                </div>
                <p className="mt-2.5 text-[15.5px] leading-snug text-ink">{body}</p>
              </li>
            ))}
          </ol>
        </section>

        <footer className="mt-10 border-t border-[#8C8270] pt-5">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
            <div className="max-w-3xl">
              <nav aria-label="More" className="caps flex flex-wrap gap-x-5 gap-y-1 text-[13px] font-semibold">
                <a href="#/casefiles" className="hover:underline">
                  Case Files <span className="font-normal normal-case">(extra cases)</span>
                </a>
                <a href="#/casebook" className="hover:underline">
                  Tricks
                </a>
                <a href="#/editor" className="hover:underline">
                  Editor’s Desk
                </a>
              </nav>
              <p className="mt-2 text-[13.5px] text-muted italic">
                Real posts are verbatim, with sources. Doctored posts only ever come from made-up accounts, and every card is watermarked. A
                human puzzle editor approves every puzzle before it goes live.
              </p>
            </div>
            <button
              type="button"
              disabled={resetting}
              className="shrink-0 text-left hover:underline sm:text-right"
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
              {resetting ? (
                <span className="caps text-[13px] font-bold">Issuing a new badge…</span>
              ) : (
                <>
                  <span className="caps block text-[13px] font-bold">Start as a new detective →</span>
                  <span className="block text-[13px] text-muted">(fresh streak, clues and stats)</span>
                </>
              )}
            </button>
          </div>
        </footer>
      </main>
    </>
  )
}
