"""YAML-based, resumable workflow automation for ShortVideoCLI."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shortvideocli.database import get_session_factory
from shortvideocli.models import WorkflowRun, WorkflowStep
from shortvideocli.services.projects import create_project
from shortvideocli.services.sources import create_source
from shortvideocli.workflow_engine import (
    StepHandler,
    WorkflowStepError,
    WorkflowStepSpec,
    create_workflow_run,
    execute_workflow_run,
)


def _validate_workflow(data: Any) -> dict[str, Any]:
    """Validate workflow structure and references between project steps."""

    if not isinstance(data, dict):
        raise ValueError("Workflow must contain a YAML mapping.")

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Workflow must have a non-empty 'name'.")

    version = data.get("version", "1")
    if not isinstance(version, (str, int)) or not str(version).strip():
        raise ValueError("Workflow version must be a non-empty string or integer.")

    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("Workflow must contain a non-empty 'steps' list.")

    step_keys: set[str] = set()
    project_aliases: set[str] = set()

    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise ValueError(f"Workflow step {index} must be a mapping.")

        action = step.get("action")
        if action not in {"project.create", "source.add"}:
            raise ValueError(f"Step {index}: unsupported action '{action}'.")

        explicit_id = step.get("id")
        if explicit_id is not None:
            if not isinstance(explicit_id, str) or not explicit_id.strip():
                raise ValueError(f"Step {index}: id must be a non-empty string.")
            step_key = explicit_id.strip()
        else:
            step_key = f"step-{index}"

        if step_key in step_keys:
            raise ValueError(f"Step {index}: duplicate workflow step id '{step_key}'.")
        step_keys.add(step_key)

        if action == "project.create":
            project_name = step.get("name")
            if not isinstance(project_name, str) or not project_name.strip():
                raise ValueError(f"Step {index}: project.create requires a name.")

            if explicit_id is not None:
                project_aliases.add(step_key)

        elif action == "source.add":
            project_reference = step.get("project")
            if not isinstance(project_reference, str) or not project_reference.strip():
                raise ValueError(f"Step {index}: source.add requires a project reference.")

            required_fields = ("platform", "url", "rights_note")
            missing = [
                field
                for field in required_fields
                if not isinstance(step.get(field), str) or not step[field].strip()
            ]
            if missing:
                raise ValueError(f"Step {index}: source.add is missing: " + ", ".join(missing))

            # A named alias must refer to a project created earlier in
            # this workflow. A value that is not an alias is treated as
            # an existing project database ID.
            if project_reference not in project_aliases and project_reference in step_keys:
                raise ValueError(
                    f"Step {index}: '{project_reference}' is not a project.create alias."
                )

    return data


def _load_workflow(path: str | Path) -> dict[str, Any]:
    """Read and validate a YAML workflow file."""

    workflow_path = Path(path).expanduser()

    if not workflow_path.is_file():
        raise ValueError(f"Workflow file does not exist: {workflow_path}")

    try:
        data = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML workflow: {exc}") from exc

    return _validate_workflow(data)


def _build_step_specs(
    workflow: dict[str, Any],
) -> list[WorkflowStepSpec]:
    """Convert YAML steps into persistent workflow step specifications."""

    specifications: list[WorkflowStepSpec] = []

    for index, step in enumerate(workflow["steps"], start=1):
        step_key = step["id"].strip() if "id" in step else f"step-{index}"

        specifications.append(
            WorkflowStepSpec(
                step_key=step_key,
                step_type=step["action"],
                position=index,
                input_data=dict(step),
            )
        )

    return specifications


async def _handle_project_create(
    session: Any,
    input_data: dict[str, object],
    completed_outputs: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Create a project as part of the current milestone transaction."""

    name = input_data.get("name")
    description = input_data.get("description")

    if not isinstance(name, str):
        raise ValueError("project.create requires a project name.")

    if description is not None and not isinstance(description, str):
        raise ValueError("Project description must be a string.")

    project = await create_project(
        session,
        name=name,
        description=description,
    )

    return {
        "project_id": str(project.id),
        "project_name": project.name,
        "message": (f"Created project '{project.name}' (ID: {project.id})"),
    }


