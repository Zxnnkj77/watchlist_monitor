"""Google News RSS provider implementation."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import struct_time
from urllib.parse import quote_plus

from models import NewsArticle, WatchlistEntry

try:
    import feedparser
except ImportError:  # pragma: no cover - exercised when optional dependency is absent
    feedparser = None


class GoogleNewsRSSProvider:
    """Fetch broad ticker and company coverage from Google News RSS."""

    BASE_URL = "https://news.google.com/rss/search"

    def fetch_recent(self, entry: WatchlistEntry, limit: int = 8) -> list[NewsArticle]:
        if feedparser is None:
            raise RuntimeError("feedparser is required for Google News RSS")

        query = _build_query(entry)
        url = f"{self.BASE_URL}?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        if getattr(feed, "bozo", False) and getattr(feed, "bozo_exception", None):
            raise RuntimeError(f"Google News RSS parse failed: {feed.bozo_exception}")

        articles = []
        for item in feed.entries[:limit]:
            headline, source = _split_google_title(getattr(item, "title", "Untitled article"))
            articles.append(
                NewsArticle(
                    ticker=entry.ticker,
                    headline=headline,
                    source=source or "Google News",
                    url=getattr(item, "link", url),
                    published_at=_parse_published_at(item),
                    summary=_clean_summary(getattr(item, "summary", None)),
                )
            )
        return articles


def _build_query(entry: WatchlistEntry) -> str:
    terms = [entry.ticker]
    if entry.company_name:
        terms.append(f'"{entry.company_name}"')
    return f"({' OR '.join(terms)}) when:7d"


def _split_google_title(title: str) -> tuple[str, str | None]:
    if " - " not in title:
        return title, None
    headline, source = title.rsplit(" - ", 1)
    return headline.strip(), source.strip() or None


def _parse_published_at(item) -> datetime:
    published_parsed = getattr(item, "published_parsed", None)
    if isinstance(published_parsed, struct_time):
        return datetime(*published_parsed[:6], tzinfo=timezone.utc)

    published = getattr(item, "published", None)
    if published:
        parsed = parsedate_to_datetime(published)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    return datetime.now(timezone.utc)


def _clean_summary(summary: str | None) -> str | None:
    if not summary:
        return None
    without_tags = re.sub(r"<[^>]+>", " ", summary)
    return " ".join(html.unescape(without_tags).split())
