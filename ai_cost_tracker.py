from datetime import datetime, timezone

from database import save_ai_usage

# Price per million tokens (input, output). Add a new entry here for any future
# model/provider — everything else in this file and its callers stays the same.
# Sonnet 5 intro pricing runs through 2026-08-31; update to $3.00/$15.00 after that.
PRICING = {
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},
}
DEFAULT_PRICING = {"input": 3.00, "output": 15.00}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = PRICING.get(model, DEFAULT_PRICING)
    return (input_tokens / 1_000_000 * rates["input"]) + (output_tokens / 1_000_000 * rates["output"])


def track_ai_usage(agent: str, model: str, input_tokens: int, output_tokens: int, feature: str = "chat") -> float:
    """Record one API call's usage. Call this right after any client.messages.create()
    call so the numbers stay accurate to what's actually billed. Never raises — a
    logging failure should never break the feature that triggered it. Returns the
    estimated cost of this call in dollars."""
    total_tokens = input_tokens + output_tokens
    cost = estimate_cost(model, input_tokens, output_tokens)

    try:
        save_ai_usage({
            "agent": agent,
            "feature": feature,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost": cost,
        })
    except Exception as e:
        print(f"Failed to record AI usage for {agent}: {e}")

    return cost
