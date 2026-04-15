"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is in requirements.txt
    load_dotenv = None


@dataclass(frozen=True)
class AppConfig:
    """Runtime settings for one briefing run."""

    output_dir: Path
    keep_history: bool
    market_data_mode: str
    news_data_mode: str
    news_sources: tuple[str, ...]
    alpha_vantage_api_key: str | None
    newsapi_api_key: str | None
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    smtp_from: str | None
    smtp_to: str | None
    smtp_use_tls: bool

    @property
    def email_is_configured(self) -> bool:
        """Return whether enough SMTP settings exist to send an email."""

        return bool(self.smtp_host and self.smtp_from and self.smtp_to)


def load_config(project_root: Path) -> AppConfig:
    """Load configuration from `.env` and process environment variables."""

    env_path = project_root / ".env"
    if load_dotenv is not None and env_path.exists():
        load_dotenv(env_path)

    return AppConfig(
        output_dir=_output_dir_from_env(project_root),
        keep_history=_bool_from_env("KEEP_HISTORY", default=False),
        market_data_mode=os.getenv("MARKET_DATA_MODE", "mock").lower(),
        news_data_mode=os.getenv("NEWS_DATA_MODE", "mock").lower(),
        news_sources=_news_sources_from_env(),
        alpha_vantage_api_key=os.getenv("ALPHA_VANTAGE_API_KEY") or None,
        newsapi_api_key=os.getenv("NEWSAPI_API_KEY") or None,
        smtp_host=os.getenv("SMTP_HOST") or None,
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_username=os.getenv("SMTP_USERNAME") or None,
        smtp_password=os.getenv("SMTP_PASSWORD") or None,
        smtp_from=os.getenv("SMTP_FROM") or None,
        smtp_to=os.getenv("SMTP_TO") or None,
        smtp_use_tls=os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"},
    )


def _output_dir_from_env(project_root: Path) -> Path:
    raw_value = os.getenv("OUTPUT_DIR")
    if not raw_value:
        return project_root / "outputs"
    path = Path(raw_value)
    return path if path.is_absolute() else project_root / path


def _news_sources_from_env() -> tuple[str, ...]:
    raw_value = os.getenv("NEWS_SOURCES", "yahoo,newsapi,google")
    sources = tuple(source.strip().lower() for source in raw_value.split(",") if source.strip())
    return sources or ("yahoo", "newsapi", "google")


def _bool_from_env(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}
