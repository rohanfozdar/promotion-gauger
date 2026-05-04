from __future__ import annotations

import argparse
from pathlib import Path

from promotion_gauger.config import AppConfig, PromoMonitor, RedditCredentials, load_promo_monitors
from promotion_gauger.evaluate import run_evaluation
from promotion_gauger.finetune import finetune_model
from promotion_gauger.ingest import (
    collect_google_news_rss,
    collect_reddit_mentions,
    collect_reddit_rss,
    load_mentions_from_jsonl,
)
from promotion_gauger.sentiment import PromotionSentimentScorer
from promotion_gauger.storage import MentionStore
from promotion_gauger.synthetic import generate_synthetic_mentions
from promotion_gauger.reviews import collect_amazon_reviews


def ensure_sample_data_loaded(store: MentionStore) -> None:
    if store.count_mentions() > 0:
        return
    config = AppConfig()
    seed_sample_data(store, sample_data_path=str(config.sample_data_path))


def seed_sample_data(store: MentionStore, *, sample_data_path: str) -> int:
    mentions = load_mentions_from_jsonl(Path(sample_data_path))
    return ingest_mentions(store, mentions)


def ingest_mentions(
    store: MentionStore,
    mentions,
    scorer: PromotionSentimentScorer | None = None,
) -> int:
    scorer = scorer or PromotionSentimentScorer()
    ingested_count = 0
    for mention in mentions:
        scores = scorer.score(mention.text)
        store.upsert_mention(
            mention,
            overall_sentiment=scores.overall,
            price_sentiment=scores.price,
            brand_sentiment=scores.brand,
            urgency_sentiment=scores.urgency,
        )
        ingested_count += 1
    return ingested_count


def seed_synthetic_data(store: MentionStore, scorer: PromotionSentimentScorer) -> None:
    config = AppConfig()
    monitors = load_promo_monitors(config.promo_config_path)
    total = 0
    for monitor in monitors:
        mentions = generate_synthetic_mentions(monitor, count=40)
        for mention in mentions:
            scores = scorer.score(mention.text)
            store.upsert_mention(
                mention,
                overall_sentiment=scores.overall,
                price_sentiment=scores.price,
                brand_sentiment=scores.brand,
                urgency_sentiment=scores.urgency,
            )
            total += 1
    print(f"Seeded {total} synthetic mentions across {len(monitors)} monitors")


# deprecated: requires Reddit API credentials
def sync_reddit_for_monitors(
    store: MentionStore,
    *,
    monitors: list[PromoMonitor],
    credentials: RedditCredentials,
) -> int:
    ingested_count = 0
    for monitor in monitors:
        if not monitor.enabled:
            continue
        mentions = collect_reddit_mentions(credentials=credentials, monitor=monitor)
        ingested_count += ingest_mentions(store, mentions)
    return ingested_count


def sync_rss_for_monitors(store: MentionStore, scorer: PromotionSentimentScorer) -> None:
    config = AppConfig()
    monitors = [monitor for monitor in load_promo_monitors(config.promo_config_path) if monitor.enabled]
    total = 0
    for monitor in monitors:
        mentions = list(collect_reddit_rss(monitor))
        ingested = 0
        for mention in mentions:
            scores = scorer.score(mention.text)
            store.upsert_mention(
                mention,
                overall_sentiment=scores.overall,
                price_sentiment=scores.price,
                brand_sentiment=scores.brand,
                urgency_sentiment=scores.urgency,
            )
            ingested += 1
        print(f"[{monitor.promo_name}] RSS: {ingested} new mentions ingested")
        total += ingested
    print(f"RSS sync complete: {total} total new mentions")


def sync_all_feeds_for_monitors(store: MentionStore, scorer: PromotionSentimentScorer) -> None:
    config = AppConfig()
    monitors = [monitor for monitor in load_promo_monitors(config.promo_config_path) if monitor.enabled]
    total = 0
    for monitor in monitors:
        rss_mentions = list(collect_reddit_rss(monitor))
        news_mentions = list(collect_google_news_rss(monitor))
        review_mentions = []
        for category in monitor.review_categories:
            review_mentions += list(
                collect_amazon_reviews(
                    category,
                    monitor.promo_name,
                    max_records=25,
                    keywords=monitor.keywords,
                )
            )
        all_mentions = rss_mentions + news_mentions + review_mentions
        ingested = 0
        for mention in all_mentions:
            scores = scorer.score(mention.text)
            store.upsert_mention(
                mention,
                overall_sentiment=scores.overall,
                price_sentiment=scores.price,
                brand_sentiment=scores.brand,
                urgency_sentiment=scores.urgency,
            )
            ingested += 1
        print(
            f"[{monitor.promo_name}] Reddit RSS: {len(rss_mentions)} fetched, "
            f"News: {len(news_mentions)} fetched, Reviews: {len(review_mentions)}, {ingested} new stored"
        )
        total += ingested
    print(f"Full feed sync complete: {total} total new mentions")


