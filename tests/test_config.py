from __future__ import annotations

from datetime import time
from pathlib import Path
from typing import Any

import pytest

from reddit_prospect_radar.config import (
    ConfigError,
    SearchSource,
    SubredditNewSource,
    load_config,
    load_secrets,
)
from tests.support import WriteConfig


def test_shipped_config_is_valid(config_dir: Path) -> None:
    config = load_config(config_dir)

    assert config.collector.base == "https://old.reddit.com"
    assert config.collector.logged_in is False
    assert config.collector.quiet_hours == (time(1, 0), time(6, 0))
    assert config.notify.daily_digest_time == time(21, 0)
    assert config.ml.mode == "similarity"
    assert config.weights.similarity_zeroshot.zeroshot == pytest.approx(0.35)
    assert len(config.collector.sources) == 12


def test_sources_parse_by_type(config_dir: Path) -> None:
    sources = load_config(config_dir).collector.sources

    assert isinstance(sources[0], SubredditNewSource)
    assert sources[0].key == "subreddit_new:saas"
    assert isinstance(sources[-1], SearchSource)
    assert sources[-1].key == 'search:new:"technical cofounder"'


def test_search_source_defaults_and_scope() -> None:
    source = SearchSource(type="search", query="need a cto", subreddit="Startups")

    assert source.sort == "new"
    assert source.key == "search:new:r/startups:need a cto"


def test_quiet_hours_can_be_disabled(
    config_data: dict[str, Any], write_config: WriteConfig
) -> None:
    config_data["collector"]["quiet_hours"] = None

    assert load_config(write_config(config_data)).collector.quiet_hours is None


def _set(data: dict[str, Any], dotted: str, value: Any) -> None:
    *parents, last = dotted.split(".")
    for key in parents:
        data = data[key]
    data[last] = value


@pytest.mark.parametrize(
    ("dotted_key", "value", "expected_message"),
    [
        ("collector.logged_in", True, "collector.logged_in: Value error, must stay false"),
        ("collector.base", "https://reddit.com", "collector.base"),
        ("collector.min_delay_s", 20, "min_delay_s must not exceed max_delay_s"),
        ("collector.min_delay_s", 0, "collector.min_delay_s: Input should be greater than 0"),
        ("collector.cycle_jitter_min", 20, "cycle_jitter_min must be less than"),
        ("collector.quiet_hours", ["01:00", "01:00"], "start and end must differ"),
        ("collector.quiet_hours", [3600, "06:00"], 'quoted 24-hour time "HH:MM"'),
        ("collector.quiet_hours", ["25:00", "06:00"], 'quoted 24-hour time "HH:MM"'),
        ("collector.sources", [], "collector.sources: List should have at least 1 item"),
        ("thresholds.notify", 1.5, "thresholds.notify: Input should be less than or equal to 1"),
        ("ml.mode", "magic", "ml.mode"),
        ("weights.similarity.embedding", 0.5, "weights must sum to 1, got 0.85"),
        ("weights.classifier.extra", 0.0, "weights.classifier.extra: Extra inputs"),
        ("notify.daily_digest_time", 1260, 'quoted 24-hour time "HH:MM"'),
        ("draft.model", "  ", "draft.model: String should have at least 1 character"),
        ("logging.level", "LOUD", "logging.level"),
        ("unexpected_section", {}, "unexpected_section: Extra inputs are not permitted"),
    ],
)
def test_invalid_values_are_rejected(
    config_data: dict[str, Any],
    write_config: WriteConfig,
    dotted_key: str,
    value: Any,
    expected_message: str,
) -> None:
    _set(config_data, dotted_key, value)

    with pytest.raises(ConfigError) as excinfo:
        load_config(write_config(config_data))

    assert expected_message in str(excinfo.value)
    assert "config.yaml" in str(excinfo.value)


def test_missing_section_is_rejected(
    config_data: dict[str, Any], write_config: WriteConfig
) -> None:
    del config_data["thresholds"]

    with pytest.raises(ConfigError, match="thresholds: Field required"):
        load_config(write_config(config_data))


def test_every_problem_is_reported(config_data: dict[str, Any], write_config: WriteConfig) -> None:
    config_data["collector"]["logged_in"] = True
    config_data["thresholds"]["notify"] = -1

    with pytest.raises(ConfigError) as excinfo:
        load_config(write_config(config_data))

    assert len(str(excinfo.value).splitlines()) == 2


@pytest.mark.parametrize(
    "source",
    [
        {"type": "subreddit_new", "name": "r/SaaS"},
        {"type": "search", "query": ""},
        {"type": "search", "query": "x", "sort": "random"},
        {"type": "rss", "url": "https://example.com"},
    ],
)
def test_invalid_sources_are_rejected(
    config_data: dict[str, Any], write_config: WriteConfig, source: dict[str, Any]
) -> None:
    config_data["collector"]["sources"].append(source)

    with pytest.raises(ConfigError, match=r"collector\.sources\.12"):
        load_config(write_config(config_data))


def test_duplicate_sources_are_rejected(
    config_data: dict[str, Any], write_config: WriteConfig
) -> None:
    sources = config_data["collector"]["sources"]
    sources.append({"type": "subreddit_new", "name": "saas"})  # names are case-insensitive

    with pytest.raises(ConfigError, match="duplicate sources: subreddit_new:saas"):
        load_config(write_config(config_data))


def test_loaded_config_is_immutable(config_dir: Path) -> None:
    config = load_config(config_dir)

    with pytest.raises(ValueError, match="frozen"):
        config.collector.headless = False  # type: ignore[misc]


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="file not found"):
        load_config(tmp_path)


def test_malformed_yaml(config_dir: Path) -> None:
    (config_dir / "config.yaml").write_text("collector: [unclosed", encoding="utf-8")

    with pytest.raises(ConfigError, match="invalid YAML"):
        load_config(config_dir)


def test_top_level_must_be_mapping(config_dir: Path) -> None:
    (config_dir / "config.yaml").write_text("- a\n- b\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="top level must be a mapping"):
        load_config(config_dir)


class TestSecrets:
    def test_reads_env_file(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(
            "TELEGRAM_BOT_TOKEN=abc:123\nTELEGRAM_CHAT_ID=-1001\nANTHROPIC_API_KEY=\n",
            encoding="utf-8",
        )

        secrets = load_secrets(env_file)

        assert secrets.telegram_bot_token is not None
        assert secrets.telegram_bot_token.get_secret_value() == "abc:123"
        assert secrets.telegram_chat_id == -1001
        assert secrets.anthropic_api_key is None

    def test_environment_overrides_env_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("TELEGRAM_CHAT_ID=1\n", encoding="utf-8")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "2")

        assert load_secrets(env_file).telegram_chat_id == 2

    def test_missing_env_file_is_allowed(self, tmp_path: Path) -> None:
        secrets = load_secrets(tmp_path / ".env")

        assert secrets.telegram_bot_token is None

    def test_secrets_are_masked(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("TELEGRAM_BOT_TOKEN=very-secret\n", encoding="utf-8")

        assert "very-secret" not in repr(load_secrets(env_file))

    def test_invalid_chat_id(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("TELEGRAM_CHAT_ID=not-a-number\n", encoding="utf-8")

        with pytest.raises(ConfigError, match="telegram_chat_id"):
            load_secrets(env_file)
