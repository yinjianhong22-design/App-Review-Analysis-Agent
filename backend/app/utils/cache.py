import os
import json
import hashlib
from typing import List, Optional, Dict, Any

from app.models.schemas import Review


class CacheManager:
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _cache_key(self, app_id: str, sort: str) -> str:
        return os.path.join(self.cache_dir, f"{app_id}_{sort}_reviews.json")

    def load_reviews(self, app_id: str, sort: str) -> Optional[List[Review]]:
        path = self._cache_key(app_id, sort)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [Review(**r) for r in data]
        except Exception:
            return None

    def save_reviews(self, app_id: str, sort: str, reviews: List[Review]):
        path = self._cache_key(app_id, sort)
        with open(path, "w", encoding="utf-8") as f:
            json.dump([r.model_dump(mode="json") for r in reviews], f, ensure_ascii=False, indent=2)

    def load_workflow(self, job_id: str) -> Optional[Dict[str, Any]]:
        path = os.path.join(self.cache_dir, f"workflow_{job_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_workflow(self, job_id: str, state: Dict[str, Any]):
        path = os.path.join(self.cache_dir, f"workflow_{job_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)


class ReviewHasher:
    @staticmethod
    def exact_hash(review: Review) -> str:
        text = f"{review.author}|{review.title}|{review.content}|{review.date}"
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def review_id(app_id: str, content: str) -> str:
        return f"R-{app_id}-{hashlib.sha256(content.encode('utf-8')).hexdigest()[:8]}"
