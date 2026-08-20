import json
import os
from typing import Type, List, Dict, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel

from app.config import get_settings

# Batch size for review classification. Keep output JSON well below provider
# completion token limits (DeepSeek/OpenAI json_object often caps at ~8k).
CLASSIFY_BATCH_SIZE = 10

# Truncate long review text before sending it to the classifier. This keeps both
# the prompt and the model's per-review output within token limits.
CLASSIFY_MAX_REVIEW_CHARS = 500


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


def _truncate_review_for_classify(review: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of the review with text truncated for classification."""
    truncated = dict(review)
    text = truncated.get("text", "")
    if len(text) > CLASSIFY_MAX_REVIEW_CHARS:
        truncated["text"] = text[:CLASSIFY_MAX_REVIEW_CHARS].rsplit(" ", 1)[0] + "..."
    # Also truncate title if needed
    title = truncated.get("title", "")
    if len(title) > 200:
        truncated["title"] = title[:200].rsplit(" ", 1)[0] + "..."
    return truncated


async def _classify_single_batch(reviews: List[Dict[str, Any]], user_goal: str, max_tokens: int = 3500) -> Dict[str, Any]:
    """Classify a small batch of reviews. Output size is bounded by batch size."""
    system = _load_prompt("classify_v1.0.txt")
    reviews = [_truncate_review_for_classify(r) for r in reviews]
    user = json.dumps({"analysis_goal": user_goal, "reviews": reviews}, ensure_ascii=False)
    return await _call_json(system, user, max_tokens=max_tokens)


def _is_length_or_truncation_error(error: Exception) -> bool:
    """Detect errors caused by the response hitting token/context limits."""
    error_text = str(error).lower()
    length_keywords = ["length", "token", "maximum context", "too long", "truncate", "context length"]
    if any(keyword in error_text for keyword in length_keywords):
        return True
    # Truncated JSON outputs also commonly fail here
    if isinstance(error, json.JSONDecodeError):
        return True
    return False


async def _classify_batch_with_retry(
    reviews: List[Dict[str, Any]],
    user_goal: str,
    min_batch_size: int = 3,
) -> Dict[str, Any]:
    """Classify a batch, automatically shrinking it on token-length errors."""
    try:
        return await _classify_single_batch(reviews, user_goal)
    except Exception as e:
        if not _is_length_or_truncation_error(e) or len(reviews) <= min_batch_size:
            raise

    # Split in half and retry recursively
    mid = len(reviews) // 2
    left = await _classify_batch_with_retry(reviews[:mid], user_goal, min_batch_size)
    right = await _classify_batch_with_retry(reviews[mid:], user_goal, min_batch_size)

    merged_topics = left.get("topics", []) + right.get("topics", [])
    merged_classifications = left.get("classifications", []) + right.get("classifications", [])

    # Re-index topic ids from the two halves to avoid collisions
    left_ids = {t["id"] for t in left.get("topics", [])}
    right_ids = {t["id"] for t in right.get("topics", [])}
    if left_ids & right_ids:
        right_topic_map: Dict[str, str] = {}
        for i, t in enumerate(right.get("topics", []), start=1):
            new_id = f"R{i:03d}-{t['id']}"
            right_topic_map[t["id"]] = new_id
            t["id"] = new_id
        for c in right.get("classifications", []):
            c["topic_ids"] = [right_topic_map.get(tid, tid) for tid in c.get("topic_ids", [])]

    return {"topics": merged_topics, "classifications": merged_classifications}


async def _merge_topics_chunk(topics: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Call the LLM to merge a chunk of topics."""
    merge_system = (
        "You are a product analyst. You are given a list of topics extracted from app reviews.\n"
        "Consolidate them by merging topics that are semantically the same or very similar.\n"
        "Rules:\n"
        "1. Keep the merged list concise and non-redundant.\n"
        "2. Each output topic must have: id, name, description, keywords, source_topic_ids.\n"
        "3. source_topic_ids must list ALL original topic ids that were merged into this topic.\n"
        "4. Keep names under 6 words and descriptions under 20 words.\n"
        "5. Output ONLY a single valid JSON object. No markdown, no explanations.\n"
    )
    merge_user = json.dumps({"topics": topics}, ensure_ascii=False)
    return await _call_json(merge_system, merge_user, max_tokens=4000)


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

    # If there are too many topics, merge in chunks to avoid token limits
    MERGE_CHUNK_SIZE = 60
    if len(all_topics) <= MERGE_CHUNK_SIZE:
        merged = await _merge_topics_chunk(all_topics)
    else:
        chunks = [all_topics[i:i + MERGE_CHUNK_SIZE] for i in range(0, len(all_topics), MERGE_CHUNK_SIZE)]
        chunk_results = []
        for chunk in chunks:
            chunk_results.extend((await _merge_topics_chunk(chunk)).get("topics", []))
        # Second pass to merge across chunks
        merged = await _merge_topics_chunk(chunk_results)

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
        return await _classify_batch_with_retry(reviews, user_goal)

    batches = [reviews[i:i + CLASSIFY_BATCH_SIZE] for i in range(0, len(reviews), CLASSIFY_BATCH_SIZE)]
    batch_results: List[Dict[str, Any]] = []
    for idx, batch in enumerate(batches):
        result = await _classify_batch_with_retry(batch, user_goal)
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


# Cap reviews per topic to keep each evaluate call small and fast.
EVALUATE_MAX_REVIEWS_PER_TOPIC = 80


async def _evaluate_single_topic(
    topic: Dict[str, Any],
    topic_reviews: List[Dict[str, Any]],
    classification_lookup: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Generate one finding for a single topic using only its relevant reviews."""
    if not topic_reviews:
        return None

    system = _load_prompt("evaluate_v1.0.txt")

    # Sort by confidence if available so the strongest evidence is included first
    def _confidence(r: Dict[str, Any]) -> float:
        c = classification_lookup.get(r.get("review_id", ""), {})
        return float(c.get("confidence", 0) or 0)

    topic_reviews = sorted(topic_reviews, key=_confidence, reverse=True)
    topic_reviews = topic_reviews[:EVALUATE_MAX_REVIEWS_PER_TOPIC]

    topic_classifications = []
    for r in topic_reviews:
        c = classification_lookup.get(r.get("review_id", ""))
        if c:
            topic_classifications.append({
                "review_id": c.get("review_id"),
                "topic_ids": [topic.get("id")],
                "sentiment": c.get("sentiment"),
                "severity": c.get("severity"),
                "confidence": c.get("confidence"),
                "evidence_quote": c.get("evidence_quote"),
            })

    user = json.dumps({
        "topics": [topic],
        "classifications": topic_classifications,
        "reviews": topic_reviews,
    }, ensure_ascii=False)

    result = await _call_json(system, user, max_tokens=4000)
    findings = result.get("findings", [])
    if not findings:
        return None

    finding = findings[0]
    finding["topic"] = topic.get("name", finding.get("topic", ""))
    finding["topic_id"] = topic.get("id", "")
    # Enforce minimum evidence rule
    if finding.get("support_count", 0) < 3:
        finding["is_hypothesis"] = True
    return finding


async def evaluate_findings(
    topics: List[Dict[str, Any]],
    classifications: List[Dict[str, Any]],
    reviews: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Evaluate evidence per topic to avoid massive single-call prompts."""
    review_lookup = {r.get("review_id"): r for r in reviews if r.get("review_id")}
    classification_lookup = {c.get("review_id"): c for c in classifications if c.get("review_id")}

    topic_review_map: Dict[str, List[Dict[str, Any]]] = {t.get("id"): [] for t in topics if t.get("id")}
    for c in classifications:
        review_id = c.get("review_id")
        r = review_lookup.get(review_id)
        if not r:
            continue
        for tid in c.get("topic_ids", []):
            if tid in topic_review_map and r not in topic_review_map[tid]:
                topic_review_map[tid].append(r)

    findings: List[Dict[str, Any]] = []
    for topic in topics:
        topic_reviews = topic_review_map.get(topic.get("id"), [])
        finding = await _evaluate_single_topic(topic, topic_reviews, classification_lookup)
        if finding:
            findings.append(finding)

    # Deduplicate and assign stable IDs
    seen: set = set()
    unique_findings: List[Dict[str, Any]] = []
    for idx, f in enumerate(findings, start=1):
        fid = f.get("finding_id") or f"F-{idx:03d}"
        if fid not in seen:
            seen.add(fid)
            f["finding_id"] = fid
            unique_findings.append(f)

    return {"findings": unique_findings}


async def plan_versions(user_goal: str, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    system = _load_prompt("plan_v1.0.txt")
    user = json.dumps({"analysis_goal": user_goal, "findings": findings}, ensure_ascii=False)
    return await _call_json(system, user, max_tokens=4000)


async def generate_prd(user_goal: str, app_id: str, findings: List[Dict[str, Any]], version_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
    system = _load_prompt("prd_v1.0.txt")
    user = json.dumps({"analysis_goal": user_goal, "app_id": app_id, "findings": findings, "version_plan": version_plan}, ensure_ascii=False)
    return await _call_json(system, user, max_tokens=12000)


async def generate_test_cases(prd: Dict[str, Any], findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    system = _load_prompt("testgen_v1.0.txt")
    user = json.dumps({"prd": prd, "findings": findings}, ensure_ascii=False)
    result = await _call_json(system, user, max_tokens=12000)
    return result.get("test_cases", [])


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


def _build_chat_context(context: Dict[str, Any], max_chars: int = 12000) -> str:
    """Build a compact, human-readable context string for the chat agent."""
    lines = [
        f"App ID: {context.get('app_id', 'unknown')}",
        f"Analysis Goal: {context.get('user_goal', '')}",
        f"Review Count: {context.get('review_count', 0)}",
        f"Summary: {context.get('summary', '')}",
        "",
        "Findings:",
    ]
    for f in context.get("findings", [])[:20]:
        lines.append(
            f"- {f.get('finding_id', 'F-???')}: {f.get('statement', '')} "
            f"(confidence: {f.get('confidence', 0)}, support: {f.get('support_count', 0)}, "
            f"hypothesis: {f.get('is_hypothesis', False)})"
        )

    lines.append("")
    lines.append("PRD Requirements:")
    prd = context.get("prd", {})
    for vp in prd.get("version_plan", []):
        version = vp.get("version", "")
        for req in vp.get("requirements", []):
            lines.append(
                f"- {req.get('req_id', 'REQ-???')}: {req.get('title', '')} "
                f"(priority: {req.get('priority', '')}, version: {version})"
            )
            desc = req.get("description", "")
            if desc:
                lines.append(f"  {desc[:200]}{'...' if len(desc) > 200 else ''}")

    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars].rsplit("\n", 1)[0] + "\n...[context truncated]"
    return text


async def chat_with_context(messages: List[Dict[str, str]], context: Dict[str, Any]) -> str:
    system = (
        "You are an App Review Analysis Agent. Answer the user's question based ONLY on the provided analysis context. "
        "The context includes the app's analysis goal, review findings, PRD requirements, and version plans. "
        "Be helpful and concise. If the answer is not in the context, say so clearly. "
        "When referencing findings or requirements, include their IDs (e.g., F-001, REQ-1.1)."
    )
    context_text = _build_chat_context(context)
    langchain_messages = [SystemMessage(content=f"{system}\n\nContext:\n{context_text}")]
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "user":
            langchain_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            langchain_messages.append(AIMessage(content=content))
        elif role == "system":
            langchain_messages.append(SystemMessage(content=content))
    llm = get_llm(temperature=0.3)
    response = await llm.ainvoke(langchain_messages, max_tokens=2000)
    return str(response.content)
