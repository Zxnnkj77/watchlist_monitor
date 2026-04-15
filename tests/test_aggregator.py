from datetime import datetime, timedelta, timezone

from models import NewsArticle
from services.aggregator import cluster_articles


def _article(headline: str, source: str, hours_old: int = 1) -> NewsArticle:
    return NewsArticle(
        ticker="ABC",
        headline=headline,
        source=source,
        url=f"https://example.com/{source}",
        published_at=datetime.now(timezone.utc) - timedelta(hours=hours_old),
        summary="Company update",
    )


def test_cluster_articles_tracks_sources_for_similar_stories() -> None:
    clusters = cluster_articles(
        [
            _article("ABC raises guidance after earnings beat", "Reuters"),
            _article("ABC raises guidance following earnings beat", "CNBC"),
            _article("ABC announces board refresh", "Yahoo Finance"),
        ]
    )

    multi_source = next(cluster for cluster in clusters if "guidance" in cluster.representative_article.headline)

    assert multi_source.source_count == 2
    assert set(multi_source.sources) == {"Reuters", "CNBC"}


def test_cluster_articles_groups_same_earnings_story_with_different_wording() -> None:
    clusters = cluster_articles(
        [
            _article(
                "JPMorgan Chase & Co. Q1 2026 Earnings Call Summary",
                "Moby",
            ),
            _article(
                "JPMorgan Tops Estimates. CEO Jamie Dimon Sees Economic Tailwinds, Risks.",
                "Investor’s Business Daily",
            ),
            _article("Morgan Stanley expected to report higher profits", "Barrons.com"),
        ]
    )

    earnings_cluster = next(cluster for cluster in clusters if "JPMorgan" in cluster.representative_article.headline)

    assert earnings_cluster.source_count == 2
    assert set(earnings_cluster.sources) == {"Moby", "Investor's Business Daily"}
