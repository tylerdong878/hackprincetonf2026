import { useCallback, useState } from 'react'
import { ClueTokens, normalizeEvidence, type KitNotice } from '../components/EvidenceKit'
import { BarHeader } from '../components/Header'
import { IconGear } from '../components/Icon'
import { Workshop } from '../components/Workshop'
import { ErrorState, Loading } from '../components/ui'
import { api, ApiError, BACKEND_START_CMD, caseCache } from '../lib/api'
import { caseNo } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { withPlayer } from '../lib/player'
import type { AnyEvidence, GameCase, ToolId, VerdictChoice, VerdictResponse } from '../lib/types'
import { Briefing } from './Briefing'
import { Investigation } from './Investigation'
import { RevealScreen } from './RevealScreen'

type Stage = 'briefing' | 'investigating' | 'revealed'

function CaseTopBar({
  game,
  stage,
  cluesLeft,
  workshopOpen,
  onToggleWorkshop,
}: {
  game: GameCase
  stage: Stage
  cluesLeft: number
  workshopOpen: boolean
  onToggleWorkshop: () => void
}) {
  return (
    <BarHeader
      right={
        <>
          {stage === 'investigating' && (
            <span className="hidden flex-col items-start gap-0.5 md:flex">
              <span className="caps text-[11px] font-semibold tracking-[0.1em] text-muted">Clues</span>
              <ClueTokens left={cluesLeft} total={game.clue_budget} />
            </span>
          )}
          {stage !== 'briefing' && (
            <button
              type="button"
              aria-expanded={workshopOpen}
              aria-controls="workshop"
              onClick={onToggleWorkshop}
              className={`press caps ml-2 inline-flex shrink-0 items-center gap-2 border-2 border-ink px-3 py-2 text-[14px] font-semibold sm:px-4 ${
                workshopOpen ? 'bg-ink text-sheet' : 'bg-sheet text-ink shadow-[var(--hard)] hover:bg-surface-2'
              }`}
            >
              <IconGear size={17} />
              <span className="hidden sm:inline">Workshop</span>
              <span className="sr-only sm:hidden">Workshop</span>
            </button>
          )}
        </>
      }
    >
      <div className="min-w-0 leading-tight">
        <p className="caps truncate text-[11.5px] font-semibold tracking-[0.08em] text-muted">Case {caseNo(game.number)}</p>
        <p className="truncate text-[17px] italic">{game.title}</p>
      </div>
    </BarHeader>
  )
}

function CaseFlow({ game }: { game: GameCase }) {
  const [stage, setStage] = useState<Stage>('briefing')
  const [verdicts, setVerdicts] = useState<Record<string, VerdictChoice>>({})
  const [evidence, setEvidence] = useState<Record<string, Partial<Record<ToolId, AnyEvidence>>>>({})
  const [cluesLeft, setCluesLeft] = useState(game.clue_budget)
  const [loadingTool, setLoadingTool] = useState<{ postId: string; tool: ToolId } | null>(null)
  const [notice, setNotice] = useState<KitNotice | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<unknown>(null)
  const [result, setResult] = useState<VerdictResponse | null>(null)
  const [workshopOpen, setWorkshopOpen] = useState(false)

  const setVerdict = useCallback((postId: string, doctored: boolean, trick: string | null) => {
    setVerdicts((v) => ({ ...v, [postId]: { doctored, trick: doctored ? trick : null, confidence: null } }))
  }, [])

  const openTool = async (postId: string, tool: ToolId) => {
    if (evidence[postId]?.[tool] || loadingTool) return
    setLoadingTool({ postId, tool })
    setNotice(null)
    try {
      const res = await withPlayer((pid) => api.evidence(game.id, pid, postId, tool))
      setEvidence((prev) => ({ ...prev, [postId]: { ...prev[postId], [tool]: normalizeEvidence(tool, res.evidence) } }))
      if (typeof res.clues_left === 'number') setCluesLeft(res.clues_left)
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setCluesLeft(0)
        setNotice({
          postId,
          tool,
          kind: 'out',
          message: 'You’re out of clue tokens. Anything you already opened stays free to re-read. The rest is your judgment.',
        })
      } else if (e instanceof ApiError && e.backendDown) {
        setNotice({ postId, tool, kind: 'error', message: `The game server isn’t answering. Start it with: ${BACKEND_START_CMD}` })
      } else {
        setNotice({ postId, tool, kind: 'error', message: e instanceof Error ? e.message : 'Couldn’t open that evidence.' })
      }
    } finally {
      setLoadingTool(null)
    }
  }

  const submit = async () => {
    setSubmitting(true)
    setSubmitError(null)
    try {
      const res = await withPlayer((pid) => api.verdict(game.id, pid, verdicts))
      // Let the locked cards register before the reveal takes over.
      await new Promise((r) => window.setTimeout(r, 450))
      setResult(res)
      setStage('revealed')
      window.scrollTo({ top: 0 })
    } catch (e) {
      setSubmitError(e)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <CaseTopBar
        game={game}
        stage={stage}
        cluesLeft={cluesLeft}
        workshopOpen={workshopOpen}
        onToggleWorkshop={() => setWorkshopOpen((o) => !o)}
      />
      {stage === 'briefing' && <Briefing game={game} onStart={() => setStage('investigating')} />}
      {stage === 'investigating' && (
        <Investigation
          game={game}
          verdicts={verdicts}
          onVerdict={setVerdict}
          evidence={evidence}
          cluesLeft={cluesLeft}
          loadingTool={loadingTool}
          notice={notice}
          onUseTool={openTool}
          submitting={submitting}
          submitError={submitError}
          onSubmit={submit}
        />
      )}
      {stage === 'revealed' && result && <RevealScreen game={game} result={result} verdicts={verdicts} />}
      <div id="workshop">
        <Workshop caseId={game.id} open={workshopOpen} onClose={() => setWorkshopOpen(false)} unmasked={stage === 'revealed'} />
      </div>
    </>
  )
}

export function CaseScreen({ caseId }: { caseId: string }) {
  const loaded = useAsync<GameCase>(async () => {
    const cached = caseCache.get(caseId)
    if (cached) return cached
    const c = await api.getCase(caseId)
    caseCache.set(c.id, c)
    return c
  }, [caseId])

  if (loaded.status === 'loading') return <Loading label="Pulling the case file…" className="flex-1" />
  if (loaded.status === 'error') {
    const notFound = loaded.error instanceof ApiError && loaded.error.status === 404
    return (
      <main className="flex flex-1 items-center px-4 py-16">
        <ErrorState
          error={loaded.error}
          onRetry={notFound ? undefined : loaded.reload}
          title={notFound ? 'No such case on file.' : 'Couldn’t open the case.'}
        />
      </main>
    )
  }
  return <CaseFlow key={loaded.data.id} game={loaded.data} />
}
