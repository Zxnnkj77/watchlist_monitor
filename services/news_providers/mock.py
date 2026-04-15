"""Deterministic news fixtures for local development and fallback runs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from models import NewsArticle, WatchlistEntry


class MockNewsDataProvider:
    """Deterministic news fixtures for local development."""

    def fetch_recent(self, entry: WatchlistEntry, limit: int = 8) -> list[NewsArticle]:
        now = datetime.now(timezone.utc)
        name = entry.company_name or entry.ticker
        templates = [
            (
                f"{name} shares move after quarterly earnings update",
                "Company results and guidance drew investor attention in early trading.",
            ),
            (
                f"{name} appoints new finance chief as strategic review continues",
                "The leadership change may affect capital allocation and investor messaging.",
            ),
            (
                f"Sector peers weigh macro pressure while {entry.ticker} investors assess demand",
                "Analysts pointed to broader sector demand and margin risks.",
            ),
            (
                f"{name} announces partnership to expand enterprise distribution",
                "The agreement could support revenue growth if execution remains on track.",
            ),
            (
                f"{name} shares move after quarterly earnings update",
                "A repeated headline is included to exercise near-duplicate filtering.",
            ),
        ]
        articles = [
            NewsArticle(
                ticker=entry.ticker,
                headline=headline,
                source="MockWire",
                url=f"https://example.com/news/{entry.ticker.lower()}/{idx}",
                published_at=now - timedelta(hours=idx * 3 + 1),
                summary=summary,
            )
            for idx, (headline, summary) in enumerate(templates)
        ]
        return articles[:limit]
