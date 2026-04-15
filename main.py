"""Command-line entrypoint for the watchlist monitoring MVP."""

from __future__ import annotations

import argparse
import logging
from dataclasses import replace
from datetime import timezone
from pathlib import Path

from config import load_config
from models import BriefingRun, ProcessedNewsItem, TickerBriefing, utc_now
from services.classify import classify_article
from services.emailer import send_email
from services.market_data import build_market_data_provider
from services.aggregator import cluster_articles
from services.news_data import build_news_data_provider
from services.relevance import filter_relevant_clusters
from services.report import render_html_email, save_briefing_artifacts
from services.summarize import summarize_development
from services.watchlist import load_watchlist

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""

    project_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Generate a daily watchlist market briefing.")
    parser.add_argument(
        "--watchlist",
        type=Path,
        default=project_root / "watchlist.yaml",
        help="Path to a YAML or CSV watchlist file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory where HTML and JSON artifacts should be written.",
    )
    parser.add_argument(
        "--market-data-mode",
        choices=["mock", "live", "auto", "yahoo"],
        default=None,
        help="Market data mode. Defaults to MARKET_DATA_MODE or mock.",
    )
    parser.add_argument(
        "--news-data-mode",
        choices=["mock", "live", "auto", "multi"],
        default=None,
        help="News data mode. Defaults to NEWS_DATA_MODE or mock.",
    )
    parser.add_argument(
        "--send-email",
        action="store_true",
        help="Send the generated briefing through SMTP if SMTP settings are configured.",
    )
    parser.add_argument(
        "--keep-history",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Keep timestamped briefing_*.html/json archives in addition to latest.html/json.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the briefing workflow once."""

    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    project_root = Path(__file__).resolve().parent
    config = load_config(project_root)
    if args.output_dir is not None:
        config = replace(config, output_dir=args.output_dir)
    if args.market_data_mode is not None:
        config = replace(config, market_data_mode=args.market_data_mode)
    if args.news_data_mode is not None:
        config = replace(config, news_data_mode=args.news_data_mode)
    if args.keep_history is not None:
        config = replace(config, keep_history=args.keep_history)

    watchlist = load_watchlist(args.watchlist)
    market_provider = build_market_data_provider(config.market_data_mode, config.alpha_vantage_api_key)
    news_provider = build_news_data_provider(config.news_data_mode, config.newsapi_api_key, config.news_sources)

    ticker_briefings: list[TickerBriefing] = []
    for entry in watchlist:
        LOGGER.info("Processing %s", entry.ticker)
        errors: list[str] = []

        try:
            snapshot = market_provider.get_snapshot(entry)
        except Exception as exc:  # noqa: BLE001 - continue one-ticker failures
            LOGGER.exception("Market data failed for %s", entry.ticker)
            snapshot = None
            errors.append(f"market_data: {exc}")

        try:
            if hasattr(news_provider, "fetch_recent_clusters"):
                event_clusters = news_provider.fetch_recent_clusters(entry)
            else:
                raw_articles = news_provider.fetch_recent(entry)
                event_clusters = cluster_articles(raw_articles)
        except Exception as exc:  # noqa: BLE001 - continue one-ticker failures
            LOGGER.exception("News fetch failed for %s", entry.ticker)
            event_clusters = []
            errors.append(f"news_data: {exc}")

        developments: list[ProcessedNewsItem] = []
        for event_cluster, relevance_score in filter_relevant_clusters(event_clusters, entry):
            article = event_cluster.representative_article
            event_type, signals = classify_article(article)
            concise_summary, why_it_matters = summarize_development(article, event_type, entry, snapshot)
            developments.append(
                ProcessedNewsItem(
                    article=article,
                    relevance_score=relevance_score,
                    event_type=event_type,
                    concise_summary=concise_summary,
                    why_it_matters=why_it_matters,
                    manual_review=_needs_manual_review(event_type, relevance_score),
                    signals=signals,
                    source_count=event_cluster.source_count,
                    sources=event_cluster.sources,
                )
            )

        ticker_briefings.append(
            TickerBriefing(
                watchlist_entry=entry,
                market_snapshot=snapshot,
                developments=developments,
                errors=errors,
            )
        )

    generated_at = utc_now()
    run_id = generated_at.astimezone(timezone.utc).strftime("briefing_%Y%m%d_%H%M%SZ")
    briefing = BriefingRun(
        run_id=run_id,
        generated_at=generated_at,
        run_date=generated_at.date(),
        tickers=ticker_briefings,
    )

    artifacts = save_briefing_artifacts(briefing, config.output_dir, keep_history=config.keep_history)
    LOGGER.info("Wrote HTML briefing to %s", artifacts.html_path)
    LOGGER.info("Wrote JSON artifact to %s", artifacts.json_path)
    if artifacts.removed_paths:
        LOGGER.info("Removed %s old generated briefing artifacts", len(artifacts.removed_paths))

    if args.send_email:
        html_body = render_html_email(briefing)
        send_email(config, f"Daily Watchlist Briefing - {briefing.run_date.isoformat()}", html_body)

    print(f"HTML briefing: {artifacts.html_path}")
    print(f"JSON artifact: {artifacts.json_path}")
    if config.keep_history:
        print(f"Latest HTML: {artifacts.latest_html_path}")
        print(f"Latest JSON: {artifacts.latest_json_path}")
    return 0


def _needs_manual_review(event_type: str, relevance_score: float) -> bool:
    high_touch_events = {"litigation", "financing", "M&A", "management change"}
    return event_type in high_touch_events or relevance_score >= 7.0


if __name__ == "__main__":
    raise SystemExit(main())
