"""Import all models so they register on the shared Base.metadata."""

from app.models.certificate import Certificate, CertificateStatus
from app.models.job import GenerationJob, JobStatus

__all__ = ["Certificate", "CertificateStatus", "GenerationJob", "JobStatus"]