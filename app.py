from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from promotion_gauger.pipeline import ensure_sample_data_loaded
from promotion_gauger.config import AppConfig, RedditCredentials, load_promo_monitors
from promotion_gauger.pipeline import sync_reddit_for_monitors
from promotion_gauger.storage import MentionStore


DB_PATH = Path("data") / "promotion_gauger.db"
SENTIMENT_COLORS = {
    "Price": "#6E7F5E",
    "Brand": "#A26752",
    "Urgency": "#B89B72",
}
PLATFORM_COLORS = {
    "reddit": "#7A8B67",
    "x": "#A77964",
}
AXIS_LABELS = {
    "price_sentiment": "Price",
    "brand_sentiment": "Brand",
    "urgency_sentiment": "Urgency",
}


def load_mentions() -> pd.DataFrame:
    store = MentionStore(DB_PATH)
    store.initialize()
    ensure_sample_data_loaded(store)
    return store.fetch_mentions_dataframe()


def sync_live_reddit(promo_names: list[str]) -> tuple[bool, str]:
    config = AppConfig()
    credentials = RedditCredentials.from_env()
    if credentials is None:
        return False, (
            "Missing Reddit credentials. Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT "
            "in your shell before syncing."
        )

    monitors = [
        monitor
        for monitor in load_promo_monitors(config.promo_config_path)
        if monitor.enabled and (not promo_names or monitor.promo_name in promo_names)
    ]
    if not monitors:
        return False, f"No enabled promo monitors matched the current selection in {config.promo_config_path}."

    store = MentionStore(config.db_path)
    store.initialize()
    count = sync_reddit_for_monitors(store, monitors=monitors, credentials=credentials)
    return True, f"Synced {count} Reddit mentions from {len(monitors)} configured monitor(s)."


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


