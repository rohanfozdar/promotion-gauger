from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(slots=True)
class MentionRecord:
    source_id: str
    platform: str
    promo_name: str
    author: str
    timestamp: str
    text: str
    engagement: int

    @classmethod
    def from_raw(cls, payload: dict) -> "MentionRecord":
        raw_timestamp = payload["timestamp"]
        if isinstance(raw_timestamp, (int, float)):
            raw_timestamp = datetime.fromtimestamp(raw_timestamp, tz=timezone.utc).isoformat()
        return cls(
            source_id=str(payload["source_id"]),
            platform=payload["platform"],
            promo_name=payload["promo_name"],
            author=payload.get("author", "unknown"),
            timestamp=raw_timestamp,
            text=payload["text"],
            engagement=int(payload.get("engagement", 0)),
        )


class MentionStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mentions (
                    source_id TEXT PRIMARY KEY,
                    platform TEXT NOT NULL,
                    promo_name TEXT NOT NULL,
                    author TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    text TEXT NOT NULL,
                    engagement INTEGER NOT NULL DEFAULT 0,
                    overall_sentiment REAL NOT NULL,
                    price_sentiment REAL NOT NULL,
                    brand_sentiment REAL NOT NULL,
                    urgency_sentiment REAL NOT NULL
                )
                """
            )

    def upsert_mention(
        self,
        mention: MentionRecord,
        *,
        overall_sentiment: float,
        price_sentiment: float,
        brand_sentiment: float,
        urgency_sentiment: float,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mentions (
                    source_id,
                    platform,
                    promo_name,
                    author,
                    timestamp,
                    text,
                    engagement,
                    overall_sentiment,
                    price_sentiment,
                    brand_sentiment,
                    urgency_sentiment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    platform = excluded.platform,
                    promo_name = excluded.promo_name,
                    author = excluded.author,
                    timestamp = excluded.timestamp,
                    text = excluded.text,
                    engagement = excluded.engagement,
                    overall_sentiment = excluded.overall_sentiment,
                    price_sentiment = excluded.price_sentiment,
                    brand_sentiment = excluded.brand_sentiment,
                    urgency_sentiment = excluded.urgency_sentiment
                """,
                (
                    mention.source_id,
                    mention.platform,
                    mention.promo_name,
                    mention.author,
                    mention.timestamp,
                    mention.text,
                    mention.engagement,
                    overall_sentiment,
                    price_sentiment,
                    brand_sentiment,
                    urgency_sentiment,
                ),
            )

    def count_mentions(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM mentions").fetchone()
        return int(row[0]) if row else 0

    def fetch_mentions_dataframe(self):
        import pandas as pd

        with self._connect() as conn:
            return pd.read_sql_query(
                "SELECT * FROM mentions ORDER BY timestamp ASC",
                conn,
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)
