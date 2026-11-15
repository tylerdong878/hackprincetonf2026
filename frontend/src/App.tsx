import { useEffect } from 'react'
import { SiteHeader } from './components/Header'
import { LinkButton } from './components/ui'
import { useRoute } from './lib/router'
import { CaseFiles } from './screens/CaseFiles'
import { CaseScreen } from './screens/CaseScreen'
import { Casebook } from './screens/Casebook'
import { bootstrapPlayer } from './screens/common'
import { ConTheCon } from './screens/ConTheCon'
import { DailyScreen } from './screens/Daily'
import { Dossier } from './screens/Dossier'
import { Home } from './screens/Home'
import { EditorCaseScreen, EditorQueue } from './screens/EditorDesk'

function NotFound() {
  return (
    <>
      <SiteHeader />
      <main className="flex flex-1 flex-col items-center justify-center gap-4 px-4 py-20 text-center">
        <h1 className="hero-title !text-5xl">Nothing in this drawer.</h1>
        <p className="text-muted">That page isn’t on file.</p>
        <LinkButton to="/" variant="primary">
          Back to the case room
        </LinkButton>
      </main>
    </>
  )
}

const TITLES: Record<string, string> = {
  daily: 'The Daily Grain',
  con: 'Con the Con',
  casefiles: 'Case Files',
  case: 'Case',
  dossier: 'Dossier',
  editor: 'Editor’s Desk',
  casebook: 'Casebook',
}

export default function App() {
  const route = useRoute()
  const [head, arg] = route

  useEffect(() => {
    bootstrapPlayer()
  }, [])

  useEffect(() => {
    document.title = head && TITLES[head] ? `${TITLES[head]} · Grain of Salt` : 'Grain of Salt'
  }, [head])

  // Back-compat: the Editor's Desk used to live at #/teacher. Old links redirect to #/editor.
  const legacyDesk = head === 'teacher'
  useEffect(() => {
    if (legacyDesk) window.location.replace(`#/editor${arg ? `/${encodeURIComponent(arg)}` : ''}`)
  }, [legacyDesk, arg])

  return (
    <>
      {/* The newspaper collage over the whole page (Figma), under every screen's content. */}
      <div className="collage-layer" aria-hidden="true" />
      <Screen head={head} arg={arg} legacyDesk={legacyDesk} />
    </>
  )
}

function Screen({ head, arg, legacyDesk }: { head: string | undefined; arg: string | undefined; legacyDesk: boolean }) {
  if (!head) return <Home />
  if (head === 'daily') return <DailyScreen />
  if (head === 'con') return <ConTheCon />
  if (head === 'casefiles') return <CaseFiles />
  if (head === 'case' && arg) return <CaseScreen key={arg} caseId={arg} />
  if (head === 'dossier') return <Dossier />
  if (head === 'editor') return arg ? <EditorCaseScreen key={arg} caseId={arg} /> : <EditorQueue />
  if (legacyDesk) return null // redirecting to #/editor (see above)
  if (head === 'casebook') return <Casebook key={arg ?? 'all'} trickId={arg} />
  return <NotFound />
}
