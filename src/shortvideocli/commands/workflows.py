"""CLI commands for managing automated workflows."""

import logging

import typer
from rich.console import Console

from shortvideocli.commands.utils import run_async
from shortvideocli.workflows import (
    resume_workflow_run,
    run_workflow_file,
)

logger = logging.getLogger(__name__)

workflow_app = typer.Typer(
    name="workflow",
    help="Run and manage automated ShortVideoCLI workflows.",
    no_args_is_help=True,
)

console = Console()


@workflow_app.command("run")
def workflow_run(
    file: str = typer.Argument(
        ...,
        help="Path to a YAML workflow file.",
    ),
) -> None:
    """Start a workflow or resume its matching incomplete run."""
    try:
        results = run_async(run_workflow_file(file))

        for result in results:
            console.print(f"[green]✓[/green] {result}")

        console.print("[bold green]Workflow completed.[/bold green]")

    except (ValueError, OSError, RuntimeError) as exc:
        logger.exception("Workflow execution failed")
        console.print(f"[red]Workflow failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc


@workflow_app.command("resume")
def workflow_resume(
    run_id: str = typer.Argument(
        ...,
        help="ID of the workflow run to resume.",
    ),
    file: str = typer.Argument(
        ...,
        help="YAML workflow file containing the corrected inputs.",
    ),
) -> None:
    """Refresh incomplete step inputs and resume a workflow run."""

    try:
        results = run_async(resume_workflow_run(run_id, file))

        for result in results:
            console.print(f"[green]✓[/green] {result}")

        console.print("[bold green]Workflow completed.[/bold green]")

    except (ValueError, OSError, RuntimeError) as exc:
        logger.exception("Workflow resume failed")
        console.print(f"[red]Workflow resume failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc
