"""Tests for refreshing inputs when resuming workflows."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from shortvideocli.models import Base, WorkflowRun, WorkflowStep
from shortvideocli.workflow_engine import (
    WorkflowStepSpec,
    create_workflow_run,
)
from shortvideocli.workflows import _refresh_incomplete_step_inputs


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
