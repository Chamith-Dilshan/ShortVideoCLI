"""Video investigation database model."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shortvideocli.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Investigation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A research and analysis run against a video source."""

    __tablename__ = "investigations"

    source_id: Mapped[str] = mapped_column(
        ForeignKey("video_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
    )

    investigation_level: Mapped[str] = mapped_column(
        String(30),
        default="standard",
        nullable=False,
    )

    summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    investigation_metadata: Mapped[dict | None] = mapped_column(JSON)

    source: Mapped["VideoSource"] = relationship(
        back_populates="investigations",
    )

    moments: Mapped[list["MomentCandidate"]] = relationship(
        back_populates="investigation",
        cascade="all, delete-orphan",
    )
