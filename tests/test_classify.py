from datetime import datetime, timedelta, timezone

from models import NewsArticle
from services.classify import classify_article


def _article(headline: str, summary: str) -> NewsArticle:
    return NewsArticle(
        ticker="MSFT",
        headline=headline,
        source="MockWire",
        url="https://example.com",
        published_at=datetime.now(timezone.utc) - timedelta(hours=1),
        summary=summary,
    )


def test_classify_does_not_match_sec_inside_sector() -> None:
    article = _article(
        "Software stocks are finally joining the tech rally",
        "The software sector ETF moved higher as Microsoft and peers gained.",
    )

    event_type, signals = classify_article(article)

    assert event_type == "macro/sector"
    assert "sec" not in signals
