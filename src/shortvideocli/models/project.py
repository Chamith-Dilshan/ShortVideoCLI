"""Project database model."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shortvideocli.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A workspace containing related video production work."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    sources: Mapped[list["VideoSource"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
