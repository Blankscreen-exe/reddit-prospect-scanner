"""Configuration models and loaders.

Tunable behaviour lives in YAML files in the config directory and secrets live in
``.env``. Everything is validated on load: invalid configuration raises
:class:`ConfigError` with one line per problem, so the program fails fast.
"""

from __future__ import annotations

import math
import re
from datetime import time
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    SecretStr,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_FILENAME = "config.yaml"
ENV_FILENAME = ".env"


class ConfigError(Exception):
    """Configuration is missing, unreadable, or invalid."""


# --- Shared field types -------------------------------------------------------

_CLOCK_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _parse_clock(value: Any) -> time:
    # YAML 1.1 reads an unquoted 21:00 as the integer 1260, so insist on a string.
    if isinstance(value, time):
        return value
    if not isinstance(value, str) or not _CLOCK_PATTERN.match(value):
        raise ValueError('must be a quoted 24-hour time "HH:MM"')
    return time.fromisoformat(value)


ClockTime = Annotated[time, BeforeValidator(_parse_clock)]
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
SubredditName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_]{2,21}$")]
UnitFloat = Annotated[float, Field(ge=0.0, le=1.0)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- collector ---------------------------------------------------------------


class SubredditNewSource(_Model):
    """Newest posts of one subreddit."""

    type: Literal["subreddit_new"]
    name: SubredditName

    @property
    def key(self) -> str:
        """Stable identifier stored in ``posts.source``."""
        return f"subreddit_new:{self.name.lower()}"


class SearchSource(_Model):
    """Site-wide search, optionally restricted to one subreddit."""

    type: Literal["search"]
    query: NonEmptyStr
    sort: Literal["relevance", "hot", "top", "new", "comments"] = "new"
    subreddit: SubredditName | None = None

    @property
    def key(self) -> str:
        """Stable identifier stored in ``posts.source``."""
        scope = f"r/{self.subreddit.lower()}:" if self.subreddit else ""
        return f"search:{self.sort}:{scope}{self.query}"


Source = Annotated[SubredditNewSource | SearchSource, Field(discriminator="type")]


class CollectorConfig(_Model):
    base: Literal["https://old.reddit.com", "https://www.reddit.com"]
    headless: bool
    user_data_dir: Path
    logged_in: bool
    min_delay_s: PositiveFloat
    max_delay_s: PositiveFloat
    max_pages_per_cycle: PositiveInt
    max_post_age_hours: PositiveInt
    cycle_interval_min: PositiveInt
    cycle_jitter_min: NonNegativeInt
    quiet_hours: tuple[ClockTime, ClockTime] | None
    sources: list[Source] = Field(min_length=1)

    @field_validator("logged_in")
    @classmethod
    def _must_be_logged_out(cls, value: bool) -> bool:
        if value:
            raise ValueError("must stay false: collection is always logged-out")
        return value

    @field_validator("quiet_hours")
    @classmethod
    def _quiet_hours_not_empty(cls, value: tuple[time, time] | None) -> tuple[time, time] | None:
        if value is not None and value[0] == value[1]:
            raise ValueError("start and end must differ; use null to disable quiet hours")
        return value

    @model_validator(mode="after")
    def _check_consistency(self) -> CollectorConfig:
        if self.min_delay_s > self.max_delay_s:
            raise ValueError("min_delay_s must not exceed max_delay_s")
        if self.cycle_jitter_min >= self.cycle_interval_min:
            raise ValueError("cycle_jitter_min must be less than cycle_interval_min")
        keys = [source.key for source in self.sources]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise ValueError(f"duplicate sources: {', '.join(duplicates)}")
        return self


# --- scoring -----------------------------------------------------------------


class ThresholdsConfig(_Model):
    fetch_body: int
    ml_stage: int
    notify: UnitFloat


MLMode = Literal["similarity", "similarity+zeroshot", "classifier"]


class MLConfig(_Model):
    mode: MLMode
    embedding_model: NonEmptyStr
    zeroshot_model: NonEmptyStr
    max_chars: PositiveInt
    classifier_min_labels: PositiveInt


class _ModeWeights(_Model):
    @model_validator(mode="after")
    def _sum_to_one(self) -> _ModeWeights:
        total = math.fsum(self.model_dump().values())
        if not math.isclose(total, 1.0, abs_tol=1e-9):
            raise ValueError(f"weights must sum to 1, got {total:g}")
        return self


class SimilarityWeights(_ModeWeights):
    rules: UnitFloat
    embedding: UnitFloat


class SimilarityZeroshotWeights(_ModeWeights):
    rules: UnitFloat
    embedding: UnitFloat
    zeroshot: UnitFloat


class ClassifierWeights(_ModeWeights):
    rules: UnitFloat
    classifier: UnitFloat


class WeightsConfig(_Model):
    similarity: SimilarityWeights
    similarity_zeroshot: SimilarityZeroshotWeights = Field(alias="similarity+zeroshot")
    classifier: ClassifierWeights


# --- outputs -----------------------------------------------------------------


class NotifyConfig(_Model):
    telegram_enabled: bool
    daily_digest_time: ClockTime
    max_notifications_per_day: PositiveInt


class DraftConfig(_Model):
    enabled: bool
    model: NonEmptyStr
    max_tokens: PositiveInt
    on_demand_only: bool


# --- runtime -----------------------------------------------------------------


class StorageConfig(_Model):
    data_dir: Path


class LoggingConfig(_Model):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    max_file_mb: PositiveInt
    backup_count: NonNegativeInt


class AppConfig(_Model):
    """Contents of ``config.yaml``."""

    collector: CollectorConfig
    thresholds: ThresholdsConfig
    ml: MLConfig
    weights: WeightsConfig
    notify: NotifyConfig
    draft: DraftConfig
    storage: StorageConfig
    logging: LoggingConfig


class Secrets(BaseSettings):
    """Secrets from environment variables, falling back to ``.env``.

    All are optional here; each feature checks for the secrets it needs when it starts.
    """

    model_config = SettingsConfigDict(extra="ignore", frozen=True, env_ignore_empty=True)

    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: int | None = None
    anthropic_api_key: SecretStr | None = None


# --- loaders -----------------------------------------------------------------


def load_config(config_dir: Path) -> AppConfig:
    """Load and validate ``config.yaml`` from ``config_dir``."""
    path = config_dir / CONFIG_FILENAME
    data = read_yaml_mapping(path)
    try:
        return AppConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(format_validation_error(path, exc)) from exc


def load_secrets(env_file: Path) -> Secrets:
    """Load secrets from the environment and ``env_file`` (if it exists)."""
    try:
        return Secrets(_env_file=env_file)
    except ValidationError as exc:
        raise ConfigError(format_validation_error(env_file, exc)) from exc


def read_yaml_mapping(path: Path) -> dict[str, Any]:
    """Read a YAML file whose top level must be a mapping."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(f"{path}: file not found") from exc
    except OSError as exc:
        raise ConfigError(f"{path}: cannot read file: {exc}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    return data


def format_validation_error(path: Path, exc: ValidationError) -> str:
    """Render a pydantic error as one ``file: location: message`` line per problem."""
    lines = []
    for error in exc.errors(include_url=False):
        location = ".".join(str(part) for part in error["loc"]) or "<root>"
        lines.append(f"{path}: {location}: {error['msg']}")
    return "\n".join(lines)