async def _handle_source_add(
    session: Any,
    input_data: dict[str, object],
    completed_outputs: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Register a video source using a project created by an earlier step."""

    project_reference = input_data.get("project")
    platform = input_data.get("platform")
    source_url = input_data.get("url")
    rights_note = input_data.get("rights_note")
    title = input_data.get("title")

    if not isinstance(project_reference, str):
        raise ValueError("source.add requires a project reference.")

    if not isinstance(platform, str):
        raise ValueError("source.add requires a platform.")

    if not isinstance(source_url, str):
        raise ValueError("source.add requires a URL.")

    if not isinstance(rights_note, str):
        raise ValueError("source.add requires a rights note.")

    if title is not None and not isinstance(title, str):
        raise ValueError("Source title must be a string.")

    # Resolve a YAML project alias from a previously completed step.
    # If no matching alias exists, treat the reference as a database ID.
    previous_output = completed_outputs.get(project_reference)
    if previous_output is not None:
        project_id = previous_output.get("project_id")
        if not isinstance(project_id, str):
            raise ValueError(f"Completed step '{project_reference}' has no project ID.")
    else:
        project_id = project_reference

    source = await create_source(
        session,
        project_id=project_id,
        platform=platform,
        source_url=source_url,
        rights_note=rights_note,
        title=title,
    )

    return {
        "source_id": str(source.id),
        "source_url": source.source_url,
        "message": f"Registered source '{source.source_url}'",
    }


def _get_handlers() -> dict[str, StepHandler]:
    """Return the supported YAML action handlers."""

    return {
        "project.create": _handle_project_create,
        "source.add": _handle_source_add,
    }


def _definition_hash(workflow: dict[str, Any]) -> str:
    """Create a stable hash of the parsed workflow definition."""

    canonical_yaml = yaml.safe_dump(
        workflow,
        sort_keys=True,
        allow_unicode=True,
    )
    return hashlib.sha256(canonical_yaml.encode("utf-8")).hexdigest()


async def _read_run_results(
    run_id: str,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> list[str]:
    """Read the saved messages from a workflow run's completed steps."""

    factory = session_factory or get_session_factory()

    async with factory() as session:
        result = await session.execute(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_run_id == run_id)
            .order_by(WorkflowStep.position)
        )
        steps = result.scalars().all()

        messages: list[str] = []

        for step in steps:
            if step.status != "completed":
                continue

            message = step.output_data.get("message")
            if isinstance(message, str):
                messages.append(message)

        return messages


async def run_workflow_file(path: str | Path) -> list[str]:
    """Run a workflow, automatically resuming a matching incomplete run.

    A completed workflow is not reused. Running the same YAML file after
    completion starts a fresh run.
    """

    workflow = _load_workflow(path)
    specifications = _build_step_specs(workflow)

    workflow_name = workflow["name"].strip()
    workflow_version = str(workflow.get("version", "1"))
    definition_hash = _definition_hash(workflow)

    async with get_session_factory()() as session:
        async with session.begin():
            existing_run = await session.scalar(
                select(WorkflowRun)
                .where(
                    WorkflowRun.workflow_name == workflow_name,
                    WorkflowRun.workflow_version == workflow_version,
                    WorkflowRun.definition_hash == definition_hash,
                    WorkflowRun.status.in_(["pending", "failed", "running"]),
                )
                .order_by(WorkflowRun.created_at.desc())
                .limit(1)
            )

            if existing_run is not None:
                run_id = str(existing_run.id)
                is_resume = True
            else:
                workflow_run = await create_workflow_run(
                    session,
                    workflow_name=workflow_name,
                    workflow_version=workflow_version,
                    definition_hash=definition_hash,
                    steps=specifications,
                )
                run_id = str(workflow_run.id)
                is_resume = False

    try:
        await execute_workflow_run(
            get_session_factory(),
            run_id=run_id,
            handlers=_get_handlers(),
        )
    except WorkflowStepError as exc:
        raise RuntimeError(
            f"{exc}\n"
            f"Workflow run ID: {run_id}\n"
            f"Run the same YAML file again to resume this workflow."
        ) from exc

    messages = await _read_run_results(run_id)

    action = "Resumed" if is_resume else "Completed"
    return [
        f"{action} workflow run: {run_id}",
        *messages,
    ]


async def resume_workflow_run(
    run_id: str,
    path: str | Path,
) -> list[str]:
    """Refresh incomplete step inputs and resume an existing workflow run."""

    workflow = _load_workflow(path)

    await _refresh_incomplete_step_inputs(
        get_session_factory(),
        run_id,
        workflow,
    )

    try:
        await execute_workflow_run(
            get_session_factory(),
            run_id=run_id,
            handlers=_get_handlers(),
        )
    except WorkflowStepError as exc:
        raise RuntimeError(
            f"{exc}\nWorkflow run ID: {run_id}\nCorrect the YAML inputs and resume this run again."
        ) from exc

    messages = await _read_run_results(run_id)

    return [
        f"Resumed workflow run: {run_id}",
        *messages,
    ]


async def _refresh_incomplete_step_inputs(
    session_factory: Any,
    run_id: str,
    workflow: dict[str, Any],
) -> None:
    """Refresh incomplete step inputs without modifying completed steps."""

    from shortvideocli.models import WorkflowRun

    specifications = _build_step_specs(workflow)
    new_specs = {spec.step_key: spec for spec in specifications}

    async with session_factory() as session, session.begin():
        run = await session.get(WorkflowRun, run_id)

        if run is None:
            raise ValueError(f"Workflow run not found: {run_id}")

        if run.workflow_name != workflow["name"].strip():
            raise ValueError("Workflow name does not match the saved run.")

        if run.workflow_version != str(workflow.get("version", "1")):
            raise ValueError("Workflow version does not match the saved run.")

        result = await session.execute(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_run_id == run_id)
            .order_by(WorkflowStep.position)
        )
        saved_steps = list(result.scalars().all())

        if {step.step_key for step in saved_steps} != set(new_specs):
            raise ValueError(
                "Workflow step structure has changed. "
                "Resume requires the same step IDs and structure."
            )

        for saved_step in saved_steps:
            spec = new_specs[saved_step.step_key]

            if saved_step.step_type != spec.step_type:
                raise ValueError(f"Action type changed for step '{saved_step.step_key}'.")

            if saved_step.status == "completed":
                continue

            saved_step.input_data = dict(spec.input_data)

        run.definition_hash = _definition_hash(workflow)


