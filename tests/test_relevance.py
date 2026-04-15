from datetime import datetime, timedelta, timezone

from models import NewsArticle, WatchlistEntry
from services.relevance import deduplicate_articles, filter_relevant_articles, score_article


def _article(headline: str, summary: str = "Company update") -> NewsArticle:
    return NewsArticle(
        ticker="ABC",
        headline=headline,
        source="MockWire",
        url="https://example.com",
        published_at=datetime.now(timezone.utc) - timedelta(hours=1),
        summary=summary,
    )


def test_deduplicate_articles_removes_near_duplicate_headlines() -> None:
    articles = [
        _article("ABC shares move after quarterly earnings update"),
        _article("ABC shares move after quarterly earnings update"),
        _article("ABC appoints new CFO after review"),
    ]

    deduped = deduplicate_articles(articles)

    assert [item.headline for item in deduped] == [
        "ABC shares move after quarterly earnings update",
        "ABC appoints new CFO after review",
    ]


def test_score_article_rewards_material_terms_and_company_mentions() -> None:
    entry = WatchlistEntry(ticker="ABC", company_name="ABC Corp")
    article = _article("ABC Corp raises guidance after earnings beat", "Revenue and margin improved.")

    score = score_article(article, entry)

    assert score >= 8.0


def test_score_article_rewards_multi_source_coverage() -> None:
    entry = WatchlistEntry(ticker="ABC", company_name="ABC Corp")
    article = _article("ABC Corp reports earnings update")

    single_source_score = score_article(article, entry, source_count=1)
    multi_source_score = score_article(article, entry, source_count=3)

    assert multi_source_score > single_source_score


def test_filter_relevant_articles_removes_low_value_watchlist_articles() -> None:
    entry = WatchlistEntry(ticker="ABC", company_name="ABC Corp")
    articles = [
        _article("Top stocks to buy for your watchlist", "Generic content."),
        _article("ABC Corp appoints new CFO", "Leadership changed during strategic review."),
    ]

    filtered = filter_relevant_articles(articles, entry, min_score=2.0)

    assert len(filtered) == 1
    assert "CFO" in filtered[0][0].headline


def test_score_article_penalizes_other_company_subject_mentions() -> None:
    entry = WatchlistEntry(ticker="AAPL", company_name="Apple Inc.")
    nike_article = _article(
        "Apple CEO Tim Cook Just Bought Nike Stock. His Last Purchase Did Not Go So Well.",
        "Cook bought shares in Nike, where he serves as lead independent director.",
    )
    apple_article = _article(
        "Apple raises iPhone guidance after stronger quarterly earnings",
        "Revenue and margin improved.",
    )

    assert score_article(nike_article, entry) < 2.0
    assert score_article(apple_article, entry) > score_article(nike_article, entry)


def test_score_article_penalizes_broad_market_roundups() -> None:
    entry = WatchlistEntry(ticker="NVDA", company_name="NVIDIA Corporation")
    roundup = _article(
        "Dow Jones Futures: Nasdaq Win Streak Hits 10 Days As Nvidia Flashes Buy Signal; What To Do Now",
        "The stock market rally moved higher with Nvidia and several other stocks.",
    )
    company_specific = _article(
        "Nvidia reports record data center revenue and raises guidance",
        "Revenue and margin beat estimates.",
    )

    assert score_article(roundup, entry) < 2.0
    assert score_article(company_specific, entry) > score_article(roundup, entry)


def test_score_article_penalizes_exact_ticker_market_sentiment_headline() -> None:
    entry = WatchlistEntry(ticker="NVDA", company_name="NVIDIA Corporation")
    sentiment = _article(
        "NVIDIA (NVDA) Stock Climbs Amid Market Optimism and Geopolitical Tensions",
        "Shares moved with broader market optimism.",
    )
    company_specific = _article(
        "Nvidia reports record data center revenue and raises guidance",
        "Revenue and margin beat estimates.",
    )

    assert score_article(sentiment, entry) < 3.0
    assert score_article(company_specific, entry) > score_article(sentiment, entry)


def test_score_article_penalizes_company_as_market_commentator() -> None:
    entry = WatchlistEntry(ticker="JPM", company_name="JPMorgan Chase & Co.")
    commentary = _article(
        "Oil to Test Wartime Highs If Hormuz Standstill Drags, JPM Warns",
        "JPMorgan analysts commented on oil market risk.",
    )
    earnings = _article(
        "JPMorgan Chase reports profits rise after Q1 earnings beat",
        "Revenue and margin beat estimates.",
    )

    assert score_article(commentary, entry) < 3.0
    assert score_article(earnings, entry) > score_article(commentary, entry)
