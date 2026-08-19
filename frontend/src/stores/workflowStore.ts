import { create } from 'zustand'
import type { WorkflowStatus, AnalysisResult } from '../types'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

interface WorkflowState {
  jobId: string | null
  status: WorkflowStatus | null
  result: AnalysisResult | null
  isLoading: boolean
  error: string | null
  pollInterval: number | null
  activeTab: string
  chatOpen: boolean
  chatMessages: ChatMessage[]
  chatLoading: boolean
  setActiveTab: (tab: string) => void
  setChatOpen: (open: boolean) => void
  startAnalysis: (appUrl: string, goal: string, filePath?: string) => Promise<void>
  fetchStatus: (jobId: string) => Promise<void>
  fetchResult: (jobId: string) => Promise<void>
  sendChatMessage: (content: string) => Promise<void>
  exportReport: (format: string) => Promise<void>
  stopPolling: () => void
  reset: () => void
}

const API_BASE = ''

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  jobId: null,
  status: null,
  result: null,
  isLoading: false,
  error: null,
  pollInterval: null,
  activeTab: 'overview',
  chatOpen: false,
  chatMessages: [],
  chatLoading: false,

  setActiveTab: (tab) => set({ activeTab: tab }),
  setChatOpen: (open) => set({ chatOpen: open }),

  startAnalysis: async (appUrl, goal, filePath) => {
    set({ isLoading: true, error: null, result: null, status: null, chatMessages: [] })
    try {
      const payload: Record<string, unknown> = {
        analysis_goal: goal || 'Improve the app based on user feedback',
        use_cache: true,
        offline_mode: !!filePath,
      }
      if (filePath) {
        payload.uploaded_file = filePath
      } else {
        payload.app_url = appUrl
      }

      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      set({ jobId: data.job_id })

      const interval = window.setInterval(() => {
        get().fetchStatus(data.job_id)
      }, 1500)
      set({ pollInterval: interval })
    } catch (err) {
      set({ error: String(err), isLoading: false })
    }
  },

  fetchStatus: async (jobId) => {
    try {
      const res = await fetch(`${API_BASE}/api/analyze/${jobId}/status`)
      if (!res.ok) throw new Error(await res.text())
      const status = await res.json()
      set({ status })

      const lastStage = status.stages[status.stages.length - 1]
      if (status.current_stage === null || lastStage?.status === 'completed' || lastStage?.status === 'failed') {
        get().stopPolling()
        await get().fetchResult(jobId)
      }
    } catch (err) {
      set({ error: String(err) })
      get().stopPolling()
    }
  },

  fetchResult: async (jobId) => {
    try {
      const res = await fetch(`${API_BASE}/api/analyze/${jobId}/result`)
      if (!res.ok) throw new Error(await res.text())
      const result = await res.json()
      set({ result, isLoading: false })
    } catch (err) {
      set({ error: String(err), isLoading: false })
    }
  },

  sendChatMessage: async (content: string) => {
    const { jobId, chatMessages } = get()
    if (!jobId) return
    const newMessages = [...chatMessages, { role: 'user' as const, content }]
    set({ chatMessages: newMessages, chatLoading: true })
    try {
      const res = await fetch(`${API_BASE}/api/chat/${jobId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: newMessages }),
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      set({ chatMessages: [...newMessages, { role: 'assistant', content: data.answer }], chatLoading: false })
    } catch (err) {
      set({ chatMessages: [...newMessages, { role: 'assistant', content: `Error: ${err}` }], chatLoading: false })
    }
  },

  exportReport: async (format: string) => {
    const { jobId } = get()
    if (!jobId) return
    try {
      const res = await fetch(`${API_BASE}/api/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: jobId, format }),
      })
      if (!res.ok) throw new Error(await res.text())
      const blob = await res.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const filename = res.headers.get('content-disposition')?.split('filename=')[1] || `export_${format}.md`
      a.download = filename.replace(/"/g, '')
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      set({ error: String(err) })
    }
  },

  stopPolling: () => {
    const interval = get().pollInterval
    if (interval) {
      window.clearInterval(interval)
      set({ pollInterval: null })
    }
  },

  reset: () => {
    get().stopPolling()
    set({
      jobId: null,
      status: null,
      result: null,
      isLoading: false,
      error: null,
      activeTab: 'overview',
      chatOpen: false,
      chatMessages: [],
      chatLoading: false,
    })
  },
}))
