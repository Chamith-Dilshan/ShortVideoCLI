"""Tests for refreshing inputs when resuming workflows."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

import shortvideocli.workflows as workflows
from shortvideocli.models import Base, WorkflowRun, WorkflowStep
from shortvideocli.models.project import Project
from shortvideocli.workflow_engine import (
    WorkflowStepSpec,
    create_workflow_run,
)
from shortvideocli.workflows import (
    _refresh_incomplete_step_inputs,
    restart_workflow_run,
    retry_workflow_run,
)


async def test_resume_refreshes_failed_step_without_repeating_completed_step():
    """Corrected YAML inputs update failed steps but preserve completed ones."""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        original_workflow = {
            "name": "Gameplay research",
            "version": "1",
            "steps": [
                {
                    "id": "gameplay",
                    "action": "project.create",
                    "name": "Gameplay Highlights",
                },
                {
                    "action": "source.add",
                    "project": "gameplay",
                    "platform": "youtube",
                    "url": "invalid-url",
                    "rights_note": "Research only.",
                },
            ],
        }

        corrected_workflow = {
            "name": "Gameplay research",
            "version": "1",
            "steps": [
                {
                    "id": "gameplay",
                    "action": "project.create",
                    "name": "Gameplay Highlights",
                },
                {
                    "action": "source.add",
                    "project": "gameplay",
                    "platform": "youtube",
                    "url": "https://youtu.be/example",
                    "rights_note": "Research only.",
                },
            ],
        }

        async with session_factory() as session, session.begin():
            run = await create_workflow_run(
                session,
                workflow_name="Gameplay research",
                workflow_version="1",
                definition_hash="original-hash",
                steps=[
                    WorkflowStepSpec(
                        step_key="gameplay",
                        step_type="project.create",
                        position=1,
                        input_data={
                            "id": "gameplay",
                            "action": "project.create",
                            "name": "Gameplay Highlights",
                        },
                    ),
                    WorkflowStepSpec(
                        step_key="step-2",
                        step_type="source.add",
                        position=2,
                        input_data={
                            "action": "source.add",
                            "project": "gameplay",
                            "platform": "youtube",
                            "url": "invalid-url",
                            "rights_note": "Research only.",
                        },
                    ),
                ],
            )
            run_id = str(run.id)

        # Simulate the first step succeeding and the second step failing.
        async with session_factory() as session, session.begin():
            steps = list(
                (
                    await session.scalars(
                        select(WorkflowStep)
                        .where(WorkflowStep.workflow_run_id == run_id)
                        .order_by(WorkflowStep.position)
                    )
                ).all()
            )

            steps[0].status = "completed"
            steps[0].output_data = {
                "project_id": "existing-project-id",
                "project_name": "Gameplay Highlights",
            }

            steps[1].status = "failed"
            steps[1].input_data["url"] = "invalid-url"

        await _refresh_incomplete_step_inputs(
            session_factory,
            run_id,
            corrected_workflow,
        )

        async with session_factory() as session:
            steps = list(
                (
                    await session.scalars(
                        select(WorkflowStep)
                        .where(WorkflowStep.workflow_run_id == run_id)
                        .order_by(WorkflowStep.position)
                    )
                ).all()
            )

            # The completed project step must remain completed.
            assert steps[0].status == "completed"
            assert steps[0].output_data["project_id"] == "existing-project-id"

            # The failed source step must receive the corrected URL.
            assert steps[1].status == "failed"
            assert steps[1].input_data["url"] == "https://youtu.be/example"

    finally:
        await engine.dispose()


async def _create_workflow_run_for_recovery(
    session_factory: async_sessionmaker,
    *,
    run_status: str,
) -> str:
    """Create a workflow run with one completed and one failed milestone."""
    async with session_factory() as session, session.begin():
        run = await create_workflow_run(
            session,
            workflow_name="Recovery test",
            workflow_version="1",
            definition_hash="test-hash",
            steps=[
                WorkflowStepSpec(
                    step_key="completed-step",
                    step_type="test.completed",
                    position=1,
                    input_data={"name": "Already completed"},
                ),
                WorkflowStepSpec(
                    step_key="failed-step",
                    step_type="test.succeed",
                    position=2,
                    input_data={"name": "Needs retry"},
                ),
            ],
        )

        steps = list(
            (
                await session.scalars(
                    select(WorkflowStep)
                    .where(WorkflowStep.workflow_run_id == run.id)
                    .order_by(WorkflowStep.position)
                )
            ).all()
        )

        steps[0].status = "completed"
        steps[0].output_data = {"result": "preserved"}

        steps[1].status = "failed"
        steps[1].error_message = "Simulated failure"

        run.status = run_status

        return str(run.id)


async def test_retry_reruns_failed_step_and_skips_completed_step(monkeypatch):
    """Retry must execute only failed or pending milestones."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    calls: list[str] = []

    async def successful_handler(session, input_data, completed_outputs):
        """Simulate a milestone that succeeds on retry."""
        calls.append(input_data["name"])

        assert completed_outputs["completed-step"] == {"result": "preserved"}

        return {"result": "recovered"}

    monkeypatch.setattr(
        workflows,
        "_get_handlers",
        lambda: {"test.succeed": successful_handler},
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        run_id = await _create_workflow_run_for_recovery(
            session_factory,
            run_status="failed",
        )

        await retry_workflow_run(run_id, session_factory)

        assert calls == ["Needs retry"]

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
            assert steps[0].output_data == {"result": "preserved"}

            assert steps[1].status == "completed"
            assert steps[1].output_data == {"result": "recovered"}
            assert steps[1].attempt_count == 1

    finally:
        await engine.dispose()


async def test_retry_rejects_workflow_that_is_not_failed():
    """Retry must reject pending, running, and completed workflow runs."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        run_id = await _create_workflow_run_for_recovery(
            session_factory,
            run_status="completed",
        )

        try:
            await retry_workflow_run(run_id, session_factory)
        except ValueError as exc:
            assert "Only failed workflows can be retried" in str(exc)
        else:
            raise AssertionError("Expected retry to reject a completed run.")

    finally:
        await engine.dispose()


async def test_restart_creates_new_run_and_preserves_original(monkeypatch):
    """Restart must create a separate recovery run without changing the original."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    calls: list[str] = []

    async def successful_handler(session, input_data, completed_outputs):
        """Simulate a successful recovery milestone."""
        calls.append(input_data["name"])

        assert completed_outputs["completed-step"] == {"result": "preserved"}

        return {"result": "recovered"}

    monkeypatch.setattr(
        workflows,
        "_get_handlers",
        lambda: {"test.succeed": successful_handler},
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        original_run_id = await _create_workflow_run_for_recovery(
            session_factory,
            run_status="failed",
        )

        results = await restart_workflow_run(
            original_run_id,
            session_factory,
        )

        assert calls == ["Needs retry"]
        assert results[0].startswith("Created recovery run:")

        new_run_id = results[0].split(": ", maxsplit=1)[1]

        assert new_run_id != original_run_id

        async with session_factory() as session:
            original_run = await session.get(
                WorkflowRun,
                original_run_id,
            )
            new_run = await session.get(
                WorkflowRun,
                new_run_id,
            )

            assert original_run is not None
            assert new_run is not None

            # The original run must remain unchanged.
            assert original_run.status == "failed"

            # The new recovery run must complete.
            assert new_run.status == "completed"

            new_steps = list(
                (
                    await session.scalars(
                        select(WorkflowStep)
                        .where(WorkflowStep.workflow_run_id == new_run_id)
                        .order_by(WorkflowStep.position)
                    )
                ).all()
            )

            assert new_steps[0].status == "completed"
            assert new_steps[0].output_data == {"result": "preserved"}

            assert new_steps[1].status == "completed"
            assert new_steps[1].output_data == {"result": "recovered"}

    finally:
        await engine.dispose()


async def test_restart_does_not_duplicate_completed_project(monkeypatch):
    """Restart must reuse a completed project milestone instead of creating another project."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    calls: list[str] = []

    async def successful_handler(session, input_data, completed_outputs):
        """Verify the completed project output is available to later milestones."""
        calls.append(input_data["name"])

        project_output = completed_outputs["completed-step"]
        assert project_output["project_id"] == existing_project_id

        return {"result": "recovered"}

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with session_factory() as session, session.begin():
            project = Project(name="Existing project")
            session.add(project)
            await session.flush()
            existing_project_id = str(project.id)

        async with session_factory() as session, session.begin():
            run = await create_workflow_run(
                session,
                workflow_name="Project recovery test",
                workflow_version="1",
                definition_hash="project-test-hash",
                steps=[
                    WorkflowStepSpec(
                        step_key="completed-step",
                        step_type="project.create",
                        position=1,
                        input_data={
                            "name": "Existing project",
                        },
                    ),
                    WorkflowStepSpec(
                        step_key="failed-step",
                        step_type="test.succeed",
                        position=2,
                        input_data={
                            "name": "Continue workflow",
                        },
                    ),
                ],
            )

            run_id = str(run.id)

            steps = list(
                (
                    await session.scalars(
                        select(WorkflowStep)
                        .where(WorkflowStep.workflow_run_id == run_id)
                        .order_by(WorkflowStep.position)
                    )
                ).all()
            )

            steps[0].status = "completed"
            steps[0].output_data = {
                "project_id": existing_project_id,
            }

            steps[1].status = "failed"
            run.status = "failed"

        monkeypatch.setattr(
            workflows,
            "_get_handlers",
            lambda: {"test.succeed": successful_handler},
        )

        results = await restart_workflow_run(
            run_id,
            session_factory,
        )

        new_run_id = results[0].split(": ", maxsplit=1)[1]

        assert calls == ["Continue workflow"]

        async with session_factory() as session:
            project_count = await session.scalar(select(func.count()).select_from(Project))

            assert project_count == 1

            new_steps = list(
                (
                    await session.scalars(
                        select(WorkflowStep)
                        .where(WorkflowStep.workflow_run_id == new_run_id)
                        .order_by(WorkflowStep.position)
                    )
                ).all()
            )

            assert new_steps[0].status == "completed"
            assert new_steps[0].output_data["project_id"] == existing_project_id

            assert new_steps[1].status == "completed"

    finally:
        await engine.dispose()


async def test_restart_rejects_workflow_that_is_not_failed():
    """Restart must reject workflow runs that are not failed."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        run_id = await _create_workflow_run_for_recovery(
            session_factory,
            run_status="completed",
        )

        try:
            await restart_workflow_run(run_id, session_factory)
        except ValueError as exc:
            assert "Only failed workflows can be restarted" in str(exc)
        else:
            raise AssertionError("Expected restart to reject a completed run.")

    finally:
        await engine.dispose()
