import type { ReactNode } from 'react'
import { Logotype } from '../components/Art'
import detectiveSrc from '../assets/figma/detective-walk.svg'
import { SiteHeader } from '../components/Header'
import { IconBook, IconFlame, IconFolder, IconMask } from '../components/Icon'
import { ErrorState } from '../components/ui'
import tornV from '../assets/figma/torn-v.webp'
import { api, ApiError } from '../lib/api'
import { useAsync } from '../lib/hooks'
import { withPlayer } from '../lib/player'
import { navigate } from '../lib/router'
import { profileExtras, usePlayerProfile } from './common'

/** The white streak slip (Figma "3-DAY STREAK"). */
function StreakSlip({ streak }: { streak: number }) {
  if (streak <= 0) return null
  return (
    <span className="inline-flex items-center gap-3 bg-paper-white px-4 py-1.5 text-ink" aria-label={`${streak}-day streak`}>
      <IconFlame size={17} className="flame text-press" />
      <span aria-hidden="true" className="caps text-[16px] font-bold">
        <span className="num">{streak}</span>-day streak
      </span>
    </span>
  )
}

/** A box on the black paper: paper-white rule, transparent ground. */
const NIGHT_BOX = 'press group block w-full border-2 border-paper-white bg-night/40 text-left text-paper-white hover:bg-white/[0.06]'

/** A section link under the two cards (Figma: CASE FILES / DOSSIER / CASEBOOK). */
function SmallLink({ to, icon, children }: { to: string; icon: ReactNode; children: ReactNode }) {
  return (
    <a href={to} className={`${NIGHT_BOX} caps flex min-h-[64px] items-center justify-center gap-3 px-3 text-[15px] font-medium`}>
      {icon}
      {children}
    </a>
  )
}

/** The rules under the masthead. White type that inverts, like the logo, so it reads on both papers. */
function SplitRules({ className = '' }: { className?: string }) {
  return (
    <div className={`mix-blend-difference [--rule:#fff] ${className}`} aria-hidden="true">
      <div className="double-rule" />
      <div className="double-rule-thin mt-4" />
    </div>
  )
}

/** The Con's line and the detective walking out of frame (Figma "con-speech-bubble" + "대지 1"). */
function ConFigure({ className = '' }: { className?: string }) {
  return (
    <figure className={`relative min-w-0 flex-col ${className || 'flex'}`}>
      <figcaption className="text-[18px] leading-snug text-black italic md:pl-[17%] md:text-right">
        Five posts. Some real, a few of mine, maybe none.
        <br className="hidden md:block" /> Two minutes. Care to test your eye, detective?
      </figcaption>
      {/* Cropped at the knees so the hero stays short: he walks out of the bottom of the frame. */}
      <div className="mx-auto mt-4 aspect-[10/9] w-[78%] max-w-[420px] overflow-hidden md:mt-8 md:w-[min(500px,100%)] md:max-w-none">
        <img
          src={detectiveSrc}
          alt="The Con, a detective in a hat, breaking into shards as he walks off"
          draggable={false}
          className="pointer-events-none block h-auto w-full select-none"
        />
      </div>
    </figure>
  )
}

