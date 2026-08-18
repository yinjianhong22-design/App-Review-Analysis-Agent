import { useState, useRef } from 'react'
import { useWorkflowStore } from '../stores/workflowStore'

export default function InputPanel() {
  const [appUrl, setAppUrl] = useState('')
  const [goal, setGoal] = useState('')
  const [filePath, setFilePath] = useState<string | undefined>()
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const { startAnalysis, isLoading } = useWorkflowStore()

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await fetch('/api/upload', { method: 'POST', body: form })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setFilePath(data.path)
    } catch (err) {
      alert(String(err))
    } finally {
      setUploading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    startAnalysis(appUrl, goal, filePath)
  }

  return (
    <div className="card">
      <h2 className="text-lg font-semibold mb-4">Start Analysis</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">U.S. App Store URL or App ID</label>
          <input
            type="text"
            value={appUrl}
            onChange={(e) => setAppUrl(e.target.value)}
            placeholder="https://apps.apple.com/us/app/example/id123456789"
            className="w-full border border-slate-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={!!filePath}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Analysis Goal</label>
          <textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="e.g. Improve subscription conversion and reduce churn"
            rows={3}
            className="w-full border border-slate-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Or upload reviews (CSV/JSON)</label>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.json"
            onChange={handleFile}
            disabled={uploading || !!appUrl}
            className="block w-full text-sm text-slate-600 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
          />
          {filePath && <p className="text-xs text-green-600 mt-1">Uploaded: {filePath}</p>}
        </div>

        <button
          type="submit"
          disabled={isLoading || uploading || (!appUrl && !filePath)}
          className="btn-primary w-full"
        >
          {isLoading ? 'Analyzing...' : 'Start Analysis'}
        </button>
      </form>
    </div>
  )
}
