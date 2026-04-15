"""Multi-source news aggregation and event clustering."""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Protocol

from models import NewsArticle, NewsEventCluster, WatchlistEntry

LOGGER = logging.getLogger(__name__)

STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}

GENERIC_HEADLINE_TOKENS = {
    "after",
    "before",
    "best",
    "buy",
    "daily",
    "dow",
    "futures",
    "higher",
    "into",
    "jones",
    "market",
    "markets",
    "move",
    "moves",
    "nasdaq",
    "need",
    "now",
    "own",
    "rally",
    "share",
    "shares",
    "stock",
    "stocks",
    "today",
    "top",
    "want",
    "what",
    "why",
}

EVENT_CONCEPTS: dict[str, tuple[str, ...]] = {
    "earnings": (
        "earnings",
        "results",
        "quarterly",
        "quarter",
        "q1",
        "q2",
        "q3",
        "q4",
        "eps",
        "revenue",
        "profit",
        "margin",
        "guidance",
        "estimates",
    ),
    "management": ("ceo", "cfo", "chief", "appoints", "resigns", "leadership", "dimon"),
    "financing": ("debt", "equity", "offering", "loan", "credit", "financing", "liquidity"),
    "litigation": ("lawsuit", "sues", "settlement", "probe", "investigation", "regulator", "doj", "sec"),
    "ma": ("acquire", "acquisition", "merger", "takeover", "buyout", "divest", "sale"),
}


class ArticleProvider(Protocol):
    """Provider shape required by the aggregator."""

    def fetch_recent(self, entry: WatchlistEntry, limit: int = 8) -> list[NewsArticle]:
        """Fetch recent articles for one watchlist entry."""


class NewsAggregator:
    """Collect articles from several providers and group similar market stories."""

    def __init__(
        self,
        providers: list[ArticleProvider],
        fallback_provider: ArticleProvider | None = None,
        similarity_threshold: float = 0.74,
    ) -> None:
        self.providers = providers
        self.fallback_provider = fallback_provider
        self.similarity_threshold = similarity_threshold

    def fetch_recent_clusters(self, entry: WatchlistEntry, limit: int = 8) -> list[NewsEventCluster]:
        """Fetch, merge, and cluster articles from all configured providers."""

        articles: list[NewsArticle] = []
        for provider in self.providers:
            provider_name = provider.__class__.__name__
            try:
                articles.extend(provider.fetch_recent(entry, limit=limit))
            except Exception as exc:  # noqa: BLE001 - one provider should not kill the run
                LOGGER.warning("%s failed for %s: %s", provider_name, entry.ticker, exc)

        if not articles and self.fallback_provider is not None:
            LOGGER.warning("No real news articles found for %s; using mock fallback news", entry.ticker)
            articles = self.fallback_provider.fetch_recent(entry, limit=limit)

        clusters = cluster_articles(articles, similarity_threshold=self.similarity_threshold)
        return sorted(
            clusters,
            key=lambda cluster: (
                cluster.source_count,
                cluster.representative_article.published_at,
            ),
            reverse=True,
        )[:limit]


def cluster_articles(
    articles: list[NewsArticle],
    similarity_threshold: float = 0.74,
) -> list[NewsEventCluster]:
    """Group near-duplicate and similar headlines into event clusters."""

    clusters: list[list[NewsArticle]] = []
    cluster_signatures: list[set[str]] = []
    cluster_core_tokens: list[set[str]] = []
    cluster_titles: list[str] = []

    for article in sorted(articles, key=lambda item: item.published_at, reverse=True):
        signature = _article_signature(article)
        core_tokens = _headline_tokens(article.headline, keep_generic=False)
        if not signature:
            continue

        match_idx = None
        for idx, existing_signature in enumerate(cluster_signatures):
            similarity = _article_similarity(
                article.headline,
                cluster_titles[idx],
                signature,
                existing_signature,
                core_tokens,
                cluster_core_tokens[idx],
            )
            if similarity >= similarity_threshold:
                match_idx = idx
                break

        if match_idx is None:
            clusters.append([article])
            cluster_signatures.append(signature)
            cluster_core_tokens.append(core_tokens)
            cluster_titles.append(article.headline)
        else:
            clusters[match_idx].append(article)
            cluster_signatures[match_idx] |= signature
            cluster_core_tokens[match_idx] |= core_tokens

    return [_build_cluster(cluster) for cluster in clusters]


