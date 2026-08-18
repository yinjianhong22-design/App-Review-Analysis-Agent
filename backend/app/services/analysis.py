from typing import List, Dict, Any

from app.services.ai_agent import LLMClient


class AnalysisService:
    def __init__(self):
        self.llm = LLMClient()

    async def classify(self, reviews: List[Dict[str, Any]], analysis_goal: str) -> Dict[str, Any]:
        """Stage 4: dynamic topic discovery via LLM."""
        batch_size = 25
        all_topics = []
        all_classifications = []
        topic_counter = 1

        for i in range(0, len(reviews), batch_size):
            batch = reviews[i : i + batch_size]
            result = await self.llm.classify_reviews(batch, analysis_goal)
            batch_topics = result.get("topics", [])
            # Remap topic IDs to global IDs to avoid collisions across batches
            id_map = {}
            for t in batch_topics:
                old_id = t["id"]
                new_id = f"T-{topic_counter:03d}"
                id_map[old_id] = new_id
                t["id"] = new_id
                topic_counter += 1
                all_topics.append(t)

            for c in result.get("classifications", []):
                c["topic_ids"] = [id_map.get(tid, tid) for tid in c.get("topic_ids", [])]
                all_classifications.append(c)

        # Merge semantically similar topics (simple keyword overlap heuristic)
        merged_topics, merged_classifications = self._merge_similar_topics(all_topics, all_classifications)

        return {"topics": merged_topics, "classifications": merged_classifications}

    def _merge_similar_topics(
        self,
        topics: List[Dict[str, Any]],
        classifications: List[Dict[str, Any]],
    ) -> tuple:
        if len(topics) <= 1:
            return topics, classifications

        # Build keyword sets
        topic_keywords = {t["id"]: set(t.get("keywords", [])) for t in topics}
        merge_map = {}
        kept = []

        for i, t in enumerate(topics):
            tid = t["id"]
            if tid in merge_map:
                continue
            merged_into = tid
            for j in range(i + 1, len(topics)):
                other = topics[j]
                oid = other["id"]
                if oid in merge_map:
                    continue
                a = topic_keywords[tid]
                b = topic_keywords[oid]
                if not a or not b:
                    continue
                overlap = len(a & b) / min(len(a), len(b))
                if overlap >= 0.5:
                    merge_map[oid] = merged_into
                    # Merge keywords and counts
                    t["keywords"] = list(a | b)
                    t["review_count"] = t.get("review_count", 0) + other.get("review_count", 0)
            kept.append(t)

        # Remap classifications
        for c in classifications:
            c["topic_ids"] = [merge_map.get(tid, tid) for tid in c.get("topic_ids", [])]

        return kept, classifications

    async def evaluate(self, topics, classifications, reviews) -> List[Dict[str, Any]]:
        """Stage 5: evidence evaluation and conflict detection.
        Chunked by topic to avoid exceeding output token limits."""
        if not topics:
            return []

        review_ids = {r["review_id"] for r in reviews}
        review_map = {r["review_id"]: r for r in reviews}

        # Build classifications-by-topic index
        topic_class_map: Dict[str, List[Dict[str, Any]]] = {t["id"]: [] for t in topics}
        for c in classifications:
            for tid in c.get("topic_ids", []):
                if tid in topic_class_map:
                    topic_class_map[tid].append(c)

        # Enrich topics with rule-based stats
        enriched_topics = []
        for t in topics:
            tid = t["id"]
            cls_list = topic_class_map[tid]
            ratings = [c.get("rating", 3) for c in cls_list if "rating" in c]
            t["rating_mean"] = sum(ratings) / len(ratings) if ratings else None
            t["rating_variance"] = self._variance(ratings) if len(ratings) > 1 else 0
            t["classification_count"] = len(cls_list)
            enriched_topics.append(t)

        # Chunk topics to keep LLM output size manageable
        batch_size = 8
        all_findings: List[Dict[str, Any]] = []
        finding_counter = 1

        for i in range(0, len(enriched_topics), batch_size):
            batch_topics = enriched_topics[i : i + batch_size]
            batch_topic_ids = {t["id"] for t in batch_topics}

            # Only include classifications relevant to this topic batch
            batch_classifications = [
                c for c in classifications
                if any(tid in batch_topic_ids for tid in c.get("topic_ids", []))
            ]

            # Include only reviews referenced by those classifications
            referenced_review_ids = set()
            for c in batch_classifications:
                referenced_review_ids.add(c.get("review_id"))
            batch_reviews = [review_map[rid] for rid in referenced_review_ids if rid in review_map]

            batch_findings = await self.llm.evaluate_findings(
                batch_topics, batch_classifications, batch_reviews
            )

            # Remap finding IDs to be globally unique
            for f in batch_findings:
                f["finding_id"] = f"F-{finding_counter:03d}"
                finding_counter += 1
                f["supporting_reviews"] = [rid for rid in f.get("supporting_reviews", []) if rid in review_ids]
                f["conflicting_reviews"] = [rid for rid in f.get("conflicting_reviews", []) if rid in review_ids]
                f["sample_count"] = len(f["supporting_reviews"])
                all_findings.append(f)

        return all_findings

    @staticmethod
    def _variance(values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / (len(values) - 1)
