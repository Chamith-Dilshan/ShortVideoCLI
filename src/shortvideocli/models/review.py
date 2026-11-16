"""Human review decision database model."""

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shortvideocli.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class ReviewDecision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A human decision concerning a candidate moment or generated clip."""

    __tablename__ = "review_decisions"

    __table_args__ = (
        CheckConstraint(
            "(moment_id IS NOT NULL AND clip_id IS NULL) OR "
            "(moment_id IS NULL AND clip_id IS NOT NULL)",
            name="ck_review_exactly_one_target",
        ),
    )

    moment_id: Mapped[str | None] = mapped_column(
        ForeignKey("moment_candidates.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    clip_id: Mapped[str | None] = mapped_column(
        ForeignKey("clips.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    decision: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    reviewer: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
