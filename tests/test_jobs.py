"""Tests for job creation, request validation, and job status."""

import pytest

from app.schemas.job import MAX_RECIPIENTS_PER_JOB

VALID_PAYLOAD = {
    "event_name": "Python Workshop 2026",
    "certificate_title": "Certificate of Completion",
    "issue_date": "2026-10-08",
    "recipients": [
        {"name": "Vaishnavi Dhule", "email": "vaishnavi@example.com"},
        {"name": "Rahul Sharma", "email": "rahul@example.com"},
    ],
}


def _payload_without(field: str) -> dict:
    return {key: value for key, value in VALID_PAYLOAD.items() if key != field}


class TestCreateJob:
    def test_create_job_returns_201_with_initial_job_state(self, client):
        response = client.post("/api/jobs/", json=VALID_PAYLOAD)

        assert response.status_code == 201
        body = response.json()
        assert isinstance(body["id"], int)
        assert body["status"] == "PENDING"
        assert body["total"] == 2
        assert body["successful"] == 0
        assert body["failed"] == 0
        assert body["progress"] == 0
        assert body["completed_at"] is None

    def test_background_task_processes_job_after_response(self, client):
        create_response = client.post("/api/jobs/", json=VALID_PAYLOAD)
        job_id = create_response.json()["id"]

        status_response = client.get(f"/api/jobs/{job_id}/")

        assert status_response.status_code == 200
        status = status_response.json()
        assert status["status"] == "COMPLETED"
        assert status["successful"] == 2
        assert status["failed"] == 0
        assert status["progress"] == 100
        assert status["completed_at"] is not None

    def test_recipients_are_persisted_as_certificate_rows(self, client):
        job_id = client.post("/api/jobs/", json=VALID_PAYLOAD).json()["id"]

        certificates = client.get(f"/api/jobs/{job_id}/certificates/").json()

        assert len(certificates) == 2
        assert {c["recipient_name"] for c in certificates} == {
            "Vaishnavi Dhule",
            "Rahul Sharma",
        }


INVALID_PAYLOAD_CASES = [
    ("empty-recipients", {**VALID_PAYLOAD, "recipients": []}),
    ("missing-recipient-name", {**VALID_PAYLOAD, "recipients": [{"email": "a@example.com"}]}),
    ("blank-recipient-name", {**VALID_PAYLOAD, "recipients": [{"name": "   ", "email": "a@example.com"}]}),
    ("missing-recipient-email", {**VALID_PAYLOAD, "recipients": [{"name": "A B"}]}),
    ("invalid-recipient-email", {**VALID_PAYLOAD, "recipients": [{"name": "A B", "email": "not-an-email"}]}),
    ("non-iso-issue-date", {**VALID_PAYLOAD, "issue_date": "08/10/2026"}),
    ("issue-date-not-a-date", {**VALID_PAYLOAD, "issue_date": "yesterday"}),
    ("missing-event-name", _payload_without("event_name")),
    ("blank-event-name", {**VALID_PAYLOAD, "event_name": "   "}),
    ("missing-certificate-title", _payload_without("certificate_title")),
]


@pytest.mark.parametrize(
    ("case", "payload"),
    INVALID_PAYLOAD_CASES,
    ids=[case for case, _ in INVALID_PAYLOAD_CASES],
)
def test_invalid_create_requests_return_422(client, case, payload):
    response = client.post("/api/jobs/", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]


def test_more_recipients_than_allowed_returns_422(client):
    payload = {
        **VALID_PAYLOAD,
        "recipients": [
            {"name": f"Person {index}", "email": f"person{index}@example.com"}
            for index in range(MAX_RECIPIENTS_PER_JOB + 1)
        ],
    }
    assert client.post("/api/jobs/", json=payload).status_code == 422


class TestJobStatus:
    def test_unknown_job_returns_404(self, client):
        response = client.get("/api/jobs/999/")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_non_integer_job_id_returns_422(self, client):
        assert client.get("/api/jobs/not-a-number/").status_code == 422