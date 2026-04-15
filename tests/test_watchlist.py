from pathlib import Path

from services.watchlist import load_watchlist


def test_load_watchlist_yaml(tmp_path: Path) -> None:
    path = tmp_path / "watchlist.yaml"
    path.write_text(
        """
watchlist:
  - ticker: aapl
    company_name: Apple Inc.
    sector: Technology
    alert_threshold: 3.5
""",
        encoding="utf-8",
    )

    entries = load_watchlist(path)

    assert len(entries) == 1
    assert entries[0].ticker == "AAPL"
    assert entries[0].company_name == "Apple Inc."
    assert entries[0].sector == "Technology"
    assert entries[0].alert_threshold == 3.5


def test_load_watchlist_csv(tmp_path: Path) -> None:
    path = tmp_path / "watchlist.csv"
    path.write_text(
        "ticker,company_name,sector,alert_threshold\nmsft,Microsoft Corporation,Software,2.5\n",
        encoding="utf-8",
    )

    entries = load_watchlist(path)

    assert entries[0].ticker == "MSFT"
    assert entries[0].alert_threshold == 2.5
