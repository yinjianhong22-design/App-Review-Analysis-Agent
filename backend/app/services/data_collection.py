import re
import asyncio
import json
from typing import List, Optional, Tuple

import httpx

from app.config import get_settings
from app.models.schemas import Review, ReviewSource
from app.utils.cache import CacheManager, ReviewHasher


class AppStoreRSSCollector:
    RSS_URL = "https://itunes.apple.com/us/rss/customerreviews/page={page}/id={app_id}/sortby={sort}/json"

    def __init__(self):
        self.settings = get_settings()
        self.cache = CacheManager()

    @staticmethod
    def extract_app_id(url_or_id: str) -> Optional[str]:
        """Extract numeric App ID from URL or raw id."""
        if url_or_id.isdigit():
            return url_or_id
        match = re.search(r"/id(\d+)", url_or_id)
        if match:
            return match.group(1)
        match = re.search(r"id(\d+)", url_or_id)
        if match:
            return match.group(1)
        return None

    async def fetch_page(self, client: httpx.AsyncClient, app_id: str, page: int, sort: str) -> List[Review]:
        url = self.RSS_URL.format(page=page, app_id=app_id, sort=sort)
        try:
            resp = await client.get(url, timeout=20.0)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise RuntimeError(f"Failed to fetch page {page} ({sort}): {e}")

        entries = data.get("feed", {}).get("entry", [])
        reviews = []
        for entry in entries:
            # Skip non-review entries (first entry is usually app metadata)
            if "im:rating" not in entry:
                continue
            try:
                review = Review(
                    review_id=entry.get("id", {}).get("label", ""),
                    author=entry.get("author", {}).get("name", {}).get("label", ""),
                    rating=int(entry.get("im:rating", {}).get("label", 0)),
                    version=entry.get("im:version", {}).get("label", ""),
                    date=entry.get("updated", {}).get("label", ""),
                    title=entry.get("title", {}).get("label", ""),
                    content=entry.get("content", {}).get("label", ""),
                    source=ReviewSource.RSS,
                    page=page,
                    sort=sort,
                    app_id=app_id,
                )
                review.review_id = ReviewHasher.review_id(app_id, review.content)
                reviews.append(review)
            except Exception:
                continue
        return reviews

    async def collect(
        self,
        app_id: str,
        sorts: Tuple[str, str] = ("mostrecent", "mosthelpful"),
        use_cache: bool = True,
    ) -> List[Review]:
        settings = self.settings
        all_reviews: List[Review] = []

        async with httpx.AsyncClient() as client:
            for sort in sorts:
                if use_cache:
                    cached = self.cache.load_reviews(app_id, sort)
                    if cached:
                        all_reviews.extend(cached)
                        continue

                sort_reviews: List[Review] = []
                for page in range(1, settings.rss_max_pages + 1):
                    page_reviews = await self.fetch_page(client, app_id, page, sort)
                    if not page_reviews:
                        break
                    sort_reviews.extend(page_reviews)
                    if len(page_reviews) < settings.rss_page_size:
                        break
                    await asyncio.sleep(settings.rss_request_delay_ms / 1000.0)

                if use_cache:
                    self.cache.save_reviews(app_id, sort, sort_reviews)
                all_reviews.extend(sort_reviews)

        # Deduplicate by exact content hash
        seen = set()
        unique = []
        for r in all_reviews:
            h = ReviewHasher.exact_hash(r)
            if h not in seen:
                seen.add(h)
                unique.append(r)

        return unique[: settings.max_reviews_per_app]


class FileCollector:
    """Load reviews from user-uploaded CSV or JSON."""

    @staticmethod
    def load_json(path: str) -> List[Review]:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "reviews" in data:
            data = data["reviews"]
        reviews = []
        for r in data:
            r = dict(r)
            r["source"] = ReviewSource.JSON
            reviews.append(Review(**r))
        return reviews

    @staticmethod
    def load_csv(path: str) -> List[Review]:
        import csv
        reviews = []
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                reviews.append(Review(
                    review_id=row.get("review_id", ""),
                    author=row.get("author", ""),
                    rating=int(row.get("rating", 3)),
                    version=row.get("version", ""),
                    date=row.get("date", ""),
                    title=row.get("title", ""),
                    content=row.get("content", ""),
                    source=ReviewSource.CSV,
                ))
        return reviews
