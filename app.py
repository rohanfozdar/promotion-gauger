from __future__ import annotations

from pathlib import Path
import sys
from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from apscheduler.schedulers.background import BackgroundScheduler

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from promotion_gauger.config import AppConfig, PromoMonitor
from promotion_gauger.ingest import collect_google_news_rss, collect_reddit_rss
from promotion_gauger.pipeline import ingest_mentions, sync_all_feeds_for_monitors
from promotion_gauger.sentiment import PromotionSentimentScorer
from promotion_gauger.storage import MentionStore


DB_PATH = Path("data") / "promotion_gauger.db"
SENTIMENT_COLORS = {
    "Overall": "#4A5568",
    "Price": "#6E7F5E",
    "Brand": "#A26752",
    "Urgency": "#B89B72",
}


@st.cache_resource
def get_store() -> MentionStore:
    store = MentionStore(AppConfig().db_path)
    store.initialize()
    return store


@st.cache_resource
def get_scorer() -> PromotionSentimentScorer:
    finetuned_path = Path("models/retail_sentiment")
    return PromotionSentimentScorer(
        model_path=finetuned_path if finetuned_path.exists() else None
    )


def load_mentions() -> pd.DataFrame:
    return get_store().fetch_mentions_dataframe()


def sync_live_feeds(store: MentionStore, scorer: PromotionSentimentScorer) -> tuple[bool, str]:
    try:
        sync_all_feeds_for_monitors(store, scorer)
        return True, "Synced all public feeds for configured monitors."
    except Exception as exc:
        return False, f"Feed sync failed: {exc}"


def execute_market_search(
    search_query: str,
    store: MentionStore,
    scorer: PromotionSentimentScorer,
) -> pd.DataFrame:
    monitor = PromoMonitor(
        promo_name=search_query,
        keywords=[search_query],
        subreddits=["deals", "frugal", "buyitforlife"],
        # Do NOT pull Amazon reviews for ad-hoc searches.
        # They are category-generic and will contaminate non-retail queries.
        review_categories=[],
        enabled=True,
    )

    mentions = []
    mentions += list(collect_reddit_rss(monitor))
    mentions += list(collect_google_news_rss(monitor))
    ingest_mentions(store, mentions, scorer)

    df = store.fetch_mentions_dataframe()
    return df[(df["promo_name"] == search_query) & (df["platform"] != "review")].copy()


