from typing import Dict, Any, List

from app.graph.state import PipelineState, ReviewItem, Finding, Requirement, VersionPlan, ValidationIssue
from app.graph import chains
from app.services.data_collection import AppStoreRSSCollector, FileCollector
from app.services.cleaning import CleaningService


def _log(state: PipelineState, message: str) -> None:
    state.logs.append(message)


def _review_to_item(r: Any) -> ReviewItem:
    return ReviewItem(
        review_id=r.review_id,
        date=r.date,
        rating=r.rating,
        title=r.title,
        text=r.content,
        version=r.version,
    )


async def fetch_and_clean_node(state: PipelineState) -> Dict[str, Any]:
    _log(state, "Fetching and cleaning reviews...")
    try:
        collector = AppStoreRSSCollector()
        app_id = state.app_id or collector.extract_app_id(state.app_url or "")
        if not app_id and not state.app_url:
            raise ValueError("No app_id or app_url provided")

        if state.app_url and state.app_url.endswith((".json", ".csv")):
            # Treat as uploaded file path
            if state.app_url.endswith(".json"):
                reviews = FileCollector.load_json(state.app_url)
            else:
                reviews = FileCollector.load_csv(state.app_url)
        else:
            reviews = await collector.collect(app_id, use_cache=True)

        raw_items = [_review_to_item(r) for r in reviews]
        cleaner = CleaningService()
        cleaned = cleaner.clean(reviews)
        cleaned_items = [_review_to_item(r) for r in cleaned]

        return {
            "stage": "collect",
            "app_id": app_id,
            "raw_reviews": raw_items,
            "cleaned_reviews": cleaned_items,
        }
    except Exception as e:
        return {"error": f"fetch_and_clean failed: {e}"}


async def classify_node(state: PipelineState) -> Dict[str, Any]:
    _log(state, "Classifying reviews into topics...")
    try:
        reviews = [r.model_dump(mode="json") for r in state.cleaned_reviews]
        result = await chains.classify_reviews(reviews, state.user_goal)

        # Attach topics to reviews
        topic_map = {c["review_id"]: c.get("topic_ids", []) for c in result.get("classifications", [])}
        for r in state.cleaned_reviews:
            r.topics = topic_map.get(r.review_id, [])

        return {"stage": "classify", "topics": result.get("topics", [])}
    except Exception as e:
        return {"error": f"classify failed: {e}"}


async def evaluate_node(state: PipelineState) -> Dict[str, Any]:
    _log(state, "Evaluating evidence and generating findings...")
    try:
        reviews = [r.model_dump(mode="json") for r in state.cleaned_reviews]
        classifications = []
        for r in state.cleaned_reviews:
            if r.topics:
                classifications.append({
                    "review_id": r.review_id,
                    "topic_ids": r.topics,
                    "rating": r.rating,
                })

        result = await chains.evaluate_findings(state.topics or [], classifications, reviews)
        findings_data = result.get("findings", [])
        findings = [Finding(**f) for f in findings_data]

        # Mark hypotheses if insufficient evidence
        for f in findings:
            if f.support_count < 3:
                f.is_hypothesis = True

        return {"stage": "evaluate", "findings": findings}
    except Exception as e:
        return {"error": f"evaluate failed: {e}"}


async def plan_node(state: PipelineState) -> Dict[str, Any]:
    _log(state, "Planning versions...")
    try:
        findings = [f.model_dump(mode="json") for f in state.findings]
        result = await chains.plan_versions(state.user_goal, findings)
        versions = [VersionPlan(**v) for v in result.get("versions", [])]
        return {"stage": "plan", "version_plan": versions}
    except Exception as e:
        return {"error": f"plan failed: {e}"}


async def prd_node(state: PipelineState) -> Dict[str, Any]:
    _log(state, "Generating PRD...")
    try:
        findings = [f.model_dump(mode="json") for f in state.findings]
        version_plan = [v.model_dump(mode="json") for v in state.version_plan]
        result = await chains.generate_prd(state.user_goal, state.app_id or "unknown", findings, version_plan)
        return {"stage": "prd", "prd": result.get("prd", {})}
    except Exception as e:
        return {"error": f"prd failed: {e}"}


async def verify_node(state: PipelineState) -> Dict[str, Any]:
    _log(state, "Verifying traceability...")
    issues: List[ValidationIssue] = []
    review_ids = {r.review_id for r in state.cleaned_reviews}
    finding_ids = {f.finding_id for f in state.findings}

    # Verify requirements link to findings and reviews
    for vp in state.version_plan:
        for req in vp.requirements:
            if not req.finding_ids:
                issues.append(ValidationIssue(type="orphan_requirement", item_id=req.req_id, message="No finding linked"))
            else:
                for fid in req.finding_ids:
                    if fid not in finding_ids:
                        issues.append(ValidationIssue(type="missing_finding", item_id=req.req_id, message=f"Finding {fid} not found"))
            invalid_reviews = [rid for rid in req.source_reviews if rid not in review_ids]
            if invalid_reviews:
                issues.append(ValidationIssue(type="invalid_review", item_id=req.req_id, message=f"Reviews not found: {invalid_reviews}"))

    # Verify findings link to reviews
    for f in state.findings:
        invalid = [rid for rid in f.evidence_ids if rid not in review_ids]
        if invalid:
            issues.append(ValidationIssue(type="invalid_evidence", item_id=f.finding_id, message=f"Evidence not found: {invalid}"))

    if not issues:
        status = "PASSED"
    elif state.retry_count < 2:
        status = "NEEDS_RETRY"
        state.retry_count += 1
    else:
        status = "PARTIAL"
    return {
        "stage": "validate",
        "validation_issues": issues,
        "validation_status": status,
        "retry_count": state.retry_count,
    }


async def present_node(state: PipelineState) -> Dict[str, Any]:
    _log(state, "Generating final summary...")
    try:
        summary = await chains.generate_summary(
            state.prd,
            [f.model_dump(mode="json") for f in state.findings],
            state.user_goal,
        )
        return {
            "stage": "present",
            "summary": summary,
            "validation_status": "COMPLETED",
        }
    except Exception as e:
        return {"error": f"present failed: {e}"}
