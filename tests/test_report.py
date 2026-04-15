from datetime import date, datetime, timezone
from pathlib import Path

from models import BriefingRun
from services.report import save_briefing_artifacts


def _briefing() -> BriefingRun:
    return BriefingRun(
        run_id="briefing_20260415_120000Z",
        generated_at=datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc),
        run_date=date(2026, 4, 15),
        tickers=[],
    )


def test_default_save_removes_only_old_generated_briefing_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    old_html = output_dir / "briefing_20260414_120000Z.html"
    old_json = output_dir / "briefing_20260414_120000Z.json"
    gitkeep = output_dir / ".gitkeep"
    log_file = output_dir / "briefing_20260414_120000Z.log"
    manual_file = output_dir / "manual_notes.html"

    old_html.write_text("old html", encoding="utf-8")
    old_json.write_text("{}", encoding="utf-8")
    gitkeep.write_text("", encoding="utf-8")
    log_file.write_text("log", encoding="utf-8")
    manual_file.write_text("notes", encoding="utf-8")

    artifacts = save_briefing_artifacts(_briefing(), output_dir)

    assert artifacts.html_path == output_dir / "latest.html"
    assert artifacts.json_path == output_dir / "latest.json"
    assert artifacts.html_path.exists()
    assert artifacts.json_path.exists()
    assert sorted(path.name for path in artifacts.removed_paths) == [
        old_html.name,
        old_json.name,
    ]
    assert not old_html.exists()
    assert not old_json.exists()
    assert gitkeep.exists()
    assert log_file.exists()
    assert manual_file.exists()
    assert not (output_dir / "briefing_20260415_120000Z.html").exists()
    assert not (output_dir / "briefing_20260415_120000Z.json").exists()


def test_keep_history_preserves_generated_briefings_and_updates_latest(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    old_html = output_dir / "briefing_20260414_120000Z.html"
    old_json = output_dir / "briefing_20260414_120000Z.json"
    old_html.write_text("old html", encoding="utf-8")
    old_json.write_text("{}", encoding="utf-8")

    artifacts = save_briefing_artifacts(_briefing(), output_dir, keep_history=True)

    assert artifacts.html_path == output_dir / "briefing_20260415_120000Z.html"
    assert artifacts.json_path == output_dir / "briefing_20260415_120000Z.json"
    assert artifacts.latest_html_path == output_dir / "latest.html"
    assert artifacts.latest_json_path == output_dir / "latest.json"
    assert artifacts.removed_paths == ()
    assert old_html.exists()
    assert old_json.exists()
    assert artifacts.html_path.read_text(encoding="utf-8") == artifacts.latest_html_path.read_text(
        encoding="utf-8"
    )
    assert artifacts.json_path.read_text(encoding="utf-8") == artifacts.latest_json_path.read_text(
        encoding="utf-8"
    )
