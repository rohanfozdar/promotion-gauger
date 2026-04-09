from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(slots=True)
class AppConfig:
    db_path: Path = Path("data") / "promotion_gauger.db"
    sample_data_path: Path = Path("data") / "sample_mentions.jsonl"
    promo_config_path: Path = Path("data") / "promo_monitors.json"


@dataclass(slots=True)
class RedditCredentials:
    client_id: str
    client_secret: str
    user_agent: str

    @classmethod
    def from_env(cls) -> "RedditCredentials | None":
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = os.getenv("REDDIT_USER_AGENT")
        if not client_id or not client_secret or not user_agent:
            return None
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )


@dataclass(slots=True)
class PromoMonitor:
    promo_name: str
    keywords: list[str]
    subreddits: list[str]
    lookback_hours: int = 72
    post_limit: int = 25
    comments_per_post: int = 5
    enabled: bool = True

    @property
    def query(self) -> str:
        quoted_keywords = [f'"{keyword}"' if " " in keyword else keyword for keyword in self.keywords]
        return " OR ".join(quoted_keywords)

    @property
    def subreddit_query(self) -> str:
        return "+".join(self.subreddits)

    @property
    def earliest_timestamp(self) -> datetime:
        return datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)

    @classmethod
    def from_dict(cls, payload: dict) -> "PromoMonitor":
        return cls(
            promo_name=payload["promo_name"],
            keywords=list(payload["keywords"]),
            subreddits=list(payload["subreddits"]),
            lookback_hours=int(payload.get("lookback_hours", 72)),
            post_limit=int(payload.get("post_limit", 25)),
            comments_per_post=int(payload.get("comments_per_post", 5)),
            enabled=bool(payload.get("enabled", True)),
        )


def load_promo_monitors(path: Path) -> list[PromoMonitor]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [PromoMonitor.from_dict(item) for item in payload]


@dataclass(slots=True)
class AxisLexicon:
    positive: set[str] = field(default_factory=set)
    negative: set[str] = field(default_factory=set)


PRICE_LEXICON = AxisLexicon(
    positive={
        "deal",
        "discount",
        "value",
        "worth",
        "cheap",
        "save",
        "solid",
        "great",
        "best",
    },
    negative={
        "expensive",
        "fake",
        "markup",
        "marked",
        "overpriced",
        "bad",
        "shady",
    },
)

BRAND_LEXICON = AxisLexicon(
    positive={
        "love",
        "premium",
        "trust",
        "great",
        "best",
        "quality",
        "worth",
    },
    negative={
        "desperate",
        "shady",
        "bad",
        "boring",
        "cheap",
        "fake",
        "trick",
    },
)

URGENCY_LEXICON = AxisLexicon(
    positive={
        "now",
        "before",
        "limited",
        "countdown",
        "grabbed",
        "sell",
        "ends",
        "fomo",
        "faster",
    },
    negative={
        "meh",
        "same",
        "again",
        "weekend",
        "every",
        "not",
        "neutral",
    },
)
