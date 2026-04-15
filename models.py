"""Core dataclasses used by the market monitoring workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any


@dataclass(frozen=True)
class WatchlistEntry:
    """One monitored security from the local watchlist."""

    ticker: str
    company_name: str | None = None
    sector: str | None = None
    alert_threshold: float = 5.0


@dataclass(frozen=True)
class MarketSnapshot:
    """Small set of market metrics for one ticker."""

    ticker: str
    price: float
    previous_close: float
    change_percent: float
    volume: int | None = None
    market_cap: float | None = None
    source: str = "mock"


@dataclass(frozen=True)
class NewsArticle:
    """Raw news article fetched from a provider."""

    ticker: str
    headline: str
    source: str
    url: str
    published_at: datetime
    summary: str | None = None


@dataclass(frozen=True)
class NewsEventCluster:
    """A group of articles that appear to cover the same market event."""

    representative_article: NewsArticle
    articles: list[NewsArticle]
    source_count: int
    sources: list[str]


@dataclass(frozen=True)
class ProcessedNewsItem:
    """News article after relevance scoring, classification, and summarization."""

    article: NewsArticle
    relevance_score: float
    event_type: str
    concise_summary: str
    why_it_matters: str
    manual_review: bool = False
    signals: list[str] = field(default_factory=list)
    source_count: int = 1
    sources: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TickerBriefing:
    """Processed market and news context for one ticker."""

    watchlist_entry: WatchlistEntry
    market_snapshot: MarketSnapshot | None
    developments: list[ProcessedNewsItem]
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BriefingRun:
    """Complete output for one monitoring run."""

    run_id: str
    generated_at: datetime
    run_date: date
    tickers: list[TickerBriefing]

    def to_json_dict(self) -> dict[str, Any]:
        """Convert the run to a JSON-serializable dictionary."""

        return _serialize(asdict(self))


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value
