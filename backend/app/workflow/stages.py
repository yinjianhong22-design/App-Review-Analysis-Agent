from typing import List, Dict, Any

from app.models.schemas import WorkflowStage, StageInfo, StageStatus, WorkflowState, Review
from app.services.data_collection import AppStoreRSSCollector, FileCollector
from app.services.cleaning import CleaningService
from app.services.analysis import AnalysisService
from app.services.planning import PlanningService
from app.services.testgen import TestGenService
from app.services.validation import ValidationService
from app.utils.traceability import TraceabilityBuilder


class StageExecutor:
    def __init__(self, state: WorkflowState):
        self.state = state
        self.trace_builder = TraceabilityBuilder()

    async def scope(self) -> Dict[str, Any]:
        """Stage 1: parse input and define scope."""
        inp = self.state.input
        collector = AppStoreRSSCollector()
        app_id = None
        if inp.app_id:
            app_id = inp.app_id
        elif inp.app_url:
            app_id = collector.extract_app_id(inp.app_url)

        if not app_id and not inp.uploaded_file and not inp.offline_mode:
            raise ValueError("Could not extract app_id from URL and no file provided")

        self.state.input.app_id = app_id
        return {
            "app_id": app_id,
            "analysis_goal": inp.analysis_goal,
            "mode": "offline" if inp.offline_mode else ("upload" if inp.uploaded_file else "rss"),
        }

    async def collect(self) -> Dict[str, Any]:
        """Stage 2: collect reviews from RSS or file."""
        inp = self.state.input
        if inp.offline_mode or inp.uploaded_file:
            path = inp.uploaded_file
            if not path:
                raise ValueError("Offline/upload mode requires a file path")
            if path.endswith(".json"):
                reviews = FileCollector.load_json(path)
            elif path.endswith(".csv"):
                reviews = FileCollector.load_csv(path)
            else:
                raise ValueError("Unsupported file format")
        else:
            collector = AppStoreRSSCollector()
            reviews = await collector.collect(inp.app_id, use_cache=inp.use_cache)

        self.state.reviews = reviews
        return {"review_count": len(reviews), "source": "upload" if inp.uploaded_file else "rss"}

    async def clean(self) -> Dict[str, Any]:
        """Stage 3: clean and deduplicate reviews."""
        original_count = len(self.state.reviews)
        service = CleaningService()
        cleaned = service.clean(self.state.reviews)
        self.state.reviews = cleaned
        return {
            "review_count_after_clean": len(cleaned),
            "removed_count": original_count - len(cleaned),
        }

    async def classify(self) -> Dict[str, Any]:
        """Stage 4: LLM-driven dynamic topic discovery."""
        service = AnalysisService()
        review_dicts = [r.model_dump(mode="json") for r in self.state.reviews]
        result = await service.classify(review_dicts, self.state.input.analysis_goal)
        self.state.topics = result.get("topics", [])
        # Attach classifications to reviews for downstream use
        classifications = result.get("classifications", [])
        class_map = {c["review_id"]: c for c in classifications}
        for r in self.state.reviews:
            r.extra = class_map.get(r.review_id, {})
        return {"topic_count": len(self.state.topics)}

    async def evaluate(self) -> Dict[str, Any]:
        """Stage 5: evidence evaluation and conflict detection."""
        service = AnalysisService()
        review_dicts = [r.model_dump(mode="json") for r in self.state.reviews]
        classifications = [r.extra for r in self.state.reviews]
        findings = await service.evaluate(self.state.topics, classifications, review_dicts)
        self.state.findings = findings

        # Build trace links: review -> finding
        for f in findings:
            for rid in f.get("supporting_reviews", []):
                self.trace_builder.add_link(
                    source_type="review", source_id=rid,
                    target_type="finding", target_id=f["finding_id"],
                    confidence=f.get("confidence", 0.5),
                )
        return {"finding_count": len(findings)}

    async def plan(self) -> Dict[str, Any]:
        """Stage 6: version planning."""
        service = PlanningService()
        plan = await service.plan_versions(self.state.input.analysis_goal, self.state.findings)
        self.state.version_plan = plan
        return {"version_count": len(plan)}

    async def prd(self) -> Dict[str, Any]:
        """Stage 7: PRD generation."""
        service = PlanningService()
        prd = await service.generate_prd(
            self.state.input.analysis_goal,
            self.state.input.app_id or "unknown",
            self.state.findings,
            self.state.version_plan,
        )
        self.state.prd = prd

        # Build trace links: finding -> requirement
        for vp in prd.get("version_plan", []):
            for req in vp.get("requirements", []):
                for fid in req.get("source_findings", []):
                    self.trace_builder.add_link(
                        source_type="finding", source_id=fid,
                        target_type="requirement", target_id=req["req_id"],
                    )
        return {"requirement_count": sum(len(vp.get("requirements", [])) for vp in prd.get("version_plan", []))}

    async def testgen(self) -> Dict[str, Any]:
        """Stage 8: test case generation."""
        service = TestGenService()
        tcs = await service.generate_test_cases(self.state.prd)
        self.state.test_cases = tcs

        # Build trace links: requirement -> test case
        for tc in tcs:
            self.trace_builder.add_link(
                source_type="requirement", source_id=tc["req_id"],
                target_type="testcase", target_id=tc["tc_id"],
            )
        return {"test_case_count": len(tcs)}

    async def validate(self) -> Dict[str, Any]:
        """Stage 9: traceability validation."""
        service = ValidationService()
        self.state.trace_links = self.trace_builder.to_dict()
        report = service.validate(
            self.state.reviews,
            self.state.findings,
            self.state.prd,
            self.state.test_cases,
            self.state.trace_links,
        )
        self.state.validation_report = report
        return report

    async def present(self) -> Dict[str, Any]:
        """Stage 10: final presentation formatting."""
        return {
            "review_count": len(self.state.reviews),
            "topic_count": len(self.state.topics),
            "finding_count": len(self.state.findings),
            "requirement_count": sum(
                len(vp.get("requirements", [])) for vp in self.state.prd.get("version_plan", [])
            ),
            "test_case_count": len(self.state.test_cases),
            "valid": self.state.validation_report.get("valid", False),
            "issue_count": self.state.validation_report.get("issue_count", 0),
        }
