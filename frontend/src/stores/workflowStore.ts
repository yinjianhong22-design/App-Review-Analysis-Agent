import { create } from 'zustand'
import type { WorkflowStatus, AnalysisResult } from '../types'

interface WorkflowState {
  jobId: string | null
  status: WorkflowStatus | null
  result: AnalysisResult | null
  isLoading: boolean
  error: string | null
  pollInterval: number | null
  activeTab: string
  selectedReviewId: string | null
  setActiveTab: (tab: string) => void
  setSelectedReviewId: (id: string | null) => void
  startAnalysis: (appUrl: string, goal: string, filePath?: string) => Promise<void>
  fetchStatus: (jobId: string) => Promise<void>
  fetchResult: (jobId: string) => Promise<void>
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
  selectedReviewId: null,

  setActiveTab: (tab) => set({ activeTab: tab }),
  setSelectedReviewId: (id) => set({ selectedReviewId: id }),

  startAnalysis: async (appUrl, goal, filePath) => {
    set({ isLoading: true, error: null, result: null, status: null })
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
      selectedReviewId: null,
    })
  },
}))
