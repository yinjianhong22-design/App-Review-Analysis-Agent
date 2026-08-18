from typing import List, Dict, Any

from app.services.ai_agent import LLMClient


class TestGenService:
    def __init__(self):
        self.llm = LLMClient()

    async def generate_test_cases(self, prd: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Stage 8: generate test cases from PRD.
        Chunked by requirement to avoid exceeding output token limits."""
        all_test_cases: List[Dict[str, Any]] = []
        review_ids = set()
        for vp in prd.get("version_plan", []):
            for req in vp.get("requirements", []):
                review_ids.update(req.get("source_reviews", []))

        for vp in prd.get("version_plan", []):
            for req in vp.get("requirements", []):
                # Cap source reviews to keep LLM output compact
                slim_req = dict(req)
                source_reviews = req.get("source_reviews", [])[:5]
                slim_req["source_reviews"] = source_reviews

                mini_prd = {
                    "app_id": prd.get("app_id", ""),
                    "analysis_goal": prd.get("analysis_goal", ""),
                    "version_plan": [{
                        "version": vp.get("version", ""),
                        "theme": vp.get("theme", ""),
                        "requirements": [slim_req],
                    }],
                }
                tcs = await self.llm.generate_test_cases(mini_prd)
                for tc in tcs:
                    tc["source_reviews"] = [rid for rid in tc.get("source_reviews", []) if rid in review_ids]
                    all_test_cases.append(tc)

        return all_test_cases
