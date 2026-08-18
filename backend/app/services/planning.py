from typing import List, Dict, Any

from app.services.ai_agent import LLMClient


class PlanningService:
    def __init__(self):
        self.llm = LLMClient()

    async def plan_versions(
        self,
        analysis_goal: str,
        findings: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Stage 6: generate version roadmap."""
        if not findings:
            return []
        return await self.llm.plan_versions(analysis_goal, findings)

    async def generate_prd(
        self,
        analysis_goal: str,
        app_id: str,
        findings: List[Dict[str, Any]],
        version_plan: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Stage 7: generate PRD with trace links.
        Chunked by version and then by findings batch to avoid output token limits."""
        findings_map = {f["finding_id"]: f for f in findings}
        prd = {"app_id": app_id, "analysis_goal": analysis_goal, "version_plan": []}
        req_counter = 1

        for version in version_plan:
            version_findings_ids = version.get("findings_addressed", [])
            version_findings = [
                findings_map[fid] for fid in version_findings_ids if fid in findings_map
            ]
            if not version_findings:
                # Fallback: include all findings if none explicitly addressed
                version_findings = findings

            # Batch findings so each LLM call emits only a few requirements
            batch_size = 4
            all_version_requirements = []

            for i in range(0, len(version_findings), batch_size):
                batch = version_findings[i : i + batch_size]
                mini_version = {
                    "version": version.get("version", "v1.0.0"),
                    "theme": version.get("theme", ""),
                    "findings_addressed": [f["finding_id"] for f in batch],
                }
                version_prd = await self.llm.generate_prd(
                    analysis_goal, app_id, batch, [mini_version]
                )
                vp = version_prd.get("version_plan", [{}])[0]
                all_version_requirements.extend(vp.get("requirements", []))

            # Renumber req_ids sequentially within the version
            for req in all_version_requirements:
                req["req_id"] = f"REQ-{req_counter}"
                req_counter += 1

            prd["version_plan"].append({
                "version": version.get("version", "v1.0.0"),
                "theme": version.get("theme", ""),
                "requirements": all_version_requirements,
            })

        return prd
