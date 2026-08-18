import os
import json
import csv
from datetime import datetime
from typing import Dict, Any, List


class ExportService:
    def __init__(self, export_dir: str = "data/exports"):
        self.export_dir = export_dir
        os.makedirs(export_dir, exist_ok=True)

    async def export(self, state: Any, fmt: str) -> str:
        data = state.model_dump(mode="json")
        app_id = data.get("input", {}).get("app_id", "unknown")
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        if fmt == "json":
            path = os.path.join(self.export_dir, f"report_{app_id}_{ts}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return path

        if fmt == "markdown":
            path = os.path.join(self.export_dir, f"prd_{app_id}_{ts}.md")
            md = self._to_markdown(data)
            with open(path, "w", encoding="utf-8") as f:
                f.write(md)
            return path

        if fmt == "csv":
            path = os.path.join(self.export_dir, f"testcases_{app_id}_{ts}.csv")
            self._test_cases_to_csv(data.get("test_cases", []), path)
            return path

        raise ValueError(f"Unsupported export format: {fmt}")

    def _to_markdown(self, data: Dict[str, Any]) -> str:
        prd = data.get("prd", {})
        input_data = data.get("input", {})
        lines = [
            f"# Product Requirements Document",
            "",
            f"**App ID:** {prd.get('app_id', input_data.get('app_id', 'N/A'))}",
            f"**Analysis Goal:** {prd.get('analysis_goal', input_data.get('analysis_goal', 'N/A'))}",
            f"**Generated:** {datetime.utcnow().isoformat()}Z",
            "",
            "## Summary",
            "",
            f"- Total reviews analyzed: {len(data.get('reviews', []))}",
            f"- Topics discovered: {len(data.get('topics', []))}",
            f"- Findings: {len(data.get('findings', []))}",
            f"- Test cases: {len(data.get('test_cases', []))}",
            "",
            "## Version Plan",
            "",
        ]
        for vp in prd.get("version_plan", []):
            lines.append(f"### {vp.get('version', 'Unknown')} — {vp.get('theme', '')}")
            lines.append("")
            for req in vp.get("requirements", []):
                status = req.get("status", "")
                badge = f" [{status}]" if status else ""
                lines.append(f"#### {req.get('req_id', 'REQ-?')}: {req.get('title', '')}{badge}")
                lines.append(f"Priority: **{req.get('priority', 'N/A')}**")
                lines.append("")
                lines.append(req.get("description", ""))
                lines.append("")
                lines.append("**Acceptance Criteria:**")
                for ac in req.get("acceptance_criteria", []):
                    lines.append(f"- {ac}")
                lines.append("")
                lines.append(f"**Source Findings:** {', '.join(req.get('source_findings', []))}")
                lines.append(f"**Source Reviews:** {', '.join(req.get('source_reviews', []))}")
                lines.append("")
        return "\n".join(lines)

    def _test_cases_to_csv(self, test_cases: List[Dict[str, Any]], path: str):
        if not test_cases:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write("tc_id,req_id,title,steps,expected_result,source_reviews,test_type,priority\n")
            return
        keys = ["tc_id", "req_id", "title", "steps", "expected_result", "source_reviews", "test_type", "priority"]
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for tc in test_cases:
                row = dict(tc)
                row["steps"] = " | ".join(row.get("steps", []))
                row["source_reviews"] = ", ".join(row.get("source_reviews", []))
                writer.writerow(row)
