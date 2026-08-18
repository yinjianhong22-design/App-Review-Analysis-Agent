from typing import List, Dict, Any

from app.utils.traceability import TraceabilityBuilder


class ValidationService:
    def __init__(self, min_evidence: int = 3):
        self.min_evidence = min_evidence

    def validate(
        self,
        reviews: List[Any],
        findings: List[Dict[str, Any]],
        prd: Dict[str, Any],
        test_cases: List[Dict[str, Any]],
        trace_links: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Stage 9: validate traceability and mark assumptions."""
        review_ids = set()
        for r in reviews:
            rid = getattr(r, "review_id", None)
            if not rid and isinstance(r, dict):
                rid = r.get("review_id")
            if rid:
                review_ids.add(rid)
        builder = TraceabilityBuilder(min_evidence=self.min_evidence)
        builder.links = trace_links

        # Collect requirements
        requirements = []
        for vp in prd.get("version_plan", []):
            requirements.extend(vp.get("requirements", []))

        report = builder.validate(reviews, findings, requirements, test_cases)

        # Additional checks
        for f in findings:
            supported = set(f.get("supporting_reviews", [])) & review_ids
            f["sample_count"] = len(supported)
            if len(supported) < self.min_evidence:
                f["status"] = "ASSUMPTION"
            elif f.get("status") == "ASSUMPTION":
                f["status"] = "VALIDATED"

        return report
