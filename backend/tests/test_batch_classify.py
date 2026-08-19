"""Quick smoke tests for batch classification and per-topic evaluation."""
import asyncio
import json
from app.graph import chains


async def fake_classify(batch, user_goal, max_tokens=6000):
    batch_idx = batch[0]["review_id"].split("-")[-1]
    topics = [
        {
            "id": f"B{batch_idx}-T001",
            "name": f"Topic A from batch {batch_idx}",
            "description": "Common issue A",
            "keywords": ["a", "issue"],
            "review_count": len(batch),
        },
        {
            "id": f"B{batch_idx}-T002",
            "name": "Subscription confusion",
            "description": "Users confused by pricing",
            "keywords": ["price", "subscription"],
            "review_count": max(0, len(batch) - 10),
        },
    ]
    classifications = []
    for i, r in enumerate(batch):
        if i % 2 == 0:
            tids = [f"B{batch_idx}-T001"]
        else:
            tids = [f"B{batch_idx}-T001", f"B{batch_idx}-T002"]
        classifications.append({
            "review_id": r["review_id"],
            "topic_ids": tids,
            "sentiment": "negative",
            "severity": 3,
            "confidence": 0.8,
            "evidence_quote": r["text"][:20],
        })
    return {"topics": topics, "classifications": classifications}


async def fake_merge(system, user, max_tokens=8000):
    data = json.loads(user)
    return {
        "topics": [
            {
                "id": "T-GLOBAL-001",
                "name": "Common issue A",
                "description": "Merged topic A",
                "keywords": ["a", "issue"],
                "source_topic_ids": [t["id"] for t in data["topics"] if "T001" in t["id"]],
            },
            {
                "id": "T-GLOBAL-002",
                "name": "Subscription confusion",
                "description": "Merged pricing topic",
                "keywords": ["price", "subscription"],
                "source_topic_ids": [t["id"] for t in data["topics"] if "T002" in t["id"]],
            },
        ]
    }


async def fake_evaluate(system, user, max_tokens=4000):
    data = json.loads(user)
    topic = data["topics"][0]
    return {
        "findings": [
            {
                "finding_id": f"F-{topic['id']}",
                "topic": topic["name"],
                "statement": f"Users report {topic['name']}",
                "evidence_ids": [r["review_id"] for r in data["reviews"][:3]],
                "sample_quotes": [data["reviews"][0]["text"][:30]],
                "support_count": len(data["reviews"]),
                "confidence": 0.9,
                "conflict_notes": [],
                "is_hypothesis": False,
            }
        ]
    }


async def fake_chat_invoke(messages, max_tokens=2000):
    # Verify conversation history roles are mapped correctly
    roles = [m.__class__.__name__ for m in messages]
    assert roles[0] == "SystemMessage"
    assert any(isinstance(m, chains.HumanMessage) for m in messages)
    assert any(isinstance(m, chains.AIMessage) for m in messages)
    class _Resp:
        content = "This is a test answer based on the context."
    return _Resp()


async def test_classify_batches():
    original = chains._classify_single_batch
    original_call_json = chains._call_json
    chains._classify_single_batch = fake_classify
    chains._call_json = fake_merge

    reviews = [
        {"review_id": f"R-{i:03d}", "text": f"Review text number {i}" * 5, "rating": 3}
        for i in range(120)
    ]

    result = await chains.classify_reviews(reviews, "Improve the app")

    assert len(result["topics"]) == 2, f"Expected 2 global topics, got {len(result['topics'])}"
    assert len(result["classifications"]) == 120, f"Expected 120 classifications, got {len(result['classifications'])}"
    global_ids = {t["id"] for t in result["topics"]}
    for c in result["classifications"]:
        for tid in c["topic_ids"]:
            assert tid in global_ids, f"Unknown topic id {tid}"

    print("Batch classification smoke test passed.")

    chains._classify_single_batch = original
    chains._call_json = original_call_json


async def test_evaluate_per_topic():
    original_call_json = chains._call_json
    chains._call_json = fake_evaluate

    topics = [
        {"id": "T-GLOBAL-001", "name": "Topic A", "description": "...", "keywords": ["a"]},
        {"id": "T-GLOBAL-002", "name": "Topic B", "description": "...", "keywords": ["b"]},
    ]
    reviews = [
        {"review_id": f"R-{i:03d}", "text": f"Review text number {i}" * 5, "rating": 3}
        for i in range(10)
    ]
    classifications = []
    for i, r in enumerate(reviews):
        classifications.append({
            "review_id": r["review_id"],
            "topic_ids": ["T-GLOBAL-001"] if i < 7 else ["T-GLOBAL-002"],
            "sentiment": "negative",
            "severity": 3,
            "confidence": 0.8,
            "evidence_quote": r["text"][:20],
        })

    result = await chains.evaluate_findings(topics, classifications, reviews)
    assert len(result["findings"]) == 2, f"Expected 2 findings, got {len(result['findings'])}"
    finding_ids = {f["finding_id"] for f in result["findings"]}
    assert "T-GLOBAL-001" in finding_ids or "F-T-GLOBAL-001" in finding_ids

    print("Per-topic evaluation smoke test passed.")

    chains._call_json = original_call_json


class FakeLLM:
    async def ainvoke(self, messages, max_tokens=2000):
        roles = [m.__class__.__name__ for m in messages]
        assert roles[0] == "SystemMessage"
        assert any(isinstance(m, chains.HumanMessage) for m in messages)
        assert any(isinstance(m, chains.AIMessage) for m in messages)
        class _Resp:
            content = "This is a test answer based on the context."
        return _Resp()


async def test_chat_message_roles():
    original_get_llm = chains.get_llm
    chains.get_llm = lambda temperature=None: FakeLLM()

    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
        {"role": "user", "content": "What are the top issues?"},
    ]
    context = {
        "app_id": "123",
        "user_goal": "Improve app",
        "review_count": 100,
        "summary": "summary",
        "findings": [{"finding_id": "F-001", "statement": "Crash on launch", "confidence": 0.9, "support_count": 10, "is_hypothesis": False}],
        "prd": {"version_plan": []},
    }
    answer = await chains.chat_with_context(messages, context)
    assert "test answer" in answer

    print("Chat message role smoke test passed.")

    chains.get_llm = original_get_llm


async def test_classify_retry_on_length_error():
    call_count = [0]

    async def fake_classify_with_failure(batch, user_goal, max_tokens=4000):
        call_count[0] += 1
        # First call with full batch fails; subsequent calls succeed
        if len(batch) > 10:
            raise Exception("This model's maximum context length is 8192 tokens")
        return await fake_classify(batch, user_goal, max_tokens)

    original = chains._classify_single_batch
    chains._classify_single_batch = fake_classify_with_failure

    reviews = [
        {"review_id": f"R-{i:03d}", "text": f"Review text number {i}" * 5, "rating": 3}
        for i in range(24)
    ]

    result = await chains._classify_batch_with_retry(reviews, "Improve the app")
    assert len(result["classifications"]) == 24, f"Expected 24 classifications, got {len(result['classifications'])}"
    assert call_count[0] > 1, "Expected retry after length error"

    print(f"Adaptive retry test passed ({call_count[0]} calls).")

    chains._classify_single_batch = original


async def main():
    await test_classify_batches()
    await test_evaluate_per_topic()
    await test_classify_retry_on_length_error()
    await test_chat_message_roles()


if __name__ == "__main__":
    asyncio.run(main())
