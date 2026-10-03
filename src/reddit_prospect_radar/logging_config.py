"""Logging setup: a rotating log file plus the console."""

from __future__ import annotations

import logging.config
from pathlib import Path

from reddit_prospect_radar.config import LoggingConfig

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_BYTES_PER_MB = 1024 * 1024


def configure_logging(config: LoggingConfig, log_file: Path, *, verbose: bool = False) -> None:
    """Configure the root logger. Safe to call more than once; handlers are replaced.

    ``verbose`` lowers the level to DEBUG for this process regardless of config.
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)
    level = "DEBUG" if verbose else config.level
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"standard": {"format": _FORMAT}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "stream": "ext://sys.stderr",
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "standard",
                    "filename": str(log_file),
                    "maxBytes": config.max_file_mb * _BYTES_PER_MB,
                    "backupCount": config.backup_count,
                    "encoding": "utf-8",
                },
            },
            "root": {"level": level, "handlers": ["console", "file"]},
        }
    )
