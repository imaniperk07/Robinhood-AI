import json
import sqlite3
from abc import ABC, abstractmethod
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
CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    entry_price REAL,
    target_price REAL,
    stop_loss REAL,
    position_size_usd REAL,
    shares REAL,
    trade_score INTEGER,
    athena_confidence INTEGER,
    risk_level TEXT,
    reason_for_entry TEXT,
    expected_holding_time TEXT,
    date_opened TEXT,
    date_closed TEXT,
    status TEXT,
    exit_reason TEXT,
    current_price REAL,
    profit_loss_pct REAL,
    highest_gain_pct REAL,
    largest_drawdown_pct REAL,
    days_held INTEGER
);
CREATE TABLE IF NOT EXISTS trade_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER REFERENCES paper_trades(id),
    original_thesis TEXT,
    news_summary TEXT,
    technical_analysis TEXT,
    confidence_score INTEGER,
    reason_entry_approved TEXT,
    reason_exit_occurred TEXT,
    lessons_learned TEXT,
    final_outcome TEXT,
    created_at TEXT
);
"""


class Storage(ABC):
    """Interface every storage backend implements. Callers only ever talk to this
    (via the `storage` singleton below), never to a concrete backend directly —
    swapping SQLite for a shared/persistent database later means writing a new
    class here, not touching app.py, main.py, discord_notifier.py, etc."""

    @abstractmethod
    def init(self) -> None: ...

    @abstractmethod
    def save_source_item(self, item: SourceItem) -> int: ...

    @abstractmethod
    def save_analysis(self, source_item_id: int, report: dict) -> int: ...

    @abstractmethod
    def get_recent_items(self, limit: int = 25) -> list[dict]: ...

    @abstractmethod
    def get_recent_analyses(self, limit: int = 25) -> list[dict]: ...

    @abstractmethod
    def search_analyses(
        self,
        query: str = "",
        ticker: str | None = None,
        source: str | None = None,
        verdict: str | None = None,
        limit: int = 50,
    ) -> list[dict]: ...

    @abstractmethod
    def get_distinct_tickers(self) -> list[str]: ...

    @abstractmethod
    def save_ai_usage(self, usage: dict) -> int: ...

    @abstractmethod
    def get_usage_by_day_prefix(self, day_prefix: str) -> list[dict]: ...

    @abstractmethod
    def get_usage_today(self) -> list[dict]: ...

    @abstractmethod
    def get_usage_this_month(self) -> list[dict]: ...

    @abstractmethod
    def get_daily_usage_history(self, days: int = 14) -> list[dict]: ...

    @abstractmethod
    def save_paper_trade(self, trade: dict) -> int: ...

    @abstractmethod
    def update_paper_trade(self, trade_id: int, fields: dict) -> None: ...

    @abstractmethod
    def get_open_paper_trades(self) -> list[dict]: ...

    @abstractmethod
    def get_closed_paper_trades(self, limit: int = 100) -> list[dict]: ...

    @abstractmethod
    def get_paper_trade(self, trade_id: int) -> dict | None: ...

    @abstractmethod
    def save_trade_journal_entry(self, entry: dict) -> int: ...

    @abstractmethod
    def update_trade_journal_entry(self, trade_id: int, fields: dict) -> None: ...

    @abstractmethod
    def get_trade_journal(self, trade_id: int) -> dict | None: ...


class SQLiteStorage(Storage):
    """v0.1 backend — a local SQLite file. Ephemeral on Streamlit Cloud's free tier
    (wiped on redeploy/restart); a future backend pointed at a persistent shared
    database is a new class implementing Storage, with the `storage` singleton
    below swapped to it — nothing else in the app changes."""

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def init(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def save_source_item(self, item: SourceItem) -> int:
        """Insert a SourceItem, or return the existing row's id if it's a duplicate
        (same source + external_id, e.g. the same Discord message seen twice)."""
        external_id = item.metadata.get("message_id") or item.metadata.get("id") or item.timestamp

        with self._get_connection() as conn:
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

    def save_analysis(self, source_item_id: int, report: dict) -> int:
        with self._get_connection() as conn:
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

    def get_recent_items(self, limit: int = 25) -> list[dict]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM source_items ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_recent_analyses(self, limit: int = 25) -> list[dict]:
        with self._get_connection() as conn:
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
        self,
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

        with self._get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def get_distinct_tickers(self) -> list[str]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT ticker FROM analyses WHERE ticker IS NOT NULL ORDER BY ticker"
            ).fetchall()
            return [r["ticker"] for r in rows]

    def save_ai_usage(self, usage: dict) -> int:
        with self._get_connection() as conn:
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

    def get_usage_by_day_prefix(self, day_prefix: str) -> list[dict]:
        """Per-agent requests/tokens/cost for rows whose timestamp starts with day_prefix
        (e.g. '2026-07-27' for one day, '2026-07' for a whole month)."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT agent, COUNT(*) as requests, SUM(total_tokens) as tokens, SUM(estimated_cost) as cost
                   FROM ai_usage
                   WHERE timestamp LIKE ?
                   GROUP BY agent
                   ORDER BY cost DESC""",
                (f"{day_prefix}%",),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_usage_today(self) -> list[dict]:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.get_usage_by_day_prefix(today)

    def get_usage_this_month(self) -> list[dict]:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        return self.get_usage_by_day_prefix(month)

    def get_daily_usage_history(self, days: int = 14) -> list[dict]:
        """Per-day totals (all agents combined) for the most recent days with any usage."""
        with self._get_connection() as conn:
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

    def save_paper_trade(self, trade: dict) -> int:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO paper_trades (
                    ticker, entry_price, target_price, stop_loss, position_size_usd, shares,
                    trade_score, athena_confidence, risk_level, reason_for_entry, expected_holding_time,
                    date_opened, date_closed, status, exit_reason, current_price, profit_loss_pct,
                    highest_gain_pct, largest_drawdown_pct, days_held
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trade["ticker"], trade["entry_price"], trade.get("target_price"), trade.get("stop_loss"),
                    trade.get("position_size_usd"), trade.get("shares"), trade.get("trade_score"),
                    trade.get("athena_confidence"), trade.get("risk_level"), trade.get("reason_for_entry"),
                    trade.get("expected_holding_time"), trade.get("date_opened"), trade.get("date_closed"),
                    trade.get("status", "Open"), trade.get("exit_reason"), trade.get("current_price"),
                    trade.get("profit_loss_pct"), trade.get("highest_gain_pct"), trade.get("largest_drawdown_pct"),
                    trade.get("days_held"),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def update_paper_trade(self, trade_id: int, fields: dict) -> None:
        if not fields:
            return
        set_clause = ", ".join(f"{key} = ?" for key in fields)
        with self._get_connection() as conn:
            conn.execute(
                f"UPDATE paper_trades SET {set_clause} WHERE id = ?",
                (*fields.values(), trade_id),
            )
            conn.commit()

    def get_open_paper_trades(self) -> list[dict]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM paper_trades WHERE status = 'Open' ORDER BY date_opened DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_closed_paper_trades(self, limit: int = 100) -> list[dict]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM paper_trades WHERE status = 'Closed' ORDER BY date_closed DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_paper_trade(self, trade_id: int) -> dict | None:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM paper_trades WHERE id = ?", (trade_id,)).fetchone()
            return dict(row) if row else None

    def save_trade_journal_entry(self, entry: dict) -> int:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO trade_journal (
                    trade_id, original_thesis, news_summary, technical_analysis, confidence_score,
                    reason_entry_approved, reason_exit_occurred, lessons_learned, final_outcome, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry["trade_id"], entry.get("original_thesis"), entry.get("news_summary"),
                    entry.get("technical_analysis"), entry.get("confidence_score"),
                    entry.get("reason_entry_approved"), entry.get("reason_exit_occurred"),
                    entry.get("lessons_learned"), entry.get("final_outcome"),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def update_trade_journal_entry(self, trade_id: int, fields: dict) -> None:
        if not fields:
            return
        set_clause = ", ".join(f"{key} = ?" for key in fields)
        with self._get_connection() as conn:
            conn.execute(
                f"UPDATE trade_journal SET {set_clause} WHERE trade_id = ?",
                (*fields.values(), trade_id),
            )
            conn.commit()

    def get_trade_journal(self, trade_id: int) -> dict | None:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM trade_journal WHERE trade_id = ? ORDER BY id DESC LIMIT 1", (trade_id,)
            ).fetchone()
            return dict(row) if row else None


storage: Storage = SQLiteStorage()


if __name__ == "__main__":
    storage.init()
    print(f"Initialized {DB_FILE} — {len(storage.get_recent_analyses())} existing analyses.")
