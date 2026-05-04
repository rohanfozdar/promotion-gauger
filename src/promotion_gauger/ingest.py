from __future__ import annotations

import html
import json
import re
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus

import feedparser
import requests

from promotion_gauger.config import PromoMonitor, RedditCredentials
from promotion_gauger.storage import MentionRecord


REMOVED_BODIES = {"[deleted]", "[removed]"}
MAX_SUBMISSION_TEXT_LENGTH = 1000
RSS_USER_AGENT = "PromotionGauger/1.0"
BOILERPLATE_SIGNALS = {"submitted by", "[link]", "[comments]"}
OFF_TOPIC_SIGNALS = {
    "arrested",
    "robbery",
    "robbed",
    "assault",
    "beaten",
    "shooting",
    "stabbed",
    "killed",
    "murder",
    "crime",
    "police",
    "lawsuit",
    "sued",
    "court",
    "verdict",
    "scandal",
    "suspended",
}


def load_mentions_from_jsonl(path: Path) -> list[MentionRecord]:
    mentions: list[MentionRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            mentions.append(MentionRecord.from_raw(payload))
    return mentions


def _fetch_subreddit_posts(reddit, monitor: PromoMonitor):
    subreddit = reddit.subreddit(monitor.subreddit_query)
    return subreddit.search(
        query=monitor.query,
        sort="new",
        time_filter="week",
        limit=monitor.post_limit,
    )


def _extract_submission(submission, promo_name: str) -> MentionRecord:
    text = f"{submission.title} {(submission.selftext or '')}".strip()[:MAX_SUBMISSION_TEXT_LENGTH]
    permalink = getattr(submission, "permalink", "")
    source_url = f"https://www.reddit.com{permalink}" if permalink else getattr(submission, "url", "")
    return MentionRecord(
        source_id=f"reddit_submission_{submission.id}",
        platform="reddit",
        promo_name=promo_name,
        author=str(submission.author) if submission.author else "unknown",
        timestamp=datetime.fromtimestamp(submission.created_utc, tz=timezone.utc).isoformat(),
        text=text,
        engagement=int(submission.score or 0),
        source_url=source_url,
    )


def _extract_comments(submission, promo_name: str, limit: int) -> Iterable[MentionRecord]:
    comment_count = 0
    submission.comments.replace_more(limit=0)
    for comment in submission.comments:
        if comment_count >= limit:
            break
        body = (comment.body or "").strip()
        if not body or body in REMOVED_BODIES:
            continue
        yield MentionRecord(
            source_id=f"reddit_comment_{comment.id}",
            platform="reddit",
            promo_name=promo_name,
            author=str(comment.author) if comment.author else "unknown",
            timestamp=datetime.fromtimestamp(comment.created_utc, tz=timezone.utc).isoformat(),
            text=body,
            engagement=int(comment.score or 0),
            source_url=f"https://www.reddit.com{comment.permalink}" if getattr(comment, "permalink", "") else "",
        )
        comment_count += 1


def _is_boilerplate(text: str) -> bool:
    lowered = text.lower()
    return sum(signal in lowered for signal in BOILERPLATE_SIGNALS) >= 2


def _is_off_topic(text: str) -> bool:
    lowered = text.lower()
    return any(signal in lowered for signal in OFF_TOPIC_SIGNALS)


# deprecated: requires Reddit API credentials
def collect_reddit_mentions(
    *,
    credentials: RedditCredentials,
    monitor: PromoMonitor,
) -> Iterable[MentionRecord]:
    try:
        import praw

        reddit = praw.Reddit(
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            user_agent=credentials.user_agent,
        )
        reddit.read_only = True

        for submission in _fetch_subreddit_posts(reddit, monitor):
            yield _extract_submission(submission, monitor.promo_name)
            yield from _extract_comments(
                submission,
                promo_name=monitor.promo_name,
                limit=monitor.comments_per_post,
            )
    except Exception as exc:
        try:
            import praw

            if isinstance(exc, praw.exceptions.PRAWException):
                print(f"Reddit fetch error: {exc}")
                return
        except Exception:
            pass
        print(f"Reddit fetch error: {exc}")
        return


def collect_reddit_rss(monitor: PromoMonitor) -> Iterable[MentionRecord]:
    encoded_query = quote_plus(monitor.query)
    subreddits = monitor.subreddit_query
    urls = [
        f"https://www.reddit.com/search.rss?q={encoded_query}&sort=new&limit=25",
        f"https://www.reddit.com/r/{subreddits}/search.rss?q={encoded_query}&sort=new&restrict_sr=1&limit=25",
    ]

    for url in urls:
        try:
            response = requests.get(
                url,
                headers={"User-Agent": RSS_USER_AGENT},
                timeout=10,
            )
            response.raise_for_status()
            feed = feedparser.parse(response.text)
            yielded_for_url = 0

            for entry in feed.entries:
                raw_text = entry.get("summary", "") or entry.get("title", "")
                cleaned_text = re.sub(r"<[^>]+>", "", raw_text)
                cleaned_text = html.unescape(cleaned_text).strip()[:MAX_SUBMISSION_TEXT_LENGTH]
                if _is_boilerplate(cleaned_text):
                    continue
                if len(cleaned_text) < 40:
                    continue

                try:
                    timestamp = parsedate_to_datetime(entry.get("published", "")).isoformat()
                except Exception:
                    timestamp = datetime.now(timezone.utc).isoformat()

                yield MentionRecord(
                    source_id=f"reddit_rss_{entry.get('id', entry.get('link', ''))[-32:]}",
                    platform="reddit",
                    promo_name=monitor.promo_name,
                    author=entry.get("author", "unknown"),
                    timestamp=timestamp,
                    text=cleaned_text,
                    engagement=0,
                    source_url=entry.get("link", ""),
                )
                yielded_for_url += 1
            if yielded_for_url == 0:
                print(f"RSS URL returned 0 usable mentions: {url}")
        except Exception as exc:
            print(f"RSS fetch error for {url}: {exc}")
            continue


def collect_google_news_rss(monitor: PromoMonitor) -> Iterable[MentionRecord]:
    encoded_query = quote_plus(monitor.query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

    try:
        response = requests.get(
            url,
            headers={"User-Agent": RSS_USER_AGENT},
            timeout=10,
        )
        response.raise_for_status()
        feed = feedparser.parse(response.text)

        for entry in feed.entries:
            title = html.unescape(entry.get("title", ""))
            summary = html.unescape(re.sub(r"<[^>]+>", "", entry.get("summary", "")))
            source = entry.get("source", {})
            source_title = source.get("title", "") if isinstance(source, dict) else ""
            if source_title and title.endswith(f" - {source_title}"):
                title = title[: -(len(source_title) + 3)].strip()
            if summary and summary.strip() != title.strip():
                cleaned_text = f"{title}. {summary}"
            else:
                cleaned_text = title
            if cleaned_text.count(title[:30]) > 1:
                cleaned_text = title[:500]
            if source_title and cleaned_text.rstrip().endswith(source_title):
                cleaned_text = cleaned_text[: cleaned_text.rstrip().rfind(source_title)].rstrip(". ").strip()
            cleaned_text = cleaned_text.strip()[:500]
            if _is_boilerplate(cleaned_text):
                continue
            if _is_off_topic(cleaned_text):
                continue
            if len(cleaned_text) < 40:
                continue

            try:
                timestamp = parsedate_to_datetime(entry.get("published", "")).isoformat()
            except Exception:
                timestamp = datetime.now(timezone.utc).isoformat()

            yield MentionRecord(
                source_id=f"gnews_{hash(entry.get('link', '')) % 10**12}",
                platform="news",
                promo_name=monitor.promo_name,
                author=source.get("title", "unknown") if isinstance(source, dict) else "unknown",
                timestamp=timestamp,
                text=cleaned_text,
                engagement=0,
                source_url=entry.get("link", ""),
            )
    except Exception as exc:
        print(f"Google News RSS fetch error: {exc}")
        return
