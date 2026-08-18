export interface Review {
  review_id: string
  author: string
  rating: number
  version: string
  date?: string
  title: string
  content: string
  source: string
  app_id?: string
  extra?: Record<string, unknown>
}

export interface Stage {
  stage: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'retrying' | 'skipped'
  message: string
  result: Record<string, unknown>
  started_at?: string
  completed_at?: string
}

export interface WorkflowStatus {
  job_id: string
  current_stage: string | null
  stages: Stage[]
  progress_pct: number
  error?: string
}

export interface AnalysisResult {
  job_id: string
  input: {
    app_id?: string
    app_url?: string
    analysis_goal: string
  }
  reviews: Review[]
  topics: Array<Record<string, unknown>>
  findings: Array<Record<string, unknown>>
  version_plan: Array<Record<string, unknown>>
  prd: Record<string, unknown>
  test_cases: Array<Record<string, unknown>>
  trace_links: Array<Record<string, unknown>>
  validation_report: Record<string, unknown>
  error?: string
}
