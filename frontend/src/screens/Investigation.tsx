import { useCallback, useEffect, useRef, useState } from 'react'
import { ConMascot } from '../components/Art'
import { BottomSheet } from '../components/BottomSheet'
import { ConBubble } from '../components/ConBubble'
import { ClueTokens, EvidenceKit, type KitNotice } from '../components/EvidenceKit'
import { PostCard } from '../components/PostCard'
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

  // Keyboard play (SPEC §3.12): Tab through posts, R / D to mark, 1–3 to name the trick, E for evidence.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey || locked) return
      const target = e.target as HTMLElement | null
      if (target?.closest('input, textarea, select, [contenteditable="true"]')) return
      const k = e.key.toLowerCase()
      if (!['r', 'd', 'e', '1', '2', '3'].includes(k)) return
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

  const submitBtn = (
    <button
      type="button"
      onClick={onSubmit}
      disabled={!allMarked || submitting}
      className="inline-flex shrink-0 items-center gap-2 rounded-xl bg-con px-4 py-2.5 font-semibold text-on-accent shadow-[0_6px_20px_-8px_var(--con)] transition hover:brightness-110 disabled:opacity-40 disabled:shadow-none"
      title={allMarked ? 'Submit your verdicts' : 'Mark every post Real or Doctored first'}
    >
      {submitting ? 'Closing the case…' : 'Submit verdicts'} <span aria-hidden="true">→</span>
    </button>
  )

  return (
    <>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 pt-4 pb-36 md:grid md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] md:gap-6 md:pb-28">
        <section aria-labelledby="feed-heading" className="min-w-0">
          <div className="mx-auto flex max-w-[620px] flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <SectionLabel>
              <span id="feed-heading">The feed</span>
            </SectionLabel>
            <p className="hidden text-xs text-muted lg:block">
              <kbd className="font-mono">Tab</kbd> move · <kbd className="font-mono">R</kbd> real · <kbd className="font-mono">D</kbd> doctored ·{' '}
              <kbd className="font-mono">1–3</kbd> trick · <kbd className="font-mono">E</kbd> evidence
            </p>
          </div>
          <p className="mx-auto mt-2 mb-4 max-w-[620px] rounded-xl border border-dashed border-line px-3 py-2 text-center font-con text-sm text-muted">
            Some posts may be doctored. Maybe none are.
          </p>
          <div className="mx-auto flex max-w-[620px] flex-col gap-6">
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
            <div className="mx-auto mt-6 max-w-[620px]">
              <ErrorState error={submitError} onRetry={onSubmit} title="Couldn’t submit your verdicts." />
            </div>
          )}
        </section>

        {!isMobile && (
          <aside aria-label="Evidence Kit" className="hidden min-w-0 md:block">
            <div
              ref={kitRef}
              className="sticky top-[72px] max-h-[calc(100vh-72px-104px)] overflow-y-auto rounded-2xl border border-line bg-surface p-4 thin-scroll"
            >
              {kit}
            </div>
          </aside>
        )}
      </main>

      {/* Bottom dock (desktop) */}
      <div className="fixed inset-x-0 bottom-0 z-20 hidden border-t border-line bg-bg/95 backdrop-blur md:block">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
          <ConMascot size={48} className="shrink-0" />
          <ConBubble key={conLine} text={conLine} size="sm" speed={18} className="min-w-0 flex-1 md:max-w-2xl" />
          <p className="ml-auto shrink-0 text-sm text-muted" aria-live="polite">
            <span className="font-mono font-semibold text-text">{marked}</span> of {posts.length} marked
          </p>
          {submitBtn}
        </div>
      </div>

      {/* Sticky bar + Con toast (mobile) */}
      <div className="fixed inset-x-0 bottom-0 z-20 md:hidden">
        {toastVisible && (
          <div className="fade-in pointer-events-none mx-4 mb-2 flex items-end gap-2">
            <ConMascot size={36} className="shrink-0" />
            <ConBubble key={conLine} text={conLine} size="sm" typewriter={false} className="min-w-0 flex-1" />
          </div>
        )}
        <div className="flex items-center gap-3 border-t border-line bg-bg/95 px-4 py-3 backdrop-blur">
          <ClueTokens left={cluesLeft} total={game.clue_budget} />
          <p className="ml-auto text-xs whitespace-nowrap text-muted" aria-live="polite">
            <span className="font-mono font-semibold text-text">{marked}</span>/{posts.length}
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
