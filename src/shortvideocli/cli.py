"""Command-line interface for ShortVideoCLI."""

import asyncio
import logging
from collections.abc import Coroutine
from importlib.metadata import PackageNotFoundError, version
from typing import Annotated, Any, TypeVar

import typer
from sqlalchemy import text

from shortvideocli.config import get_settings
from shortvideocli.database import get_engine, get_session_factory
from shortvideocli.logging_config import setup_logging
from shortvideocli.services.projects import (
    create_project as create_project_service,
)
from shortvideocli.services.projects import (
    list_projects as list_projects_service,
)
from shortvideocli.services.sources import (
    create_source as create_source_service,
)
from shortvideocli.services.sources import (
    list_sources as list_sources_service,
)

T = TypeVar("T")

logger = logging.getLogger("shortvideocli")

app = typer.Typer(
    name="shortvideocli",
    help="Discover, investigate, and prepare compelling short-form video clips.",
    no_args_is_help=False,
    invoke_without_command=True,
)

project_app = typer.Typer(
    help="Create and manage video production projects.",
    no_args_is_help=True,
)

source_app = typer.Typer(
    help="Register and manage original video sources.",
    no_args_is_help=True,
)

app.add_typer(project_app, name="project")
app.add_typer(source_app, name="source")


def run_async[T](coroutine: Coroutine[Any, Any, T]) -> T:
    """Run an asynchronous application operation from the synchronous CLI."""
    return asyncio.run(coroutine)


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


@project_app.command("create")
def create_project(
    name: Annotated[
        str,
        typer.Argument(help="Name of the new project."),
    ],
    description: Annotated[
        str | None,
        typer.Option("--description", "-d", help="Optional project description."),
    ] = None,
) -> None:
    """Create a new project."""

    async def operation():
        async with get_session_factory()() as session, session.begin():
            return await create_project_service(
                session,
                name=name,
                description=description,
            )

    try:
        project = run_async(operation())
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    logger.info("Created project %s", project.id)

    typer.echo("Project created.")
    typer.echo(f"ID: {project.id}")
    typer.echo(f"Name: {project.name}")


@project_app.command("list")
def list_projects() -> None:
    """List all registered projects."""

    async def operation():
        async with get_session_factory()() as session:
            return await list_projects_service(session)

    projects = run_async(operation())

    if not projects:
        typer.echo("No projects found.")
        return

    for project in projects:
        typer.echo(f"{project.id} | {project.name}")


@source_app.command("add")
def add_source(
    project_id: Annotated[
        str,
        typer.Argument(help="UUID of the project that owns this source."),
    ],
    platform: Annotated[
        str,
        typer.Option("--platform", help="Source platform, e.g. youtube."),
    ],
    source_url: Annotated[
        str,
        typer.Option("--url", help="Original video URL."),
    ],
    rights_note: Annotated[
        str,
        typer.Option(
            "--rights-note",
            help="Explain your rights or permission to use this video.",
        ),
    ],
    title: Annotated[
        str | None,
        typer.Option("--title", help="Optional video title."),
    ] = None,
) -> None:
    """Register a video source under an existing project."""

    async def operation():
        async with get_session_factory()() as session, session.begin():
            return await create_source_service(
                session,
                project_id=project_id,
                platform=platform,
                source_url=source_url,
                rights_note=rights_note,
                title=title,
            )

    try:
        source = run_async(operation())
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    logger.info("Registered video source %s", source.id)

    typer.echo("Video source registered.")
    typer.echo(f"ID: {source.id}")
    typer.echo(f"Platform: {source.platform}")
    typer.echo(f"URL: {source.source_url}")


@source_app.command("list")
def list_sources(
    project_id: Annotated[
        str,
        typer.Argument(help="UUID of the project."),
    ],
) -> None:
    """List video sources belonging to a project."""

    async def operation():
        async with get_session_factory()() as session:
            return await list_sources_service(session, project_id)

    sources = run_async(operation())

    if not sources:
        typer.echo("No sources found for this project.")
        return

    for source in sources:
        typer.echo(
            f"{source.id} | {source.platform} | {source.title or 'Untitled'} | {source.source_url}"
        )


workflow_app = typer.Typer(
    name="workflow",
    help="Run automated ShortVideoCLI workflows.",
)

app.add_typer(workflow_app, name="workflow")


@workflow_app.command("run")
def workflow_run(
    file: str = typer.Argument(
        ...,
        help="Path to a YAML workflow file.",
    ),
) -> None:
    """Execute a YAML automation workflow."""

    import asyncio

    from rich.console import Console

    from shortvideocli.workflows import run_workflow_file

    console = Console()

    try:
        results = asyncio.run(run_workflow_file(file))
        for result in results:
            console.print(f"[green]✓[/green] {result}")
        console.print("[bold green]Workflow completed.[/bold green]")
    except (ValueError, OSError) as exc:
        console.print(f"[red]Workflow failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
