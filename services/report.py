"""HTML and JSON report generation."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path

from models import BriefingRun, TickerBriefing

GENERATED_BRIEFING_PATTERNS = ("briefing_*.html", "briefing_*.json")
LATEST_HTML_FILENAME = "latest.html"
LATEST_JSON_FILENAME = "latest.json"


@dataclass(frozen=True)
class BriefingArtifactPaths:
    """Paths written for one briefing run."""

    html_path: Path
    json_path: Path
    latest_html_path: Path
    latest_json_path: Path
    removed_paths: tuple[Path, ...]


def save_json_artifact(briefing: BriefingRun, output_dir: Path) -> Path:
    """Save a structured JSON artifact for the run."""

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{briefing.run_id}.json"
    with path.open("w", encoding="utf-8") as file:
        json.dump(briefing.to_json_dict(), file, indent=2)
    return path


def save_html_briefing(briefing: BriefingRun, output_dir: Path) -> Path:
    """Render and save the HTML email briefing."""

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{briefing.run_id}.html"
    path.write_text(render_html_email(briefing), encoding="utf-8")
    return path


def save_briefing_artifacts(
    briefing: BriefingRun,
    output_dir: Path,
    *,
    keep_history: bool = False,
) -> BriefingArtifactPaths:
    """Save the briefing artifacts for the default daily workflow.

    By default this keeps only stable latest files. When history is enabled,
    timestamped copies are also kept for archival use.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    removed_paths: tuple[Path, ...] = ()
    if not keep_history:
        removed_paths = cleanup_generated_briefing_artifacts(output_dir)

    latest_html_path = output_dir / LATEST_HTML_FILENAME
    latest_json_path = output_dir / LATEST_JSON_FILENAME
    html_path = output_dir / f"{briefing.run_id}.html" if keep_history else latest_html_path
    json_path = output_dir / f"{briefing.run_id}.json" if keep_history else latest_json_path

    html_text = render_html_email(briefing)
    json_text = json.dumps(briefing.to_json_dict(), indent=2)

    html_path.write_text(html_text, encoding="utf-8")
    json_path.write_text(json_text, encoding="utf-8")

    if keep_history:
        latest_html_path.write_text(html_text, encoding="utf-8")
        latest_json_path.write_text(json_text, encoding="utf-8")

    return BriefingArtifactPaths(
        html_path=html_path,
        json_path=json_path,
        latest_html_path=latest_html_path,
        latest_json_path=latest_json_path,
        removed_paths=removed_paths,
    )


def cleanup_generated_briefing_artifacts(output_dir: Path) -> tuple[Path, ...]:
    """Remove old generated timestamped briefing artifacts from an output directory."""

    if not output_dir.exists():
        return ()

    removed_paths: list[Path] = []
    for pattern in GENERATED_BRIEFING_PATTERNS:
        for path in output_dir.glob(pattern):
            if path.is_file():
                path.unlink()
                removed_paths.append(path)
    return tuple(sorted(removed_paths))


