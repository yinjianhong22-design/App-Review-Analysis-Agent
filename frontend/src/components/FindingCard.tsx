import { useWorkflowStore } from '../stores/workflowStore'

export default function FindingCard() {
  const { result } = useWorkflowStore()
  if (!result) return null

  const findings = result.findings || []

  return (
    <div className="space-y-3">
      <h3 className="font-semibold">Findings ({findings.length})</h3>
      {findings.length === 0 && <p className="text-sm text-slate-500">No findings yet.</p>}
      {findings.map((f, idx) => {
        const finding = f as Record<string, any>
        return (
          <div key={idx} className="card border-l-4 border-l-blue-500">
            <div className="flex justify-between items-start">
              <h4 className="font-medium">{(finding.statement as string) || 'Untitled finding'}</h4>
              {finding.status === 'ASSUMPTION' && (
                <span className="text-xs bg-amber-100 text-amber-800 px-2 py-0.5 rounded">ASSUMPTION</span>
              )}
            </div>
            <div className="mt-2 text-sm text-slate-600">
              <p>Confidence: <span className="font-medium">{Math.round(((finding.confidence as number) || 0) * 100)}%</span></p>
              <p>Supporting reviews: {((finding.supporting_reviews as string[]) || []).length}</p>
            </div>
            {((finding.supporting_reviews as string[]) || []).length > 0 && (
              <div className="mt-2 text-xs text-slate-500">
                Sources: {((finding.supporting_reviews as string[]) || []).join(', ')}
              </div>
            )}
            {finding.uncertainty && (
              <p className="mt-2 text-xs text-slate-500 italic">{String(finding.uncertainty)}</p>
            )}
          </div>
        )
      })}
    </div>
  )
}
