"""HTTP endpoint for downloading generated certificates."""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.certificate import Certificate, CertificateStatus
from app.utils.exceptions import ConflictError, NotFoundError

router = APIRouter(prefix="/api/certificates", tags=["certificates"])


@router.get(
    "/{certificate_id}/download",
    responses={
        404: {"description": "Certificate or generated file not found"},
        409: {"description": "Certificate exists but has not been generated yet"},
    },
    summary="Download a generated certificate PDF",
)
def download_certificate(
    certificate_id: int, db: Session = Depends(get_db)
) -> FileResponse:
    """Stream the generated PDF file for a single certificate."""
    certificate = db.get(Certificate, certificate_id)
    if certificate is None:
        raise NotFoundError("Certificate", certificate_id)

    if certificate.status != CertificateStatus.GENERATED:
        raise ConflictError(
            f"Certificate {certificate_id} is not ready for download "
            f"(current status: {certificate.status.value})."
        )

    file_path = Path(certificate.file_path or "")
    if not file_path.is_file():
        raise NotFoundError(
            "Certificate file", certificate.certificate_code or certificate_id
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"{certificate.certificate_code}.pdf",
    )