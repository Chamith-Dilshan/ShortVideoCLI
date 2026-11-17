"""Business logic for project management."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shortvideocli.models import Project


async def create_project(
    session: AsyncSession,
    *,
    name: str,
    description: str | None = None,
) -> Project:
    """Create and persist a project.

    Args:
        session: Active asynchronous database session.
        name: Human-readable project name.
        description: Optional project description.

    Returns:
        The newly persisted project.

    Raises:
        ValueError: If the project name is empty.
    """
    normalized_name = name.strip()

    if not normalized_name:
        raise ValueError("Project name cannot be empty.")

    project = Project(
        name=normalized_name,
        description=description.strip() if description else None,
    )

    session.add(project)
    await session.commit()
    await session.refresh(project)

    return project


async def list_projects(
    session: AsyncSession,
) -> list[Project]:
    """Return all projects, newest first."""
    statement = select(Project).order_by(Project.created_at.desc())

    result = await session.scalars(statement)
    return list(result.all())


async def get_project(
    session: AsyncSession,
    project_id: str,
) -> Project | None:
    """Find a project by its UUID."""
    return await session.get(Project, project_id)
