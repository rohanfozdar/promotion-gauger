# Promotion Gauger

Promotion Gauger is a lightweight starter project for tracking how shoppers react to a live retail promotion across social channels. It is designed as a complementary product story for Operand: Operand measures commercial performance, while this app surfaces customer reaction signals in real time.

## What this version does

- Tracks promotion-related posts and comments in a simple normalized format
- Scores each mention across three sentiment axes:
  - price sentiment
  - brand sentiment
  - urgency sentiment
- Stores events in SQLite
- Visualizes sentiment over time, mention volume, and notable verbatims in Streamlit
- Ships with sample data so the app works immediately

## Project layout

```text
.
├── app.py
├── data/
│   └── sample_mentions.jsonl
├── pyproject.toml
├── README.md
└── src/promotion_gauger/
    ├── config.py
    ├── ingest.py
    ├── pipeline.py
    ├── sentiment.py
    └── storage.py
```

## Quick start

1. Create and activate a virtual environment.
2. Install the project:

```bash
pip install -e .
```

3. Seed the local SQLite database with sample mentions:

```bash
python3 seed_demo.py --seed-sample-data
```

4. Launch the dashboard:

```bash
streamlit run app.py
```

## Adding live data later

This scaffold now includes a first live Reddit ingestion path using configured promo monitors.

### Reddit setup

1. Create a Reddit app and export credentials:

```bash
export REDDIT_CLIENT_ID="your_client_id"
export REDDIT_CLIENT_SECRET="your_client_secret"
export REDDIT_USER_AGENT="promotion-gauger/0.1 by your_reddit_username"
```

2. Edit the monitor file at `data/promo_monitors.json` to define:

- `promo_name`
- `keywords`
- `subreddits`
- `lookback_hours`
- `post_limit`
- `comments_per_post`

3. Run a live sync:

```bash
python3 seed_demo.py --sync-reddit
```

4. Optional: sync only one campaign:

```bash
python3 seed_demo.py --sync-reddit --promo-name "Spring Sneaker Drop"
```

### Next iteration ideas

The scaffold still keeps live collection intentionally simple. A stronger next iteration would:

1. Replace or extend the sample loader with a Reddit collector using `praw`.
2. Add X/Twitter or TikTok ingestion behind separate adapters.
3. Swap the rule-based sentiment scorer for a fine-tuned transformer model.
4. Join sentiment data to sales lift or campaign KPIs for a stronger Operand-style narrative.

## Notes

- Sample data is the default so the app remains runnable without API credentials.
- Reddit collection is stubbed in code but requires API keys and a subreddit/query strategy.
- The baseline scoring model is heuristic, which makes it easy to inspect and improve.
