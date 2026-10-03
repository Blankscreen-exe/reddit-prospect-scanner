from __future__ import annotations

from pathlib import Path
from typing import Any

from reddit_prospect_radar.config import load_config
from reddit_prospect_radar.paths import AppPaths
from tests.support import WriteConfig


def test_relative_paths_resolve_against_root(config_dir: Path) -> None:
    root = config_dir.parent
    paths = AppPaths.from_config(load_config(config_dir), root)

    assert paths.data_dir == root.resolve() / "data"
    assert paths.db_file == root.resolve() / "data" / "prospect_radar.db"
    assert paths.log_file.parent == paths.log_dir
    assert paths.browser_profile_dir == root.resolve() / "data" / "browser_profile"


def test_absolute_paths_are_kept(
    tmp_path: Path, config_data: dict[str, Any], write_config: WriteConfig
) -> None:
    elsewhere = tmp_path / "elsewhere"
    config_data["storage"]["data_dir"] = str(elsewhere)
    config_dir = write_config(config_data)

    paths = AppPaths.from_config(load_config(config_dir), config_dir.parent)

    assert paths.data_dir == elsewhere
    assert paths.snapshot_dir == elsewhere / "snapshots"


def test_ensure_dirs_creates_everything(config_dir: Path) -> None:
    paths = AppPaths.from_config(load_config(config_dir), config_dir.parent)

    paths.ensure_dirs()
    paths.ensure_dirs()  # idempotent

    assert all(directory.is_dir() for directory in paths.runtime_dirs)
