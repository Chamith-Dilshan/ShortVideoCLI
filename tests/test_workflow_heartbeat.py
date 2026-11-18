"""Tests for workflow execution heartbeat management."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shortvideocli.models import Base, WorkflowRun
from shortvideocli.workflow_engine import (
    WorkflowStepSpec,
    _run_workflow_heartbeat,
    _update_workflow_heartbeat,
    create_workflow_run,
)


async def create_running_workflow(session_factory):
    """Create a running workflow with an execution owner."""
    async with session_factory() as session, session.begin():
        run = await create_workflow_run(
            session,
            workflow_name="Heartbeat test",
            workflow_version="1",
            definition_hash="heartbeat-test",
            steps=[
                WorkflowStepSpec(
                    step_key="step-one",
                    step_type="test.step",
                    position=1,
                ),
            ],
        )

        run.status = "running"
        run.execution_id = "execution-one"

        return str(run.id)


async def test_heartbeat_updates_owned_workflow():
    """The current execution should be able to update its heartbeat."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        run_id = await create_running_workflow(session_factory)

        updated = await _update_workflow_heartbeat(
            session_factory,
            run_id=run_id,
            execution_id="execution-one",
        )

        assert updated is True

        async with session_factory() as session:
            run = await session.get(WorkflowRun, run_id)

            assert run is not None
            assert run.last_heartbeat_at is not None

    finally:
        await engine.dispose()


async def test_heartbeat_rejects_wrong_execution_id():
    """An old execution must not update a newer execution's heartbeat."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        run_id = await create_running_workflow(session_factory)

        updated = await _update_workflow_heartbeat(
            session_factory,
            run_id=run_id,
            execution_id="old-execution",
        )

        assert updated is False

    finally:
        await engine.dispose()


async def test_heartbeat_rejects_completed_workflow():
    """A completed workflow must not receive further heartbeats."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        run_id = await create_running_workflow(session_factory)

        async with session_factory() as session, session.begin():
            run = await session.get(WorkflowRun, run_id)
            assert run is not None
            run.status = "completed"

        updated = await _update_workflow_heartbeat(
            session_factory,
            run_id=run_id,
            execution_id="execution-one",
        )

        assert updated is False

    finally:
        await engine.dispose()


async def test_periodic_heartbeat_stops_when_requested():
    """The heartbeat task should stop when its event is set."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        run_id = await create_running_workflow(session_factory)

        stop_event = asyncio.Event()

        heartbeat_task = asyncio.create_task(
            _run_workflow_heartbeat(
                session_factory,
                run_id=run_id,
                execution_id="execution-one",
                interval_seconds=60,
                stop_event=stop_event,
            )
        )

        stop_event.set()

        await asyncio.wait_for(heartbeat_task, timeout=2)

        assert heartbeat_task.done()

    finally:
        await engine.dispose()
