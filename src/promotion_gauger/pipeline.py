from __future__ import annotations

import argparse
from pathlib import Path

from promotion_gauger.config import AppConfig, PromoMonitor, RedditCredentials, load_promo_monitors
from promotion_gauger.ingest import collect_reddit_mentions, load_mentions_from_jsonl
from promotion_gauger.sentiment import PromotionSentimentScorer
from promotion_gauger.storage import MentionStore


def ensure_sample_data_loaded(store: MentionStore) -> None:
    if store.count_mentions() > 0:
        return
    config = AppConfig()
    seed_sample_data(store, sample_data_path=str(config.sample_data_path))


def seed_sample_data(store: MentionStore, *, sample_data_path: str) -> int:
    mentions = load_mentions_from_jsonl(Path(sample_data_path))
    return ingest_mentions(store, mentions)


def ingest_mentions(store: MentionStore, mentions) -> int:
    scorer = PromotionSentimentScorer()
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


def get_enabled_monitors(config: AppConfig, promo_names: list[str] | None = None) -> list[PromoMonitor]:
    monitors = load_promo_monitors(config.promo_config_path)
    if promo_names:
        selected = set(promo_names)
        monitors = [monitor for monitor in monitors if monitor.promo_name in selected]
    return [monitor for monitor in monitors if monitor.enabled]


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
        "--promo-name",
        action="append",
        default=[],
        help="Optional promotion name filter for Reddit sync. Repeat for multiple campaigns.",
    )
    args = parser.parse_args()

    config = AppConfig()
    store = MentionStore(config.db_path)
    store.initialize()

    if args.seed_sample_data:
        count = seed_sample_data(store, sample_data_path=str(config.sample_data_path))
        print(f"Loaded {count} sample mentions into {config.db_path}")
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
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
