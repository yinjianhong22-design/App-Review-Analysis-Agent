from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from enum import Enum


# -----------------------------------------------------------------------------
# Review schemas
# -----------------------------------------------------------------------------
class ReviewSource(str, Enum):
    RSS = "rss_feed"
    CSV = "csv_upload"
    JSON = "json_upload"
    CACHE = "cache"


class Review(BaseModel):
    review_id: str
    author: str = ""
    rating: int = Field(ge=1, le=5)
    version: str = ""
    date: Optional[str] = None
    title: str = ""
    content: str
    source: ReviewSource = ReviewSource.RSS
    page: Optional[int] = None
    sort: Optional[str] = None
    app_id: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# Workflow schemas
# -----------------------------------------------------------------------------
class WorkflowStage(str, Enum):
    SCOPE = "scope"
    COLLECT = "collect"
    CLEAN = "clean"
    CLASSIFY = "classify"
    EVALUATE = "evaluate"
    PLAN = "plan"
    PRD = "prd"
    TESTGEN = "testgen"
    VALIDATE = "validate"
    PRESENT = "present"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    SKIPPED = "skipped"


class StageInfo(BaseModel):
    stage: WorkflowStage
    status: StageStatus = StageStatus.PENDING
    message: str = ""
    result: Dict[str, Any] = Field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AnalysisInput(BaseModel):
    app_url: Optional[str] = None
    app_id: Optional[str] = None
    analysis_goal: str = "Improve the app based on user feedback"
    uploaded_file: Optional[str] = None  # path to uploaded file
    use_cache: bool = True
    offline_mode: bool = False


class WorkflowState(BaseModel):
    job_id: str
    input: AnalysisInput
    stages: List[StageInfo] = Field(default_factory=list)
    current_stage_index: int = 0
    reviews: List[Review] = Field(default_factory=list)
    topics: List[Dict[str, Any]] = Field(default_factory=list)
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    version_plan: List[Dict[str, Any]] = Field(default_factory=list)
    prd: Dict[str, Any] = Field(default_factory=dict)
    test_cases: List[Dict[str, Any]] = Field(default_factory=list)
    trace_links: List[Dict[str, Any]] = Field(default_factory=list)
    validation_report: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None


# -----------------------------------------------------------------------------
# API response schemas
# -----------------------------------------------------------------------------
class StartAnalysisResponse(BaseModel):
    job_id: str
    status: str


class WorkflowStatusResponse(BaseModel):
    job_id: str
    current_stage: Optional[str]
    stages: List[StageInfo]
    progress_pct: float
    error: Optional[str] = None


class ExportRequest(BaseModel):
    job_id: str
    format: Literal["markdown", "json", "csv"]
