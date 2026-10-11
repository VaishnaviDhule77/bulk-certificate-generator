"""Pydantic schemas for job requests and job status responses."""

from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.job import JobStatus

MAX_RECIPIENTS_PER_JOB = 500


def _strip_and_require(value: str) -> str:
    """Trim whitespace and reject values that contain nothing else."""
    value = value.strip()
    if not value:
        raise ValueError("must not be empty or only whitespace")
    return value


class RecipientIn(BaseModel):
    """A single recipient submitted in a generation request."""

    name: str = Field(max_length=150, examples=["Vaishnavi Dhule"])
    email: EmailStr = Field(max_length=254, examples=["vaishnavi@example.com"])

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        return _strip_and_require(value)


class JobCreateRequest(BaseModel):
    """Request body for POST /api/jobs/."""

    event_name: str = Field(max_length=200, examples=["Python Workshop 2026"])
    certificate_title: str = Field(
        max_length=200, examples=["Certificate of Completion"]
    )
    issue_date: date
    recipients: list[RecipientIn] = Field(
        min_length=1, max_length=MAX_RECIPIENTS_PER_JOB
    )

    @field_validator("event_name", "certificate_title")
    @classmethod
    def text_fields_must_not_be_blank(cls, value: str) -> str:
        return _strip_and_require(value)


class JobStatusResponse(BaseModel):
    """Response for both job creation (201) and job status (200)."""

    id: int
    status: JobStatus
    event_name: str
    certificate_title: str
    issue_date: date
    total: int
    successful: int
    failed: int
    progress: int
    created_at: datetime
    completed_at: datetime | None = None