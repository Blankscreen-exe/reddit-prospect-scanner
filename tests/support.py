"""Helpers shared by tests. Fixtures live in conftest.py."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

WriteConfig = Callable[[dict[str, Any]], Path]
"""Type of the ``write_config`` fixture."""
