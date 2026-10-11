"""HTTP endpoints for creating and inspecting certificate generation jobs."""

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db, get_session_factory
from app.models.certificate import Certificate, CertificateStatus
from app.models.job import GenerationJob, JobStatus
from app.schemas.certificate import CertificateResponse
from app.schemas.job import JobCreateRequest, JobStatusResponse
from app.services.job_processor import process_job
from app.utils.exceptions import NotFoundError

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post(
    "/",
    response_model=JobStatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a bulk certificate generation job",
)
def create_generation_job(
    payload: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    session_factory: sessionmaker[Session] = Depends(get_session_factory),
) -> JobStatusResponse:
    """Validate the request, persist the job and its recipients, then queue
    certificate generation as a background task and return immediately."""
    job = GenerationJob(
        event_name=payload.event_name,
        certificate_title=payload.certificate_title,
        issue_date=payload.issue_date,
        total_count=len(payload.recipients),
        status=JobStatus.PENDING,
    )
    db.add(job)

    for recipient in payload.recipients:
        db.add(
            Certificate(
                job=job,
                recipient_name=recipient.name,
                recipient_email=str(recipient.email),
                status=CertificateStatus.PENDING,
            )
        )

    db.commit()  # job.id is available afterwards (expire_on_commit=False)

    # The task opens its own DB session via the factory (see job_processor).
    background_tasks.add_task(
        process_job, job_id=job.id, session_factory=session_factory
    )

    return _build_job_status(job)


@router.get(
    "/{job_id}/",
    response_model=JobStatusResponse,
    responses={404: {"description": "Job not found"}},
    summary="Get the status and progress of a job",
)
def get_job_status(job_id: int, db: Session = Depends(get_db)) -> JobStatusResponse:
    """Return the current status, counters, and progress of a job."""
    job = _get_job_or_404(db, job_id)
    return _build_job_status(job)


@router.get(
    "/{job_id}/certificates/",
    response_model=list[CertificateResponse],
    responses={404: {"description": "Job not found"}},
    summary="List all certificates of a job",
)
def list_job_certificates(
    job_id: int, db: Session = Depends(get_db)
) -> list[CertificateResponse]:
    """Return one record per recipient, including status, error message and
    the download URL once the certificate has been generated."""
    _get_job_or_404(db, job_id)
    certificates = db.scalars(
        select(Certificate).where(Certificate.job_id == job_id).order_by(Certificate.id)
    ).all()
    return [CertificateResponse.model_validate(c) for c in certificates]


def _get_job_or_404(db: Session, job_id: int) -> GenerationJob:
    """Fetch a job by id or raise the API's standard 404 error."""
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise NotFoundError("Job", job_id)
    return job


def _build_job_status(job: GenerationJob) -> JobStatusResponse:
    """Map a GenerationJob ORM object onto the API response schema."""
    processed = job.successful_count + job.failed_count
    progress = (processed * 100) // job.total_count if job.total_count > 0 else 0
    return JobStatusResponse(
        id=job.id,
        status=job.status,
        event_name=job.event_name,
        certificate_title=job.certificate_title,
        issue_date=job.issue_date,
        total=job.total_count,
        successful=job.successful_count,
        failed=job.failed_count,
        progress=progress,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )