"""Source video database model."""

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shortvideocli.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class VideoSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An original video submitted for investigation."""

    __tablename__ = "video_sources"

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "source_url",
            name="uq_source_project_url",
        ),
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    platform: Mapped[str] = mapped_column(String(40), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str | None] = mapped_column(Text)
    channel_name: Mapped[str | None] = mapped_column(String(300))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)

    # A right note must be supplied when a source is registered.
    rights_note: Mapped[str] = mapped_column(Text, nullable=False)

    source_metadata: Mapped[dict | None] = mapped_column(JSON)

    project: Mapped["Project"] = relationship(back_populates="sources")

    investigations: Mapped[list["Investigation"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )
