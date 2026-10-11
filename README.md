# Bulk Certificate Generator

A backend API that accepts bulk certificate generation requests, validates
recipient data, generates one personalized PDF certificate per recipient
(ReportLab), tracks per-job progress, and serves the files for download.

**Stack:** Python 3.11 · FastAPI · PostgreSQL · SQLAlchemy 2 · Pydantic v2 · ReportLab · Pytest

## 1. Project overview
Job-based API: a client POSTs one request containing event details and a list
of recipients. The service creates a *generation job*, renders a certificate
for every valid recipient in the background, tracks per-recipient outcomes,
and exposes endpoints to poll progress and download the PDFs.

## 2. Features
- Bulk generation: 1-500 recipients in one request
- Strict validation with clear 422 errors (Pydantic)
- Per-recipient failure isolation -> PARTIALLY_COMPLETED
- Pollable progress (total / successful / failed / percent)
- PDF download per certificate with safe, server-generated filenames
- Centralized error handling; no stack traces in responses
- Automated test suite with per-test database + storage isolation
- Interactive docs at /docs and /openapi.json

## 3. Technology stack
| Technology | Role |
|---|---|
| Python 3.11 | Language |
| FastAPI | Web framework, validation, DI, background tasks |
| PostgreSQL + psycopg | Relational database |
| SQLAlchemy 2.x | Typed ORM |
| Pydantic v2 (+ settings, email-validator) | Validation + config |
| ReportLab | PDF rendering |
| Uvicorn | ASGI server |
| Pytest + httpx | Tests |

## 4. Architecture
Client -> POST /api/jobs/ -> Pydantic validation -> job + recipient rows -> PostgreSQL
       -> 201 (PENDING) -> background task (threadpool): per recipient -> generate PDF
       -> update row -> commit -> final status (COMPLETED / PARTIALLY_COMPLETED / FAILED)
Client -> GET /api/jobs/{id}/ (poll) -> list certificates -> download PDFs

Layers: app/api/ (HTTP) -> app/schemas/ (contracts) -> app/models/ (ORM) ->
app/services/ (business logic) -> templates/ (pure ReportLab drawing).

## 5. Project structure
app/main.py, config.py, database.py, init_db.py; app/api/ (jobs, certificates);
app/models/ (job, certificate); app/schemas/; app/services/ (certificate_generator,
job_processor); app/utils/exceptions.py; templates/certificate_template.py;
storage/ (generated PDFs, git-ignored); tests/.

## 6. Database design
generation_jobs: id, event_name, certificate_title, issue_date, status
(PENDING/PROCESSING/COMPLETED/PARTIALLY_COMPLETED/FAILED), total_count,
successful_count, failed_count, created_at, completed_at.
certificates: id, job_id (FK, cascade, indexed), recipient_name, recipient_email,
status (PENDING/GENERATED/FAILED), certificate_code (UNIQUE, printed on the PDF),
file_path, error_message, created_at, completed_at.
Recipients and certificates share one table on purpose: a recipient exists only
inside a job and produces exactly one certificate, so a separate table would add
a join without enabling any needed query. Progress = (successful + failed) /
total x 100.

## 7. Certificate generation flow
process_job -> per certificate: new CERT-XXXXXXXX code ->
templates/certificate_template.render_certificate() draws an A4-landscape PDF
(double border, title, auto-shrinking recipient name, event, issue date,
certificate ID) -> code + absolute file path stored on the row. Files land in
storage/certificates/job_<job_id>/.

## 8. Bulk processing approach
FastAPI BackgroundTasks (sync task -> threadpool; event loop never blocks).
Each certificate is generated and committed individually inside a narrow
try/except: a failure records FAILED + a short error message on that row and
moves on. Final status is derived from the counters. A crashed task is marked
FAILED by a last-resort guard; re-runs skip non-PENDING rows (resumable).

## 9. Error handling
| Situation | HTTP |
|---|---|
| Invalid request data | 422 (field-level detail) |
| Job / certificate not found | 404 |
| Certificate not generated yet | 409 |
| Generated file missing on disk | 404 |
| Unexpected/database errors | 500 (generic body; traceback only in logs) |

