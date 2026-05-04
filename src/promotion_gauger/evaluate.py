from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd
from scipy.stats import pearsonr, spearmanr


def run_evaluation(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query("SELECT * FROM mentions", conn)

    if df.empty:
        print("Evaluation skipped: no mentions found in the database")
        return

    reviews = df[df["platform"] == "review"].copy()
    reviews["stars"] = reviews["engagement"] / 10
    reviews = reviews[(reviews["stars"] >= 1) & (reviews["stars"] <= 5)]
    if len(reviews) >= 10 and reviews["stars"].nunique() > 1 and reviews["overall_sentiment"].nunique() > 1:
        corr, p = spearmanr(reviews["stars"], reviews["overall_sentiment"])
        print(f"Star-Sentiment Correlation: r={corr:.3f}, p={p:.4f}")
        print(f"  {'PASS' if corr > 0.3 and p < 0.05 else 'FAIL'} (target: r > 0.3, p < 0.05)")
    else:
        print("Star-Sentiment Correlation: insufficient review data")

    discount_pattern = re.compile(
        r"\d+\s*%\s*off|half.?price|huge discount|massive sale|best deal|great value",
        re.IGNORECASE,
    )
    has_discount = df["text"].str.contains(discount_pattern, na=False)
    mean_with = df[has_discount]["price_sentiment"].mean()
    mean_without = df[~has_discount]["price_sentiment"].mean()
    gap = mean_with - mean_without
    print(f"\nDiscount Language Price Sensitivity:")
    print(f"  Mean price sentiment WITH discount language:    {mean_with:+.3f}")
    print(f"  Mean price sentiment WITHOUT discount language: {mean_without:+.3f}")
    print(f"  Gap: {gap:+.3f}")
    print(f"  {'PASS' if gap > 0.1 else 'FAIL'} (target gap > 0.1)")

    print(f"\nOverall-Price Axis Consistency:")
    if len(df) >= 2 and df["overall_sentiment"].nunique() > 1 and df["price_sentiment"].nunique() > 1:
        corr, p = pearsonr(df["overall_sentiment"], df["price_sentiment"])
        print(f"  Pearson r={corr:.3f}, p={p:.4f}")
        print(f"  {'PASS' if corr > 0.5 else 'FAIL'} (target: r > 0.5)")
    else:
        print("  insufficient sentiment variance")
        print("  FAIL (target: r > 0.5)")

    print("\nPer-Platform Sentiment Distribution:")
    for platform in df["platform"].dropna().unique():
        sub = df[df["platform"] == platform]
        pos = (sub["overall_sentiment"] > 0.15).sum()
        neg = (sub["overall_sentiment"] < -0.15).sum()
        neu = len(sub) - pos - neg
        print(
            f"  {platform:10s}: {len(sub):4d} total | "
            f"pos={pos} ({100 * pos // len(sub)}%) "
            f"neu={neu} ({100 * neu // len(sub)}%) "
            f"neg={neg} ({100 * neg // len(sub)}%) "
            f"| mean={sub['overall_sentiment'].mean():+.3f}"
        )
