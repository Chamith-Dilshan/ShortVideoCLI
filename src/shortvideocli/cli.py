"""Command-line interface for ShortVideoCLI."""

import logging
from importlib.metadata import PackageNotFoundError, version
from typing import TypeVar

import typer
from sqlalchemy import text

from shortvideocli.commands.projects import project_app
from shortvideocli.commands.sources import source_app
from shortvideocli.commands.utils import run_async
from shortvideocli.commands.workflows import workflow_app
from shortvideocli.config import get_settings
from shortvideocli.database import get_engine
from shortvideocli.logging_config import setup_logging

T = TypeVar("T")

logger = logging.getLogger("shortvideocli")

app = typer.Typer(
    name="shortvideocli",
    help="Discover, investigate, and prepare compelling short-form video clips.",
    no_args_is_help=False,
    invoke_without_command=True,
)

app.add_typer(project_app, name="project")
app.add_typer(source_app, name="source")
app.add_typer(workflow_app, name="workflow")


def get_package_version() -> str:
    """Read the installed package version from distribution metadata."""
    try:
        return version("shortvideocli")
    except PackageNotFoundError:
        return "unknown (run 'uv sync' to install the project)"


def version_callback(value: bool) -> None:
    """Display the installed version and exit."""
    if value:
        typer.echo(f"ShortVideoCLI {get_package_version()}")
        raise typer.Exit()


@app.callback()
def main(ctx: typer.Context) -> None:
    """Start ShortVideoCLI or run a specific command."""

    settings = get_settings()
    log_path = setup_logging(settings)

    logger.info("ShortVideoCLI started in %s mode", settings.app_env)
    logger.debug("Application log file: %s", log_path)

    # No command means the user wants the interactive application.
    if ctx.invoked_subcommand is None:
        from shortvideocli.interactive import run_interactive

        try:
            run_interactive()
        except KeyboardInterrupt:
            typer.echo("\nShortVideoCLI interrupted.")
        finally:
            from shortvideocli.database import close_database

            run_async(close_database())


@app.command()
def status() -> None:
    """Display application configuration and runtime status."""
    settings = get_settings()

    logger.info("Status command executed")

    typer.echo("ShortVideoCLI is running.")
    typer.echo(f"Environment: {settings.app_env}")
    typer.echo(f"Log level: {settings.log_level}")
    typer.echo(f"Log file: {settings.log_file.resolve()}")


@app.command("db-check")
def database_check() -> None:
    """Check whether the asynchronous database connection works."""

    async def check() -> None:
        async with get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))

    try:
        run_async(check())
        logger.info("Async database connection successful")
        typer.echo("Database connection: OK")
    except Exception:
        logger.exception("Async database connection failed")
        typer.echo("Database connection: FAILED", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
