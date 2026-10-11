"""Tests for the generation pipeline, bulk processing, and failure isolation."""

from datetime import date

from app.config import settings
from app.models.certificate import Certificate
from app.models.job import GenerationJob
from app.services import job_processor
from app.services.certificate_generator import generate_certificate

RECIPIENTS = [
    {"name": "Vaishnavi Dhule", "email": "vaishnavi@example.com"},
    {"name": "Rahul Sharma", "email": "rahul@example.com"},
    {"name": "Priya Patel", "email": "priya@example.com"},
]

PAYLOAD = {
    "event_name": "Python Workshop 2026",
    "certificate_title": "Certificate of Completion",
    "issue_date": "2026-10-08",
    "recipients": RECIPIENTS,
}


def _create_job(client, recipients) -> int:
    payload = {**PAYLOAD, "recipients": recipients}
    response = client.post("/api/jobs/", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def _job_status(client, job_id) -> dict:
    return client.get(f"/api/jobs/{job_id}/").json()


def _certificates(client, job_id) -> list:
    return client.get(f"/api/jobs/{job_id}/certificates/").json()


class TestSuccessfulGeneration:
    def test_job_completes_and_creates_pdf_files(self, client):
        job_id = _create_job(client, RECIPIENTS[:2])

        status = _job_status(client, job_id)
        assert status["status"] == "COMPLETED"
        assert status["successful"] == 2
        assert status["failed"] == 0
        assert status["progress"] == 100

        for certificate in _certificates(client, job_id):
            assert certificate["status"] == "GENERATED"
            assert certificate["error_message"] is None
            assert certificate["certificate_code"].startswith("CERT-")

            file_path = (
                settings.output_dir
                / f"job_{job_id}"
                / f"{certificate['certificate_code']}.pdf"
            )
            assert file_path.is_file(), f"expected PDF at {file_path}"

            with file_path.open("rb") as pdf_file:
                assert pdf_file.read(5) == b"%PDF-"


class TestUnitGeneration:
    def test_generate_certificate_writes_pdf_and_returns_code(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "output_dir", tmp_path)

        job = GenerationJob(
            event_name="Python Workshop 2026",
            certificate_title="Certificate of Completion",
            issue_date=date(2026, 10, 8),
        )
        certificate = Certificate(
            job_id=1,
            job=job,
            recipient_name="Unit Test User",
            recipient_email="unit@example.com",
        )

        result = generate_certificate(certificate)

        assert result.certificate_code.startswith("CERT-")
        assert result.file_path.is_file()
        assert result.file_path.parent == (tmp_path / "job_1").resolve()


class TestBulkFailureIsolation:
    def test_one_failure_does_not_stop_other_certificates(self, client, monkeypatch):
        original_generate = job_processor.generate_certificate

        def generate_that_fails_for_one_recipient(certificate):
            if certificate.recipient_name == "Broken Recipient":
                raise RuntimeError("simulated PDF rendering failure")
            return original_generate(certificate)

        monkeypatch.setattr(
            job_processor, "generate_certificate", generate_that_fails_for_one_recipient
        )

        recipients = RECIPIENTS[:2] + [
            {"name": "Broken Recipient", "email": "broken@example.com"}
        ]
        job_id = _create_job(client, recipients)

        status = _job_status(client, job_id)
        assert status["status"] == "PARTIALLY_COMPLETED"
        assert status["successful"] == 2
        assert status["failed"] == 1
        assert status["progress"] == 100

        certificates = _certificates(client, job_id)
        failed = [c for c in certificates if c["status"] == "FAILED"]
        successful = [c for c in certificates if c["status"] == "GENERATED"]

        assert len(failed) == 1
        assert "simulated PDF rendering failure" in failed[0]["error_message"]
        assert len(successful) == 2

    def test_job_where_every_certificate_fails_is_failed(self, client, monkeypatch):
        def always_fail(certificate):
            raise RuntimeError("boom")

        monkeypatch.setattr(job_processor, "generate_certificate", always_fail)

        job_id = _create_job(client, RECIPIENTS[:2])

        status = _job_status(client, job_id)
        assert status["status"] == "FAILED"
        assert status["successful"] == 0
        assert status["failed"] == 2

        certificates = _certificates(client, job_id)
        assert all(c["status"] == "FAILED" for c in certificates)
        assert all("boom" in c["error_message"] for c in certificates)