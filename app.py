import json
import random

import streamlit as st
import yfinance as yf

from dashboard import INDICES, get_index_data, simplified_fear_greed, overall_sentiment
from watchlist import WATCHLIST, get_stock_data, format_market_cap
from technical_analysis import (
    calculate_sma, calculate_rsi, calculate_macd, calculate_bollinger_bands,
    calculate_support_resistance, interpret_trend, interpret_rsi,
    interpret_macd, interpret_bollinger,
)
from news_analysis import get_news, rough_tag, get_product_news, get_market_wide_news, flag_watchlist_mentions
from stock_ratings import (
    score_trend, score_rsi, score_macd, score_bollinger, score_news,
)
from portfolio_assistant import (
    build_portfolio, calculate_risk_score, get_snaptrade_positions,
)
from stock_chart import build_candlestick_chart
from pullback_indicator import check_pullback_risk
st.set_page_config(page_title="Robinhood AI", page_icon="📈", layout="wide")
theme = st.sidebar.radio("Theme", ["Dark", "Light"], horizontal=True)
from smart_alerts import check_ticker as check_alerts_for_ticker
from daily_briefing import (
    USER_NAME, get_market_overview, get_watchlist_highlights,
    get_top_news_story, get_highest_risk_ticker,
)
from jarvis import ask_jarvis
from athena import analyze_stock as athena_analyze_stock
from opportunity_hunter import UNIVERSE as HUNTER_UNIVERSE, scan_theme as hunter_scan_theme
from memory_agent import load_memory, update_profile, clear_notes, get_journal_insights
from mentor import ask_mentor, get_categories as mentor_categories, get_terms as mentor_terms
from wealth_builder import WEALTH_UNIVERSE, analyze_pick as wealth_analyze_pick, scan_universe as wealth_scan_universe
from database import storage
from sources.base_source import build_manual_item
from ticker_extractor import extract_tickers
from report_generator import build_report, build_general_impact_report, MARKET_TICKER
# ---------------- Dark theme styling ----------------
THEMES = {
    "Dark": {
        "bg": "#0A0A0D",
        "bg_image": "radial-gradient(circle at 15% 0%, rgba(215,255,61,0.05), transparent 40%)",
        "sidebar_bg": "#111116",
        "card_bg": "#17171C",
        "border": "#F5F5F0",
        "shadow": "#D7FF3D",
        "text": "#F5F5F0",
        "text_muted": "#9A9AA5",
        "positive": "#4ADE80",
        "negative": "#FB7185",
    },
    "Light": {
        "bg": "#7C5CFA",
        "bg_image": "none",
        "sidebar_bg": "#6947E8",
        "card_bg": "#FFFFFF",
        "border": "#0D0D0D",
        "shadow": "#0D0D0D",
        "text": "#0D0D0D",
        "text_muted": "#52525B",
        "positive": "#16A34A",
        "negative": "#E11D48",
    },
}

