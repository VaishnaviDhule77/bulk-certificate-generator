"""Certificate ORM model (one row per recipient per job) and its status enum."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.job import GenerationJob


class CertificateStatus(str, enum.Enum):
    """Per-certificate outcomes."""

    PENDING = "PENDING"
    GENERATED = "GENERATED"
    FAILED = "FAILED"


class Certificate(Base):
    """One recipient inside one job, plus the outcome of their certificate."""

    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("generation_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_name: Mapped[str] = mapped_column(String(150), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(254), nullable=False)
    status: Mapped[CertificateStatus] = mapped_column(
        SAEnum(CertificateStatus, native_enum=False, length=32),
        default=CertificateStatus.PENDING,
        nullable=False,
        index=True,
    )
    certificate_code: Mapped[str | None] = mapped_column(
        String(20), nullable=True, unique=True
    )
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    job: Mapped["GenerationJob"] = relationship(back_populates="certificates")

    def __repr__(self) -> str:
        return (
            f"<Certificate id={self.id} job_id={self.job_id} "
            f"name={self.recipient_name!r} status={self.status}>"
        )