# Watchlist Monitor

A Python MVP for a watchlist-based market monitoring and daily briefing workflow.

The project reads a local stock watchlist, fetches market data and recent news, filters and ranks material developments, classifies event types, generates concise business summaries, and writes a daily HTML email briefing plus a structured JSON artifact.

This is intentionally not a dashboard. It is a small investing operations workflow that can run once from the command line or on the included daily GitHub Actions schedule.

## Architecture

```text
watchlist_monitor/
  main.py                  # CLI orchestration for one run
  config.py                # Environment-backed runtime configuration
  models.py                # Dataclasses for watchlist, market, news, and briefing output
  watchlist.yaml           # Sample local watchlist
  services/
    watchlist.py           # YAML/CSV watchlist parser
    market_data.py         # Market data provider interface, mock, Alpha Vantage, and Yahoo adapters
    news_data.py           # News provider factory and fallback wrapper
    aggregator.py          # Multi-source article merge, deduplication, and event clustering
    news_providers/        # Yahoo Finance, NewsAPI, Google News RSS, and mock providers
    relevance.py           # Filtering, source-aware ranking, near-duplicate detection, and scoring
    classify.py            # Rule-based event classification
    summarize.py           # Short businesslike summaries and why-it-matters notes
    report.py              # HTML email rendering and JSON/HTML artifact writing
    emailer.py             # Optional SMTP delivery
  outputs/                 # Generated HTML and JSON artifacts
  tests/                   # Focused unit tests
```

The system uses provider interfaces so real data sources can be swapped in without changing the processing or reporting layers. The default mode is `mock`, which requires no network access or API keys and gives deterministic laptop-friendly output. `NEWS_DATA_MODE=multi` turns on the aggregation pipeline across Yahoo Finance, NewsAPI, and Google News RSS.

## Setup

Use Python 3.11 or newer.

```bash
cd watchlist_monitor
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

The project can run without editing `.env` because mock data is enabled by default.

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `MARKET_DATA_MODE` | `mock`, `live`, `auto`, or `yahoo`. Defaults to `mock`. |
| `NEWS_DATA_MODE` | `mock`, `live`, `auto`, or `multi`. Defaults to `mock`. |
| `NEWS_SOURCES` | Comma-separated source list used by `NEWS_DATA_MODE=multi`. Supported values: `yahoo`, `newsapi`, `google`. Defaults to `yahoo,google`, which does not require NewsAPI. |
| `ALPHA_VANTAGE_API_KEY` | Used by the Alpha Vantage market data adapter. |
| `NEWSAPI_API_KEY` | Used by the NewsAPI adapter in `live`, `auto`, or `multi` mode when `newsapi` is enabled. |
| `OUTPUT_DIR` | Output folder for generated `.html` and `.json` artifacts. Defaults to `outputs`. |
| `KEEP_HISTORY` | Set to `true` to keep timestamped `briefing_*.html/json` archives. Defaults to `false`. |
| `SMTP_HOST` | SMTP server for optional email delivery. |
| `SMTP_PORT` | SMTP port. Defaults to `587`. |
| `SMTP_USERNAME` | Optional SMTP username. |
| `SMTP_PASSWORD` | Optional SMTP password. |
| `SMTP_FROM` | Sender address. |
| `SMTP_TO` | Recipient address. |
| `SMTP_USE_TLS` | Whether to start TLS. Defaults to `true`. |

If a real market or news provider fails, the run falls back to available providers or mock data and logs a warning. This keeps the daily workflow from failing completely because of one external outage.

## Watchlist Format

YAML:

```yaml
watchlist:
  - ticker: AAPL
    company_name: Apple Inc.
    sector: Technology Hardware
    alert_threshold: 3.0
```

CSV:

```csv
ticker,company_name,sector,alert_threshold
AAPL,Apple Inc.,Technology Hardware,3.0
```

`ticker` is required. `company_name`, `sector`, and `alert_threshold` are optional. The threshold is a daily percentage move that should trigger manual review.

## Run Once Manually

Mock mode:

```bash
python main.py
```

Explicit modes:

```bash
python main.py --market-data-mode mock --news-data-mode mock
python main.py --market-data-mode auto --news-data-mode auto
python main.py --market-data-mode yahoo --news-data-mode multi
```

Daily workflow with SMTP delivery:

```bash
python main.py \
  --market-data-mode yahoo \
  --news-data-mode multi \
  --send-email