def metric_card(label: str, value: str, copy: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-copy">{copy}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_feed_card(row: pd.Series) -> None:
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
                <span class="feed-pill">{row["platform"]}</span>
                <span class="feed-pill">{row["promo_name"]}</span>
                <span>@{row["author"]}</span>
                <span>{row["timestamp"].strftime("%b %d, %I:%M %p UTC")}</span>
                <span>{int(row["engagement"])} engagements</span>
            </div>
            <p class="feed-text">{row["text"]}</p>
            <div class="signal-row">{chips}</div>
        </article>
        """,
        unsafe_allow_html=True,
    )


def build_timeline_figure(timeline: pd.DataFrame):
    fig = px.line(
        timeline,
        x="hour",
        y="score",
        color="axis",
        color_discrete_map=SENTIMENT_COLORS,
        markers=True,
    )
    fig.update_traces(line=dict(width=3), marker=dict(size=8))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=12, r=12, t=14, b=12),
        legend_title_text="",
        hovermode="x unified",
        font=dict(color="#3b3129", family="Inter, sans-serif"),
    )
    fig.update_xaxes(
        title=None,
        showgrid=False,
        linecolor="rgba(60, 47, 34, 0.16)",
        tickfont=dict(color="#6f665c"),
    )
    fig.update_yaxes(
        title=None,
        showgrid=True,
        gridcolor="rgba(60, 47, 34, 0.08)",
        zeroline=True,
        zerolinecolor="rgba(60, 47, 34, 0.12)",
        tickfont=dict(color="#6f665c"),
    )
    return fig


def build_volume_figure(volume: pd.DataFrame):
    fig = px.bar(
        volume,
        x="hour",
        y="size",
        color="platform",
        color_discrete_map=PLATFORM_COLORS,
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=12, r=12, t=14, b=12),
        legend_title_text="",
        hovermode="x unified",
        font=dict(color="#3b3129", family="Inter, sans-serif"),
        bargap=0.28,
    )
    fig.update_xaxes(
        title=None,
        showgrid=False,
        linecolor="rgba(60, 47, 34, 0.16)",
        tickfont=dict(color="#6f665c"),
    )
    fig.update_yaxes(
        title=None,
        showgrid=True,
        gridcolor="rgba(60, 47, 34, 0.08)",
        tickfont=dict(color="#6f665c"),
    )
    return fig


st.set_page_config(
    page_title="Promotion Gauger",
    page_icon="🔥",
    layout="wide",
)

inject_styles()

mentions = load_mentions()

if mentions.empty:
    st.warning("No mentions are available yet. Seed sample data or connect a live source.")
    st.stop()

mentions["timestamp"] = pd.to_datetime(mentions["timestamp"], utc=True)
mentions["hour"] = mentions["timestamp"].dt.floor("h")
mentions["platform"] = mentions["platform"].str.upper().replace({"X": "X", "REDDIT": "REDDIT"})

st.sidebar.markdown("### Monitoring Lens")
st.sidebar.caption("Shape the view without losing the editorial feel of the main canvas.")

platforms = sorted(mentions["platform"].dropna().unique().tolist())
selected_platforms = st.sidebar.multiselect(
    "Platform",
    options=platforms,
    default=platforms,
)

promo_names = sorted(mentions["promo_name"].dropna().unique().tolist())
selected_promos = st.sidebar.multiselect(
    "Promotion",
    options=promo_names,
    default=promo_names,
)

config = AppConfig()
configured_monitors = load_promo_monitors(config.promo_config_path)
configured_names = [monitor.promo_name for monitor in configured_monitors if monitor.enabled]

st.sidebar.markdown("### Live sync")
st.sidebar.caption("Use your configured Reddit monitors to pull fresh mentions into the local store.")
st.sidebar.markdown(
    f"Configured monitors: **{len(configured_names)}**  \n"
    f"Active campaigns: **{', '.join(configured_names) if configured_names else 'None'}**"
)
if st.sidebar.button("Sync Reddit now", width="stretch"):
    with st.sidebar:
        with st.spinner("Pulling fresh Reddit mentions..."):
            ok, message = sync_live_reddit(selected_promos)
    if ok:
        st.sidebar.success(message)
        st.rerun()
    else:
        st.sidebar.error(message)

filtered = mentions[
    mentions["platform"].isin(selected_platforms)
    & mentions["promo_name"].isin(selected_promos)
].copy()

if filtered.empty:
    st.markdown('<p class="section-label">No active view</p>', unsafe_allow_html=True)
    st.info("No mentions match the active filters.")
    st.stop()

selected_promo_text = ", ".join(selected_promos[:2]) if selected_promos else "All campaigns"
if len(selected_promos) > 2:
    selected_promo_text += f" +{len(selected_promos) - 2} more"
latest_window = filtered["timestamp"].max() - filtered["timestamp"].min()
avg_sentiment = filtered[
    ["price_sentiment", "brand_sentiment", "urgency_sentiment"]
].mean().mean()
top_platform = filtered["platform"].mode().iat[0]

st.markdown(
    f"""
    <section class="hero-shell">
        <div class="hero-grid">
            <div>
                <span class="eyebrow"><span class="pulse-dot"></span>Live promotion monitoring</span>
                <h1 class="hero-title">Promotion Gauger</h1>
                <p class="hero-copy">
                    Read the emotional temperature of a promotion before the revenue curve catches up.
                    This view turns scattered social chatter into a calm operating surface for pricing,
                    brand, and urgency response.
                </p>
                <div class="chip-row">
                    <span class="chip">Campaigns: {selected_promo_text}</span>
                    <span class="chip">Platforms: {', '.join(selected_platforms)}</span>
                    <span class="chip">Lead platform: {top_platform}</span>
                </div>
            </div>
            <div class="hero-panel">
                <p class="hero-panel-label">Current read</p>
                <p class="hero-panel-value">{avg_sentiment:+.2f}</p>
                <p class="hero-panel-copy">
                    Average signal across the three sentiment lenses over an observed window of
                    {str(latest_window).split('.')[0]}. Use this as an early read on whether a
                    campaign feels compelling, trustworthy, and time-sensitive.
                </p>
            </div>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

st.markdown('<p class="section-label">Executive snapshot</p>', unsafe_allow_html=True)
metric_cols = st.columns(4)
with metric_cols[0]:
    metric_card("Mentions captured", f"{len(filtered):,}", "Active conversation volume across the selected monitoring window.")
with metric_cols[1]:
    metric_card("Price sentiment", f"{filtered['price_sentiment'].mean():+.2f}", "How credible and valuable the offer feels in the market.")
with metric_cols[2]:
    metric_card("Brand sentiment", f"{filtered['brand_sentiment'].mean():+.2f}", "Whether the promotion strengthens trust or creates skepticism.")
with metric_cols[3]:
    metric_card("Urgency sentiment", f"{filtered['urgency_sentiment'].mean():+.2f}", "Whether shoppers feel compelled to act now rather than wait.")

timeline = (
    filtered.groupby("hour", as_index=False)[
        ["price_sentiment", "brand_sentiment", "urgency_sentiment"]
    ]
    .mean()
    .melt(id_vars="hour", var_name="axis", value_name="score")
)
timeline["axis"] = timeline["axis"].map(AXIS_LABELS).fillna(timeline["axis"])

volume = filtered.groupby(["hour", "platform"], as_index=False).size()
volume["platform"] = volume["platform"].str.lower()

left_col, right_col = st.columns([1.35, 1], gap="large")
with left_col:
    st.markdown(
        """
        <section class="panel">
            <div class="panel-heading">
                <div>
                    <p class="panel-title">Sentiment over time</p>
                    <p class="panel-copy">Track how the tone of the promotion moves across price, brand, and urgency as conversation evolves.</p>
                </div>
                <span class="panel-kicker">Signal trend</span>
            </div>
        """,
        unsafe_allow_html=True,
    )
    st.plotly_chart(build_timeline_figure(timeline), width="stretch")
    st.markdown("</section>", unsafe_allow_html=True)

with right_col:
    st.markdown(
        """
        <section class="panel">
            <div class="panel-heading">
                <div>
                    <p class="panel-title">Conversation volume</p>
                    <p class="panel-copy">Watch where discussion is clustering so spikes in chatter stand out before downstream performance does.</p>
                </div>
                <span class="panel-kicker">Channel mix</span>
            </div>
        """,
        unsafe_allow_html=True,
    )
    st.plotly_chart(build_volume_figure(volume), width="stretch")
    st.markdown(
        '<p class="operator-note">The strongest platform in this view is highlighted through calmer earth-toned bars instead of default dashboard colors.</p>',
        unsafe_allow_html=True,
    )
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
            "price_sentiment",
            "brand_sentiment",
            "urgency_sentiment",
            "text",
        ]
    ].copy()
    st.dataframe(table_view, width="stretch", hide_index=True)

st.markdown("</section>", unsafe_allow_html=True)
