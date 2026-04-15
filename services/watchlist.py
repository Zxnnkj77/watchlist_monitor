"""Watchlist file parsing."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml

from models import WatchlistEntry


def load_watchlist(path: Path) -> list[WatchlistEntry]:
    """Load watchlist entries from a YAML or CSV file."""

    if not path.exists():
        raise FileNotFoundError(f"Watchlist file not found: {path}")

    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return _load_yaml(path)
    if suffix == ".csv":
        return _load_csv(path)
    raise ValueError("Watchlist must be a .yaml, .yml, or .csv file")


def _load_yaml(path: Path) -> list[WatchlistEntry]:
    with path.open("r", encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}

    raw_entries = payload.get("watchlist", payload)
    if not isinstance(raw_entries, list):
        raise ValueError("YAML watchlist must contain a list or a 'watchlist' list")

    return [_entry_from_mapping(item) for item in raw_entries]


def _load_csv(path: Path) -> list[WatchlistEntry]:
    with path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    return [_entry_from_mapping(row) for row in rows]


def _entry_from_mapping(raw: dict[str, Any]) -> WatchlistEntry:
    ticker = str(raw.get("ticker", "")).strip().upper()
    if not ticker:
        raise ValueError(f"Watchlist entry is missing ticker: {raw}")

    threshold = raw.get("alert_threshold", raw.get("alert_threshold_percent", 5.0))
    return WatchlistEntry(
        ticker=ticker,
        company_name=_clean_optional(raw.get("company_name") or raw.get("name")),
        sector=_clean_optional(raw.get("sector")),
        alert_threshold=float(threshold or 5.0),
    )


def _clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None
