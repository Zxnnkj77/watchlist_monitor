"""Concise rule-based summarization."""

from __future__ import annotations

from models import MarketSnapshot, NewsArticle, WatchlistEntry


def summarize_development(
    article: NewsArticle,
    event_type: str,
    entry: WatchlistEntry,
    market_snapshot: MarketSnapshot | None,
) -> tuple[str, str]:
    """Create a short summary and business relevance note."""

    company = entry.company_name or entry.ticker
    headline = article.headline.rstrip(".")
    base = article.summary or headline
    concise_summary = _clip_sentence(f"{company}: {base}", max_chars=150)

    move_context = ""
    if market_snapshot is not None and abs(market_snapshot.change_percent) >= entry.alert_threshold:
        direction = "up" if market_snapshot.change_percent > 0 else "down"
        move_context = f" Shares {direction} {abs(market_snapshot.change_percent):.1f}% today."

    why = {
        "earnings": "Check estimate revisions and guidance read-through.",
        "management change": "Watch execution priorities and investor confidence.",
        "financing": "Review dilution, leverage, and liquidity impact.",
        "litigation": "Size legal, regulatory, and headline risk.",
        "M&A": "Assess strategic fit, integration risk, and earnings impact.",
        "macro/sector": "Track demand, cost, or policy read-through.",
        "other": "Review for thesis or position-size impact.",
    }.get(event_type, "Review for thesis or position-size impact.")

    return concise_summary, f"{why}{move_context}"


def _clip_sentence(text: str, max_chars: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."