async def retry_workflow_run(
    run_id: str,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> list[str]:
    """Retry a failed workflow using its saved milestone inputs.

    Completed milestones are skipped by the workflow engine. The failed
    milestone and any subsequent pending milestones are executed again.

    Args:
        run_id: ID of the failed workflow run.
        session_factory: Optional session factory, primarily for testing.

    Returns:
        A list of workflow execution messages.

    Raises:
        ValueError: If the run does not exist or is not failed.
        RuntimeError: If a milestone fails again.
    """
    factory = session_factory or get_session_factory()

    async with factory() as session:
        run = await session.get(WorkflowRun, run_id)

        if run is None:
            raise ValueError(f"Workflow run not found: {run_id}")

        if run.status != "failed":
            raise ValueError(
                f"Cannot retry workflow with status '{run.status}'. "
                "Only failed workflows can be retried."
            )

        failed_step = await session.scalar(
            select(WorkflowStep).where(
                WorkflowStep.workflow_run_id == run_id,
                WorkflowStep.status == "failed",
            )
        )

        if failed_step is None:
            raise ValueError("The workflow is marked as failed but has no failed milestone.")

    try:
        await execute_workflow_run(
            factory,
            run_id=run_id,
            handlers=_get_handlers(),
        )
    except WorkflowStepError as exc:
        raise RuntimeError(
            f"{exc}\nWorkflow run ID: {run_id}\n"
            "Correct the underlying problem and retry this run again."
        ) from exc

    messages = await _read_run_results(run_id, factory)

    return [
        f"Retried and completed workflow run: {run_id}",
        *messages,
    ]


async def restart_workflow_run(
    run_id: str,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> list[str]:
    """Create a new recovery run from a failed workflow.

    Completed milestones are copied as completed checkpoints. Failed and
    pending milestones are reset to pending and will execute in the new run.

    The original workflow run and its database records are preserved.

    Args:
        run_id: ID of the failed workflow run to restart.
        session_factory: Optional session factory, primarily for testing.

    Returns:
        A list of messages from the new workflow run.

    Raises:
        ValueError: If the original run is missing, is not failed, or has
            no failed milestone.
        RuntimeError: If a milestone fails in the new run.
    """
    factory = session_factory or get_session_factory()

    async with factory() as session:
        original_run = await session.get(WorkflowRun, run_id)

        if original_run is None:
            raise ValueError(f"Workflow run not found: {run_id}")

        if original_run.status != "failed":
            raise ValueError(
                f"Cannot restart workflow with status '{original_run.status}'. "
                "Only failed workflows can be restarted."
            )

        result = await session.execute(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_run_id == run_id)
            .order_by(WorkflowStep.position)
        )
        original_steps = list(result.scalars().all())

        if not original_steps:
            raise ValueError("Cannot restart a workflow with no milestones.")

        if not any(step.status == "failed" for step in original_steps):
            raise ValueError("The workflow is marked as failed but has no failed milestone.")

        specifications = [
            WorkflowStepSpec(
                step_key=step.step_key,
                step_type=step.step_type,
                position=step.position,
                input_data=dict(step.input_data),
            )
            for step in original_steps
        ]

        workflow_name = original_run.workflow_name
        workflow_version = original_run.workflow_version
        definition_hash = original_run.definition_hash

        completed_outputs = {
            step.step_key: dict(step.output_data)
            for step in original_steps
            if step.status == "completed"
        }

    # Create the new run and copy successful checkpoints in one transaction.
    async with factory() as session, session.begin():
        new_run = await create_workflow_run(
            session,
            workflow_name=workflow_name,
            workflow_version=workflow_version,
            definition_hash=definition_hash,
            steps=specifications,
        )

        new_run_id = str(new_run.id)

        result = await session.execute(
            select(WorkflowStep).where(WorkflowStep.workflow_run_id == new_run_id)
        )
        new_steps = {step.step_key: step for step in result.scalars().all()}

        for step_key, output_data in completed_outputs.items():
            new_step = new_steps[step_key]
            new_step.status = "completed"
            new_step.output_data = output_data

    try:
        await execute_workflow_run(
            factory,
            run_id=new_run_id,
            handlers=_get_handlers(),
        )
    except WorkflowStepError as exc:
        raise RuntimeError(
            f"{exc}\n"
            f"New workflow run ID: {new_run_id}\n"
            f"Original workflow run ID: {run_id}\n"
            "Correct the underlying problem and retry the new run."
        ) from exc

    messages = await _read_run_results(new_run_id, factory)

    return [
        f"Created recovery run: {new_run_id}",
        f"Original workflow run preserved: {run_id}",
        *messages,
    ]
