import os

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

load_dotenv()

_client = None


def get_client() -> TradingClient | None:
    """None if ALPACA_API_KEY/ALPACA_SECRET_KEY aren't set — lets this feature ship
    now and silently no-op until the user actually signs up for a free Alpaca
    account, rather than requiring the keys to exist before anything else works."""
    global _client
    if _client is not None:
        return _client
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        return None
    _client = TradingClient(api_key, secret_key, paper=True)
    return _client


def mirror_open_trade(ticker: str, shares: float) -> None:
    """Best-effort mirror of a locally-opened paper trade onto Alpaca's free paper
    account, purely so it shows up in Alpaca's visual dashboard. Never raises — our
    own Storage stays the source of truth regardless of whether this succeeds."""
    client = get_client()
    if client is None:
        return
    try:
        order = MarketOrderRequest(symbol=ticker, qty=shares, side=OrderSide.BUY, time_in_force=TimeInForce.DAY)
        client.submit_order(order_data=order)
    except Exception as e:
        print(f"Alpaca mirror (open) failed for {ticker}: {e}")


def mirror_close_trade(ticker: str) -> None:
    """Best-effort mirror of a locally-closed paper trade. Never raises."""
    client = get_client()
    if client is None:
        return
    try:
        client.close_position(ticker)
    except Exception as e:
        print(f"Alpaca mirror (close) failed for {ticker}: {e}")


def is_mirror_active() -> bool:
    """True only if ALPACA_API_KEY/ALPACA_SECRET_KEY are actually set — a cheap,
    side-effect-free check the UI uses to show whether mirroring is configured,
    without making any network call."""
    return get_client() is not None


if __name__ == "__main__":
    print("Mirror active:", is_mirror_active())
