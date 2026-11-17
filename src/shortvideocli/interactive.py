"""Interactive terminal interface for ShortVideoCLI."""

from __future__ import annotations

import asyncio

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from sqlalchemy.ext.asyncio import AsyncSession

from shortvideocli.database import get_session_factory
from shortvideocli.services.projects import create_project, list_projects
from shortvideocli.services.sources import create_source, list_sources

console = Console()


BANNER = r"""
  ███████╗██╗  ██╗ ██████╗ ██████╗ ████████╗
  ██╔════╝██║  ██║██╔═══██╗██╔══██╗╚══██╔══╝
  ███████╗███████║██║   ██║██████╔╝   ██║
  ╚════██║██╔══██║██║   ██║██╔══██╗   ██║
  ███████║██║  ██║╚██████╔╝██║  ██║   ██║
  ╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝
"""


def show_intro() -> None:
    """Display the startup banner and application introduction."""

    console.clear()
    console.print(
        Panel(
            Text(BANNER, style="bold bright_green", justify="center"),
            border_style="bright_green",
            box=box.DOUBLE,
            padding=(1, 2),
        )
    )

    console.print(
        Panel(
            "[bold white]VIDEO INTELLIGENCE WORKBENCH[/bold white]\n\n"
            "Find the moments worth watching.\n"
            "[dim]Create projects • Analyze videos • Discover moments • Export clips[/dim]",
            border_style="cyan",
            title="[bold cyan]Welcome to ShortVideoCLI[/bold cyan]",
            padding=(1, 3),
        )
    )


def show_help() -> None:
    """Display instructions for using the interactive application."""

    console.print(
        Panel(
            "[bold cyan]Getting started[/bold cyan]\n\n"
            "1. Create a project to organize your work.\n"
            "2. Add video sources to that project.\n"
            "3. Investigate sources to find interesting moments.\n"
            "4. Review detected moments before approving them.\n"
            "5. Export approved clips for your target platforms.\n\n"
            "[bold yellow]Important:[/bold yellow] Only add sources you have "
            "permission to use. Keep the rights information with each source.\n\n"
            "You can also run a YAML workflow to automate supported tasks.",
            title="ShortVideoCLI instructions",
            border_style="cyan",
        )
    )


_runner: asyncio.Runner | None = None


def _run(coroutine):
    """Run an async operation on the interactive session's event loop."""

    if _runner is None:
        raise RuntimeError("Interactive event loop is not initialized.")

    return _runner.run(coroutine)


def _show_projects(projects) -> None:
    """Render projects in a readable terminal table."""

    if not projects:
        console.print("[yellow]No projects found. Create one first.[/yellow]")
        return

    table = Table(title="Your projects", box=box.ROUNDED)
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Name", style="bold")
    table.add_column("Project ID", style="dim")
    table.add_column("Created", style="green")

    for index, project in enumerate(projects, start=1):
        table.add_row(
            str(index),
            project.name,
            str(project.id),
            str(project.created_at),
        )

    console.print(table)


def _create_project() -> None:
    """Prompt for and create a project."""

    name = console.input("[bold cyan]Project name:[/bold cyan] ").strip()

    if not name:
        console.print("[red]Project name cannot be empty.[/red]")
        return

    description = console.input("[bold cyan]Description (optional):[/bold cyan] ").strip()

    async def operation():
        async with get_session_factory()() as session, session.begin():
            return await create_project(
                session,
                name=name,
                description=description or None,
            )

    try:
        project = _run(operation())
        console.print(f"[green]Created project:[/green] {project.name}")
        console.print(f"[dim]Project ID: {project.id}[/dim]")

    except ValueError as exc:
        console.print(f"[red]Error: {exc}[/red]")


def _list_projects() -> list:
    """Load and display all projects."""

    async def operation():
        async with get_session_factory()() as session:
            return await list_projects(session)

    projects = _run(operation())
    _show_projects(projects)
    return projects


def _add_source() -> None:
    """Interactively register a video source."""

    projects = _list_projects()
    if not projects:
        return

    selection = console.input("[bold cyan]Enter the project number:[/bold cyan] ").strip()

    try:
        project_index = int(selection) - 1
        project = projects[project_index]
    except ValueError, IndexError:
        console.print("[red]Invalid project selection.[/red]")
        return

    platform = console.input("[bold cyan]Platform (e.g. youtube):[/bold cyan] ").strip()
    source_url = console.input("[bold cyan]Video URL:[/bold cyan] ").strip()
    title = console.input("[bold cyan]Video title (optional):[/bold cyan] ").strip()
    rights_note = console.input("[bold cyan]Rights / permission note:[/bold cyan] ").strip()

    async def operation():
        async with get_session_factory()() as session, session.begin():
            return await create_source(
                session,
                project_id=project.id,
                platform=platform,
                source_url=source_url,
                rights_note=rights_note,
                title=title or None,
            )

    try:
        source = _run(operation())
        console.print(f"[green]Source registered successfully:[/green] {source.source_url}")
    except ValueError as exc:
        console.print(f"[red]Error: {exc}[/red]")


