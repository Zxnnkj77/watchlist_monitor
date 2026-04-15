"""Yahoo Finance news provider implementation."""

from __future__ import annotations

from datetime import datetime, timezone

from models import NewsArticle, WatchlistEntry

try:
    import yfinance as yf
except ImportError:  # pragma: no cover - exercised when optional dependency is absent
    yf = None


class YahooFinanceNewsProvider:
    """Fetch ticker news from Yahoo Finance through yfinance."""

    def fetch_recent(self, entry: WatchlistEntry, limit: int = 8) -> list[NewsArticle]:
        if yf is None:
            raise RuntimeError("yfinance is required for Yahoo Finance news")

        ticker = yf.Ticker(entry.ticker)
        raw_items = ticker.news or []
        articles = []
        for item in raw_items[:limit]:
            article = _convert_yahoo_item(entry, item)
            if article is not None:
                articles.append(article)
        return articles


def _convert_yahoo_item(entry: WatchlistEntry, item: dict) -> NewsArticle | None:
    content = item.get("content") or {}
    title = content.get("title") or item.get("title")
    if not title:
        return None

    provider = content.get("provider") or {}
    source = provider.get("displayName") or item.get("publisher") or "Yahoo Finance"
    url = _extract_url(content) or item.get("link") or f"https://finance.yahoo.com/quote/{entry.ticker}/news"
    published_at = _parse_published_at(content, item)
    summary = content.get("summary") or item.get("summary")

    return NewsArticle(
        ticker=entry.ticker,
        headline=title,
        source=source,
        url=url,
        published_at=published_at,
        summary=summary,
    )


def _extract_url(content: dict) -> str | None:
    for key in ("canonicalUrl", "clickThroughUrl"):
        value = content.get(key) or {}
        if value.get("url"):
            return value["url"]
    return None


def _parse_published_at(content: dict, item: dict) -> datetime:
    raw_pub_date = content.get("pubDate")
    if raw_pub_date:
        return datetime.fromisoformat(raw_pub_date.replace("Z", "+00:00"))

    raw_epoch = item.get("providerPublishTime")
    if raw_epoch:
        return datetime.fromtimestamp(int(raw_epoch), tz=timezone.utc)

    return datetime.now(timezone.utc)
