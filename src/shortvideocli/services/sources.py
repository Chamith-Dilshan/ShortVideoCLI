"""Business logic for registering and listing video sources."""

from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shortvideocli.models import Project, VideoSource


def validate_source_url(source_url: str) -> str:
    """Validate and normalize an HTTP or HTTPS source URL.

    Args:
        source_url: URL supplied by the user.

    Returns:
        A trimmed URL.

    Raises:
        ValueError: If the URL is invalid or uses an unsupported scheme.
    """
    normalized_url = source_url.strip()
    parsed = urlparse(normalized_url)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Source URL must be a valid HTTP or HTTPS URL.")

    return normalized_url


async def create_source(
    session: AsyncSession,
    *,
    project_id: str,
    platform: str,
    source_url: str,
    rights_note: str,
    title: str | None = None,
) -> VideoSource:
    """Register a video source under an existing project.

    The rights note is required so that the user records the basis on
    which they are entitled to investigate and edit the source.

    Args:
        session: Active asynchronous database session.
        project_id: UUID of the parent project.
        platform: Origin platform, such as YouTube or Twitch.
        source_url: Original video URL.
        rights_note: User-provided rights and permission note.
        title: Optional title supplied by the user.

    Returns:
        The newly persisted video source.

    Raises:
        ValueError: If input is invalid, the project does not exist,
            or the source is already registered in this project.
    """
    normalized_platform = platform.strip().lower()
    normalized_rights_note = rights_note.strip()

    if not normalized_platform:
        raise ValueError("Platform cannot be empty.")

    if not normalized_rights_note:
        raise ValueError("A rights note is required.")

    normalized_url = validate_source_url(source_url)

    project = await session.get(Project, project_id)

    if project is None:
        raise ValueError(f"Project not found: {project_id}")

    existing_statement = select(VideoSource).where(
        VideoSource.project_id == project_id,
        VideoSource.source_url == normalized_url,
    )

    existing_source = await session.scalar(existing_statement)

    if existing_source is not None:
        raise ValueError("This source is already registered in the project.")

    source = VideoSource(
        project_id=project_id,
        platform=normalized_platform,
        source_url=normalized_url,
        rights_note=normalized_rights_note,
        title=title.strip() if title else None,
    )

    session.add(source)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError(
            "This source could not be registered. It may already exist in this project."
        ) from exc

    await session.refresh(source)

    return source


async def list_sources(
    session: AsyncSession,
    project_id: str,
) -> list[VideoSource]:
    """Return all video sources registered under a project."""
    statement = (
        select(VideoSource)
        .where(VideoSource.project_id == project_id)
        .order_by(VideoSource.created_at.desc())
    )

    result = await session.scalars(statement)
    return list(result.all())
