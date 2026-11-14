import { useCallback, useState } from 'react'
import { ClueTokens, normalizeEvidence, type KitNotice } from '../components/EvidenceKit'
import { Brand } from '../components/Header'
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
    <header className="sticky top-0 z-30 border-b border-line/70 bg-bg/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4">
        <span className="hidden sm:inline-flex">
          <Brand />
        </span>
        <span className="sm:hidden">
          <Brand compact />
        </span>
        <div className="min-w-0 flex-1 truncate text-sm">
          <span className="font-mono font-semibold text-muted">Case {caseNo(game.number)}</span>
          <span className="text-muted"> · </span>
          <span className="font-semibold">{game.title}</span>
        </div>
        {stage === 'investigating' && (
          <span className="hidden md:inline-flex">
            <ClueTokens left={cluesLeft} total={game.clue_budget} />
          </span>
        )}
        {stage !== 'briefing' && (
          <button
            type="button"
            aria-expanded={workshopOpen}
            aria-controls="workshop"
            onClick={onToggleWorkshop}
            className={`inline-flex shrink-0 items-center gap-1.5 rounded-xl border px-3 py-1.5 text-sm font-semibold transition ${
              workshopOpen ? 'border-con bg-con text-on-accent' : 'border-con/60 text-text hover:bg-con/15'
            }`}
          >
            <span className="hidden sm:inline">Workshop</span>
            <span className="sm:hidden" aria-hidden="true">
              ⚙
            </span>
            <span className="sr-only sm:hidden">Workshop</span>
            <span aria-hidden="true">{workshopOpen ? '◂' : '▸'}</span>
          </button>
        )}
      </div>
    </header>
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
