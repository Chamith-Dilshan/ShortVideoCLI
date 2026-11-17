"""Read-only queries for workflow history and inspection."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shortvideocli.models import WorkflowRun, WorkflowStep


async def list_workflow_runs(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    limit: int = 20,
) -> list[WorkflowRun]:
    """Return the most recently created workflow runs.

    Args:
        session_factory: Factory used to create asynchronous sessions.
        limit: Maximum number of workflow runs to return.

    Returns:
        Workflow runs ordered from newest to oldest.

    Raises:
        ValueError: If the requested limit is less than one.
    """
    if limit < 1:
        raise ValueError("Workflow history limit must be at least 1.")

    async with session_factory() as session:
        result = await session.execute(
            select(WorkflowRun).order_by(WorkflowRun.created_at.desc()).limit(limit)
        )

        return list(result.scalars().all())


async def get_workflow_run_details(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    run_id: str,
) -> tuple[WorkflowRun, list[WorkflowStep]] | None:
    """Return a workflow run and its milestones.

    Args:
        session_factory: Factory used to create asynchronous sessions.
        run_id: ID of the workflow run to inspect.

    Returns:
        A tuple containing the workflow run and its ordered milestones,
        or None if the run does not exist.
    """
    async with session_factory() as session:
        run = await session.get(WorkflowRun, run_id)

        if run is None:
            return None

        result = await session.execute(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_run_id == run_id)
            .order_by(WorkflowStep.position)
        )

        steps = list(result.scalars().all())

        return run, steps
