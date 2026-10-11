"""Pydantic schema for certificate records returned by the API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, computed_field

from app.models.certificate import CertificateStatus


class CertificateResponse(BaseModel):
    """One recipient's record inside a job, including their outcome."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    recipient_name: str
    recipient_email: EmailStr
    status: CertificateStatus
    certificate_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    @computed_field
    @property
    def download_url(self) -> str:
        """Relative URL the client can use once status is GENERATED."""
        return f"/api/certificates/{self.id}/download"