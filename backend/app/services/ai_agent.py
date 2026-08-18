import os
import json
import re
import logging
from typing import List, Dict, Any, Optional

from openai import AsyncOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None, base_url: Optional[str] = None):
        settings = get_settings()
        self.model = model or settings.openai_model
        self.api_key = api_key or settings.openai_api_key
        self.base_url = base_url or settings.openai_base_url
        self.temperature = settings.llm_temperature
        self.max_retries = settings.llm_max_retries
        self.json_mode = settings.llm_json_mode
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def _load_prompt(self, name: str) -> str:
        path = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", name)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def _extract_json(text: Optional[str]) -> Dict[str, Any]:
        """Extract JSON from model output, handling markdown fences and empty content."""
        if not text:
            raise ValueError("Model returned empty content")

        text = text.strip()
        # Remove markdown code fences
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()

        # If model wrapped output in single backticks, strip them
        if text.startswith("`") and text.endswith("`"):
            text = text[1:-1].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # Try to find the first JSON object/array in the text
            match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Model output is not valid JSON: {e}\nRaw output:\n{text[:500]}")

    async def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: Optional[Dict[str, Any]] = None,
        max_tokens: int = 4000,
    ) -> Dict[str, Any]:
        # Strongly instruct the model to output only JSON. This is critical for
        # reasoning models (e.g. DeepSeek-R1/V4) that tend to emit thinking text.
        json_instruction = (
            "\n\nCRITICAL: Output ONLY a single valid JSON object. "
            "Do not write explanations, do not write thinking steps, do not use markdown code fences, "
            "do not add preamble or postscript. Output compact JSON without unnecessary whitespace. "
            "Use ASCII straight quotes \" only — never use curly quotes or other typographic quote characters. "
            "Your entire response must be parseable by json.loads()."
        )
        if json_schema:
            json_instruction += (
                "\nThe JSON must strictly match this schema:\n"
                f"{json.dumps(json_schema, ensure_ascii=False, indent=2)}"
            )

        messages = [
            {"role": "system", "content": system_prompt + json_instruction},
            {"role": "user", "content": user_prompt},
            {"role": "user", "content": "Remember: output ONLY raw JSON and nothing else."},
        ]

        params = {
            "model": self.model,
            "messages": messages,
            "temperature": min(self.temperature, 0.05),
            "max_tokens": max_tokens,
        }

        if self.json_mode == "json_schema" and json_schema:
            params["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_output",
                    "strict": True,
                    "schema": json_schema,
                },
            }
        elif self.json_mode == "json_object":
            params["response_format"] = {"type": "json_object"}
        # disabled: do not pass response_format at all

        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.info(f"LLM request attempt {attempt + 1}/{self.max_retries} model={self.model}")
                resp = await self.client.chat.completions.create(**params)
                content = resp.choices[0].message.content
                # Some DeepSeek models return reasoning_content separately
                if not content and getattr(resp.choices[0].message, "reasoning_content", None):
                    content = resp.choices[0].message.reasoning_content
                logger.debug(f"LLM raw response:\n{content}")
                return self._extract_json(content)
            except Exception as e:
                last_error = e
                logger.warning(f"LLM attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    break
        raise RuntimeError(f"LLM call failed after {self.max_retries} attempts: {last_error}")

    async def classify_reviews(
        self,
        reviews: List[Dict[str, Any]],
        analysis_goal: str,
    ) -> Dict[str, Any]:
        system = self._load_prompt("classify_v1.0.txt")
        user = json.dumps({
            "analysis_goal": analysis_goal,
            "reviews": reviews,
        }, ensure_ascii=False, indent=2)
        schema = {
            "type": "object",
            "properties": {
                "topics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "keywords": {"type": "array", "items": {"type": "string"}},
                            "review_count": {"type": "integer"},
                        },
                        "required": ["id", "name", "description", "keywords", "review_count"],
                        "additionalProperties": False,
                    },
                },
                "classifications": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "review_id": {"type": "string"},
                            "topic_ids": {"type": "array", "items": {"type": "string"}},
                            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral", "mixed"]},
                            "severity": {"type": "integer", "minimum": 1, "maximum": 5},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "evidence_quote": {"type": "string"},
                        },
                        "required": ["review_id", "topic_ids", "sentiment", "severity", "confidence", "evidence_quote"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["topics", "classifications"],
            "additionalProperties": False,
        }
        return await self.chat_json(system, user, schema, max_tokens=8000)

    async def evaluate_findings(
        self,
        topics: List[Dict[str, Any]],
        classifications: List[Dict[str, Any]],
        reviews: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        system = self._load_prompt("evaluate_v1.0.txt")
        user = json.dumps({
            "topics": topics,
            "classifications": classifications,
            "reviews": reviews,
        }, ensure_ascii=False, indent=2)
        schema = {
            "type": "object",
            "properties": {
                "findings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "finding_id": {"type": "string"},
                            "topic_id": {"type": "string"},
                            "statement": {"type": "string"},
                            "supporting_reviews": {"type": "array", "items": {"type": "string"}},
                            "conflicting_reviews": {"type": "array", "items": {"type": "string"}},
                            "confidence": {"type": "number"},
                            "uncertainty": {"type": "string"},
                            "data_limitation": {"type": "string"},
                        },
                        "required": ["finding_id", "topic_id", "statement", "supporting_reviews", "confidence", "uncertainty"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["findings"],
            "additionalProperties": False,
        }
        result = await self.chat_json(system, user, schema, max_tokens=16000)
        return result.get("findings", [])

    async def plan_versions(
        self,
        analysis_goal: str,
        findings: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        system = self._load_prompt("plan_v1.0.txt")
        user = json.dumps({
            "analysis_goal": analysis_goal,
            "findings": findings,
        }, ensure_ascii=False, indent=2)
        schema = {
            "type": "object",
            "properties": {
                "versions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "version": {"type": "string"},
                            "theme": {"type": "string"},
                            "findings_addressed": {"type": "array", "items": {"type": "string"}},
                            "rationale": {"type": "string"},
                        },
                        "required": ["version", "theme", "findings_addressed", "rationale"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["versions"],
            "additionalProperties": False,
        }
        result = await self.chat_json(system, user, schema, max_tokens=4000)
        return result.get("versions", [])

    async def generate_prd(
        self,
        analysis_goal: str,
        app_id: str,
        findings: List[Dict[str, Any]],
        version_plan: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        system = self._load_prompt("prd_v1.0.txt")
        user = json.dumps({
            "analysis_goal": analysis_goal,
            "app_id": app_id,
            "findings": findings,
            "version_plan": version_plan,
        }, ensure_ascii=False, indent=2)
        schema = {
            "type": "object",
            "properties": {
                "prd": {
                    "type": "object",
                    "properties": {
                        "app_id": {"type": "string"},
                        "analysis_goal": {"type": "string"},
                        "version_plan": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "version": {"type": "string"},
                                    "theme": {"type": "string"},
                                    "requirements": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "req_id": {"type": "string"},
                                                "title": {"type": "string"},
                                                "description": {"type": "string"},
                                                "priority": {"type": "string"},
                                                "source_findings": {"type": "array", "items": {"type": "string"}},
                                                "source_reviews": {"type": "array", "items": {"type": "string"}},
                                                "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                                            },
                                            "required": ["req_id", "title", "description", "priority", "source_findings", "source_reviews", "acceptance_criteria"],
                                            "additionalProperties": False,
                                        },
                                    },
                                },
                                "required": ["version", "theme", "requirements"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["app_id", "analysis_goal", "version_plan"],
                    "additionalProperties": False,
                },
            },
            "required": ["prd"],
            "additionalProperties": False,
        }
        result = await self.chat_json(system, user, schema, max_tokens=12000)
        return result.get("prd", {})

    async def generate_test_cases(
        self,
        prd: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        system = self._load_prompt("testgen_v1.0.txt")
        user = json.dumps({"prd": prd}, ensure_ascii=False, indent=2)
        schema = {
            "type": "object",
            "properties": {
                "test_cases": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tc_id": {"type": "string"},
                            "req_id": {"type": "string"},
                            "title": {"type": "string"},
                            "steps": {"type": "array", "items": {"type": "string"}},
                            "expected_result": {"type": "string"},
                            "source_reviews": {"type": "array", "items": {"type": "string"}},
                            "test_type": {"type": "string", "enum": ["functional", "usability", "regression", "performance"]},
                            "priority": {"type": "string"},
                        },
                        "required": ["tc_id", "req_id", "title", "steps", "expected_result", "source_reviews", "test_type", "priority"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["test_cases"],
            "additionalProperties": False,
        }
        result = await self.chat_json(system, user, schema, max_tokens=16000)
        return result.get("test_cases", [])
