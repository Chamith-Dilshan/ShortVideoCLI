import logging
from typing import Annotated

import typer

from shortvideocli.commands.utils import run_async
from shortvideocli.database import get_session_factory
from shortvideocli.services.sources import (
    create_source as create_source_service,
)
from shortvideocli.services.sources import (
    list_sources as list_sources_service,
)

logger = logging.getLogger(__name__)

source_app = typer.Typer(
    name="source",
    help="Register and manage original video sources.",
    no_args_is_help=True,
)


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
