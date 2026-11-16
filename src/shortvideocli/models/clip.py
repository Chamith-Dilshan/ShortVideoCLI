"""Generated clip database model."""

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shortvideocli.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Clip(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A clip prepared from a selected moment."""

    __tablename__ = "clips"

    moment_id: Mapped[str] = mapped_column(
        ForeignKey("moment_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    platform: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    output_path: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(30),
        default="draft",
        nullable=False,
    )

    export_settings: Mapped[dict | None] = mapped_column(JSON)

    moment: Mapped["MomentCandidate"] = relationship(
        back_populates="clips",
    )
