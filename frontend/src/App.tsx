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
import { TeacherCaseScreen, TeacherQueue } from './screens/Teacher'

function NotFound() {
  return (
    <>
      <SiteHeader />
      <main className="flex flex-1 flex-col items-center justify-center gap-4 px-4 py-20 text-center">
        <h1 className="font-display text-3xl font-bold">Nothing in this drawer.</h1>
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
  teacher: 'Teacher mode',
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

  if (!head) return <Home />
  if (head === 'daily') return <DailyScreen />
  if (head === 'con') return <ConTheCon />
  if (head === 'casefiles') return <CaseFiles />
  if (head === 'case' && arg) return <CaseScreen key={arg} caseId={arg} />
  if (head === 'dossier') return <Dossier />
  if (head === 'teacher') return arg ? <TeacherCaseScreen key={arg} caseId={arg} /> : <TeacherQueue />
  if (head === 'casebook') return <Casebook key={arg ?? 'all'} trickId={arg} />
  return <NotFound />
}
