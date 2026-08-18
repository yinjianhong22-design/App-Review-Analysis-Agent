import { useMemo } from 'react'
import { useWorkflowStore } from '../stores/workflowStore'

interface Node {
  id: string
  label: string
  type: 'review' | 'finding' | 'requirement' | 'testcase'
  x: number
  y: number
}

interface Link {
  source: string
  target: string
}

export default function TraceabilityGraph() {
  const { result } = useWorkflowStore()
  if (!result) return null

  const { nodes, links } = useMemo(() => {
    const nodes: Node[] = []
    const links: Link[] = []
    const reviews = result.reviews.slice(0, 20) // limit for readability
    const findings = result.findings.slice(0, 10)
    const requirements: Array<Record<string, unknown>> = []
    const versionPlan = (result.prd?.version_plan || []) as Array<Record<string, any>>
    versionPlan.forEach((vp) => {
      requirements.push(...(vp.requirements || []))
    })
    const testCases = result.test_cases.slice(0, 10)

    reviews.forEach((r, i) => nodes.push({ id: r.review_id, label: r.review_id, type: 'review', x: 50, y: 40 + i * 25 }))
    findings.forEach((f, i) => nodes.push({ id: f.finding_id as string, label: f.finding_id as string, type: 'finding', x: 250, y: 40 + i * 40 }))
    requirements.forEach((r, i) => nodes.push({ id: r.req_id as string, label: r.req_id as string, type: 'requirement', x: 450, y: 40 + i * 40 }))
    testCases.forEach((t, i) => nodes.push({ id: t.tc_id as string, label: t.tc_id as string, type: 'testcase', x: 650, y: 40 + i * 40 }))

    result.trace_links.forEach((l: any) => {
      if (nodes.some((n) => n.id === l.source_id) && nodes.some((n) => n.id === l.target_id)) {
        links.push({ source: l.source_id, target: l.target_id })
      }
    })

    return { nodes, links }
  }, [result])

  const nodeColor = (type: string) => {
    switch (type) {
      case 'review': return '#3b82f6'
      case 'finding': return '#8b5cf6'
      case 'requirement': return '#10b981'
      case 'testcase': return '#f59e0b'
      default: return '#94a3b8'
    }
  }

  return (
    <div className="space-y-3">
      <h3 className="font-semibold">Traceability Graph (sample)</h3>
      <div className="overflow-auto border border-slate-200 rounded-md bg-white">
        <svg width={800} height={Math.max(300, nodes.length * 20)}>
          {links.map((l, i) => {
            const s = nodes.find((n) => n.id === l.source)
            const t = nodes.find((n) => n.id === l.target)
            if (!s || !t) return null
            return (
              <line
                key={i}
                x1={s.x}
                y1={s.y}
                x2={t.x}
                y2={t.y}
                stroke="#cbd5e1"
                strokeWidth={1}
              />
            )
          })}
          {nodes.map((n) => (
            <g key={n.id} transform={`translate(${n.x},${n.y})`}>
              <circle r={6} fill={nodeColor(n.type)} />
              <text x={10} y={4} fontSize={10} fill="#334155">{n.label}</text>
            </g>
          ))}
        </svg>
      </div>
      <div className="flex gap-4 text-xs">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500" /> Review</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-purple-500" /> Finding</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500" /> Requirement</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500" /> Test Case</span>
      </div>
    </div>
  )
}