def get_enabled_monitors(config: AppConfig, promo_names: list[str] | None = None) -> list[PromoMonitor]:
    monitors = load_promo_monitors(config.promo_config_path)
    if promo_names:
        selected = set(promo_names)
        monitors = [monitor for monitor in monitors if monitor.promo_name in selected]
    return [monitor for monitor in monitors if monitor.enabled]


def dry_run_reddit_pipeline(monitor_name: str | None = None) -> None:
    config = AppConfig()
    monitors = load_promo_monitors(config.promo_config_path)
    if monitor_name is not None:
        monitors = [monitor for monitor in monitors if monitor.promo_name == monitor_name]

    if not monitors:
        print(f"No promo monitors found in {config.promo_config_path}.")
        return

    for monitor in monitors:
        print(f"Monitor: {monitor.promo_name}")
        print(f"Query: {monitor.query}")

    credentials = RedditCredentials.from_env()
    if credentials is None:
        print("No Reddit credentials found. Add .env file when API access is approved.")
        return

    print("Credentials found. Pipeline ready — run with --sync-reddit to ingest.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Promotion Gauger data pipeline")
    parser.add_argument(
        "--seed-sample-data",
        action="store_true",
        help="Load bundled sample social mentions into the SQLite database.",
    )
    parser.add_argument(
        "--sync-reddit",
        action="store_true",
        help="Fetch live Reddit mentions for configured promotion monitors.",
    )
    parser.add_argument(
        "--sync-rss",
        action="store_true",
        help="Fetch public Reddit RSS mentions for configured promotion monitors.",
    )
    parser.add_argument(
        "--sync-feeds",
        action="store_true",
        help="Fetch all public feed sources for configured promotion monitors.",
    )
    parser.add_argument(
        "--promo-name",
        action="append",
        default=[],
        help="Optional promotion name filter for Reddit sync. Repeat for multiple campaigns.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configured Reddit monitors and credential presence without calling the Reddit API.",
    )
    parser.add_argument(
        "--seed-synthetic",
        action="store_true",
        help="Seed synthetic social mentions for all configured promo monitors.",
    )
    parser.add_argument(
        "--finetune",
        action="store_true",
        help="Fine-tune the sentiment model on Amazon review mentions in the local database.",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run sentiment quality checks against the local database.",
    )
    args = parser.parse_args()

    config = AppConfig()
    store = MentionStore(config.db_path)
    store.initialize()

    if args.seed_sample_data:
        count = seed_sample_data(store, sample_data_path=str(config.sample_data_path))
        print(f"Loaded {count} sample mentions into {config.db_path}")
    elif args.evaluate:
        run_evaluation(config.db_path)
    elif args.finetune:
        finetune_model(
            db_path=AppConfig().db_path,
            output_dir=Path("models/retail_sentiment"),
        )
    elif args.seed_synthetic:
        seed_synthetic_data(store, PromotionSentimentScorer())
    elif args.sync_rss:
        sync_rss_for_monitors(store, PromotionSentimentScorer())
    elif args.sync_feeds:
        sync_all_feeds_for_monitors(store, PromotionSentimentScorer())
    elif args.sync_reddit:
        credentials = RedditCredentials.from_env()
        if credentials is None:
            raise SystemExit(
                "Missing Reddit credentials. Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT."
            )
        monitors = get_enabled_monitors(config, promo_names=args.promo_name)
        if not monitors:
            raise SystemExit(
                f"No enabled promo monitors found in {config.promo_config_path} for the requested selection."
            )
        count = sync_reddit_for_monitors(store, monitors=monitors, credentials=credentials)
        print(f"Ingested {count} Reddit mentions into {config.db_path}")
    elif args.dry_run:
        dry_run_reddit_pipeline(args.promo_name[0] if args.promo_name else None)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
