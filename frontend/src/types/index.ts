export interface Review {
  review_id: string
  date?: string
  rating: number
  title: string
  text: string
  version?: string
  topics?: string[]
}

export interface Finding {
  finding_id: string
  topic: string
  statement: string
  evidence_ids: string[]
  sample_quotes: string[]
  support_count: number
  confidence: number
  conflict_notes: string[]
  is_hypothesis: boolean
}

export interface Requirement {
  req_id: string
  finding_ids: string[]
  title: string
  description: string
  priority: string
  target_version: string
  scope_in: string[]
  scope_out: string[]
  source_reviews: string[]
}

export interface VersionPlan {
  version: string
  theme: string
  requirements: Requirement[]
}

export interface Stage {
  stage: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  message: string
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
  app_id?: string
  app_url?: string
  user_goal: string
  stage: string
  cleaned_reviews: Review[]
  findings: Finding[]
  version_plan: VersionPlan[]
  prd: {
    app_id: string
    analysis_goal: string
    version_plan: VersionPlan[]
  }
  summary: string
  validation_status: string
  validation_issues: any[]
  retry_count: number
  logs: string[]
  error?: string
}
