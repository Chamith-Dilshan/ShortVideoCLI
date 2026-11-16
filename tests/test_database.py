"""Tests for the initial database schema."""

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from shortvideocli.models import Base, Project, VideoSource


def test_database_schema_creation() -> None:
    """All expected application tables should be registered."""
    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(engine)

    table_names = set(inspect(engine).get_table_names())

    assert {
        "projects",
        "video_sources",
        "investigations",
        "moment_candidates",
        "clips",
        "assets",
        "review_decisions",
    }.issubset(table_names)

    engine.dispose()


def test_project_and_source_relationship() -> None:
    """A project should be able to own a video source."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        project = Project(name="Test gameplay project")

        source = VideoSource(
            platform="youtube",
            source_url="https://www.youtube.com/watch?v=example",
            rights_note="I own this recording and have permission to edit it.",
        )

        project.sources.append(source)
        session.add(project)
        session.commit()

        saved_project = session.get(Project, project.id)

        assert saved_project is not None
        assert len(saved_project.sources) == 1
        assert saved_project.sources[0].platform == "youtube"

    engine.dispose()