export function Home() {
  const daily = useAsync(() => withPlayer((pid) => api.daily(pid)), [])
  const profile = usePlayerProfile()

  const d = daily.status === 'ok' ? daily.data : null
  const played = !!d?.already_played
  const streak = Math.max(d?.result?.streak ?? 0, profileExtras(profile).streak)
  const noDaily = daily.status === 'error' && daily.error instanceof ApiError && daily.error.status === 404

  const dailyTitle =
    daily.status === 'loading'
      ? 'Shaking out today’s Grain…'
      : d
        ? played
          ? `Grain #${d.daily_number} done`
          : `Today’s Grain #${d.daily_number}`
        : noDaily
          ? 'Today’s Grain'
          : 'Retry: today’s Grain'

  return (
    <>
      <SiteHeader />
      <main className="flex-1">
        {/* ---- The front page: black paper torn down the middle (Figma "Component 1") ---- */}
        <section className="home-hero torn-hero relative overflow-hidden md:!pb-0 md:before:hidden">
          {/* Desktop: the tear runs top to bottom, black on the left. */}
          <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-20 hidden overflow-hidden md:block">
            <div className="absolute inset-y-0 left-0 bg-night" style={{ width: 'max(0px, calc(50% - 1422px))' }} />
            <img src={tornV} alt="" className="absolute top-0 max-w-none select-none" style={{ left: 'calc(50% - 1426px)', width: 1771, height: 4000 }} />
          </div>
          {/* The red halftone corner. */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute right-0 bottom-0 -z-[5] hidden h-[120px] w-[120px] md:block"
            style={{
              clipPath: 'polygon(100% 0, 100% 100%, 0 100%)',
              backgroundImage: 'radial-gradient(circle, var(--press) 38%, transparent 42%)',
              backgroundSize: '7px 7px',
            }}
          />

          <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-[58px]">
            {/* Masthead: the blackletter logo across both papers, then the rules. The logo is the page heading. */}
            <header className="pt-3 text-center md:pt-2">
              <h1 className="flex justify-center">
                <Logotype tone="split" size={180} className="[&_img]:!w-[min(1060px,92vw)]" />
              </h1>
              <SplitRules className="-mt-[2%]" />
            </header>

            <div className="grid gap-10 pt-9 pb-6 md:grid-cols-[minmax(0,645px)_1fr] md:gap-12 md:pb-0">
              {/* Left: the Daily, Con the Con, the three sections (on the black paper) */}
              <div className="flex min-w-0 flex-col gap-6 text-paper-white">
                <button
                  type="button"
                  onClick={() => (noDaily || daily.status === 'ok' ? navigate('/daily') : daily.reload())}
                  disabled={daily.status === 'loading'}
                  className={`${NIGHT_BOX} px-7 pt-9 pb-11 disabled:opacity-80`}
                >
                  <span className="caps block text-[13px] font-bold tracking-[0.02em]">The Daily Grain</span>
                  <span className="mt-1 block text-[clamp(40px,6vw,64px)] leading-[1.15] font-bold text-press">{dailyTitle}</span>
                  {streak > 0 && (
                    <span className="mt-4 flex">
                      <StreakSlip streak={streak} />
                    </span>
                  )}
                </button>

                <a href="#/con" className={`${NIGHT_BOX} flex items-center gap-8 px-8 py-7`}>
                  <IconMask size={38} strokeWidth={1.8} className="shrink-0 text-press" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[34px] leading-tight font-bold text-[#e1e4e8]">Con the Con</span>
                    <span className="block text-[16px] text-[#e1e4e8]">Doctor a real post. Our AI tries to catch you, live.</span>
                  </span>
                </a>

                {daily.status === 'error' && !noDaily && <ErrorState error={daily.error} onRetry={daily.reload} />}

                <nav aria-label="Sections" className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <SmallLink to="#/casefiles" icon={<IconFolder size={18} />}>
                    Case Files
                  </SmallLink>
                  <SmallLink to="#/dossier" icon={<IconFolder size={18} />}>
                    Dossier
                  </SmallLink>
                  <SmallLink to="#/casebook" icon={<IconBook size={18} />}>
                    Casebook
                  </SmallLink>
                </nav>
              </div>

              {/* Right: the Con speaks, and walks out of the frame (on the newsprint). Phones: below the tear. */}
              <ConFigure className="hidden md:flex" />
            </div>
            <SplitRules className="relative mt-4 hidden md:block" />
            <div className="hidden h-10 md:block" aria-hidden="true" />
          </div>
        </section>
        <div className="px-4 pt-2 sm:px-6 md:hidden">
          <ConFigure />
        </div>

      </main>
    </>
  )
}
