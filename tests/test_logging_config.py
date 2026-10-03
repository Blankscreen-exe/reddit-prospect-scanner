from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from reddit_prospect_radar.config import LoggingConfig
from reddit_prospect_radar.logging_config import configure_logging

CONFIG = LoggingConfig(level="WARNING", max_file_mb=2, backup_count=3)


def _file_handler() -> RotatingFileHandler:
    handlers = [h for h in logging.getLogger().handlers if isinstance(h, RotatingFileHandler)]
    assert len(handlers) == 1
    return handlers[0]


def test_writes_to_rotating_file(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "app.log"

    configure_logging(CONFIG, log_file)
    logging.getLogger("some.module").warning("hello file")
    logging.getLogger("some.module").info("below level")
    _file_handler().flush()

    content = log_file.read_text(encoding="utf-8")
    assert "WARNING  some.module: hello file" in content
    assert "below level" not in content
    assert _file_handler().maxBytes == 2 * 1024 * 1024
    assert _file_handler().backupCount == 3


def test_verbose_lowers_level(tmp_path: Path) -> None:
    configure_logging(CONFIG, tmp_path / "app.log", verbose=True)

    assert logging.getLogger().level == logging.DEBUG


def test_reconfiguring_replaces_handlers(tmp_path: Path) -> None:
    configure_logging(CONFIG, tmp_path / "a.log")
    configure_logging(CONFIG, tmp_path / "b.log")

    assert Path(_file_handler().baseFilename).name == "b.log"
