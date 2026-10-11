"""Background processing of a certificate generation job.

Design goals:
- run AFTER the HTTP response has been sent (FastAPI BackgroundTasks),
- process every recipient, even if some of them fail,
- commit per certificate so progress is durable and pollable,
- never leak stack traces into API responses (errors go to logs + rows).
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.models.certificate import Certificate, CertificateStatus
from app.models.job import GenerationJob, JobStatus
from app.services.certificate_generator import generate_certificate

logger = logging.getLogger(__name__)

MAX_ERROR_MESSAGE_LENGTH = 500


def process_job(job_id: int, session_factory: sessionmaker[Session]) -> None:
    """Generate every pending certificate that belongs to ``job_id``."""
    try:
        with session_factory() as db:
            job = db.get(GenerationJob, job_id)
            if job is None:
                logger.error("Job %s not found; nothing to process.", job_id)
                return

            job.status = JobStatus.PROCESSING
            db.commit()

            for certificate in job.certificates:
                _process_single_certificate(db, job, certificate)

            _finalize_job(db, job)
    except Exception:
        # Last-resort guard: a crashed job must never stay PROCESSING forever.
        logger.exception("Job %s crashed unexpectedly.", job_id)
        _mark_job_failed(session_factory, job_id)


def _process_single_certificate(
    db: Session, job: GenerationJob, certificate: Certificate
) -> None:
    """Attempt one certificate; record success or failure; commit.

    The try/except is deliberately narrow: only the generation call is
    guarded, so one recipient's failure can never stop the others.
    """
    if certificate.status != CertificateStatus.PENDING:
        return  # already processed by an earlier run - makes re-runs safe

    try:
        result = generate_certificate(certificate)
    except Exception as exc:
        db.rollback()  # keep the session usable even if the error came from the DB
        logger.exception("Certificate %s (job %s) failed.", certificate.id, job.id)
        certificate.status = CertificateStatus.FAILED
        certificate.error_message = _short_error_message(exc)
        certificate.completed_at = datetime.now(timezone.utc)
        job.failed_count += 1
    else:
        certificate.status = CertificateStatus.GENERATED
        certificate.certificate_code = result.certificate_code
        certificate.file_path = str(result.file_path)
        certificate.completed_at = datetime.now(timezone.utc)
        job.successful_count += 1

    db.commit()  # per-certificate commit -> durable, pollable progress


def _finalize_job(db: Session, job: GenerationJob) -> None:
    """Derive the final job status from the per-certificate results."""
    if job.failed_count == 0:
        job.status = JobStatus.COMPLETED
    elif job.successful_count == 0:
        job.status = JobStatus.FAILED
    else:
        job.status = JobStatus.PARTIALLY_COMPLETED

    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(
        "Job %s finished: %s successful, %s failed.",
        job.id, job.successful_count, job.failed_count,
    )


def _mark_job_failed(session_factory: sessionmaker[Session], job_id: int) -> None:
    """Best-effort attempt to flag a crashed job as FAILED."""
    try:
        with session_factory() as db:
            job = db.get(GenerationJob, job_id)
            if job is not None and job.status not in (
                JobStatus.COMPLETED,
                JobStatus.PARTIALLY_COMPLETED,
            ):
                job.status = JobStatus.FAILED
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
    except Exception:
        logger.exception("Could not mark job %s as FAILED.", job_id)


def _short_error_message(exc: Exception) -> str:
    """Short, safe message stored on the certificate row (no stack trace)."""
    message = f"{type(exc).__name__}: {exc}"
    return message[:MAX_ERROR_MESSAGE_LENGTH]