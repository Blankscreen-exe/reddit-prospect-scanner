# Reddit Prospect Radar

The specification is `docs/spec.md` and it is the source of truth for the build. Wherever the spec says "Lead Radar", read it as **Reddit Prospect Radar**. Naming:

| Item | Name |
|---|---|
| Project name | Reddit Prospect Radar |
| Distribution (`pyproject.toml`) | `reddit-prospect-radar` |
| Python import package | `reddit_prospect_radar` (spec: `leadradar`) |
| CLI command | `prospect-radar` (spec: `leadradar`) |
| Database file | `data/prospect_radar.db` (spec: `data/leadradar.db`) |

Record any implementation decision the spec leaves open in `docs/DECISIONS.md`.

## Project building guidelines

- **Follow established good practice for every technology used.** The project must stay maintainable, and new developers must be able to onboard easily, 5-10 years from now.
- **Keep the code modular and DRY.**
- **Keep testing consistent** and use each library's standard testing tools (pytest and its conventions).
- **Build to production quality.** Not every production feature will ship now: each feature will grow over time by expanding around its edges. But every feature that is built must be built in its best, correct form from the start.
- **No "it doesn't need proper work yet" decisions.** Do not cut corners because a feature is at an early stage.
- **No workarounds unless the owner explicitly permits them.** The goal is never to have to go back to a feature because a workaround was built instead of the correct implementation. If the correct implementation is blocked, stop and ask rather than working around it.

## Commands

```bash
uv sync                                # install (runtime + dev)
uv run prospect-radar --help           # CLI
uv run pytest                          # tests
uv run ruff format . && uv run ruff check .
uv run mypy                            # strict type check of src and tests
```

All four checks (format, lint, mypy, pytest) must pass before a milestone is reported done.
