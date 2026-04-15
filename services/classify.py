"""Rule-based event classification."""

from __future__ import annotations

import re

from models import NewsArticle

EVENT_KEYWORDS: dict[str, list[str]] = {
    "earnings": ["earnings", "quarterly", "results", "guidance", "revenue", "margin", "profit", "profits"],
    "management change": ["appoints", "resigns", "ceo", "cfo", "chief", "leadership", "management"],
    "financing": ["debt", "equity", "offering", "loan", "credit", "financing", "raise"],
    "litigation": ["lawsuit", "sues", "settlement", "probe", "investigation", "sec", "doj"],
    "M&A": ["acquire", "acquisition", "merger", "takeover", "buyout", "divest", "sale"],
    "macro/sector": ["sector", "macro", "inflation", "rates", "demand", "supply", "tariff"],
}


def classify_article(article: NewsArticle) -> tuple[str, list[str]]:
    """Classify one article into a business event type."""

    text = f"{article.headline} {article.summary or ''}".lower()
    matches: list[tuple[str, int, list[str]]] = []
    for event_type, keywords in EVENT_KEYWORDS.items():
        found = [keyword for keyword in keywords if _contains_keyword(text, keyword)]
        if found:
            matches.append((event_type, len(found), found))

    if not matches:
        return "other", []

    matches.sort(key=lambda item: item[1], reverse=True)
    event_type, _, signals = matches[0]
    return event_type, signals


def _contains_keyword(text: str, keyword: str) -> bool:
    if " " in keyword:
        return keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None
