import { useWorkflowStore } from '../stores/workflowStore'
import ReviewExplorer from './ReviewExplorer'
import FindingCard from './FindingCard'
import TraceabilityGraph from './TraceabilityGraph'
import ExportPanel from './ExportPanel'
import ReactMarkdown from 'react-markdown'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'reviews', label: 'Reviews' },
  { id: 'findings', label: 'Findings' },
  { id: 'prd', label: 'PRD' },
  { id: 'tests', label: 'Test Cases' },
  { id: 'trace', label: 'Traceability' },
]

export default function ResultsDashboard() {
  const { result, activeTab, setActiveTab, status } = useWorkflowStore()

  if (!result && !status) return null
  if (!result) {
    return (
      <div className="card text-slate-500 text-sm">
        Analysis in progress... Results will appear here.
      </div>
    )
  }

  const prdMarkdown = result.prd ? `# Product Requirements Document

**App ID:** ${(result.prd.app_id as string) || result.input?.app_id || 'N/A'}
**Goal:** ${(result.prd.analysis_goal as string) || result.input?.analysis_goal || 'N/A'}

${(result.prd.version_plan as Array<Record<string, unknown>> || []).map((vp) => `## ${vp.version} — ${vp.theme}

${(vp.requirements as Array<Record<string, unknown>> || []).map((req) => `### ${req.req_id}: ${req.title}
Priority: **${req.priority}**

${req.description}

**Acceptance Criteria:**
${(req.acceptance_criteria as string[] || []).map((ac) => `- ${ac}`).join('\n')}

Sources: ${(req.source_findings as string[] || []).join(', ')} | ${(req.source_reviews as string[] || []).join(', ')}
`).join('\n')}
`).join('\n')}` : 'No PRD generated.'

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-2">
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

      {activeTab === 'overview' && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="card text-center">
            <div className="text-2xl font-bold text-blue-600">{result.reviews?.length || 0}</div>
            <div className="text-xs text-slate-500">Reviews</div>
          </div>
          <div className="card text-center">
            <div className="text-2xl font-bold text-purple-600">{result.topics?.length || 0}</div>
            <div className="text-xs text-slate-500">Topics</div>
          </div>
          <div className="card text-center">
            <div className="text-2xl font-bold text-green-600">{result.findings?.length || 0}</div>
            <div className="text-xs text-slate-500">Findings</div>
          </div>
          <div className="card text-center">
            <div className="text-2xl font-bold text-amber-600">{result.test_cases?.length || 0}</div>
            <div className="text-xs text-slate-500">Test Cases</div>
          </div>
          <div className="card col-span-full">
            <h4 className="font-semibold mb-2">Validation</h4>
            <p className="text-sm text-slate-700">
              {result.validation_report?.valid ? '✅ Traceability valid' : '⚠️ Traceability issues detected'}
              {result.validation_report?.issue_count ? ` — ${result.validation_report.issue_count} issue(s)` : ''}
            </p>
          </div>
          <div className="col-span-full">
            <ExportPanel />
          </div>
        </div>
      )}

      {activeTab === 'reviews' && <ReviewExplorer />}
      {activeTab === 'findings' && <FindingCard />}
      {activeTab === 'prd' && (
        <div className="card prose prose-sm max-w-none">
          <ReactMarkdown>{prdMarkdown}</ReactMarkdown>
        </div>
      )}
      {activeTab === 'tests' && (
        <div className="overflow-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100">
              <tr>
                <th className="px-3 py-2 text-left">TC ID</th>
                <th className="px-3 py-2 text-left">Requirement</th>
                <th className="px-3 py-2 text-left">Title</th>
                <th className="px-3 py-2 text-left">Type</th>
                <th className="px-3 py-2 text-left">Priority</th>
              </tr>
            </thead>
            <tbody>
              {(result.test_cases || []).map((tc: any) => (
                <tr key={tc.tc_id} className="border-b border-slate-100">
                  <td className="px-3 py-2 font-mono text-xs">{tc.tc_id}</td>
                  <td className="px-3 py-2 font-mono text-xs">{tc.req_id}</td>
                  <td className="px-3 py-2">{tc.title}</td>
                  <td className="px-3 py-2">{tc.test_type}</td>
                  <td className="px-3 py-2">{tc.priority}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {activeTab === 'trace' && <TraceabilityGraph />}
    </div>
  )
}
