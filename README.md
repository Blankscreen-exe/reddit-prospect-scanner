# Reddit Prospect Radar

Finds people on Reddit who are publicly asking for help Gray Lining can provide, scores each post for buying intent, and alerts the owner on Telegram. It reads public pages only and never posts, comments, votes, or messages on Reddit.

The full specification is in [`docs/spec.md`](docs/spec.md). Implementation decisions are logged in [`docs/DECISIONS.md`](docs/DECISIONS.md).

> Status: under construction (milestone 1 of 10). This README is a stub and will be completed in milestone 10.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Quickstart

```bash
uv sync                          # create .venv and install dependencies
cp .env.example .env             # then fill in the values
uv run prospect-radar init-db    # create the database and data folders
```

With pip instead of uv:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
prospect-radar init-db
```

## Configuration

All tunable behaviour lives in `config/`:

| File | Purpose |
|---|---|
| `config/config.yaml` | Sources, pacing, thresholds, models, notifications, storage, logging |

Relative paths in `config.yaml` are resolved against the project root (the parent of the config directory). Use `--config-dir` or the `PROSPECT_RADAR_CONFIG_DIR` environment variable to point at a different config directory. Secrets are read from `.env` in the project root.

Invalid configuration stops every command with a list of the problems found.

## Development

```bash
uv run pytest          # tests
uv run ruff check .    # lint
uv run ruff format .   # format
uv run mypy            # type check
```
