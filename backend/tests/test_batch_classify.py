"""Quick smoke test for batch classification without real LLM calls."""
import asyncio
from app.graph import chains


async def fake_classify(batch, user_goal, max_tokens=6000):
    # Simulate different topics per batch
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
    # Simulate merging: B*-T001 are similar, B*-T002 are similar
    data = __import__("json").loads(user)
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


async def main():
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
    # Every classification should map to a global topic id
    global_ids = {t["id"] for t in result["topics"]}
    for c in result["classifications"]:
        for tid in c["topic_ids"]:
            assert tid in global_ids, f"Unknown topic id {tid}"

    print("Batch classification smoke test passed.")

    chains._classify_single_batch = original
    chains._call_json = original_call_json


if __name__ == "__main__":
    asyncio.run(main())