def _list_sources() -> None:
    """Select a project and display its registered video sources."""

    projects = _list_projects()
    if not projects:
        return

    selection = console.input("[bold cyan]Enter the project number:[/bold cyan] ").strip()

    try:
        project = projects[int(selection) - 1]
    except ValueError, IndexError:
        console.print("[red]Invalid project selection.[/red]")
        return

    async def operation():
        async with get_session_factory()() as session:
            return await list_sources(session, project.id)

    sources = _run(operation())

    if not sources:
        console.print("[yellow]This project has no sources yet.[/yellow]")
        return

    table = Table(title=f"Sources: {project.name}", box=box.ROUNDED)
    table.add_column("#", style="cyan")
    table.add_column("Platform")
    table.add_column("Title")
    table.add_column("URL", overflow="fold")

    for index, source in enumerate(sources, start=1):
        table.add_row(
            str(index),
            source.platform,
            source.title or "Untitled",
            source.source_url,
        )

    console.print(table)


def run_interactive() -> None:
    """Start the application with one persistent asynchronous event loop."""

    global _runner

    with asyncio.Runner() as runner:
        _runner = runner
        try:
            _run_interactive_loop()
        finally:
            _runner = None


def _run_interactive_loop() -> None:
    """Run the persistent interactive application menu."""

    show_intro()
    show_help()

    while True:
        console.print(
            Panel(
                "[1] Projects\n"
                "[2] Video sources\n"
                "[3] Investigations [dim](coming in a later phase)[/dim]\n"
                "[4] Review moments [dim](coming in a later phase)[/dim]\n"
                "[5] Export clips [dim](coming in a later phase)[/dim]\n"
                "[6] Run automation workflow\n"
                "[H] Help and instructions\n"
                "[Q] Quit",
                title="[bold bright_green]MAIN MENU[/bold bright_green]",
                border_style="bright_green",
            )
        )

        choice = console.input("[bold cyan]Select an option:[/bold cyan] ")
        choice = choice.strip().lower()

        if choice == "1":
            _projects_menu()
        elif choice == "2":
            _sources_menu()
        elif choice == "3":
            console.print("[yellow]Investigation features will be added in a later phase.[/yellow]")
        elif choice == "4":
            console.print("[yellow]Moment review features will be added in a later phase.[/yellow]")
        elif choice == "5":
            console.print("[yellow]Clip export features will be added in a later phase.[/yellow]")
        elif choice == "6":
            _run_workflow_prompt()
        elif choice == "h":
            show_help()
        elif choice == "q":
            console.print("[bright_green]Thanks for using ShortVideoCLI. Goodbye![/bright_green]")
            break
        else:
            console.print("[red]Unknown option. Choose an item from the menu.[/red]")


def _projects_menu() -> None:
    """Display project-related actions."""

    while True:
        console.print("\n[bold]PROJECTS[/bold]")
        console.print("[1] Create project")
        console.print("[2] List projects")
        console.print("[B] Back")

        choice = console.input("Choose: ").strip().lower()

        if choice == "1":
            _create_project()
        elif choice == "2":
            _list_projects()
        elif choice == "b":
            return
        else:
            console.print("[red]Invalid choice.[/red]")


def _sources_menu() -> None:
    """Display video-source actions."""

    while True:
        console.print("\n[bold]VIDEO SOURCES[/bold]")
        console.print("[1] Add source")
        console.print("[2] List sources")
        console.print("[B] Back")

        choice = console.input("Choose: ").strip().lower()

        if choice == "1":
            _add_source()
        elif choice == "2":
            _list_sources()
        elif choice == "b":
            return
        else:
            console.print("[red]Invalid choice.[/red]")


def _run_workflow_prompt() -> None:
    """Ask for a workflow file and run it."""

    from shortvideocli.workflows import run_workflow_file

    path = console.input("[bold cyan]Workflow YAML path:[/bold cyan] ").strip()

    if not path:
        return

    try:
        results = _run(run_workflow_file(path))
        for result in results:
            console.print(f"[green]✓[/green] {result}")
    except (ValueError, OSError) as exc:
        console.print(f"[red]Workflow failed: {exc}[/red]")
