import { useCallback, useEffect, useRef, useState } from 'react'
import { ConMascot } from '../components/Art'
import { BottomSheet } from '../components/BottomSheet'
import { ConBubble } from '../components/ConBubble'
import { ClueTokens, EvidenceKit, type KitNotice } from '../components/EvidenceKit'
import { PostCard } from '../components/PostCard'
import { IconArrow } from '../components/Icon'
import { ErrorState, SectionLabel } from '../components/ui'
import { CON_LINES, pick } from '../lib/content'
import { useIsMobile } from '../lib/hooks'
import type { AnyEvidence, GameCase, ToolId, VerdictChoice } from '../lib/types'

export function Investigation({
  game,
  verdicts,
  onVerdict,
  evidence,
  cluesLeft,
  loadingTool,
  notice,
  onUseTool,
  submitting,
  submitError,
  onSubmit,
}: {
  game: GameCase
  verdicts: Record<string, VerdictChoice>
  onVerdict: (postId: string, doctored: boolean, trick: string | null) => void
  evidence: Record<string, Partial<Record<ToolId, AnyEvidence>>>
  cluesLeft: number
  loadingTool: { postId: string; tool: ToolId } | null
  notice: KitNotice | null
  onUseTool: (postId: string, tool: ToolId) => void
  submitting: boolean
  submitError: unknown
  onSubmit: () => void
}) {
  const isMobile = useIsMobile()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [pickerFor, setPickerFor] = useState<string | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)
  const [conLine, setConLine] = useState(() => pick(CON_LINES.idle, 0))
  const [toastVisible, setToastVisible] = useState(false)
  const cardRefs = useRef<Record<string, HTMLElement | null>>({})
  const kitRef = useRef<HTMLDivElement>(null)
  const kitHeading = useRef<HTMLHeadingElement>(null)

  const posts = game.posts
  const marked = posts.filter((p) => verdicts[p.id]).length
  const allMarked = marked === posts.length
  const locked = submitting
  const selectedIndex = posts.findIndex((p) => p.id === selectedId)
  const selected = selectedIndex >= 0 ? posts[selectedIndex] : null

  const say = useCallback((line: string) => {
    setConLine(line)
    setToastVisible(true)
  }, [])

  // Mobile toast hides itself.
  useEffect(() => {
    if (!toastVisible) return
    const id = window.setTimeout(() => setToastVisible(false), 4200)
    return () => window.clearTimeout(id)
  }, [toastVisible, conLine])

  // React to clue spending.
  const prevClues = useRef(cluesLeft)
  useEffect(() => {
    if (cluesLeft < prevClues.current) say(cluesLeft === 0 ? CON_LINES.outOfClues[0] : pick(CON_LINES.evidence))
    prevClues.current = cluesLeft
  }, [cluesLeft, say])

  useEffect(() => {
    if (submitting) say(CON_LINES.submitting[0])
  }, [submitting, say])

  const mark = useCallback(
    (postId: string, doctored: boolean, trick: string | null) => {
      const before = verdicts[postId]
      onVerdict(postId, doctored, trick)
      const nowMarked = posts.filter((p) => p.id === postId || verdicts[p.id]).length
      if (nowMarked === posts.length && !before) say(CON_LINES.allMarked[0])
      else if (!before || before.doctored !== doctored) say(pick(doctored ? CON_LINES.markDoctored : CON_LINES.markReal))
    },
    [verdicts, onVerdict, posts, say],
  )

  const focusCard = (id: string) => window.setTimeout(() => cardRefs.current[id]?.focus({ preventScroll: true }), 0)

  const openKit = useCallback(
    (postId: string) => {
      setSelectedId(postId)
      if (isMobile) setSheetOpen(true)
      else
        window.setTimeout(() => {
          const btn = kitRef.current?.querySelector<HTMLButtonElement>('ul button:not(:disabled)')
          ;(btn ?? kitHeading.current)?.focus()
        }, 0)
    },
    [isMobile],
  )

  // Keyboard play (SPEC §3.12): Tab through posts, R / D to mark, 1–4 to name the trick, E for evidence.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || locked) return
      const target = e.target as HTMLElement | null
      if (target?.closest('input, textarea, select, [contenteditable="true"]')) return
      const k = e.key.toLowerCase()
      if (!['r', 'd', 'e', '1', '2', '3', '4'].includes(k)) return
      const id = selectedId ?? posts[0]?.id
      if (!id) return
      e.preventDefault()
      if (!selectedId) {
        setSelectedId(id)
        cardRefs.current[id]?.scrollIntoView({ block: 'nearest' })
      }
      if (k === 'r') {
        setPickerFor(null)
        mark(id, false, null)
        focusCard(id)
      } else if (k === 'd') {
        mark(id, true, verdicts[id]?.trick ?? null)
        setPickerFor(id)
      } else if (k === 'e') {
        openKit(id)
      } else {
        const trick = game.trick_options[Number(k) - 1]
        if (!trick) return
        mark(id, true, trick)
        setPickerFor(null)
        focusCard(id)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selectedId, posts, verdicts, mark, openKit, game.trick_options, locked])

  const kit = (
    <EvidenceKit
      game={game}
      post={selected}
      postIndex={selectedIndex}
      cluesLeft={cluesLeft}
      opened={selected ? evidence[selected.id] ?? {} : {}}
      loadingTool={selected && loadingTool?.postId === selected.id ? loadingTool.tool : null}
      notice={notice}
      locked={locked}
      onUse={(tool) => selected && onUseTool(selected.id, tool)}
      headingRef={kitHeading}
    />
  )

  const trickKeys = `1–${Math.max(1, Math.min(4, game.trick_options.length))}`

  const submitBtn = (
    <button
      type="button"
      onClick={onSubmit}
      disabled={!allMarked || submitting}
      className="press caps inline-flex shrink-0 items-center gap-2 border-2 border-sheet bg-press px-4 py-2.5 text-[16px] font-bold text-white hover:bg-press-dark disabled:border-dashed disabled:border-[#8C8270] disabled:bg-transparent disabled:text-[#8C8270]"
      title={allMarked ? 'Submit your verdicts' : 'Mark every post Real or Doctored first'}
    >
      {submitting ? 'Closing the case…' : 'Submit verdicts'} <IconArrow size={17} />
    </button>
  )

  const progress = (
    <span className="flex gap-1" aria-hidden="true">
      {posts.map((p) => (
        <span key={p.id} className={`h-2 w-5 border border-sheet ${verdicts[p.id] ? 'bg-sheet' : ''}`} />
      ))}
    </span>
  )

  return (
    <>
      <main className="mx-auto w-full max-w-[1360px] flex-1 px-4 pt-6 pb-40 sm:px-6 md:grid md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] md:gap-8 md:pb-32">
        <section aria-labelledby="feed-heading" className="min-w-0">
          <div className="mx-auto max-w-[680px]">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <SectionLabel>
                <span id="feed-heading">The feed</span>
              </SectionLabel>
              <p className="hidden text-[12px] text-muted lg:block">
                <kbd>Tab</kbd> move · <kbd>R</kbd> real · <kbd>D</kbd> doctored · <kbd>{trickKeys}</kbd> trick · <kbd>E</kbd> evidence
              </p>
            </div>
            {/* jump strip: one tab per post */}
            <nav aria-label="Posts in this case" className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {posts.map((p, i) => {
                const v = verdicts[p.id]
                const on = selectedId === p.id
                return (
                  <button
                    key={p.id}
                    type="button"
                    aria-current={on ? 'true' : undefined}
                    onClick={() => {
                      setSelectedId(p.id)
                      cardRefs.current[p.id]?.scrollIntoView({ block: 'center', behavior: 'smooth' })
                      focusCard(p.id)
                    }}
                    className={`caps flex flex-col items-center border-2 px-2 py-1.5 leading-tight ${
                      on ? 'border-ink bg-ink text-sheet' : 'border-[#CFC6B4] bg-sheet text-ink hover:border-ink'
                    }`}
                  >
                    <span className="text-[15px] font-bold">Post {i + 1}</span>
                    <span className={`text-[11px] font-semibold tracking-[0.06em] ${on ? 'text-press-soft' : v?.doctored ? 'text-press' : 'text-muted'}`}>
                      {on ? 'inspecting' : v ? (v.doctored ? 'marked doctored' : 'marked real') : 'not marked'}
                    </span>
                  </button>
                )
              })}
            </nav>
            <p className="mt-3 mb-6 border-[1.5px] border-dashed border-press px-3 py-2.5 text-center text-[17px] text-press italic">
              Some posts may be doctored. Maybe none are.
            </p>
          </div>
          <div className="mx-auto flex max-w-[680px] flex-col gap-8">
            {posts.map((p, i) => (
              <PostCard
                key={p.id}
                ref={(el: HTMLElement | null) => {
                  cardRefs.current[p.id] = el
                }}
                post={p}
                index={i}
                caseNumber={game.number}
                trickOptions={game.trick_options}
                verdict={verdicts[p.id]}
                selected={selectedId === p.id}
                locked={locked}
                pickerOpen={pickerFor === p.id}
                onPickerOpenChange={(open) => setPickerFor(open ? p.id : null)}
                onSelect={(source) => {
                  setSelectedId(p.id)
                  if (source === 'tap' && isMobile) setSheetOpen(true)
                }}
                onMark={(doctored, trick) => mark(p.id, doctored, trick)}
                onInspect={() => openKit(p.id)}
              />
            ))}
          </div>
          {submitError != null && (
            <div className="mx-auto mt-6 max-w-[680px]">
              <ErrorState error={submitError} onRetry={onSubmit} title="Couldn’t submit your verdicts." />
            </div>
          )}
          {game.notice && <p className="mx-auto mt-6 max-w-[680px] text-center text-xs text-muted italic">{game.notice}</p>}
        </section>

        {!isMobile && (
          <aside aria-label="Evidence Kit" className="hidden min-w-0 border-l border-ink pl-6 md:block">
            <div
              ref={kitRef}
              className="panel sticky top-[88px] max-h-[calc(100vh-88px-120px)] overflow-y-auto p-5 thin-scroll"
            >
              {kit}
            </div>
          </aside>
        )}
      </main>

      {/* Bottom dock (desktop): the Con on an ink bar */}
      <div className="fixed inset-x-0 bottom-0 z-20 hidden border-t-4 border-press bg-ink text-sheet md:block">
        <div className="mx-auto flex max-w-[1360px] items-center gap-4 px-6 py-3">
          <ConMascot size={56} className="shrink-0 border-sheet" />
          <ConBubble key={conLine} text={conLine} size="md" speed={18} className="min-w-0 flex-1 !border-l-0 !px-0 !shadow-none md:max-w-2xl" />
          <div className="ml-auto flex shrink-0 flex-col items-start gap-1.5" aria-live="polite">
            <p className="caps text-[12.5px] font-semibold tracking-[0.06em]">
              <span className="num">{marked}</span> of {posts.length} marked
            </p>
            {progress}
          </div>
          {submitBtn}
        </div>
      </div>

      {/* Sticky bar + Con toast (mobile) */}
      <div className="fixed inset-x-0 bottom-0 z-20 md:hidden">
        {toastVisible && (
          <div className="fade-in pointer-events-none mx-4 mb-2 flex items-end gap-2">
            <ConMascot size={40} className="shrink-0" />
            <ConBubble key={conLine} text={conLine} size="sm" typewriter={false} className="min-w-0 flex-1" />
          </div>
        )}
        <div className="flex items-center gap-3 border-t-4 border-press bg-ink px-4 py-3 text-sheet">
          <span className="bg-sheet px-1.5 py-1">
            <ClueTokens left={cluesLeft} total={game.clue_budget} />
          </span>
          <p className="caps ml-auto text-xs whitespace-nowrap" aria-live="polite">
            <span className="num font-semibold">{marked}</span>/{posts.length}
            <span className="sr-only"> marked</span>
          </p>
          {submitBtn}
        </div>
      </div>

      <BottomSheet open={isMobile && sheetOpen} onClose={() => setSheetOpen(false)} label="Evidence Kit">
        {kit}
      </BottomSheet>
    </>
  )
}
