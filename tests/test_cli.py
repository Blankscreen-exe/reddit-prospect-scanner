from __future__ import annotations

from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from reddit_prospect_radar import __version__
from reddit_prospect_radar.cli import EXIT_CONFIG_ERROR, app
from tests.support import WriteConfig

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == __version__


def test_init_db_creates_database_and_folders(config_dir: Path) -> None:
    result = runner.invoke(app, ["--config-dir", str(config_dir), "init-db"])

    data_dir = config_dir.parent / "data"
    assert result.exit_code == 0, result.output
    assert (data_dir / "prospect_radar.db").is_file()
    for name in ("logs", "snapshots", "models", "browser_profile"):
        assert (data_dir / name).is_dir()
    assert "schema version 1" in (data_dir / "logs" / "prospect_radar.log").read_text("utf-8")


def test_config_dir_from_environment(config_dir: Path) -> None:
    result = runner.invoke(app, ["init-db"], env={"PROSPECT_RADAR_CONFIG_DIR": str(config_dir)})

    assert result.exit_code == 0, result.output
    assert (config_dir.parent / "data" / "prospect_radar.db").is_file()


def test_invalid_config_fails_fast(config_data: dict[str, Any], write_config: WriteConfig) -> None:
    config_data["collector"]["logged_in"] = True
    config_dir = write_config(config_data)

    result = runner.invoke(app, ["--config-dir", str(config_dir), "init-db"])

    assert result.exit_code == EXIT_CONFIG_ERROR
    assert "Invalid configuration" in result.output
    assert "collector.logged_in" in result.output
    assert not (config_dir.parent / "data").exists()
