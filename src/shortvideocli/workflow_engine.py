"""Execute workflows with persistent, resumable milestone checkpoints."""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shortvideocli.models import WorkflowRun, WorkflowStep


@dataclass(frozen=True, slots=True)
class WorkflowStepSpec:
    """Describe a milestone before a workflow run is created."""

    step_key: str
    step_type: str
    position: int
    input_data: dict[str, object] = field(default_factory=dict)


StepHandler = Callable[
    [
        AsyncSession,
        dict[str, object],
        dict[str, dict[str, object]],
    ],
    Awaitable[dict[str, object]],
]


class WorkflowStepError(RuntimeError):
    """Indicate that a workflow milestone failed."""

    def __init__(self, step_key: str, message: str) -> None:
        self.step_key = step_key
        super().__init__(f"Workflow step '{step_key}' failed: {message}")


async def create_workflow_run(
    session: AsyncSession,
    *,
    workflow_name: str,
    workflow_version: str,
    definition_hash: str,
    steps: Sequence[WorkflowStepSpec],
) -> WorkflowRun:
    """Create a workflow run and all its pending milestone records.

    This function does not commit. The caller owns the transaction.
    """
    if not workflow_name.strip():
        raise ValueError("Workflow name cannot be empty.")

    if not workflow_version.strip():
        raise ValueError("Workflow version cannot be empty.")

    if not definition_hash.strip():
        raise ValueError("Workflow definition hash cannot be empty.")

    if not steps:
        raise ValueError("A workflow must contain at least one step.")

    step_keys = [step.step_key for step in steps]
    if len(step_keys) != len(set(step_keys)):
        raise ValueError("Workflow step keys must be unique.")

    if any(not step_key.strip() for step_key in step_keys):
        raise ValueError("Workflow step keys cannot be empty.")

    run = WorkflowRun(
        workflow_name=workflow_name.strip(),
        workflow_version=workflow_version.strip(),
        definition_hash=definition_hash,
        status="pending",
    )
    session.add(run)
    await session.flush()

    for spec in sorted(steps, key=lambda item: item.position):
        if not spec.step_type.strip():
            raise ValueError(f"Step '{spec.step_key}' must have a step type.")

        session.add(
            WorkflowStep(
                workflow_run_id=run.id,
                step_key=spec.step_key,
                step_type=spec.step_type,
                position=spec.position,
                status="pending",
                attempt_count=0,
                input_data=dict(spec.input_data),
                output_data={},
            )
        )

    await session.flush()
    return run


async def execute_workflow_run(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    run_id: str,
    handlers: Mapping[str, StepHandler],
) -> None:
    """Execute pending milestones and skip already completed milestones.

    Each milestone's database changes and completed checkpoint are committed
    in the same transaction. A failed milestone is rolled back and recorded
    as failed in a separate transaction.
    """
    async with session_factory() as session:
        run = await session.get(WorkflowRun, run_id)
        if run is None:
            raise ValueError(f"Workflow run not found: {run_id}")

        result = await session.execute(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_run_id == run_id)
            .order_by(WorkflowStep.position)
        )
        steps = list(result.scalars().all())

    if not steps:
        raise ValueError(f"Workflow run has no steps: {run_id}")

    completed_outputs: dict[str, dict[str, object]] = {
        step.step_key: dict(step.output_data) for step in steps if step.status == "completed"
    }

    async with session_factory() as session, session.begin():
        run = await session.get(WorkflowRun, run_id)
        if run is None:
            raise ValueError(f"Workflow run not found: {run_id}")

        run.status = "running"
        run.completed_at = None
        run.error_message = None
        if run.started_at is None:
            run.started_at = datetime.now(UTC)

    for step_snapshot in steps:
        if step_snapshot.status == "completed":
            continue

        handler = handlers.get(step_snapshot.step_type)
        if handler is None:
            error_message = f"No handler registered for step type '{step_snapshot.step_type}'."
            await _record_step_failure(
                session_factory,
                run_id=run_id,
                step_key=step_snapshot.step_key,
                error_message=error_message,
            )
            raise WorkflowStepError(
                step_snapshot.step_key,
                error_message,
            )

        # Persist the attempt before starting the milestone.
        async with session_factory() as session, session.begin():
            step = await session.scalar(
                select(WorkflowStep).where(
                    WorkflowStep.workflow_run_id == run_id,
                    WorkflowStep.step_key == step_snapshot.step_key,
                )
            )
            if step is None:
                raise ValueError(f"Workflow step not found: {step_snapshot.step_key}")

            if step.status == "completed":
                completed_outputs[step.step_key] = dict(step.output_data)
                continue

            step.status = "running"
            step.attempt_count += 1
            step.started_at = datetime.now(UTC)
            step.completed_at = None
            step.error_message = None

        try:
            # The handler's database writes and the completed checkpoint
            # share this transaction.
            async with session_factory() as session, session.begin():
                step = await session.scalar(
                    select(WorkflowStep).where(
                        WorkflowStep.workflow_run_id == run_id,
                        WorkflowStep.step_key == step_snapshot.step_key,
                    )
                )
                if step is None:
                    raise ValueError(f"Workflow step not found: {step_snapshot.step_key}")

                output_data = await handler(
                    session,
                    dict(step.input_data),
                    dict(completed_outputs),
                )

                if not isinstance(output_data, dict):
                    raise TypeError("A workflow step handler must return a dictionary.")

                step.output_data = output_data
                step.status = "completed"
                step.completed_at = datetime.now(UTC)
                step.error_message = None

            completed_outputs[step_snapshot.step_key] = output_data

        except Exception as exc:
            error_message = str(exc) or type(exc).__name__
            await _record_step_failure(
                session_factory,
                run_id=run_id,
                step_key=step_snapshot.step_key,
                error_message=error_message,
            )
            raise WorkflowStepError(
                step_snapshot.step_key,
                error_message,
            ) from exc

    async with session_factory() as session, session.begin():
        run = await session.get(WorkflowRun, run_id)
        if run is None:
            raise ValueError(f"Workflow run not found: {run_id}")

        run.status = "completed"
        run.completed_at = datetime.now(UTC)
        run.error_message = None


async def _record_step_failure(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    run_id: str,
    step_key: str,
    error_message: str,
) -> None:
    """Persist a failed step and its parent run status."""
    async with session_factory() as session, session.begin():
        step = await session.scalar(
            select(WorkflowStep).where(
                WorkflowStep.workflow_run_id == run_id,
                WorkflowStep.step_key == step_key,
            )
        )
        run = await session.get(WorkflowRun, run_id)

        if step is not None:
            step.status = "failed"
            step.error_message = error_message[:4000]

        if run is not None:
            run.status = "failed"
            run.error_message = error_message[:4000]
