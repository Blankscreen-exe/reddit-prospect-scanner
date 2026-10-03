"""Command-line interface (``prospect-radar``)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer

from reddit_prospect_radar import __version__, db
from reddit_prospect_radar.config import ConfigError
from reddit_prospect_radar.context import AppContext
from reddit_prospect_radar.logging_config import configure_logging

logger = logging.getLogger(__name__)

# Exit code for invalid configuration or environment (EX_CONFIG from sysexits.h).
EXIT_CONFIG_ERROR = 78
EXIT_DATABASE_ERROR = 1

app = typer.Typer(
    name="prospect-radar",
    help="Reddit Prospect Radar: find Reddit posts from people who need what Gray Lining sells.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit


@app.callback()
def main(
    ctx: typer.Context,
    config_dir: Annotated[
        Path,
        typer.Option(
            "--config-dir",
            envvar="PROSPECT_RADAR_CONFIG_DIR",
            help="Directory containing config.yaml. Its parent is the project root.",
            file_okay=False,
        ),
    ] = Path("config"),
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Log at DEBUG level.")] = False,
    version: Annotated[  # noqa: ARG001 - handled eagerly by the callback
        bool,
        typer.Option(
            "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
        ),
    ] = False,
) -> None:
    """Load and validate configuration, then set up logging, before any command runs."""
    try:
        app_context = AppContext.load(config_dir)
    except ConfigError as exc:
        typer.echo(f"Invalid configuration:\n{exc}", err=True)
        raise typer.Exit(EXIT_CONFIG_ERROR) from exc
    configure_logging(app_context.config.logging, app_context.paths.log_file, verbose=verbose)
    ctx.obj = app_context


@app.command("init-db")
def init_db(ctx: typer.Context) -> None:
    """Create the data folders and the database, or bring an existing schema up to date."""
    app_context: AppContext = ctx.obj
    paths = app_context.paths
    paths.ensure_dirs()
    try:
        version = db.initialize(paths.db_file)
    except db.DatabaseError as exc:
        logger.error("Database initialization failed: %s", exc)
        raise typer.Exit(EXIT_DATABASE_ERROR) from exc
    logger.info("Database ready at %s (schema version %d)", paths.db_file, version)
