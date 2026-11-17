import logging
from typing import Annotated

import typer

from shortvideocli.commands.utils import run_async
from shortvideocli.database import get_session_factory
from shortvideocli.services.projects import (
    create_project as create_project_service,
)
from shortvideocli.services.projects import (
    list_projects as list_projects_service,
)

logger = logging.getLogger(__name__)

project_app = typer.Typer(
    help="Create and manage video production projects.",
    no_args_is_help=True,
)


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
