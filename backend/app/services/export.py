import os
import json
from datetime import datetime
from typing import Dict, Any


class ExportService:
    def __init__(self, export_dir: str = "data/exports"):
        self.export_dir = export_dir
        os.makedirs(export_dir, exist_ok=True)

    async def export(self, state: Any, fmt: str) -> str:
        data = state.model_dump(mode="json")
        app_id = data.get("app_id", "unknown")
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

        if fmt == "prd_doc":
            path = os.path.join(self.export_dir, f"PRD_{app_id}_{ts}.md")
            md = self._to_prd_markdown(data)
            with open(path, "w", encoding="utf-8") as f:
                f.write(md)
            return path

        if fmt == "test_cases_doc":
            path = os.path.join(self.export_dir, f"TestCases_{app_id}_{ts}.md")
            md = self._to_test_cases_markdown(data)
            with open(path, "w", encoding="utf-8") as f:
                f.write(md)
            return path

        raise ValueError(f"Unsupported export format: {fmt}")

    def _to_markdown(self, data: Dict[str, Any]) -> str:
        prd = data.get("prd", {})
        app_id = data.get("app_id", "N/A")
        user_goal = data.get("user_goal", "N/A")
        lines = [
            f"# Product Requirements Document",
            "",
            f"**App ID:** {app_id}",
            f"**Analysis Goal:** {user_goal}",
            f"**Generated:** {datetime.utcnow().isoformat()}Z",
            "",
            "## Summary",
            "",
            data.get("summary", ""),
            "",
            f"- Total reviews analyzed: {len(data.get('cleaned_reviews', []))}",
            f"- Findings: {len(data.get('findings', []))}",
            "",
            "## Version Plan",
            "",
        ]
        for vp in prd.get("version_plan", []):
            lines.append(f"### {vp.get('version', 'Unknown')} — {vp.get('theme', '')}")
            lines.append("")
            for req in vp.get("requirements", []):
                lines.append(f"#### {req.get('req_id', 'REQ-?')}: {req.get('title', '')}")
                lines.append(f"Priority: **{req.get('priority', 'N/A')}**")
                lines.append("")
                lines.append(req.get("description", ""))
                lines.append("")
                lines.append("**Scope In:**")
                for s in req.get("scope_in", []):
                    lines.append(f"- {s}")
                lines.append("")
                lines.append("**Scope Out:**")
                for s in req.get("scope_out", []):
                    lines.append(f"- {s}")
                lines.append("")
                lines.append(f"**Source Findings:** {', '.join(req.get('finding_ids', []))}")
                lines.append(f"**Source Reviews:** {', '.join(req.get('source_reviews', []))}")
                lines.append("")
        return "\n".join(lines)

    def _to_prd_markdown(self, data: Dict[str, Any]) -> str:
        prd = data.get("prd", {})
        app_id = data.get("app_id", "N/A")
        user_goal = data.get("user_goal", "N/A")
        lines = [
            f"# Product Requirements Document (PRD)",
            "",
            f"**App ID:** {app_id}",
            f"**Analysis Goal:** {user_goal}",
            f"**Generated:** {datetime.utcnow().isoformat()}Z",
            "",
            "## Executive Summary",
            "",
            data.get("summary", ""),
            "",
            f"- Total reviews analyzed: {len(data.get('cleaned_reviews', []))}",
            f"- Findings: {len(data.get('findings', []))}",
            f"- Requirements: {sum(len(vp.get('requirements', [])) for vp in prd.get('version_plan', []))}",
            "",
        ]

        for vp in prd.get("version_plan", []):
            lines.append(f"## {vp.get('version', 'Unknown')} — {vp.get('theme', '')}")
            lines.append("")
            for req in vp.get("requirements", []):
                lines.append(f"### {req.get('req_id', 'REQ-?')}: {req.get('title', '')}")
                lines.append(f"**Priority:** {req.get('priority', 'N/A')} | **Target Version:** {req.get('target_version', 'N/A')}")
                lines.append("")
                lines.append(req.get("description", ""))
                lines.append("")
                lines.append("**Scope In:**")
                for s in req.get("scope_in", []):
                    lines.append(f"- {s}")
                if not req.get("scope_in"):
                    lines.append("- _Not specified_")
                lines.append("")
                lines.append("**Scope Out:**")
                for s in req.get("scope_out", []):
                    lines.append(f"- {s}")
                if not req.get("scope_out"):
                    lines.append("- _Not specified_")
                lines.append("")
                lines.append(f"**Source Findings:** {', '.join(req.get('finding_ids', []))}")
                lines.append(f"**Source Reviews:** {', '.join(req.get('source_reviews', []))}")
                lines.append("")
        return "\n".join(lines)

    def _to_test_cases_markdown(self, data: Dict[str, Any]) -> str:
        app_id = data.get("app_id", "N/A")
        user_goal = data.get("user_goal", "N/A")
        test_cases = data.get("test_cases", [])
        lines = [
            f"# Test Cases",
            "",
            f"**App ID:** {app_id}",
            f"**Analysis Goal:** {user_goal}",
            f"**Generated:** {datetime.utcnow().isoformat()}Z",
            f"**Total Test Cases:** {len(test_cases)}",
            "",
        ]

        for tc in test_cases:
            lines.append(f"## {tc.get('tc_id', 'TC-?')}: {tc.get('title', '')}")
            lines.append(f"**Requirement:** {tc.get('req_id', 'REQ-?')} | **Type:** {tc.get('test_type', 'functional')} | **Priority:** {tc.get('priority', 'P1')}")
            lines.append("")
            if tc.get("description"):
                lines.append(tc.get("description", ""))
                lines.append("")
            lines.append("**Steps:**")
            for i, step in enumerate(tc.get("steps", []), start=1):
                lines.append(f"{i}. {step}")
            lines.append("")
            lines.append(f"**Expected Result:** {tc.get('expected_result', '')}")
            lines.append("")
            lines.append(f"**Source Reviews:** {', '.join(tc.get('source_reviews', []))}")
            lines.append("")
        return "\n".join(lines)
