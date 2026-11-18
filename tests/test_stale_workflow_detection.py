"""Tests for detecting stale workflow executions."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shortvideocli.models import Base, WorkflowRun
from shortvideocli.workflow_engine import find_stale_workflow_runs, recover_stale_workflow_runs


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    yield factory

    await engine.dispose()


async def create_running_run(
    session_factory,
    *,
    heartbeat_age_seconds: int,
    heartbeat_interval_seconds: int = 10,
):
    """Create a running workflow with a specified heartbeat age."""
    async with session_factory() as session, session.begin():
        run = WorkflowRun(
            workflow_name="test-workflow",
            workflow_version="1.0",
            definition_hash="test-hash",
            status="running",
            execution_id="execution-one",
            last_heartbeat_at=(datetime.now(UTC) - timedelta(seconds=heartbeat_age_seconds)),
            heartbeat_interval_seconds=heartbeat_interval_seconds,
        )
        session.add(run)
        await session.flush()

        return run.id


async def test_fresh_workflow_is_not_stale(session_factory):
    run_id = await create_running_run(
        session_factory,
        heartbeat_age_seconds=5,
    )

    stale_runs = await find_stale_workflow_runs(session_factory)

    assert run_id not in stale_runs


async def test_expired_workflow_is_stale(session_factory):
    run_id = await create_running_run(
        session_factory,
        heartbeat_age_seconds=35,
    )

    stale_runs = await find_stale_workflow_runs(session_factory)

    assert run_id in stale_runs


async def test_workflow_without_heartbeat_is_not_stale(session_factory):
    async with session_factory() as session, session.begin():
        run = WorkflowRun(
            workflow_name="legacy-workflow",
            workflow_version="1.0",
            definition_hash="legacy-hash",
            status="running",
            heartbeat_interval_seconds=10,
        )
        session.add(run)
        await session.flush()

        run_id = run.id

    stale_runs = await find_stale_workflow_runs(session_factory)

    assert run_id not in stale_runs


async def test_non_running_workflow_is_not_stale(session_factory):
    run_id = await create_running_run(
        session_factory,
        heartbeat_age_seconds=60,
    )

    async with session_factory() as session, session.begin():
        run = await session.get(WorkflowRun, run_id)
        assert run is not None
        run.status = "completed"

    stale_runs = await find_stale_workflow_runs(session_factory)

    assert run_id not in stale_runs


async def test_invalid_timeout_multiplier_is_rejected(session_factory):
    with pytest.raises(ValueError, match="at least one"):
        await find_stale_workflow_runs(
            session_factory,
            timeout_multiplier=0,
        )


async def test_expired_workflow_is_recovered(session_factory):
    run_id = await create_running_run(
        session_factory,
        heartbeat_age_seconds=35,
    )

    recovered_runs = await recover_stale_workflow_runs(session_factory)

    assert run_id in recovered_runs

    async with session_factory() as session:
        run = await session.get(WorkflowRun, run_id)

    assert run is not None
    assert run.status == "failed"
    assert run.error_message == ("Workflow heartbeat expired; recovered as interrupted.")


async def test_fresh_workflow_is_not_recovered(session_factory):
    run_id = await create_running_run(
        session_factory,
        heartbeat_age_seconds=5,
    )

    recovered_runs = await recover_stale_workflow_runs(session_factory)

    assert run_id not in recovered_runs

    async with session_factory() as session:
        run = await session.get(WorkflowRun, run_id)

    assert run is not None
    assert run.status == "running"
