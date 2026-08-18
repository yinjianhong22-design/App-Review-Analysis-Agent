import re
from typing import List, Set

from app.models.schemas import Review
from app.utils.cache import ReviewHasher


class CleaningService:
    def __init__(self, fuzzy_threshold: float = 0.85):
        self.fuzzy_threshold = fuzzy_threshold

    @staticmethod
    def normalize_text(text: str) -> str:
        text = text.strip()
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def normalize_version(version: str) -> str:
        v = version.strip()
        if not v:
            return "unknown"
        # Basic semver cleanup
        v = re.sub(r"[^0-9.]", "", v)
        parts = v.split(".")
        if len(parts) >= 3:
            return ".".join(parts[:3])
        return v or "unknown"

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        """Simple word tokenization for Jaccard similarity."""
        return set(re.findall(r"[a-zA-Z0-9]{2,}", text.lower()))

    @staticmethod
    def _jaccard(a: Set[str], b: Set[str]) -> float:
        if not a or not b:
            return 0.0
        intersection = len(a & b)
        union = len(a | b)
        return intersection / union if union else 0.0

    def clean(self, reviews: List[Review]) -> List[Review]:
        # Normalize content
        for r in reviews:
            r.title = self.normalize_text(r.title)
            r.content = self.normalize_text(r.content)
            r.version = self.normalize_version(r.version)

        # Filter empty / too short
        filtered = [r for r in reviews if len(r.content) >= 5]

        # Exact dedup
        exact_seen = set()
        exact_unique = []
        for r in filtered:
            h = ReviewHasher.exact_hash(r)
            if h not in exact_seen:
                exact_seen.add(h)
                exact_unique.append(r)

        # Fuzzy dedup
        deduped = self._fuzzy_dedup(exact_unique)
        return deduped

    def _fuzzy_dedup(self, reviews: List[Review]) -> List[Review]:
        if len(reviews) < 2:
            return reviews

        tokens = [self._tokenize(r.content) for r in reviews]
        keep = [True] * len(reviews)

        for i in range(len(reviews)):
            if not keep[i]:
                continue
            for j in range(i + 1, len(reviews)):
                if not keep[j]:
                    continue
                sim = self._jaccard(tokens[i], tokens[j])
                if sim >= self.fuzzy_threshold:
                    keep[j] = False

        return [reviews[i] for i in range(len(reviews)) if keep[i]]