def start_scheduler(
    store: MentionStore,
    scorer: PromotionSentimentScorer,
    interval_minutes: int = 30,
) -> None:
    """Start background feed sync scheduler. Safe to call multiple times — only starts once."""
    current_scheduler = st.session_state.get("scheduler")
    if current_scheduler is not None and not st.session_state.get("scheduler_started"):
        current_scheduler.shutdown(wait=False)
        st.session_state.pop("scheduler", None)

    if st.session_state.get("scheduler_started"):
        return

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=lambda: sync_all_feeds_for_monitors(store, scorer),
        trigger="interval",
        minutes=interval_minutes,
        id="feed_sync",
        replace_existing=True,
    )
    scheduler.start()
    st.session_state["scheduler"] = scheduler
    st.session_state["scheduler_started"] = True
    st.session_state["scheduler_interval"] = interval_minutes


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600;700&display=swap');

        :root {
            --bg: #f4efe6;
            --bg-accent: #ebe3d5;
            --surface: rgba(255, 251, 245, 0.86);
            --surface-strong: rgba(250, 244, 235, 0.98);
            --surface-contrast: #f0e6d8;
            --text: #27211b;
            --muted: #72675d;
            --line: rgba(63, 48, 35, 0.10);
            --shadow: 0 22px 60px rgba(72, 57, 41, 0.08);
            --olive: #6e7f5e;
            --clay: #a26752;
            --sand: #b89b72;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(184, 155, 114, 0.14), transparent 28%),
                radial-gradient(circle at top right, rgba(110, 127, 94, 0.14), transparent 24%),
                linear-gradient(180deg, #f7f2ea 0%, var(--bg) 40%, #f1e8db 100%);
            color: var(--text);
            font-family: "Inter", sans-serif;
        }

        .stApp [data-testid="stAppViewContainer"] {
            background: transparent;
        }

        .stApp [data-testid="stHeader"] {
            background: rgba(244, 239, 230, 0.78);
            border-bottom: 1px solid rgba(63, 48, 35, 0.06);
        }

        .stApp [data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(248, 243, 236, 0.96) 0%, rgba(239, 232, 221, 0.96) 100%);
            border-right: 1px solid var(--line);
        }

        .stApp [data-testid="stSidebar"] > div:first-child {
            padding-top: 2rem;
        }

        .stApp [data-testid="stSidebar"] label,
        .stApp [data-testid="stSidebar"] p,
        .stApp [data-testid="stSidebar"] span,
        .stApp [data-testid="stSidebar"] h1,
        .stApp [data-testid="stSidebar"] h2,
        .stApp [data-testid="stSidebar"] h3 {
            color: var(--text);
        }

        .stApp [data-testid="stSidebar"] [data-baseweb="select"],
        .stApp [data-testid="stSidebar"] [data-baseweb="tag"] {
            font-family: "Inter", sans-serif;
        }

        section[data-testid="stSidebar"] .stButton > button {
            background-color: #F5F2ED !important;
            color: #2D2D2D !important;
            border: 1px solid #D9D4CC !important;
            border-radius: 6px !important;
        }

        section[data-testid="stSidebar"] .stButton > button:hover {
            background-color: #EDE8E0 !important;
            border-color: #C4BDB4 !important;
        }

        .block-container {
            padding-top: 2.25rem;
            padding-bottom: 3rem;
            max-width: 1240px;
        }

        h1, h2, h3 {
            color: var(--text);
            letter-spacing: -0.02em;
        }

        .eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.42rem 0.8rem;
            border-radius: 999px;
            background: rgba(255, 250, 243, 0.8);
            border: 1px solid rgba(80, 63, 47, 0.08);
            color: var(--muted);
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
        }

        .pulse-dot {
            width: 0.5rem;
            height: 0.5rem;
            border-radius: 999px;
            background: var(--olive);
            box-shadow: 0 0 0 0 rgba(110, 127, 94, 0.4);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(110, 127, 94, 0.32); }
            70% { box-shadow: 0 0 0 10px rgba(110, 127, 94, 0); }
            100% { box-shadow: 0 0 0 0 rgba(110, 127, 94, 0); }
        }

        .hero-shell {
            position: relative;
            overflow: hidden;
            padding: 2rem 2rem 2.2rem 2rem;
            border-radius: 30px;
            background:
                linear-gradient(135deg, rgba(255, 252, 247, 0.96), rgba(244, 235, 223, 0.92)),
                var(--surface);
            border: 1px solid rgba(77, 60, 42, 0.08);
            box-shadow: var(--shadow);
            margin-bottom: 1.4rem;
        }

        .hero-shell::after {
            content: "";
            position: absolute;
            top: -80px;
            right: -20px;
            width: 280px;
            height: 280px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(110, 127, 94, 0.14) 0%, rgba(110, 127, 94, 0) 72%);
            pointer-events: none;
        }

        .hero-grid {
            display: grid;
            grid-template-columns: minmax(0, 1.7fr) minmax(260px, 0.9fr);
            gap: 1.4rem;
            align-items: end;
        }

        .hero-title {
            margin: 0.8rem 0 0.7rem 0;
            font-family: "Instrument Serif", serif;
            font-size: clamp(3rem, 6vw, 5.1rem);
            line-height: 0.96;
            font-weight: 400;
        }

        .hero-copy {
            max-width: 48rem;
            color: var(--muted);
            font-size: 1.05rem;
            line-height: 1.7;
            margin-bottom: 1.2rem;
        }

        .chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.65rem;
        }

        .chip {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.62rem 0.9rem;
            border-radius: 999px;
            background: rgba(255, 250, 243, 0.74);
            border: 1px solid rgba(63, 48, 35, 0.08);
            color: var(--text);
            font-size: 0.9rem;
        }

        .hero-panel {
            padding: 1.2rem 1.2rem 1.1rem 1.2rem;
            border-radius: 22px;
            background: rgba(251, 245, 237, 0.84);
            border: 1px solid rgba(63, 48, 35, 0.08);
            backdrop-filter: blur(4px);
        }

        .hero-panel-label {
            margin: 0;
            color: var(--muted);
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
        }

        .hero-panel-value {
            margin: 0.5rem 0 0.2rem 0;
            font-size: 2rem;
            font-weight: 600;
            letter-spacing: -0.04em;
        }

        .hero-panel-copy {
            margin: 0;
            color: var(--muted);
            line-height: 1.55;
            font-size: 0.94rem;
        }

        .section-label {
            margin: 1.8rem 0 0.75rem 0;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.16em;
            font-size: 0.76rem;
        }

        .metric-card {
            height: 100%;
            padding: 1.15rem 1.15rem 1.25rem 1.15rem;
            border-radius: 24px;
            background: var(--surface);
            border: 1px solid rgba(72, 57, 41, 0.08);
            box-shadow: 0 16px 40px rgba(72, 57, 41, 0.06);
        }

        .metric-label {
            color: var(--muted);
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            margin-bottom: 0.75rem;
        }

        .metric-value {
            color: var(--text);
            font-size: 2.15rem;
            line-height: 1;
            font-weight: 600;
            letter-spacing: -0.05em;
            margin-bottom: 0.55rem;
            display: flex;
            align-items: center;
            gap: 0.6rem;
        }

        .metric-dot {
            width: 0.72rem;
            height: 0.72rem;
            border-radius: 999px;
            flex: 0 0 auto;
        }

        .metric-copy {
            color: var(--muted);
            font-size: 0.95rem;
            line-height: 1.55;
        }

        .panel {
            padding: 1.2rem 1.2rem 0.7rem 1.2rem;
            border-radius: 28px;
            background: rgba(255, 251, 245, 0.78);
            border: 1px solid rgba(63, 48, 35, 0.08);
            box-shadow: var(--shadow);
            margin-bottom: 1rem;
        }

        .panel-heading {
            display: flex;
            justify-content: space-between;
            align-items: end;
            gap: 1rem;
            margin-bottom: 0.6rem;
        }

        .panel-title {
            margin: 0;
            font-family: "Instrument Serif", serif;
            font-size: 2rem;
            font-weight: 400;
            line-height: 1;
        }

        .panel-copy {
            margin: 0.25rem 0 0 0;
            color: var(--muted);
            font-size: 0.96rem;
            line-height: 1.5;
        }

        .panel-kicker {
            color: var(--muted);
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            white-space: nowrap;
        }

        .feed-card {
            padding: 1rem 1rem 1rem 1rem;
            border-radius: 22px;
            background: rgba(255, 250, 244, 0.82);
            border: 1px solid rgba(63, 48, 35, 0.08);
            box-shadow: 0 14px 32px rgba(72, 57, 41, 0.05);
            margin-bottom: 0.9rem;
        }

        .feed-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            align-items: center;
            margin-bottom: 0.8rem;
            color: var(--muted);
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
        }

        .feed-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.32rem 0.62rem;
            border-radius: 999px;
            border: 1px solid rgba(63, 48, 35, 0.08);
            background: rgba(247, 240, 230, 0.9);
        }

        .score-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.32rem 0.62rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 600;
            letter-spacing: 0.02em;
            border: 1px solid rgba(63, 48, 35, 0.08);
        }

        .feed-text {
            color: var(--text);
            font-size: 1rem;
            line-height: 1.7;
            margin: 0 0 0.9rem 0;
        }

        .signal-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
        }

        .signal-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.48rem 0.68rem;
            border-radius: 999px;
            font-size: 0.86rem;
            border: 1px solid rgba(63, 48, 35, 0.08);
            background: rgba(255, 255, 255, 0.55);
            color: var(--text);
        }

        .signal-dot {
            width: 0.55rem;
            height: 0.55rem;
            border-radius: 999px;
        }

        .operator-note {
            margin-top: 0.35rem;
            color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.55;
        }

        [data-testid="stDataFrame"],
        [data-testid="stMetric"] {
            border-radius: 18px;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.4rem;
        }

        .stTabs [data-baseweb="tab"] {
            background: rgba(249, 243, 236, 0.86);
            border: 1px solid rgba(63, 48, 35, 0.08);
            border-radius: 999px;
            color: var(--muted);
            padding: 0.6rem 0.9rem;
        }

        .stTabs [aria-selected="true"] {
            color: var(--text);
            border-color: rgba(63, 48, 35, 0.16);
            background: rgba(255, 250, 243, 0.96);
        }

        @media (max-width: 980px) {
            .hero-grid {
                grid-template-columns: 1fr;
            }

            .hero-title {
                font-size: 3.25rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sentiment_state(value: float) -> tuple[str, str]:
    if value > 0.1:
        return "#6E7F5E", "rgba(110, 127, 94, 0.16)"
    if value < -0.1:
        return "#A26752", "rgba(162, 103, 82, 0.16)"
    return "#8B8378", "rgba(139, 131, 120, 0.14)"


def metric_card(label: str, value: float, copy: str) -> None:
    dot_color, _ = sentiment_state(value)
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value"><span class="metric-dot" style="background:{dot_color};"></span>{value:+.2f}</div>
            <div class="metric-copy">{copy}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_feed_card(row: pd.Series) -> None:
    _, badge_background = sentiment_state(float(row["overall_sentiment"]))
    badge_color, _ = sentiment_state(float(row["overall_sentiment"]))
    text = str(row["text"])
    truncated_text = f"{text[:200]}..." if len(text) > 200 else text
    source_url = str(row.get("source_url", "") or "").strip()
    source_link = ""
    if source_url:
        source_link = (
            f'<a href="{escape(source_url, quote=True)}" target="_blank" '
            'style="font-size:0.78rem;color:#6E7F5E;text-decoration:none;">'
            "↗ View source</a>"
        )
    axes = [
        ("Price", row["price_sentiment"], SENTIMENT_COLORS["Price"]),
        ("Brand", row["brand_sentiment"], SENTIMENT_COLORS["Brand"]),
        ("Urgency", row["urgency_sentiment"], SENTIMENT_COLORS["Urgency"]),
    ]
    chips = "".join(
        f"""
        <span class="signal-chip">
            <span class="signal-dot" style="background:{color};"></span>
            {label} {score:+.2f}
        </span>
        """
        for label, score, color in axes
    )
    st.markdown(
        f"""
        <article class="feed-card">
            <div class="feed-meta">
                <span class="feed-pill">{escape(str(row["platform"]).lower())}</span>
                <span class="feed-pill">↑ {int(row["engagement"])}</span>
                {source_link}
                <span class="feed-pill">{escape(str(row["promo_name"]))}</span>
                <span class="score-badge" style="background:{badge_background}; color:{badge_color};">{row["overall_sentiment"]:+.2f}</span>
                <span>@{escape(str(row["author"]))}</span>
                <span>{row["timestamp"].strftime("%b %d, %I:%M %p UTC")}</span>
            </div>
            <p class="feed-text">{escape(truncated_text)}</p>
            <div class="signal-row">{chips}</div>
        </article>
        """,
        unsafe_allow_html=True,
    )


def build_sentiment_distribution_figure(df: pd.DataFrame):
    """
    Horizontal stacked bar showing % positive / neutral / negative
    for each sentiment axis: Overall, Price, Brand, Urgency.
    Positive = score > 0.15, Negative = score < -0.15, Neutral = between.
    """
    axes = {
        "Overall": "overall_sentiment",
        "Price": "price_sentiment",
        "Brand": "brand_sentiment",
        "Urgency": "urgency_sentiment",
    }
    rows = []
    for label, col in axes.items():
        total = max(len(df), 1)
        pos = (df[col] > 0.15).sum() / total * 100
        neg = (df[col] < -0.15).sum() / total * 100
        neu = 100 - pos - neg
        rows.append({"Axis": label, "Positive": pos, "Neutral": neu, "Negative": neg})

    dist_df = pd.DataFrame(rows)
    fig = go.Figure()
    for sentiment, color in [
        ("Positive", "#6E7F5E"),
        ("Neutral", "#B89B72"),
        ("Negative", "#A26752"),
    ]:
        fig.add_trace(
            go.Bar(
                name=sentiment,
                x=dist_df[sentiment],
                y=dist_df["Axis"],
                orientation="h",
                marker_color=color,
                text=dist_df[sentiment].apply(lambda value: f"{value:.0f}%"),
                textposition="inside",
            )
        )

    fig.update_layout(
        barmode="stack",
        title="Sentiment Breakdown by Axis",
        font=dict(color="#1A1A1A"),
        xaxis=dict(
            title="% of mentions",
            range=[0, 100],
            showgrid=False,
            tickfont=dict(color="#1A1A1A"),
            title_font=dict(color="#1A1A1A"),
        ),
        yaxis=dict(showgrid=False, tickfont=dict(color="#1A1A1A")),
        plot_bgcolor="#FAF9F6",
        paper_bgcolor="#FAF9F6",
        legend=dict(orientation="h", y=-0.2, font=dict(color="#1A1A1A")),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def build_source_breakdown_figure(df: pd.DataFrame):
    """
    Two-panel view:
    Left: donut chart showing mention count by platform (reddit / news / review)
    Right: horizontal bar showing average overall_sentiment per platform
    Rendered as two Plotly subplots side by side.
    """
    from plotly.subplots import make_subplots

    platform_counts = df["platform"].value_counts().reset_index()
    platform_counts.columns = ["platform", "count"]
    platform_sentiment = df.groupby("platform")["overall_sentiment"].mean().reset_index()

    color_map = {"reddit": "#6E7F5E", "news": "#B89B72", "review": "#A26752"}
    fig = make_subplots(
        rows=1,
        cols=2,
        specs=[[{"type": "domain"}, {"type": "xy"}]],
        subplot_titles=["Mentions by Source", "Avg Sentiment by Source"],
    )
    fig.add_trace(
        go.Pie(
            labels=platform_counts["platform"],
            values=platform_counts["count"],
            hole=0.5,
            marker_colors=[color_map.get(platform, "#999") for platform in platform_counts["platform"]],
            textinfo="label+percent",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=platform_sentiment["overall_sentiment"],
            y=platform_sentiment["platform"],
            orientation="h",
            marker_color=[color_map.get(platform, "#999") for platform in platform_sentiment["platform"]],
            text=platform_sentiment["overall_sentiment"].apply(lambda value: f"{value:+.2f}"),
            textposition="outside",
        ),
        row=1,
        col=2,
    )
    fig.update_layout(
        font=dict(color="#1A1A1A"),
        plot_bgcolor="#FAF9F6",
        paper_bgcolor="#FAF9F6",
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(
            range=[-1, 1],
            zeroline=True,
            zerolinecolor="#ddd",
            showgrid=False,
            tickfont=dict(color="#1A1A1A"),
            title_font=dict(color="#1A1A1A"),
        ),
        yaxis=dict(showgrid=False, tickfont=dict(color="#1A1A1A")),
    )
    for annotation in fig.layout.annotations:
        annotation.font.color = "#1A1A1A"
    return fig


st.set_page_config(
    page_title="Promotion Gauger",
    page_icon="🔥",
    layout="wide",
)

inject_styles()

store = get_store()
scorer = get_scorer()
start_scheduler(store, scorer, interval_minutes=30)

if st.sidebar.button("Sync all feeds", width="stretch"):
    with st.sidebar:
        with st.spinner("Pulling fresh public feed mentions..."):
            ok, message = sync_live_feeds(store, scorer)
    if ok:
        st.sidebar.success(message)
        st.rerun()
    else:
        st.sidebar.error(message)

if st.session_state.get("scheduler_started"):
    interval = st.session_state.get("scheduler_interval", 30)
    st.sidebar.caption(f"Auto-sync every {interval} min")

st.markdown(
    """
    <section class="hero-shell">
        <div class="hero-grid">
            <div>
                <span class="eyebrow"><span class="pulse-dot"></span>Market consensus tracking</span>
                <h1 class="hero-title">Promotion Gauger</h1>
                <p class="hero-copy">
                    Search a promotion, product, or offer and pull a live read from Reddit, news,
                    and retail reviews before the revenue curve catches up.
                </p>
            </div>
            <div class="hero-panel">
                <p class="hero-panel-label">Search mode</p>
                <p class="hero-panel-value">Live</p>
                <p class="hero-panel-copy">
                    Each search builds a temporary monitor and scores fresh mentions with the
                    retail-tuned sentiment model.
                </p>
            </div>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

st.markdown("### What promotion do you want to track?")
search_query = st.text_input(
    label="",
    placeholder="e.g. Nike Air Max sale, whey protein discount, summer running gear...",
    label_visibility="collapsed",
    key="market_consensus_query",
)
run_search = st.button("Get Market Consensus", type="primary")
search_query = search_query.strip()

if run_search and search_query:
    with st.spinner("Pulling data from Reddit, News, and Reviews..."):
        filtered = execute_market_search(search_query, store, scorer)
    st.session_state["last_market_consensus_query"] = search_query
elif search_query and st.session_state.get("last_market_consensus_query") == search_query:
    mentions = load_mentions()
    filtered = mentions[(mentions["promo_name"] == search_query) & (mentions["platform"] != "review")].copy()
else:
    if store.count_mentions() == 0:
        st.info("No data yet — click 'Sync all feeds' in the sidebar to load mentions.")
    st.markdown(
        """
        <div style="text-align:center;padding:4rem 2rem;color:#999">
            <div style="font-size:3rem;margin-bottom:1rem">🔍</div>
            <div style="font-size:1.1rem">Enter a promotion above to see what the market thinks</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

if len(filtered) == 0:
    st.warning(
        f"No mentions found for '{search_query}'. Try broader keywords — e.g. "
        "'Jaguar EV rebrand' instead of 'Jaguar electric vehicle promotion'."
    )
    st.stop()

filtered["timestamp"] = pd.to_datetime(filtered["timestamp"], utc=True, format="mixed")
filtered["platform"] = filtered["platform"].astype(str).str.lower()

overall_mean = filtered["overall_sentiment"].mean()
if overall_mean > 0.15:
    consensus_label = "Positive"
    consensus_color = "#6E7F5E"
elif overall_mean < -0.15:
    consensus_label = "Negative"
    consensus_color = "#A26752"
else:
    consensus_label = "Mixed"
    consensus_color = "#B89B72"

st.markdown(
    f"""
    <div style="padding:1.5rem;border-radius:8px;background:{consensus_color}18;border-left:4px solid {consensus_color};margin-bottom:1.5rem">
        <div style="font-size:0.85rem;color:#666;margin-bottom:0.25rem">Market Consensus — {len(filtered)} sources analyzed</div>
        <div style="font-size:2rem;font-weight:700;color:{consensus_color}">{consensus_label}</div>
        <div style="font-size:0.9rem;color:#444;margin-top:0.25rem">Overall sentiment score: {overall_mean:+.2f}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<p class="section-label">Executive snapshot</p>', unsafe_allow_html=True)
metric_cols = st.columns(4)
with metric_cols[0]:
    metric_card("Overall sentiment", float(filtered["overall_sentiment"].mean()), "The blended emotional read across all captured conversation.")
with metric_cols[1]:
    metric_card("Price sentiment", float(filtered["price_sentiment"].mean()), "How credible and valuable the offer feels in the market.")
with metric_cols[2]:
    metric_card("Brand sentiment", float(filtered["brand_sentiment"].mean()), "Whether the promotion strengthens trust or creates skepticism.")
with metric_cols[3]:
    metric_card("Urgency sentiment", float(filtered["urgency_sentiment"].mean()), "Whether shoppers feel compelled to act now rather than wait.")

left_col, right_col = st.columns([1.35, 1], gap="large")
with left_col:
    st.markdown(
        """
        <section class="panel">
            <div class="panel-heading">
                <div>
                    <p class="panel-title">Sentiment distribution</p>
                    <p class="panel-copy">See how mentions split into positive, neutral, and negative reads across each sentiment axis.</p>
                </div>
                <span class="panel-kicker">Axis mix</span>
            </div>
        """,
        unsafe_allow_html=True,
    )
    st.plotly_chart(build_sentiment_distribution_figure(filtered), width="stretch")
    st.markdown("</section>", unsafe_allow_html=True)

with right_col:
    st.markdown(
        """
        <section class="panel">
            <div class="panel-heading">
                <div>
                    <p class="panel-title">Source breakdown</p>
                    <p class="panel-copy">Compare where mentions came from and how each source type is leaning on overall sentiment.</p>
                </div>
                <span class="panel-kicker">Source mix</span>
            </div>
        """,
        unsafe_allow_html=True,
    )
    st.plotly_chart(build_source_breakdown_figure(filtered), width="stretch")
    st.markdown("</section>", unsafe_allow_html=True)

st.markdown(
    """
    <section class="panel">
        <div class="panel-heading">
            <div>
                <p class="panel-title">Live mention feed</p>
                <p class="panel-copy">A readable stream of the highest-signal posts and comments, prioritized by engagement and recency.</p>
            </div>
            <span class="panel-kicker">Verbatim intelligence</span>
        </div>
    """,
    unsafe_allow_html=True,
)

feed = filtered.sort_values(["engagement", "timestamp"], ascending=[False, False]).head(8)
for _, row in feed.iterrows():
    render_feed_card(row)

with st.expander("Operator table view"):
    table_view = feed[
        [
            "timestamp",
            "platform",
            "author",
            "promo_name",
            "overall_sentiment",
            "price_sentiment",
            "brand_sentiment",
            "urgency_sentiment",
            "source_url",
            "text",
        ]
    ].copy()
    st.dataframe(table_view, width="stretch", hide_index=True)

st.markdown("</section>", unsafe_allow_html=True)
