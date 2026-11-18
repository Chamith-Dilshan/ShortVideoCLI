"""CLI commands for managing automated workflows."""

import logging

import typer
from rich.console import Console
from rich.table import Table

from shortvideocli.commands.utils import run_async
from shortvideocli.database import get_session_factory
from shortvideocli.workflow_engine import recover_interrupted_workflow_run
from shortvideocli.workflow_queries import (
    get_workflow_run_details,
    list_workflow_runs,
)
from shortvideocli.workflows import (
    restart_workflow_run,
    resume_workflow_run,
    retry_workflow_run,
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


@workflow_app.command("history")
def workflow_history(
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        min=1,
        max=100,
        help="Maximum number of workflow runs to display.",
    ),
) -> None:
    """List recent workflow runs."""
    try:
        runs = run_async(
            list_workflow_runs(
                get_session_factory(),
                limit=limit,
            )
        )

        if not runs:
            console.print("No workflow runs found.")
            return

        table = Table(title="Workflow History")
        table.add_column("Workflow")
        table.add_column("Version")
        table.add_column("Run ID")
        table.add_column("Status")
        table.add_column("Created")

        for run in runs:
            created = run.created_at.strftime("%Y-%m-%d %H:%M:%S") if run.created_at else "Unknown"

            table.add_row(
                run.workflow_name,
                run.workflow_version,
                run.id,
                run.status,
                created,
            )

        console.print(table)

    except (ValueError, OSError) as exc:
        logger.exception("Could not retrieve workflow history.")
        console.print(f"[red]Could not retrieve workflow history:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@workflow_app.command("inspect")
def workflow_inspect(
    run_id: str = typer.Argument(
        ...,
        help="ID of the workflow run to inspect.",
    ),
) -> None:
    """Inspect a workflow run and its milestone progress."""
    try:
        result = run_async(
            get_workflow_run_details(
                get_session_factory(),
                run_id=run_id,
            )
        )

        if result is None:
            console.print(f"[red]Workflow run not found:[/red] {run_id}")
            raise typer.Exit(code=1)

        run, steps = result

        console.print(f"\n[bold]Workflow:[/bold] {run.workflow_name}")
        console.print(f"[bold]Version:[/bold] {run.workflow_version}")
        console.print(f"[bold]Run ID:[/bold] {run.id}")
        console.print(f"[bold]Status:[/bold] {run.status}")
        console.print(f"[bold]Created:[/bold] {run.created_at}")
        console.print(f"[bold]Started:[/bold] {run.started_at or 'Not started'}")
        console.print(f"[bold]Completed:[/bold] {run.completed_at or 'Not completed'}")

        if run.error_message:
            console.print(f"[red]Run error:[/red] {run.error_message}")

        table = Table(title="Workflow Milestones")
        table.add_column("Position", justify="right")
        table.add_column("Step")
        table.add_column("Type")
        table.add_column("Status")
        table.add_column("Attempts", justify="right")
        table.add_column("Error")

        for step in steps:
            table.add_row(
                str(step.position),
                step.step_key,
                step.step_type,
                step.status,
                str(step.attempt_count),
                step.error_message or "",
            )

        console.print(table)

    except (ValueError, OSError) as exc:
        logger.exception("Could not inspect workflow run.")
        console.print(f"[red]Could not inspect workflow run:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@workflow_app.command("retry")
def workflow_retry(
    run_id: str = typer.Argument(
        ...,
        help="ID of the failed workflow run to retry.",
    ),
) -> None:
    """Retry a failed workflow using its saved inputs."""
    try:
        results = run_async(retry_workflow_run(run_id))

        for result in results:
            console.print(f"[green]✓[/green] {result}")

        console.print("[bold green]Workflow retry completed.[/bold green]")

    except (ValueError, OSError, RuntimeError) as exc:
        logger.exception("Workflow retry failed")
        console.print(f"[red]Workflow retry failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc


@workflow_app.command("restart")
def workflow_restart(
    run_id: str = typer.Argument(
        ...,
        help="ID of the failed workflow run to restart.",
    ),
) -> None:
    """Create a new recovery run from a failed workflow."""
    try:
        results = run_async(restart_workflow_run(run_id))

        for result in results:
            console.print(f"[green]✓[/green] {result}")

        console.print("[bold green]Workflow restart completed.[/bold green]")

    except (ValueError, OSError, RuntimeError) as exc:
        logger.exception("Workflow restart failed")
        console.print(f"[red]Workflow restart failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc


@workflow_app.command("recover")
def workflow_recover(
    run_id: str = typer.Argument(
        ...,
        help="ID of the interrupted workflow run to recover.",
    ),
) -> None:
    """Recover a workflow run left in the running state."""
    try:
        result = run_async(
            get_workflow_run_details(
                get_session_factory(),
                run_id=run_id,
            )
        )

        if result is None:
            console.print(f"[red]Workflow run not found:[/red] {run_id}")
            raise typer.Exit(code=1)

        run, steps = result

        if run.status != "running":
            console.print(f"[red]Cannot recover workflow run.[/red] Current status: {run.status}")
            raise typer.Exit(code=1)

        console.print("\n[bold yellow]Warning: Workflow recovery[/bold yellow]")
        console.print(
            "This operation will mark the running workflow as failed "
            "and mark any running milestones as failed."
        )
        console.print("Completed milestones and their saved outputs will be preserved.")
        console.print(
            "\n[bold red]Make sure the original workflow process "
            "has completely stopped before continuing.[/bold red]"
        )

        confirmed = typer.confirm(
            "\nDo you want to recover this workflow run?",
            default=False,
        )

        if not confirmed:
            console.print("[yellow]Workflow recovery cancelled.[/yellow]")
            raise typer.Exit(code=0)

        interrupted_count = run_async(
            recover_interrupted_workflow_run(
                get_session_factory(),
                run_id=run_id,
                reason="Workflow manually recovered after interruption.",
            )
        )

        console.print("\n[green]Workflow recovery completed.[/green]")
        console.print(f"Interrupted milestones marked as failed: {interrupted_count}")
        console.print("\nYou can now resume the workflow using the resume command.")

    except (ValueError, OSError, RuntimeError) as exc:
        logger.exception("Workflow recovery failed")
        console.print(f"[red]Workflow recovery failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc
