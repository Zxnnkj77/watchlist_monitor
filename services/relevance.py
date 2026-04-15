"""Article filtering, deduplication, and relevance scoring."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from models import NewsArticle, NewsEventCluster, WatchlistEntry

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

LEGAL_SUFFIXES = {
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "co",
    "company",
    "ltd",
    "limited",
    "plc",
    "holdings",
    "group",
    "class",
    "sa",
    "nv",
}

MATERIAL_KEYWORDS = {
    "earnings": 2.5,
    "guidance": 2.5,
    "revenue": 1.5,
    "margin": 1.5,
    "profit": 1.5,
    "profits": 1.5,
    "eps": 1.5,
    "estimates": 1.0,
    "analyst": 1.0,
    "rating": 1.0,
    "price target": 1.0,
    "shares": 1.0,
    "stock": 1.0,
    "dividend": 1.5,
    "buyback": 1.5,
    "cash flow": 1.5,
    "data center": 1.5,
    "delay": 1.0,
    "delays": 1.0,
    "partnership": 1.0,
    "ceo": 2.0,
    "cfo": 2.0,
    "appoints": 1.5,
    "resigns": 2.0,
    "acquisition": 2.5,
    "merger": 2.5,
    "lawsuit": 2.0,
    "investigation": 2.0,
    "debt": 1.5,
    "offering": 1.5,
    "sector": 1.0,
    "macro": 1.0,
}

SOURCE_QUALITY_BONUS = {
    "sec": 1.4,
    "company press release": 1.2,
    "business wire": 1.0,
    "globe newswire": 1.0,
    "pr newswire": 0.8,
    "reuters": 0.8,
    "associated press": 0.6,
    "wall street journal": 0.6,
    "bloomberg": 0.6,
}

LOW_VALUE_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"\bwatchlist\b", re.IGNORECASE), 2.5),
    (re.compile(r"\btop\s+\d*\s*stocks?\s+to\s+buy\b", re.IGNORECASE), 3.0),
    (re.compile(r"\bstocks?\s+(?:i|we)\s+want\s+to\s+own\b", re.IGNORECASE), 3.0),
    (re.compile(r"\bbest\s+stocks?\b", re.IGNORECASE), 2.5),
    (re.compile(r"\bamong\s+the\s+\d+\s+.+\bstocks?\b", re.IGNORECASE), 3.0),
    (re.compile(r"\bstock\s+price,\s+quote\s+&?\s+chart\b", re.IGNORECASE), 4.0),
    (re.compile(r"\bquote\s+&?\s+chart\b", re.IGNORECASE), 3.0),
    (re.compile(r"\bopinions?\s+on\b", re.IGNORECASE), 3.0),
    (re.compile(r"\bhere.?s\s+why\b", re.IGNORECASE), 2.0),
    (re.compile(r"\blove\s+[A-Z][A-Za-z0-9&.\-]+\b", re.IGNORECASE), 1.75),
    (re.compile(r"\bwinning\s+streak\b", re.IGNORECASE), 1.5),
    (re.compile(r"\bstock\s+(?:climbs|rises|falls|drops)\s+amid\s+market\b", re.IGNORECASE), 2.5),
    (re.compile(r"\bmarket\s+optimism\b", re.IGNORECASE), 2.0),
    (re.compile(r"\bwhat\s+you\s+need\s+to\s+know\b", re.IGNORECASE), 2.0),
    (re.compile(r"\bwhat\s+to\s+do\s+now\b", re.IGNORECASE), 2.5),
    (re.compile(r"\boutperforms\s+broader\s+market\b", re.IGNORECASE), 2.5),
    (re.compile(r"\bdow\s+jones\s+futures\b", re.IGNORECASE), 3.0),
    (re.compile(r"\bstock\s+market\s+today\b", re.IGNORECASE), 2.5),
    (re.compile(r"\bmarket\s+rally\b", re.IGNORECASE), 2.0),
    (re.compile(r"\bprice\s+target\s+roundup\b", re.IGNORECASE), 2.5),
    (re.compile(r"\bwhy\s+.+\s+stock\s+(?:skyrocketed|soared|jumped|plunged)\b", re.IGNORECASE), 1.75),
    (re.compile(r"\bbuy\s+signals?\b", re.IGNORECASE), 1.5),
]

OTHER_COMPANY_SUBJECT_PATTERNS = [
    re.compile(r"\b[A-Z][A-Za-z0-9&.\-]+\s+(?:[Ss]tock|[Ss]hares)\b"),
    re.compile(r"\b(?:NYSE|NASDAQ|Nasdaq|nyse|nasdaq):\s*([A-Z.]{1,6})\b"),
]

OTHER_EXECUTIVE_PATTERN = re.compile(r"^\s*([A-Z][A-Za-z0-9&.\-]+(?:\s+[A-Z][A-Za-z0-9&.\-]+){0,2})\s+CEO\b")

COMPANY_ACTION_PATTERN = re.compile(
    r"\b(announces?|reports?|raises?|cuts?|beats?|misses?|tops?|launches?|files?|sues?|settles?|"
    r"appoints?|resigns?|acquires?|buys?|sells?|invests?|plans?|expands?|warns?)\b",
    re.IGNORECASE,
)

BROAD_MARKET_TERMS = {
    "dow",
    "futures",
    "nasdaq",
    "s&p",
    "broader market",
    "market rally",
    "stock market",
    "sector etf",
    "peers",
}

GENERIC_SUBJECT_WORDS = {
    "artificial",
    "bank",
    "big",
    "growth",
    "tech",
    "utility",
    "value",
}


def filter_relevant_articles(
    articles: list[NewsArticle],
    entry: WatchlistEntry,
    min_score: float = 2.0,
    max_items: int = 5,
) -> list[tuple[NewsArticle, float]]:
    """Filter, deduplicate, and score articles for one ticker."""

    deduped = deduplicate_articles(articles)
    scored = [(article, score_article(article, entry)) for article in deduped]
    material = [item for item in scored if item[1] >= min_score]
    material.sort(key=lambda item: item[1], reverse=True)
    return material[:max_items]


def filter_relevant_clusters(
    clusters: list[NewsEventCluster],
    entry: WatchlistEntry,
    min_score: float = 3.0,
    max_items: int = 5,
) -> list[tuple[NewsEventCluster, float]]:
    """Filter and score clustered market events for one ticker."""

    scored: list[tuple[NewsEventCluster, float]] = []
    for cluster in clusters:
        article_scores = [
            (
                article,
                score_article(
                    article,
                    entry,
                    source_count=cluster.source_count,
                ),
            )
            for article in cluster.articles
        ]
        best_article, best_score = max(
            article_scores,
            key=lambda item: (
                item[1],
                bool(item[0].summary),
                item[0].published_at,
            ),
        )
        scored.append(
            (
                NewsEventCluster(
                    representative_article=best_article,
                    articles=cluster.articles,
                    source_count=cluster.source_count,
                    sources=cluster.sources,
                ),
                best_score,
            )
        )
    material = [item for item in scored if item[1] >= min_score]
    material.sort(
        key=lambda item: (
            item[1],
            item[0].source_count,
            item[0].representative_article.published_at,
        ),
        reverse=True,
    )
    return material[:max_items]


def deduplicate_articles(articles: list[NewsArticle], similarity_threshold: float = 0.82) -> list[NewsArticle]:
    """Remove near-duplicate articles using normalized headline token overlap."""

    kept: list[NewsArticle] = []
    kept_tokens: list[set[str]] = []
    for article in articles:
        tokens = _headline_tokens(article.headline)
        if not tokens:
            continue
        if any(_jaccard(tokens, existing) >= similarity_threshold for existing in kept_tokens):
            continue
        kept.append(article)
        kept_tokens.append(tokens)
    return kept


def score_article(
    article: NewsArticle,
    entry: WatchlistEntry,
    now: datetime | None = None,
    source_count: int = 1,
) -> float:
    """Score an article for relevance and materiality."""

    now = now or datetime.now(timezone.utc)
    headline = article.headline or ""
    summary = article.summary or ""
    text = f"{headline} {summary}"
    normalized_text = text.lower()
    target = _target_focus(article, entry)
    score = 0.0

    score += target.score

    material_score = sum(weight for keyword, weight in MATERIAL_KEYWORDS.items() if _contains_keyword(normalized_text, keyword))
    if target.headline_score >= 2.0:
        score += material_score
    elif target.score >= 1.5:
        score += material_score * 0.45
    else:
        score += min(material_score * 0.15, 0.75)

    if target.headline_score >= 2.0 and COMPANY_ACTION_PATTERN.search(headline):
        score += 1.25

    age_hours = max((now - article.published_at).total_seconds() / 3600, 0)
    recency_bonus = max(0.0, 1.25 - math.log1p(age_hours) / 2.25)
    score += recency_bonus if target.score else recency_bonus * 0.2

    score += SOURCE_QUALITY_BONUS.get(article.source.lower(), 0.0)

    source_count_bonus = min(2.5, max(source_count - 1, 0) * (1.1 if target.score >= 2.0 else 0.45))
    score += source_count_bonus

    score -= _noise_penalty(article, entry, target)

    if target.score == 0:
        score = min(score, 1.5)
    if target.headline_score == 0 and _is_broad_market_article(normalized_text):
        score -= 1.25

    return round(max(score, 0.0), 2)


class _TargetFocus:
    def __init__(self, score: float, headline_score: float) -> None:
        self.score = score
        self.headline_score = headline_score


def _target_focus(article: NewsArticle, entry: WatchlistEntry) -> _TargetFocus:
    headline = article.headline.lower()
    summary = (article.summary or "").lower()
    headline_score = 0.0
    body_score = 0.0

    ticker_pattern = rf"\b{re.escape(entry.ticker.lower())}\b"
    if re.search(ticker_pattern, headline):
        headline_score += 3.0
    elif re.search(ticker_pattern, summary):
        body_score += 1.5

    aliases = _company_aliases(entry)
    for alias in aliases:
        pattern = rf"\b{re.escape(alias)}\b"
        if re.search(pattern, headline):
            headline_score = max(headline_score, 2.5 if " " in alias else 1.6)
        elif re.search(pattern, summary):
            body_score = max(body_score, 1.25 if " " in alias else 0.8)

    return _TargetFocus(min(headline_score + body_score, 4.5), headline_score)


def _company_aliases(entry: WatchlistEntry) -> list[str]:
    if not entry.company_name:
        return []
    tokens = re.findall(r"[a-z0-9]+", entry.company_name.lower())
    core_tokens = [token for token in tokens if token not in LEGAL_SUFFIXES and len(token) > 2]
    aliases: list[str] = []
    if core_tokens:
        aliases.append(" ".join(core_tokens[:2]))
        aliases.extend(token for token in core_tokens[:2] if len(token) >= 4)
    return _ordered_unique(aliases)


def _contains_keyword(text: str, keyword: str) -> bool:
    if " " in keyword:
        return keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def _noise_penalty(article: NewsArticle, entry: WatchlistEntry, target: _TargetFocus) -> float:
    text = f"{article.headline} {article.summary or ''}"
    penalty = sum(weight for pattern, weight in LOW_VALUE_PATTERNS if pattern.search(text))

    if _is_broad_market_article(text.lower()) and target.headline_score < 3.0:
        penalty += 1.5

    if _looks_like_other_company_subject(article.headline, entry) and target.headline_score < 3.0:
        penalty += 4.0 if target.headline_score < 2.0 else 2.0

    if _starts_with_other_company_executive(article.headline, entry) and target.headline_score < 3.0:
        penalty += 2.75

    if _target_is_commentator(article.headline, entry):
        penalty += 4.0

    if target.headline_score == 0 and target.score < 2.0:
        penalty += 1.0

    return penalty


def _is_broad_market_article(text: str) -> bool:
    return any(term in text for term in BROAD_MARKET_TERMS)


def _looks_like_other_company_subject(headline: str, entry: WatchlistEntry) -> bool:
    lowered = headline.lower()
    target_words = {entry.ticker.lower(), *_company_aliases(entry)}
    for pattern in OTHER_COMPANY_SUBJECT_PATTERNS:
        for match in pattern.finditer(headline):
            matched_text = match.group(0).lower()
            first_word = matched_text.split()[0]
            if first_word in GENERIC_SUBJECT_WORDS:
                continue
            if any(target in matched_text for target in target_words):
                continue
            if matched_text.startswith("stock market"):
                continue
            return True
    return False


def _starts_with_other_company_executive(headline: str, entry: WatchlistEntry) -> bool:
    match = OTHER_EXECUTIVE_PATTERN.search(headline)
    if not match:
        return False
    subject = match.group(1).lower()
    return not any(target in subject for target in {entry.ticker.lower(), *_company_aliases(entry)})


def _target_is_commentator(headline: str, entry: WatchlistEntry) -> bool:
    lowered = headline.lower()
    aliases = {entry.ticker.lower(), *_company_aliases(entry)}
    starts_with_target = any(lowered.startswith(alias) for alias in aliases)
    if starts_with_target:
        return False
    return any(
        re.search(rf"\b{re.escape(alias)}\s+(?:warns|says|sees|predicts|expects|estimates)\b", lowered)
        for alias in aliases
    )


def _headline_tokens(headline: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", headline.lower())
    return {token for token in tokens if token not in STOPWORDS}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _ordered_unique(values) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
