import InputPanel from './components/InputPanel'
import StageNavigator from './components/StageNavigator'
import ResultsDashboard from './components/ResultsDashboard'

function App() {
  return (
    <div className="min-h-screen p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">App Review Analysis Agent</h1>
        <p className="text-sm text-slate-500">
          Transform U.S. App Store reviews into PRDs, roadmaps, and test cases.
        </p>
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