def render_html_email(briefing: BriefingRun) -> str:
    """Render the daily briefing as clean email-friendly HTML."""

    movers = _biggest_movers(briefing.tickers)
    risk_flags = _risk_flags(briefing.tickers)

    ticker_sections = "\n".join(_render_ticker_section(item) for item in briefing.tickers)
    movers_rows = "\n".join(_render_mover_row(item) for item in movers) or _empty_row("No market data available")
    risk_rows = "\n".join(_render_risk_row(item) for item in risk_flags) or _empty_row("No risk flags", colspan=3)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Daily Watchlist Briefing</title>
  <style>
    body {{ margin: 0; padding: 0; background: #f4f5f6; color: #24272a; font-family: Arial, Helvetica, sans-serif; }}
    .container {{ max-width: 920px; margin: 0 auto; padding: 28px 22px; }}
    .header {{ background: #ffffff; border: 1px solid #d6d9dd; border-top: 4px solid #22543d; border-radius: 8px; padding: 20px 22px; }}
    h1 {{ margin: 0 0 6px; font-size: 24px; letter-spacing: 0; }}
    h2 {{ margin: 28px 0 12px; font-size: 17px; color: #2f3438; }}
    h3 {{ margin: 0 0 8px; font-size: 16px; color: #1f2326; }}
    table {{ width: 100%; border-collapse: collapse; background: #ffffff; border: 1px solid #d6d9dd; border-radius: 8px; overflow: hidden; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #e5e7e9; text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ background: #ededee; color: #3f454a; font-size: 12px; text-transform: uppercase; letter-spacing: 0; }}
    tr:last-child td {{ border-bottom: 0; }}
    .ticker {{ background: #ffffff; border: 1px solid #d6d9dd; border-radius: 8px; padding: 16px 18px; margin-bottom: 14px; }}
    .ticker-head {{ display: flex; justify-content: space-between; gap: 16px; align-items: baseline; border-bottom: 1px solid #eceeef; padding-bottom: 10px; margin-bottom: 10px; }}
    .meta {{ color: #626a70; font-size: 13px; line-height: 1.45; }}
    .positive {{ color: #11723f; font-weight: bold; }}
    .negative {{ color: #b42318; font-weight: bold; }}
    .tag {{ display: inline-block; padding: 2px 7px; border-radius: 6px; background: #e7f3ee; color: #22543d; font-size: 12px; font-weight: bold; }}
    .manual {{ background: #fff0df; color: #9a4b00; }}
    .confidence {{ display: inline-block; padding: 2px 7px; border-radius: 6px; background: #ece6ff; color: #4b2f89; font-size: 12px; font-weight: bold; }}
    .development {{ border-left: 3px solid #c9cdd1; padding: 10px 0 10px 12px; margin: 8px 0; }}
    .high-confidence {{ border-left-color: #22543d; }}
    .headline {{ margin: 7px 0 5px; font-size: 15px; line-height: 1.4; }}
    .source-chip {{ display: inline-block; margin: 4px 4px 0 0; padding: 2px 7px; border: 1px solid #d6d9dd; border-radius: 6px; color: #3f454a; background: #fafafa; font-size: 12px; }}
    .score {{ color: #626a70; font-size: 12px; }}
    a {{ color: #0f5f8c; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Daily Watchlist Briefing</h1>
      <div class="meta">Generated {html.escape(briefing.generated_at.isoformat())} | Run {html.escape(briefing.run_id)}</div>
    </div>

    <h2>Biggest Movers</h2>
    <table>
      <tr><th>Ticker</th><th>Price</th><th>Move</th><th>Volume</th><th>Source</th></tr>
      {movers_rows}
    </table>

    <h2>Company Developments</h2>
    {ticker_sections}

    <h2>Review Flags</h2>
    <table>
      <tr><th>Ticker</th><th>Item</th><th>Reason</th></tr>
      {risk_rows}
    </table>
  </div>
</body>
</html>"""


def _biggest_movers(tickers: list[TickerBriefing]) -> list[TickerBriefing]:
    with_market = [item for item in tickers if item.market_snapshot is not None]
    return sorted(with_market, key=lambda item: abs(item.market_snapshot.change_percent), reverse=True)[:5]


def _risk_flags(tickers: list[TickerBriefing]) -> list[tuple[str, str, str]]:
    flags: list[tuple[str, str, str]] = []
    for item in tickers:
        snapshot = item.market_snapshot
        if snapshot and abs(snapshot.change_percent) >= item.watchlist_entry.alert_threshold:
            flags.append(
                (
                    item.watchlist_entry.ticker,
                    f"{snapshot.change_percent:+.2f}% price move",
                    f"Exceeded alert threshold of {item.watchlist_entry.alert_threshold:.1f}%",
                )
            )
        for development in item.developments:
            if development.manual_review:
                flags.append(
                    (
                        item.watchlist_entry.ticker,
                        development.article.headline,
                        f"{development.event_type}; score {development.relevance_score:.2f}",
                    )
                )
    return flags


def _render_ticker_section(item: TickerBriefing) -> str:
    entry = item.watchlist_entry
    snapshot = item.market_snapshot
    if snapshot:
        move_class = "positive" if snapshot.change_percent >= 0 else "negative"
        market = (
            f'<span class="{move_class}">{snapshot.change_percent:+.2f}%</span> '
            f'at ${snapshot.price:,.2f}; volume {snapshot.volume or 0:,}; source {html.escape(snapshot.source)}'
        )
    else:
        market = "Market data unavailable"

    if item.developments:
        developments = "\n".join(_render_development(dev) for dev in item.developments)
    else:
        developments = "<p class=\"meta\">No material developments found.</p>"

    errors = ""
    if item.errors:
        errors = "<p class=\"meta\">Errors: " + html.escape("; ".join(item.errors)) + "</p>"

    return f"""<div class="ticker">
  <div class="ticker-head">
    <h3>{html.escape(entry.ticker)} {html.escape(entry.company_name or "")}</h3>
    <div class="meta">{html.escape(entry.sector or "Sector not provided")}</div>
  </div>
  <div class="meta">{market}</div>
  {developments}
  {errors}
</div>"""


def _render_development(item) -> str:
    manual = '<span class="tag manual">manual review</span>' if item.manual_review else ""
    sources = item.sources or [item.article.source]
    source_count = item.source_count or len(sources)
    confidence = ""
    if source_count > 1:
        confidence = '<span class="confidence">high confidence</span>'
    source_label = f"{source_count} source{'s' if source_count != 1 else ''}"
    source_chips = _render_source_chips(sources)
    class_name = "development high-confidence" if source_count > 1 else "development"
    return f"""<div class="{class_name}">
  <span class="tag">{html.escape(item.event_type)}</span> {manual}
  {confidence}
  <div class="headline"><strong>{html.escape(item.concise_summary)}</strong></div>
  <div class="meta"><strong>Why it matters:</strong> {html.escape(item.why_it_matters)}</div>
  <div class="meta"><strong>{html.escape(source_label)}:</strong> {source_chips}
  <a href="{html.escape(item.article.url)}">Open representative story</a>
  <span class="score">Signal {item.relevance_score:.2f}</span></div>
</div>"""


def _render_source_chips(sources: list[str]) -> str:
    return "".join(f'<span class="source-chip">{html.escape(source)}</span>' for source in sources)


def _render_mover_row(item: TickerBriefing) -> str:
    snapshot = item.market_snapshot
    assert snapshot is not None
    move_class = "positive" if snapshot.change_percent >= 0 else "negative"
    return (
        "<tr>"
        f"<td>{html.escape(snapshot.ticker)}</td>"
        f"<td>${snapshot.price:,.2f}</td>"
        f'<td class="{move_class}">{snapshot.change_percent:+.2f}%</td>'
        f"<td>{snapshot.volume or 0:,}</td>"
        f"<td>{html.escape(snapshot.source)}</td>"
        "</tr>"
    )


def _render_risk_row(item: tuple[str, str, str]) -> str:
    ticker, headline, reason = item
    return (
        "<tr>"
        f"<td>{html.escape(ticker)}</td>"
        f"<td>{html.escape(headline)}</td>"
        f"<td>{html.escape(reason)}</td>"
        "</tr>"
    )


def _empty_row(message: str, colspan: int = 5) -> str:
    return f'<tr><td colspan="{colspan}">{html.escape(message)}</td></tr>'
