import pandas as pd
import plotly.graph_objects as go

from technical_analysis import calculate_sma, calculate_bollinger_bands

# Teal/orange candlestick colors, fixed across both themes (not theme-tied like the
# app's positive/negative pills) — a deliberate, distinctive chart identity requested
# to match a specific reference image, independent of Dark/Light mode.
CANDLE_COLORS = {"up": "#14B8A6", "down": "#F59E0B"}

# Blue/green SMA overlay lines — orange is now taken by down-candles, so this swaps out
# the old blue/orange pairing (which would clash) for blue/green, re-validated with the
# palette validator against both app surfaces (light #fcfcfb / dark #1a1a19, close to the
# app's actual #FFFFFF / #17171C card_bg): CVD ΔE 26.5 light / 27.3 dark, normal-vision ΔE
# 29.0 / 29.9, both ≥3:1 contrast.
OVERLAY_COLORS = {
    "Light": {"sma_fast": "#2a78d6", "sma_slow": "#008300"},
    "Dark": {"sma_fast": "#3987e5", "sma_slow": "#008300"},
}


def _hex_to_rgb(hex_color: str) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return f"{r},{g},{b}"


def build_candlestick_chart(
    ticker: str,
    history: pd.DataFrame,
    theme: dict,
    theme_name: str,
    sma_windows: tuple[int, int] = (20, 50),
    show_bollinger: bool = False,
) -> go.Figure:
    """Themed OHLC candlestick chart with SMA overlays (and optional Bollinger Bands).
    `history` is a yfinance OHLC DataFrame already fetched by the caller — this function
    makes no network calls of its own. `theme` is one of app.py's THEMES[theme_name] dicts."""
    colors = OVERLAY_COLORS[theme_name]
    closes = history["Close"]

    fig = go.Figure(data=[go.Candlestick(
        x=history.index, open=history["Open"], high=history["High"],
        low=history["Low"], close=history["Close"], name=ticker,
        increasing_line_color=CANDLE_COLORS["up"], decreasing_line_color=CANDLE_COLORS["down"],
        increasing_fillcolor=CANDLE_COLORS["up"], decreasing_fillcolor=CANDLE_COLORS["down"],
    )])

    fast, slow = sma_windows
    if len(closes) >= fast:
        fig.add_trace(go.Scatter(
            x=history.index, y=calculate_sma(closes, fast),
            name=f"SMA {fast}", line=dict(color=colors["sma_fast"], width=2),
        ))
    if len(closes) >= slow:
        fig.add_trace(go.Scatter(
            x=history.index, y=calculate_sma(closes, slow),
            name=f"SMA {slow}", line=dict(color=colors["sma_slow"], width=2),
        ))

    if show_bollinger and len(closes) >= 20:
        upper, _mid, lower = calculate_bollinger_bands(closes)
        band_rgb = _hex_to_rgb(theme["text_muted"])
        fig.add_trace(go.Scatter(
            x=history.index, y=upper, name="Bollinger Upper",
            line=dict(color=theme["text_muted"], width=1, dash="dot"), showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            x=history.index, y=lower, name="Bollinger Lower",
            line=dict(color=theme["text_muted"], width=1, dash="dot"),
            fill="tonexty", fillcolor=f"rgba({band_rgb},0.08)", showlegend=False,
        ))

    fig.update_layout(
        paper_bgcolor=theme["card_bg"], plot_bgcolor=theme["card_bg"],
        font=dict(color=theme["text"], family="IBM Plex Mono, monospace"),
        xaxis=dict(showgrid=False, rangeslider_visible=False),
        yaxis=dict(gridcolor=theme["text_muted"], gridwidth=0.5),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified", margin=dict(l=10, r=10, t=10, b=10), height=420,
    )
    return fig


def add_trade_markers(
    fig: go.Figure,
    theme: dict,
    history: pd.DataFrame,
    entry_date,
    entry_price: float,
    exit_date=None,
    exit_price: float | None = None,
    is_win: bool | None = None,
) -> go.Figure:
    """Marks exactly where a paper trade opened (and closed, if finished) on an
    existing candlestick figure. Snaps entry_date/exit_date to the nearest real candle
    in history.index rather than plotting the raw stored timestamp — our dates are
    stored as UTC isoformat strings while yfinance's index is exchange-local-tz, so a
    raw plot could land a few hours off; snapping to the nearest actual candle
    sidesteps that entirely and guarantees the marker always sits exactly on a real bar."""
    def _nearest(date):
        # Match by calendar date (in the exchange's own timezone), not raw timestamp
        # distance — daily candles are exactly 24h apart, so an afternoon timestamp is
        # numerically closer to the *next* day's midnight bar than the current day's,
        # which silently rounds the marker forward a day on raw-distance nearest-match.
        ts = pd.Timestamp(date)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        ts = ts.tz_convert(history.index.tz).normalize()
        index_dates = history.index.normalize()
        idx = index_dates.get_indexer([ts], method="nearest")[0]
        return history.index[idx]

    fig.add_trace(go.Scatter(
        x=[_nearest(entry_date)], y=[entry_price], mode="markers", name="Entry",
        marker=dict(symbol="triangle-up", size=14, color=theme["text"], line=dict(width=1, color=theme["card_bg"])),
    ))
    if exit_date is not None and exit_price is not None:
        exit_color = CANDLE_COLORS["up"] if is_win else CANDLE_COLORS["down"]
        fig.add_trace(go.Scatter(
            x=[_nearest(exit_date)], y=[exit_price], mode="markers", name="Exit",
            marker=dict(symbol="triangle-down", size=14, color=exit_color, line=dict(width=1, color=theme["card_bg"])),
        ))
    return fig