def _build_cluster(articles: list[NewsArticle]) -> NewsEventCluster:
    canonical_articles = [_canonicalize_article_source(article) for article in articles]
    raw_representative = max(
        canonical_articles,
        key=lambda article: (
            bool(article.summary),
            article.published_at,
            len(article.headline),
        ),
    )
    representative = raw_representative
    sources = _ordered_unique(article.source for article in canonical_articles if article.source)
    return NewsEventCluster(
        representative_article=representative,
        articles=canonical_articles,
        source_count=len(sources),
        sources=sources,
    )


def _headline_similarity(
    left_headline: str,
    right_headline: str,
    left_tokens: set[str],
    right_tokens: set[str],
) -> float:
    token_similarity = _jaccard(left_tokens, right_tokens)
    text_similarity = SequenceMatcher(None, _normalize(left_headline), _normalize(right_headline)).ratio()
    return max(token_similarity, text_similarity)


def _article_similarity(
    left_headline: str,
    right_headline: str,
    left_signature: set[str],
    right_signature: set[str],
    left_core_tokens: set[str],
    right_core_tokens: set[str],
) -> float:
    token_similarity = _jaccard(left_signature, right_signature)
    title_similarity = SequenceMatcher(None, _normalize(left_headline), _normalize(right_headline)).ratio()
    core_similarity = _jaccard(left_core_tokens, right_core_tokens)
    concept_overlap = _jaccard(
        {token for token in left_signature if token.startswith("event:")},
        {token for token in right_signature if token.startswith("event:")},
    )

    if concept_overlap and core_similarity >= 0.18:
        token_similarity = max(token_similarity, 0.68 + concept_overlap * 0.12)
    if concept_overlap >= 0.5 and _has_shared_company_context(left_core_tokens, right_core_tokens):
        token_similarity = max(token_similarity, 0.76)
    if (
        "event:earnings" in left_signature
        and "event:earnings" in right_signature
        and _has_shared_company_context(left_core_tokens, right_core_tokens)
    ):
        token_similarity = max(token_similarity, 0.76)

    return max(token_similarity, title_similarity)


def _article_signature(article: NewsArticle) -> set[str]:
    text = f"{article.headline} {article.summary or ''}"
    tokens = _headline_tokens(text, keep_generic=False)
    concepts = _event_concepts(text)
    if concepts and article.ticker:
        tokens.add(f"ticker:{article.ticker.lower()}")
    return tokens | concepts


def _headline_tokens(headline: str, keep_generic: bool = True) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", headline.lower())
    ignored = STOPWORDS if keep_generic else STOPWORDS | GENERIC_HEADLINE_TOKENS
    return {token for token in tokens if token not in ignored}


def _normalize(headline: str) -> str:
    return " ".join(sorted(_headline_tokens(headline, keep_generic=False)))


def _event_concepts(text: str) -> set[str]:
    normalized = text.lower()
    concepts: set[str] = set()
    for concept, terms in EVENT_CONCEPTS.items():
        if any(re.search(rf"\b{re.escape(term)}\b", normalized) for term in terms):
            concepts.add(f"event:{concept}")
    return concepts


def _has_shared_company_context(left: set[str], right: set[str]) -> bool:
    shared = left & right
    return any(len(token) >= 4 and not token.startswith("event:") for token in shared)


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _ordered_unique(values) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        normalized = value.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(value)
    return unique


def _canonical_source(source: str) -> str:
    normalized = " ".join(source.replace("’", "'").split()).strip()
    replacements = {
        "barrons.com": "Barron's",
        "barron's": "Barron's",
        "the wall street journal": "Wall Street Journal",
        "wsj": "Wall Street Journal",
        "yahoo finance video": "Yahoo Finance Video",
        "investors business daily": "Investor's Business Daily",
        "investor's business daily": "Investor's Business Daily",
    }
    return replacements.get(normalized.casefold(), normalized)


def _canonicalize_article_source(article: NewsArticle) -> NewsArticle:
    canonical_source = _canonical_source(article.source)
    if canonical_source == article.source:
        return article
    return NewsArticle(
        ticker=article.ticker,
        headline=article.headline,
        source=canonical_source,
        url=article.url,
        published_at=article.published_at,
        summary=article.summary,
    )
