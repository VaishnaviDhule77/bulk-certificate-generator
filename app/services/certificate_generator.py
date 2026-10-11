"""Turns a pending certificate row into a generated PDF on disk."""

import secrets
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.models.certificate import Certificate
from templates.certificate_template import CertificateData, render_certificate

CODE_PREFIX = "CERT"
CODE_RANDOM_BYTES = 4  # 4 bytes -> 8 hexadecimal characters


@dataclass(frozen=True)
class GenerationResult:
    """Outcome of a successful certificate generation attempt."""

    certificate_code: str
    file_path: Path


def new_certificate_code() -> str:
    """Return a new certificate code such as ``CERT-4F2A9C1B``."""
    return f"{CODE_PREFIX}-{secrets.token_hex(CODE_RANDOM_BYTES).upper()}"


def generate_certificate(certificate: Certificate) -> GenerationResult:
    """Render the PDF for one certificate row; return its code and path.

    Any error raised by ReportLab or the filesystem bubbles up so the job
    processor can record a per-certificate failure.
    """
    certificate_code = new_certificate_code()
    output_path = _build_output_path(certificate.job_id, certificate_code)

    data = CertificateData(
        title=certificate.job.certificate_title,
        recipient_name=certificate.recipient_name,
        event_name=certificate.job.event_name,
        issue_date=certificate.job.issue_date,
        certificate_code=certificate_code,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    render_certificate(data, output_path)

    return GenerationResult(
        certificate_code=certificate_code, file_path=output_path.resolve()
    )


def _build_output_path(job_id: int, certificate_code: str) -> Path:
    """Predictable on-disk location for one certificate PDF."""
    return settings.output_dir / f"job_{job_id}" / f"{certificate_code}.pdf"