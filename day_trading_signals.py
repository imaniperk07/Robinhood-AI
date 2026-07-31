import pandas as pd
import yfinance as yf

from technical_analysis import detect_candlestick_patterns


def get_intraday_history(ticker: str, interval: str = "5m") -> pd.DataFrame:
    """Today's (or the most recent session's, if the market is currently closed)
    intraday bars. The caller is responsible for checking whether the market is
    actually open — this just returns whatever yfinance has for the latest session."""
    return yf.Ticker(ticker).history(period="1d", interval=interval)


def get_opening_range(history: pd.DataFrame, minutes: int = 30) -> dict | None:
    """Opening Range Breakout signal: the high/low of the first N minutes of the
    session, and whether the current price has broken above or below it."""
    if history.empty:
        return None
    session_start = history.index[0]
    cutoff = session_start + pd.Timedelta(minutes=minutes)
    opening_bars = history[history.index <= cutoff]
    if opening_bars.empty:
        return None

    range_high = float(opening_bars["High"].max())
    range_low = float(opening_bars["Low"].min())
    current_price = float(history["Close"].iloc[-1])

    if current_price > range_high:
        breakout = "Above"
    elif current_price < range_low:
        breakout = "Below"
    else:
        breakout = "Inside"

    return {
        "range_high": round(range_high, 2), "range_low": round(range_low, 2),
        "current_price": round(current_price, 2), "breakout": breakout,
    }


def get_gap_info(ticker: str) -> dict | None:
    """Gap & Go / Gap Fade signal: today's open vs yesterday's close."""
    history = yf.Ticker(ticker).history(period="5d")
    if len(history) < 2:
        return None
    prev_close = float(history["Close"].iloc[-2])
    today_open = float(history["Open"].iloc[-1])
    if prev_close <= 0:
        return None
    gap_pct = (today_open - prev_close) / prev_close * 100
    direction = "Up" if gap_pct > 0.1 else "Down" if gap_pct < -0.1 else "Flat"
    return {"gap_pct": round(gap_pct, 2), "direction": direction}


def get_vwap_position(history: pd.DataFrame) -> dict | None:
    """VWAP Bounce/Rejection signal: session VWAP (volume-weighted average price)
    and whether price is currently above, below, or right at it."""
    if history.empty:
        return None
    typical_price = (history["High"] + history["Low"] + history["Close"]) / 3
    cum_vol = history["Volume"].cumsum()
    if cum_vol.iloc[-1] <= 0:
        return None
    vwap = (typical_price * history["Volume"]).cumsum() / cum_vol
    current_vwap = float(vwap.iloc[-1])
    current_price = float(history["Close"].iloc[-1])
    position = "Above" if current_price > current_vwap else "Below" if current_price < current_vwap else "At"
    return {"vwap": round(current_vwap, 2), "current_price": round(current_price, 2), "position": position}


def get_inside_bar_setup(daily_history: pd.DataFrame) -> dict | None:
    """Inside Bar Breakout signal: is today's daily range fully contained within
    yesterday's (the "mother bar")?"""
    if len(daily_history) < 2:
        return None
    today = daily_history.iloc[-1]
    yesterday = daily_history.iloc[-2]
    is_inside = bool(today["High"] <= yesterday["High"] and today["Low"] >= yesterday["Low"])
    return {
        "is_inside_bar": is_inside,
        "mother_bar_high": round(float(yesterday["High"]), 2),
        "mother_bar_low": round(float(yesterday["Low"]), 2),
    }


def get_flag_pattern(history: pd.DataFrame, pole_bars: int = 10, flag_bars: int = 5) -> dict | None:
    """Bull Flag Continuation signal, as a heuristic (not full geometric detection):
    a real directional move (the "pole") followed by a visible contraction in range
    (the "flag") relative to the pole. Returns None if there isn't a real pole move."""
    if len(history) < pole_bars + flag_bars:
        return None

    closes = history["Close"]
    pole_start = float(closes.iloc[-(pole_bars + flag_bars)])
    pole_end = float(closes.iloc[-flag_bars])
    if pole_start <= 0:
        return None
    pole_move_pct = (pole_end - pole_start) / pole_start * 100
    if abs(pole_move_pct) < 2.0:
        return None  # no real flagpole move, not a flag setup

    recent_range = (history["High"].iloc[-flag_bars:] - history["Low"].iloc[-flag_bars:]).mean()
    prior_range = (history["High"].iloc[-(pole_bars + flag_bars):-flag_bars]
                   - history["Low"].iloc[-(pole_bars + flag_bars):-flag_bars]).mean()
    consolidating = bool(prior_range > 0 and recent_range < prior_range * 0.7)

    return {
        "direction": "Bullish" if pole_move_pct > 0 else "Bearish",
        "pole_move_pct": round(pole_move_pct, 2),
        "consolidating": consolidating,
    }


def get_intraday_volume_signal(history: pd.DataFrame) -> dict | None:
    """Simplified intraday volume confirmation: the latest bar's volume against the
    average of the rest of today's session so far. Not normalized against a historical
    same-time-of-day baseline (that needs multi-day intraday alignment) — a simpler
    "is this bar unusual relative to today" proxy."""
    if len(history) < 5:
        return None
    latest_volume = float(history["Volume"].iloc[-1])
    avg_volume = float(history["Volume"].iloc[:-1].mean())
    if avg_volume <= 0:
        return None
    ratio = latest_volume / avg_volume
    return {"volume_ratio": round(ratio, 2), "elevated": bool(ratio >= 1.5)}


def get_intraday_candlestick_patterns(history: pd.DataFrame) -> list[dict]:
    """Reuses the same TA-Lib-backed detector used for daily bars — it's generic OHLC,
    not hardcoded to any interval."""
    if history.empty:
        return []
    return detect_candlestick_patterns(history)


if __name__ == "__main__":
    test_ticker = "AAPL"
    intraday = get_intraday_history(test_ticker)
    daily = yf.Ticker(test_ticker).history(period="1mo")
    print("Opening range:", get_opening_range(intraday))
    print("Gap info:", get_gap_info(test_ticker))
    print("VWAP position:", get_vwap_position(intraday))
    print("Inside bar:", get_inside_bar_setup(daily))
    print("Flag pattern:", get_flag_pattern(intraday))
    print("Volume signal:", get_intraday_volume_signal(intraday))
    print("Candlestick patterns:", get_intraday_candlestick_patterns(intraday))
