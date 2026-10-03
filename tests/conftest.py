"""Shared fixtures."""

from __future__ import annotations

import logging
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.support import WriteConfig

REPO_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """A copy of the shipped config directory inside a temporary project root."""
    target = tmp_path / "config"
    shutil.copytree(REPO_CONFIG_DIR, target)
    return target


@pytest.fixture
def config_data(config_dir: Path) -> dict[str, Any]:
    """The shipped ``config.yaml`` as a mutable dict."""
    data: dict[str, Any] = yaml.safe_load((config_dir / "config.yaml").read_text("utf-8"))
    return data


@pytest.fixture
def write_config(config_dir: Path) -> WriteConfig:
    """Write a dict as ``config.yaml`` in the temporary config directory."""

    def write(data: dict[str, Any]) -> Path:
        (config_dir / "config.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
        return config_dir

    return write


@pytest.fixture(autouse=True)
def _restore_root_logger() -> Iterator[None]:
    """Undo logging configuration done by a test, closing any handlers it added."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    for handler in root.handlers:
        if handler not in handlers:
            handler.close()
    root.handlers[:] = handlers
    root.setLevel(level)


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep real secrets and config overrides in the environment out of tests."""
    for name in (
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "ANTHROPIC_API_KEY",
        "PROSPECT_RADAR_CONFIG_DIR",
    ):
        monkeypatch.delenv(name, raising=False)
