"""Execute workflows with persistent, resumable milestone checkpoints."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shortvideocli.models import WorkflowRun, WorkflowStep

logger = logging.getLogger(__name__)


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


class WorkflowExecutionOwnershipLost(RuntimeError):
    """Raised when a workflow execution no longer owns its run."""


async def _record_owned_step_failure(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    run_id: str,
    step_key: str,
    execution_id: str,
    error_message: str,
) -> bool:
    """Record a step failure only if this execution still owns the run."""
    async with session_factory() as session, session.begin():
        claim_result = await session.execute(
            update(WorkflowRun)
            .where(
                WorkflowRun.id == run_id,
                WorkflowRun.status == "running",
                WorkflowRun.execution_id == execution_id,
            )
            .values(
                status="failed",
                error_message=error_message[:4000],
            )
        )

        if claim_result.rowcount != 1:
            return False

        await session.execute(
            update(WorkflowStep)
            .where(
                WorkflowStep.workflow_run_id == run_id,
                WorkflowStep.step_key == step_key,
            )
            .values(
                status="failed",
                error_message=error_message[:4000],
            )
        )

    return True


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


async def _update_workflow_heartbeat(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    run_id: str,
    execution_id: str,
) -> bool:
    """Update the heartbeat if this process still owns the workflow run.

    The conditional update prevents an older execution from updating the
    heartbeat after ownership has changed or the workflow has stopped.

    Args:
        session_factory: Factory for creating independent database sessions.
        run_id: ID of the workflow run.
        execution_id: Unique ID of the current execution attempt.

    Returns:
        True if the heartbeat was updated, otherwise False.
    """
    async with session_factory() as session, session.begin():
        result = await session.execute(
            update(WorkflowRun)
            .where(
                WorkflowRun.id == run_id,
                WorkflowRun.status == "running",
                WorkflowRun.execution_id == execution_id,
            )
            .values(last_heartbeat_at=datetime.now(UTC))
        )

    return result.rowcount == 1


async def _run_workflow_heartbeat(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    run_id: str,
    execution_id: str,
    interval_seconds: int,
    stop_event: asyncio.Event,
) -> None:
    """Periodically update the heartbeat while a workflow is executing.

    Heartbeat failures are logged and retried on the next interval. If this
    execution no longer owns the workflow run, the heartbeat task stops.

    Args:
        session_factory: Factory for creating independent database sessions.
        run_id: ID of the workflow run.
        execution_id: Unique ID of the current execution attempt.
        interval_seconds: Number of seconds between heartbeat updates.
        stop_event: Event used to stop the heartbeat task.
    """
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=interval_seconds,
            )
            break
        except TimeoutError:
            pass

        try:
            updated = await _update_workflow_heartbeat(
                session_factory,
                run_id=run_id,
                execution_id=execution_id,
            )
        except Exception:
            logger.exception(
                "Could not update heartbeat for workflow run %s",
                run_id,
            )
            continue

        if not updated:
            logger.warning(
                "Heartbeat stopped because execution ownership was lost for workflow run %s",
                run_id,
            )
            break


async def execute_workflow_run(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    run_id: str,
    handlers: Mapping[str, StepHandler],
    heartbeat_interval_seconds: int = 30,
) -> None:
    """Execute pending milestones while maintaining execution ownership.

    Only pending or failed runs can be claimed. Each execution receives a
    unique identifier so that stale processes cannot overwrite newer runs.

    A background task periodically updates the workflow heartbeat.
    Each milestone's database changes and completed checkpoint are committed
    in the same transaction.

    A failed milestone is rolled back and recorded as failed in a separate
    transaction, provided this execution still owns the workflow run.
    """
    if heartbeat_interval_seconds <= 0:
        raise ValueError("Heartbeat interval must be greater than zero.")

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

    # Assign a unique identifier to this execution attempt.
    execution_id = str(uuid4())
    now = datetime.now(UTC)

    # Atomically claim the workflow run.
    async with session_factory() as session, session.begin():
        claim_result = await session.execute(
            update(WorkflowRun)
            .where(
                WorkflowRun.id == run_id,
                WorkflowRun.status.in_(["pending", "failed"]),
            )
            .values(
                status="running",
                execution_id=execution_id,
                last_heartbeat_at=now,
                heartbeat_interval_seconds=heartbeat_interval_seconds,
                completed_at=None,
                error_message=None,
            )
        )

        if claim_result.rowcount != 1:
            current_status = await session.scalar(
                select(WorkflowRun.status).where(WorkflowRun.id == run_id)
            )

            if current_status is None:
                raise ValueError(f"Workflow run not found: {run_id}")

            raise ValueError(
                f"Cannot execute workflow run '{run_id}' because "
                f"its current status is '{current_status}'. "
                "Only pending or failed workflow runs can be executed."
            )

        # Set started_at only on the first execution attempt.
        await session.execute(
            update(WorkflowRun)
            .where(
                WorkflowRun.id == run_id,
                WorkflowRun.started_at.is_(None),
            )
            .values(started_at=now)
        )

    completed_outputs: dict[str, dict[str, object]] = {
        step.step_key: dict(step.output_data) for step in steps if step.status == "completed"
    }

    # Start the background heartbeat after successfully claiming the run.
    stop_event = asyncio.Event()

    heartbeat_task = asyncio.create_task(
        _run_workflow_heartbeat(
            session_factory,
            run_id=run_id,
            execution_id=execution_id,
            interval_seconds=heartbeat_interval_seconds,
            stop_event=stop_event,
        )
    )

    try:
        for step_snapshot in steps:
            if step_snapshot.status == "completed":
                continue

            handler = handlers.get(step_snapshot.step_type)

            if handler is None:
                error_message = f"No handler registered for step type '{step_snapshot.step_type}'."

                recorded = await _record_owned_step_failure(
                    session_factory,
                    run_id=run_id,
                    step_key=step_snapshot.step_key,
                    execution_id=execution_id,
                    error_message=error_message,
                )

                if not recorded:
                    raise WorkflowExecutionOwnershipLost(
                        f"Execution ownership lost for workflow run '{run_id}'."
                    )

                raise WorkflowStepError(
                    step_snapshot.step_key,
                    error_message,
                )

            # Persist the attempt before starting the milestone.
            async with session_factory() as session, session.begin():
                ownership_result = await session.execute(
                    update(WorkflowRun)
                    .where(
                        WorkflowRun.id == run_id,
                        WorkflowRun.status == "running",
                        WorkflowRun.execution_id == execution_id,
                    )
                    .values(last_heartbeat_at=datetime.now(UTC))
                )

                if ownership_result.rowcount != 1:
                    raise WorkflowExecutionOwnershipLost(
                        f"Execution ownership lost for workflow run '{run_id}'."
                    )

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
                # The handler's database writes and completed checkpoint
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

                    # Verify ownership immediately before committing the
                    # handler's changes and completed checkpoint.
                    ownership_result = await session.execute(
                        update(WorkflowRun)
                        .where(
                            WorkflowRun.id == run_id,
                            WorkflowRun.status == "running",
                            WorkflowRun.execution_id == execution_id,
                        )
                        .values(last_heartbeat_at=datetime.now(UTC))
                    )

                    if ownership_result.rowcount != 1:
                        raise WorkflowExecutionOwnershipLost(
                            f"Execution ownership lost for workflow run '{run_id}'."
                        )

                    step.output_data = output_data
                    step.status = "completed"
                    step.completed_at = datetime.now(UTC)
                    step.error_message = None

                completed_outputs[step_snapshot.step_key] = output_data

            except WorkflowExecutionOwnershipLost:
                # Do not let an old execution modify a run owned by another
                # execution or recovered by the user.
                raise

            except Exception as exc:
                error_message = str(exc) or type(exc).__name__

                recorded = await _record_owned_step_failure(
                    session_factory,
                    run_id=run_id,
                    step_key=step_snapshot.step_key,
                    execution_id=execution_id,
                    error_message=error_message,
                )

                if not recorded:
                    raise WorkflowExecutionOwnershipLost(
                        f"Execution ownership lost for workflow run '{run_id}'."
                    ) from exc

                raise WorkflowStepError(
                    step_snapshot.step_key,
                    error_message,
                ) from exc

        # Complete the workflow only if this execution still owns it.
        async with session_factory() as session, session.begin():
            completion_result = await session.execute(
                update(WorkflowRun)
                .where(
                    WorkflowRun.id == run_id,
                    WorkflowRun.status == "running",
                    WorkflowRun.execution_id == execution_id,
                )
                .values(
                    status="completed",
                    completed_at=datetime.now(UTC),
                    error_message=None,
                )
            )

            if completion_result.rowcount != 1:
                raise WorkflowExecutionOwnershipLost(
                    f"Execution ownership lost for workflow run '{run_id}'."
                )

    finally:
        # Stop and await the heartbeat task regardless of success or failure.
        stop_event.set()
        await heartbeat_task


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


async def recover_interrupted_workflow_run(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    run_id: str,
    reason: str = "Workflow execution was interrupted.",
) -> int:
    """Mark an interrupted workflow run as failed so it can be resumed.

    This operation does not execute any workflow steps. It changes the run
    status from running to failed and marks any running steps as failed.
    Completed steps and their output data are preserved.

    The caller must first confirm that no process is still executing this
    workflow run. There is no automatic stale-run detection in this version.

    Args:
        session_factory: Factory used to create asynchronous database sessions.
        run_id: ID of the workflow run to recover.
        reason: Explanation recorded on the run and interrupted steps.

    Returns:
        The number of steps that were marked as failed.

    Raises:
        ValueError: If the run does not exist or is not currently running.
    """
    clean_reason = reason.strip()
    if not clean_reason:
        raise ValueError("Recovery reason cannot be empty.")

    async with session_factory() as session, session.begin():
        claim_result = await session.execute(
            update(WorkflowRun)
            .where(
                WorkflowRun.id == run_id,
                WorkflowRun.status == "running",
            )
            .values(
                status="failed",
                completed_at=None,
                error_message=clean_reason,
            )
        )

        if claim_result.rowcount != 1:
            run = await session.get(WorkflowRun, run_id)

            if run is None:
                raise ValueError(f"Workflow run '{run_id}' was not found.")

            raise ValueError(
                f"Cannot recover workflow run '{run_id}' because "
                f"its current status is '{run.status}'. "
                "Only running workflows can be recovered."
            )

        now = datetime.now(UTC)

        step_result = await session.execute(
            update(WorkflowStep)
            .where(
                WorkflowStep.workflow_run_id == run_id,
                WorkflowStep.status == "running",
            )
            .values(
                status="failed",
                completed_at=now,
                error_message=clean_reason,
            )
        )

        interrupted_steps = step_result.rowcount or 0

    return interrupted_steps
