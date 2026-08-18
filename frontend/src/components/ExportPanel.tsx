import { useState } from 'react'
import { useWorkflowStore } from '../stores/workflowStore'

export default function ExportPanel() {
  const { result } = useWorkflowStore()
  const [downloading, setDownloading] = useState(false)

  if (!result) return null

  const handleExport = async (format: 'markdown' | 'json' | 'csv') => {
    setDownloading(true)
    try {
      const res = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: result.job_id, format }),
      })
      if (!res.ok) throw new Error(await res.text())
      const blob = await res.blob()
      const disposition = res.headers.get('content-disposition')
      const filename = disposition?.match(/filename="?([^"]+)"?/)?.[1] || `export.${format}`
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      alert(String(err))
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="card">
      <h3 className="font-semibold mb-3">Export</h3>
      <div className="flex gap-2">
        <button onClick={() => handleExport('markdown')} disabled={downloading} className="btn-secondary text-sm">
          PRD (.md)
        </button>
        <button onClick={() => handleExport('csv')} disabled={downloading} className="btn-secondary text-sm">
          Test Cases (.csv)
        </button>
        <button onClick={() => handleExport('json')} disabled={downloading} className="btn-secondary text-sm">
          Full Report (.json)
        </button>
      </div>
    </div>
  )
}
