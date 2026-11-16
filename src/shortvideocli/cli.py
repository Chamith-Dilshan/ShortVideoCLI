"""Command-line interface for ShortVideoCLI."""

import logging
from importlib.metadata import PackageNotFoundError, version
from typing import Annotated

import typer

from shortvideocli.config import get_settings
from shortvideocli.logging_config import setup_logging

app = typer.Typer(
    name="shortvideocli",
    help="Discover, investigate, and prepare compelling short-form video clips.",
    no_args_is_help=False,
    invoke_without_command=True,
)

logger = logging.getLogger("shortvideocli")


def get_package_version() -> str:
    """Read the installed package version from distribution metadata."""
    try:
        return version("shortvideocli")
    except PackageNotFoundError:
        return "unknown (install the project with uv sync)"


def version_callback(value: bool) -> None:
    """Display the installed version and exit."""
    if value:
        typer.echo(f"ShortVideoCLI {get_package_version()}")
        raise typer.Exit()


@app.callback()
def main(
    version_option: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show the application version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Initialize application configuration and logging."""
    settings = get_settings()
    setup_logging(settings)
    logger.info("ShortVideoCLI started in %s mode", settings.app_env)


@app.command()
def status() -> None:
    """Display application status and verify logging."""
    settings = get_settings()

    logger.info("Status command executed")

    typer.echo("ShortVideoCLI is running.")
    typer.echo(f"Environment: {settings.app_env}")
    typer.echo(f"Log level: {settings.log_level}")
    typer.echo(f"Log file: {settings.log_file.resolve()}")


if __name__ == "__main__":
    app()
