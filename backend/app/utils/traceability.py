from typing import List, Dict, Any


class TraceabilityBuilder:
    """Builds and validates trace links across the analysis pipeline."""

    MIN_EVIDENCE_REVIEWS = 3

    def __init__(self, min_evidence: int = 3):
        self.min_evidence = min_evidence
        self.links: List[Dict[str, Any]] = []

    def add_link(
        self,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        link_type: str = "supports",
        confidence: float = 1.0,
        evidence_quote: str = "",
    ):
        self.links.append({
            "source_type": source_type,
            "source_id": source_id,
            "target_type": target_type,
            "target_id": target_id,
            "link_type": link_type,
            "confidence": confidence,
            "evidence_quote": evidence_quote,
        })

    def validate(self, reviews: List[Any], findings, requirements, test_cases) -> Dict[str, Any]:
        review_ids = set()
        for r in reviews:
            rid = getattr(r, "review_id", None) or (r.get("review_id") if isinstance(r, dict) else None)
            if rid:
                review_ids.add(rid)
        issues = []

        # Validate findings
        for f in findings:
            supported = set(f.get("supporting_reviews", [])) & review_ids
            if len(supported) < self.min_evidence:
                issues.append({
                    "type": "insufficient_evidence",
                    "finding_id": f.get("finding_id"),
                    "message": f"Finding has only {len(supported)} supporting reviews (min {self.min_evidence})",
                })
                f["status"] = "ASSUMPTION"

        # Validate requirements link back to findings
        req_orphans = []
        for req in requirements:
            if not req.get("source_findings"):
                req_orphans.append(req.get("req_id"))
                req["status"] = "ASSUMPTION"

        # Validate test cases link back to requirements
        tc_orphans = []
        for tc in test_cases:
            if not tc.get("req_id"):
                tc_orphans.append(tc.get("tc_id"))
                tc["status"] = "ASSUMPTION"

        return {
            "valid": len(issues) == 0 and len(req_orphans) == 0 and len(tc_orphans) == 0,
            "issue_count": len(issues) + len(req_orphans) + len(tc_orphans),
            "insufficient_evidence": issues,
            "orphan_requirements": req_orphans,
            "orphan_test_cases": tc_orphans,
            "link_count": len(self.links),
        }

    def to_dict(self) -> List[Dict[str, Any]]:
        return self.links
