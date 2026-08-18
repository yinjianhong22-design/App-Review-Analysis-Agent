import { useWorkflowStore } from '../stores/workflowStore'
import type { Review } from '../types'

export default function ReviewExplorer() {
  const { result, selectedReviewId, setSelectedReviewId } = useWorkflowStore()
  if (!result) return null

  const reviews = result.reviews || []

  return (
    <div className="space-y-3">
      <h3 className="font-semibold">Reviews ({reviews.length})</h3>
      <div className="max-h-[600px] overflow-y-auto space-y-2">
        {reviews.map((r: Review) => (
          <div
            key={r.review_id}
            onClick={() => setSelectedReviewId(r.review_id === selectedReviewId ? null : r.review_id)}
            className={`p-3 rounded-md border cursor-pointer transition ${
              r.review_id === selectedReviewId
                ? 'border-blue-500 bg-blue-50'
                : 'border-slate-200 bg-white hover:bg-slate-50'
            }`}
          >
            <div className="flex justify-between items-start">
              <div>
                <span className="text-xs font-mono text-slate-500">{r.review_id}</span>
                <p className="font-medium text-sm">{r.title}</p>
              </div>
              <span className="text-sm font-semibold">{'⭐'.repeat(r.rating)}</span>
            </div>
            <p className="text-sm text-slate-700 mt-1 line-clamp-3">{r.content}</p>
            {r.extra && (r.extra as { topic_ids?: string[] }).topic_ids && (
              <div className="flex gap-1 mt-2 flex-wrap">
                {(r.extra as { topic_ids: string[] }).topic_ids.map((tid) => (
                  <span key={tid} className="text-xs bg-slate-200 px-2 py-0.5 rounded">{tid}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