```

Custom watchlist:

```bash
python main.py --watchlist path/to/watchlist.yaml
```

Send email after writing local artifacts:

```bash
python main.py --send-email
```

The command prints the generated HTML and JSON paths. The HTML file is the same content used as the email body.

## Local Artifacts

By default, each run writes only the latest local briefing files:

```text
outputs/latest.html
outputs/latest.json
```

Before saving a new run, the CLI removes old generated timestamped files in `outputs/` that match:

```text
briefing_*.html
briefing_*.json
```

Cleanup is limited to those generated briefing patterns inside `outputs/`. It does not delete `.gitkeep`, logs, watchlists, `.env`, tests, or manually named files such as `notes.html`.

To keep a timestamped archive later, set `KEEP_HISTORY=true` or pass `--keep-history`:

```bash
KEEP_HISTORY=true python main.py
python main.py --keep-history
```

History mode writes a timestamped pair for the run and also refreshes the convenience files:

```text
outputs/briefing_YYYYMMDD_HHMMSSZ.html
outputs/briefing_YYYYMMDD_HHMMSSZ.json
outputs/latest.html
outputs/latest.json
```

Use `outputs/latest.html` when you just want to open the newest report.

## GitHub Actions Daily Briefing

The repository includes `.github/workflows/daily_briefing.yml` to run the monitor automatically and by manual trigger.

The workflow:

- Runs from GitHub Actions on `ubuntu-latest`.
- Checks out the repository.
- Sets up Python 3.11.
- Installs dependencies with `python -m pip install -r requirements.txt`.
- Sets `NEWS_SOURCES=yahoo,google` so NewsAPI is not required.
- Sets `KEEP_HISTORY=false` and writes only the latest generated files inside the runner.
- Runs:

```bash
python main.py --market-data-mode yahoo --news-data-mode multi --send-email
```

For email delivery from GitHub Actions, add these required GitHub Secrets in the repository settings under **Settings > Secrets and variables > Actions > New repository secret**:

| Secret | Purpose |
| --- | --- |
| `SMTP_HOST` | SMTP server hostname, for example `smtp.gmail.com`. |
| `SMTP_FROM` | Sender email address. |
| `SMTP_TO` | Recipient email address. |

If your SMTP provider requires authentication, also add `SMTP_USERNAME` and `SMTP_PASSWORD`. The workflow sets `SMTP_PORT=587` and `SMTP_USE_TLS=true`. Change those values in `.github/workflows/daily_briefing.yml` if your SMTP provider requires a different port or TLS setting.

To trigger the workflow manually:

1. Open the repository on GitHub.
2. Go to **Actions**.
3. Select **Daily Watchlist Briefing**.
4. Click **Run workflow**.
5. Choose the branch and click **Run workflow** again.

### Schedule

GitHub Actions cron schedules are evaluated in UTC, not in a named timezone. To run at 8:00 AM `America/New_York`, the workflow has two schedule entries:

```yaml
- cron: "0 12 * * *"
- cron: "0 13 * * *"
```

`12:00 UTC` matches 8:00 AM in New York during daylight saving time. `13:00 UTC` matches 8:00 AM in New York during standard time. A schedule gate at the start of the job checks the current hour with `TZ=America/New_York` and only continues when the local hour is `08`, so one of the two scheduled runs skips each day.

## Testing

```bash
pytest
```

The included tests cover watchlist parsing, near-duplicate headline removal, relevance scoring, and low-value article filtering.

## Multi-Source Ranking

In `NEWS_DATA_MODE=multi`, the app fetches articles from the enabled providers, merges them into one feed, clusters similar headlines into event groups, and tracks which sources are covering each story. Each processed development keeps a representative article plus `source_count` and `sources`.

Ranking combines ticker/company mention strength, financial keywords, recency, and a source-count bonus. A story covered by multiple outlets ranks higher and is marked as high confidence in the HTML report with text such as `3 sources reporting: Reuters, CNBC, Yahoo Finance`.

## Gmail SMTP

For Gmail, create an app password for the sending account and configure:

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your.name@gmail.com
SMTP_PASSWORD=your-gmail-app-password
SMTP_FROM=your.name@gmail.com
SMTP_TO=recipient@example.com
SMTP_USE_TLS=true
```

## NewsAPI

Create a NewsAPI key and configure:

```dotenv
NEWS_DATA_MODE=multi
NEWS_SOURCES=yahoo,newsapi,google
NEWSAPI_API_KEY=your-newsapi-key
```

Yahoo Finance and Google News RSS do not require API keys and are the default multi-source providers. NewsAPI is optional and is skipped in multi-source mode if `NEWSAPI_API_KEY` is not set.

## What Works

- Local YAML and CSV watchlist parsing.
- Deterministic mock market data and mock news for laptop-friendly runs.
- Optional live adapters for Alpha Vantage market quotes and NewsAPI articles.
- Yahoo Finance market snapshots through yfinance.
- Multi-source news aggregation from Yahoo Finance, NewsAPI, and Google News RSS.
- Event clustering with source coverage counts and source lists.
- Filtering for low-value articles.
- Near-duplicate headline removal.
- Rule-based materiality scoring.
- Event classification across earnings, management change, financing, litigation, M&A, macro/sector, and other.
- Short summaries with a why-it-matters note.
- HTML email briefing rendering.
- Latest HTML and JSON local artifacts, with optional timestamped history.
- Optional SMTP delivery.

## Current Stubs And Limits

- Summarization is rule-based, not LLM-backed.
- Relevance and classification use keyword logic, not a trained model.
- Mock data is synthetic and deterministic.
- Yahoo Finance data depends on yfinance availability and Yahoo's upstream response shape.
- Google News RSS links may resolve through Google News redirect URLs.
- There is no database, position sizing, portfolio context, or authentication.

## What To Build Next

1. Replace keyword summarization with an LLM or a more structured extraction layer.
2. Add provider-specific tests using recorded fixtures.
3. Add SEC filings, press releases, and earnings calendar sources.
4. Track previous run state to detect new developments since the last briefing.
5. Add portfolio metadata such as position size, thesis, owner, and review priority.
6. Add alert routing for high-severity items through Slack, email labels, or ticketing.
