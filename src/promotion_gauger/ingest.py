from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from promotion_gauger.config import PromoMonitor, RedditCredentials
from promotion_gauger.storage import MentionRecord


def load_mentions_from_jsonl(path: Path) -> list[MentionRecord]:
    mentions: list[MentionRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            mentions.append(MentionRecord.from_raw(payload))
    return mentions


def collect_reddit_mentions(
    *,
    credentials: RedditCredentials,
    monitor: PromoMonitor,
) -> Iterable[MentionRecord]:
    import praw

    reddit = praw.Reddit(
        client_id=credentials.client_id,
        client_secret=credentials.client_secret,
        user_agent=credentials.user_agent,
    )

    subreddit = reddit.subreddit(monitor.subreddit_query)
    earliest_utc = monitor.earliest_timestamp

    for submission in subreddit.search(
        query=monitor.query,
        sort="new",
        time_filter="week",
        limit=monitor.post_limit,
    ):
        created_at = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
        if created_at < earliest_utc:
            continue
        yield MentionRecord(
            source_id=f"reddit_submission_{submission.id}",
            platform="reddit",
            promo_name=monitor.promo_name,
            author=str(submission.author) if submission.author else "unknown",
            timestamp=submission.created_utc,
            text=f"{submission.title}\n\n{submission.selftext}".strip(),
            engagement=int(submission.score or 0),
        )

        submission.comments.replace_more(limit=0)
        comment_count = 0
        for comment in submission.comments.list():
            if comment_count >= monitor.comments_per_post:
                break
            comment_created_at = datetime.fromtimestamp(comment.created_utc, tz=timezone.utc)
            if comment_created_at < earliest_utc:
                continue
            comment_body = (comment.body or "").strip()
            if not comment_body or comment_body in {"[deleted]", "[removed]"}:
                continue
            yield MentionRecord(
                source_id=f"reddit_comment_{comment.id}",
                platform="reddit",
                promo_name=monitor.promo_name,
                author=str(comment.author) if comment.author else "unknown",
                timestamp=comment.created_utc,
                text=comment_body,
                engagement=int(comment.score or 0),
            )
            comment_count += 1