t = THEMES[theme]

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@700;800&family=IBM+Plex+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }}
    .stApp {{
        background-color: {t['bg']};
        background-image: {t['bg_image']};
        color: {t['text']};
    }}
    section[data-testid="stSidebar"] {{
        background-color: {t['sidebar_bg']};
        border-right: 3px solid {t['border']};
    }}
    .brand-header {{
        padding: 4px 4px 18px 4px;
        margin-bottom: 10px;
        border-bottom: 2px solid {t['text_muted']};
    }}
    .brand-header .brand-name {{
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 800;
        font-size: 22px;
        text-transform: uppercase;
        letter-spacing: -0.01em;
        color: {t['text']};
    }}
    .brand-header .brand-sub {{
        font-family: 'IBM Plex Mono', monospace;
        font-size: 10.5px;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: {t['text_muted']};
    }}
    section[data-testid="stSidebar"] div[data-testid="stRadio"] label {{
        display: block;
        padding: 9px 14px;
        margin-bottom: 4px;
        border-radius: 8px;
        border: 2px solid transparent;
        cursor: pointer;
        transition: background-color .12s ease, border-color .12s ease;
    }}
    section[data-testid="stSidebar"] div[data-testid="stRadio"] label > div:first-child {{
        display: none;
    }}
    section[data-testid="stSidebar"] div[data-testid="stRadio"] label p {{
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        letter-spacing: 0.02em;
        font-size: 12.5px !important;
        color: {t['text_muted']};
        margin: 0;
    }}
    section[data-testid="stSidebar"] div[data-testid="stRadio"] label:hover {{
        border-color: {t['text_muted']};
    }}
    section[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) {{
        background-color: {t['text']};
        border-color: {t['text']};
    }}
    section[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) p {{
        color: {t['sidebar_bg']} !important;
    }}
    .hero-headline {{
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 800;
        font-size: 34px;
        line-height: 1.05;
        text-transform: uppercase;
        letter-spacing: -0.01em;
        color: {t['text']};
        margin-bottom: 18px;
    }}
    .card-expand {{
        position: absolute;
        top: 12px; right: 14px;
        font-size: 13px;
        color: {t['text_muted']};
    }}
    .pill {{
        display: inline-block;
        padding: 3px 11px;
        border-radius: 999px;
        font-family: 'IBM Plex Mono', monospace;
        font-weight: 700;
        font-size: 12px;
        color: #FFFFFF;
    }}
    .pill-positive {{ background-color: {t['positive']}; }}
    .pill-negative {{ background-color: {t['negative']}; }}
    .pill-neutral {{ background-color: {t['text_muted']}; }}
    .stMarkdown h2, .stMarkdown h3 {{
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 800 !important;
        text-transform: uppercase;
        letter-spacing: -0.01em;
        color: {t['text']};
    }}
    .card {{
        position: relative;
        background-color: {t['card_bg']};
        border: 3px solid {t['border']};
        box-shadow: 6px 6px 0 {t['shadow']};
        border-radius: 6px;
        padding: 34px 20px 18px 20px;
        margin-bottom: 18px;
        color: {t['text']};
    }}
    .card::before {{
        content: "";
        position: absolute;
        top: 14px; left: 16px;
        width: 8px; height: 8px;
        border-radius: 50%;
        background: {t['border']};
        box-shadow: 16px 0 0 {t['border']}, 32px 0 0 {t['border']};
    }}
    .card-label {{
        color: {t['text_muted']};
        font-size: 12.5px;
        font-weight: 600;
        letter-spacing: 0.01em;
        margin-bottom: 4px;
    }}
    .card-value {{
        font-size: 22px;
        font-weight: 700;
        font-family: 'IBM Plex Mono', monospace;
        font-variant-numeric: tabular-nums;
        letter-spacing: -0.01em;
        color: {t['text']};
    }}
    .positive {{ color: {t['positive']}; }}
    .negative {{ color: {t['negative']}; }}
    .neutral {{ color: {t['text_muted']}; }}
    .banner {{
        background-color: {t['card_bg']};
        border: 3px solid {t['border']};
        box-shadow: 4px 4px 0 {t['shadow']};
        border-radius: 6px;
        padding: 16px 20px;
        font-size: 14.5px;
        line-height: 1.5;
        margin-bottom: 18px;
        color: {t['text']};
    }}
    .score-ring {{
        font-size: 28px;
        font-weight: 800;
        font-family: 'IBM Plex Mono', monospace;
    }}
    .ticker-wrap {{
        width: 100%;
        overflow: hidden;
        border-radius: 4px;
        padding: 10px 0;
        margin-bottom: 22px;
        white-space: nowrap;
        background-color: #D7FF3D;
        border-top: 3px solid #0D0D0D;
        border-bottom: 3px solid #0D0D0D;
    }}
    .ticker-move {{
        display: inline-block;
        padding-left: 100%;
        animation: ticker-scroll 40s linear infinite;
        font-family: 'IBM Plex Mono', monospace;
        font-weight: 700;
        font-size: 13px;
        letter-spacing: 0.02em;
        color: #0D0D0D;
    }}
    .ticker-move span {{
        margin-right: 36px;
    }}
    .ticker-move .positive {{ color: #0F7A34; }}
    .ticker-move .negative {{ color: #B0102D; }}
    @keyframes ticker-scroll {{
        0%   {{ transform: translateX(0); }}
        100% {{ transform: translateX(-100%); }}
    }}
    @media (prefers-reduced-motion: reduce) {{
        .ticker-move {{ animation: none; padding-left: 20px; }}
    }}
</style>
""", unsafe_allow_html=True)


def pct_class(value: float) -> str:
    if value > 0:
        return "positive"
    elif value < 0:
        return "negative"
    return "neutral"


def score_color(score: int) -> str:
    if score >= 70:
        return "positive"
    elif score >= 45:
        return "neutral"
    else:
        return "negative"


def confidence_color(score: int) -> str:
    if score >= 7:
        return "positive"
    elif score >= 4:
        return "neutral"
    else:
        return "negative"


def render_dashboard():
    st.markdown('<div class="hero-headline">Built for research.<br>Made for clarity.</div>', unsafe_allow_html=True)

    results = []
    for name, ticker in INDICES.items():
        result = get_index_data(name, ticker)
        if result:
            results.append(result)

    if not results:
        st.warning("Couldn't load market data right now.")
        return

    headline = next((r for r in results if r["name"] == "S&P 500"), results[0])
    sub_indices = [r for r in results if r["name"] != headline["name"]]

    vix_result = next((r for r in results if r["name"] == "VIX"), None)
    fear_greed = simplified_fear_greed(vix_result["price"]) if vix_result else "Unavailable"
    sentiment = overall_sentiment(results)
    sentiment_class = "positive" if "Bullish" in sentiment else "negative" if "Bearish" in sentiment else "neutral"

    hero_col, side_col = st.columns([2, 1])

    with hero_col:
        css_class = pct_class(headline["change_pct"])
        arrow = "▲" if headline["change_pct"] >= 0 else "▼"
        st.markdown(f"""
        <div class="card" style="padding-top:34px;">
            <span class="card-expand">⤢</span>
            <div class="card-label">MARKET OVERVIEW &mdash; {headline['name']}</div>
            <div style="font-size:40px; font-weight:800; font-family:'IBM Plex Mono', monospace; margin:6px 0 10px 0;">
                ${headline['price']:,.2f}
            </div>
            <span class="pill pill-{css_class}">{arrow} {headline['change_pct']:+.2f}%</span>
        </div>
        """, unsafe_allow_html=True)

    with side_col:
        st.markdown(f"""
        <div class="card" style="padding-top:34px;">
            <div class="card-label">SENTIMENT</div>
            <span class="pill pill-{sentiment_class}" style="font-size:11px;">{sentiment.split('—')[0].strip().upper()}</span>
            <div class="card-label" style="margin-top:14px;">FEAR / GREED</div>
            <div style="font-size:14px; font-weight:600;">{fear_greed}</div>
        </div>
        """, unsafe_allow_html=True)

    sub_cols = st.columns(len(sub_indices)) if sub_indices else []
    for col, r in zip(sub_cols, sub_indices):
        arrow = "▲" if r["change_pct"] >= 0 else "▼"
        css_class = pct_class(r["change_pct"])
        col.markdown(f"""
        <div class="card">
            <div class="card-label">{r['name']}</div>
            <div class="card-value">${r['price']:,.2f}</div>
            <span class="pill pill-{css_class}">{arrow} {r['change_pct']:+.2f}%</span>
        </div>
        """, unsafe_allow_html=True)

    if "dashboard_spotlight_ticker" not in st.session_state:
        try:
            holdings = get_snaptrade_positions()
        except Exception:
            holdings = []
        tickers = [h["ticker"] for h in holdings] or WATCHLIST
        st.session_state.dashboard_spotlight_ticker = random.choice(tickers)

    spotlight_ticker = st.session_state.dashboard_spotlight_ticker

    @st.fragment(run_every="60s")
    def render_spotlight():
        st.markdown('<div class="card-label" style="margin-top:24px;">FEATURED HOLDING</div>', unsafe_allow_html=True)
        spotlight_history = yf.Ticker(spotlight_ticker).history(period="5d", interval="15m")
        if spotlight_history.empty:
            st.warning(f"Couldn't load chart data for {spotlight_ticker}.")
            return
        fig = build_candlestick_chart(spotlight_ticker, spotlight_history, t, theme, show_bollinger=False)
        st.plotly_chart(fig, width="stretch", key=f"dashboard_chart_{spotlight_ticker}")

    render_spotlight()


def render_watchlist():
    st.markdown('<div class="hero-headline">Your Watchlist.</div>', unsafe_allow_html=True)

    with st.spinner("Loading watchlist data..."):
        stock_data = [d for d in (get_stock_data(ticker) for ticker in WATCHLIST) if d]

    for i in range(0, len(stock_data), 2):
        cols = st.columns(2)
        for col, data in zip(cols, stock_data[i:i + 2]):
            daily_class = pct_class(data["daily_pct"] or 0)
            weekly_class = pct_class(data["weekly_pct"] or 0)
            monthly_class = pct_class(data["monthly_pct"] or 0)

            daily_str = f"{data['daily_pct']:+.2f}%" if data["daily_pct"] is not None else "N/A"
            weekly_str = f"{data['weekly_pct']:+.2f}%" if data["weekly_pct"] is not None else "N/A"
            monthly_str = f"{data['monthly_pct']:+.2f}%" if data["monthly_pct"] is not None else "N/A"

            col.markdown(f"""
            <div class="card">
                <div class="card-value">{data['ticker']}</div>
                <div class="card-label">${data['price']:.2f}</div>
                <div style="margin-top:12px; display:flex; gap:6px; flex-wrap:wrap;">
                    <span class="pill pill-{daily_class}">D {daily_str}</span>
                    <span class="pill pill-{weekly_class}">W {weekly_str}</span>
                    <span class="pill pill-{monthly_class}">M {monthly_str}</span>
                </div>
                <div class="card-label" style="margin-top:10px;">
                    Volume: {data['volume']:,.0f} &nbsp;|&nbsp; Market Cap: {format_market_cap(data['market_cap'])}
                </div>
            </div>
            """, unsafe_allow_html=True)


def render_technical_analysis():
    st.markdown('<div class="hero-headline">Read the chart.</div>', unsafe_allow_html=True)

    ticker = st.selectbox("Choose a stock", WATCHLIST)

    @st.fragment(run_every="60s")
    def render_technical_analysis_content(ticker: str):
        with st.spinner(f"Analyzing {ticker}..."):
            stock = yf.Ticker(ticker)
            history = stock.history(period="6mo")

            if history.empty or len(history) < 50:
                st.warning(f"Not enough data to analyze {ticker}.")
                return

            closes = history["Close"]
            latest_price = closes.iloc[-1]
            sma_20 = calculate_sma(closes, 20).iloc[-1]
            sma_50 = calculate_sma(closes, 50).iloc[-1]
            rsi = calculate_rsi(closes).iloc[-1]
            macd_line, signal_line = calculate_macd(closes)
            upper_band, mid_band, lower_band = calculate_bollinger_bands(closes)
            support, resistance = calculate_support_resistance(history)

        if latest_price > sma_20 > sma_50:
            trend_class, trend_label = "positive", "UPTREND"
        elif latest_price < sma_20 < sma_50:
            trend_class, trend_label = "negative", "DOWNTREND"
        else:
            trend_class, trend_label = "neutral", "MIXED"

        hero_col, stat_col = st.columns([2, 1])
        with hero_col:
            st.markdown(f"""
            <div class="card" style="padding-top:34px;">
                <span class="card-expand">⤢</span>
                <div class="card-label">{ticker} &mdash; CURRENT PRICE</div>
                <div style="font-size:40px; font-weight:800; font-family:'IBM Plex Mono', monospace; margin:6px 0 10px 0;">
                    ${latest_price:.2f}
                </div>
                <span class="pill pill-{trend_class}">{trend_label}</span>
            </div>
            """, unsafe_allow_html=True)
        with stat_col:
            st.markdown(f"""
            <div class="card" style="padding-top:34px;">
                <div class="card-label">SMA 20 / SMA 50</div>
                <div class="card-value" style="font-size:16px;">${sma_20:.2f} / ${sma_50:.2f}</div>
                <div class="card-label" style="margin-top:14px;">SUPPORT / RESISTANCE</div>
                <div class="card-value" style="font-size:16px;">${support:.2f} / ${resistance:.2f}</div>
            </div>
            """, unsafe_allow_html=True)

        fig = build_candlestick_chart(ticker, history, t, theme, show_bollinger=True)
        st.plotly_chart(fig, width="stretch", key=f"tech_chart_{ticker}")

        explanations = [
            interpret_trend(latest_price, sma_20, sma_50),
            interpret_rsi(rsi),
            interpret_macd(macd_line.iloc[-1], signal_line.iloc[-1]),
            interpret_bollinger(latest_price, upper_band.iloc[-1], lower_band.iloc[-1]),
        ]

        for explanation in explanations:
            st.markdown(f"""
            <div class="banner">{explanation}</div>
            """, unsafe_allow_html=True)

    render_technical_analysis_content(ticker)


def render_news():
    st.markdown('<div class="hero-headline">Know before it moves.</div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["Ticker Headlines", "Product / Launch News", "Market-Wide News"])

    with tab1:
        ticker = st.selectbox("Choose a stock", WATCHLIST, key="news_ticker")

        with st.spinner(f"Fetching news for {ticker}..."):
            articles = get_news(ticker, max_articles=8)

        if not articles:
            st.info("No recent articles found.")
        else:
            for article in articles:
                title = article.get("title", "No title")
                source = article.get("source", {}).get("name", "Unknown source")
                tag = rough_tag(title)

                if tag == "Possibly Positive":
                    tag_class = "positive"
                elif tag == "Possibly Negative":
                    tag_class = "negative"
                else:
                    tag_class = "neutral"

                st.markdown(f"""
                <div class="card">
                    <span class="pill pill-{tag_class}" style="font-size:10.5px;">{tag.upper()}</span>
                    <div style="font-size:15px; font-weight:500; margin-top:8px;">{title}</div>
                    <div class="card-label" style="margin-top:6px;">{source}</div>
                </div>
                """, unsafe_allow_html=True)

    with tab2:
        product_ticker = st.selectbox("Choose a stock", WATCHLIST, key="product_ticker")

        with st.spinner(f"Checking for product news on {product_ticker}..."):
            product_articles = get_product_news(product_ticker, max_articles=8)

        if not product_articles:
            st.info("No product-launch news found recently.")
        else:
            for article in product_articles:
                title = article.get("title", "No title")
                source = article.get("source", {}).get("name", "Unknown source")
                st.markdown(f"""
                <div class="card">
                    <div style="font-size:15px; font-weight:500;">📦 {title}</div>
                    <div class="card-label" style="margin-top:6px;">{source}</div>
                </div>
                """, unsafe_allow_html=True)

    with tab3:
        with st.spinner("Fetching market-wide news..."):
            market_articles = get_market_wide_news()

        if not market_articles:
            st.info("No market-wide news found.")
        else:
            for article in market_articles:
                title = article.get("title", "No title")
                source = article.get("source", {}).get("name", "Unknown source")
                tag = rough_tag(title)
                mentions = flag_watchlist_mentions(title)

                if tag == "Possibly Positive":
                    tag_class = "positive"
                elif tag == "Possibly Negative":
                    tag_class = "negative"
                else:
                    tag_class = "neutral"

                mention_html = ""
                if mentions:
                    mention_html = f'<div style="margin-top:6px;"><span class="pill pill-negative" style="font-size:10.5px;">⚠️ {", ".join(mentions)}</span></div>'

                st.markdown(f"""
                <div class="card">
                    <span class="pill pill-{tag_class}" style="font-size:10.5px;">{tag.upper()}</span>
                    <div style="font-size:15px; font-weight:500; margin-top:8px;">{title}</div>
                    <div class="card-label" style="margin-top:6px;">{source}</div>
                    {mention_html}
                </div>
                """, unsafe_allow_html=True)


def render_stock_ratings():
    st.markdown('<div class="hero-headline">Score every stock.</div>', unsafe_allow_html=True)

    with st.spinner("Scoring your watchlist..."):
        cols = None
        slot = 0
        for ticker in WATCHLIST:
            stock = yf.Ticker(ticker)
            history = stock.history(period="6mo")
            if history.empty or len(history) < 50:
                continue

            closes = history["Close"]
            latest_price = closes.iloc[-1]
            sma_20 = calculate_sma(closes, 20).iloc[-1]
            sma_50 = calculate_sma(closes, 50).iloc[-1]
            rsi = calculate_rsi(closes).iloc[-1]
            macd_line, signal_line = calculate_macd(closes)
            upper_band, mid_band, lower_band = calculate_bollinger_bands(closes)

            trend_points, trend_note = score_trend(latest_price, sma_20, sma_50)
            rsi_points, rsi_note = score_rsi(rsi)
            macd_points, macd_note = score_macd(macd_line.iloc[-1], signal_line.iloc[-1])
            boll_points, boll_note = score_bollinger(latest_price, upper_band.iloc[-1], lower_band.iloc[-1])
            news_points, news_note = score_news(ticker)

            total = trend_points + rsi_points + macd_points + boll_points + news_points
            color = score_color(total)

            if slot % 2 == 0:
                cols = st.columns(2)
            target = cols[slot % 2]
            slot += 1

            target.markdown(f"""
            <div class="card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div class="card-value">{ticker}</div>
                    <div class="score-ring {color}">{total}/100</div>
                </div>
                <div class="card-label" style="margin-top:10px;">Trend: {trend_points}/25 — {trend_note}</div>
                <div class="card-label">RSI: {rsi_points}/20 — {rsi_note}</div>
                <div class="card-label">MACD: {macd_points}/20 — {macd_note}</div>
                <div class="card-label">Bollinger: {boll_points}/15 — {boll_note}</div>
                <div class="card-label">News tone: {news_points}/20 — {news_note}</div>
            </div>
            """, unsafe_allow_html=True)


def render_portfolio():
    st.markdown('<div class="hero-headline">Your money, mapped.</div>', unsafe_allow_html=True)

    with st.spinner("Loading your portfolio..."):
        portfolio = build_portfolio()

    if not portfolio:
        st.warning("No holdings data available. Check that the SnapTrade CLI is installed and connected.")
        return

    total_value = sum(h["current_value"] for h in portfolio)
    total_cost = sum(h["cost_value"] for h in portfolio)
    total_daily_gain_loss = sum(h["daily_gain_loss"] for h in portfolio)
    total_gain_loss = total_value - total_cost
    total_gain_loss_pct = (total_gain_loss / total_cost * 100) if total_cost else 0

    daily_class = pct_class(total_daily_gain_loss)
    total_class = pct_class(total_gain_loss)
    daily_arrow = "▲" if total_daily_gain_loss >= 0 else "▼"
    total_arrow = "▲" if total_gain_loss >= 0 else "▼"

    col1, col2, col3 = st.columns(3)
    col1.markdown(f"""
    <div class="card">
        <div class="card-label">Total Value</div>
        <div class="card-value">${total_value:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)
    col2.markdown(f"""
    <div class="card">
        <div class="card-label">Today's Gain/Loss</div>
        <div class="card-value">${total_daily_gain_loss:,.2f}</div>
        <span class="pill pill-{daily_class}" style="margin-top:8px; display:inline-block;">{daily_arrow} ${abs(total_daily_gain_loss):,.2f}</span>
    </div>
    """, unsafe_allow_html=True)
    col3.markdown(f"""
    <div class="card">
        <div class="card-label">Total Gain/Loss</div>
        <div class="card-value">${total_gain_loss:,.2f}</div>
        <span class="pill pill-{total_class}" style="margin-top:8px; display:inline-block;">{total_arrow} {total_gain_loss_pct:+.2f}%</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### Holdings")
    for h in portfolio:
        gain_class = pct_class(h["total_gain_loss"])
        arrow = "▲" if h["total_gain_loss"] >= 0 else "▼"
        st.markdown(f"""
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <div class="card-value">{h['ticker']}</div>
                    <div class="card-label">{h['shares']} shares @ ${h['current_price']:.2f} — {h['sector']}</div>
                </div>
                <span class="pill pill-{gain_class}">{arrow} {h['total_gain_loss_pct']:+.1f}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    sector_totals = {}
    for h in portfolio:
        sector_totals[h["sector"]] = sector_totals.get(h["sector"], 0) + h["current_value"]

    st.markdown("#### Sector Allocation")
    for sector, value in sorted(sector_totals.items(), key=lambda x: x[1], reverse=True):
        pct = (value / total_value * 100) if total_value else 0
        st.markdown(f"""
        <div class="banner">{sector}: {pct:.1f}% (${value:,.2f})</div>
        """, unsafe_allow_html=True)

    sorted_by_pct = sorted(portfolio, key=lambda h: h["total_gain_loss_pct"], reverse=True)
    best = sorted_by_pct[0]
    worst = sorted_by_pct[-1]

    st.markdown("#### Best / Worst Performers")
    st.markdown(f"""
    <div class="banner">
        <b>Best:</b> {best['ticker']} {best['total_gain_loss_pct']:+.2f}%<br>
        <b>Worst:</b> {worst['ticker']} {worst['total_gain_loss_pct']:+.2f}%
    </div>
    """, unsafe_allow_html=True)

    risk_score, notes = calculate_risk_score(portfolio, sector_totals, total_value)
    st.markdown("#### Portfolio Risk Score")
    st.markdown(f"""
    <div class="banner">
        <div class="score-ring {score_color(100 - risk_score)}">{risk_score}/100</div>
        <div class="card-label">(higher = more risk)</div>
        {"<br>".join(notes)}
    </div>
    """, unsafe_allow_html=True)
def render_pullback_indicator():
    st.markdown('<div class="hero-headline">Spot the stretch.</div>', unsafe_allow_html=True)
    st.caption("Pattern-based, not a prediction — shows how many warning signs are stacking up.")

    risk_colors = {"HIGH": "negative", "MODERATE": "neutral", "LOW": "positive"}
    risk_icons = {"HIGH": "🔴", "MODERATE": "🟡", "LOW": "🟢"}

    with st.spinner("Scanning your watchlist for pullback signals..."):
        results = []
        for ticker in WATCHLIST:
            result = check_pullback_risk(ticker)
            if result:
                results.append(result)

    results.sort(key=lambda r: r["signal_count"], reverse=True)

    flagged = [r for r in results if r["risk_level"] != "NONE"]
    quiet = [r for r in results if r["risk_level"] == "NONE"]

    if not flagged:
        st.markdown('<div class="banner">No pullback signals detected across your watchlist right now.</div>', unsafe_allow_html=True)
    else:
        for r in flagged:
            color = risk_colors[r["risk_level"]]
            icon = risk_icons[r["risk_level"]]
            signals_html = "<br>".join(f"— {s}" for s in r["signals"])
            st.markdown(f"""
            <div class="card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div class="card-value">{icon} {r['ticker']}</div>
                    <span class="pill pill-{color}">{r['risk_level']} ({r['signal_count']}/4)</span>
                </div>
                <div class="card-label" style="margin-top:8px;">{signals_html}</div>
            </div>
            """, unsafe_allow_html=True)

    if quiet:
        quiet_tickers = ", ".join(r["ticker"] for r in quiet)
        st.markdown(f'<div class="card-label" style="margin-top:10px;">No signals: {quiet_tickers}</div>', unsafe_allow_html=True)
def render_smart_alerts():
    st.markdown('<div class="hero-headline">Nothing slips by.</div>', unsafe_allow_html=True)
    st.caption("Large moves, volume spikes, RSI extremes, and moving average crossovers across your watchlist.")

    with st.spinner("Scanning your watchlist for alerts..."):
        any_alerts = False
        for ticker in WATCHLIST:
            alerts = check_alerts_for_ticker(ticker)
            if alerts:
                any_alerts = True
                alerts_html = "<br>".join(f"⚠️ {a}" for a in alerts)
                st.markdown(f"""
                <div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div class="card-value">{ticker}</div>
                        <span class="pill pill-neutral">{len(alerts)} ALERT{'S' if len(alerts) != 1 else ''}</span>
                    </div>
                    <div class="card-label" style="margin-top:8px;">{alerts_html}</div>
                </div>
                """, unsafe_allow_html=True)

    if not any_alerts:
        st.markdown('<div class="banner">No alerts triggered right now — nothing crossed a threshold.</div>', unsafe_allow_html=True)


def render_daily_briefing():
    st.markdown(f'<div class="hero-headline">Good morning,<br>{USER_NAME}.</div>', unsafe_allow_html=True)

    with st.spinner("Putting together your briefing..."):
        fear_greed, sentiment = get_market_overview()
        highlights = get_watchlist_highlights()
        top_story = get_top_news_story()
        highest_risk = get_highest_risk_ticker()

    sentiment_class = "positive" if "Bullish" in sentiment else "negative" if "Bearish" in sentiment else "neutral"

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
        <div class="card" style="padding-top:34px;">
            <div class="card-label">SENTIMENT</div>
            <span class="pill pill-{sentiment_class}">{sentiment.split('—')[0].strip().upper()}</span>
            <div class="card-label" style="margin-top:14px;">FEAR / GREED</div>
            <div style="font-size:14px; font-weight:600;">{fear_greed}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="card" style="padding-top:34px;">
            <div class="card-label">HIGHEST RISK TODAY</div>
            <div class="card-value">{highest_risk if highest_risk else "Not enough data"}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("#### Watchlist Highlights")
    if highlights:
        for i in range(0, len(highlights), 2):
            cols = st.columns(2)
            for col, (ticker, note) in zip(cols, highlights[i:i + 2]):
                col.markdown(f"""
                <div class="card">
                    <div class="card-value">{ticker}</div>
                    <div class="card-label">{note}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="card-label">Nothing notable today.</div>', unsafe_allow_html=True)

    st.markdown("#### Today's News")
    st.markdown(f'<div class="banner">{top_story if top_story else "No recent headlines found."}</div>', unsafe_allow_html=True)
def render_jarvis_tab():
    st.caption("Ask about a stock, your portfolio, or today's market.")

    if "jarvis_history" not in st.session_state:
        st.session_state.jarvis_history = []
    if "jarvis_display" not in st.session_state:
        st.session_state.jarvis_display = []

    for role, text in st.session_state.jarvis_display:
        with st.chat_message(role):
            st.markdown(text)

    prompt = st.chat_input("Ask Jarvis anything...")
    if prompt:
        st.session_state.jarvis_display.append(("user", prompt))
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    reply, updated_history = ask_jarvis(prompt, st.session_state.jarvis_history)
                except Exception as e:
                    reply, updated_history = f"Something went wrong talking to Jarvis: {e}", st.session_state.jarvis_history
            st.markdown(reply)

        st.session_state.jarvis_history = updated_history
        st.session_state.jarvis_display.append(("assistant", reply))


def render_athena_tab():
    st.caption("Fundamental analysis: valuation, growth, profitability, and financial health — with the bull and bear case.")

    ticker = st.selectbox("Choose a stock", WATCHLIST, key="athena_ticker")

    with st.spinner(f"Analyzing {ticker}'s fundamentals..."):
        result = athena_analyze_stock(ticker)

    if not result:
        st.warning(f"Couldn't find fundamental data for {ticker}.")
        return

    f = result["fundamentals"]
    score = result["confidence_score"]
    color = score_color(score)
    pe_str = f"{f['trailing_pe']:.1f}" if f["trailing_pe"] else "N/A"

    hero_col, side_col = st.columns([2, 1])
    with hero_col:
        st.markdown(f"""
        <div class="card" style="padding-top:34px;">
            <span class="card-expand">⤢</span>
            <div class="card-label">{f['name']} ({ticker}) &mdash; CONFIDENCE SCORE</div>
            <div style="font-size:40px; font-weight:800; font-family:'IBM Plex Mono', monospace; margin:6px 0 10px 0;">
                {score}/100
            </div>
            <span class="pill pill-{color}">{f['sector']}</span>
        </div>
        """, unsafe_allow_html=True)
    with side_col:
        st.markdown(f"""
        <div class="card" style="padding-top:34px;">
            <div class="card-label">P/E (TRAILING)</div>
            <div class="card-value" style="font-size:16px;">{pe_str}</div>
            <div class="card-label" style="margin-top:14px;">MARKET CAP</div>
            <div class="card-value" style="font-size:16px;">{format_market_cap(f['market_cap'])}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("#### Score Breakdown")
    for label, note in result["score_breakdown"].items():
        st.markdown(f'<div class="card-label" style="margin-bottom:6px;"><b>{label}:</b> {note}</div>', unsafe_allow_html=True)

    bull_col, bear_col = st.columns(2)
    with bull_col:
        bull_html = "<br>".join(f"🟢 {b}" for b in result["bull_case"])
        st.markdown(f'<div class="banner"><b>Bull Case</b><br><br>{bull_html}</div>', unsafe_allow_html=True)
    with bear_col:
        bear_html = "<br>".join(f"🔴 {b}" for b in result["bear_case"])
        st.markdown(f'<div class="banner"><b>Bear Case</b><br><br>{bear_html}</div>', unsafe_allow_html=True)


def render_opportunity_hunter_tab():
    st.caption("Scans a curated universe of stocks by theme for breakouts, volume spikes, and strong "
               "fundamentals. Not a recommendation — always do your own research.")

    theme = st.selectbox("Choose a theme to scan", list(HUNTER_UNIVERSE.keys()), key="hunter_theme")

    with st.spinner(f"Scanning {theme}..."):
        results = hunter_scan_theme(theme)

    if not results:
        st.warning("Couldn't load data for this theme right now.")
        return

    for r in results:
        color = score_color(r["confidence_score"]) if r["confidence_score"] is not None else "neutral"
        score_str = f"{r['confidence_score']}/100" if r["confidence_score"] is not None else "N/A"
        pct_str = f"{r['daily_pct']:+.2f}%" if r["daily_pct"] is not None else "N/A"
        signals_html = "<br>".join(f"⚡ {s}" for s in r["signals"]) if r["signals"] else "No active technical signals right now."
        penny_badge = ' <span class="pill pill-negative" style="font-size:10px;">SPECULATIVE</span>' if r["is_penny_stock"] else ""

        st.markdown(f"""
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div class="card-value">{r['ticker']}{penny_badge}</div>
                <span class="pill pill-{color}">{score_str}</span>
            </div>
            <div class="card-label" style="margin-top:6px;">${r['price']:.2f} ({pct_str})</div>
            <div class="card-label" style="margin-top:8px;">{signals_html}</div>
        </div>
        """, unsafe_allow_html=True)


def render_wealth_builder_tab():
    st.caption("Long-term research on quality companies, dividend payers, and popular ETFs/index funds. "
               "Not a recommendation — always do your own research.")

    browse_tab, deep_dive_tab = st.tabs(["🗂️ Browse Universe", "🔍 Deep Dive"])

    with browse_tab:
        category = st.selectbox("Choose a category to scan", list(WEALTH_UNIVERSE.keys()), key="wealth_category")

        with st.spinner(f"Scanning {category}..."):
            results = wealth_scan_universe(category)

        if not results:
            st.warning("Couldn't load data for this category right now.")
        else:
            for r in results:
                f = r["fundamentals"]
                color = score_color(r["quality_score"])
                sub_label = f.get("sector") if f["asset_type"] == "Stock" else f.get("category")

                st.markdown(f"""
                <div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div class="card-value">{f['ticker']} <span class="pill pill-neutral" style="font-size:10px;">{f['asset_type'].upper()}</span></div>
                        <span class="pill pill-{color}">{r['quality_score']}/100</span>
                    </div>
                    <div class="card-label" style="margin-top:6px;">{sub_label}</div>
                    <div class="card-label" style="margin-top:8px;">{r['thesis_note']}</div>
                </div>
                """, unsafe_allow_html=True)

    with deep_dive_tab:
        all_tickers = [t for tickers in WEALTH_UNIVERSE.values() for t in tickers]
        ticker = st.selectbox("Choose a pick", all_tickers, key="wealth_ticker")

        with st.spinner(f"Analyzing {ticker}..."):
            result = wealth_analyze_pick(ticker)

        if not result:
            st.warning(f"Couldn't find data for {ticker}.")
        else:
            f = result["fundamentals"]
            color = score_color(result["quality_score"])
            second_stat_label = "MARKET CAP" if f["asset_type"] == "Stock" else "TOTAL ASSETS"
            second_stat_value = format_market_cap(f.get("market_cap") or f.get("total_assets"))
            yield_str = f"{f['dividend_yield']:.2f}%" if f.get("dividend_yield") else "N/A"

            hero_col, side_col = st.columns([2, 1])
            with hero_col:
                st.markdown(f"""
                <div class="card" style="padding-top:34px;">
                    <span class="card-expand">⤢</span>
                    <div class="card-label">{f['name']} ({ticker}) &mdash; QUALITY SCORE</div>
                    <div style="font-size:40px; font-weight:800; font-family:'IBM Plex Mono', monospace; margin:6px 0 10px 0;">
                        {result['quality_score']}/100
                    </div>
                    <span class="pill pill-{color}">{f['asset_type'].upper()}</span>
                </div>
                """, unsafe_allow_html=True)
            with side_col:
                st.markdown(f"""
                <div class="card" style="padding-top:34px;">
                    <div class="card-label">DIVIDEND YIELD</div>
                    <div class="card-value" style="font-size:16px;">{yield_str}</div>
                    <div class="card-label" style="margin-top:14px;">{second_stat_label}</div>
                    <div class="card-value" style="font-size:16px;">{second_stat_value}</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("#### Score Breakdown")
            for label, note in result["score_breakdown"].items():
                st.markdown(f'<div class="card-label" style="margin-bottom:6px;"><b>{label}:</b> {note}</div>', unsafe_allow_html=True)

            st.markdown(f'<div class="banner">{result["thesis_note"]}</div>', unsafe_allow_html=True)

            opp_col, risk_col = st.columns(2)
            with opp_col:
                opp_html = "<br>".join(f"🟢 {o}" for o in result["opportunities"])
                st.markdown(f'<div class="banner"><b>Opportunities</b><br><br>{opp_html}</div>', unsafe_allow_html=True)
            with risk_col:
                risk_html = "<br>".join(f"🔴 {r}" for r in result["risks"])
                st.markdown(f'<div class="banner"><b>Risks</b><br><br>{risk_html}</div>', unsafe_allow_html=True)


VERDICT_PILL_CLASS = {
    "Confirmed": "positive",
    "Partially Confirmed": "neutral",
    "Not Supported": "negative",
}


MANUAL_ENTRY_SOURCES = ["tiktok", "youtube", "reddit", "news", "other"]


def render_manual_entry_form():
    with st.expander("➕ Manually analyze a post/video"):
        st.caption("For sources without live monitoring yet (TikTok, YouTube, Reddit...) — paste in a "
                   "caption, description, or transcript and it runs through the same analysis pipeline "
                   "as everything else.")
        manual_source = st.selectbox("Source", MANUAL_ENTRY_SOURCES, key="manual_source")
        manual_author = st.text_input("Creator / author (optional)", key="manual_author")
        manual_url = st.text_input("URL (optional)", key="manual_url")
        manual_content = st.text_area("Caption, description, or transcript", key="manual_content", height=120)

        if st.button("Analyze", key="manual_analyze_btn"):
            if not manual_content.strip():
                st.warning("Paste in some text to analyze.")
                return

            item = build_manual_item(manual_source, manual_author, manual_content, manual_url or None)
            tickers = extract_tickers(item.content)
            item_id = storage.save_source_item(item)

            if not tickers:
                with st.spinner("No specific ticker mentioned — fact-checking the claim and checking "
                                 "impact on your watchlist/portfolio..."):
                    try:
                        report = build_general_impact_report(item)
                        storage.save_analysis(item_id, report)
                        st.success("Analyzed as a general market claim (no specific ticker mentioned).")
                    except Exception as e:
                        st.error(f"Failed to analyze: {e}")
                st.rerun()
                return

            with st.spinner(f"Analyzing {', '.join(tickers)}..."):
                for ticker in tickers:
                    try:
                        report = build_report(ticker, item)
                        storage.save_analysis(item_id, report)
                    except Exception as e:
                        st.error(f"Failed to analyze {ticker}: {e}")

            st.success(f"Analyzed {len(tickers)} ticker(s): {', '.join(tickers)}")
            st.rerun()


def render_content_signals_tab():
    st.caption("Stock mentions detected across watched sources — fact-checked, technically analyzed, and "
               "scored for confidence. Not a recommendation — always do your own research.")

    storage.init()
    render_manual_entry_form()

    recent_analyses = storage.get_recent_analyses(limit=200)

    if not recent_analyses:
        st.markdown(
            '<div class="card-label">No analyses yet — use the form above, or run '
            '<code>python main.py</code> in your terminal to start listening on Discord (requires a bot '
            'token in .env; see setup notes).</div>',
            unsafe_allow_html=True,
        )
        return

    total_count = len(recent_analyses)
    tickers_count = len({a["ticker"] for a in recent_analyses if a["ticker"]})
    avg_confidence = sum(a["confidence_score"] or 0 for a in recent_analyses) / total_count

    stat_cols = st.columns(3)
    stat_cols[0].markdown(f"""
    <div class="card"><div class="card-label">TOTAL ANALYSES</div><div class="card-value">{total_count}</div></div>
    """, unsafe_allow_html=True)
    stat_cols[1].markdown(f"""
    <div class="card"><div class="card-label">TICKERS DETECTED</div><div class="card-value">{tickers_count}</div></div>
    """, unsafe_allow_html=True)
    stat_cols[2].markdown(f"""
    <div class="card"><div class="card-label">AVG CONFIDENCE</div><div class="card-value">{avg_confidence:.1f}/10</div></div>
    """, unsafe_allow_html=True)

    search_col, ticker_col, verdict_col = st.columns(3)
    query = search_col.text_input("Search", key="signals_search")
    ticker_filter = ticker_col.selectbox("Ticker", ["All"] + storage.get_distinct_tickers(), key="signals_ticker_filter")
    verdict_filter = verdict_col.selectbox("Fact-check verdict", ["All"] + list(VERDICT_PILL_CLASS.keys()), key="signals_verdict_filter")

    results = storage.search_analyses(
        query=query,
        ticker=None if ticker_filter == "All" else ticker_filter,
        verdict=None if verdict_filter == "All" else verdict_filter,
        limit=100,
    )

    st.markdown("#### Analyses")
    if not results:
        st.markdown('<div class="card-label">No analyses match this filter.</div>', unsafe_allow_html=True)
    for a in results:
        conf_color = confidence_color(a["confidence_score"] or 0)
        verdict_color = VERDICT_PILL_CLASS.get(a["fact_check_verdict"], "neutral")
        news = json.loads(a["news_json"]) if a["news_json"] else []
        news_html = "<br>".join(f"— {n.get('title', '')}" for n in news[:3]) or "No recent headlines."
        is_market_wide = a["ticker"] == MARKET_TICKER
        ticker_label = "GENERAL / MARKET-WIDE" if is_market_wide else a["ticker"]
        summary_label = "Likely impact" if is_market_wide else "Technical"

        st.markdown(f"""
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
                <div class="card-value">{ticker_label} <span class="pill pill-neutral" style="font-size:10px;">{a['item_source'].upper()}</span></div>
                <div style="display:flex; gap:6px;">
                    <span class="pill pill-{verdict_color}">{a['fact_check_verdict']}</span>
                    <span class="pill pill-{conf_color}">{a['confidence_score']}/10</span>
                </div>
            </div>
            <div class="card-label" style="margin-top:10px;">"{a['item_content']}" &mdash; {a['item_author']}</div>
            <div class="card-label" style="margin-top:8px;"><b>Sentiment:</b> {a['sentiment']} — {a['sentiment_reasoning']}</div>
            <div class="card-label" style="margin-top:4px;"><b>Fact check:</b> {a['fact_check_explanation']}</div>
            <div class="card-label" style="margin-top:4px;"><b>{summary_label}:</b> {a['technical_summary']}</div>
            <div class="card-label" style="margin-top:8px;">{news_html}</div>
            <div class="banner" style="margin-top:10px; margin-bottom:0;">{a['reasoning']}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("#### Recent Source Items")
    st.caption("Every message seen, regardless of whether a ticker was detected — confirms the source is connected.")
    for item in storage.get_recent_items(limit=10):
        st.markdown(f"""
        <div class="card">
            <div class="card-label">{item['source'].upper()} &mdash; {item['author']}</div>
            <div style="margin-top:4px;">{item['content']}</div>
        </div>
        """, unsafe_allow_html=True)


MEMORY_RISK_OPTIONS = ["Not set", "Conservative", "Moderate", "Aggressive"]
MEMORY_STYLE_OPTIONS = ["Not set", "Value", "Growth", "Income / Dividend", "Index / Passive", "Active / Trading"]
MEMORY_SECTOR_OPTIONS = [
    "Technology", "Healthcare", "Financial Services", "Consumer Cyclical",
    "Consumer Defensive", "Energy", "Industrials", "Basic Materials",
    "Real Estate", "Utilities", "Communication Services",
]


def render_memory_tab():
    st.caption("What Jarvis remembers about you — set it directly here, or just tell Jarvis in chat.")

    memory = load_memory()

    with st.form("memory_profile_form"):
        risk_tolerance = st.selectbox(
            "Risk tolerance", MEMORY_RISK_OPTIONS,
            index=MEMORY_RISK_OPTIONS.index(memory["risk_tolerance"]) if memory["risk_tolerance"] in MEMORY_RISK_OPTIONS else 0,
        )
        investing_style = st.selectbox(
            "Investing style", MEMORY_STYLE_OPTIONS,
            index=MEMORY_STYLE_OPTIONS.index(memory["investing_style"]) if memory["investing_style"] in MEMORY_STYLE_OPTIONS else 0,
        )
        favorite_sectors = st.multiselect(
            "Favorite sectors", MEMORY_SECTOR_OPTIONS,
            default=[s for s in memory["favorite_sectors"] if s in MEMORY_SECTOR_OPTIONS],
        )
        favorite_companies_str = st.text_input(
            "Favorite companies (comma-separated tickers)",
            value=", ".join(memory["favorite_companies"]),
        )
        long_term_goals = st.text_area("Long-term goals", value=memory["long_term_goals"])

        submitted = st.form_submit_button("Save")
        if submitted:
            favorite_companies = [t.strip().upper() for t in favorite_companies_str.split(",") if t.strip()]
            update_profile(
                risk_tolerance=risk_tolerance,
                investing_style=investing_style,
                favorite_sectors=favorite_sectors,
                favorite_companies=favorite_companies,
                long_term_goals=long_term_goals,
            )
            st.success("Saved.")
            st.rerun()

    if memory["notes"]:
        st.markdown("#### Notes Jarvis Has Saved From Chat")
        notes_html = "<br>".join(
            f"— {n['note']} <span class='card-label'>({n['date']})</span>" for n in memory["notes"]
        )
        st.markdown(f'<div class="banner">{notes_html}</div>', unsafe_allow_html=True)
        if st.button("Clear saved notes"):
            clear_notes()
            st.rerun()

    insights = get_journal_insights()
    st.markdown("#### Insights From Your Trading Journal")
    if insights:
        st.markdown(f"""
        <div class="card">
            <div class="card-label">STRATEGY ADHERENCE</div>
            <div class="card-value">{insights['strategy_adherence_pct']}%</div>
            <div class="card-label" style="margin-top:6px;">Based on {insights['entry_count']} journal entries</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="card-label">No trading journal entries yet — run '
            '<code>python trading_journal.py</code> in your terminal to start logging trades.</div>',
            unsafe_allow_html=True,
        )


def render_mentor_tab():
    st.caption("Learn the concepts used across this app, explained in plain language.")

    glossary_tab, chat_tab = st.tabs(["📚 Glossary", "💬 Ask Mentor"])

    with glossary_tab:
        category = st.selectbox("Category", mentor_categories(), key="mentor_category")
        for term, info in mentor_terms(category).items():
            st.markdown(f"""
            <div class="card">
                <div class="card-value" style="font-size:17px;">{term}</div>
                <div class="card-label" style="margin-top:8px; font-size:13.5px; line-height:1.5;">{info['definition']}</div>
                <div class="banner" style="margin-top:10px; margin-bottom:0;"><b>Why it matters:</b> {info['why_it_matters']}</div>
            </div>
            """, unsafe_allow_html=True)

    with chat_tab:
        if "mentor_history" not in st.session_state:
            st.session_state.mentor_history = []
        if "mentor_display" not in st.session_state:
            st.session_state.mentor_display = []

        for role, text in st.session_state.mentor_display:
            with st.chat_message(role):
                st.markdown(text)

        prompt = st.chat_input("Ask Mentor to explain something...", key="mentor_chat_input")
        if prompt:
            st.session_state.mentor_display.append(("user", prompt))
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        reply, updated_history = ask_mentor(prompt, st.session_state.mentor_history)
                    except Exception as e:
                        reply, updated_history = f"Something went wrong talking to Mentor: {e}", st.session_state.mentor_history
                st.markdown(reply)

            st.session_state.mentor_history = updated_history
            st.session_state.mentor_display.append(("assistant", reply))


def render_cost_tracker_tab():
    st.caption("AI usage and estimated spend across every Claude-powered feature in this app.")

    storage.init()
    today_usage = storage.get_usage_today()

    st.markdown("#### AI Usage Today")
    total_requests = sum(r["requests"] for r in today_usage)
    total_tokens = sum(r["tokens"] for r in today_usage)
    total_cost = sum(r["cost"] for r in today_usage)

    stat_cols = st.columns(3)
    stat_cols[0].markdown(f"""
    <div class="card"><div class="card-label">REQUESTS</div><div class="card-value">{total_requests}</div></div>
    """, unsafe_allow_html=True)
    stat_cols[1].markdown(f"""
    <div class="card"><div class="card-label">TOKENS</div><div class="card-value">{total_tokens:,}</div></div>
    """, unsafe_allow_html=True)
    stat_cols[2].markdown(f"""
    <div class="card"><div class="card-label">ESTIMATED COST</div><div class="card-value">${total_cost:.2f}</div></div>
    """, unsafe_allow_html=True)

    if today_usage:
        for row in today_usage:
            st.markdown(f"""
            <div class="card">
                <div class="card-value">{row['agent']}</div>
                <div class="card-label" style="margin-top:6px;">{row['requests']} requests &nbsp;|&nbsp; {row['tokens']:,} tokens &nbsp;|&nbsp; ${row['cost']:.2f}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown('<div class="card-label">No AI usage recorded yet today.</div>', unsafe_allow_html=True)

    st.markdown("#### Monthly Summary")
    month_usage = storage.get_usage_this_month()
    if month_usage:
        total_requests_month = sum(r["requests"] for r in month_usage)
        total_cost_month = sum(r["cost"] for r in month_usage)
        most_used = max(month_usage, key=lambda r: r["requests"])
        most_expensive = max(month_usage, key=lambda r: r["cost"])

        m_cols = st.columns(2)
        m_cols[0].markdown(f"""
        <div class="card"><div class="card-label">MOST USED AGENT</div><div class="card-value">{most_used['agent']}</div></div>
        """, unsafe_allow_html=True)
        m_cols[1].markdown(f"""
        <div class="card"><div class="card-label">MOST EXPENSIVE AGENT</div><div class="card-value">{most_expensive['agent']}</div></div>
        """, unsafe_allow_html=True)

        st.markdown(
            f'<div class="banner">This month so far: {total_requests_month} requests, ${total_cost_month:.2f} total.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div class="card-label">No usage recorded yet this month.</div>', unsafe_allow_html=True)

    st.markdown("#### Daily History")
    history = storage.get_daily_usage_history(days=14)
    if history:
        for day in history:
            st.markdown(
                f'<div class="card-label" style="margin-bottom:6px;">{day["day"]} — '
                f'{day["requests"]} requests, {day["tokens"]:,} tokens, ${day["cost"]:.2f}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown('<div class="card-label">No history yet.</div>', unsafe_allow_html=True)


def render_ai_agents():
    st.markdown('<div class="hero-headline">AI Agents.</div>', unsafe_allow_html=True)
    st.caption("Educational only — not financial advice.")

    tab_jarvis, tab_athena, tab_hunter, tab_wealth, tab_signals, tab_memory, tab_mentor, tab_cost = st.tabs(
        ["💬 Jarvis — Chat", "📈 Athena — Fundamentals", "🔎 Opportunity Hunter — Scanner",
         "💎 Wealth Builder — Long-Term", "🗣️ Content Signals", "🧠 Memory — Profile", "📖 Mentor — Learn",
         "💰 Cost Tracker"]
    )

    with tab_jarvis:
        render_jarvis_tab()

    with tab_athena:
        render_athena_tab()

    with tab_hunter:
        render_opportunity_hunter_tab()

    with tab_wealth:
        render_wealth_builder_tab()

    with tab_signals:
        render_content_signals_tab()

    with tab_memory:
        render_memory_tab()

    with tab_mentor:
        render_mentor_tab()

    with tab_cost:
        render_cost_tracker_tab()


# ---------------- Sidebar navigation ----------------
st.sidebar.markdown("""
<div class="brand-header">
    <div class="brand-name">Robinhood AI</div>
    <div class="brand-sub">Investment Research</div>
</div>
""", unsafe_allow_html=True)
page = st.sidebar.radio(
    "Navigate",
    ["Market Dashboard", "Watchlist", "Technical Analysis", "News", "Stock Ratings",
     "Portfolio", "Pullback Indicator", "Smart Alerts", "Daily Briefing", "AI Agents"],
    label_visibility="collapsed",
)

if page == "Market Dashboard":
    render_dashboard()
elif page == "Watchlist":
    render_watchlist()
elif page == "Technical Analysis":
    render_technical_analysis()
elif page == "News":
    render_news()
elif page == "Stock Ratings":
    render_stock_ratings()
elif page == "Portfolio":
    render_portfolio()
elif page == "Pullback Indicator":
    render_pullback_indicator()
elif page == "Smart Alerts":
    render_smart_alerts()
elif page == "Daily Briefing":
    render_daily_briefing()
elif page == "AI Agents":
    render_ai_agents()