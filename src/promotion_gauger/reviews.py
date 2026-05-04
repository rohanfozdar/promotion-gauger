from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from promotion_gauger.storage import MentionRecord


VALID_CATEGORIES = [
    "Clothing_Shoes_and_Jewelry",
    "Sports_and_Outdoors",
    "Health_and_Household",
]


def _is_relevant(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def collect_amazon_reviews(
    category: str,
    promo_name: str,
    max_records: int = 50,
    min_rating: int = 1,
    keywords: list[str] | None = None,
) -> Iterable[MentionRecord]:
    if category not in VALID_CATEGORIES:
        print(f"Amazon review warning: unsupported category {category}")
        return

    try:
        from datasets import load_dataset

        dataset = load_dataset(
            "McAuley-Lab/Amazon-Reviews-2023",
            f"raw_review_{category}",
            split="full",
            streaming=True,
            trust_remote_code=True,
        )

        emitted = 0
        for index, record in enumerate(dataset):
            if emitted >= max_records:
                break
            text = str(record.get("text", "")).strip()
            if len(text) < 40:
                continue
            if keywords and not _is_relevant(text, keywords):
                continue

            rating = record.get("rating", 3)
            if rating < min_rating:
                continue

            try:
                timestamp = datetime.fromtimestamp(
                    record.get("timestamp", 0) / 1000,
                    tz=timezone.utc,
                ).isoformat()
            except Exception:
                timestamp = datetime.now(timezone.utc).isoformat()

            asin = record.get("asin", "")
            yield MentionRecord(
                source_id=f"amazon_{category[:8]}_{asin or 'unknown'}_{index}",
                platform="review",
                promo_name=promo_name,
                author=record.get("user_id", "anonymous")[:16],
                timestamp=timestamp,
                text=text[:600],
                engagement=int(float(rating) * 10),
                source_url=f"https://www.amazon.com/dp/{asin}" if asin else "",
            )
            emitted += 1
    except Exception as exc:
        print(f"Amazon review fetch error for {category}: {exc}")
        return
