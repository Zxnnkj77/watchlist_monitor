"""News provider factory and fallback wrapper."""

from __future__ import annotations

import logging
from typing import Protocol

from models import NewsArticle, WatchlistEntry
from services.aggregator import NewsAggregator
from services.news_providers import (
    GoogleNewsRSSProvider,
    MockNewsDataProvider,
    NewsApiProvider,
    YahooFinanceNewsProvider,
)

LOGGER = logging.getLogger(__name__)


class NewsDataProvider(Protocol):
    """Interface for fetching recent news articles."""

    def fetch_recent(self, entry: WatchlistEntry, limit: int = 8) -> list[NewsArticle]:
        """Fetch recent articles for one watchlist entry."""


class FallbackNewsDataProvider:
    """Try a primary provider, then fall back to mock data if it fails."""

    def __init__(self, primary: NewsDataProvider, fallback: NewsDataProvider) -> None:
        self.primary = primary
        self.fallback = fallback

    def fetch_recent(self, entry: WatchlistEntry, limit: int = 8) -> list[NewsArticle]:
        try:
            return self.primary.fetch_recent(entry, limit=limit)
        except Exception as exc:  # noqa: BLE001 - provider boundaries should not crash the run
            LOGGER.warning("News provider failed for %s; using mock news: %s", entry.ticker, exc)
            return self.fallback.fetch_recent(entry, limit=limit)


def build_news_data_provider(
    mode: str,
    newsapi_api_key: str | None,
    enabled_sources: tuple[str, ...] = ("yahoo", "newsapi", "google"),
) -> NewsDataProvider | NewsAggregator:
    """Create a news provider from runtime configuration."""

    mock = MockNewsDataProvider()
    normalized_mode = mode.lower()

    if normalized_mode == "multi":
        providers = _build_multi_source_providers(enabled_sources, newsapi_api_key)
        if providers:
            return NewsAggregator(providers, fallback_provider=mock)
        LOGGER.warning("NEWS_DATA_MODE=multi but no usable sources are configured; using mock news")
        return mock

    if normalized_mode in {"live", "auto"} and newsapi_api_key:
        return FallbackNewsDataProvider(NewsApiProvider(newsapi_api_key), mock)

    if normalized_mode in {"live", "auto"} and not newsapi_api_key:
        LOGGER.warning("NEWS_DATA_MODE=%s but NEWSAPI_API_KEY is missing; using mock news", mode)

    return mock


def _build_multi_source_providers(
    enabled_sources: tuple[str, ...],
    newsapi_api_key: str | None,
) -> list[NewsDataProvider]:
    providers: list[NewsDataProvider] = []
    enabled = {source.lower().strip() for source in enabled_sources}

    if "yahoo" in enabled:
        providers.append(YahooFinanceNewsProvider())

    if "newsapi" in enabled:
        if newsapi_api_key:
            providers.append(NewsApiProvider(newsapi_api_key))
        else:
            LOGGER.warning("NEWS_SOURCES includes newsapi but NEWSAPI_API_KEY is missing; skipping NewsAPI")

    if "google" in enabled or "google_rss" in enabled:
        providers.append(GoogleNewsRSSProvider())

    unknown_sources = enabled - {"yahoo", "newsapi", "google", "google_rss"}
    if unknown_sources:
        LOGGER.warning("Ignoring unknown NEWS_SOURCES values: %s", ", ".join(sorted(unknown_sources)))

    return providers
