import json
import os
from typing import Type, List, Dict, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel

from app.config import get_settings

# Batch size for review classification. Keep output JSON well below provider
# completion token limits (DeepSeek/OpenAI json_object often caps at ~8k).
CLASSIFY_BATCH_SIZE = 50


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


async def _classify_single_batch(reviews: List[Dict[str, Any]], user_goal: str, max_tokens: int = 6000) -> Dict[str, Any]:
    """Classify a small batch of reviews. Output size is bounded by batch size."""
    system = _load_prompt("classify_v1.0.txt")
    user = json.dumps({"analysis_goal": user_goal, "reviews": reviews}, ensure_ascii=False)
    return await _call_json(system, user, max_tokens=max_tokens)


async def _merge_batch_topics(batch_results: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Merge topics discovered across batches into a global topic list.

    Returns:
        global_topics: list of consolidated topics
        id_map: mapping from original batch topic id -> global topic id
    """
    all_topics = []
    for result in batch_results:
        for topic in result.get("topics", []):
            all_topics.append(topic)

    if not all_topics:
        return [], {}

    merge_system = (
        "You are a product analyst. You are given multiple topic lists extracted from different batches of the same app reviews.\n"
        "Consolidate them by merging topics that are semantically the same or very similar.\n"
        "Rules:\n"
        "1. Keep the merged list concise and non-redundant.\n"
        "2. Each output topic must have: id, name, description, keywords, source_topic_ids.\n"
        "3. source_topic_ids must list ALL original topic ids that were merged into this topic.\n"
        "4. Output ONLY a single valid JSON object. No markdown, no explanations.\n"
    )
    merge_user = json.dumps({"topics": all_topics}, ensure_ascii=False)
    merged = await _call_json(merge_system, merge_user, max_tokens=8000)

    global_topics = []
    id_map: Dict[str, str] = {}
    used_source_ids = set()

    for i, topic in enumerate(merged.get("topics", []), start=1):
        global_id = topic.get("id") or f"T-{i:03d}"
        # ensure unique global ids
        if any(t["id"] == global_id for t in global_topics):
            global_id = f"T-{i:03d}-{len(global_topics)}"
        topic["id"] = global_id
        global_topics.append(topic)
        for source_id in topic.get("source_topic_ids", []):
            id_map[str(source_id)] = global_id
            used_source_ids.add(str(source_id))

    # Any source topic that was not included in a merge group keeps its own id
    for topic in all_topics:
        tid = str(topic.get("id", ""))
        if tid and tid not in used_source_ids:
            global_topics.append({
                "id": tid,
                "name": topic.get("name", ""),
                "description": topic.get("description", ""),
                "keywords": topic.get("keywords", []),
                "review_count": topic.get("review_count", 0),
                "source_topic_ids": [tid],
            })
            id_map[tid] = tid

    return global_topics, id_map


def _remap_topic_ids(classification: Dict[str, Any], id_map: Dict[str, str]) -> Dict[str, Any]:
    new_ids = []
    for tid in classification.get("topic_ids", []):
        mapped = id_map.get(str(tid))
        if mapped and mapped not in new_ids:
            new_ids.append(mapped)
    classification["topic_ids"] = new_ids
    return classification


async def classify_reviews(reviews: List[Dict[str, Any]], user_goal: str) -> Dict[str, Any]:
    """Classify reviews in batches and merge topics globally.

    This avoids hitting the provider completion-token limit when analysing
    the maximum 500 App Store reviews at once.
    """
    if len(reviews) <= CLASSIFY_BATCH_SIZE:
        return await _classify_single_batch(reviews, user_goal)

    batches = [reviews[i:i + CLASSIFY_BATCH_SIZE] for i in range(0, len(reviews), CLASSIFY_BATCH_SIZE)]
    batch_results: List[Dict[str, Any]] = []
    for idx, batch in enumerate(batches):
        result = await _classify_single_batch(batch, user_goal)
        batch_results.append(result)

    global_topics, id_map = await _merge_batch_topics(batch_results)

    all_classifications: List[Dict[str, Any]] = []
    for result in batch_results:
        for classification in result.get("classifications", []):
            all_classifications.append(_remap_topic_ids(classification, id_map))

    # Recalculate review_count per global topic from merged classifications
    topic_counts: Dict[str, int] = {}
    for classification in all_classifications:
        for tid in classification.get("topic_ids", []):
            topic_counts[tid] = topic_counts.get(tid, 0) + 1
    for topic in global_topics:
        topic["review_count"] = topic_counts.get(topic["id"], 0)

    return {"topics": global_topics, "classifications": all_classifications}


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
