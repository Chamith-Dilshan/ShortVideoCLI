"""Database operations for video-source management.

Transaction boundaries are owned by the caller, not by this service.
"""

from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shortvideocli.models import Project, VideoSource


def validate_source_url(source_url: str) -> str:
    """Validate an HTTP or HTTPS video URL."""

    clean_url = source_url.strip()
    parsed = urlparse(clean_url)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Source URL must be a valid HTTP or HTTPS URL.")

    return clean_url


async def create_source(
    session: AsyncSession,
    *,
    project_id: str,
    platform: str,
    source_url: str,
    rights_note: str,
    title: str | None = None,
) -> VideoSource:
    """Register a source without committing the surrounding transaction."""

    clean_platform = platform.strip().lower()
    clean_rights_note = rights_note.strip()
    clean_url = validate_source_url(source_url)

    if not clean_platform:
        raise ValueError("Platform cannot be empty.")

    if not clean_rights_note:
        raise ValueError("A rights note is required.")

    project = await session.get(Project, project_id)

    if project is None:
        raise ValueError(f"Project not found: {project_id}")

    existing_source = await session.scalar(
        select(VideoSource).where(
            VideoSource.project_id == project_id,
            VideoSource.source_url == clean_url,
        )
    )

    if existing_source is not None:
        raise ValueError("This video source is already registered in this project.")

    source = VideoSource(
        project_id=project_id,
        platform=clean_platform,
        source_url=clean_url,
        rights_note=clean_rights_note,
        title=title.strip() if title else None,
    )

    session.add(source)
    await session.flush()
    await session.refresh(source)

    return source


async def list_sources(
    session: AsyncSession,
    project_id: str,
) -> list[VideoSource]:
    """Return a project's sources, newest first."""

    result = await session.execute(
        select(VideoSource)
        .where(VideoSource.project_id == project_id)
        .order_by(VideoSource.created_at.desc())
    )

    return list(result.scalars().all())
