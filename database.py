import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from sources.base_source import SourceItem

DB_FILE = "discord_research.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS source_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    author TEXT,
    content TEXT,
    url TEXT,
    timestamp TEXT,
    metadata_json TEXT,
    external_id TEXT,
    UNIQUE(source, external_id)
);
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_item_id INTEGER REFERENCES source_items(id),
    ticker TEXT,
    company_name TEXT,
    price REAL,
    market_cap TEXT,
    daily_change_pct REAL,
    sentiment TEXT,
    sentiment_reasoning TEXT,
    fact_check_verdict TEXT,
    fact_check_explanation TEXT,
    technical_summary TEXT,
    confidence_score INTEGER,
    reasoning TEXT,
    news_json TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS ai_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT,
    feature TEXT,
    timestamp TEXT,
    model TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    estimated_cost REAL
);
"""


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def save_source_item(item: SourceItem) -> int:
    """Insert a SourceItem, or return the existing row's id if it's a duplicate
    (same source + external_id, e.g. the same Discord message seen twice)."""
    external_id = item.metadata.get("message_id") or item.metadata.get("id") or item.timestamp

    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT id FROM source_items WHERE source = ? AND external_id = ?",
            (item.source, external_id),
        )
        existing = cursor.fetchone()
        if existing:
            return existing["id"]

        cursor = conn.execute(
            """INSERT INTO source_items (source, author, content, url, timestamp, metadata_json, external_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (item.source, item.author, item.content, item.url, item.timestamp,
             json.dumps(item.metadata), external_id),
        )
        conn.commit()
        return cursor.lastrowid


def save_analysis(source_item_id: int, report: dict) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO analyses (
                source_item_id, ticker, company_name, price, market_cap, daily_change_pct,
                sentiment, sentiment_reasoning, fact_check_verdict, fact_check_explanation,
                technical_summary, confidence_score, reasoning, news_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                source_item_id,
                report.get("ticker"),
                report.get("company"),
                report.get("price"),
                report.get("market_cap"),
                report.get("daily_change_pct"),
                report.get("sentiment"),
                report.get("sentiment_reasoning"),
                report.get("fact_check_verdict"),
                report.get("fact_check_explanation"),
                report.get("technical_summary"),
                report.get("confidence_score"),
                report.get("reasoning"),
                json.dumps(report.get("recent_news", [])),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        return cursor.lastrowid


def get_recent_items(limit: int = 25) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM source_items ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_recent_analyses(limit: int = 25) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT analyses.*, source_items.source AS item_source, source_items.author AS item_author,
                      source_items.content AS item_content, source_items.url AS item_url
               FROM analyses
               JOIN source_items ON analyses.source_item_id = source_items.id
               ORDER BY analyses.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def search_analyses(
    query: str = "",
    ticker: str | None = None,
    source: str | None = None,
    verdict: str | None = None,
    limit: int = 50,
) -> list[dict]:
    sql = """SELECT analyses.*, source_items.source AS item_source, source_items.author AS item_author,
                    source_items.content AS item_content, source_items.url AS item_url
             FROM analyses
             JOIN source_items ON analyses.source_item_id = source_items.id
             WHERE 1=1"""
    params: list = []

    if query:
        sql += " AND (analyses.ticker LIKE ? OR analyses.reasoning LIKE ? OR source_items.content LIKE ?)"
        like = f"%{query}%"
        params.extend([like, like, like])
    if ticker:
        sql += " AND analyses.ticker = ?"
        params.append(ticker)
    if source:
        sql += " AND source_items.source = ?"
        params.append(source)
    if verdict:
        sql += " AND analyses.fact_check_verdict = ?"
        params.append(verdict)

    sql += " ORDER BY analyses.id DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def get_distinct_tickers() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT ticker FROM analyses WHERE ticker IS NOT NULL ORDER BY ticker"
        ).fetchall()
        return [r["ticker"] for r in rows]


def save_ai_usage(usage: dict) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO ai_usage (agent, feature, timestamp, model, input_tokens, output_tokens, total_tokens, estimated_cost)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                usage["agent"], usage["feature"], usage["timestamp"], usage["model"],
                usage["input_tokens"], usage["output_tokens"], usage["total_tokens"], usage["estimated_cost"],
            ),
        )
        conn.commit()
        return cursor.lastrowid


def get_usage_by_day_prefix(day_prefix: str) -> list[dict]:
    """Per-agent requests/tokens/cost for rows whose timestamp starts with day_prefix
    (e.g. '2026-07-27' for one day, '2026-07' for a whole month)."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT agent, COUNT(*) as requests, SUM(total_tokens) as tokens, SUM(estimated_cost) as cost
               FROM ai_usage
               WHERE timestamp LIKE ?
               GROUP BY agent
               ORDER BY cost DESC""",
            (f"{day_prefix}%",),
        ).fetchall()
        return [dict(r) for r in rows]


def get_usage_today() -> list[dict]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return get_usage_by_day_prefix(today)


def get_usage_this_month() -> list[dict]:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    return get_usage_by_day_prefix(month)


def get_daily_usage_history(days: int = 14) -> list[dict]:
    """Per-day totals (all agents combined) for the most recent days with any usage."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT substr(timestamp, 1, 10) as day, COUNT(*) as requests,
                      SUM(total_tokens) as tokens, SUM(estimated_cost) as cost
               FROM ai_usage
               GROUP BY day
               ORDER BY day DESC
               LIMIT ?""",
            (days,),
        ).fetchall()
        return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    print(f"Initialized {DB_FILE} — {len(get_recent_analyses())} existing analyses.")
