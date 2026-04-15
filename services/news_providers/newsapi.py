"""NewsAPI provider implementation."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote_plus

import requests

from models import NewsArticle, WatchlistEntry


class NewsApiProvider:
    """News provider backed by NewsAPI's everything endpoint."""

    BASE_URL = "https://newsapi.org/v2/everything"

    def __init__(self, api_key: str, timeout_seconds: int = 10) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def fetch_recent(self, entry: WatchlistEntry, limit: int = 8) -> list[NewsArticle]:
        query_terms = [entry.ticker]
        if entry.company_name:
            query_terms.append(f'"{entry.company_name}"')
        query = " OR ".join(query_terms)
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": limit,
            "apiKey": self.api_key,
        }
        response = requests.get(self.BASE_URL, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()

        articles = []
        for item in payload.get("articles", []):
            published_at = _parse_datetime(item.get("publishedAt"))
            articles.append(
                NewsArticle(
                    ticker=entry.ticker,
                    headline=item.get("title") or "Untitled article",
                    source=(item.get("source") or {}).get("name") or "NewsAPI",
                    url=item.get("url") or _fallback_search_url(entry),
                    published_at=published_at,
                    summary=item.get("description"),
                )
            )
        return articles


def _parse_datetime(raw_value: str | None) -> datetime:
    if not raw_value:
        return datetime.now(timezone.utc)
    normalized = raw_value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _fallback_search_url(entry: WatchlistEntry) -> str:
    query = quote_plus(entry.company_name or entry.ticker)
    return f"https://news.google.com/search?q={query}"
