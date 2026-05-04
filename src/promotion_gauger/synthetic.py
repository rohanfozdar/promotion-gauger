from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random

from promotion_gauger.config import PromoMonitor
from promotion_gauger.storage import MentionRecord


AUTHOR_POOL = [
    "deal_hawk_99",
    "frugal_finds",
    "promo_watcher",
    "savings_scout",
    "checkout_chaser",
    "value_vault",
    "retail_radar",
    "discount_digger",
    "cart_sniper",
    "bargain_beacon",
    "price_patrol",
    "sale_signal",
    "offer_oracle",
    "thrifty_thread",
    "dealroom_daily",
    "coupon_current",
    "markdown_maven",
    "flashsalefan",
    "basket_buzz",
    "promo_pulse",
]

POSITIVE_TEMPLATES = [
    "Just grabbed the {keyword} deal — honestly couldn't believe the price",
    "The {keyword} promo is legit, stock is moving fast",
    "Been waiting for a {keyword} sale like this, great timing",
    "Picked up two, the {keyword} discount is real this time",
    "This {keyword} offer is the best I've seen all year",
]

NEGATIVE_TEMPLATES = [
    "The {keyword} sale feels like a fake markup situation",
    "Not impressed with the {keyword} promo, they do this every month",
    "Disappointing {keyword} deal honestly, not what was advertised",
    "The {keyword} discount barely covers shipping, feels like a joke",
    "Seen better {keyword} pricing from competitors this week",
]

NEUTRAL_TEMPLATES = [
    "Anyone else see the {keyword} sale? Wondering if it's worth it",
    "The {keyword} promo is available now according to their site",
    "Just noticed {keyword} dropped in price, not sure for how long",
    "Posted about the {keyword} deal in case anyone's interested",
    "The {keyword} promotion started today, details in the link",
]

PLATFORMS = ["reddit", "reddit", "reddit", "twitter"]


def generate_synthetic_mentions(
    monitor: PromoMonitor,
    count: int = 40,
    hours_back: int = 72,
    seed: int | None = 42,
) -> list[MentionRecord]:
    rng = random.Random(seed) if seed is not None else random.Random()
    now = datetime.now(timezone.utc)
    mentions: list[MentionRecord] = []

    for index in range(count):
        tier_roll = rng.random()
        if tier_roll < 0.4:
            template = rng.choice(POSITIVE_TEMPLATES)
        elif tier_roll < 0.7:
            template = rng.choice(NEGATIVE_TEMPLATES)
        else:
            template = rng.choice(NEUTRAL_TEMPLATES)

        keyword = rng.choice(monitor.keywords)
        base_offset_hours = (hours_back / max(count, 1)) * index
        jitter_minutes = rng.randint(-15, 15)
        timestamp = now - timedelta(hours=base_offset_hours, minutes=jitter_minutes)

        mentions.append(
            MentionRecord(
                source_id=f"synthetic_{monitor.promo_name.replace(' ', '_')}_{index}",
                platform=rng.choice(PLATFORMS),
                promo_name=monitor.promo_name,
                author=rng.choice(AUTHOR_POOL),
                timestamp=timestamp.isoformat(),
                text=template.format(keyword=keyword),
                engagement=min(int(rng.expovariate(0.3)), 500),
            )
        )

    return mentions
