"""Filesystem locations derived from configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reddit_prospect_radar.config import AppConfig

DB_FILENAME = "prospect_radar.db"
LOG_FILENAME = "prospect_radar.log"


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Absolute paths used at runtime. Relative config paths resolve against ``root``."""

    root: Path
    data_dir: Path
    db_file: Path
    log_dir: Path
    log_file: Path
    snapshot_dir: Path
    model_dir: Path
    browser_profile_dir: Path

    @classmethod
    def from_config(cls, config: AppConfig, root: Path) -> AppPaths:
        root = root.resolve()
        data_dir = root / config.storage.data_dir
        log_dir = data_dir / "logs"
        return cls(
            root=root,
            data_dir=data_dir,
            db_file=data_dir / DB_FILENAME,
            log_dir=log_dir,
            log_file=log_dir / LOG_FILENAME,
            snapshot_dir=data_dir / "snapshots",
            model_dir=data_dir / "models",
            browser_profile_dir=root / config.collector.user_data_dir,
        )

    @property
    def runtime_dirs(self) -> tuple[Path, ...]:
        """Directories the program writes into."""
        return (
            self.data_dir,
            self.log_dir,
            self.snapshot_dir,
            self.model_dir,
            self.browser_profile_dir,
        )

    def ensure_dirs(self) -> None:
        """Create every runtime directory that does not exist yet."""
        for directory in self.runtime_dirs:
            directory.mkdir(parents=True, exist_ok=True)
