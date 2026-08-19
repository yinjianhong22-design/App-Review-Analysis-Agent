import { useWorkflowStore } from '../stores/workflowStore'
import ChatPanel from './ChatPanel'

const TABS = [
  { id: 'overview', label: 'Summary' },
  { id: 'findings', label: 'Findings' },
  { id: 'prd', label: 'PRD' },
  { id: 'testcases', label: 'Test Cases' },
  { id: 'reviews', label: 'Reviews' },
]

export default function ResultsDashboard() {
  const { result, activeTab, setActiveTab, exportReport } = useWorkflowStore()

  if (!result) {
    return (
      <div className="card text-slate-500 text-sm">
        Start an analysis to see results here.
      </div>
    )
  }

  const findings = result.findings || []
  const versionPlan = result.prd?.version_plan || result.version_plan || []
  const requirements = versionPlan.flatMap((vp: any) => vp.requirements || [])
  const testCases = result.test_cases || []
  const hypothesisCount = findings.filter((f: any) => f.is_hypothesis).length

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-2">
        <div className="flex flex-wrap gap-2">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1 text-sm rounded-t-md transition ${
                activeTab === tab.id
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => exportReport('prd_doc')}
            className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700"
          >
            Download PRD
          </button>
          <button
            onClick={() => exportReport('test_cases_doc')}
            className="px-3 py-1 text-sm bg-purple-600 text-white rounded hover:bg-purple-700"
          >
            Download Test Cases
          </button>
        </div>
      </div>

      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 space-y-4">
            <div className="card">
              <h3 className="font-semibold mb-2">Analysis Summary</h3>
              <div className="text-sm text-slate-700 whitespace-pre-wrap">
                {result.summary || 'Summary will appear here after analysis completes.'}
              </div>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="card text-center">
                <div className="text-2xl font-bold text-blue-600">{result.cleaned_reviews?.length || 0}</div>
                <div className="text-xs text-slate-500">Reviews</div>
              </div>
              <div className="card text-center">
                <div className="text-2xl font-bold text-purple-600">{findings.length}</div>
                <div className="text-xs text-slate-500">Findings</div>
              </div>
              <div className="card text-center">
                <div className="text-2xl font-bold text-green-600">{requirements.length}</div>
                <div className="text-xs text-slate-500">Requirements</div>
              </div>
              <div className="card text-center">
                <div className="text-2xl font-bold text-purple-600">{testCases.length}</div>
                <div className="text-xs text-slate-500">Test Cases</div>
              </div>
            </div>
            {hypothesisCount > 0 && (
              <div className="card bg-amber-50 border-amber-200">
                <p className="text-sm text-amber-800">
                  ⚠️ {hypothesisCount} finding(s) marked as hypothesis due to insufficient evidence.
                </p>
              </div>
            )}
          </div>
          <div className="lg:col-span-1">
            <ChatPanel />
          </div>
        </div>
      )}

      {activeTab === 'findings' && (
        <div className="space-y-3">
          <h3 className="font-semibold">Findings ({findings.length})</h3>
          {findings.length === 0 && <p className="text-sm text-slate-500">No findings yet.</p>}
          {findings.map((f: any) => (
            <div key={f.finding_id} className="card border-l-4 border-l-blue-500">
              <div className="flex justify-between items-start">
                <h4 className="font-medium">{f.statement}</h4>
                {f.is_hypothesis && (
                  <span className="text-xs bg-amber-100 text-amber-800 px-2 py-0.5 rounded">HYPOTHESIS</span>
                )}
              </div>
              <div className="mt-2 text-sm text-slate-600">
                <span className="mr-4">Topic: <b>{f.topic}</b></span>
                <span className="mr-4">Confidence: <b>{Math.round((f.confidence || 0) * 100)}%</b></span>
                <span>Evidence: <b>{f.support_count || f.evidence_ids?.length || 0} reviews</b></span>
              </div>
              {f.sample_quotes?.length > 0 && (
                <div className="mt-2 text-xs text-slate-500 italic">
                  “{f.sample_quotes[0]}”
                </div>
              )}
              {f.conflict_notes?.length > 0 && (
                <div className="mt-2 text-xs text-slate-500">
                  Conflict: {f.conflict_notes.join('; ')}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {activeTab === 'prd' && (
        <div className="space-y-6">
          {versionPlan.length === 0 && <p className="text-sm text-slate-500">No PRD generated yet.</p>}
          {versionPlan.map((vp: any) => (
            <div key={vp.version} className="card">
              <h3 className="font-semibold text-lg mb-4">
                {vp.version} — {vp.theme}
              </h3>
              <div className="space-y-4">
                {(vp.requirements || []).map((req: any) => (
                  <div key={req.req_id} className="border-l-4 border-l-green-500 pl-4">
                    <div className="flex justify-between items-start">
                      <h4 className="font-medium">{req.req_id}: {req.title}</h4>
                      <span className="text-xs bg-slate-100 px-2 py-0.5 rounded">{req.priority}</span>
                    </div>
                    <p className="text-sm text-slate-700 mt-1">{req.description}</p>
                    <div className="mt-2 text-xs text-slate-500">
                      Source: {req.finding_ids?.join(', ') || 'N/A'}
                    </div>
                    {(req.scope_in?.length > 0 || req.scope_out?.length > 0) && (
                      <div className="mt-2 grid grid-cols-2 gap-4 text-xs">
                        <div>
                          <span className="font-medium text-green-700">In Scope:</span>
                          <ul className="list-disc ml-4">
                            {req.scope_in?.map((s: string) => <li key={s}>{s}</li>)}
                          </ul>
                        </div>
                        <div>
                          <span className="font-medium text-red-700">Out of Scope:</span>
                          <ul className="list-disc ml-4">
                            {req.scope_out?.map((s: string) => <li key={s}>{s}</li>)}
                          </ul>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'testcases' && (
        <div className="space-y-3">
          <h3 className="font-semibold">Test Cases ({testCases.length})</h3>
          {testCases.length === 0 && <p className="text-sm text-slate-500">No test cases generated yet.</p>}
          {testCases.map((tc: any) => (
            <div key={tc.tc_id} className="card border-l-4 border-l-purple-500">
              <div className="flex justify-between items-start">
                <h4 className="font-medium">{tc.tc_id}: {tc.title}</h4>
                <div className="flex gap-2">
                  <span className="text-xs bg-slate-100 px-2 py-0.5 rounded">{tc.test_type}</span>
                  <span className="text-xs bg-slate-100 px-2 py-0.5 rounded">{tc.priority}</span>
                </div>
              </div>
              <div className="text-xs text-slate-500 mt-1">
                Requirement: <b>{tc.req_id}</b>
              </div>
              {tc.description && (
                <p className="text-sm text-slate-700 mt-2">{tc.description}</p>
              )}
              <div className="mt-2">
                <p className="text-xs font-medium text-slate-600">Steps:</p>
                <ol className="list-decimal list-inside text-sm text-slate-700">
                  {tc.steps?.map((step: string, idx: number) => (
                    <li key={idx}>{step}</li>
                  ))}
                </ol>
              </div>
              <div className="mt-2 text-sm text-slate-700">
                <span className="font-medium">Expected:</span> {tc.expected_result}
              </div>
              {tc.source_reviews?.length > 0 && (
                <div className="mt-2 text-xs text-slate-500">
                  Source reviews: {tc.source_reviews.join(', ')}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {activeTab === 'reviews' && (
        <div className="space-y-3 max-h-[600px] overflow-y-auto">
          <h3 className="font-semibold">Reviews ({result.cleaned_reviews?.length || 0})</h3>
          {(result.cleaned_reviews || []).map((r: any) => (
            <div key={r.review_id} className="card">
              <div className="flex justify-between items-start">
                <span className="text-xs font-mono text-slate-500">{r.review_id}</span>
                <span className="text-sm">{'⭐'.repeat(r.rating)}</span>
              </div>
              <p className="text-sm font-medium mt-1">{r.title}</p>
              <p className="text-sm text-slate-700 mt-1">{r.text}</p>
              {r.topics?.length > 0 && (
                <div className="flex gap-1 mt-2 flex-wrap">
                  {r.topics.map((tid: string) => (
                    <span key={tid} className="text-xs bg-slate-200 px-2 py-0.5 rounded">{tid}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
