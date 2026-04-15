"""Market data provider interfaces and implementations."""

from __future__ import annotations

import hashlib
import logging
from typing import Protocol

import requests

from models import MarketSnapshot, WatchlistEntry

LOGGER = logging.getLogger(__name__)

try:
    import yfinance as yf
except ImportError:  # pragma: no cover - exercised when optional dependency is absent
    yf = None


class MarketDataProvider(Protocol):
    """Interface for fetching market data."""

    def get_snapshot(self, entry: WatchlistEntry) -> MarketSnapshot:
        """Fetch a current market snapshot for a watchlist entry."""


class MockMarketDataProvider:
    """Deterministic mock market data for local development and tests."""

    def get_snapshot(self, entry: WatchlistEntry) -> MarketSnapshot:
        seed = int(hashlib.sha256(entry.ticker.encode("utf-8")).hexdigest()[:8], 16)
        previous_close = round(80 + (seed % 22000) / 100, 2)
        change_percent = round(((seed % 1500) / 100) - 7.5, 2)
        price = round(previous_close * (1 + change_percent / 100), 2)
        volume = 750_000 + seed % 8_000_000
        market_cap = round(price * (200_000_000 + seed % 1_500_000_000), 2)
        return MarketSnapshot(
            ticker=entry.ticker,
            price=price,
            previous_close=previous_close,
            change_percent=change_percent,
            volume=volume,
            market_cap=market_cap,
            source="mock",
        )


class AlphaVantageMarketDataProvider:
    """Market data provider backed by Alpha Vantage's Global Quote endpoint."""

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str, timeout_seconds: int = 10) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def get_snapshot(self, entry: WatchlistEntry) -> MarketSnapshot:
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": entry.ticker,
            "apikey": self.api_key,
        }
        response = requests.get(self.BASE_URL, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        quote = payload.get("Global Quote") or {}
        if not quote:
            raise RuntimeError(f"Alpha Vantage returned no quote for {entry.ticker}")

        price = float(quote["05. price"])
        previous_close = float(quote["08. previous close"])
        raw_percent = str(quote["10. change percent"]).replace("%", "")
        return MarketSnapshot(
            ticker=entry.ticker,
            price=price,
            previous_close=previous_close,
            change_percent=float(raw_percent),
            volume=int(quote.get("06. volume") or 0),
            source="alpha_vantage",
        )


class YahooFinanceMarketDataProvider:
    """Market data provider backed by Yahoo Finance through yfinance."""

    def get_snapshot(self, entry: WatchlistEntry) -> MarketSnapshot:
        if yf is None:
            raise RuntimeError("yfinance is required for Yahoo Finance market data")

        ticker = yf.Ticker(entry.ticker)
        fast_info = ticker.fast_info
        price = _float_value(_lookup(fast_info, "last_price", "lastPrice"))
        previous_close = _float_value(_lookup(fast_info, "previous_close", "previousClose"))
        volume = _int_value(_lookup(fast_info, "last_volume", "lastVolume", "volume"))

        if price is None or previous_close is None:
            history = ticker.history(period="5d")
            if history.empty:
                raise RuntimeError(f"Yahoo Finance returned no quote for {entry.ticker}")
            price = price if price is not None else float(history["Close"].iloc[-1])
            if previous_close is None:
                previous_close = float(history["Close"].iloc[-2] if len(history) > 1 else history["Close"].iloc[-1])
            if volume is None and "Volume" in history:
                volume = int(history["Volume"].iloc[-1])

        change_percent = 0.0
        if previous_close:
            change_percent = ((price - previous_close) / previous_close) * 100

        return MarketSnapshot(
            ticker=entry.ticker,
            price=round(price, 2),
            previous_close=round(previous_close, 2),
            change_percent=round(change_percent, 2),
            volume=volume,
            source="Yahoo Finance",
        )


class FallbackMarketDataProvider:
    """Try a primary provider, then fall back to mock data if it fails."""

    def __init__(self, primary: MarketDataProvider, fallback: MarketDataProvider) -> None:
        self.primary = primary
        self.fallback = fallback

    def get_snapshot(self, entry: WatchlistEntry) -> MarketSnapshot:
        try:
            return self.primary.get_snapshot(entry)
        except Exception as exc:  # noqa: BLE001 - provider boundaries should not crash the run
            LOGGER.warning("Market provider failed for %s; using mock data: %s", entry.ticker, exc)
            return self.fallback.get_snapshot(entry)


def build_market_data_provider(mode: str, alpha_vantage_api_key: str | None) -> MarketDataProvider:
    """Create a market data provider from runtime configuration."""

    mock = MockMarketDataProvider()
    if mode == "yahoo":
        return FallbackMarketDataProvider(YahooFinanceMarketDataProvider(), mock)
    if mode == "live" and alpha_vantage_api_key:
        return FallbackMarketDataProvider(AlphaVantageMarketDataProvider(alpha_vantage_api_key), mock)
    if mode == "auto" and alpha_vantage_api_key:
        return FallbackMarketDataProvider(AlphaVantageMarketDataProvider(alpha_vantage_api_key), mock)
    if mode == "live" and not alpha_vantage_api_key:
        LOGGER.warning("MARKET_DATA_MODE=live but ALPHA_VANTAGE_API_KEY is missing; using mock data")
    return mock


def _lookup(container, *names: str):
    for name in names:
        try:
            value = container[name]
        except (KeyError, TypeError):
            value = getattr(container, name, None)
        if value is not None:
            return value
    return None


def _float_value(value) -> float | None:
    if value is None:
        return None
    return float(value)


def _int_value(value) -> int | None:
    if value is None:
        return None
    return int(value)