## 10. API documentation
| Method | Path | Purpose |
|---|---|---|
| POST | /api/jobs/ | Create bulk job -> 201 |
| GET | /api/jobs/{job_id}/ | Status + progress |
| GET | /api/jobs/{job_id}/certificates/ | Per-recipient results |
| GET | /api/certificates/{id}/download | Download PDF |
| GET | /health | Liveness |

## 11. Setup instructions (local)
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements-dev.txt
    psql -U postgres -c "CREATE DATABASE certificate_db;"
    cp .env.example .env
    python -m app.init_db
    uvicorn app.main:app --reload

### Developing in GitHub Codespaces (zero local setup)
This repo ships a .devcontainer/ provisioning Python 3.11 + PostgreSQL 16:
Code -> Codespaces -> Create codespace, then create a venv, install deps,
copy .env.example to .env and switch the host from localhost to db, then
python -m app.init_db and uvicorn app.main:app --reload (open forwarded
port 8000).

## 12. Environment variables
| Variable | Default | Description |
|---|---|---|
| DATABASE_URL | postgres@localhost:5432/certificate_db | SQLAlchemy URL (psycopg) |
| OUTPUT_DIR | storage/certificates | PDF output folder |
| TEST_DATABASE_URL | temp SQLite | Optional: real DB for tests |

## 13. Running locally
From the project root: python -m app.init_db (once), then
uvicorn app.main:app --reload -> http://127.0.0.1:8000/docs

## 14. Running tests
pytest - no PostgreSQL needed. Every test gets a fresh throwaway SQLite
database (schema included) and a temporary output folder; the
get_session_factory dependency is overridden so the whole app, including
background tasks, runs against the test database. Failures are simulated by
monkeypatching the generator to raise for one recipient. Set
TEST_DATABASE_URL to run the same suite against PostgreSQL.

## 15. Example API request
    curl -X POST http://127.0.0.1:8000/api/jobs/ -H "Content-Type: application/json" \
      -d '{"event_name":"Python Workshop 2026","certificate_title":"Certificate of Completion","issue_date":"2026-10-08","recipients":[{"name":"Vaishnavi Dhule","email":"vaishnavi@example.com"}]}'

## 16. Example responses
Create (201): {"id":1,"status":"PENDING","total":1,"successful":0,"failed":0,"progress":0,...}
Status (200): {"id":1,"status":"COMPLETED","total":1,"successful":1,"failed":0,"progress":100,...}
Certificates (200): [{"id":1,"job_id":1,"recipient_name":"Vaishnavi Dhule","status":"GENERATED","certificate_code":"CERT-3FA2C1B9","error_message":null,"download_url":"/api/certificates/1/download",...}]
Download (200): application/pdf file attachment.

## 17. Design decisions
1. BackgroundTasks over synchronous (non-blocking, pollable) and over
   Celery/Redis (unjustified extra infrastructure at this scale)
2. Per-certificate commits -> durable, pollable progress + clean isolation
3. One certificates table (see section 6)
4. Sync SQLAlchemy + threadpool (ReportLab is CPU-bound; async adds no value)
5. Integer PKs + unique certificate_code as safe public identifier/filename
6. Explicit init_db script (no startup side effects; Alembic later)
7. Centralized exception types + handlers

## 18. Trade-offs
- Background tasks die with the process -> queue + workers in production
- SQLite-based tests trade a little fidelity for zero setup
- 500-recipient cap per request; duplicate emails allowed
- No pagination (<=500 rows/job), no auth (out of scope)

## 19. Learning
- Designed a job-based backend API with status/progress tracking
- Relational modeling with SQLAlchemy 2.x (relationships, FKs, constraints)
- PDF generation with ReportLab (canvas, font metrics, auto-fit)
- Validation and failure isolation in bulk processing
- Automated API testing (dependency overrides, per-test DB isolation)

## 20. Future scope
Background workers/queues for very large jobs, retries, Alembic migrations,
cloud object storage (S3), authentication, email delivery, ZIP downloads,
pagination + job listing, monitoring/logging.
