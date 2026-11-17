"""Tests for project and video-source services."""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shortvideocli.models import Base
from shortvideocli.services.projects import create_project, list_projects
from shortvideocli.services.sources import create_source, list_sources


@pytest.fixture
async def test_session():
    """Provide an isolated in-memory asynchronous database session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_create_and_list_project(test_session) -> None:
    """A project should be created and returned by the listing service."""
    project = await create_project(
        test_session,
        name="Gameplay Highlights",
        description="Interesting gameplay moments",
    )

    projects = await list_projects(test_session)

    assert project.id
    assert project.name == "Gameplay Highlights"
    assert len(projects) == 1


@pytest.mark.asyncio
async def test_reject_empty_project_name(test_session) -> None:
    """Project names cannot be empty."""
    with pytest.raises(ValueError, match="cannot be empty"):
        await create_project(test_session, name="   ")


@pytest.mark.asyncio
async def test_create_and_list_source(test_session) -> None:
    """A video source should be registered under its parent project."""
    project = await create_project(
        test_session,
        name="Gameplay Project",
    )

    source = await create_source(
        test_session,
        project_id=project.id,
        platform="youtube",
        source_url="https://www.youtube.com/watch?v=example",
        rights_note="I own this gameplay recording.",
        title="Test gameplay",
    )

    sources = await list_sources(test_session, project.id)

    assert source.project_id == project.id
    assert source.platform == "youtube"
    assert len(sources) == 1


@pytest.mark.asyncio
async def test_source_requires_rights_note(test_session) -> None:
    """A source cannot be registered without a rights note."""
    project = await create_project(
        test_session,
        name="Gameplay Project",
    )

    with pytest.raises(ValueError, match="rights note is required"):
        await create_source(
            test_session,
            project_id=project.id,
            platform="youtube",
            source_url="https://www.youtube.com/watch?v=example",
            rights_note="   ",
        )


@pytest.mark.asyncio
async def test_source_requires_existing_project(test_session) -> None:
    """A source cannot reference a project that does not exist."""
    with pytest.raises(ValueError, match="Project not found"):
        await create_source(
            test_session,
            project_id="nonexistent-project",
            platform="youtube",
            source_url="https://www.youtube.com/watch?v=example",
            rights_note="I have permission to use this video.",
        )
