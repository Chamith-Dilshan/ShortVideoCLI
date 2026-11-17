"""Database operations for project management.

Transaction boundaries are owned by the caller, not by this service.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shortvideocli.models import Project


async def create_project(
    session: AsyncSession,
    *,
    name: str,
    description: str | None = None,
) -> Project:
    """Create a project without committing the surrounding transaction."""

    clean_name = name.strip()

    if not clean_name:
        raise ValueError("Project name cannot be empty.")

    project = Project(
        name=clean_name,
        description=description.strip() if description else None,
    )

    session.add(project)
    await session.flush()
    await session.refresh(project)

    return project


async def list_projects(session: AsyncSession) -> list[Project]:
    """Return projects ordered from newest to oldest."""

    result = await session.execute(select(Project).order_by(Project.created_at.desc()))
    return list(result.scalars().all())


async def get_project(
    session: AsyncSession,
    project_id: str,
) -> Project | None:
    """Find a project by its primary key."""

    return await session.get(Project, project_id)
