"""Tests for workflow execution and milestone checkpointing."""

import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shortvideocli.models import Base, WorkflowRun, WorkflowStep
from shortvideocli.workflow_engine import (
    WorkflowStepError,
    WorkflowStepSpec,
    create_workflow_run,
    execute_workflow_run,
    recover_interrupted_workflow_run,
)


async def create_test_run(session_factory):
    """Create a workflow run with two pending milestones."""
    async with session_factory() as session, session.begin():
        run = await create_workflow_run(
            session,
            workflow_name="Execution test",
            workflow_version="1",
            definition_hash="execution-test-hash",
            steps=[
                WorkflowStepSpec(
                    step_key="step-one",
                    step_type="test.first",
                    position=1,
                    input_data={"name": "First milestone"},
                ),
                WorkflowStepSpec(
                    step_key="step-two",
                    step_type="test.second",
                    position=2,
                    input_data={"name": "Second milestone"},
                ),
            ],
        )

        return str(run.id)


async def test_execute_workflow_completes_all_steps():
    """Execution should complete every pending milestone."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    calls = []

    async def first_handler(session, input_data, completed_outputs):
        """Return the first milestone result."""
        calls.append("first")
        return {"result": "first completed"}

    async def second_handler(session, input_data, completed_outputs):
        """Verify the first milestone output and complete the second."""
        calls.append("second")

        assert completed_outputs["step-one"] == {"result": "first completed"}

        return {"result": "second completed"}

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        run_id = await create_test_run(session_factory)

        await execute_workflow_run(
            session_factory,
            run_id=run_id,
            handlers={
                "test.first": first_handler,
                "test.second": second_handler,
            },
        )

        assert calls == ["first", "second"]

        async with session_factory() as session:
            run = await session.get(WorkflowRun, run_id)

            steps = list(
                (
                    await session.scalars(
                        select(WorkflowStep)
                        .where(WorkflowStep.workflow_run_id == run_id)
                        .order_by(WorkflowStep.position)
                    )
                ).all()
            )

            assert run is not None
            assert run.status == "completed"

            assert steps[0].status == "completed"
            assert steps[0].output_data == {"result": "first completed"}

            assert steps[1].status == "completed"
            assert steps[1].output_data == {"result": "second completed"}

    finally:
        await engine.dispose()


async def test_execute_workflow_rejects_concurrent_execution():
    """A second execution must be rejected while the first is running."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    handler_started = asyncio.Event()
    allow_handler_to_finish = asyncio.Event()

    async def blocking_handler(session, input_data, completed_outputs):
        """Pause execution so a second execution can be attempted."""
        handler_started.set()
        await allow_handler_to_finish.wait()
        return {"result": "completed"}

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with session_factory() as session, session.begin():
            run = await create_workflow_run(
                session,
                workflow_name="Concurrency test",
                workflow_version="1",
                definition_hash="concurrency-test-hash",
                steps=[
                    WorkflowStepSpec(
                        step_key="blocking-step",
                        step_type="test.blocking",
                        position=1,
                        input_data={},
                    ),
                ],
            )
            run_id = str(run.id)

        first_execution = asyncio.create_task(
            execute_workflow_run(
                session_factory,
                run_id=run_id,
                handlers={"test.blocking": blocking_handler},
            )
        )

        await asyncio.wait_for(
            handler_started.wait(),
            timeout=5,
        )

        with pytest.raises(ValueError, match="current status is 'running'"):
            await execute_workflow_run(
                session_factory,
                run_id=run_id,
                handlers={"test.blocking": blocking_handler},
            )

        allow_handler_to_finish.set()

        await first_execution

        async with session_factory() as session:
            run = await session.get(WorkflowRun, run_id)

            assert run is not None
            assert run.status == "completed"

    finally:
        allow_handler_to_finish.set()
        await engine.dispose()


async def test_execute_workflow_records_failed_step():
    """A failing milestone should be rolled back and recorded as failed."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async def failing_handler(session, input_data, completed_outputs):
        """Simulate a milestone failure."""
        raise ValueError("Simulated milestone failure")

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        run_id = await create_test_run(session_factory)

        with pytest.raises(WorkflowStepError):
            await execute_workflow_run(
                session_factory,
                run_id=run_id,
                handlers={
                    "test.first": failing_handler,
                    "test.second": failing_handler,
                },
            )

        async with session_factory() as session:
            run = await session.get(WorkflowRun, run_id)

            steps = list(
                (
                    await session.scalars(
                        select(WorkflowStep)
                        .where(WorkflowStep.workflow_run_id == run_id)
                        .order_by(WorkflowStep.position)
                    )
                ).all()
            )

            assert run is not None
            assert run.status == "failed"

            assert steps[0].status == "failed"
            assert steps[0].error_message == "Simulated milestone failure"

            assert steps[0].attempt_count == 1
            assert steps[1].status == "pending"

    finally:
        await engine.dispose()


async def test_recover_interrupted_workflow_marks_running_steps_failed():
    """Recovery should fail interrupted steps and preserve completed outputs."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        run_id = await create_test_run(session_factory)

        async with session_factory() as session, session.begin():
            run = await session.get(WorkflowRun, run_id)
            assert run is not None
            run.status = "running"

            result = await session.execute(
                select(WorkflowStep)
                .where(WorkflowStep.workflow_run_id == run_id)
                .order_by(WorkflowStep.position)
            )
            steps = list(result.scalars().all())

            steps[0].status = "completed"
            steps[0].output_data = {"result": "preserved"}

            steps[1].status = "running"

        interrupted_count = await recover_interrupted_workflow_run(
            session_factory,
            run_id=run_id,
            reason="Process stopped unexpectedly.",
        )

        assert interrupted_count == 1

        async with session_factory() as session:
            run = await session.get(WorkflowRun, run_id)
            assert run is not None
            assert run.status == "failed"
            assert run.error_message == "Process stopped unexpectedly."

            result = await session.execute(
                select(WorkflowStep)
                .where(WorkflowStep.workflow_run_id == run_id)
                .order_by(WorkflowStep.position)
            )
            steps = list(result.scalars().all())

            assert steps[0].status == "completed"
            assert steps[0].output_data == {"result": "preserved"}

            assert steps[1].status == "failed"
            assert steps[1].error_message == "Process stopped unexpectedly."

    finally:
        await engine.dispose()


async def test_recover_interrupted_workflow_rejects_non_running_run():
    """Recovery should reject a workflow that is not running."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        run_id = await create_test_run(session_factory)

        with pytest.raises(ValueError, match="Only running workflows"):
            await recover_interrupted_workflow_run(
                session_factory,
                run_id=run_id,
            )

    finally:
        await engine.dispose()


async def test_recover_interrupted_workflow_rejects_missing_run():
    """Recovery should reject an unknown workflow run ID."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        with pytest.raises(ValueError, match="was not found"):
            await recover_interrupted_workflow_run(
                session_factory,
                run_id="missing-run-id",
            )

    finally:
        await engine.dispose()
