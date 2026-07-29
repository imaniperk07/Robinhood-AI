import pandas as pd
import plotly.graph_objects as go

from technical_analysis import calculate_sma, calculate_bollinger_bands

# Blue/orange — the dataviz palette's default categorical slots 1-2, validated with the
# palette validator against both app surfaces (light #fcfcfb / dark #1a1a19, close to the
# app's actual #FFFFFF / #17171C card_bg): CVD ΔE 24.7 light / 26.8 dark, normal-vision ΔE
# 33.6 / 31.8, both ≥3:1 contrast. Candle up/down colors reuse the app's own THEMES
# positive/negative instead of adding a third pair here.
OVERLAY_COLORS = {
    "Light": {"sma_fast": "#2a78d6", "sma_slow": "#eb6834"},
    "Dark": {"sma_fast": "#3987e5", "sma_slow": "#d95926"},
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
        increasing_line_color=theme["positive"], decreasing_line_color=theme["negative"],
        increasing_fillcolor=theme["positive"], decreasing_fillcolor=theme["negative"],
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
