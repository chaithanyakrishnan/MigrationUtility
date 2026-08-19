// App.tsx — v5 KB architecture shell.
import { useEffect } from 'react'
import { useStore } from '@/store'
import { SCREEN_META, type ScreenId } from '@/nav'
import Sidebar    from '@/components/layout/Sidebar'
import Topbar     from '@/components/layout/Topbar'
import Bottombar  from '@/components/layout/Bottombar'
import StepBar    from '@/components/layout/StepBar'
import NotifStack from '@/components/shared/NotifStack'
import Home         from '@/components/screens/Home'
import Placeholder   from '@/components/screens/Placeholder'
import ReliusSchema  from '@/components/screens/ReliusSchema'
import ReliusReview  from '@/components/screens/ReliusReview'
import FrpSchema    from '@/components/screens/FrpSchema'
import FrpReview    from '@/components/screens/FrpReview'
import FrpTxnUpload from '@/components/screens/FrpTxnUpload'
import FrpTxnReview from '@/components/screens/FrpTxnReview'
import FrpSummary   from '@/components/screens/FrpSummary'
import SelectTables     from '@/components/screens/SelectTables'
import AIMapping        from '@/components/screens/AIMapping'
import TransactionCards from '@/components/screens/TransactionCards'
import BatchRun         from '@/components/screens/BatchRun'
import Observability    from '@/components/screens/Observability'

// Screens are wired flow-by-flow across the rebuild phases; unbuilt ones fall
// back to a placeholder so navigation always works.
function ActiveScreen({ screen }: { screen: ScreenId }) {
  switch (screen) {
    case 'home': return <Home />
    case 's1':   return <ReliusSchema />
    case 's2':   return <ReliusReview />
    case 's3':   return <FrpSchema />
    case 's4':   return <FrpReview />
    case 's-okb-txn':     return <FrpTxnUpload />
    case 's5':            return <FrpTxnReview />
    case 's-okb-summary': return <FrpSummary />
    case 'mig-tables':    return <SelectTables />
    case 's6':            return <AIMapping />
    case 'mig-cards':     return <TransactionCards />
    case 'mig-batch':     return <BatchRun />
    case 's-obs':         return <Observability />
    default:     return <Home />
  }
}

export default function App() {
  const currentScreen = useStore(s => s.currentScreen)
  const loadKBStatus  = useStore(s => s.loadKBStatus)

  useEffect(() => { void loadKBStatus() }, [loadKBStatus])

  const meta = currentScreen === 'home' || currentScreen === 's-obs'
    ? null
    : SCREEN_META[currentScreen as Exclude<ScreenId, 'home' | 's-obs'>]

  const title = currentScreen === 'home' ? 'Home'
    : currentScreen === 's-obs' ? 'Observability dashboard'
    : meta?.title ?? ''
  const subtitle = currentScreen === 'home' ? 'Knowledge base status and migration project launchpad'
    : currentScreen === 's-obs' ? 'Real-time migration metrics'
    : meta?.subtitle ?? ''

  return (
    <div className="app">
      <Sidebar />
      <div className="main">
        <Topbar title={title} subtitle={subtitle} />
        <div className="content">
          <StepBar />
          <ActiveScreen screen={currentScreen} />
        </div>
        <Bottombar />
      </div>
      <NotifStack />
    </div>
  )
}
