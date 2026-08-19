import json
import os
from typing import Type, List, Dict, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel

from app.config import get_settings


def get_llm(temperature: Optional[float] = None) -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=temperature if temperature is not None else settings.llm_temperature,
        max_tokens=None,
    )


def _load_prompt(name: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "..", "prompts", name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


async def _call_json(system: str, user: str, max_tokens: int = 4000) -> Dict[str, Any]:
    llm = get_llm()
    system = (
        f"{system}\n\nCRITICAL: Output ONLY a single valid JSON object. "
        f"No markdown, no explanations, no thinking steps, no code fences, no preamble. "
        f"Use ASCII straight quotes only. Output compact JSON."
    )
    messages = [
        SystemMessage(content=system),
        HumanMessage(content=user),
        HumanMessage(content="Remember: output ONLY raw JSON and nothing else."),
    ]
    response = await llm.ainvoke(
        messages,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    text = response.content.strip() if response.content else ""
    if text.startswith("```"):
        import re
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    return json.loads(text)


async def classify_reviews(reviews: List[Dict[str, Any]], user_goal: str) -> Dict[str, Any]:
    system = _load_prompt("classify_v1.0.txt")
    user = json.dumps({"analysis_goal": user_goal, "reviews": reviews}, ensure_ascii=False)
    return await _call_json(system, user, max_tokens=8000)


async def evaluate_findings(topics: List[Dict[str, Any]], classifications: List[Dict[str, Any]], reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
    system = _load_prompt("evaluate_v1.0.txt")
    user = json.dumps({"topics": topics, "classifications": classifications, "reviews": reviews}, ensure_ascii=False)
    return await _call_json(system, user, max_tokens=16000)


async def plan_versions(user_goal: str, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    system = _load_prompt("plan_v1.0.txt")
    user = json.dumps({"analysis_goal": user_goal, "findings": findings}, ensure_ascii=False)
    return await _call_json(system, user, max_tokens=4000)


async def generate_prd(user_goal: str, app_id: str, findings: List[Dict[str, Any]], version_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
    system = _load_prompt("prd_v1.0.txt")
    user = json.dumps({"analysis_goal": user_goal, "app_id": app_id, "findings": findings, "version_plan": version_plan}, ensure_ascii=False)
    return await _call_json(system, user, max_tokens=12000)


async def generate_summary(prd: Dict[str, Any], findings: List[Dict[str, Any]], user_goal: str) -> str:
    system = (
        "You are a product analyst. Summarize the analysis results in 3-5 concise paragraphs. "
        "Focus on the top user pain points, the most important requirements, and recommended next steps. "
        "Write in the same language as the user's goal and reviews. Output plain text only, no JSON."
    )
    user = json.dumps({
        "user_goal": user_goal,
        "top_findings": findings[:10],
        "version_plan": prd.get("version_plan", []),
    }, ensure_ascii=False)
    llm = get_llm(temperature=0.2)
    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=user),
    ], max_tokens=2000)
    return str(response.content)


async def chat_with_context(messages: List[Dict[str, str]], context: Dict[str, Any]) -> str:
    system = (
        "You are an App Review Analysis Agent. Answer the user's question based ONLY on the provided analysis context. "
        "The context includes app reviews, findings, PRD requirements, and test cases. "
        "If the answer is not in the context, say so. Be concise. "
        "When referencing requirements or findings, include their IDs."
    )
    context_text = json.dumps(context, ensure_ascii=False, indent=2)[:12000]
    langchain_messages = [SystemMessage(content=f"{system}\n\nContext:\n{context_text}")]
    for m in messages:
        if m["role"] == "user":
            langchain_messages.append(HumanMessage(content=m["content"]))
        elif m["role"] == "assistant":
            langchain_messages.append(SystemMessage(content=m["content"]))
    llm = get_llm(temperature=0.3)
    response = await llm.ainvoke(langchain_messages, max_tokens=2000)
    return str(response.content)
