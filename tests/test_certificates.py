"""Tests for certificate listing, downloading, and error handling."""

from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_db
from app.main import app

RECIPIENT = {"name": "Vaishnavi Dhule", "email": "vaishnavi@example.com"}
PAYLOAD = {
    "event_name": "Python Workshop 2026",
    "certificate_title": "Certificate of Completion",
    "issue_date": "2026-10-08",
    "recipients": [RECIPIENT],
}


def _create_job(client) -> int:
    response = client.post("/api/jobs/", json=PAYLOAD)
    assert response.status_code == 201
    return response.json()["id"]


class TestListCertificates:
    def test_list_returns_generated_certificate_records(self, client):
        job_id = _create_job(client)

        response = client.get(f"/api/jobs/{job_id}/certificates/")

        assert response.status_code == 200
        certificates = response.json()
        assert len(certificates) == 1

        record = certificates[0]
        assert record["job_id"] == job_id
        assert record["recipient_name"] == RECIPIENT["name"]
        assert record["recipient_email"] == RECIPIENT["email"]
        assert record["status"] == "GENERATED"
        assert record["certificate_code"].startswith("CERT-")
        assert record["error_message"] is None
        assert record["download_url"] == f"/api/certificates/{record['id']}/download"

    def test_list_for_unknown_job_returns_404(self, client):
        assert client.get("/api/jobs/1234/certificates/").status_code == 404


class TestDownloadCertificate:
    def test_download_returns_pdf_file(self, client):
        job_id = _create_job(client)
        certificate_id = client.get(f"/api/jobs/{job_id}/certificates/").json()[0]["id"]

        response = client.get(f"/api/certificates/{certificate_id}/download")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/pdf")
        assert "attachment" in response.headers.get("content-disposition", "")
        assert response.content[:5] == b"%PDF-"

    def test_download_unknown_certificate_returns_404(self, client):
        assert client.get("/api/certificates/9876/download").status_code == 404

    def test_download_certificate_that_is_not_ready_returns_409(self, client, monkeypatch):
        monkeypatch.setattr("app.api.jobs.process_job", lambda **kwargs: None)

        job_id = _create_job(client)
        certificate_id = client.get(f"/api/jobs/{job_id}/certificates/").json()[0]["id"]

        response = client.get(f"/api/certificates/{certificate_id}/download")

        assert response.status_code == 409
        assert "not ready" in response.json()["detail"]

    def test_download_when_file_was_deleted_returns_404(self, client):
        job_id = _create_job(client)
        record = client.get(f"/api/jobs/{job_id}/certificates/").json()[0]

        file_path = (
            settings.output_dir / f"job_{job_id}" / f"{record['certificate_code']}.pdf"
        )
        assert file_path.is_file()
        file_path.unlink()

        response = client.get(f"/api/certificates/{record['id']}/download")
        assert response.status_code == 404


class TestCentralisedErrorHandling:
    def test_unhandled_errors_return_sanitized_500(self):
        def broken_database_session():
            raise RuntimeError("internal detail that must not leak")

        app.dependency_overrides[get_db] = broken_database_session
        try:
            plain_client = TestClient(app, raise_server_exceptions=False)
            response = plain_client.get("/api/jobs/1/")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error. Please try again later."
        assert "must not leak" not in response.text