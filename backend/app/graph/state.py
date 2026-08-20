from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ReviewItem(BaseModel):
    review_id: str
    date: Optional[str] = None
    rating: int = Field(default=3, ge=1, le=5)
    title: str = ""
    text: str
    version: Optional[str] = None
    cleaned_text: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    sentiment: Optional[str] = None


class Finding(BaseModel):
    finding_id: str
    topic: str
    statement: str
    evidence_ids: List[str] = Field(default_factory=list)
    sample_quotes: List[str] = Field(default_factory=list)
    support_count: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    conflict_notes: List[str] = Field(default_factory=list)
    is_hypothesis: bool = False


class Requirement(BaseModel):
    req_id: str
    finding_ids: List[str] = Field(default_factory=list)
    title: str
    description: str
    priority: str = "P1"
    target_version: str = "v1.0.0"
    scope_in: List[str] = Field(default_factory=list)
    scope_out: List[str] = Field(default_factory=list)
    source_reviews: List[str] = Field(default_factory=list)


class VersionPlan(BaseModel):
    version: str
    theme: str
    requirements: List[Requirement] = Field(default_factory=list)


class TestCase(BaseModel):
    tc_id: str
    req_id: str
    title: str
    description: str = ""
    steps: List[str] = Field(default_factory=list)
    expected_result: str = ""
    source_reviews: List[str] = Field(default_factory=list)
    test_type: str = "functional"  # functional / usability / regression / performance
    priority: str = "P1"


class ValidationIssue(BaseModel):
    type: str
    item_id: Optional[str] = None
    message: str


class PipelineState(BaseModel):
    job_id: Optional[str] = None
    app_url: Optional[str] = None
    app_id: Optional[str] = None
    user_goal: str = "Improve the app based on user feedback"
    stage: str = "pending"
    raw_reviews: List[ReviewItem] = Field(default_factory=list)
    cleaned_reviews: List[ReviewItem] = Field(default_factory=list)
    topics: List[Dict[str, Any]] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)
    version_plan: List[VersionPlan] = Field(default_factory=list)
    prd: Dict[str, Any] = Field(default_factory=dict)
    test_cases: List[TestCase] = Field(default_factory=list)
    summary: str = ""
    validation_status: str = "PENDING"
    validation_issues: List[ValidationIssue] = Field(default_factory=list)
    retry_count: int = 0
    logs: List[str] = Field(default_factory=list)
    error: Optional[str] = None
