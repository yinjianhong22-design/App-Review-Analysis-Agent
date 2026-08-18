import { useWorkflowStore } from '../stores/workflowStore'

const STAGE_LABELS: Record<string, string> = {
  scope: '1. Scope',
  collect: '2. Collect',
  clean: '3. Clean',
  classify: '4. Classify',
  evaluate: '5. Evaluate',
  plan: '6. Plan',
  prd: '7. PRD',
  testgen: '8. Test Cases',
  validate: '9. Validate',
  present: '10. Report',
}

export default function StageNavigator() {
  const { status } = useWorkflowStore()
  if (!status) return null

  return (
    <div className="card">
      <div className="flex justify-between items-center mb-3">
        <h2 className="text-lg font-semibold">Pipeline</h2>
        <span className="text-sm text-slate-500">{status.progress_pct.toFixed(0)}%</span>
      </div>
      <div className="w-full bg-slate-200 rounded-full h-2 mb-4">
        <div
          className="bg-blue-600 h-2 rounded-full transition-all duration-500"
          style={{ width: `${status.progress_pct}%` }}
        />
      </div>
      <ul className="space-y-2">
        {status.stages.map((s) => (
          <li key={s.stage} className="flex items-center justify-between text-sm">
            <span className={`stage-${s.status}`}>{STAGE_LABELS[s.stage] || s.stage}</span>
            <span className="text-xs text-slate-500 truncate max-w-[60%]" title={s.message}>
              {s.message}
            </span>
          </li>
        ))}
      </ul>
      {status.error && (
        <div className="mt-4 p-3 bg-red-50 text-red-700 text-sm rounded-md">
          {status.error}
        </div>
      )}
    </div>
  )
}
