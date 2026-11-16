"""External media asset and licensing database model."""

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shortvideocli.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Asset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An external media asset and its licensing/approval evidence."""

    __tablename__ = "assets"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    asset_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)

    license_name: Mapped[str | None] = mapped_column(String(200))
    commercial_use: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    attribution_text: Mapped[str | None] = mapped_column(Text)
    license_evidence_url: Mapped[str | None] = mapped_column(Text)

    approval_status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
    )

    download_approved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    downloaded_path: Mapped[str | None] = mapped_column(Text)
