"""FastAPI application entry point."""

import logging

from fastapi import FastAPI

from app.api import certificates, jobs
from app.utils.exceptions import register_exception_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

app = FastAPI(
    title="Bulk Certificate Generator API",
    description=(
        "REST API that accepts bulk certificate requests, validates recipient "
        "data, generates one PDF certificate per recipient from a predefined "
        "ReportLab template, tracks per-job progress, and serves the "
        "generated files for download."
    ),
    version="1.0.0",
)

app.include_router(jobs.router)
app.include_router(certificates.router)
register_exception_handlers(app)


@app.get("/health", tags=["health"], summary="Liveness check")
def health_check() -> dict[str, str]:
    """Simple endpoint to verify the service is running."""
    return {"status": "ok"}
