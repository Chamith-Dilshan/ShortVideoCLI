"""Candidate moment database model."""

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shortvideocli.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class MomentCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A potentially engaging moment identified in an investigation."""

    __tablename__ = "moment_candidates"

    __table_args__ = (
        Index(
            "ix_moments_investigation_score",
            "investigation_id",
            "score",
        ),
    )

    investigation_id: Mapped[str] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    title: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)

    moment_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    status: Mapped[str] = mapped_column(
        String(30),
        default="new",
        nullable=False,
    )

    evidence: Mapped[dict | None] = mapped_column(JSON)

    investigation: Mapped["Investigation"] = relationship(
        back_populates="moments",
    )

    clips: Mapped[list["Clip"]] = relationship(
        back_populates="moment",
        cascade="all, delete-orphan",
    )
