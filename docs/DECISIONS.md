# Decisions

Running log of implementation decisions where `docs/spec.md` is silent, ambiguous, or overridden by the owner.

## 2026-10-03: Project name

The owner renamed the project from "Lead Radar" to **Reddit Prospect Radar**. Derived names: distribution `reddit-prospect-radar`, import package `reddit_prospect_radar`, CLI `prospect-radar`, database `data/prospect_radar.db`. The spec text is unchanged; references to `leadradar` map to these names. The spec stays at `docs/spec.md` instead of a root-level `SPEC.md`.

## 2026-10-04: Milestone 1 (skeleton)

**Dependencies beyond the spec's list (section 4).**
- `pyyaml`: the spec requires YAML config but names no parser. Loaded with `safe_load` only.
- `pydantic-settings`: reads secrets from environment variables and `.env` into typed, masked (`SecretStr`) fields. It's the official pydantic extension for this, which avoids a hand-rolled `.env` parser.
- `hatchling`: build backend (build-time only).
- Dev only: `ruff` (lint and format), `mypy` with `strict` and the pydantic plugin, `types-PyYAML`. These keep the code consistent and type-checked for future maintainers.

**Packaging.** `src/` layout, `uv` with a committed `uv.lock`. Dev tools are in a `[dependency-groups] dev` group; `pip install -e .` still works for runtime. Each later milestone adds its dependencies (Playwright, sentence-transformers and so on) when it first uses them.

**Config scope.** Milestone 1 validates `config.yaml` and `.env`. Schemas for `rules.yaml`, `examples.yaml` and `zeroshot.yaml` are added in `config.py` in the milestones that introduce those files (3, 5, 7), so each schema is designed with the code that consumes it.

**Config additions not in the spec.**
- `storage.data_dir` (default `data`): the database, logs, snapshots and models live in fixed subfolders of this directory. The database file is `prospect_radar.db`.
- `logging.level`, `logging.max_file_mb`, `logging.backup_count`: the spec requires rotating file logs but gives no settings. The `--verbose` CLI flag forces DEBUG.

**Config validation rules.**
- Every key is required, so the YAML file shows every setting explicitly. Unknown keys are errors, which catches typos.
- `collector.logged_in` must be `false` (spec 1.2).
- `collector.base` must be `https://old.reddit.com` or `https://www.reddit.com` (spec 6.1).
- `min_delay_s <= max_delay_s`, and `cycle_jitter_min < cycle_interval_min`, so the sleep time can never be zero or negative.
- Times must be quoted `"HH:MM"` strings, because YAML 1.1 reads an unquoted `21:00` as the integer 1260. `quiet_hours: null` disables quiet hours.
- Each mode's weights must sum to 1 (spec 6.1).
- Sources are a tagged union on `type`. Search sources take an optional `sort` (default `new`) and an optional `subreddit` (for `restrict_sr`, spec 8.1).
- Duplicate sources are rejected. Each source has a stable `key` (for example `subreddit_new:saas` or `search:new:"technical cofounder"`), which will be stored in `posts.source`.
- Secrets are all optional at load time. Each feature checks for the secrets it needs when it starts, so commands like `init-db` work without a Telegram token.

**Paths.** Relative paths resolve against the project root, which is the parent of the config directory. The config directory comes from `--config-dir` or `PROSPECT_RADAR_CONFIG_DIR`, defaulting to `./config`. This keeps the program independent of the current working directory (for example when started by Task Scheduler or systemd).

**Database.**
- Schema changes are numbered SQL files in `src/reddit_prospect_radar/migrations/`, tracked with `PRAGMA user_version`. Each migration runs in its own transaction. A database newer than the code is refused.
- Tables are `STRICT` (needs SQLite 3.37+, checked when connecting). CHECK constraints are added for the enumerations and flags the spec defines: stages, labels, run status, and 0/1 outcome flags. `posts.id` must look like `t3_*`.
- Indexes on `posts.first_seen_utc` (for `replay --since`) and `scores.stage`.
- Connections use WAL, `synchronous=NORMAL`, `foreign_keys=ON` and a 10 s busy timeout. They run in autocommit mode with explicit `BEGIN IMMEDIATE` transactions (`db.transaction`).

**CLI.** The command is `prospect-radar`, also runnable as `python -m reddit_prospect_radar`. Invalid configuration exits with code 78 (`EX_CONFIG`) and one line per problem. Commands are added only in the milestone that implements them.
