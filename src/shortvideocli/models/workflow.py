"""Database models for workflow execution and milestone recovery."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shortvideocli.models.base import (
    Base,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class WorkflowRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Represent one execution of a workflow definition.

    A run stores the workflow identity and its overall execution status.
    Individual milestone progress is stored in WorkflowStep records.
    """

    __tablename__ = "workflow_runs"

    workflow_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    workflow_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    definition_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    execution_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    heartbeat_interval_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    steps: Mapped[list["WorkflowStep"]] = relationship(
        back_populates="workflow_run",
        cascade="all, delete-orphan",
        order_by="WorkflowStep.position",
    )


class WorkflowStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Represent one recoverable milestone within a workflow run.

    Each step has a stable key so the workflow engine can identify it
    across retries and resume operations.
    """

    __tablename__ = "workflow_steps"

    __table_args__ = (
        UniqueConstraint(
            "workflow_run_id",
            "step_key",
            name="uq_workflow_steps_run_step_key",
        ),
        Index(
            "ix_workflow_steps_run_status",
            "workflow_run_id",
            "status",
        ),
    )

    workflow_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_key: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    step_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    input_data: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    output_data: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    workflow_run: Mapped["WorkflowRun"] = relationship(
        back_populates="steps",
    )
