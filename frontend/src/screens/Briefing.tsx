import { useEffect, useRef, useState } from 'react'
import conSilhouette from '../assets/figma/con-silhouette.svg'
import halftone from '../assets/figma/halftone.svg'
import { ConBubble } from '../components/ConBubble'
import { ClueToken, IconArrow } from '../components/Icon'
import { caseNo, dateRange } from '../lib/format'
import type { GameCase } from '../lib/types'

/** "Con as a newspaper photo", portrait cut: paper mount, halftone ground, the arch on the bottom edge. */
function ConPortrait({ className = '' }: { className?: string }) {
  return (
    <span className={`panel block w-full max-w-[580px] p-2.5 ${className}`}>
      <span className="relative block aspect-[4/5] overflow-hidden bg-[#E6DDCB]">
        <img
          src={halftone}
          alt=""
          aria-hidden="true"
          draggable={false}
          className="absolute inset-x-0 bottom-0 h-[45%] w-full select-none"
        />
        <img
          src={conSilhouette}
          alt="The Con"
          draggable={false}
          className="absolute bottom-0 left-1/2 h-[90%] w-auto max-w-[86%] -translate-x-1/2 object-contain object-bottom select-none"
        />
      </span>
    </span>
  )
}

/** Small caps label used on the case sheet. */
const LABEL = 'caps text-[12px] font-semibold tracking-[0.08em] text-muted'

export function Briefing({ game, onStart }: { game: GameCase; onStart: () => void }) {
  const [typed, setTyped] = useState(false)
  const startBtn = useRef<HTMLButtonElement>(null)
  const range = dateRange(game.posts.map((p) => p.posted_at))
  const tokens = Math.max(0, Math.min(8, game.clue_budget))

  useEffect(() => {
    if (typed) startBtn.current?.focus({ preventScroll: true })
  }, [typed])

  return (
    <main className="mx-auto w-full max-w-[1368px] flex-1 px-4 py-8 sm:px-6 md:py-12">
      <div className="grid items-start gap-10 md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:gap-14">
        {/* The Con: speech bubble over a newspaper photo */}
        <section aria-label="The Con’s briefing" className="flex flex-col gap-6">
          <ConBubble text={game.briefing} size="lg" className="w-full" onDone={() => setTyped(true)} />
          <ConPortrait className="hidden self-center md:block" />
        </section>

        {/* The case file: a manila frame with a tab, the paper sheet inside */}
        <section aria-labelledby="case-title" className="folder-open relative pt-8">
          <div
            aria-hidden="true"
            className="absolute top-0 left-6 flex h-9 w-56 items-center justify-center border-[1.5px] border-b-0 border-[#C9AE73] bg-manila text-[15px] italic sm:left-10"
            style={{ clipPath: 'polygon(9% 0, 91% 0, 100% 100%, 0 100%)' }}
          >
            Case file
          </div>
          <div className="border-[1.5px] border-[#C9AE73] bg-manila p-4 sm:p-8">
            <div className="relative border-2 border-ink bg-sheet p-6 shadow-[var(--hard)] sm:p-9">
              <div className="flex items-center justify-between gap-3">
                <p className={`${LABEL} !text-ink`}>Case {caseNo(game.number)}</p>
                <span
                  className="stamp text-[13px] text-press opacity-90"
                  style={{ ['--stamp-rot' as string]: '6deg', transform: 'rotate(6deg)' }}
                >
                  Classified
                </span>
              </div>
              <div className="double-rule-thin mt-1.5" aria-hidden="true" />
              <h1 id="case-title" className="mt-4 font-display text-4xl leading-[1.05] font-bold sm:text-5xl">
                {game.title}
              </h1>
              <p className="mt-5 text-[18px] italic">The real topic: {game.topic}.</p>

              <dl className="mt-6 grid grid-cols-1 gap-4 border-y-2 border-dotted border-[#B9AE99] py-4 sm:grid-cols-[0.8fr_1fr_1.7fr]">
                <div>
                  <dt className={LABEL}>Posts</dt>
                  <dd className="num mt-1 text-3xl font-bold">{game.posts.length}</dd>
                </div>
                <div>
                  <dt className={LABEL}>Clues</dt>
                  <dd className="mt-2 flex flex-wrap gap-1" aria-label={`${game.clue_budget} clue tokens`}>
                    {Array.from({ length: tokens }, (_, i) => (
                      <ClueToken key={i} size={24} />
                    ))}
                  </dd>
                </div>
                {range && (
                  <div>
                    <dt className={LABEL}>Dates</dt>
                    <dd className="num mt-1.5 text-[20px] font-semibold xl:whitespace-nowrap">{range}</dd>
                  </div>
                )}
              </dl>

              <p className="mt-6 border-2 border-press bg-[#F8E1DC] px-4 py-3 text-center text-[19px] text-press italic">
                Some posts may be doctored. Maybe none are.
              </p>
              <ul className="mt-5 grid gap-x-8 gap-y-2 text-[16px] sm:grid-cols-2">
                <li className="flex items-baseline gap-4">
                  <b className="num w-12 shrink-0 text-[24px] font-bold">+100</b> each right call
                </li>
                <li className="flex items-baseline gap-4">
                  <b className="num w-12 shrink-0 text-[24px] font-bold">+50</b> for naming the trick
                </li>
                <li className="flex items-baseline gap-4">
                  <b className="num w-12 shrink-0 text-[24px] font-bold text-press">−50</b> for accusing a real post
                </li>
                <li className="flex items-baseline gap-4">
                  <b className="num w-12 shrink-0 text-[24px] font-bold">+20</b> per unused clue
                </li>
              </ul>

              <button
                ref={startBtn}
                type="button"
                onClick={onStart}
                className="press caps mt-8 inline-flex w-full items-center justify-center gap-3 border-2 border-ink bg-ink px-6 py-4 text-xl font-semibold text-sheet hover:bg-[#2a2a2a]"
              >
                <IconArrow size={20} />
                Start investigating
              </button>
            </div>
          </div>
        </section>
      </div>
    </main>
  )
}
