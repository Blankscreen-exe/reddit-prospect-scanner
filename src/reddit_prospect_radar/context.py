"""Application context: everything a command needs, loaded and validated once."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reddit_prospect_radar.config import ENV_FILENAME, AppConfig, Secrets, load_config, load_secrets
from reddit_prospect_radar.paths import AppPaths


@dataclass(frozen=True, slots=True)
class AppContext:
    config: AppConfig
    secrets: Secrets
    paths: AppPaths

    @classmethod
    def load(cls, config_dir: Path) -> AppContext:
        """Load config and secrets. The project root is the config directory's parent.

        Raises :class:`~reddit_prospect_radar.config.ConfigError` if anything is invalid.
        """
        config = load_config(config_dir)
        root = config_dir.resolve().parent
        return cls(
            config=config,
            secrets=load_secrets(root / ENV_FILENAME),
            paths=AppPaths.from_config(config, root),
        )
