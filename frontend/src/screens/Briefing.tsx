import { useEffect, useRef, useState } from 'react'
import { ConMascot } from '../components/Art'
import { ConBubble } from '../components/ConBubble'
import { caseNo, dateRange } from '../lib/format'
import type { GameCase } from '../lib/types'

export function Briefing({ game, onStart }: { game: GameCase; onStart: () => void }) {
  const [typed, setTyped] = useState(false)
  const startBtn = useRef<HTMLButtonElement>(null)
  const range = dateRange(game.posts.map((p) => p.posted_at))

  useEffect(() => {
    if (typed) startBtn.current?.focus({ preventScroll: true })
  }, [typed])

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 md:py-14">
      <div className="grid items-center gap-8 md:grid-cols-[1fr_1.1fr] md:gap-12">
        {/* The Con */}
        <section aria-label="The Con’s briefing" className="flex flex-col items-center gap-5 md:items-start">
          <ConBubble text={game.briefing} size="lg" className="w-full max-w-md" onDone={() => setTyped(true)} />
          <ConMascot size={220} shape="door" className="self-center md:ml-10 md:self-start" />
        </section>

        {/* The case card: a manila folder sliding open */}
        <section aria-labelledby="case-title" className="folder-open relative">
          <div className="absolute -top-6 left-6 rounded-t-lg paper-texture px-4 pt-1.5 pb-3 text-xs font-bold tracking-[0.2em] uppercase opacity-95">
            Case file
          </div>
          <div className="paper-texture relative rounded-2xl rounded-tl-none p-6 shadow-[0_24px_60px_-20px_rgba(0,0,0,0.6)] sm:p-8">
            <span
              className="stamp absolute top-5 right-5 text-sm text-[#B8322A] opacity-80"
              style={{ ['--stamp-rot' as string]: '6deg', transform: 'rotate(6deg)' }}
            >
              Classified
            </span>
            <p className="font-mono text-xs font-semibold tracking-[0.18em] text-[#6B5E45] uppercase">Case {caseNo(game.number)}</p>
            <h1 id="case-title" className="mt-2 pr-20 font-display text-3xl leading-tight font-bold sm:text-4xl">
              {game.title}
            </h1>
            <p className="mt-2 text-[15px] text-[#4B4232]">The real topic: {game.topic}.</p>

            <dl className="mt-6 grid grid-cols-1 gap-3 border-y border-dashed border-[#B9A985] py-4 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-xs font-semibold tracking-wide text-[#6B5E45] uppercase">Posts</dt>
                <dd className="mt-0.5 font-mono text-lg font-semibold">{game.posts.length}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold tracking-wide text-[#6B5E45] uppercase">Clues</dt>
                <dd className="mt-0.5 text-lg" aria-label={`${game.clue_budget} clue tokens`}>
                  {'🔍'.repeat(Math.max(0, Math.min(8, game.clue_budget)))}
                </dd>
              </div>
              {range && (
                <div>
                  <dt className="text-xs font-semibold tracking-wide text-[#6B5E45] uppercase">Dates</dt>
                  <dd className="mt-0.5 font-medium">{range}</dd>
                </div>
              )}
            </dl>

            <p className="mt-5 rounded-xl border-2 border-[#2A2418] px-4 py-3 text-center font-con text-lg tracking-wide">
              Some posts may be doctored. Maybe none are.
            </p>
            <ul className="mt-4 grid gap-1 text-[13px] text-[#4B4232] sm:grid-cols-2">
              <li>
                <b className="font-mono">+100</b> each right call
              </li>
              <li>
                <b className="font-mono">+50</b> for naming the trick
              </li>
              <li>
                <b className="font-mono">−50</b> for accusing a real post
              </li>
              <li>
                <b className="font-mono">+20</b> per unused clue
              </li>
            </ul>

            <button
              ref={startBtn}
              type="button"
              onClick={onStart}
              className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[#12141C] px-6 py-3.5 font-display text-lg font-semibold text-[#EFE4CC] transition hover:bg-black sm:w-auto"
            >
              Start investigating <span aria-hidden="true">→</span>
            </button>
          </div>
        </section>
      </div>
    </main>
  )
}
