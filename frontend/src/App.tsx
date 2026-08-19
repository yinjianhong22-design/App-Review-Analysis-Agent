import InputPanel from './components/InputPanel'
import StageNavigator from './components/StageNavigator'
import ResultsDashboard from './components/ResultsDashboard'
import { useWorkflowStore } from './stores/workflowStore'

function App() {
  const { result, chatOpen, setChatOpen } = useWorkflowStore()

  return (
    <div className="min-h-screen p-6">
      <header className="mb-6 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">App Review Analysis Agent</h1>
          <p className="text-sm text-slate-500">
            LangGraph-powered agent: reviews → insights → PRD
          </p>
        </div>
        {result && (
          <button
            onClick={() => setChatOpen(!chatOpen)}
            className="btn-secondary text-sm"
          >
            {chatOpen ? 'Hide Chat' : 'Ask Agent'}
          </button>
        )}
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-6">
          <InputPanel />
          <StageNavigator />
        </div>
        <div className="lg:col-span-2">
          <ResultsDashboard />
        </div>
      </div>
    </div>
  )
}

export default App
